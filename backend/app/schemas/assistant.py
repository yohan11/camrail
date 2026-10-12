from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class AssistantQueryRequest(BaseModel):
    query: str = Field(..., description="The user question for the assistant")
    conversation_id: Optional[int] = Field(None, description="Optional conversation identifier")
    department: Optional[str] = Field(None, description="Optional filter by department")
    category: Optional[str] = Field(None, description="Optional filter by category")
    language: str = Field("fr", description="The language of the query and expected response ('fr' or 'en')")

class EvidenceUnit(BaseModel):
    text: str
    page_number: int
    score: float

class CitationItem(BaseModel):
    document_id: int
    document_title: str
    document_version: str = "1.0"
    page_start: int
    page_end: int
    section: Optional[str] = None
    excerpt: str
    score: Optional[float] = None
    chunk_id: Optional[int] = None
    evidence: Optional[List[EvidenceUnit]] = []
    pagination_type: Optional[str] = "native"

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

class TranslateMessageItem(BaseModel):
    role: str
    content: str

class TranslationRequest(BaseModel):
    messages: List[TranslateMessageItem]
    target_language: str

class TranslationResponse(BaseModel):
    translated_messages: List[str]
