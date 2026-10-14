import json
import time
import random
import os
from pathlib import Path
from locust import HttpUser, task, between, events

# Charger les questions du golden set pour rejouer des cas réels
GOLDEN_SET_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / "golden_set.json"
QUESTIONS = [
    "Quel est le rôle de la signalisation ferroviaire ?",
    "En quoi consiste la maintenance préventive des voies ?",
    "Quelles sont les règles de composition d'une rame de train ?",
    "Quels éléments composent une voie ferrée classique ?",
    "Comment est organisé le système de cantonnement ferroviaire ?"
]

if GOLDEN_SET_PATH.exists():
    try:
        with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            extracted = [item.get("question") for item in data if item.get("question")]
            if extracted:
                QUESTIONS = extracted
    except Exception as e:
        print(f"Erreur lors du chargement de golden_set.json ({e}), utilisation des questions par défaut.")

class RailMindLoadTestUser(HttpUser):
    wait_time = between(2, 6)  # Pause réaliste entre deux questions d'un utilisateur

    def on_start(self):
        """Authentification de l'utilisateur virtuel et récupération du token JWT."""
        login_data = {
            "username": "readonly@camrail.net",
            "password": "readonlypassword"
        }
        # Tenter d'abord /api/v1/auth/login puis /auth/login
        resp = self.client.post("/api/v1/auth/login", data=login_data, name="Auth_Login")
        if resp.status_code != 200:
            resp = self.client.post("/auth/login", data=login_data, name="Auth_Login_Fallback")
            
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            self.client.headers["Authorization"] = f"Bearer {token}"
        else:
            print(f"Échec d'authentification ({resp.status_code}): {resp.text}")

    @task(3)
    def query_streaming(self):
        """Test de l'endpoint SSE Streaming avec mesure du Time To First Token (TTFT)."""
        question = random.choice(QUESTIONS)
        payload = {
            "query": question,
            "language": "fr"
        }
        
        start_time = time.time()
        ttft = None
        first_token_recorded = False

        with self.client.post(
            "/api/v1/assistant/query/stream",
            json=payload,
            stream=True,
            name="Assistant_Query_Stream",
            catch_response=True
        ) as response:
            if response.status_code in [200, 429, 503]:
                if response.status_code == 429:
                    response.success()  # Taux de limitation normal attendu sous charge
                    return
                elif response.status_code == 503:
                    response.success()  # File d'attente pleine normale sous saturation
                    return

                # Lecture du flux SSE ligne par ligne
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                        if decoded.startswith("event: token") and not first_token_recorded:
                            ttft = (time.time() - start_time) * 1000
                            first_token_recorded = True
                            self.environment.events.request.fire(
                                request_type="SSE_STREAM",
                                name="Time_To_First_Token",
                                response_time=ttft,
                                response_length=0,
                                exception=None
                            )
                total_duration = (time.time() - start_time) * 1000
                response.success()
            else:
                response.failure(f"Status inattendu: {response.status_code} - {response.text[:100]}")

    @task(1)
    def query_sync(self):
        """Test de l'endpoint synchrone standard."""
        question = random.choice(QUESTIONS)
        payload = {
            "query": question,
            "language": "fr"
        }
        with self.client.post(
            "/api/v1/assistant/query",
            json=payload,
            name="Assistant_Query_Sync",
            catch_response=True
        ) as response:
            if response.status_code in [200, 429, 503]:
                response.success()
            else:
                response.failure(f"Status inattendu: {response.status_code} - {response.text[:100]}")

    @task(1)
    def health_check(self):
        """Surveillance de santé du serveur sans auth."""
        self.client.get("/health", name="Health_Check")
