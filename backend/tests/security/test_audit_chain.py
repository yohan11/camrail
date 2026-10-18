import json
import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.schemas import User, AuditLog, UserRole
from app.services.audit import (
    log_audit_event,
    verify_chain,
    mask_sensitive_details,
    format_utc_iso,
    build_canonical_payload,
    compute_entry_hash
)
from app.security import hash_password, create_access_token

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_audit_env():
    """Prépare un utilisateur administrateur et un utilisateur standard pour les tests."""
    db: Session = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == "admin_audit_test@camrail.net").first()
        if not admin_user:
            admin_user = User(
                email="admin_audit_test@camrail.net",
                password_hash=hash_password("SuperAdminAuditPass2026!"),
                full_name="Admin Audit Test",
                role=UserRole.ADMIN.value,
                is_active=True
            )
            db.add(admin_user)

        normal_user = db.query(User).filter(User.email == "user_audit_test@camrail.net").first()
        if not normal_user:
            normal_user = User(
                email="user_audit_test@camrail.net",
                password_hash=hash_password("NormalAuditPass2026!"),
                full_name="Normal Audit Test",
                role=UserRole.READ_ONLY.value,
                is_active=True
            )
            db.add(normal_user)

        db.commit()
        db.refresh(admin_user)
        db.refresh(normal_user)

        admin_token = create_access_token(admin_user.email, admin_user.role)
        normal_token = create_access_token(normal_user.email, normal_user.role)

        yield {
            "admin": admin_user,
            "admin_token": admin_token,
            "normal": normal_user,
            "normal_token": normal_token
        }
    finally:
        db.close()


def test_audit_chain_valid_after_n_writes(setup_audit_env):
    """
    Exigence A & C : La chaîne de hachage est valide après N écritures séquentielles.
    Chaque écriture incrémente seq de 1 et lie prev_hash à l'entry_hash précédent.
    """
    db: Session = SessionLocal()
    try:
        admin = setup_audit_env["admin"]
        initial_ok, initial_count, _ = verify_chain(db)
        assert initial_ok is True, "La chaîne initiale doit être intègre"

        N = 10
        created_events = []
        for i in range(N):
            event = log_audit_event(
                db=db,
                actor_user_id=admin.id,
                action=f"sequential_test_write_{i}",
                entity_type="test_entity",
                entity_id=f"seq-{i}",
                details={"step": i, "description": f"Écriture séquentielle numéro {i}"},
                ip="192.168.1.10"
            )
            assert event is not None
            assert event.seq is not None
            assert len(event.entry_hash) == 64
            created_events.append(event)

        # Vérification globale de la chaîne
        ok, verified_count, broken_seq = verify_chain(db)
        assert ok is True, f"La chaîne d'audit doit être intègre après {N} écritures"
        assert verified_count == initial_count + N
        assert broken_seq is None
    finally:
        db.close()


def test_tampering_detection_modification(setup_audit_env):
    """
    Exigence C & Tests : Modification d'une ligne (trigger contourné).
    verify_chain détecte l'altération et indique le seq exact corrompu.
    """
    db: Session = SessionLocal()
    try:
        admin = setup_audit_env["admin"]
        # Création d'une entrée dédiée au test de falsification
        event = log_audit_event(
            db=db,
            actor_user_id=admin.id,
            action="pre_tamper_event",
            entity_type="tamper_test",
            entity_id="tamper-mod-1",
            details={"original": "legitimate_data"}
        )
        assert event is not None
        target_seq = event.seq

        # Contournement autorisé du trigger par le propriétaire de la table pour le test
        db.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER audit_logs_no_update_delete;"))
        db.execute(
            text("UPDATE audit_logs SET action = 'fraudulently_tampered_action' WHERE seq = :seq"),
            {"seq": target_seq}
        )
        db.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER audit_logs_no_update_delete;"))
        db.commit()

        # Vérification : l'altération doit être détectée avec le bon seq
        ok, verified_count, broken_seq = verify_chain(db)
        assert ok is False, "L'altération de l'action d'une ligne doit briser la chaîne"
        assert broken_seq == target_seq, f"Le numéro seq cassé doit être {target_seq}, obtenu {broken_seq}"

        # Remise en état légitime
        db.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER audit_logs_no_update_delete;"))
        db.execute(
            text("UPDATE audit_logs SET action = 'pre_tamper_event' WHERE seq = :seq"),
            {"seq": target_seq}
        )
        db.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER audit_logs_no_update_delete;"))
        db.commit()

        # La chaîne redevient intègre
        restored_ok, _, _ = verify_chain(db)
        assert restored_ok is True
    finally:
        db.close()


def test_tampering_detection_deletion(setup_audit_env):
    """
    Exigence C & Tests : Suppression d'une ligne au milieu de la chaîne.
    verify_chain détecte le trou dans la séquence et indique le seq manquant.
    """
    db: Session = SessionLocal()
    try:
        admin = setup_audit_env["admin"]
        # Création de 3 événements consécutifs
        e1 = log_audit_event(db, admin.id, "del_test_1", "test", "d1")
        e2 = log_audit_event(db, admin.id, "del_test_2", "test", "d2")
        e3 = log_audit_event(db, admin.id, "del_test_3", "test", "d3")
        assert e1 and e2 and e3
        deleted_seq = e2.seq

        # Sauvegarde des données de e2 pour restauration ultérieure
        e2_backup = {
            "seq": e2.seq,
            "actor_user_id": e2.actor_user_id,
            "user_email": e2.user_email,
            "action": e2.action,
            "entity_type": e2.entity_type,
            "entity_id": e2.entity_id,
            "details_json": e2.details_json,
            "ip": e2.ip,
            "prev_hash": e2.prev_hash,
            "entry_hash": e2.entry_hash,
            "created_at": e2.created_at
        }

        # Contournement du trigger et suppression de e2
        db.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER audit_logs_no_update_delete;"))
        db.execute(text("DELETE FROM audit_logs WHERE seq = :seq"), {"seq": deleted_seq})
        db.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER audit_logs_no_update_delete;"))
        db.commit()

        # Vérification : détection immédiate de la rupture à l'emplacement exact de seq supprimé
        ok, verified_count, broken_seq = verify_chain(db)
        assert ok is False, "La suppression d'un événement au milieu doit briser la chaîne"
        assert broken_seq == deleted_seq, f"Le premier seq cassé doit être {deleted_seq}, obtenu {broken_seq}"

        # Restauration de la ligne supprimée
        db.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER audit_logs_no_update_delete;"))
        db.execute(
            text("""
                INSERT INTO audit_logs (seq, actor_user_id, user_email, action, entity_type, entity_id, details_json, ip, prev_hash, entry_hash, created_at)
                VALUES (:seq, :actor_user_id, :user_email, :action, :entity_type, :entity_id, :details_json, :ip, :prev_hash, :entry_hash, :created_at)
            """),
            e2_backup
        )
        db.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER audit_logs_no_update_delete;"))
        db.commit()

        # Chaîne à nouveau valide
        restored_ok, _, _ = verify_chain(db)
        assert restored_ok is True
    finally:
        db.close()


def test_tampering_detection_insertion_in_middle(setup_audit_env):
    """
    Exigence C & Tests : Insertion frauduleuse d'une ligne au milieu.
    verify_chain détecte la duplication ou la rupture de chaînage cryptographique.
    """
    db: Session = SessionLocal()
    try:
        admin = setup_audit_env["admin"]
        e_first = log_audit_event(db, admin.id, "insert_test_before", "test", "i1")
        e_second = log_audit_event(db, admin.id, "insert_test_after", "test", "i2")
        assert e_first and e_second

        # Tentative d'insertion d'une entrée avec une fausse valeur de seq ou doublon
        db.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER audit_logs_no_update_delete;"))
        # On supprime temporairement l'index unique pour tester l'injection d'un doublon
        db.execute(text("DROP INDEX IF EXISTS ix_audit_logs_seq;"))
        
        # Insertion frauduleuse d'un doublon seq
        db.execute(
            text("""
                INSERT INTO audit_logs (seq, actor_user_id, user_email, action, entity_type, entity_id, details_json, ip, prev_hash, entry_hash, created_at)
                VALUES (:seq, :user_id, 'hacker@evil.com', 'injected_action', 'test', 'bad', '{}', '1.2.3.4', 'fake_prev_hash', 'fake_entry_hash', now())
            """),
            {"seq": e_first.seq, "user_id": admin.id}
        )
        db.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER audit_logs_no_update_delete;"))
        db.commit()

        # Vérification : détection de l'insertion illégitime
        ok, _, broken_seq = verify_chain(db)
        assert ok is False, "L'insertion d'une ligne illégitime au milieu doit briser la chaîne"
        assert broken_seq == e_first.seq

        # Nettoyage
        db.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER audit_logs_no_update_delete;"))
        db.execute(text("DELETE FROM audit_logs WHERE action = 'injected_action';"))
        db.execute(text("CREATE UNIQUE INDEX ix_audit_logs_seq ON audit_logs (seq);"))
        db.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER audit_logs_no_update_delete;"))
        db.commit()

        restored_ok, _, _ = verify_chain(db)
        assert restored_ok is True
    finally:
        db.close()


def test_concurrent_writes_20_threads_no_gaps_valid_chain(setup_audit_env):
    """
    Exigence A.4 & Tests : 20 écritures simultanées (threads).
    Grâce à pg_advisory_xact_lock, la séquence est strictement continue sans trou,
    aucune bifurcation (fork) ne se produit et la chaîne finale est 100% valide.
    """
    admin = setup_audit_env["admin"]
    num_threads = 20

    def worker_write(worker_id: int):
        thread_db: Session = SessionLocal()
        try:
            return log_audit_event(
                db=thread_db,
                actor_user_id=admin.id,
                action=f"concurrent_thread_write_{worker_id}",
                entity_type="concurrency_test",
                entity_id=f"worker-{worker_id}",
                details={"worker_id": worker_id, "thread_active": True},
                ip=f"10.0.0.{worker_id}"
            )
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_write, i) for i in range(num_threads)]
        results = [f.result() for f in futures]

    # Vérification que toutes les écritures ont réussi
    assert len(results) == num_threads
    for res in results:
        assert res is not None
        assert res.seq is not None

    db: Session = SessionLocal()
    try:
        # Contrôle cryptographique complet
        ok, verified_count, broken_seq = verify_chain(db)
        assert ok is True, f"La chaîne doit être parfaitement valide après 20 écritures concurrentes. Erreur à seq={broken_seq}"
        assert broken_seq is None

        # Contrôle de l'absence totale de trou dans les séquences générées
        inserted_seqs = sorted([r.seq for r in results])
        assert len(set(inserted_seqs)) == num_threads, "Chaque thread doit avoir un numéro seq strictement unique"
        min_seq = inserted_seqs[0]
        max_seq = inserted_seqs[-1]
        assert max_seq - min_seq + 1 == num_threads, f"La plage de séquences [{min_seq}, {max_seq}] ne doit contenir aucun trou"
    finally:
        db.close()


def test_database_trigger_refuses_update_and_delete(setup_audit_env):
    """
    Exigence B & Tests : Le trigger PostgreSQL et la révocation de droits interdisent
    UPDATE, DELETE et TRUNCATE au rôle applicatif.
    """
    db: Session = SessionLocal()
    try:
        # Test 1 : Avec le superutilisateur courant, le trigger PL/pgSQL lève une exception
        with pytest.raises(Exception) as exc_update:
            db.execute(text("UPDATE audit_logs SET action = 'unauthorized_mod' WHERE seq = 1;"))
            db.commit()
        db.rollback()
        assert "Audit logs are immutable" in str(exc_update.value)

        with pytest.raises(Exception) as exc_delete:
            db.execute(text("DELETE FROM audit_logs WHERE seq = 1;"))
            db.commit()
        db.rollback()
        assert "Audit logs are immutable" in str(exc_delete.value)

        # Test 2 : Avec le rôle applicatif 'railmind_app', le trigger ou la révocation refuse UPDATE et DELETE
        try:
            db.execute(text("SET ROLE railmind_app;"))
            with pytest.raises(Exception) as exc_app_role:
                db.execute(text("UPDATE audit_logs SET action = 'app_role_tamper' WHERE seq = 1;"))
                db.commit()
            db.rollback()
            assert any(msg in str(exc_app_role.value).lower() for msg in ["droit refusé", "insufficientprivilege", "permission denied", "immutable", "prohibited", "privilège"])

            with pytest.raises(Exception) as exc_app_delete:
                db.execute(text("DELETE FROM audit_logs WHERE seq = 1;"))
                db.commit()
            db.rollback()
            assert any(msg in str(exc_app_delete.value).lower() for msg in ["droit refusé", "insufficientprivilege", "permission denied", "immutable", "prohibited", "privilège"])
        finally:
            db.execute(text("RESET ROLE;"))
            db.commit()
    finally:
        db.close()


def test_sensitive_data_masking_in_details():
    """
    Exigence D & Tests : Le masquage retire password, token, secret, authorization
    et tronque les valeurs textuelles de plus de 500 caractères.
    """
    db: Session = SessionLocal()
    try:
        long_string = "A" * 600
        dirty_details = {
            "password": "cleartext_super_secret_password_12345",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive_payload",
            "client_secret": "my_client_secret_xyz",
            "authorization": "Bearer secret_bearer_token",
            "content": "Raw confidential document text that should not appear here",
            "safe_metadata": "Valeur publique autorisée",
            "nested": {
                "user_password": "nested_password",
                "normal_field": 42
            },
            "array_data": [
                {"token_id": "tok_123"},
                "plain_value"
            ],
            "long_text": long_string
        }

        # 1. Test unitaire direct de mask_sensitive_details
        masked = mask_sensitive_details(dirty_details)
        assert masked["password"] == "[REDACTED]"
        assert masked["token"] == "[REDACTED]"
        assert masked["client_secret"] == "[REDACTED]"
        assert masked["authorization"] == "[REDACTED]"
        assert masked["content"] == "[REDACTED_DOCUMENT_CONTENT]"
        assert masked["safe_metadata"] == "Valeur publique autorisée"
        assert masked["nested"]["user_password"] == "[REDACTED]"
        assert masked["nested"]["normal_field"] == 42
        assert masked["array_data"][0]["token_id"] == "[REDACTED]"
        assert masked["array_data"][1] == "plain_value"
        assert len(masked["long_text"]) < 600
        assert "[TRUNCATED]" in masked["long_text"]

        # 2. Test d'insertion en base via log_audit_event
        ev = log_audit_event(
            db=db,
            actor_user_id=None,
            action="masking_verification_event",
            entity_type="security_test",
            entity_id="mask-1",
            details=dirty_details,
            ip="127.0.0.1"
        )
        assert ev is not None
        assert ev.details_json is not None
        assert "cleartext_super_secret_password_12345" not in ev.details_json
        assert "sensitive_payload" not in ev.details_json
        assert "my_client_secret_xyz" not in ev.details_json
        assert "secret_bearer_token" not in ev.details_json
        assert "Raw confidential document text" not in ev.details_json

        saved_details = json.loads(ev.details_json)
        assert saved_details["password"] == "[REDACTED]"
        assert saved_details["safe_metadata"] == "Valeur publique autorisée"
    finally:
        db.close()


def test_dashboard_verify_endpoint(setup_audit_env):
    """
    Exigence C.3 : GET /api/v1/dashboard/audit/verify
    - Réservé aux administrateurs (403 pour rôle standard)
    - Retourne le statut normalisé "Intégrité du journal : vérifiée"
    - Écrit un événement d'audit 'audit_verified' à chaque appel.
    """
    admin_token = setup_audit_env["admin_token"]
    normal_token = setup_audit_env["normal_token"]

    # 1. Refus pour utilisateur standard (non admin)
    res_forbidden = client.get(
        "/api/v1/dashboard/audit/verify",
        headers={"Authorization": f"Bearer {normal_token}"}
    )
    assert res_forbidden.status_code == 403

    # 2. Succès pour administrateur
    res_admin = client.get(
        "/api/v1/dashboard/audit/verify",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert data["ok"] is True
    assert data["message"] == "Intégrité du journal : vérifiée"
    assert data["verified_count"] > 0
    assert data["first_broken_seq"] is None

    # 3. Vérification que l'événement 'audit_verified' a bien été consigné dans la chaîne
    db: Session = SessionLocal()
    try:
        last_audit = db.query(AuditLog).order_by(AuditLog.seq.desc()).first()
        assert last_audit.action == "audit_verified"
        assert last_audit.actor_user_id == setup_audit_env["admin"].id
        
        # Et la chaîne reste 100% intègre après cet ajout
        ok, _, _ = verify_chain(db)
        assert ok is True
    finally:
        db.close()
