import logging
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.schemas import User, UserRole, AuditLog, LoginAttempt
from app.security import hash_password, create_access_token
from app.services.concurrency import user_rate_limiter

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_rate_limit_user():
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ratelimit_user@camrail.net").first()
        if not user:
            user = User(
                email="ratelimit_user@camrail.net",
                password_hash=hash_password("RateLimitPassword123!"),
                full_name="Rate Limit User",
                role=UserRole.READ_ONLY,
                department="Traction",
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_access_token(user.email, user.role)
        yield {
            "user": user,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"}
        }
    finally:
        db.close()


def test_token_not_leaked_in_audit_and_logs(setup_rate_limit_user, caplog):
    """
    Vérifie qu'aucun jeton d'accès ou de rafraîchissement n'est jamais consigné
    dans les journaux d'audit de la base de données ni dans les flux de logs applicatifs.
    """
    data = setup_rate_limit_user
    token = data["token"]
    user = data["user"]

    caplog.set_level(logging.DEBUG)

    # 1. Connexion nominale générant access_token et refresh_token
    login_res = client.post(
        "/auth/login",
        data={"username": user.email, "password": "RateLimitPassword123!"}
    )
    assert login_res.status_code == 200
    issued_access_token = login_res.json()["access_token"]
    issued_refresh_token = login_res.cookies.get("refresh_token", "")

    # 2. Requête authentifiée
    me_res = client.get("/users/me", headers={"Authorization": f"Bearer {issued_access_token}"})
    assert me_res.status_code == 200

    # 3. Vérification des logs d'audit en base
    db: Session = SessionLocal()
    try:
        recent_audits = db.query(AuditLog).order_by(AuditLog.seq.desc()).limit(20).all()
        for audit in recent_audits:
            details_str = audit.details_json or ""
            assert issued_access_token not in details_str, "Access token leaked in AuditLog details_json!"
            if issued_refresh_token:
                assert issued_refresh_token not in details_str, "Refresh token leaked in AuditLog details_json!"
            assert "RateLimitPassword123!" not in details_str, "Password leaked in AuditLog details_json!"
    finally:
        db.close()

    # 4. Vérification dans les logs applicatifs capturés
    captured_logs = caplog.text
    assert issued_access_token not in captured_logs, "Access token leaked in python application logs!"
    if issued_refresh_token:
        assert issued_refresh_token not in captured_logs, "Refresh token leaked in python application logs!"


def test_question_rate_limiting_429(setup_rate_limit_user):
    """
    Vérifie la limitation de débit des questions :
    Au-delà de RATE_LIMIT_PER_MINUTE requêtes dans la fenêtre glissante,
    l'API répond avec HTTP 429 Too Many Requests.
    """
    data = setup_rate_limit_user
    headers = data["headers"]
    user = data["user"]

    user_rate_limiter.reset()
    limit = getattr(settings, "RATE_LIMIT_PER_MINUTE", 10)

    try:
        # Envoi de 'limit' requêtes autorisées
        for idx in range(limit):
            # Simulation via appel direct du rate limiter
            user_rate_limiter.check(user.id)

        # La requête suivante doit déclencher une exception HTTP 429
        with pytest.raises(Exception) as exc_info:
            user_rate_limiter.check(user.id)

        assert "429" in str(exc_info.value) or "Trop de requêtes" in str(exc_info.value)

        # Test sur l'endpoint /assistant/query directement
        res_endpoint = client.post(
            "/assistant/query",
            headers=headers,
            json={"query": "Question sous rate limit"}
        )
        assert res_endpoint.status_code == 429
        assert "Trop de requêtes" in res_endpoint.json()["detail"]
    finally:
        user_rate_limiter.reset()


def test_ip_based_rate_limiting_on_login():
    """
    Vérifie la limitation par adresse IP sur l'authentification :
    Trop d'échecs depuis une même IP déclenchent un blocage HTTP 429 avec Retry-After.
    """
    client_ip = "192.168.100.99"
    headers = {"X-Forwarded-For": client_ip}

    orig_limit = settings.LOGIN_MAX_PER_IP
    settings.LOGIN_MAX_PER_IP = 5
    db: Session = SessionLocal()
    try:
        db.query(LoginAttempt).filter(LoginAttempt.ip == client_ip).delete()
        db.commit()

        # Effectue 5 échecs consécutifs
        for attempt_i in range(5):
            res = client.post(
                "/auth/login",
                data={"username": f"user_{attempt_i}@camrail.net", "password": "BadPassword123!"},
                headers=headers
            )
            assert res.status_code == 401

        # La 6ème tentative depuis cette même IP est bloquée
        blocked_res = client.post(
            "/auth/login",
            data={"username": "another_user@camrail.net", "password": "BadPassword123!"},
            headers=headers
        )
        assert blocked_res.status_code == 429
        assert "Retry-After" in blocked_res.headers
    finally:
        settings.LOGIN_MAX_PER_IP = orig_limit
        db.query(LoginAttempt).filter(LoginAttempt.ip == client_ip).delete()
        db.commit()
        db.close()
