import os
import io
import re
import zipfile
import pypdf
import hashlib
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.deps import get_current_user, RoleChecker
from app.config import settings
from app.models.schemas import User, Document, DocumentPage, SecurityGroup
from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.services.document_processor import process_document
from app.services.indexing import index_document
from app.services.audit import log_audit_event
from app.security import can_access_document, ensure_document_access, filter_accessible_documents

router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentGroupsUpdate(BaseModel):
    group_names: List[str]



def sanitize_filename(filename: str) -> str:
    r"""
    Nettoie le nom de fichier original :
    - Retire les séparateurs de chemin (/ et \) pour neutraliser les attaques de traversée (ex: ../../x.pdf)
    - Retire les caractères de contrôle non imprimables et caractères interdits
    - Supprime les points et espaces de début/fin
    """
    if not filename:
        return "document_inconnu"
    clean = filename.replace("\\", "/").split("/")[-1]
    clean = re.sub(r'[\x00-\x1f\x7f-\x9f<>:"/\\|?*]', '_', clean).strip()
    clean = clean.strip(". ")
    return clean if clean else "document_inconnu"


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
    # 0. Nettoyage du nom de fichier original et du titre
    raw_filename = file.filename or ""
    clean_filename = sanitize_filename(raw_filename)
    clean_title = sanitize_filename(title) if title else clean_filename

    # 1. Validation de l'extension et détection de double extension dangereuse
    ext = os.path.splitext(clean_filename)[1].lower()
    if ext not in [".pdf", ".docx"]:
        log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="upload_rejected",
            entity_type="document",
            entity_id="unknown",
            details={"reason": "unsupported_extension", "filename": clean_filename}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format de fichier non supporté. Seuls les fichiers .pdf et .docx sont acceptés."
        )

    parts = clean_filename.split(".")
    if len(parts) > 2:
        dangerous_exts = {"exe", "bat", "cmd", "sh", "php", "js", "vbs", "ps1", "dll", "msi", "com", "scr", "pif", "bin"}
        if any(p.lower() in dangerous_exts for p in parts[:-1]):
            log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="upload_rejected",
                entity_type="document",
                entity_id="unknown",
                details={"reason": "dangerous_double_extension", "filename": clean_filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nom de fichier suspect (double extension dangereuse interdite)."
            )

    # 2. Lecture et validation de la taille brute
    contents = await file.read()
    if not contents:
        log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="upload_rejected",
            entity_type="document",
            entity_id="unknown",
            details={"reason": "empty_file", "filename": clean_filename}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier est vide."
        )
        
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="upload_rejected",
            entity_type="document",
            entity_id="unknown",
            details={"reason": "file_too_large", "size": len(contents), "max": max_bytes, "filename": clean_filename}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La taille du fichier dépasse la limite autorisée de {settings.MAX_UPLOAD_MB} Mo."
        )

    # 3. Durcissement approfondi selon le type MIME / format
    if ext == ".pdf":
        # Signature magique PDF
        if not contents.startswith(b"%PDF-"):
            log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="upload_rejected",
                entity_type="document",
                entity_id="unknown",
                details={"reason": "invalid_pdf_header", "filename": clean_filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fichier PDF invalide : l'en-tête du document doit débuter par %PDF-."
            )
            
        # Comptage de pages pré-extraction
        try:
            reader = pypdf.PdfReader(io.BytesIO(contents))
            page_count = len(reader.pages)
        except Exception as e:
            log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="upload_rejected",
                entity_type="document",
                entity_id="unknown",
                details={"reason": "corrupt_pdf", "error": str(e), "filename": clean_filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier PDF est corrompu ou illisible."
            )

        if page_count > settings.MAX_PDF_PAGES:
            log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="upload_rejected",
                entity_type="document",
                entity_id="unknown",
                details={"reason": "max_pages_exceeded", "page_count": page_count, "max_pages": settings.MAX_PDF_PAGES, "filename": clean_filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le document dépasse le nombre maximal de {settings.MAX_PDF_PAGES} pages autorisé ({page_count} pages détectées)."
            )

    elif ext == ".docx":
        docx_bytes = io.BytesIO(contents)
        if not zipfile.is_zipfile(docx_bytes):
            log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="upload_rejected",
                entity_type="document",
                entity_id="unknown",
                details={"reason": "not_a_zip", "filename": clean_filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fichier DOCX invalide : l'archive zip est corrompue ou illisible."
            )

        try:
            with zipfile.ZipFile(docx_bytes, "r") as zf:
                infolist = zf.infolist()

                if len(infolist) > 5000:
                    log_audit_event(
                        db=db,
                        actor_user_id=current_user.id,
                        action="upload_rejected",
                        entity_type="document",
                        entity_id="unknown",
                        details={"reason": "too_many_zip_entries", "entries": len(infolist), "filename": clean_filename}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Le fichier DOCX contient un nombre excessif d'entrées (supérieur à 5000)."
                    )

                names = {info.filename for info in infolist}
                if "word/document.xml" not in names:
                    log_audit_event(
                        db=db,
                        actor_user_id=current_user.id,
                        action="upload_rejected",
                        entity_type="document",
                        entity_id="unknown",
                        details={"reason": "missing_document_xml", "filename": clean_filename}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Structure DOCX non conforme : le composant principal word/document.xml est manquant."
                    )

                max_uncompressed_bytes = settings.MAX_UNCOMPRESSED_MB * 1024 * 1024
                total_uncompressed = 0
                total_compressed = 0

                for info in infolist:
                    total_uncompressed += info.file_size
                    total_compressed += info.compress_size

                    if info.compress_size > 0:
                        ratio = info.file_size / info.compress_size
                        if ratio > settings.MAX_ZIP_RATIO:
                            log_audit_event(
                                db=db,
                                actor_user_id=current_user.id,
                                action="upload_rejected",
                                entity_type="document",
                                entity_id="unknown",
                                details={"reason": "zip_bomb_ratio", "entry": info.filename, "ratio": ratio, "filename": clean_filename}
                            )
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Fichier DOCX rejeté : ratio de compression excessif (suspicion de bombe de décompression)."
                            )
                    elif info.file_size > 1024 * 1024:
                        log_audit_event(
                            db=db,
                            actor_user_id=current_user.id,
                            action="upload_rejected",
                            entity_type="document",
                            entity_id="unknown",
                            details={"reason": "uncompressed_entry_too_large", "entry": info.filename, "size": info.file_size, "filename": clean_filename}
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Fichier DOCX rejeté : entrée non compressée anormalement volumineuse."
                        )

                    if total_uncompressed > max_uncompressed_bytes:
                        log_audit_event(
                            db=db,
                            actor_user_id=current_user.id,
                            action="upload_rejected",
                            entity_type="document",
                            entity_id="unknown",
                            details={"reason": "uncompressed_size_exceeded", "total": total_uncompressed, "max": max_uncompressed_bytes, "filename": clean_filename}
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"La taille totale décompressée dépasse la limite autorisée de {settings.MAX_UNCOMPRESSED_MB} Mo."
                        )

                if total_compressed > 0 and (total_uncompressed / total_compressed) > settings.MAX_ZIP_RATIO:
                    log_audit_event(
                        db=db,
                        actor_user_id=current_user.id,
                        action="upload_rejected",
                        entity_type="document",
                        entity_id="unknown",
                        details={"reason": "global_zip_bomb_ratio", "ratio": total_uncompressed / total_compressed, "filename": clean_filename}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Fichier DOCX rejeté : ratio de compression global excessif (suspicion de bombe de décompression)."
                    )
        except HTTPException:
            raise
        except Exception as e:
            log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="upload_rejected",
                entity_type="document",
                entity_id="unknown",
                details={"reason": "bad_docx", "error": str(e), "filename": clean_filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier DOCX est corrompu ou illisible."
            )

    # 4. Calcul du checksum SHA-256 et vérification des doublons
    checksum = hashlib.sha256(contents).hexdigest()
    existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
    if existing_doc:
        log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="upload_rejected",
            entity_type="document",
            entity_id="unknown",
            details={"reason": "duplicate_document", "existing_id": existing_doc.id, "filename": clean_filename}
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ce document existe déjà dans RailMind : {existing_doc.title}"
        )

    # 5. Enregistrement sécurisé du fichier (nom basé sur le hash SHA-256)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    storage_dir = os.path.join(base_dir, "storage", "documents")
    os.makedirs(storage_dir, exist_ok=True)
    
    saved_filename = f"{checksum}{ext}"
    saved_path = os.path.join(storage_dir, saved_filename)
    with open(saved_path, "wb") as f:
        f.write(contents)

    # 6. Date d'effet
    parsed_date = None
    if effective_date:
        try:
            parsed_date = datetime.fromisoformat(effective_date.replace("Z", "+00:00"))
        except Exception:
            try:
                parsed_date = datetime.strptime(effective_date, "%Y-%m-%d")
            except Exception:
                pass

    # 7. Groupes de sécurité
    from app.models.schemas import SecurityGroup
    groups = db.query(SecurityGroup).filter(SecurityGroup.name.in_(security_groups)).all()
    if not groups:
        groups = db.query(SecurityGroup).filter(SecurityGroup.name == "default").all()

    # 8. Création de l'enregistrement Document en base (titre nettoyé)
    doc = Document(
        title=clean_title,
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
            "filename": clean_filename,
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
    
    # Règle unique d'accès : filtrer selon le rôle, département et groupes de sécurité
    query = filter_accessible_documents(query, current_user)
        
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()
    ensure_document_access(current_user, doc, db, action="read")

    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="document_view",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "category": doc.category, "department": doc.department},
        request=request
    )

    return doc


@router.post("/{id}/activate", response_model=DocumentResponse)
def activate_document(
    id: int,
    request: Request,
    current_user: User = Depends(RoleChecker(["admin", "document_admin"])),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()
    ensure_document_access(current_user, doc, db, action="activate")
    
    if doc.status not in ["indexed", "archived"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seuls les documents avec le statut 'indexed' ou 'archived' peuvent être activés."
        )
    
    old_status = doc.status
    doc.status = "active"
    db.commit()
    
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="activate_document",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "old_status": old_status, "new_status": "active"},
        request=request
    )
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="document_status_changed",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "old_status": old_status, "new_status": "active"},
        request=request
    )
    
    db.refresh(doc)
    return doc


@router.post("/{id}/archive", response_model=DocumentResponse)
def archive_document(
    id: int,
    request: Request,
    current_user: User = Depends(RoleChecker(["admin", "document_admin"])),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()
    ensure_document_access(current_user, doc, db, action="archive")
    
    if doc.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seuls les documents avec le statut 'active' peuvent être archivés."
        )
    
    old_status = doc.status
    doc.status = "archived"
    db.commit()
    
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="archive_document",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "old_status": old_status, "new_status": "archived"},
        request=request
    )
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="document_status_changed",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "old_status": old_status, "new_status": "archived"},
        request=request
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
    ensure_document_access(current_user, doc, db, action="retry")
    
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Serve the original document file."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    ensure_document_access(current_user, doc, db, action="download")
        
    if not doc.file_url or not os.path.exists(doc.file_url):
        raise HTTPException(status_code=404, detail="Fichier original non trouvé sur le serveur")
    
    filename = os.path.basename(doc.file_url)

    # Journalisation de l'audit de téléchargement
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="document_file_download",
        entity_type="document",
        entity_id=str(doc.id),
        details={"title": doc.title, "filename": filename},
        request=request
    )

    ext = os.path.splitext(filename)[1].lower()
    
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext in [".doc", ".docx"]:
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media_type = "application/octet-stream"
    
    # Pour la scalabilité (ne pas charger tout le fichier en RAM), on utilise FileResponse
    # On retire le filename pour éviter que le navigateur ou IDM force le téléchargement
    return FileResponse(
        path=doc.file_url,
        media_type=media_type,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.put("/{id}/security-groups", response_model=DocumentResponse)
def update_document_security_groups(
    id: int,
    groups_in: DocumentGroupsUpdate,
    request: Request,
    current_user: User = Depends(RoleChecker(["admin", "document_admin"])),
    db: Session = Depends(get_db)
):
    """
    Modification administrateur des groupes de sécurité associés à un document.
    Journalise 'document_groups_changed'.
    """
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    old_groups = [g.name for g in doc.security_groups]
    new_groups = db.query(SecurityGroup).filter(SecurityGroup.name.in_(groups_in.group_names)).all()
    doc.security_groups = new_groups
    db.commit()
    db.refresh(doc)

    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="document_groups_changed",
        entity_type="document",
        entity_id=str(doc.id),
        details={
            "title": doc.title,
            "old_groups": old_groups,
            "new_groups": [g.name for g in new_groups]
        },
        request=request
    )

    return doc

