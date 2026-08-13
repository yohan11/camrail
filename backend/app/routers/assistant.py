import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.schemas import User, RdaQuery
from app.schemas.assistant import AssistantQueryRequest, AssistantQueryResponse, CitationItem
from app.services.retrieval import hybrid_search
from app.services.generation import generate_answer
from app.services.audit import log_audit_event

router = APIRouter(prefix="/assistant", tags=["Assistant"])

@router.post("/query", response_model=AssistantQueryResponse, status_code=status.HTTP_200_OK)
def assistant_query(
    payload: AssistantQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    RAG Endpoint: Retrieves relevant context using hybrid_search,
    then generates a natural language answer using a local LLM via Ollama.
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    # 1. Retrieve chunks with user's authorized security groups (bypass for admins)
    if current_user.role in ["admin", "document_admin"]:
        user_security_groups = None
    else:
        user_security_groups = [group.name for group in current_user.security_groups]
    
    # Simple department-based access restriction for PoC
    search_department = payload.department
    if current_user.role == "read_only" and current_user.department:
        search_department = current_user.department
        
    # Heuristique simple (PoC, pas un vrai NER) pour extraire un nom de document
    import re
    document_title_hint = None
    match = re.search(r"(?i)document\s+([a-zA-Z0-9_\-\.]+\.(?:pdf|docx))", payload.query)
    if not match:
        match = re.search(r"(?i)selon le document\s+([a-zA-Z0-9_\-\.]+)", payload.query)
    
    if match:
        document_title_hint = match.group(1).strip()

    search_results = hybrid_search(
        db=db,
        query=payload.query,
        top_k=5,
        department=search_department,
        category=payload.category,
        security_groups=user_security_groups,
        document_title_hint=document_title_hint
    )

    # 2. Generate answer
    gen_result = generate_answer(query=payload.query, search_results=search_results)

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Build citations list
    citations = [CitationItem(**c) for c in gen_result.get("citations", [])]

    # 3. Save telemetry in RdaQuery
    from app.config import settings
    rda_query = RdaQuery(
        request_id=request_id,
        user_id=current_user.id,
        query_text=payload.query,
        results_count=len(search_results),
        duration_ms=duration_ms,
        confidence=gen_result.get("confidence"),
        model_name=settings.OLLAMA_MODEL,
        citation_count=len(citations),
        abstained=(gen_result.get("confidence") == "insufficient")
    )
    db.add(rda_query)
    db.commit()

    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="assistant_query",
        entity_type="rda_query",
        entity_id=request_id,
        details={
            "confidence": gen_result.get("confidence"),
            "results_count": len(search_results)
        }
    )

    return AssistantQueryResponse(
        request_id=request_id,
        query=payload.query,
        answer=gen_result.get("answer", ""),
        confidence=gen_result.get("confidence", "insufficient"),
        citations=citations,
        duration_ms=duration_ms
    )
