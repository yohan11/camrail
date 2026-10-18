import io
import json
import zipfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.schemas import User, AuditEvent, UserRole
from app.security import hash_password, create_access_token
from app.routers.documents import sanitize_filename

client = TestClient(app)

@pytest.fixture(scope="module")
def doc_admin_auth():
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "hardened_admin@camrail.net").first()
        if not user:
            user = User(
                email="hardened_admin@camrail.net",
                password_hash=hash_password("adminpass"),
                full_name="Hardened Admin",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_access_token(user.email, user.role)
        yield {
            "user": user,
            "headers": {"Authorization": f"Bearer {token}"}
        }
    finally:
        db.close()


def test_sanitize_filename_neutralizes_path_traversal():
    """Vérifie que la fonction sanitize_filename neutralise toute tentative de traversée de chemin."""
    # 1. Path traversal relatif
    assert sanitize_filename("../../x.pdf") == "x.pdf"
    assert sanitize_filename("..\\..\\x.pdf") == "x.pdf"
    assert sanitize_filename("/etc/passwd") == "passwd"
    assert sanitize_filename("C:\\Windows\\System32\\cmd.exe") == "cmd.exe"
    
    # 2. Caractères de contrôle et séparateurs
    assert sanitize_filename("document\x00malicious.pdf") == "document_malicious.pdf"
    assert sanitize_filename("..//..//test<bad>.pdf") == "test_bad_.pdf"
    assert sanitize_filename("") == "document_inconnu"


def test_reject_fake_pdf(doc_admin_auth):
    """Rejette un fichier texte renommé en .pdf qui ne commence pas par %PDF-."""
    headers = doc_admin_auth["headers"]
    fake_content = b"Ceci est du simple texte ASCII qui n'est pas un fichier PDF valide."

    files = {"file": ("fake.pdf", io.BytesIO(fake_content), "application/pdf")}
    data = {
        "title": "Faux PDF Test",
        "category": "procedure",
        "department": "Traction",
        "version": "1.0"
    }

    res = client.post("/documents", headers=headers, files=files, data=data)
    assert res.status_code == 400
    assert "PDF invalide" in res.json()["detail"] or "%PDF-" in res.json()["detail"]

    # Vérification événement audit upload_rejected
    db: Session = SessionLocal()
    try:
        rejected = db.query(AuditEvent).filter(
            AuditEvent.action == "upload_rejected",
            AuditEvent.actor_user_id == doc_admin_auth["user"].id
        ).order_by(AuditEvent.id.desc()).first()
        assert rejected is not None
        details = json.loads(rejected.details_json) if rejected.details_json else {}
        assert details.get("reason") == "invalid_pdf_header"
    finally:
        db.close()


def test_reject_docx_without_document_xml(doc_admin_auth):
    """Rejette un fichier DOCX zip valide mais sans le fichier word/document.xml requis."""
    headers = doc_admin_auth["headers"]
    
    # Création d'un zip en mémoire sans word/document.xml
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test.txt", "Fichier quelconque")
        zf.writestr("[Content_Types].xml", "<Types></Types>")
    buf.seek(0)

    files = {"file": ("bad_structure.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {
        "title": "Docx Sans XML",
        "category": "procedure",
        "department": "Traction",
        "version": "1.0"
    }

    res = client.post("/documents", headers=headers, files=files, data=data)
    assert res.status_code == 400
    assert "word/document.xml" in res.json()["detail"]

    # Vérification événement audit upload_rejected
    db: Session = SessionLocal()
    try:
        rejected = db.query(AuditEvent).filter(
            AuditEvent.action == "upload_rejected",
            AuditEvent.actor_user_id == doc_admin_auth["user"].id
        ).order_by(AuditEvent.id.desc()).first()
        assert rejected is not None
        details = json.loads(rejected.details_json) if rejected.details_json else {}
        assert details.get("reason") == "missing_document_xml"
    finally:
        db.close()


def test_reject_decompression_bomb(doc_admin_auth):
    """Rejette une archive DOCX contenant une bombe de décompression (ratio excessif > 100)."""
    headers = doc_admin_auth["headers"]

    # Création d'une bombe de compression en mémoire (haut ratio de compression)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # word/document.xml nécessaire
        zf.writestr("word/document.xml", "<w:document></w:document>")
        # 10 Mo de zéros compressés qui occupent seulement quelques dizaines d'octets
        zf.writestr("word/huge_zeros.bin", b"\x00" * (10 * 1024 * 1024))
    buf.seek(0)

    files = {"file": ("zip_bomb.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {
        "title": "Zip Bomb Test",
        "category": "procedure",
        "department": "Traction",
        "version": "1.0"
    }

    res = client.post("/documents", headers=headers, files=files, data=data)
    assert res.status_code == 400
    assert "ratio de compression" in res.json()["detail"] or "bombe de décompression" in res.json()["detail"]

    db: Session = SessionLocal()
    try:
        rejected = db.query(AuditEvent).filter(
            AuditEvent.action == "upload_rejected",
            AuditEvent.actor_user_id == doc_admin_auth["user"].id
        ).order_by(AuditEvent.id.desc()).first()
        assert rejected is not None
        details = json.loads(rejected.details_json) if rejected.details_json else {}
        assert "zip_bomb" in details.get("reason", "")
    finally:
        db.close()


def test_reject_oversized_file(doc_admin_auth):
    """Rejette un fichier dépassant la limite MAX_UPLOAD_MB (ex: 26 Mo si max 25 Mo)."""
    from app.config import settings
    headers = doc_admin_auth["headers"]

    # Fichier dépassant MAX_UPLOAD_MB
    oversized_bytes = b"%PDF-1.4 " + b"A" * (settings.MAX_UPLOAD_MB * 1024 * 1024 + 1024)

    files = {"file": ("too_large.pdf", io.BytesIO(oversized_bytes), "application/pdf")}
    data = {
        "title": "Fichier Trop Grand",
        "category": "procedure",
        "department": "Traction",
        "version": "1.0"
    }

    res = client.post("/documents", headers=headers, files=files, data=data)
    assert res.status_code == 400
    assert "dépasse la limite autorisée" in res.json()["detail"]

    db: Session = SessionLocal()
    try:
        rejected = db.query(AuditEvent).filter(
            AuditEvent.action == "upload_rejected",
            AuditEvent.actor_user_id == doc_admin_auth["user"].id
        ).order_by(AuditEvent.id.desc()).first()
        assert rejected is not None
        details = json.loads(rejected.details_json) if rejected.details_json else {}
        assert details.get("reason") == "file_too_large"
    finally:
        db.close()


def test_reject_dangerous_double_extension(doc_admin_auth):
    """Rejette les fichiers ayant une double extension dangereuse (ex: .exe.pdf)."""
    headers = doc_admin_auth["headers"]
    valid_pdf = b"%PDF-1.4 test double extension"

    files = {"file": ("malicious_payload.exe.pdf", io.BytesIO(valid_pdf), "application/pdf")}
    data = {
        "title": "Double Extension Test",
        "category": "procedure",
        "department": "Traction",
        "version": "1.0"
    }

    res = client.post("/documents", headers=headers, files=files, data=data)
    assert res.status_code == 400
    assert "double extension" in res.json()["detail"].lower()

    # Rejette aussi les extensions non autorisées en dernière position
    bad_ext_files = {"file": ("exploit.pdf.exe", io.BytesIO(valid_pdf), "application/octet-stream")}
    res_bad_ext = client.post("/documents", headers=headers, files=bad_ext_files, data=data)
    assert res_bad_ext.status_code == 400
    assert "non supporté" in res_bad_ext.json()["detail"].lower()


def test_read_only_user_cannot_upload():
    """Vérifie qu'un utilisateur avec le rôle read_only ne peut jamais uploader de document (403 Forbidden)."""
    db: Session = SessionLocal()
    try:
        ro_user = db.query(User).filter(User.email == "ro_uploader_test@camrail.net").first()
        if not ro_user:
            ro_user = User(
                email="ro_uploader_test@camrail.net",
                password_hash=hash_password("ropassword"),
                full_name="RO Uploader",
                role=UserRole.READ_ONLY,
                is_active=True
            )
            db.add(ro_user)
            db.commit()
            db.refresh(ro_user)

        token = create_access_token(ro_user.email, ro_user.role)
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("normal.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")}
        data = {
            "title": "Document Non Autorisé",
            "category": "procedure",
            "department": "Traction",
            "version": "1.0"
        }

        res = client.post("/documents", headers=headers, files=files, data=data)
        assert res.status_code == 403
    finally:
        db.close()

