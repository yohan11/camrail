from pydantic import BaseModel
from typing import Dict, Optional

class DashboardSummary(BaseModel):
    documents_total: int
    documents_by_status: Dict[str, int]
    documents_active: int
    questions_total: int
    questions_today: int
    confidence_breakdown: Dict[str, int]
    recent_audit_count: int

class DashboardQueryItem(BaseModel):
    id: int
    query_text: str
    confidence: Optional[str] = None
    created_at: str
    user_email: str
    duration_ms: Optional[int] = None

class DashboardAuditItem(BaseModel):
    id: int
    action: str
    entity_type: Optional[str] = None
    created_at: str
    user_email: str
