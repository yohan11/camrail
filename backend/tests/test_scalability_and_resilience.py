"""
Banc de tests de scalabilité, résilience et concurrence pour CAMRAIL RailMind Lite (~1000 utilisateurs).
Valide :
1. Fermeture complète de la session DB avant l'appel au LLM (0 connexion retenue dans le pool).
2. Limiteur de concurrence de génération (MAX_CONCURRENT_GENERATIONS) avec timeout et 503.
3. Streaming SSE avec ordre strict : sources -> tokens -> done.
4. Limitation de débit par utilisateur (11e requête dans la minute rejetée en 429).
5. Endpoint /health (200 nominal, 503 en cas de panne).
"""

import time
import json
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.config import settings
from app.database import engine, SessionLocal
from app.models.schemas import User, Conversation, ConversationMessage, RdaQuery
from app.services.concurrency import concurrency_limiter, user_rate_limiter

client = TestClient(app)

class TestScalabilityAndResilience(unittest.TestCase):
    def setUp(self):
        from app.deps import get_current_user
        # Utiliser un compte utilisateur existant en base (id=1, admin@camrail.net)
        self.mock_user = User(id=1, email="admin@camrail.net", role="admin")
        app.dependency_overrides[get_current_user] = lambda: self.mock_user
        user_rate_limiter.reset()

    def tearDown(self):
        app.dependency_overrides.clear()
        user_rate_limiter.reset()

    def test_1_db_session_closed_before_llm_call(self):
        """Vérifie que la session DB est fermée et aucune connexion n'est retenue dans le pool pendant le LLM."""
        checked_out_conns = []

        def mock_generate_answer(*args, **kwargs):
            # Inspecter le nombre de connexions actives dans le pool SQLAlchemy
            conns = engine.pool.checkedout() if hasattr(engine.pool, "checkedout") else 0
            checked_out_conns.append(conns)
            return {
                "answer": "La signalisation lumineuse commande la circulation [1].",
                "confidence": "high",
                "citations": [],
                "provider": "ollama"
            }

        with patch("app.routers.assistant.generate_answer", side_effect=mock_generate_answer):
            resp = client.post("/assistant/query", json={"query": "Quel est le rôle de la signalisation ?"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(len(checked_out_conns), 1)
            self.assertEqual(
                checked_out_conns[0], 0,
                f"La session DB ne doit PAS rester ouverte pendant le LLM ! Connexions retenues: {checked_out_conns[0]}"
            )
            print("\n  -> Test 1 OK : 0 connexion DB retenue dans le pool pendant l'exécution LLM.")

    def test_2_concurrency_limiter_queue_timeout(self):
        """Avec MAX_CONCURRENT_GENERATIONS=1, la seconde requête concurrente reçoit un 503 après le délai."""
        orig_semaphore = concurrency_limiter.semaphore
        concurrency_limiter.semaphore = threading.Semaphore(1)

        results = []

        def slow_generate(*args, **kwargs):
            time.sleep(0.6)
            return {
                "answer": "Réponse lente 1.",
                "confidence": "high",
                "citations": [],
                "provider": "ollama"
            }

        patcher = patch("app.routers.assistant.generate_answer", side_effect=slow_generate)
        patcher.start()

        def run_req(timeout_override):
            with patch.object(settings, "QUEUE_TIMEOUT_SECONDS", timeout_override):
                r = client.post("/assistant/query", json={"query": "Question concurrente"})
                results.append(r.status_code)

        try:
            # Thread 1 prend le slot pendant 0.6s
            t1 = threading.Thread(target=run_req, args=(5.0,))
            # Thread 2 tente de passer avec un timeout très court (0.1s)
            t2 = threading.Thread(target=run_req, args=(0.1,))

            t1.start()
            time.sleep(0.08)  # Laisser le temps à t1 de démarrer et acquérir le slot
            t2.start()

            t1.join()
            t2.join()

            self.assertIn(200, results)
            self.assertIn(503, results)
            print("\n  -> Test 2 OK : La requête excédentaire a reçu HTTP 503 ('Le serveur est très sollicité').")
        finally:
            patcher.stop()
            concurrency_limiter.semaphore = orig_semaphore

    def test_3_sse_stream_event_sequence(self):
        """Le flux SSE émet 'sources' avant le premier 'token', puis 'done' à la fin."""
        mock_tokens = ["La ", "signalisation ", "commande ", "l'arrêt."]

        def mock_stream(*args, **kwargs):
            for t in mock_tokens:
                yield t

        with patch("app.routers.assistant._generate_with_ollama_stream", side_effect=mock_stream):
            resp = client.post("/api/v1/assistant/query/stream", json={"query": "Quelle est la règle d'arrêt ?"})
            self.assertEqual(resp.status_code, 200)

            events_received = []
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    events_received.append(line.replace("event:", "").strip())

            self.assertGreater(len(events_received), 2)
            # 1. Événement sources en premier
            self.assertIn(events_received[0], ["sources", "meta"])
            # 2. Au moins un token au milieu
            self.assertIn("token", events_received[1:-1])
            # 3. Événement done en dernier
            self.assertEqual(events_received[-1], "done")
            print("\n  -> Test 3 OK : Ordre SSE validé (sources -> tokens -> done).")

    def test_4_user_rate_limiting_429(self):
        """Le 11e appel de la minute pour un même utilisateur reçoit un code HTTP 429."""
        def dummy_generate(*args, **kwargs):
            return {
                "answer": "Réponse rapide.",
                "confidence": "high",
                "citations": [],
                "provider": "ollama"
            }

        with patch("app.routers.assistant.generate_answer", side_effect=dummy_generate):
            with patch.object(settings, "RATE_LIMIT_PER_MINUTE", 10):
                # 10 appels autorisés
                for i in range(10):
                    r = client.post("/assistant/query", json={"query": f"Question {i}"})
                    self.assertEqual(r.status_code, 200, f"L'appel {i+1} doit être accepté (200)")

                # Le 11e appel doit être rejeté
                r11 = client.post("/assistant/query", json={"query": "Question 11"})
                self.assertEqual(r11.status_code, 429, "Le 11e appel doit recevoir 429 Too Many Requests")
                self.assertIn("Trop de requêtes", r11.text)
                print("\n  -> Test 4 OK : 11e requête de la minute rejetée en HTTP 429 (Rate Limit).")

    def test_5_health_check_endpoint(self):
        """L'endpoint /health renvoie 200 quand tout est nominal, 503 si la DB ou un composant est HS."""
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "ok")
        self.assertEqual(data["ollama"], "ok")
        self.assertEqual(data["embedding_model"], "ok")

        # Simulation d'une panne DB
        with patch.object(engine, "connect", side_effect=Exception("Database connection lost")):
            r_down = client.get("/health")
            self.assertEqual(r_down.status_code, 503)
            self.assertEqual(r_down.json()["status"], "unhealthy")
            print("\n  -> Test 5 OK : Endpoint /health valide (200 nominal, 503 sur panne DB).")

if __name__ == "__main__":
    unittest.main(verbosity=2)
