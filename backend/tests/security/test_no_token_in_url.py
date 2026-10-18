import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.schemas import User, Document, UserRole
from app.security import hash_password, create_access_token

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_user_and_doc():
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "notoken_user@camrail.net").first()
        if not user:
            user = User(
                email="notoken_user@camrail.net",
                password_hash=hash_password("pass123"),
                full_name="NoToken User",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        doc = db.query(Document).first()
        token = create_access_token(user.email, user.role)

        yield {
            "user": user,
            "doc_id": doc.id if doc else 1,
            "token": token
        }
    finally:
        db.close()


def test_get_file_with_query_param_token_returns_401(setup_user_and_doc):
    """
    Règle B : Plus aucun jeton dans une URL.
    GET /documents/{id}/file?token=... sans en-tête Authorization doit impérativement retourner 401.
    """
    data = setup_user_and_doc
    doc_id = data["doc_id"]
    token = data["token"]

    # 1. Avec ?token= dans l'URL mais sans en-tête Authorization -> 401
    resp = client.get(f"/documents/{doc_id}/file?token={token}")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"

    # 2. Sans aucun token ni en-tête -> 401
    resp_no_auth = client.get(f"/documents/{doc_id}/file")
    assert resp_no_auth.status_code == 401
    assert resp_no_auth.json()["detail"] == "Not authenticated"

    # 3. Avec en-tête Authorization: Bearer -> Authentification acceptée (non 401)
    resp_valid = client.get(
        f"/documents/{doc_id}/file",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_valid.status_code in [200, 404]
    # Le statut est 200 (si fichier présent) ou 404 (si fichier physique absent), mais JAMAIS 401
    assert resp_valid.status_code != 401
