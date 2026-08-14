import os
import hashlib
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
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
    initial_status: str = Form("indexed"),
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
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier est vide."
        )
        
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
            detail=f"Ce document existe déjà dans RailMind : {existing_doc.title}"
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
        doc.status = initial_status if initial_status in ["indexed", "active"] else "indexed"
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
        
    if current_user.role == "read_only" and current_user.department:
        if doc.department != current_user.department:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé. Le document n'appartient pas à votre département."
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
    
    if doc.status not in ["indexed", "archived"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seuls les documents avec le statut 'indexed' ou 'archived' peuvent être activés."
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


@router.post("/{id}/archive", response_model=DocumentResponse)
def archive_document(
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
    
    if doc.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seuls les documents avec le statut 'active' peuvent être archivés."
        )
    
    doc.status = "archived"
    db.commit()
    
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="archive_document",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "new_status": "archived"}
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

@router.get("/{document_id}/file")
def get_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Serve the original document file."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
        
    if not doc.file_url or not os.path.exists(doc.file_url):
        raise HTTPException(status_code=404, detail="Fichier original non trouvé sur le serveur")
        
    # Check access rights
    if current_user.role == "read_only":
        user_groups = {g.id for g in current_user.security_groups}
        doc_groups = {g.id for g in doc.security_groups}
        if not user_groups.intersection(doc_groups):
             raise HTTPException(status_code=403, detail="Accès refusé")
    
    filename = os.path.basename(doc.file_url)
    ext = os.path.splitext(filename)[1].lower()
    media_type = "application/pdf" if ext == ".pdf" else "application/octet-stream"
    
    return FileResponse(
        path=doc.file_url, 
        filename=f"{doc.title}{ext}",
        media_type=media_type,
        content_disposition_type="inline"
    )
