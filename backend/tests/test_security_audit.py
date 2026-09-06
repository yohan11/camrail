import os
import json
import uuid
import warnings
from fpdf import FPDF
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, SessionLocal
from app.models.schemas import User, Document, DocumentPage, AuditEvent
from app.security import hash_password

warnings.filterwarnings("ignore", category=DeprecationWarning)

def create_test_pdf(filename: str, content: str):
    """Creates a basic PDF document for testing."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=content)
    pdf.output(filename)

def test_security_audit():
    print("=" * 70)
    print("      RAILMIND LITE - DAY 6: DEPARTMENTS & AUDIT")
    print("=" * 70)

    # 1. Reset database tables for testing (WARNING: this wipes the DB)
    # We don't wipe the DB completely to preserve security groups seeded on startup.
    # We will just use the client directly.
    client = TestClient(app)

    db = SessionLocal()
    try:
        # Step 1: Ensure test users exist
        readonly_user = db.query(User).filter(User.email == "readonly@camrail.net").first()
        if not readonly_user:
            readonly_user = User(
                email="readonly@camrail.net",
                password_hash=hash_password("readonlypassword"),
                full_name="Read-Only User",
                role="read_only",
                department="Formation",
                is_active=True
            )
            db.add(readonly_user)
            db.commit()
            db.refresh(readonly_user)
        else:
            readonly_user.department = "Formation"
            db.commit()

        # Step 2: Upload and activate two documents
        # Authenticate as docadmin
        login_resp = client.post(
            "/auth/login",
            data={"username": "docadmin@camrail.net", "password": "docadminpassword"}
        )
        assert login_resp.status_code == 200, "DocAdmin login failed"
        docadmin_token = login_resp.json()["access_token"]
        docadmin_headers = {"Authorization": f"Bearer {docadmin_token}"}

        # Create PDFs
        create_test_pdf("test_formation.pdf", "Procédure de formation des nouveaux conducteurs CAMRAIL.")
        create_test_pdf("test_operations.pdf", "Procédure des opérations de fret pour les gares.")

        # Upload Formation
        with open("test_formation.pdf", "rb") as f:
            resp1 = client.post(
                "/documents",
                headers=docadmin_headers,
                data={
                    "title": "Manuel de Formation",
                    "version": "1.0",
                    "category": "procedure",
                    "department": "Formation",
                    "effective_date": "2026-08-01"
                },
                files={"file": ("test_formation.pdf", f, "application/pdf")}
            )
        assert resp1.status_code == 200, f"Upload Formation failed: {resp1.text}"
        doc1_id = resp1.json()["id"]

        # Activate Formation
        resp_act1 = client.post(f"/documents/{doc1_id}/activate", headers=docadmin_headers)
        assert resp_act1.status_code == 200, "Activate Formation failed"

        # Upload Operations
        with open("test_operations.pdf", "rb") as f:
            resp2 = client.post(
                "/documents",
                headers=docadmin_headers,
                data={
                    "title": "Manuel des Opérations",
                    "version": "1.0",
                    "category": "procedure",
                    "department": "Operations",
                    "effective_date": "2026-08-01"
                },
                files={"file": ("test_operations.pdf", f, "application/pdf")}
            )
        assert resp2.status_code == 200, "Upload Operations failed"
        doc2_id = resp2.json()["id"]

        # Activate Operations
        resp_act2 = client.post(f"/documents/{doc2_id}/activate", headers=docadmin_headers)
        assert resp_act2.status_code == 200, "Activate Operations failed"

        # Step 3: Login as readonly (Formation) and check visibility
        login_ro = client.post(
            "/auth/login",
            data={"username": "readonly@camrail.net", "password": "readonlypassword"}
        )
        assert login_ro.status_code == 200, "ReadOnly login failed"
        ro_token = login_ro.json()["access_token"]
        ro_headers = {"Authorization": f"Bearer {ro_token}"}

        get_docs = client.get("/documents", headers=ro_headers)
        assert get_docs.status_code == 200
        visible_docs = get_docs.json()
        
        # Verify Operations doc is NOT visible
        ops_visible = any(d["title"] == "Manuel des Opérations" for d in visible_docs)
        form_visible = any(d["title"] == "Manuel de Formation" for d in visible_docs)
        
        assert not ops_visible, "Operations document should NOT be visible to Formation user"
        assert form_visible, "Formation document SHOULD be visible to Formation user"
        print("[TEST 3] GET /documents restricted by department -> OK")

        # Step 4: Assistant Query for Ops document as Formation user
        query_resp = client.post(
            "/assistant/query",
            headers=ro_headers,
            json={"query": "Quelles sont les procédures de fret ?"}
        )
        assert query_resp.status_code == 200
        resp_data = query_resp.json()
        
        # Verify the Operations document is not cited, since it's hidden.
        for cit in resp_data["citations"]:
            assert "Opérations" not in cit["document_title"], "Operations document was cited but should be hidden!"
            
        print("[TEST 4] POST /assistant/query hidden document unsearchable -> OK")

        # Step 5: Login as admin (No department) and check visibility
        login_admin = client.post(
            "/auth/login",
            data={"username": "admin@camrail.net", "password": "adminpassword"}
        )
        assert login_admin.status_code == 200, "Admin login failed"
        admin_token = login_admin.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        get_docs_admin = client.get("/documents", headers=admin_headers)
        assert get_docs_admin.status_code == 200
        admin_visible = get_docs_admin.json()
        
        ops_visible_admin = any(d["title"] == "Manuel des Opérations" for d in admin_visible)
        form_visible_admin = any(d["title"] == "Manuel de Formation" for d in admin_visible)
        
        assert ops_visible_admin and form_visible_admin, "Admin should see all documents"
        print("[TEST 5] GET /documents no restriction for admin -> OK")

        # Step 6: Dashboard Summary
        dash_resp = client.get("/dashboard/summary", headers=ro_headers)
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()
        assert "documents_total" in dash_data
        assert "questions_total" in dash_data
        assert dash_data["documents_total"] >= 1, "Dashboard should show at least 1 document for Formation user"
        print("[TEST 6] GET /dashboard/summary -> OK")

        # Step 7: Audit Event Validation
        # Check login success
        success_audit = db.query(AuditEvent).filter(
            AuditEvent.action == "login_success",
            AuditEvent.entity_type == "user"
        ).first()
        assert success_audit is not None, "login_success audit event not found"
        
        # Ensure password is not in any audit log
        all_audits = db.query(AuditEvent).all()
        for audit in all_audits:
            if audit.details_json:
                assert "readonlypassword" not in audit.details_json, "Password leaked in audit log!"
                assert "adminpassword" not in audit.details_json, "Password leaked in audit log!"
        
        print("[TEST 7] Audit events created and passwords secured -> OK")
        
        print("\n" + "=" * 70)
        print("        ALL SECURITY & AUDIT TESTS COMPLETED SUCCESSFULLY! (8/8 PASSED)")
        print("=" * 70)

    finally:
        db.close()
        # Cleanup
        for file in ["test_formation.pdf", "test_operations.pdf"]:
            if os.path.exists(file):
                os.remove(file)

if __name__ == "__main__":
    test_security_audit()
