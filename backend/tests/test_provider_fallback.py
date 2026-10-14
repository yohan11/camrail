import os
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from fastapi import HTTPException, status

from app.main import app
from app.config import settings

client = TestClient(app)

class TestLocalProviderAndError(unittest.TestCase):
    def setUp(self):
        from app.deps import get_current_user
        from app.models.schemas import User
        
        self.mock_user = User(id=1, email="test@camrail.net", role="admin")
        app.dependency_overrides[get_current_user] = lambda: self.mock_user
        
        self.query_payload = {
            "query": "Quel est le rôle de la signalisation ferroviaire ?"
        }
        settings.LLM_PROVIDER = "ollama"

    def tearDown(self):
        app.dependency_overrides.clear()
        
    def _check_ollama_available(self):
        try:
            r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def test_1_nominal_ollama_local(self):
        print("\n--- Test 1: Exécution nominale 100% locale (Ollama exclusif) ---")
        if not self._check_ollama_available():
            print("SKIPPED: Ollama n'est pas démarré localement.")
            return

        response = client.post("/assistant/query", json=self.query_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"Réponse: {data['answer'][:80]}...")
        print(f"Provider utilisé: {data.get('provider')}")
        self.assertEqual(data.get("provider"), "ollama")

    @patch("app.services.generation._generate_with_ollama", side_effect=HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Le moteur de réponse local est indisponible"
    ))
    def test_2_ollama_offline_returns_503_no_external_fallback(self, mock_ollama):
        print("\n--- Test 2: Ollama indisponible -> Erreur 503 stricte sans repli externe ---")
        response = client.post("/assistant/query", json=self.query_payload)
        self.assertEqual(response.status_code, 503)
        self.assertIn("Le moteur de réponse local est indisponible", response.text)
        print("  -> OK : HTTP 503 renvoyé avec message clair en français.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
