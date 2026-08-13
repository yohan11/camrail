from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import pytz

from app.database import get_db
from app.deps import get_current_user
from app.models.schemas import User, Document, RdaQuery, AuditEvent
from app.schemas.dashboard import DashboardSummary, DashboardQueryItem, DashboardAuditItem
from typing import List

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Documents Metrics (Isolated by department if read_only)
    doc_query = db.query(Document)
    if current_user.role == "read_only" and current_user.department:
        doc_query = doc_query.filter(Document.department == current_user.department)
        
    documents_total = doc_query.count()
    
    # documents_by_status
    status_counts = db.query(Document.status, func.count(Document.id))\
        .group_by(Document.status)
        
    if current_user.role == "read_only" and current_user.department:
        status_counts = status_counts.filter(Document.department == current_user.department)
        
    documents_by_status = {status: count for status, count in status_counts.all()}
    
    documents_active = documents_by_status.get("active", 0)
    
    # 2. Questions Metrics (Global - as per instructions for PoC)
    questions_total = db.query(RdaQuery).count()
    
    # Get start of today
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    questions_today = db.query(RdaQuery).filter(RdaQuery.created_at >= today).count()
    
    # Confidence breakdown
    conf_counts = db.query(RdaQuery.confidence, func.count(RdaQuery.id))\
        .group_by(RdaQuery.confidence).all()
    confidence_breakdown = {conf if conf else "insufficient": count for conf, count in conf_counts}
    
    # 3. Recent Audit Events (Global)
    yesterday = datetime.now() - timedelta(days=1)
    recent_audit_count = db.query(AuditEvent).filter(AuditEvent.created_at >= yesterday).count()
    
    return DashboardSummary(
        documents_total=documents_total,
        documents_by_status=documents_by_status,
        documents_active=documents_active,
        questions_total=questions_total,
        questions_today=questions_today,
        confidence_breakdown=confidence_breakdown,
        recent_audit_count=recent_audit_count
    )

@router.get("/details/queries", response_model=List[DashboardQueryItem])
def get_dashboard_queries(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent queries for dashboard detail view."""
    queries = db.query(RdaQuery, User).join(User, RdaQuery.user_id == User.id)\
        .order_by(RdaQuery.created_at.desc()).limit(limit).all()
        
    return [
        DashboardQueryItem(
            id=q.RdaQuery.id,
            query_text=q.RdaQuery.query_text,
            confidence=q.RdaQuery.confidence,
            created_at=q.RdaQuery.created_at.isoformat(),
            user_email=q.User.email,
            duration_ms=q.RdaQuery.duration_ms
        ) for q in queries
    ]

@router.get("/details/audit", response_model=List[DashboardAuditItem])
def get_dashboard_audit(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent audit events for dashboard detail view."""
    events = db.query(AuditEvent, User).outerjoin(User, AuditEvent.actor_user_id == User.id)\
        .order_by(AuditEvent.created_at.desc()).limit(limit).all()
        
    return [
        DashboardAuditItem(
            id=e.AuditEvent.id,
            action=e.AuditEvent.action,
            entity_type=e.AuditEvent.entity_type,
            created_at=e.AuditEvent.created_at.isoformat(),
            user_email=e.User.email if e.User else "Système"
        ) for e in events
    ]
