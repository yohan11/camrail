from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class AssistantQueryRequest(BaseModel):
    query: str = Field(..., description="The user question for the assistant")
    conversation_id: Optional[int] = Field(None, description="Optional conversation identifier")
    department: Optional[str] = Field(None, description="Optional filter by department")
    category: Optional[str] = Field(None, description="Optional filter by category")

class CitationItem(BaseModel):
    document_id: int
    document_title: str
    document_version: str
    page_start: int
    page_end: int
    section: Optional[str] = None
    excerpt: str
    score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class AssistantQueryResponse(BaseModel):
    request_id: str
    conversation_id: Optional[int] = None
    query: str
    answer: str
    confidence: str
    citations: List[CitationItem]
    duration_ms: int
    provider: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
