import os
import hashlib
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, RoleChecker
from app.config import settings
from app.models.schemas import User, Document, DocumentPage, AuditEvent
from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.services.document_processor import process_document

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(...),
    department: str = Form(...),
    version: str = Form("1.0"),
    effective_date: Optional[str] = Form(None),
    current_user: User = Depends(RoleChecker(["admin", "document_admin"])),
    db: Session = Depends(get_db)
):
    # 1. Validate file extension
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format de fichier non supporté. Seuls les fichiers .pdf et .docx sont acceptés."
        )

    # 2. Read and validate file size
    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La taille du fichier dépasse la limite autorisée de {settings.MAX_UPLOAD_MB} Mo."
        )

    # 3. Calculate SHA-256 checksum and check duplicate
    checksum = hashlib.sha256(contents).hexdigest()
    existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
    if existing_doc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce document a déjà été uploadé"
        )

    # 4. Save file to storage
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    storage_dir = os.path.join(base_dir, "storage", "documents")
    os.makedirs(storage_dir, exist_ok=True)
    
    saved_filename = f"{checksum}{ext}"
    saved_path = os.path.join(storage_dir, saved_filename)
    with open(saved_path, "wb") as f:
        f.write(contents)

    # 5. Parse effective_date if provided
    parsed_date = None
    if effective_date:
        try:
            parsed_date = datetime.fromisoformat(effective_date.replace("Z", "+00:00"))
        except Exception:
            try:
                parsed_date = datetime.strptime(effective_date, "%Y-%m-%d")
            except Exception:
                pass

    # 6. Create initial document record with status "processing"
    doc = Document(
        title=title,
        version=version,
        category=category,
        department=department,
        effective_date=parsed_date,
        status="processing",
        file_url=saved_path,
        checksum=checksum,
        uploaded_by=current_user.id
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 7. Extract document pages and text
    try:
        extracted_pages = process_document(saved_path, ext)
        for page_info in extracted_pages:
            page_record = DocumentPage(
                document_id=doc.id,
                page_number=page_info["page_number"],
                extracted_text=page_info["text"],
                extraction_method=page_info["method"]
            )
            db.add(page_record)
        doc.status = "indexed"
    except Exception as e:
        # Failure during processing does not crash the request; document is marked failed
        doc.status = "failed"

    # 8. Log audit event
    audit = AuditEvent(
        actor_user_id=current_user.id,
        action="upload_document",
        entity_type="document",
        entity_id=str(doc.id),
        details_json=json.dumps({
            "title": doc.title,
            "filename": filename,
            "status": doc.status,
            "checksum": doc.checksum
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(doc)

    return doc


@router.get("", response_model=List[DocumentResponse])
@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Document)
    if status:
        query = query.filter(Document.status == status)
    if category:
        query = query.filter(Document.category == category)
    if department:
        query = query.filter(Document.department == department)
    
    return query.order_by(Document.created_at.desc()).all()


@router.get("/{id}", response_model=DocumentDetailResponse)
def get_document(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    return doc


@router.post("/{id}/activate", response_model=DocumentResponse)
def activate_document(
    id: int,
    current_user: User = Depends(RoleChecker(["admin", "document_admin"])),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    if doc.status != "indexed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seuls les documents avec le statut 'indexed' peuvent être activés."
        )
    
    doc.status = "active"
    
    audit = AuditEvent(
        actor_user_id=current_user.id,
        action="activate_document",
        entity_type="document",
        entity_id=str(doc.id),
        details_json=json.dumps({"title": doc.title, "new_status": "active"})
    )
    db.add(audit)
    db.commit()
    db.refresh(doc)
    
    return doc


@router.post("/{id}/retry", response_model=DocumentResponse)
def retry_document_processing(
    id: int,
    current_user: User = Depends(RoleChecker(["admin", "document_admin"])),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    if doc.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seuls les documents avec le statut 'failed' peuvent être retentés."
        )
    
    # Delete any previous partial pages
    db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).delete()
    
    ext = os.path.splitext(doc.file_url)[1] if doc.file_url else ""
    try:
        extracted_pages = process_document(doc.file_url, ext)
        for page_info in extracted_pages:
            page_record = DocumentPage(
                document_id=doc.id,
                page_number=page_info["page_number"],
                extracted_text=page_info["text"],
                extraction_method=page_info["method"]
            )
            db.add(page_record)
        doc.status = "indexed"
    except Exception:
        doc.status = "failed"
    
    audit = AuditEvent(
        actor_user_id=current_user.id,
        action="retry_document_processing",
        entity_type="document",
        entity_id=str(doc.id),
        details_json=json.dumps({"title": doc.title, "status": doc.status})
    )
    db.add(audit)
    db.commit()
    db.refresh(doc)
    
    return doc
