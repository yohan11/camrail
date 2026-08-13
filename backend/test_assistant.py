from fastapi.testclient import TestClient
from app.main import app
import json

def test():
    client = TestClient(app)
    
    # Login to get token
    res = client.post("/auth/login", data={"username": "docadmin@camrail.net", "password": "docadminpassword"})
    print("Login:", res.status_code)
    token = res.json()["access_token"]
    
    # Send query
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": "test query"}
    res = client.post("/assistant/query", headers=headers, json=payload)
    print("Query:", res.status_code)
    try:
        print(json.dumps(res.json(), indent=2))
    except:
        print(res.text)

if __name__ == "__main__":
    test()
