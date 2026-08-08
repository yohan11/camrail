from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class DocumentCreate(BaseModel):
    title: str
    category: str
    department: str
    version: str = "1.0"
    effective_date: Optional[datetime] = None

class DocumentResponse(BaseModel):
    id: int
    title: str
    family_key: Optional[str] = None
    version: str
    category: str
    department: str
    effective_date: Optional[datetime] = None
    status: str
    checksum: str
    uploaded_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentPageResponse(BaseModel):
    id: int
    page_number: int
    extracted_text: str
    extraction_method: str

    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(DocumentResponse):
    pages: List[DocumentPageResponse] = []

    model_config = ConfigDict(from_attributes=True)
