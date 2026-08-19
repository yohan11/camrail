import os
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)

class TestProviderFallback(unittest.TestCase):
    def setUp(self):
        # On a besoin d'un token d'auth admin pour passer le middleware facilement
        # Par simplicité on peut bypass le deps d'authentification ou utiliser un token existant.
        # Mais le plus simple est d'override le get_current_user
        from app.deps import get_current_user
        from app.models.schemas import User
        
        # Override du get_current_user pour retourner un admin fictif
        self.mock_user = User(id=1, email="test@camrail.net", role="admin")
        app.dependency_overrides[get_current_user] = lambda: self.mock_user
        
        self.query_payload = {
            "query": "Quel est le rôle de la signalisation ferroviaire ?"
        }
        
        # S'assurer qu'on pointe bien sur Gemini par défaut
        settings.LLM_PROVIDER = "gemini"

    def tearDown(self):
        app.dependency_overrides.clear()
        
    def _check_ollama_available(self):
        try:
            r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
            return r.status_code == 200
        except:
            return False

    def test_1_nominal_gemini(self):
        print("\n--- Test 1: Connectivité normale (Gemini par défaut) ---")
        response = client.post("/assistant/query", json=self.query_payload)
        
        if response.status_code != 200:
            print(f"Erreur API: {response.text}")
            
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"Réponse: {data['answer'][:100]}...")
        print(f"Provider utilisé: {data.get('provider')}")
        
        # Si on est vraiment en ligne et avec une clé valide, le provider doit être gemini
        self.assertEqual(data.get("provider"), "gemini")

    @patch("app.services.generation.is_online", return_value=False)
    def test_2_offline_ollama_fallback(self, mock_is_online):
        print("\n--- Test 2: Mode hors ligne (Bascule sur Ollama) ---")
        if not self._check_ollama_available():
            print("SKIPPED: Ollama n'est pas disponible localement pour exécuter ce test.")
            return

        response = client.post("/assistant/query", json=self.query_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        print(f"Réponse: {data['answer'][:100]}...")
        print(f"Provider utilisé: {data.get('provider')}")
        self.assertEqual(data.get("provider"), "ollama")

    @patch("app.services.generation.is_online", return_value=True)
    @patch("app.services.generation._generate_with_gemini", side_effect=Exception("API limit exceeded"))
    def test_3_gemini_error_ollama_fallback(self, mock_gemini, mock_is_online):
        print("\n--- Test 3: Gemini plante (Bascule sur Ollama) ---")
        if not self._check_ollama_available():
            print("SKIPPED: Ollama n'est pas disponible localement pour exécuter ce test.")
            return

        response = client.post("/assistant/query", json=self.query_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        print(f"Réponse: {data['answer'][:100]}...")
        print(f"Provider utilisé: {data.get('provider')}")
        self.assertEqual(data.get("provider"), "ollama")

if __name__ == "__main__":
    unittest.main(verbosity=2)
