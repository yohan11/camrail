"""add audit hash chain and triggers

Revision ID: a831e5f38102
Revises: f92a18b74c01
Create Date: 2026-10-18 15:45:00.000000

NOTE DE SÉCURITÉ & DOCUMENTATION DES LIMITES :
==============================================
Cette migration configure une protection en profondeur à deux niveaux :
1. Protection au niveau base de données (Triggers PostgreSQL et REVOKE) :
   - Un trigger BEFORE UPDATE OR DELETE et BEFORE TRUNCATE interdit formellement
     toute modification ou suppression directe de lignes.
   - Les privilèges UPDATE, DELETE, TRUNCATE sont révoqués pour le rôle applicatif 'railmind_app'.
   
   LIMITE ARCHITECTURALE DOCUMENTÉE :
   Le propriétaire de la table (table owner) ou un super-administrateur PostgreSQL a le pouvoir
   d'altérer les droits ou de désactiver temporairement les triggers (ex: DISABLE TRIGGER).
   C'est la raison d'être de la chaîne de hachage cryptographique HMAC-SHA256 :
   même si le trigger est contourné en base de données, la fonction de vérification
   (verify_chain / scripts/verify_audit_chain.py) détectera immédiatement toute altération,
   suppression ou insertion frauduleuse en identifiant avec exactitude le premier numéro 'seq' corrompu.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
import json
import hmac
import hashlib
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = 'a831e5f38102'
down_revision = 'f92a18b74c01'
branch_labels = None
depends_on = None


def format_utc_iso(dt):
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def mask_sensitive(data, max_len=500):
    if data is None:
        return None
    sensitive_keys = {"password", "token", "secret", "authorization", "auth_header", "api_key", "cookie"}
    doc_keys = {"content", "raw_text", "document_content", "file_content", "extracted_text", "page_content"}
    if isinstance(data, dict):
        res = {}
        for k, v in data.items():
            kl = str(k).lower()
            if any(s in kl for s in sensitive_keys):
                res[k] = "[REDACTED]"
            elif any(s in kl for s in doc_keys):
                res[k] = "[REDACTED_DOCUMENT_CONTENT]"
            else:
                res[k] = mask_sensitive(v, max_len)
        return res
    elif isinstance(data, list):
        return [mask_sensitive(x, max_len) for x in data]
    elif isinstance(data, str):
        if len(data) > max_len:
            return data[:max_len] + "...[TRUNCATED]"
        return data
    return data


def build_canonical(seq, created_at_iso, user_id, user_email, action, entity_type, entity_id, details, ip):
    payload = {
        "action": str(action),
        "created_at": str(created_at_iso),
        "details": details,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "entity_type": str(entity_type) if entity_type is not None else None,
        "ip": str(ip) if ip is not None else None,
        "seq": int(seq),
        "user_email": str(user_email) if user_email is not None else None,
        "user_id": int(user_id) if user_id is not None else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_hash(prev_hash, canonical_json, key):
    data = (prev_hash + canonical_json).encode("utf-8")
    return hmac.new(key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Renommer la table audit_events -> audit_logs
    op.rename_table('audit_events', 'audit_logs')

    # Vue rétrocompatible pour les requêtes résiduelles
    conn.execute(text("CREATE OR REPLACE VIEW audit_events AS SELECT * FROM audit_logs;"))

    # 2. Ajout des colonnes requises (temporairement nullables pour le backfill)
    op.add_column('audit_logs', sa.Column('seq', sa.Integer(), nullable=True))
    op.add_column('audit_logs', sa.Column('prev_hash', sa.String(length=64), nullable=True))
    op.add_column('audit_logs', sa.Column('entry_hash', sa.String(length=64), nullable=True))
    op.add_column('audit_logs', sa.Column('ip', sa.String(length=100), nullable=True))
    op.add_column('audit_logs', sa.Column('user_email', sa.String(length=255), nullable=True))

    # 3. Remplissage des lignes existantes dans l'ordre chronologique
    # Récupération de la clé HMAC depuis les configurations
    from app.config import settings
    hmac_key = getattr(settings, "AUDIT_HMAC_KEY", "") or "railmind_audit_tamperproof_hmac_secret_key_prod_2026_fixed"

    # Récupération des emails utilisateurs pour enrichir l'audit
    user_rows = conn.execute(text("SELECT id, email FROM users;")).fetchall()
    user_map = {row[0]: row[1] for row in user_rows}

    # Lecture de toutes les lignes audit_logs existantes
    existing_rows = conn.execute(
        text("SELECT id, actor_user_id, action, entity_type, entity_id, details_json, created_at FROM audit_logs ORDER BY created_at ASC, id ASC;")
    ).fetchall()

    seq = 1
    prev_hash = "GENESIS"

    for r in existing_rows:
        row_id = r[0]
        actor_user_id = r[1]
        action = r[2]
        entity_type = r[3]
        entity_id = r[4]
        details_raw = r[5]
        created_at_val = r[6]

        user_email = user_map.get(actor_user_id) if actor_user_id else None

        details_obj = None
        if details_raw:
            try:
                details_obj = json.loads(details_raw)
            except Exception:
                details_obj = details_raw
        safe_details = mask_sensitive(details_obj)
        details_json_safe = json.dumps(safe_details) if safe_details is not None else None

        created_at_iso = format_utc_iso(created_at_val)
        canonical_json = build_canonical(
            seq=seq,
            created_at_iso=created_at_iso,
            user_id=actor_user_id,
            user_email=user_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=safe_details,
            ip=None
        )
        entry_hash = compute_hash(prev_hash, canonical_json, hmac_key)

        conn.execute(
            text("""
                UPDATE audit_logs
                SET seq = :seq,
                    prev_hash = :prev_hash,
                    entry_hash = :entry_hash,
                    user_email = :user_email,
                    details_json = :details_json
                WHERE id = :id
            """),
            {
                "seq": seq,
                "prev_hash": prev_hash,
                "entry_hash": entry_hash,
                "user_email": user_email,
                "details_json": details_json_safe,
                "id": row_id
            }
        )
        prev_hash = entry_hash
        seq += 1

    # 4. Passer les colonnes de la chaîne en NOT NULL
    op.alter_column('audit_logs', 'seq', nullable=False)
    op.alter_column('audit_logs', 'prev_hash', nullable=False)
    op.alter_column('audit_logs', 'entry_hash', nullable=False)

    # 5. Index unique sur seq
    op.create_index(op.f('ix_audit_logs_seq'), 'audit_logs', ['seq'], unique=True)

    # 6. Protection dans la base : Trigger empêchant UPDATE, DELETE, TRUNCATE
    conn.execute(text("""
        CREATE OR REPLACE FUNCTION prevent_audit_logs_tampering()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit logs are immutable: UPDATE, DELETE, and TRUNCATE are strictly prohibited.';
        END;
        $$ LANGUAGE plpgsql;
    """))

    conn.execute(text("""
        DROP TRIGGER IF EXISTS audit_logs_no_update_delete ON audit_logs;
        CREATE TRIGGER audit_logs_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_logs_tampering();
    """))

    conn.execute(text("""
        DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs;
        CREATE TRIGGER audit_logs_no_truncate
        BEFORE TRUNCATE ON audit_logs
        FOR EACH STATEMENT
        EXECUTE FUNCTION prevent_audit_logs_tampering();
    """))

    # 7. Révocation des droits pour le rôle applicatif 'railmind_app'
    conn.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'railmind_app') THEN
                REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM railmind_app;
            END IF;
        END $$;
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Supprimer les triggers et la fonction
    conn.execute(text("DROP TRIGGER IF EXISTS audit_logs_no_update_delete ON audit_logs;"))
    conn.execute(text("DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs;"))
    conn.execute(text("DROP FUNCTION IF EXISTS prevent_audit_logs_tampering();"))

    # Réattribuer les droits si le rôle existe
    conn.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'railmind_app') THEN
                GRANT UPDATE, DELETE, TRUNCATE ON audit_logs TO railmind_app;
            END IF;
        END $$;
    """))

    # Supprimer l'index unique
    op.drop_index(op.f('ix_audit_logs_seq'), table_name='audit_logs')

    # Supprimer les colonnes ajoutées
    op.drop_column('audit_logs', 'user_email')
    op.drop_column('audit_logs', 'ip')
    op.drop_column('audit_logs', 'entry_hash')
    op.drop_column('audit_logs', 'prev_hash')
    op.drop_column('audit_logs', 'seq')

    # Supprimer la vue rétrocompatible
    conn.execute(text("DROP VIEW IF EXISTS audit_events;"))

    # Renommer la table vers audit_events
    op.rename_table('audit_logs', 'audit_events')
