import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.schemas import User, UserRole
from app.security import hash_password, create_access_token

client = TestClient(app)

SQLI_PAYLOADS = [
    "' OR 1=1--",
    "\"' OR '1'='1\"",
    "'; DROP TABLE users;--",
    "' UNION SELECT NULL, NULL, NULL--",
    "admin'--",
    "1' OR '1' = '1",
    "'; EXEC xp_cmdshell('dir');--",
    "' OR SLEEP(5)--",
    "\" OR \"\"=\"",
    "1; SELECT * FROM audit_logs",
]

@pytest.fixture(scope="module")
def admin_and_ro_auth():
    db: Session = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "sqli_admin@camrail.net").first()
        if not admin:
            admin = User(
                email="sqli_admin@camrail.net",
                password_hash=hash_password("adminpass123"),
                full_name="SQLi Admin",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin)

        ro_user = db.query(User).filter(User.email == "sqli_ro@camrail.net").first()
        if not ro_user:
            ro_user = User(
                email="sqli_ro@camrail.net",
                password_hash=hash_password("ropass123"),
                full_name="SQLi RO",
                role=UserRole.READ_ONLY,
                department="Traction",
                is_active=True
            )
            db.add(ro_user)
        db.commit()

        token_admin = create_access_token(admin.email, admin.role)
        token_ro = create_access_token(ro_user.email, ro_user.role)

        yield {
            "admin": admin,
            "ro_user": ro_user,
            "admin_headers": {"Authorization": f"Bearer {token_admin}"},
            "ro_headers": {"Authorization": f"Bearer {token_ro}"}
        }
    finally:
        db.close()


def test_sql_injection_in_login():
    """Vérifie que l'injection SQL dans le formulaire d'authentification ne provoque aucune fuite ni 500."""
    for payload in SQLI_PAYLOADS:
        res = client.post(
            "/auth/login",
            data={"username": payload, "password": payload}
        )
        assert res.status_code == 401, f"Failed for payload {payload}: {res.status_code}"
        assert res.json()["detail"] == "Email ou mot de passe incorrect."


def test_sql_injection_in_assistant_query(admin_and_ro_auth):
    """Vérifie que l'injection SQL dans la question de l'assistant ne provoque aucune erreur 500."""
    headers = admin_and_ro_auth["ro_headers"]
    for payload in SQLI_PAYLOADS:
        res = client.post(
            "/assistant/query",
            headers=headers,
            json={"query": f"Consignes de sécurité {payload}"}
        )
        assert res.status_code != 500, f"500 Internal Server Error for payload: {payload}"
        assert res.status_code in [200, 400, 404, 422]


def test_sql_injection_in_document_upload(admin_and_ro_auth):
    """Vérifie que l'injection SQL dans le titre, catégorie, département ou nom de fichier est neutralisée."""
    headers = admin_and_ro_auth["admin_headers"]
    valid_pdf = b"%PDF-1.4 test sqli injection neutralisation"

    for payload in SQLI_PAYLOADS[:4]:
        # Injection dans le titre et département
        files = {"file": ("normal_sqli_test.pdf", io.BytesIO(valid_pdf), "application/pdf")}
        data = {
            "title": f"Titre {payload}",
            "category": "procedure",
            "department": f"Traction {payload}",
            "version": "1.0"
        }
        res = client.post("/documents", headers=headers, files=files, data=data)
        assert res.status_code != 500, f"500 Internal Server Error on metadata upload with: {payload}"
        assert res.status_code in [200, 400, 422]

        # Injection dans le nom de fichier
        malicious_filename = f"test_{payload.replace('/', '_')}.pdf"
        bad_file = {"file": (malicious_filename, io.BytesIO(valid_pdf), "application/pdf")}
        data_clean = {
            "title": "Document Test Nom Fichier",
            "category": "procedure",
            "department": "Traction",
            "version": "1.0"
        }
        res_file = client.post("/documents", headers=headers, files=bad_file, data=data_clean)
        assert res_file.status_code != 500, f"500 Internal Server Error on filename upload with: {payload}"


def test_sql_injection_in_document_listing_and_detail(admin_and_ro_auth):
    """Vérifie que les injections SQL dans les paramètres GET ou IDs ne provoquent pas d'erreur 500."""
    headers = admin_and_ro_auth["ro_headers"]
    for payload in SQLI_PAYLOADS[:5]:
        # GET /documents?department=payload
        res_list = client.get(f"/documents?department={payload}", headers=headers)
        assert res_list.status_code != 500
        assert res_list.status_code in [200, 400, 422]

        # GET /documents/{id}
        res_detail = client.get(f"/documents/{payload}", headers=headers)
        assert res_detail.status_code != 500
        assert res_detail.status_code in [404, 422]
