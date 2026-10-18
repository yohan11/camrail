import os
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.schemas import User, Document, SecurityGroup, UserRole, AuditEvent
from app.security import hash_password, can_access_document, ensure_document_access, create_access_token

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_security_matrix():
    db: Session = SessionLocal()
    try:
        # Create security groups
        grp_default = db.query(SecurityGroup).filter(SecurityGroup.name == "default").first()
        if not grp_default:
            grp_default = SecurityGroup(name="default")
            db.add(grp_default)

        grp_traction = db.query(SecurityGroup).filter(SecurityGroup.name == "Traction").first()
        if not grp_traction:
            grp_traction = SecurityGroup(name="Traction")
            db.add(grp_traction)

        grp_rh = db.query(SecurityGroup).filter(SecurityGroup.name == "RH").first()
        if not grp_rh:
            grp_rh = SecurityGroup(name="RH")
            db.add(grp_rh)
        db.commit()

        # Create dummy file on disk for file download endpoint tests
        storage_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "documents")
        os.makedirs(storage_dir, exist_ok=True)
        dummy_file = os.path.join(storage_dir, "test_matrix_file.pdf")
        with open(dummy_file, "wb") as f:
            f.write(b"%PDF-1.4 test document content for access matrix")

        # 1. Admin user
        admin = db.query(User).filter(User.email == "matrix_admin@camrail.net").first()
        if not admin:
            admin = User(
                email="matrix_admin@camrail.net",
                password_hash=hash_password("pass123"),
                full_name="Matrix Admin",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin)

        # 2. Document Admin user
        doc_admin = db.query(User).filter(User.email == "matrix_docadmin@camrail.net").first()
        if not doc_admin:
            doc_admin = User(
                email="matrix_docadmin@camrail.net",
                password_hash=hash_password("pass123"),
                full_name="Matrix Doc Admin",
                role=UserRole.DOCUMENT_ADMIN,
                is_active=True
            )
            db.add(doc_admin)

        # 3. Read Only User in Department "Traction" with group "Traction"
        user_traction = db.query(User).filter(User.email == "matrix_traction@camrail.net").first()
        if not user_traction:
            user_traction = User(
                email="matrix_traction@camrail.net",
                password_hash=hash_password("pass123"),
                full_name="User Traction",
                role=UserRole.READ_ONLY,
                department="Traction",
                is_active=True
            )
            user_traction.security_groups.append(grp_traction)
            db.add(user_traction)

        # 4. Read Only User in Department "Exploitation" with group "RH"
        user_rh = db.query(User).filter(User.email == "matrix_rh@camrail.net").first()
        if not user_rh:
            user_rh = User(
                email="matrix_rh@camrail.net",
                password_hash=hash_password("pass123"),
                full_name="User RH",
                role=UserRole.READ_ONLY,
                department="Exploitation",
                is_active=True
            )
            user_rh.security_groups.append(grp_rh)
            db.add(user_rh)

        # 5. Read Only User with NO security group
        user_nogroup = db.query(User).filter(User.email == "matrix_nogroup@camrail.net").first()
        if not user_nogroup:
            user_nogroup = User(
                email="matrix_nogroup@camrail.net",
                password_hash=hash_password("pass123"),
                full_name="User NoGroup",
                role=UserRole.READ_ONLY,
                department="Traction",
                is_active=True
            )
            db.add(user_nogroup)

        db.commit()

        # Documents:
        # Doc 1: Active, Traction department, group Traction
        doc_act_trac = db.query(Document).filter(Document.title == "Matrix Doc Active Traction").first()
        if not doc_act_trac:
            doc_act_trac = Document(
                title="Matrix Doc Active Traction",
                version="1.0",
                category="consigne",
                department="Traction",
                status="active",
                checksum="matrix_chk_1",
                file_url=dummy_file,
                uploaded_by=admin.id
            )
            doc_act_trac.security_groups = [grp_traction]
            db.add(doc_act_trac)

        # Doc 2: Active, Exploitation department, group RH
        doc_act_rh = db.query(Document).filter(Document.title == "Matrix Doc Active RH").first()
        if not doc_act_rh:
            doc_act_rh = Document(
                title="Matrix Doc Active RH",
                version="1.0",
                category="procedure",
                department="Exploitation",
                status="active",
                checksum="matrix_chk_2",
                file_url=dummy_file,
                uploaded_by=admin.id
            )
            doc_act_rh.security_groups = [grp_rh]
            db.add(doc_act_rh)

        # Doc 3: Inactive / Indexed, Traction department, group Traction
        doc_indexed_trac = db.query(Document).filter(Document.title == "Matrix Doc Indexed Traction").first()
        if not doc_indexed_trac:
            doc_indexed_trac = Document(
                title="Matrix Doc Indexed Traction",
                version="1.0",
                category="consigne",
                department="Traction",
                status="indexed",
                checksum="matrix_chk_3",
                file_url=dummy_file,
                uploaded_by=admin.id
            )
            doc_indexed_trac.security_groups = [grp_traction]
            db.add(doc_indexed_trac)

        # Doc 4: Archived, Traction department, group Traction
        doc_archived_trac = db.query(Document).filter(Document.title == "Matrix Doc Archived Traction").first()
        if not doc_archived_trac:
            doc_archived_trac = Document(
                title="Matrix Doc Archived Traction",
                version="1.0",
                category="consigne",
                department="Traction",
                status="archived",
                checksum="matrix_chk_4",
                file_url=dummy_file,
                uploaded_by=admin.id
            )
            doc_archived_trac.security_groups = [grp_traction]
            db.add(doc_archived_trac)

        db.commit()

        yield {
            "admin": admin,
            "doc_admin": doc_admin,
            "user_traction": user_traction,
            "user_rh": user_rh,
            "user_nogroup": user_nogroup,
            "doc_act_trac": doc_act_trac,
            "doc_act_rh": doc_act_rh,
            "doc_indexed_trac": doc_indexed_trac,
            "doc_archived_trac": doc_archived_trac,
        }
    finally:
        db.close()


def test_can_access_document_logic(setup_security_matrix):
    data = setup_security_matrix
    admin = data["admin"]
    doc_admin = data["doc_admin"]
    user_traction = data["user_traction"]
    user_rh = data["user_rh"]
    user_nogroup = data["user_nogroup"]

    doc_act_trac = data["doc_act_trac"]
    doc_act_rh = data["doc_act_rh"]
    doc_indexed = data["doc_indexed_trac"]
    doc_archived = data["doc_archived_trac"]

    # 1. Admin can access all documents
    assert can_access_document(admin, doc_act_trac) is True
    assert can_access_document(admin, doc_act_rh) is True
    assert can_access_document(admin, doc_indexed) is True
    assert can_access_document(admin, doc_archived) is True

    # 2. DocAdmin can access all documents
    assert can_access_document(doc_admin, doc_act_trac) is True
    assert can_access_document(doc_admin, doc_act_rh) is True
    assert can_access_document(doc_admin, doc_indexed) is True
    assert can_access_document(doc_admin, doc_archived) is True

    # 3. ReadOnly user Traction can access only active doc in Traction with group Traction
    assert can_access_document(user_traction, doc_act_trac) is True
    # Mismatched department & security group -> False
    assert can_access_document(user_traction, doc_act_rh) is False
    # Non-active status (indexed, archived) -> False
    assert can_access_document(user_traction, doc_indexed) is False
    assert can_access_document(user_traction, doc_archived) is False

    # 4. ReadOnly user RH can access only active doc in Exploitation with group RH
    assert can_access_document(user_rh, doc_act_rh) is True
    assert can_access_document(user_rh, doc_act_trac) is False

    # 5. ReadOnly user without security group cannot access any document
    assert can_access_document(user_nogroup, doc_act_trac) is False
    assert can_access_document(user_nogroup, doc_act_rh) is False


def test_endpoints_access_matrix(setup_security_matrix):
    data = setup_security_matrix
    user_trac = data["user_traction"]
    doc_act_trac = data["doc_act_trac"]
    doc_act_rh = data["doc_act_rh"]
    doc_indexed = data["doc_indexed_trac"]

    token_trac = create_access_token(user_trac.email, user_trac.role)
    headers_trac = {"Authorization": f"Bearer {token_trac}"}

    # A. GET /documents/{id}
    # Authorized: own department, matching group, active status -> 200
    res_ok = client.get(f"/documents/{doc_act_trac.id}", headers=headers_trac)
    assert res_ok.status_code == 200

    # Denied (wrong department / group) -> 404 (NEVER 403)
    res_denied_dept = client.get(f"/documents/{doc_act_rh.id}", headers=headers_trac)
    assert res_denied_dept.status_code == 404
    assert res_denied_dept.json()["detail"] == "Document non trouvé"

    # Denied (inactive status) -> 404 (NEVER 403)
    res_denied_status = client.get(f"/documents/{doc_indexed.id}", headers=headers_trac)
    assert res_denied_status.status_code == 404
    assert res_denied_status.json()["detail"] == "Document non trouvé"

    # B. GET /documents/{id}/file
    # Authorized -> 200
    res_file_ok = client.get(f"/documents/{doc_act_trac.id}/file", headers=headers_trac)
    assert res_file_ok.status_code == 200

    # Denied -> 404
    res_file_denied = client.get(f"/documents/{doc_act_rh.id}/file", headers=headers_trac)
    assert res_file_denied.status_code == 404
    assert res_file_denied.json()["detail"] == "Document non trouvé"

    # C. Verify audit event "access_denied" is written in DB
    db: Session = SessionLocal()
    try:
        denied_events = db.query(AuditEvent).filter(
            AuditEvent.actor_user_id == user_trac.id,
            AuditEvent.action == "access_denied",
            AuditEvent.entity_type == "document"
        ).all()
        assert len(denied_events) >= 1
    finally:
        db.close()


def test_documents_listing_scoping(setup_security_matrix):
    data = setup_security_matrix
    user_trac = data["user_traction"]
    doc_act_trac = data["doc_act_trac"]
    doc_act_rh = data["doc_act_rh"]

    token_trac = create_access_token(user_trac.email, user_trac.role)
    headers_trac = {"Authorization": f"Bearer {token_trac}"}

    res = client.get("/documents", headers=headers_trac)
    assert res.status_code == 200
    docs = res.json()
    doc_ids = [d["id"] for d in docs]

    # User Traction can only see their accessible active doc, NOT doc_act_rh
    assert doc_act_trac.id in doc_ids
    assert doc_act_rh.id not in doc_ids


def test_document_detail_pages_and_idor_matrix(setup_security_matrix):
    """
    Règle B.1 : Vérifie que le détail du document (avec ses pages) est accessible
    uniquement selon la matrice d'autorisation, et renvoie 404 sinon (IDOR).
    """
    data = setup_security_matrix
    user_trac = data["user_traction"]
    user_rh = data["user_rh"]
    doc_act_trac = data["doc_act_trac"]
    doc_act_rh = data["doc_act_rh"]

    token_trac = create_access_token(user_trac.email, user_trac.role)
    token_rh = create_access_token(user_rh.email, user_rh.role)

    # 1. User Traction accède au détail et aux pages de son document
    res_trac = client.get(f"/documents/{doc_act_trac.id}", headers={"Authorization": f"Bearer {token_trac}"})
    assert res_trac.status_code == 200
    assert "pages" in res_trac.json()

    # 2. User Traction tente d'accéder au document RH -> 404 (IDOR neutralisé)
    res_idor = client.get(f"/documents/{doc_act_rh.id}", headers={"Authorization": f"Bearer {token_trac}"})
    assert res_idor.status_code == 404
    assert res_idor.json()["detail"] == "Document non trouvé"

    # 3. User RH accède au document RH mais se voit refuser le document Traction -> 404
    res_rh_ok = client.get(f"/documents/{doc_act_rh.id}", headers={"Authorization": f"Bearer {token_rh}"})
    assert res_rh_ok.status_code == 200
    assert "pages" in res_rh_ok.json()

    res_rh_denied = client.get(f"/documents/{doc_act_trac.id}", headers={"Authorization": f"Bearer {token_rh}"})
    assert res_rh_denied.status_code == 404


def test_citations_and_evidence_scoping(setup_security_matrix):
    """
    Règle B.1 : Scoping strict des citations et preuves documentaires dans la recherche/RAG.
    Un utilisateur ne reçoit JAMAIS d'extraits, citations ou preuves provenant de documents
    en dehors de son département et de ses groupes de sécurité.
    """
    from unittest.mock import patch
    data = setup_security_matrix
    user_trac = data["user_traction"]
    doc_act_trac = data["doc_act_trac"]
    doc_act_rh = data["doc_act_rh"]

    token_trac = create_access_token(user_trac.email, user_trac.role)

    # Simulation où la recherche dense / hybride remonte à la fois un chunk Traction et un chunk RH
    candidate_chunks = [
        {"document_id": doc_act_trac.id, "text": "Procédure freinage locomotive Traction", "score": 0.95},
        {"document_id": doc_act_rh.id, "text": "Directive confidentielle RH salaires", "score": 0.92}
    ]

    # Mock de génération qui s'appuie sur les chunks filtrés
    def mock_answer_gen(*args, **kwargs):
        # Vérification que le document RH a bien été exclu avant génération
        passed_chunks = kwargs.get("chunks", []) or (args[1] if len(args) > 1 else [])
        for ch in passed_chunks:
            assert ch.get("document_id") != doc_act_rh.id, "Fuite de chunk hors périmètre vers le LLM !"
        return {
            "answer": "Voici la procédure de freinage Traction [1].",
            "citations": [
                {
                    "document_id": doc_act_trac.id,
                    "document_title": doc_act_trac.title,
                    "document_version": doc_act_trac.version,
                    "page_start": 1,
                    "page_end": 1,
                    "excerpt": "Procédure freinage locomotive Traction",
                    "score": 0.95
                }
            ],
            "provider": "ollama",
            "confidence": "high",
            "is_abstain": False
        }

    with patch("app.routers.assistant.generate_answer", side_effect=mock_answer_gen):
        res = client.post(
            "/assistant/query",
            headers={"Authorization": f"Bearer {token_trac}"},
            json={"query": "Quelles sont les consignes ferroviaires ?"}
        )

    assert res.status_code == 200
    citations = res.json().get("citations", [])
    # Seul le document autorisé apparaît dans les citations
    assert all(c["document_id"] != doc_act_rh.id for c in citations)

