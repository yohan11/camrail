import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.schemas import User, RdaQuery
from app.schemas.search import SearchRequest, SearchResponse
from app.services.retrieval import hybrid_search

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("", response_model=SearchResponse, status_code=status.HTTP_200_OK)
def search_documents(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Hybrid semantic (vector pgvector) and lexical (tsvector) search
    across all active documents in the knowledge base.
    Accessible to all authenticated users.
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    results = hybrid_search(
        db=db,
        query=payload.query,
        top_k=payload.top_k,
        department=payload.department,
        category=payload.category,
        security_groups=[g.name for g in current_user.security_groups]
    )

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Log query to RDA Queries table
    rda_query = RdaQuery(
        request_id=request_id,
        user_id=current_user.id,
        query_text=payload.query,
        results_count=len(results),
        duration_ms=duration_ms
    )
    db.add(rda_query)
    db.commit()

    return SearchResponse(request_id=request_id, query=payload.query, results=results)
