import os
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.schemas import Document, DocumentChunk, User
from fastapi.testclient import TestClient
from app.main import app

def run_diagnostic():
    db = SessionLocal()
    report = {}
    try:
        # Check user
        user = db.query(User).filter(User.email == "docadmin@camrail.net").first()
        report['user'] = {'email': user.email, 'role': user.role, 'security_groups': [g.name for g in user.security_groups]}

        client = TestClient(app)
        
        # Login
        login_resp = client.post(
            "/auth/login",
            data={"username": "docadmin@camrail.net", "password": "docadminpassword"}
        )
        if login_resp.status_code != 200:
            report['error'] = "Login failed"
        else:
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Query
            query_text = "a quoi sert l'heritage en java"
            resp = client.post("/assistant/query", headers=headers, json={"query": query_text})
            
            if resp.status_code == 200:
                data = resp.json()
                report['assistant_query_result'] = {
                    'confidence': data.get('confidence'),
                    'answer': data.get('answer')[:100] + "...",
                    'citations_count': len(data.get('citations', [])),
                    'citations': [c.get('document_title') for c in data.get('citations', [])]
                }
            else:
                report['assistant_query_result'] = f"Error: {resp.status_code} - {resp.text}"

    finally:
        db.close()
        
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    run_diagnostic()
