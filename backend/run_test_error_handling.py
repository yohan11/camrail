import os
from fastapi.testclient import TestClient
import warnings

from app.main import app
from app.database import SessionLocal
from app.models.schemas import User

warnings.filterwarnings("ignore", category=DeprecationWarning)

def test_error_handling():
    print("=" * 60)
    print("       RAILMIND LITE - ERROR HANDLING AUDIT")
    print("=" * 60)
    
    client = TestClient(app)
    
    db = SessionLocal()
    try:
        # Get a valid token for authenticated routes
        login_resp = client.post(
            "/auth/login",
            data={"username": "docadmin@camrail.net", "password": "docadminpassword"}
        )
        assert login_resp.status_code == 200, "DocAdmin login failed, run seed_demo.py first!"
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test 1: POST /auth/login with invalid email (should be 401)
        resp1 = client.post("/auth/login", data={"username": "fake@camrail.net", "password": "123"})
        assert resp1.status_code == 401
        assert resp1.json()["detail"] == "Incorrect email or password"
        print("[TEST 1] Invalid login -> 401 Unauthorized (OK)")
        
        # Test 2: POST /auth/login with missing field (should be 422 Unprocessable Entity)
        # We omit the password field
        resp2 = client.post("/auth/login", data={"username": "docadmin@camrail.net"})
        assert resp2.status_code == 422
        print("[TEST 2] Missing login field -> 422 Unprocessable Entity (OK)")
        
        # Test 3: POST /documents with empty file
        empty_file_path = "empty_test.pdf"
        with open(empty_file_path, "wb") as f:
            pass
            
        with open(empty_file_path, "rb") as f:
            resp3 = client.post(
                "/documents",
                headers=headers,
                data={
                    "title": "Empty Doc",
                    "version": "1.0",
                    "category": "procedure",
                    "department": "Operations",
                    "effective_date": "2026-08-01"
                },
                files={"file": ("empty_test.pdf", f, "application/pdf")}
            )
        assert resp3.status_code == 400
        assert resp3.json()["detail"] == "Le fichier est vide."
        os.remove(empty_file_path)
        print("[TEST 3] Empty file upload -> 400 Bad Request (OK)")
        
        # Test 4: GET /documents/{id} with non-existent ID
        resp4 = client.get("/documents/99999", headers=headers)
        assert resp4.status_code == 404
        assert resp4.json()["detail"] == "Document non trouvé"
        print("[TEST 4] Non-existent document ID -> 404 Not Found (OK)")
        
        # Test 5: Protected route without token
        resp5 = client.get("/documents/99999")
        assert resp5.status_code == 401
        print("[TEST 5] Protected route without token -> 401 Unauthorized (OK)")
        
        # Test 6: Protected route with invalid token
        resp6 = client.get("/documents/99999", headers={"Authorization": "Bearer invalidtoken"})
        assert resp6.status_code == 401
        print("[TEST 6] Protected route with invalid token -> 401 Unauthorized (OK)")
        
        # Test 7: Assistant Query fallback
        # If Ollama is running, it returns 200 with normal answer.
        # If Ollama is NOT running, it also returns 200 but with fallback answer.
        # In both cases, it should NOT return 500.
        resp7 = client.post(
            "/assistant/query",
            headers=headers,
            json={"query": "Test error handling"}
        )
        assert resp7.status_code == 200, f"Assistant query failed with status {resp7.status_code}"
        print("[TEST 7] Assistant query (Ollama fallback/success) -> 200 OK (OK)")
        
        print("\n" + "=" * 60)
        print("        ALL ERROR HANDLING TESTS COMPLETED SUCCESSFULLY! (7/7 PASSED)")
        print("=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    test_error_handling()
