import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.schemas import User, RdaQuery, Rule, DocumentChunk, Document, Conversation, ConversationMessage
from app.schemas.assistant import AssistantQueryRequest, AssistantQueryResponse, CitationItem
from app.services.retrieval import hybrid_search
from app.services.generation import generate_answer
from app.services.audit import log_audit_event
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/assistant", tags=["Assistant"])

class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[int] = None
    
class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: str
    
class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: str

@router.get("/conversations", response_model=List[ConversationResponse])
def get_conversations(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve all conversations for the current user."""
    convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.updated_at.desc()).all()
    return [{"id": c.id, "title": c.title or "Nouvelle conversation", "created_at": c.created_at.isoformat()} for c in convs]

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(conversation_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve all messages for a specific conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conversation_id).order_by(ConversationMessage.created_at.asc()).all()
    return [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages]

@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"status": "deleted"}

@router.post("/query", response_model=AssistantQueryResponse, status_code=status.HTTP_200_OK)
def assistant_query(
    payload: AssistantQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    RAG Endpoint: Retrieves relevant context using hybrid_search,
    then generates a natural language answer using a local LLM via Ollama.
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    # 1. Retrieve chunks with user's authorized security groups (bypass for admins)
    if current_user.role in ["admin", "document_admin"]:
        user_security_groups = None
    else:
        user_security_groups = [group.name for group in current_user.security_groups]
    
    # Simple department-based access restriction for PoC
    search_department = payload.department
    if current_user.role == "read_only" and current_user.department:
        search_department = current_user.department
        
    # Heuristique simple (PoC, pas un vrai NER) pour extraire un nom de document
    import re
    document_title_hint = None
    match = re.search(r"(?i)document\s+([a-zA-Z0-9_\-\.]+\.(?:pdf|docx))", payload.query)
    if not match:
        match = re.search(r"(?i)selon le document\s+([a-zA-Z0-9_\-\.]+)", payload.query)
    
    if match:
        document_title_hint = match.group(1).strip()

    search_results = hybrid_search(
        db=db,
        query=payload.query,
        top_k=5,
        department=search_department,
        category=payload.category,
        security_groups=user_security_groups,
        document_title_hint=document_title_hint
    )

    # 2. Generate answer
    gen_result = generate_answer(query=payload.query, search_results=search_results)

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Build citations list
    citations = [CitationItem(**c) for c in gen_result.get("citations", [])]

    # 3. Save telemetry in RdaQuery
    from app.config import settings
    rda_query = RdaQuery(
        request_id=request_id,
        user_id=current_user.id,
        query_text=payload.query,
        results_count=len(search_results),
        duration_ms=duration_ms,
        confidence=gen_result.get("confidence"),
        model_name=settings.OLLAMA_MODEL,
        citation_count=len(citations),
        abstained=(gen_result.get("confidence") == "insufficient")
    )
    db.add(rda_query)
    
    # 5. Handle conversation saving
    conv_id = payload.conversation_id
    if not conv_id:
        title = payload.query[:50] + "..." if len(payload.query) > 50 else payload.query
        new_conv = Conversation(user_id=current_user.id, title=title)
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)
        conv_id = new_conv.id
    else:
        # Verify conversation belongs to user
        conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
    # Add user message
    user_msg = ConversationMessage(
        conversation_id=conv_id,
        role="user",
        content=payload.query
    )
    db.add(user_msg)
    
    # Add assistant response
    asst_msg = ConversationMessage(
        conversation_id=conv_id,
        role="assistant",
        content=gen_result.get("answer", ""),
    )
    db.add(asst_msg)
    
    # Update conversation timestamp
    db.query(Conversation).filter(Conversation.id == conv_id).update({"updated_at": func.now()})
    db.commit()

    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="assistant_query",
        entity_type="rda_query",
        entity_id=request_id,
        details={
            "confidence": gen_result.get("confidence"),
            "results_count": len(search_results)
        }
    )

    return AssistantQueryResponse(
        request_id=request_id,
        conversation_id=conv_id,
        answer=gen_result.get("answer", ""),
        confidence=gen_result.get("confidence", "insufficient"),
        citations=citations,
        duration_ms=duration_ms
    )
    