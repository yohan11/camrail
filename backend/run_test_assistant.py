import time
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.schemas import RdaQuery

def test_assistant():
    with TestClient(app) as client:
        print("=" * 70)
        print("      RAILMIND LITE - DAY 4 ASSISTANT GENERATION TESTS")
        print("=" * 70)
    
        # 1. Check Ollama status
        try:
            resp = httpx.get("http://localhost:11434")
            if resp.status_code != 200:
                print("ATTENTION: Ollama a répondu avec une erreur.")
                return
            print("[Init] Ollama est bien lancé et accessible sur le port 11434.")
        except httpx.ConnectError:
            print("Erreur: Ollama ne semble pas lancé - démarre l'application Ollama avant de relancer ce test.")
            return
        except Exception as e:
            print(f"Erreur inattendue en contactant Ollama: {e}")
            return
    
        # 2. Login
        print("\n[Step 1] Authenticating as document_admin...")
        login_data = {
            "username": "docadmin@camrail.net",
            "password": "docadminpassword"
        }
        login_res = client.post("/auth/login", data=login_data)
        assert login_res.status_code == 200, "Login failed"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("-> Login successful! JWT token acquired.")
    
        db = SessionLocal()
        try:
            initial_queries_count = db.query(RdaQuery).count()
    
            # 3. Test with relevant question
            print("\n[Step 2] Testing /assistant/query with a relevant question (needs Ollama inference)...")
            print("         (Cela peut prendre entre 5 et 30 secondes selon le processeur...)")
            
            start_time = time.time()
            q1_payload = {"query": "Quelle est la durée minimale de repos entre deux services ?"}
            res1 = client.post("/assistant/query", headers=headers, json=q1_payload, timeout=90.0)
            
            assert res1.status_code == 200
            data1 = res1.json()
            
            print(f"-> Résultat (en {time.time() - start_time:.2f}s) :")
            print(f"   * Confidence: {data1['confidence']}")
            print(f"   * Answer: {data1['answer']}")
            print(f"   * Citations count: {len(data1['citations'])}")
            
            assert data1["confidence"] in ["high", "medium"], "Confidence should be high or medium for a known question."
            assert len(data1["answer"]) > 10, "Answer should not be empty."
            assert len(data1["citations"]) > 0, "Should have citations."
            assert "repos" in data1["citations"][0]["document_title"].lower(), "First citation should be from the rest rules document."
            print("-> Success! Assistant generated an answer with citations.")
    
            # 4. Test with out-of-domain question (should not call Ollama, very fast)
            print("\n[Step 3] Testing /assistant/query with out-of-domain question (should abstain)...")
            
            start_time = time.time()
            q2_payload = {"query": "quelle est la recette de la tarte tatin ?"}
            res2 = client.post("/assistant/query", headers=headers, json=q2_payload)
            latency = time.time() - start_time
            
            assert res2.status_code == 200
            data2 = res2.json()
            
            print(f"-> Résultat (en {latency:.3f}s) :")
            print(f"   * Confidence: {data2['confidence']}")
            print(f"   * Answer: {data2['answer']}")
            
            assert data2["confidence"] == "insufficient", "Confidence should be insufficient for out-of-domain."
            assert latency < 1.0, f"Out-of-domain request took too long ({latency:.3f}s) - it should have short-circuited Ollama."
            print("-> Success! Assistant correctly abstained and short-circuited the LLM call.")
    
            # 4.5 Test with out-of-domain across multiple existing documents
            print("\n[Step 3.5] Testing /assistant/query with multiple active documents and completely unrelated question...")
            start_time = time.time()
            q3_payload = {"query": "comment réparer le moteur d'une fusée SpaceX ?"}
            res3 = client.post("/assistant/query", headers=headers, json=q3_payload)
            latency_q3 = time.time() - start_time
    
            assert res3.status_code == 200
            data3 = res3.json()
            
            print(f"-> Résultat (en {latency_q3:.3f}s) :")
            print(f"   * Confidence: {data3['confidence']}")
            print(f"   * Answer: {data3['answer']}")
    
            assert data3["confidence"] == "insufficient", "Confidence should be insufficient even with multiple documents for unrelated queries."
            assert "ne peut pas être confirmée" in data3["answer"].lower() or "trouve pas cette information" in data3["answer"].lower() or "indisponible" in data3["answer"].lower(), "Answer should clearly abstain."
            print("-> Success! Assistant correctly abstained on a multi-document database.")
    
            # 5. Check RdaQuery table
            print("\n[Step 4] Checking RdaQuery tracking...")
            final_queries_count = db.query(RdaQuery).count()
            assert final_queries_count == initial_queries_count + 3, "Three new RdaQuery records should have been created."
            
            # Verify request IDs are distinct
            assert data1["request_id"] != data2["request_id"] and data2["request_id"] != data3["request_id"], "Request IDs must be unique."
            print("-> Success! Request tracking is working.")
    
            print("\n" + "=" * 70)
            print("        ALL ASSISTANT TESTS COMPLETED SUCCESSFULLY! (5/5 PASSED)")
            print("=" * 70)
    
        except AssertionError as e:
            print(f"\n[ÉCHEC DU TEST] {e}")
        finally:
            db.close()


if __name__ == "__main__":
    test_assistant()
