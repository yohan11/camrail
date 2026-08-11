from pydantic import BaseModel
from typing import Dict

class DashboardSummary(BaseModel):
    documents_total: int
    documents_by_status: Dict[str, int]
    documents_active: int
    questions_total: int
    questions_today: int
    confidence_breakdown: Dict[str, int]
    recent_audit_count: int
