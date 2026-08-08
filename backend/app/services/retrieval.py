import json
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.schemas import Document, DocumentChunk
from app.services.indexing import embed_text


def hybrid_search(
    db: Session,
    query: str,
    top_k: int = 5,
    department: Optional[str] = None,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Performs hybrid search (vector similarity + PostgreSQL full-text search)
    fused with Reciprocal Rank Fusion (RRF, k=60).
    Only considers active documents.
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

    # 2. Vector search (Top 8 by cosine distance)
    vector_results = (
        db.query(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(*base_filter)
        .filter(DocumentChunk.embedding.isnot(None))
        .order_by(DocumentChunk.embedding.cosine_distance(query_emb))
        .limit(8)
        .all()
    )

    # 3. Lexical full-text search (Top 8 by ts_rank)
    ts_query = func.plainto_tsquery("french", clean_query)
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

    for rank, (chunk, doc) in enumerate(vector_results, start=1):
        chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + (1.0 / (60.0 + rank))
        chunk_map[chunk.id] = (chunk, doc)

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
            "is_full_document_citation": is_full_doc,
        })

    return formatted_results
