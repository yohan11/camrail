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
from app.models.schemas import User, Document, DocumentPage
from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.services.document_processor import process_document
from app.services.indexing import index_document
from app.services.audit import log_audit_event

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
    security_groups: List[str] = Form(["default"]),
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

    # 6. Fetch Security Groups
    from app.models.schemas import SecurityGroup
    groups = db.query(SecurityGroup).filter(SecurityGroup.name.in_(security_groups)).all()
    if not groups:
        groups = db.query(SecurityGroup).filter(SecurityGroup.name == "default").all()

    # 7. Create initial document record with status "processing"
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
    doc.security_groups = groups
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 8. Extract document pages and index chunks
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
        db.commit()

        # Generate chunk embeddings and tsvectors
        index_document(doc.id, db)
        doc.status = "indexed"
    except Exception as e:
        # Failure during extraction or indexing sets status to failed
        doc.status = "failed"

    # 9. Log audit event
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="upload_document",
        entity_type="document",
        entity_id=str(doc.id),
        details={
            "title": doc.title,
            "filename": filename,
            "status": doc.status,
            "checksum": doc.checksum
        }
    )
    
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
    
    # Simple department-based access restriction for PoC
    if current_user.role == "read_only" and current_user.department:
        query = query.filter(Document.department == current_user.department)
        
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
    db.commit()
    
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="activate_document",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "new_status": "active"}
    )
    
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
    
    # Delete any previous partial pages and chunks
    db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).delete()
    db.commit()
    
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
        db.commit()

        # Re-index chunks
        index_document(doc.id, db)
        doc.status = "indexed"
    except Exception:
        doc.status = "failed"
    
    db.commit()
    
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="retry_document_processing",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "status": doc.status}
    )
    
    db.refresh(doc)
    
    return doc
