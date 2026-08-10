from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    query: str = Field(..., description="Query string for hybrid semantic and lexical search")
    department: Optional[str] = Field(None, description="Optional filter by department")
    category: Optional[str] = Field(None, description="Optional filter by category")
    security_group: Optional[str] = Field(None, description="Optional filter by security group")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of relevant chunks to return")


class SearchResultItem(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    document_version: str
    page_start: int
    page_end: int
    excerpt: str
    score: float
    vector_distance: Optional[float] = None
    is_full_document_citation: bool

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    request_id: str
    query: str
    results: List[SearchResultItem]

    model_config = ConfigDict(from_attributes=True)
