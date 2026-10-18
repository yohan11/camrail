import time
import uuid
import json
import re
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from app.database import get_db, SessionLocal
from app.deps import get_current_user
from app.models.schemas import User, RdaQuery, DocumentChunk, Document, Conversation, ConversationMessage
from app.schemas.assistant import AssistantQueryRequest, AssistantQueryResponse, CitationItem, TranslationRequest, TranslationResponse
from app.services.retrieval import hybrid_search
from app.services.generation import (
    generate_answer, 
    translate_messages,
    prepare_rag_prompt_and_citations,
    finalize_citations_and_evidence,
    _generate_with_ollama_stream
)
from app.services.concurrency import concurrency_limiter, user_rate_limiter
from app.services.audit import log_audit_event
from app.security import get_effective_search_scope, ensure_conversation_access
from app.config import settings

logger = logging.getLogger(__name__)

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
    citations: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[str] = None


@router.get("/conversations", response_model=List[ConversationResponse])
def get_conversations(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve all conversations for the current user."""
    convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.updated_at.desc()).all()
    return [{"id": c.id, "title": c.title or "Nouvelle conversation", "created_at": c.created_at.isoformat()} for c in convs]


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(conversation_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve all messages for a specific conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    ensure_conversation_access(current_user, conv, db, action="read_messages")
    
    messages = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conversation_id).order_by(ConversationMessage.created_at.asc()).all()
    
    result = []
    for m in messages:
        cits = None
        if m.citations:
            try:
                cits = json.loads(m.citations)
            except:
                pass
        result.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
            "citations": cits,
            "confidence": m.confidence
        })
    return result


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    ensure_conversation_access(current_user, conv, db, action="delete_conversation")
    db.delete(conv)
    db.commit()
    return {"status": "deleted"}


def _extract_document_hint(query: str) -> Optional[str]:
    match = re.search(r"(?i)document\s+([a-zA-Z0-9_\-\.]+\.(?:pdf|docx))", query)
    if not match:
        match = re.search(r"(?i)selon le document\s+([a-zA-Z0-9_\-\.]+)", query)
    return match.group(1).strip() if match else None


@router.post("/query", response_model=AssistantQueryResponse, status_code=status.HTTP_200_OK)
def assistant_query(
    payload: AssistantQueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    RAG Endpoint standard (Synchrone) restructuré en 3 temps :
    1. Lecture/écriture DB initiale (périmètre d'accès, recherche hybride, historique) puis db.commit()/fermeture.
    2. Appel LLM 100% hors connexion DB avec régulation de concurrence (concurrency_limiter.slot()).
    3. Réouverture d'une session DB courte pour enregistrer la télémétrie, la réponse et les citations.
    """
    # 0. Limitation de débit par utilisateur
    user_rate_limiter.check(current_user.id)
    
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    # --- TEMPS 1 : Session DB courte pour recherche et initialisation ---
    with SessionLocal() as db:
        scope_department, user_security_groups = get_effective_search_scope(current_user)
        search_department = scope_department or payload.department
        document_title_hint = _extract_document_hint(payload.query)

        search_results = hybrid_search(
            db=db,
            query=payload.query,
            top_k=10,
            department=search_department,
            category=payload.category,
            security_groups=user_security_groups,
            document_title_hint=document_title_hint
        )

        conv_id = payload.conversation_id
        if not conv_id:
            title = payload.query[:50] + "..." if len(payload.query) > 50 else payload.query
            conv = Conversation(user_id=current_user.id, title=title)
            db.add(conv)
            db.commit()
            db.refresh(conv)
            conv_id = conv.id
        else:
            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            ensure_conversation_access(current_user, conv, db, action="add_message")

        user_msg = ConversationMessage(
            conversation_id=conv_id,
            role="user",
            content=payload.query
        )
        db.add(user_msg)
        if not conv.title:
            conv.title = payload.query[:50] + "..." if len(payload.query) > 50 else payload.query
        db.commit()

    # --- TEMPS 2 : Appel LLM SANS AUCUNE CONNEXION DB OUVERTE ---
    with concurrency_limiter.slot():
        gen_result = generate_answer(
            query=payload.query, 
            search_results=search_results,
            language=payload.language
        )
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    from app.services.output_filter import sanitize_answer
    raw_answer = gen_result.get("answer", "")
    clean_answer, removed_elements = sanitize_answer(raw_answer)

    citations = [CitationItem(**c) for c in gen_result.get("citations", [])]
    provider = gen_result.get("provider")

    # --- TEMPS 3 : Réouverture d'une session courte pour enregistrer la réponse ---
    with SessionLocal() as db_write:
        rda_query = RdaQuery(
            request_id=request_id,
            user_id=current_user.id,
            query_text=payload.query,
            results_count=len(search_results),
            duration_ms=duration_ms,
            confidence=gen_result.get("confidence"),
            model_name=provider if provider else settings.OLLAMA_MODEL,
            citation_count=len(citations),
            abstained=(gen_result.get("confidence") == "insufficient")
        )
        db_write.add(rda_query)

        asst_msg = ConversationMessage(
            conversation_id=conv_id,
            role="assistant",
            content=clean_answer,
            confidence=gen_result.get("confidence"),
            citations=json.dumps([c.model_dump() for c in citations]) if citations else None
        )
        db_write.add(asst_msg)
        db_write.query(Conversation).filter(Conversation.id == conv_id).update({"updated_at": func.now()})
        db_write.commit()

        if removed_elements > 0:
            log_audit_event(
                db=db_write,
                actor_user_id=current_user.id,
                action="response_sanitized",
                entity_type="rda_query",
                entity_id=request_id,
                details={
                    "removed_elements": removed_elements,
                    "query": payload.query
                }
            )

        log_audit_event(
            db=db_write,
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
        query=payload.query,
        answer=clean_answer,
        confidence=gen_result.get("confidence", "insufficient"),
        citations=citations,
        duration_ms=duration_ms,
        provider=gen_result.get("provider")
    )


@router.post("/query/stream")
def assistant_query_stream(
    payload: AssistantQueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    RAG Endpoint Streaming (Server-Sent Events) :
    Émet 3 types d'évènements SSE :
    - 'sources' : citations et phrases de preuves dès la fin de la recherche documentaire.
    - 'token'   : tokens émis au fil de la génération Ollama locale.
    - 'done'    : métadonnées finales (id message, réponse complète, citations définitives).
    Aucune connexion DB n'est maintenue pendant la génération LLM.
    """
    user_rate_limiter.check(current_user.id)
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    # --- TEMPS 1 : Recherche et persistance du message utilisateur en base ---
    with SessionLocal() as db:
        scope_department, user_security_groups = get_effective_search_scope(current_user)
        search_department = scope_department or payload.department
        document_title_hint = _extract_document_hint(payload.query)

        search_results = hybrid_search(
            db=db,
            query=payload.query,
            top_k=10,
            department=search_department,
            category=payload.category,
            security_groups=user_security_groups,
            document_title_hint=document_title_hint
        )

        conv_id = payload.conversation_id
        if not conv_id:
            title = payload.query[:50] + "..." if len(payload.query) > 50 else payload.query
            conv = Conversation(user_id=current_user.id, title=title)
            db.add(conv)
            db.commit()
            db.refresh(conv)
            conv_id = conv.id
        else:
            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            ensure_conversation_access(current_user, conv, db, action="stream_message")

        user_msg = ConversationMessage(
            conversation_id=conv_id,
            role="user",
            content=payload.query
        )
        db.add(user_msg)
        if not conv.title:
            conv.title = payload.query[:50] + "..." if len(payload.query) > 50 else payload.query
        db.commit()

        # Préparation du prompt et des citations initiales
        rag_prep = prepare_rag_prompt_and_citations(payload.query, search_results, payload.language)

    # Convert initial candidate citations to clean JSON serializable
    initial_sources_payload = []
    for cit in rag_prep.get("citations", []):
        cit_copy = {k: v for k, v in cit.items() if k not in ["content", "segments", "llm_index"]}
        initial_sources_payload.append(cit_copy)

    def event_stream():
        full_answer = ""
        # 1. Émettre les métadonnées de démarrage
        yield f"event: meta\ndata: {json.dumps({'conversation_id': conv_id, 'confidence': rag_prep['confidence']}, ensure_ascii=False)}\n\n"

        # 2. Cas d'abstention immédiate
        if rag_prep.get("is_abstain", False):
            abstain_text = rag_prep.get("answer", "")
            yield f"event: token\ndata: {json.dumps({'token': abstain_text}, ensure_ascii=False)}\n\n"
            full_answer = abstain_text
            final_citations = []
        else:
            # 3. Génération en streaming avec contrôle de concurrence (SANS connexion DB)
            try:
                with concurrency_limiter.slot():
                    for token in _generate_with_ollama_stream(rag_prep["system_prompt"], rag_prep["user_message"]):
                        full_answer += token
                        yield f"event: token\ndata: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"Erreur durant le streaming Ollama : {e}")
                err_detail = "Le serveur est très sollicité, réessayez dans un instant" if "503" in str(e) else "Erreur de génération locale"
                yield f"event: error\ndata: {json.dumps({'detail': err_detail}, ensure_ascii=False)}\n\n"
                return

            final_citations = finalize_citations_and_evidence(full_answer, rag_prep["all_citations"], payload.query)

        from app.services.output_filter import sanitize_answer
        clean_answer, removed_elements = sanitize_answer(full_answer)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # 4. TEMPS 3 : Réouverture de session courte pour sauvegarder la réponse et la télémétrie
        message_id = None
        try:
            with SessionLocal() as db_write:
                asst_msg = ConversationMessage(
                    conversation_id=conv_id,
                    role="assistant",
                    content=clean_answer,
                    confidence=rag_prep["confidence"] if final_citations else "insufficient",
                    citations=json.dumps(final_citations, ensure_ascii=False) if final_citations else None
                )
                db_write.add(asst_msg)
                db_write.commit()
                db_write.refresh(asst_msg)
                message_id = asst_msg.id

                rda_query = RdaQuery(
                    request_id=request_id,
                    user_id=current_user.id,
                    query_text=payload.query,
                    results_count=len(search_results),
                    duration_ms=duration_ms,
                    confidence=rag_prep["confidence"] if final_citations else "insufficient",
                    model_name="ollama",
                    citation_count=len(final_citations),
                    abstained=(not bool(final_citations))
                )
                db_write.add(rda_query)

                if removed_elements > 0:
                    log_audit_event(
                        db=db_write,
                        actor_user_id=current_user.id,
                        action="response_sanitized",
                        entity_type="rda_query",
                        entity_id=request_id,
                        details={
                            "removed_elements": removed_elements,
                            "query": payload.query
                        }
                    )

                db_write.query(Conversation).filter(Conversation.id == conv_id).update({"updated_at": func.now()})
                db_write.commit()
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de la réponse streamée : {e}")

        # 5. Émettre l'évènement final "done"
        done_payload = {
            "message_id": message_id,
            "conversation_id": conv_id,
            "answer": clean_answer,
            "citations": final_citations,
            "confidence": rag_prep["confidence"] if final_citations else "insufficient",
            "duration_ms": duration_ms
        }
        yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/translate", response_model=TranslationResponse)
def translate_conversation(payload: TranslationRequest, current_user = Depends(get_current_user)):
    """Translates a list of messages to the target language."""
    messages = [{"role": msg.role, "content": msg.content} for msg in payload.messages]
    translated = translate_messages(messages, payload.target_language)
    return TranslationResponse(translated_messages=translated)
