from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.schemas import User
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
    results = hybrid_search(
        db=db,
        query=payload.query,
        top_k=payload.top_k,
        department=payload.department,
        category=payload.category
    )
    return SearchResponse(query=payload.query, results=results)
