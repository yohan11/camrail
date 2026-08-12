import json
import re
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.schemas import Document, DocumentChunk
from app.services.indexing import embed_text


def _sanitize_query_terms(query: str) -> list[str]:
    """
    Découpe la requête en mots alphanumériques (accents inclus), en filtrant tout
    caractère spécial qui ferait planter to_tsquery (&, |, !, (, ), :, etc.).
    Retourne une liste de mots nettoyés, vide si rien d'exploitable.
    """
    words = re.findall(r"[a-zA-ZÀ-ÖØ-öø-ÿ0-9]+", query)
    return [w for w in words if len(w) > 1]  # ignore les mots d'une seule lettre


def hybrid_search(
    db: Session,
    query: str,
    top_k: int = 5,
    department: Optional[str] = None,
    category: Optional[str] = None,
    security_groups: Optional[List[str]] = None,
    document_title_hint: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Performs hybrid search (vector similarity + PostgreSQL full-text search)
    fused with Reciprocal Rank Fusion (RRF, k=60).
    Only considers active documents.
    If document_title_hint is provided, restricts search to documents containing the hint.
    """
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    query_emb = embed_text(clean_query)

    # 1. Base query filters: active documents only + optional metadata filters
    base_filter = [Document.status == "active"]
    if department:
        base_filter.append(Document.department == department)
    if category:
        base_filter.append(Document.category == category)
    if security_groups is not None:
        if not security_groups:
            # Safely fail if user has no authorized security groups
            return []
        
        # Clean architecture: filter chunks by the document's assigned security groups
        from app.models.schemas import SecurityGroup
        base_filter.append(Document.security_groups.any(SecurityGroup.name.in_(security_groups)))

    # Apply document_title_hint filter if provided
    if document_title_hint:
        import logging
        logger = logging.getLogger(__name__)
        # Check if any active document actually matches this hint
        matching_docs_count = db.query(Document).filter(
            *base_filter,
            Document.title.ilike(f"%{document_title_hint}%")
        ).count()
        if matching_docs_count > 0:
            base_filter.append(Document.title.ilike(f"%{document_title_hint}%"))
            logger.info(f"Applying document_title_hint filter for: {document_title_hint}")
        else:
            logger.warning(f"document_title_hint '{document_title_hint}' did not match any active documents. Falling back to global search.")

    # 2. Vector search (Top 8 by cosine distance)
    distance_expr = DocumentChunk.embedding.cosine_distance(query_emb).label("distance")
    vector_results = (
        db.query(DocumentChunk, Document, distance_expr)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(*base_filter)
        .filter(DocumentChunk.embedding.isnot(None))
        .order_by(distance_expr)
        .limit(8)
        .all()
    )

    # 3. Lexical full-text search (Top 8 by ts_rank)
    terms = _sanitize_query_terms(clean_query)
    if not terms:
        lexical_results = []
    else:
        or_query_string = " | ".join(terms)
        ts_query = func.to_tsquery("french", or_query_string)
        lexical_results = (
            db.query(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(*base_filter)
            .filter(DocumentChunk.search_vector.op("@@")(ts_query))
            .order_by(func.ts_rank(DocumentChunk.search_vector, ts_query).desc())
            .limit(8)
            .all()
        )

    # 4. Reciprocal Rank Fusion (RRF, k=60)
    # Score formula: 1 / (60 + rank_vector) + 1 / (60 + rank_lexical)
    chunk_scores: Dict[int, float] = {}
    chunk_map: Dict[int, tuple[DocumentChunk, Document]] = {}
    chunk_distances: Dict[int, float] = {}

    for rank, (chunk, doc, dist) in enumerate(vector_results, start=1):
        chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + (1.0 / (60.0 + rank))
        chunk_map[chunk.id] = (chunk, doc)
        # Store the actual cosine distance (will be between 0 and 2)
        if dist is not None:
            chunk_distances[chunk.id] = float(dist)

    for rank, (chunk, doc) in enumerate(lexical_results, start=1):
        chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + (1.0 / (60.0 + rank))
        chunk_map[chunk.id] = (chunk, doc)

    if not chunk_scores:
        return []

    # 5. Sort by fusion score descending and pick top_k
    sorted_chunk_ids = sorted(chunk_scores.keys(), key=lambda cid: chunk_scores[cid], reverse=True)[:top_k]

    # 6. Format response items
    formatted_results = []
    for cid in sorted_chunk_ids:
        chunk, doc = chunk_map[cid]
        score = chunk_scores[cid]
        vector_dist = chunk_distances.get(cid)

        meta = {}
        if chunk.metadata_json:
            try:
                meta = json.loads(chunk.metadata_json)
            except Exception:
                meta = {}

        excerpt = chunk.content or ""
        if len(excerpt) > 300:
            excerpt = excerpt[:300] + "..."

        is_full_doc = meta.get("is_full_document_citation", False)

        formatted_results.append({
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "document_title": doc.title,
            "document_version": doc.version,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "excerpt": excerpt,
            "score": round(score, 6),
            "vector_distance": vector_dist,
            "is_full_document_citation": is_full_doc,
        })

    return formatted_results
