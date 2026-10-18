import os
import sys
import time
import uuid
import json
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import jwt
from pydantic import ValidationError

from app.main import app
from app.config import Settings, settings
from app.database import SessionLocal
from app.models.schemas import User, UserRole, RefreshToken, RevokedToken, LoginAttempt, AuditEvent
from app.security import (
    hash_password,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    DUMMY_BCRYPT_HASH,
)

client = TestClient(app)


def test_jwt_secret_validation_production():
    """
    Vérifie les contraintes de robustesse du secret JWT :
    - En production : refus strict si secret trop court, trivial ou caractères répétés.
    - En développement : simple avertissement (autorisé).
    """
    # 1. En production : secret trop court (< 32 caractères)
    with pytest.raises((ValueError, ValidationError)):
        Settings(APP_ENV="production", JWT_SECRET="short_secret_under_32")

    # 2. En production : secret faible / trivial
    with pytest.raises((ValueError, ValidationError)):
        Settings(APP_ENV="production", JWT_SECRET="changeme_changeme_changeme_changeme")

    # 3. En production : caractère répété
    with pytest.raises((ValueError, ValidationError)):
        Settings(APP_ENV="production", JWT_SECRET="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    # 4. En production : secret robuste (>= 32 caractères avec entropie)
    prod_valid = Settings(
        APP_ENV="production",
        JWT_SECRET="vEry-StR0ng-S3cr3t-w1th-pl3nty-0f-3ntr0py-987654321"
    )
    assert prod_valid.JWT_SECRET.startswith("vEry")

    # 5. En développement : secret faible accepté (avec warning log)
    dev_settings = Settings(APP_ENV="development", JWT_SECRET="weak_dev_secret")
    assert dev_settings.JWT_SECRET == "weak_dev_secret"


def test_access_token_claims_and_validation():
    """
    Vérifie la présence et la validation des claims du jeton d'accès :
    sub, exp, iat, jti, iss="railmind", aud="railmind-api", type="access".
    Teste le rejet de : alg none, jeton altéré, jeton expiré, mauvais iss/aud,
    rôle modifié côté client (ignoré côté serveur), utilisateur inactif, révocation logout.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "hardening_test@camrail.net").first()
        if not user:
            user = User(
                email="hardening_test@camrail.net",
                password_hash=hash_password("PassHardening123!"),
                full_name="Hardening User",
                role=UserRole.READ_ONLY,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 1. Présence des claims obligatoires
        token = create_access_token(user.email, user.role)
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="railmind",
            audience="railmind-api"
        )
        assert payload.get("sub") == user.email
        assert payload.get("iss") == "railmind"
        assert payload.get("aud") == "railmind-api"
        assert payload.get("type") == "access"
        assert payload.get("jti") is not None
        assert payload.get("iat") is not None
        assert payload.get("exp") is not None

        # 2. Rejet de l'algorithme "none" (sans signature)
        none_token = jwt.encode(
            {
                "sub": user.email,
                "iss": "railmind",
                "aud": "railmind-api",
                "type": "access",
                "jti": str(uuid.uuid4())
            },
            key="",
            algorithm="none"
        )
        res_none = client.get("/users/me", headers={"Authorization": f"Bearer {none_token}"})
        assert res_none.status_code == 401

        # 3. Rejet d'un jeton altéré
        tampered_token = token[:-4] + "abcd"
        res_tampered = client.get("/users/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert res_tampered.status_code == 401

        # 4. Rejet d'un jeton expiré
        expired_token = create_access_token(user.email, user.role, expires_delta=timedelta(seconds=-10))
        res_exp = client.get("/users/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert res_exp.status_code == 401

        # 5. Rejet d'un mauvais issuer / audience
        wrong_iss = jwt.encode(
            {
                "sub": user.email,
                "iss": "evil_issuer",
                "aud": "railmind-api",
                "type": "access",
                "jti": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=10)
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )
        assert client.get("/users/me", headers={"Authorization": f"Bearer {wrong_iss}"}).status_code == 401

        wrong_aud = jwt.encode(
            {
                "sub": user.email,
                "iss": "railmind",
                "aud": "evil_audience",
                "type": "access",
                "jti": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=10)
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )
        assert client.get("/users/me", headers={"Authorization": f"Bearer {wrong_aud}"}).status_code == 401

        # 6. Rôle modifié dans le payload est IGNORÉ (le rôle en base fait foi)
        faked_admin_token = jwt.encode(
            {
                "sub": user.email,
                "role": "admin", # Rôle forgé
                "iss": "railmind",
                "aud": "railmind-api",
                "type": "access",
                "jti": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=10)
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )
        # Tentative d'accès à un endpoint réservé aux admins : POST /users/
        res_forge = client.post(
            "/users/",
            headers={"Authorization": f"Bearer {faked_admin_token}"},
            json={
                "email": f"fake_{uuid.uuid4()}@camrail.net",
                "password": "Password1234!",
                "full_name": "Test User",
                "role": "read_only"
            }
        )
        assert res_forge.status_code == 403

        # 7. Utilisateur désactivé après émission du jeton (échec immédiat)
        user.is_active = False
        db.commit()
        token_active = create_access_token(user.email, user.role)
        res_inactive = client.get("/users/me", headers={"Authorization": f"Bearer {token_active}"})
        assert res_inactive.status_code == 401
        
        # Réactivation
        user.is_active = True
        db.commit()

        # 8. Jeton d'accès révoqué via logout
        logout_token = create_access_token(user.email, user.role)
        assert client.get("/users/me", headers={"Authorization": f"Bearer {logout_token}"}).status_code == 200

        res_logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {logout_token}"})
        assert res_logout.status_code == 200

        res_revoked = client.get("/users/me", headers={"Authorization": f"Bearer {logout_token}"})
        assert res_revoked.status_code == 401
    finally:
        db.close()


def test_refresh_token_lifecycle_and_reuse_detection():
    """
    Vérifie le cycle de vie du refresh token :
    - Rotation nominale à chaque rafraîchissement
    - Révocation de l'ancien jeton
    - Détection de réutilisation : révocation de tous les refresh tokens de l'utilisateur + alerte audit critique.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "refresh_cycle@camrail.net").first()
        if not user:
            user = User(
                email="refresh_cycle@camrail.net",
                password_hash=hash_password("RefreshPass123!"),
                full_name="Refresh Cycle User",
                role=UserRole.READ_ONLY,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Nettoyage des anciens jetons pour cet utilisateur
        db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()
        db.commit()

        # 1. Connexion initiale
        login_res = client.post(
            "/auth/login",
            data={"username": user.email, "password": "RefreshPass123!"}
        )
        assert login_res.status_code == 200
        assert "refresh_token" in login_res.cookies
        raw_token_1 = login_res.cookies["refresh_token"]

        token_hash_1 = hash_refresh_token(raw_token_1)
        db_token_1 = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash_1).first()
        assert db_token_1 is not None
        assert db_token_1.revoked_at is None

        # 2. Rotation nominale : POST /auth/refresh avec le jeton 1
        client.cookies.set("refresh_token", raw_token_1)
        ref_res_1 = client.post("/auth/refresh")
        assert ref_res_1.status_code == 200
        data_1 = ref_res_1.json()
        assert "access_token" in data_1
        raw_token_2 = ref_res_1.cookies.get("refresh_token")
        assert raw_token_2 is not None
        assert raw_token_2 != raw_token_1

        # L'ancien jeton 1 doit être marqué comme révoqué
        db.refresh(db_token_1)
        assert db_token_1.revoked_at is not None
        assert db_token_1.replaced_by is not None

        # Le nouveau jeton 2 doit être actif en base
        token_hash_2 = hash_refresh_token(raw_token_2)
        db_token_2 = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash_2).first()
        assert db_token_2 is not None
        assert db_token_2.revoked_at is None

        # 3. DÉTECTION DE RÉUTILISATION (Attaque par rejeu du jeton 1 déjà révoqué)
        client.cookies.set("refresh_token", raw_token_1)
        reuse_res = client.post("/auth/refresh")
        assert reuse_res.status_code == 401

        # Tous les jetons de l'utilisateur (y compris le jeton 2 valide) doivent être révoqués
        active_count = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None)
        ).count()
        assert active_count == 0

        # Vérification de l'événement d'audit 'refresh_reuse_detected'
        audit_entry = db.query(AuditEvent).filter(
            AuditEvent.action == "refresh_reuse_detected"
        ).order_by(AuditEvent.created_at.desc()).first()
        assert audit_entry is not None
        assert json.loads(audit_entry.details_json).get("severity") == "CRITICAL"

        # Le jeton 2 ne fonctionne plus non plus
        client.cookies.set("refresh_token", raw_token_2)
        ref_res_2 = client.post("/auth/refresh")
        assert ref_res_2.status_code == 401
    finally:
        db.close()


def test_bruteforce_protection_and_timing_mitigation():
    """
    Vérifie la protection brute force et l'atténuation des attaques par analyse temporelle :
    - 5 échecs consécutifs -> verrouillage 429 avec Retry-After
    - Message strictement identique que l'utilisateur existe ou non
    - Déverrouillage administrateur via POST /users/{id}/unlock
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "bruteforce_target@camrail.net").first()
        if not user:
            user = User(
                email="bruteforce_target@camrail.net",
                password_hash=hash_password("ValidPassword123!"),
                full_name="Brute Target",
                role=UserRole.READ_ONLY,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Purge préalable des tentatives pour cet email
        db.query(LoginAttempt).filter(LoginAttempt.email_lower == user.email.lower()).delete()
        db.commit()

        # 1. Exécution de 5 tentatives erronées consécutives
        for attempt_idx in range(5):
            res = client.post(
                "/auth/login",
                data={"username": user.email, "password": "WrongPassword!"}
            )
            assert res.status_code == 401
            assert res.json()["detail"] == "Email ou mot de passe incorrect."

        # 2. La 6ème tentative doit être verrouillée avec HTTP 429 et Retry-After
        lock_res = client.post(
            "/auth/login",
            data={"username": user.email, "password": "WrongPassword!"}
        )
        assert lock_res.status_code == 429
        assert "Retry-After" in lock_res.headers
        assert "Trop de tentatives" in lock_res.json()["detail"]

        # Événement d'audit account_locked enregistré
        lock_audit = db.query(AuditEvent).filter(
            AuditEvent.action == "account_locked",
            AuditEvent.entity_id == str(user.id)
        ).first()
        assert lock_audit is not None

        # 3. Déverrouillage administrateur POST /users/{id}/unlock
        admin = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).first()
        assert admin is not None
        admin_token = create_access_token(admin.email, admin.role)

        unlock_res = client.post(
            f"/users/{user.id}/unlock",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert unlock_res.status_code == 200
        assert "déverrouillé" in unlock_res.json()["detail"]

        # Connexion avec le mot de passe valide réussit désormais
        ok_res = client.post(
            "/auth/login",
            data={"username": user.email, "password": "ValidPassword123!"}
        )
        assert ok_res.status_code == 200

        # 4. Atténuation des attaques par analyse temporelle (timing attacks)
        # Comparaison du temps de réponse : utilisateur inexistant vs mot de passe erroné
        times_unknown = []
        for _ in range(3):
            t0 = time.perf_counter()
            r_unk = client.post(
                "/auth/login",
                data={"username": f"nonexistent_{uuid.uuid4()}@camrail.net", "password": "Password123!"}
            )
            times_unknown.append(time.perf_counter() - t0)
            assert r_unk.status_code == 401
            assert r_unk.json()["detail"] == "Email ou mot de passe incorrect."

        times_bad_pwd = []
        for _ in range(3):
            t0 = time.perf_counter()
            r_bad = client.post(
                "/auth/login",
                data={"username": user.email, "password": "PasswordErrone123!"}
            )
            times_bad_pwd.append(time.perf_counter() - t0)
            assert r_bad.status_code == 401
            assert r_bad.json()["detail"] == "Email ou mot de passe incorrect."

        avg_unk = sum(times_unknown) / len(times_unknown)
        avg_bad = sum(times_bad_pwd) / len(times_bad_pwd)

        # Les deux calculs effectuent un tour de bcrypt (~50ms à 300ms)
        assert avg_unk > 0.03
        assert avg_bad > 0.03
        # Les moyennes doivent être comparables (facteur < 3.0)
        ratio = max(avg_unk, avg_bad) / min(avg_unk, avg_bad)
        assert ratio < 3.0
    finally:
        db.close()


def test_demo_accounts_production_protection():
    """
    Vérifie la protection des comptes de démo en production :
    - seed_demo.py refuse de s'exécuter en production (exit code 1).
    - Le démarrage en production désactive tout compte de démo utilisant le mot de passe par défaut.
    """
    import subprocess
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["JWT_SECRET"] = "a_very_secure_production_secret_key_exceeding_32_characters"
    
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    seed_script = os.path.join(backend_dir, "seed_demo.py")

    proc = subprocess.run(
        [sys.executable, seed_script],
        env=env,
        capture_output=True,
        text=True
    )
    assert proc.returncode == 1
    assert "interdite en environnement de production" in (proc.stderr + proc.stdout)

    # 2. Vérification de la désactivation des comptes de démo par défaut au démarrage
    db = SessionLocal()
    try:
        from app.main import startup_event
        demo_admin = db.query(User).filter(User.email == "admin@camrail.net").first()
        if demo_admin:
            demo_admin.password_hash = hash_password("adminpassword")
            demo_admin.is_active = True
            db.commit()

            orig_env = settings.APP_ENV
            try:
                settings.APP_ENV = "production"
                startup_event()

                db.refresh(demo_admin)
                assert demo_admin.is_active is False

                audit_demo = db.query(AuditEvent).filter(
                    AuditEvent.action == "demo_account_disabled"
                ).order_by(AuditEvent.created_at.desc()).first()
                assert audit_demo is not None
            finally:
                settings.APP_ENV = orig_env
                db.query(User).filter(User.email.in_(["admin@camrail.net", "docadmin@camrail.net", "readonly@camrail.net"])).update({"is_active": True})
                db.commit()
    finally:
        db.close()
