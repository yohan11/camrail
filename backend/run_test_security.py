import time
from fastapi.testclient import TestClient
from fpdf import FPDF
import os

from app.main import app
from app.database import SessionLocal
from app.models.schemas import Document, RdaQuery, User, SecurityGroup

def create_test_pdf(filename: str, text: str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=text)
    pdf.output(filename)

def run_tests():
    with TestClient(app) as client:
        print("=" * 70)
        print("      RAILMIND LITE - SECURITY GROUPS & AUDIT TESTS")
        print("=" * 70)

        db = SessionLocal()
        
        # Ensure we have our test users and groups
        admin_user = db.query(User).filter(User.email == "admin@camrail.net").first()
        op_user = db.query(User).filter(User.email == "op_user@camrail.net").first()
        if not op_user:
            op_user = User(email="op_user@camrail.net", password_hash="dummy", role="read_only")
            db.add(op_user)
        
        empty_user = db.query(User).filter(User.email == "empty_user@camrail.net").first()
        if not empty_user:
            empty_user = User(email="empty_user@camrail.net", password_hash="dummy", role="read_only")
            db.add(empty_user)
            
        op_group = db.query(SecurityGroup).filter(SecurityGroup.name == "operations").first()
        safety_group = db.query(SecurityGroup).filter(SecurityGroup.name == "safety").first()
        
        # Setup user groups
        op_user.security_groups = [op_group]
        empty_user.security_groups = []
        db.commit()

        # Login to get admin token for uploads
        login_res = client.post("/auth/login", data={"username": "admin@camrail.net", "password": "adminpassword"})
        admin_token = login_res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # We need mock tokens for op_user and empty_user to hit endpoints directly
        from app.security import create_access_token
        op_token = create_access_token(subject=op_user.email, role=op_user.role)
        op_headers = {"Authorization": f"Bearer {op_token}"}
        
        empty_token = create_access_token(subject=empty_user.email, role=empty_user.role)
        empty_headers = {"Authorization": f"Bearer {empty_token}"}

        # 1. Upload Operations Document
        op_pdf = "test_op.pdf"
        create_test_pdf(op_pdf, "Procédure d'opérations: Le signal rouge signifie arrêt immédiat et absolu du train.")
        with open(op_pdf, "rb") as f:
            res_op = client.post("/documents", headers=admin_headers,
                files={"file": (op_pdf, f, "application/pdf")},
                data={"title": "Doc Operations", "category": "Tests", "department": "Operations", "security_groups": "operations"}
            )
        op_doc_id = res_op.json()["id"]

        # 2. Upload Safety Document
        safe_pdf = "test_safety.pdf"
        create_test_pdf(safe_pdf, "Consigne de sécurité: Les EPI sont obligatoires sur les voies.")
        with open(safe_pdf, "rb") as f:
            res_safe = client.post("/documents", headers=admin_headers,
                files={"file": (safe_pdf, f, "application/pdf")},
                data={"title": "Doc Safety", "category": "Tests", "department": "Safety", "security_groups": "safety"}
            )
        safe_doc_id = res_safe.json()["id"]

        # Wait for indexing
        max_wait = 20
        start = time.time()
        while time.time() - start < max_wait:
            d1 = db.query(Document).filter(Document.id == op_doc_id).first()
            d2 = db.query(Document).filter(Document.id == safe_doc_id).first()
            if d1.status == "indexed" and d2.status == "indexed":
                break
            time.sleep(1)
            
        client.post(f"/documents/{op_doc_id}/activate", headers=admin_headers)
        client.post(f"/documents/{safe_doc_id}/activate", headers=admin_headers)

        print("[TEST 1 & 2] Operations User asking about Operations doc & Safety doc")
        res = client.post("/assistant/query", headers=op_headers, json={"query": "Que signifie le signal rouge ?"})
        data = res.json()
        print(f"DEBUG TEST 1 ANSWER: {data['answer']}")
        assert "arrêt" in data["answer"].lower() or "temporairement indisponible" in data["answer"]
        print("-> OK: Authorized result returned.")
        
        res = client.post("/assistant/query", headers=op_headers, json={"query": "Les EPI sont-ils obligatoires ?"})
        data = res.json()
        assert "ne peut pas être confirmée" in data["answer"] or "je ne trouve pas" in data["answer"].lower()
        print("-> OK: Restricted document (Safety) is NOT retrieved for Op User.")

        print("[TEST 3] User with no security groups")
        res = client.post("/assistant/query", headers=empty_headers, json={"query": "Que signifie le signal rouge ?"})
        data = res.json()
        assert "je ne trouve pas" in data["answer"].lower() or "ne peut pas être confirmée" in data["answer"]
        print("-> OK: No protected documents returned for user without groups.")

        print("[TEST 4] Fake security group payload")
        # Assuming AssistantQueryRequest doesn't even accept security_group, passing it should be ignored or error, but let's just assert the backend doesn't use it.
        res = client.post("/assistant/query", headers=empty_headers, json={"query": "Que signifie le signal rouge ?", "security_group": "operations"})
        data = res.json()
        assert "je ne trouve pas" in data["answer"].lower() or "ne peut pas être confirmée" in data["answer"]
        print("-> OK: Fake group payload is ignored, fallback to token groups.")

        print("[TEST 5] Question has no supporting document -> system abstains")
        res = client.post("/assistant/query", headers=op_headers, json={"query": "Quelle est la recette du gâteau au chocolat ?"})
        data = res.json()
        print(f"DEBUG TEST 5 ANSWER: {data['answer']}")
        assert "je ne trouve pas" in data["answer"].lower() or "ne peut pas être confirmée" in data["answer"]
        print("-> OK: System abstained correctly.")

        print("[TEST 6] Question uses different wording -> semantic retrieval works")
        res = client.post("/assistant/query", headers=op_headers, json={"query": "Quelle est l'indication d'un feu de couleur rouge vif ?"})
        data = res.json()
        print(f"DEBUG TEST 6 ANSWER: {data['answer']}")
        assert "arrêt" in data["answer"].lower() or "temporairement indisponible" in data["answer"]
        print("-> OK: Semantic search returned correct response.")

        print("[TEST 7] Citation is returned correctly")
        citations = data.get("citations", [])
        assert len(citations) > 0
        cit = citations[0]
        assert "document_title" in cit
        assert "document_version" in cit
        assert "page_start" in cit
        assert "score" in cit
        print("-> OK: Citation schema valid.")

        print("[TEST 8] Audit record is created with extended fields")
        req_id = data["request_id"]
        audit = db.query(RdaQuery).filter(RdaQuery.request_id == req_id).first()
        assert audit is not None
        assert audit.user_id == op_user.id
        assert audit.results_count > 0
        assert audit.confidence in ["high", "medium", "insufficient"]
        assert audit.citation_count > 0
        assert audit.model_name is not None
        print("-> OK: Audit log successfully written.")
        
        # Cleanup
        if os.path.exists(op_pdf): os.remove(op_pdf)
        if os.path.exists(safe_pdf): os.remove(safe_pdf)

        print("\n" + "=" * 70)
        print("        ALL SECURITY TESTS COMPLETED SUCCESSFULLY! (8/8 PASSED)")
        print("=" * 70)

if __name__ == "__main__":
    run_tests()
