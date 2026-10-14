import os
import re
import json
import hashlib
from typing import List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from app.models.schemas import Document, DocumentPage, DocumentChunk
from app.config import settings

from typing import Optional

# Lazy-loaded model instance
_model: Optional[SentenceTransformer] = None

def get_embedding_model() -> SentenceTransformer:
    """
    Charge le modèle SentenceTransformer localement depuis MODELS_DIR en mode 100% hors-ligne.
    Valide les 384 dimensions d'embedding et configure max_seq_length à 512.
    Lève une RuntimeError explicite si le modèle n'a pas été préparé dans MODELS_DIR.
    """
    global _model
    if _model is None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        
        models_dir = getattr(settings, "MODELS_DIR", "./models")
        if not os.path.isabs(models_dir):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            models_dir = os.path.abspath(os.path.join(base_dir, models_dir))
            
        model_name = getattr(settings, "EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
        model_basename = model_name.split("/")[-1]
        
        candidate_paths = [
            os.path.join(models_dir, model_basename),
            os.path.join(models_dir, model_name),
            os.path.join(models_dir, model_name.replace("/", "_")),
            models_dir
        ]
        
        target_path = None
        for p in candidate_paths:
            if os.path.isdir(p) and (os.path.exists(os.path.join(p, "config.json")) or os.path.exists(os.path.join(p, "modules.json"))):
                target_path = p
                break
                
        if not target_path:
            raise RuntimeError(
                f"Modèle d'embedding '{model_name}' absent du dossier local '{models_dir}'. "
                f"Veuillez exécuter 'python scripts/prepare_models.py' sur une machine connectée pour préparer les modèles hors-ligne."
            )
            
        model = SentenceTransformer(target_path, local_files_only=True)
        dim = model.get_sentence_embedding_dimension()
        expected_dim = getattr(settings, "EMBEDDING_DIM", 384)
        assert dim == expected_dim, f"Dimension du modèle d'embedding invalide : attendu {expected_dim}, obtenu {dim}"
        model.max_seq_length = 512
        _model = model
    return _model

from collections import OrderedDict
import threading
import time

_query_cache_lock = threading.Lock()
_query_embedding_cache = OrderedDict()  # key -> (embedding_list, expire_time)

def get_cached_query_embedding(query_text: str):
    now = time.time()
    with _query_cache_lock:
        if query_text in _query_embedding_cache:
            emb, expire_at = _query_embedding_cache[query_text]
            if now < expire_at:
                _query_embedding_cache.move_to_end(query_text)
                return emb
            else:
                del _query_embedding_cache[query_text]
    return None

def set_cached_query_embedding(query_text: str, emb):
    cache_size = getattr(settings, "QUERY_EMBEDDING_CACHE_SIZE", 1024)
    ttl = getattr(settings, "QUERY_CACHE_TTL_SECONDS", 3600)
    now = time.time()
    with _query_cache_lock:
        if len(_query_embedding_cache) >= cache_size:
            _query_embedding_cache.popitem(last=False)
        _query_embedding_cache[query_text] = (emb, now + ttl)

def clear_query_embedding_cache():
    with _query_cache_lock:
        _query_embedding_cache.clear()

def embed_text(text: str, kind: str = "passage") -> List[float]:
    """
    Computes dense 384-dimensional vector embedding for the given text.
    kind must be 'passage' or 'query' (mandatory for e5).
    normalize_embeddings=True enables standard cosine distance comparisons.
    Uses in-memory LRU cache with TTL for identical query embeddings (kind='query').
    """
    if kind not in {"passage", "query"}:
        raise ValueError(f"Paramètre kind invalide : '{kind}'. Attendu 'passage' ou 'query'.")

    expected_dim = getattr(settings, "EMBEDDING_DIM", 384)
    if not text or not text.strip():
        return [0.0] * expected_dim

    clean_text = text.strip()
    if kind == "query":
        cached = get_cached_query_embedding(clean_text)
        if cached is not None:
            return cached

    model = get_embedding_model()
    prefix = settings.EMBEDDING_QUERY_PREFIX if kind == "query" else settings.EMBEDDING_PASSAGE_PREFIX
    prefixed_text = f"{prefix}{clean_text}"
    emb = model.encode(prefixed_text, normalize_embeddings=True)
    import numpy as np
    if np.isnan(emb).any():
        emb = np.nan_to_num(emb, nan=0.0)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
            
    res_list = emb.tolist()
    if kind == "query":
        set_cached_query_embedding(clean_text, res_list)
        
    return res_list

def embed_texts(texts: List[str], kind: str = "passage") -> List[List[float]]:
    """
    Computes dense 384-dimensional vector embeddings in batch for a list of texts.
    kind must be 'passage' or 'query' (mandatory for e5).
    """
    if kind not in {"passage", "query"}:
        raise ValueError(f"Paramètre kind invalide : '{kind}'. Attendu 'passage' ou 'query'.")

    if not texts:
        return []

    model = get_embedding_model()
    prefix = settings.EMBEDDING_QUERY_PREFIX if kind == "query" else settings.EMBEDDING_PASSAGE_PREFIX
    prefixed_texts = [f"{prefix}{t.strip()}" if t and t.strip() else f"{prefix}" for t in texts]
    embs = model.encode(prefixed_texts, normalize_embeddings=True)
    import numpy as np
    result: List[List[float]] = []
    for emb in embs:
        if np.isnan(emb).any():
            emb = np.nan_to_num(emb, nan=0.0)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
        result.append(emb.tolist())
    return result

def _split_oversized_block(block_text: str, page_num: int, chunk_size_words: int) -> List[Dict[str, Any]]:
    """
    Splits a block that exceeds chunk_size_words into sub-blocks.
    - If markdown table: split by rows (lines), never cutting in the middle of a row.
    - If regular text: split by sentences.
    Each sub-block is an exact substring of the original block text.
    """
    words = block_text.split()
    if len(words) <= chunk_size_words:
        return [{"text": block_text, "page_number": page_num, "words": len(words)}]

    lines = block_text.split("\n")
    is_table = any(line.strip().startswith("|") for line in lines)

    sub_blocks = []
    if is_table:
        curr_lines = []
        curr_words = 0
        for line in lines:
            if not line.strip():
                continue
            line_w = len(line.split())
            if curr_words + line_w > chunk_size_words and curr_words > 0:
                sub_text = "\n".join(curr_lines)
                sub_blocks.append({"text": sub_text, "page_number": page_num, "words": curr_words})
                curr_lines = [line]
                curr_words = line_w
            else:
                curr_lines.append(line)
                curr_words += line_w
        if curr_lines:
            sub_text = "\n".join(curr_lines)
            sub_blocks.append({"text": sub_text, "page_number": page_num, "words": curr_words})
    else:
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', block_text)
        curr_sents = []
        curr_words = 0
        for sent in sentences:
            if not sent.strip():
                continue
            sent_w = len(sent.split())
            if curr_words + sent_w > chunk_size_words and curr_words > 0:
                sub_text = " ".join(curr_sents)
                sub_blocks.append({"text": sub_text, "page_number": page_num, "words": curr_words})
                curr_sents = [sent]
                curr_words = sent_w
            else:
                curr_sents.append(sent)
                curr_words += sent_w
        if curr_sents:
            sub_text = " ".join(curr_sents)
            sub_blocks.append({"text": sub_text, "page_number": page_num, "words": curr_words})

    return sub_blocks if sub_blocks else [{"text": block_text, "page_number": page_num, "words": len(words)}]


def chunk_pages_across_boundaries(
    pages: List[Any],
    chunk_size_words: int = 150,
    overlap_words: int = 30
) -> List[Dict[str, Any]]:
    """
    Chunks a list of pages across page boundaries preserving atomic blocks and original text substrings.
    - Flattens all pages into atomic blocks (separated by '\n\n') tracking page_number for each block.
    - A block (paragraph/table) is never split unless it alone exceeds chunk_size_words (split by sentences or table lines).
    - Chunk text is an exact concatenation of original blocks joined by '\n\n' (never ' '.join(words)).
    - Overlap preserves whole block(s) from the tail of the previous chunk <= overlap_words.
    - Returns list of {"text", "page_start", "page_end", "segments"}.
    """
    if not pages:
        return []

    # 1. Flatten all pages into atomic blocks
    all_blocks: List[Dict[str, Any]] = []
    for p in pages:
        page_num = getattr(p, "page_number", None) if not isinstance(p, dict) else p.get("page_number")
        if page_num is None:
            page_num = 1
        raw_text = getattr(p, "extracted_text", None) or getattr(p, "text", "") if not isinstance(p, dict) else (p.get("extracted_text") or p.get("text", ""))
        if not raw_text or not raw_text.strip():
            continue

        raw_blocks = [b.strip() for b in raw_text.split("\n\n") if b.strip()]
        for b in raw_blocks:
            sub_b = _split_oversized_block(b, page_num, chunk_size_words)
            all_blocks.extend(sub_b)

    if not all_blocks:
        return []

    # 2. Build chunks across boundaries
    chunks: List[Dict[str, Any]] = []
    start_idx = 0
    n_blocks = len(all_blocks)

    while start_idx < n_blocks:
        current_chunk_blocks = [all_blocks[start_idx]]
        current_words = all_blocks[start_idx]["words"]
        end_idx = start_idx

        # Greedily add next blocks up to chunk_size_words
        next_idx = start_idx + 1
        while next_idx < n_blocks:
            b = all_blocks[next_idx]
            if current_words + b["words"] <= chunk_size_words:
                current_chunk_blocks.append(b)
                current_words += b["words"]
                end_idx = next_idx
                next_idx += 1
            else:
                break

        # Construct chunk data
        chunk_text_str = "\n\n".join(b["text"] for b in current_chunk_blocks)
        segments: List[Dict[str, Any]] = []
        curr_char = 0
        for b in current_chunk_blocks:
            blen = len(b["text"])
            segments.append({
                "page_number": b["page_number"],
                "char_start": curr_char,
                "char_end": curr_char + blen
            })
            curr_char += blen + 2  # len("\n\n") == 2

        page_start = min(b["page_number"] for b in current_chunk_blocks)
        page_end = max(b["page_number"] for b in current_chunk_blocks)

        chunks.append({
            "text": chunk_text_str,
            "page_start": page_start,
            "page_end": page_end,
            "segments": segments
        })

        if end_idx >= n_blocks - 1:
            break

        # Calculate overlap for next chunk
        # Look backwards from end_idx to pick whole blocks <= overlap_words
        overlap_start = end_idx + 1
        curr_overlap = 0
        for k in range(end_idx, start_idx - 1, -1):
            if curr_overlap + all_blocks[k]["words"] <= overlap_words:
                curr_overlap += all_blocks[k]["words"]
                overlap_start = k
            else:
                break

        # Ensure that overlap_blocks + next new block (end_idx + 1) does not exceed chunk_size_words
        next_new_block_words = all_blocks[end_idx + 1]["words"]
        while overlap_start <= end_idx and (curr_overlap + next_new_block_words > chunk_size_words):
            curr_overlap -= all_blocks[overlap_start]["words"]
            overlap_start += 1

        if overlap_start > end_idx:
            start_idx = end_idx + 1
        else:
            start_idx = overlap_start

    return chunks


def chunk_text(text: str, chunk_size_words: int = 350, overlap_words: int = 50) -> List[str]:
    """
    DEPRECATED: Use chunk_pages_across_boundaries instead.
    This function is maintained for backwards compatibility.
    
    Splits text into chunks of approximately chunk_size_words (500-900 tokens)
    with overlap_words overlap between consecutive chunks to preserve semantic context.
    """
    if not text or not text.strip():
        return []
    
    blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
    
    chunks = []
    current_chunk_words = []
    current_word_count = 0
    
    for block in blocks:
        block_words = block.split()
        block_word_count = len(block_words)
        
        if current_word_count + block_word_count > chunk_size_words and current_word_count > 0:
            chunks.append(" ".join(current_chunk_words).strip())
            overlap = current_chunk_words[-overlap_words:] if overlap_words > 0 else []
            current_chunk_words = overlap + block_words
            current_word_count = len(current_chunk_words)
        else:
            current_chunk_words.extend(block_words)
            current_word_count += block_word_count
            
    if current_chunk_words:
        chunks.append(" ".join(current_chunk_words).strip())
        
    return chunks


def index_document(document_id: int, db: Session) -> int:
    """
    Indexes an extracted document using boundary-crossing chunking:
    1. Fetches all DocumentPages ordered by page_number.
    2. Determines source_format (pdf, docx, other) and pagination_type ('virtual' if DOCX multi-pages, else 'native').
    3. Chunks pages across boundaries using chunk_pages_across_boundaries() once for the whole document.
    4. Computes per-chunk metadata_json containing source_format, pagination_type, and segments.
    5. Deduplicates by content_hash locally and against existing chunks for this document in DB.
    6. Generates embeddings and PostgreSQL TSVECTOR, then stores DocumentChunk rows.
    Returns the total number of chunks created.
    """
    # Clear existing chunks for idempotency (e.g. retry workflow)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
    db.flush()

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document with ID {document_id} not found")

    file_url = (doc.file_url or "").lower()
    source_format = "pdf" if file_url.endswith(".pdf") else ("docx" if file_url.endswith(".docx") else "other")

    pages = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc())
        .all()
    )

    if not pages:
        return 0

    pagination_type = "virtual" if (source_format == "docx" and len(pages) > 1) else "native"

    chunk_size_words = getattr(settings, "CHUNK_SIZE_WORDS", 150)
    overlap_words = getattr(settings, "CHUNK_OVERLAP_WORDS", 30)

    raw_chunks = chunk_pages_across_boundaries(
        pages=pages,
        chunk_size_words=chunk_size_words,
        overlap_words=overlap_words
    )

    chunk_index = 0
    created_count = 0
    seen_hashes = set()
    
    fallback_security_group = doc.security_groups[0].name if doc.security_groups else "default"

    valid_chunk_data = []
    texts_to_embed = []

    for cdata in raw_chunks:
        piece = cdata["text"]
        if not piece or not piece.strip():
            continue

        content_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()

        # Deduplication: local set check
        if content_hash in seen_hashes:
            continue

        # Deduplication: database check for this document
        existing_in_db = (
            db.query(DocumentChunk.id)
            .filter(DocumentChunk.document_id == doc.id, DocumentChunk.content_hash == content_hash)
            .first()
        )
        if existing_in_db:
            continue

        seen_hashes.add(content_hash)

        # Section detection
        section = None
        lines = piece.split("\n")
        if lines:
            first_line = lines[0].strip()
            if first_line and len(first_line) < 80 and not first_line[-1] in {'.', ':', '!', '?'}:
                section = first_line

        metadata = {
            "source_format": source_format,
            "pagination_type": pagination_type,
            "segments": cdata["segments"]
        }
        metadata_json = json.dumps(metadata)

        valid_chunk_data.append({
            "page_start": cdata["page_start"],
            "page_end": cdata["page_end"],
            "piece": piece,
            "section": section,
            "metadata_json": metadata_json,
            "content_hash": content_hash
        })
        texts_to_embed.append(piece)

    if not valid_chunk_data:
        db.commit()
        return 0

    # Batch embed all chunks for the document in a single model forward pass
    all_embeddings = embed_texts(texts_to_embed, kind="passage")

    for i, item in enumerate(valid_chunk_data):
        chunk_obj = DocumentChunk(
            document_id=doc.id,
            page_start=item["page_start"],
            page_end=item["page_end"],
            chunk_index=chunk_index,
            content=item["piece"],
            embedding=all_embeddings[i],
            search_vector=func.to_tsvector("french", item["piece"]),
            metadata_json=item["metadata_json"],
            section=item["section"],
            security_group=fallback_security_group,
            content_hash=item["content_hash"]
        )
        db.add(chunk_obj)
        chunk_index += 1
        created_count += 1

    db.commit()
    return created_count
