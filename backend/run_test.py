import sys
import os

# Add the current directory to sys.path so we can import app
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app, startup_event
from app.database import SessionLocal
from app.models.schemas import User

def run_tests():
    print("=" * 60)
    print("        RAILMIND LITE - BACKEND POSTGRESQL VERIFICATION")
    print("=" * 60)
    
    # 1. Ensure DB is seeded via startup event
    print("\n[Step 1] Initializing and seeding Database...")
    startup_event()
    
    db = SessionLocal()
    users = db.query(User).all()
    print(f"-> Database connected (PostgreSQL). Total users seeded: {len(users)}")
    for u in users:
        print(f"   * User: {u.email} | Role: {u.role} | Active: {u.is_active}")
    db.close()
    
    # 2. Setup TestClient
    client = TestClient(app)
    
    # 3. Test Root endpoint
    print("\n[Step 2] Testing API Root endpoint...")
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print(f"-> Root API Response: {res.json()}")
    
    # 4. Test Login (Happy Path)
    print("\n[Step 3] Testing Login with admin credentials...")
    login_data = {
        "username": "admin@camrail.net",
        "password": "adminpassword"
    }
    res = client.post("/auth/login", data=login_data)
    assert res.status_code == 200, f"Login failed: {res.text}"
    token_resp = res.json()
    print(f"-> Login successful! Token type: {token_resp['token_type']}")
    print(f"-> Token: {token_resp['access_token'][:30]}...[TRUNCATED]")
    print(f"-> Returned User Role: {token_resp['role']}")
    assert token_resp["role"] == "admin"
    
    access_token = token_resp["access_token"]
    
    # 5. Test Profile retrieval /me
    print("\n[Step 4] Testing GET /users/me profile endpoint using admin token...")
    headers = {"Authorization": f"Bearer {access_token}"}
    res = client.get("/users/me", headers=headers)
    assert res.status_code == 200, f"Profile fetch failed: {res.text}"
    profile = res.json()
    print(f"-> Profile fetched successfully!")
    print(f"   * Email: {profile['email']}")
    print(f"   * Full Name: {profile['full_name']}")
    print(f"   * Role: {profile['role']}")
    assert profile["role"] == "admin"
    
    # 6. Test Invalid Login
    print("\n[Step 5] Testing Login with incorrect credentials...")
    bad_login_data = {
        "username": "admin@camrail.net",
        "password": "wrongpassword"
    }
    res = client.post("/auth/login", data=bad_login_data)
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print(f"-> Invalid login correctly rejected with 401: {res.json()['detail']}")
    
    # 7. Test Admin User Creation endpoint
    print("\n[Step 6] Testing Admin user creation route...")
    new_user_payload = {
        "email": "new_docadmin@camrail.net",
        "password": "docadminpassword123",
        "full_name": "New Document Admin Test",
        "role": "document_admin",
        "is_active": True
    }
    # If user already exists in DB from a previous test run, clean it or use unique email
    db = SessionLocal()
    existing = db.query(User).filter(User.email == new_user_payload["email"]).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    res = client.post("/users/", json=new_user_payload, headers=headers)
    assert res.status_code == 200, f"User creation failed: {res.text}"
    new_user = res.json()
    print(f"-> User created successfully by admin!")
    print(f"   * Email: {new_user['email']}")
    print(f"   * Role: {new_user['role']}")
    assert new_user["role"] == "document_admin"
    
    # 8. Test Non-Admin Role Restriction (read_only user)
    print("\n[Step 7] Testing security constraint (read_only creating a user)...")
    # Login as read_only user
    readonly_login = {
        "username": "readonly@camrail.net",
        "password": "readonlypassword"
    }
    res = client.post("/auth/login", data=readonly_login)
    assert res.status_code == 200, f"Read-only login failed: {res.text}"
    readonly_token = res.json()["access_token"]
    readonly_headers = {"Authorization": f"Bearer {readonly_token}"}
    
    # Attempt to create user with read_only token
    attempt_payload = {
        "email": "unauthorized_user@camrail.net",
        "password": "somepassword123",
        "full_name": "Unauthorized Attempt",
        "role": "read_only",
        "is_active": True
    }
    res = client.post("/users/", json=attempt_payload, headers=readonly_headers)
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}"
    print(f"-> Access denied correctly (403 Forbidden): {res.json()['detail']}")
    
    print("\n" + "=" * 60)
    print("        ALL TESTS COMPLETED SUCCESSFULLY! (7/7 PASSED)")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

