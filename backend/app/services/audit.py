import json
import logging
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.models.schemas import AuditLog, User

logger = logging.getLogger(__name__)

# Identifiant 64-bit unique pour le verrou transactionnel PostgreSQL (pg_advisory_xact_lock)
# Empêche toute bifurcation de séquence (fork) ou race condition lors des écritures concurrentes
AUDIT_ADVISORY_LOCK_ID = 847291038491
GENESIS_HASH = "GENESIS"

SENSITIVE_KEYS = {"password", "token", "secret", "authorization", "auth_header", "api_key", "cookie"}
DOCUMENT_CONTENT_KEYS = {"content", "raw_text", "document_content", "file_content", "extracted_text", "page_content"}


def get_client_ip(request: Any) -> Optional[str]:
    """
    Extrait l'adresse IP du client à partir de l'objet Request FastAPI / Starlette
    en respectant la liste des reverse proxies de confiance (TRUSTED_PROXIES).
    """
    if request is None:
        return None
    client_host = getattr(getattr(request, "client", None), "host", "127.0.0.1")
    trusted_proxies = getattr(settings, "trusted_proxies_list", [])
    if trusted_proxies and client_host in trusted_proxies:
        forwarded_for = getattr(request, "headers", {}).get("x-forwarded-for")
        if forwarded_for:
            ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
            if ips:
                return ips[0]
    return client_host


def mask_sensitive_details(data: Any, max_string_len: int = 500) -> Any:
    """
    Règle de sécurité : le champ details ne contient JAMAIS de mot de passe, de jeton,
    de secret ni de contenu de document.
    Masque récursivement les clés sensibles et tronque les chaînes trop longues (> max_string_len).
    """
    if data is None:
        return None
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in SENSITIVE_KEYS):
                masked[k] = "[REDACTED]"
            elif any(s in k_lower for s in DOCUMENT_CONTENT_KEYS):
                masked[k] = "[REDACTED_DOCUMENT_CONTENT]"
            else:
                masked[k] = mask_sensitive_details(v, max_string_len)
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_details(item, max_string_len) for item in data]
    elif isinstance(data, str):
        if len(data) > max_string_len:
            return data[:max_string_len] + "...[TRUNCATED]"
        return data
    else:
        return data


def format_utc_iso(dt: Union[datetime, str]) -> str:
    """
    Formate un datetime en chaîne canonique UTC ISO avec microsecondes et suffixe 'Z'.
    Ex: 2026-10-18T14:30:00.123456Z
    Garantit une sérialisation 100% déterministe entre insertion et vérification.
    """
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def build_canonical_payload(
    seq: int,
    created_at_iso: str,
    user_id: Optional[int],
    user_email: Optional[str],
    action: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
    details: Optional[Dict[str, Any]],
    ip: Optional[str]
) -> str:
    """
    Construit le JSON canonique avec clés triées alphabétiquement et sans espaces :
    {action, created_at, details, entity_id, entity_type, ip, seq, user_email, user_id}
    """
    payload_dict = {
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
    return json.dumps(payload_dict, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_entry_hash(prev_hash: str, canonical_json: str, key: Optional[str] = None) -> str:
    """
    Calcule entry_hash = HMAC-SHA256(AUDIT_HMAC_KEY, prev_hash + JSON canonique).
    Retourne la chaîne hexadécimale de 64 caractères.
    """
    hmac_key = key or getattr(settings, "AUDIT_HMAC_KEY", "")
    if not hmac_key:
        raise ValueError("AUDIT_HMAC_KEY est requis pour calculer le hachage d'audit.")
    data = (prev_hash + canonical_json).encode("utf-8")
    return hmac.new(hmac_key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def log_audit_event(
    db: Session,
    actor_user_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip: Optional[str] = None,
    request: Optional[Any] = None,
    user_email: Optional[str] = None,
    created_at: Optional[datetime] = None
) -> Optional[AuditLog]:
    """
    Insère un événement d'audit dans la chaîne de hachage infalsifiable.
    
    Sécurité & Concurrence multi-workers :
    1. Dans la transaction, prend un verrou consultatif PostgreSQL exclusif (pg_advisory_xact_lock)
       pour éliminer tout risque de bifurcation (fork) ou de collision de seq.
    2. Lit la dernière entrée enregistrée pour récupérer seq et entry_hash (devenant prev_hash).
       Si la table est vide, seq=1 et prev_hash="GENESIS".
    3. Masque récursivement les clés sensibles (password, token, secret...) dans details.
    4. Calcule entry_hash = HMAC-SHA256(AUDIT_HMAC_KEY, prev_hash + JSON canonique).
    5. Insère l'enregistrement et valide la transaction (commit).
    """
    try:
        # Résolution de l'IP depuis request si fournie
        if ip is None and request is not None:
            ip = get_client_ip(request)

        # Résolution de l'email si non fourni
        if user_email is None and actor_user_id is not None:
            try:
                user = db.query(User).filter(User.id == actor_user_id).first()
                if user:
                    user_email = user.email
            except Exception:
                pass

        # Masquage des données sensibles
        safe_details = mask_sensitive_details(details)

        # Verrouillage consultatif sous PostgreSQL pour écriture concurrente stricte sans fork
        try:
            is_postgres = db.bind and getattr(db.bind.dialect, "name", "") == "postgresql"
            if is_postgres:
                db.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": AUDIT_ADVISORY_LOCK_ID}
                )
        except Exception as lock_err:
            logger.warning(f"Impossible de poser pg_advisory_xact_lock: {lock_err}")

        # Lecture de la dernière ligne
        last_entry = db.query(AuditLog).order_by(AuditLog.seq.desc()).first()
        if last_entry is None:
            seq = 1
            prev_hash = GENESIS_HASH
        else:
            seq = last_entry.seq + 1
            prev_hash = last_entry.entry_hash

        # Horodatage UTC déterministe (sans décalage de fuseau sur TIMESTAMP postgres)
        if created_at is None:
            event_time = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            if created_at.tzinfo is not None:
                event_time = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                event_time = created_at
        created_at_iso = format_utc_iso(event_time)

        # Construction du JSON canonique et du HMAC
        canonical_json = build_canonical_payload(
            seq=seq,
            created_at_iso=created_at_iso,
            user_id=actor_user_id,
            user_email=user_email,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=safe_details,
            ip=ip
        )
        entry_hash = compute_entry_hash(prev_hash, canonical_json)

        # Préparation du JSON stocké
        details_json = json.dumps(safe_details) if safe_details is not None else None

        audit = AuditLog(
            seq=seq,
            actor_user_id=actor_user_id,
            user_email=user_email,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details_json=details_json,
            ip=ip,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            created_at=event_time
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
    except Exception as e:
        db.rollback()
        logger.error(f"Échec critique de journalisation d'audit : {e}")
        return None


def verify_chain(db: Session, key: Optional[str] = None) -> Tuple[bool, int, Optional[int]]:
    """
    Vérifie l'intégrité cryptographique complète du journal d'audit.
    
    Contrôles effectués pour chaque entrée dans l'ordre croissant de seq :
    1. Continuité stricte de la séquence seq (commence à 1, sans aucun trou ni doublon).
    2. Continuité de la chaîne de hachage (prev_hash du premier = 'GENESIS',
       prev_hash des suivants = entry_hash du précédent).
    3. Recalcul et comparaison du HMAC-SHA256 (détecte toute modification d'un champ).
    
    Retourne :
        (ok, nombre_vérifié, premier_seq_cassé)
        - ok: True si 100% de la chaîne est intègre, False sinon.
        - nombre_vérifié: Nombre d'enregistrements consécutifs vérifiés avec succès.
        - premier_seq_cassé: Le numéro 'seq' du premier événement altéré/manquant, ou None si valide.
    """
    rows = db.query(AuditLog).order_by(AuditLog.seq.asc()).all()
    if not rows:
        return True, 0, None

    expected_seq = 1
    expected_prev_hash = GENESIS_HASH
    verified_count = 0

    for row in rows:
        # Contrôle 1 : Continuité stricte de la séquence
        if row.seq != expected_seq:
            # Trou ou doublon dans la séquence
            broken_seq = expected_seq if row.seq > expected_seq else row.seq
            logger.warning(
                f"Rupture de séquence d'audit : seq attendu {expected_seq}, trouvé {row.seq}"
            )
            return False, verified_count, broken_seq

        # Contrôle 2 : Chaînage prev_hash
        if row.prev_hash != expected_prev_hash:
            logger.warning(
                f"Rupture de chaînage prev_hash pour seq={row.seq}: attendu {expected_prev_hash}, trouvé {row.prev_hash}"
            )
            return False, verified_count, row.seq

        # Contrôle 3 : Recalcul du HMAC-SHA256 sur les données canoniques
        created_at_iso = format_utc_iso(row.created_at)
        row_details = None
        if row.details_json:
            try:
                row_details = json.loads(row.details_json)
            except Exception:
                row_details = row.details_json

        canonical_json = build_canonical_payload(
            seq=row.seq,
            created_at_iso=created_at_iso,
            user_id=row.actor_user_id,
            user_email=row.user_email,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=str(row.entity_id) if row.entity_id is not None else None,
            details=row_details,
            ip=row.ip
        )

        expected_entry_hash = compute_entry_hash(row.prev_hash, canonical_json, key=key)

        if not hmac.compare_digest(row.entry_hash, expected_entry_hash):
            logger.warning(
                f"Altération cryptographique détectée pour seq={row.seq}: "
                f"hash stocké={row.entry_hash}, hash calculé={expected_entry_hash}"
            )
            return False, verified_count, row.seq

        # Mise à jour pour le rang suivant
        expected_prev_hash = row.entry_hash
        expected_seq += 1
        verified_count += 1

    return True, verified_count, None
