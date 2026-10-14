# © 2026 MBIH NGALLY YOHAN JONATHAN & TIENTCHEU NLOM DAVID. Tous droits réservés.
# Utilisation en production strictement interdite sans licence commerciale.
# TODO (DÉCISION HUMAINE) : Vérifier si cette mention de licence commerciale stricte n'entre pas en conflit avec le règlement de soumission du concours.

import json
import re
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.schemas import Document, DocumentChunk
from app.services.indexing import embed_text
from app.config import settings

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from sentence_transformers import CrossEncoder
        
        models_dir = getattr(settings, "MODELS_DIR", "./models")
        if not os.path.isabs(models_dir):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            models_dir = os.path.abspath(os.path.join(base_dir, models_dir))
            
        model_name = getattr(settings, "RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
        model_basename = model_name.split("/")[-1]
        
        candidate_paths = [
            os.path.join(models_dir, model_basename),
            os.path.join(models_dir, model_name),
            os.path.join(models_dir, model_name.replace("/", "_")),
            models_dir
        ]
        
        target_path = None
        for p in candidate_paths:
            if os.path.isdir(p) and (os.path.exists(os.path.join(p, "config.json")) or os.path.exists(os.path.join(p, "model.safetensors")) or os.path.exists(os.path.join(p, "pytorch_model.bin"))):
                target_path = p
                break
                
        if not target_path:
            raise RuntimeError(
                f"Modèle reranker '{model_name}' absent du dossier local '{models_dir}'. "
                f"Veuillez exécuter 'python scripts/prepare_models.py --include-reranker' sur une machine connectée pour préparer les modèles hors-ligne."
            )
            
        _reranker = CrossEncoder(target_path, local_files_only=True)
    return _reranker

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
    
    # Configuration dynamique de hnsw.ef_search pour l'index HNSW pgvector
    ef_search = getattr(settings, "HNSW_EF_SEARCH", 64)
    try:
        from sqlalchemy import text
        db.execute(text(f"SET hnsw.ef_search = {int(ef_search)};"))
    except Exception:
        pass

    query_emb = embed_text(clean_query, kind="query")

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
        
        # Filtrage strict au niveau du document ET au niveau du chunk (Option B rigoureuse)
        from app.models.schemas import SecurityGroup
        base_filter.append(Document.security_groups.any(SecurityGroup.name.in_(security_groups)))
        base_filter.append(DocumentChunk.security_group.in_(security_groups))

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
        .limit(15 if getattr(settings, "RERANKER_ENABLED", False) else 8)
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
            .limit(15 if getattr(settings, "RERANKER_ENABLED", False) else 8)
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

    import numpy as np
    q_emb_arr = np.array(query_emb)
    norm_q = float(np.linalg.norm(q_emb_arr))

    for rank, (chunk, doc) in enumerate(lexical_results, start=1):
        chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0.0) + (1.0 / (60.0 + rank))
        chunk_map[chunk.id] = (chunk, doc)
        if chunk.id not in chunk_distances and chunk.embedding is not None:
            c_emb_arr = np.array(chunk.embedding)
            norm_c = float(np.linalg.norm(c_emb_arr))
            if norm_c > 0 and norm_q > 0:
                cos_sim = float(np.dot(c_emb_arr, q_emb_arr) / (norm_c * norm_q))
                chunk_distances[chunk.id] = float(max(0.0, 1.0 - cos_sim))
            else:
                chunk_distances[chunk.id] = 1.0

    if not chunk_scores:
        return []

    # 5. Sort candidates and optionally rerank with CrossEncoder
    candidate_ids = sorted(chunk_scores.keys(), key=lambda cid: chunk_scores[cid], reverse=True)
    
    if getattr(settings, "RERANKER_ENABLED", False) and candidate_ids:
        rerank_candidates = candidate_ids[:15]
        reranker = get_reranker()
        pairs = [(clean_query, chunk_map[cid][0].content or "") for cid in rerank_candidates]
        rerank_scores = reranker.predict(pairs)
        # Sort by reranker cross-encoder score descending
        sorted_pairs = sorted(zip(rerank_scores, rerank_candidates), key=lambda x: x[0], reverse=True)
        sorted_chunk_ids = [cid for _, cid in sorted_pairs][:top_k]
    else:
        sorted_chunk_ids = candidate_ids[:top_k]

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

        is_full_doc = meta.get("is_full_document_citation", False)
        pagination_type = meta.get("pagination_type", "native")
        segments = meta.get("segments", [])

        formatted_results.append({
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "document_title": doc.title,
            "document_version": doc.version,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "pagination_type": pagination_type,
            "segments": segments,
            "content": chunk.content or "",
            "excerpt": excerpt,
            "score": round(score, 6),
            "vector_distance": vector_dist,
            "is_full_document_citation": is_full_doc,
        })

    return formatted_results
