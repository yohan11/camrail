from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class AssistantQueryRequest(BaseModel):
    query: str = Field(..., description="The user question for the assistant")
    department: Optional[str] = Field(None, description="Optional filter by department")
    category: Optional[str] = Field(None, description="Optional filter by category")

class CitationItem(BaseModel):
    document_title: str
    page_start: int
    page_end: int
    excerpt: str

    model_config = ConfigDict(from_attributes=True)

class AssistantQueryResponse(BaseModel):
    request_id: str
    query: str
    answer: str
    confidence: str
    citations: List[CitationItem]
    duration_ms: int

    model_config = ConfigDict(from_attributes=True)
