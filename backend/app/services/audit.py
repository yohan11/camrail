import json
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.schemas import AuditEvent

logger = logging.getLogger(__name__)

def log_audit_event(
    db: Session,
    actor_user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Centralized function to log audit events in the database.
    
    Args:
        db: SQLAlchemy Session
        actor_user_id: The ID of the user performing the action, or None if unknown
        action: The action performed (e.g., "login_success", "assistant_query")
        entity_type: The type of entity affected (e.g., "user", "rda_query", "document")
        entity_id: The ID of the affected entity
        details: Optional dictionary of additional details to store as JSON
    """
    try:
        # Security precaution: never log passwords
        if details and "password" in details:
            safe_details = details.copy()
            safe_details.pop("password")
            details = safe_details
            
        details_json = json.dumps(details) if details else None
        
        audit = AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details_json=details_json
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to log audit event: {e}")
