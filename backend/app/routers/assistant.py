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

    # 1. Retrieve chunks with user's authorized security groups
    user_security_groups = [group.name for group in current_user.security_groups]
    search_results = hybrid_search(
        db=db,
        query=payload.query,
        top_k=5,
        department=payload.department,
        category=payload.category,
        security_groups=user_security_groups
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

    return AssistantQueryResponse(
        request_id=request_id,
        query=payload.query,
        answer=gen_result.get("answer", ""),
        confidence=gen_result.get("confidence", "insufficient"),
        citations=citations,
        duration_ms=duration_ms
    )
