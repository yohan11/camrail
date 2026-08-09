import os
import json
from typing import List
from sqlalchemy import func
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from app.models.schemas import Document, DocumentPage, DocumentChunk

# Initialize sentence-transformers model from local cache
_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def embed_text(text: str) -> List[float]:
    """
    Computes dense 384-dimensional vector embedding for the given text.
    normalize_embeddings=True enables standard cosine distance comparisons.
    """
    if not text or not text.strip():
        return [0.0] * 384
    emb = _model.encode(text, normalize_embeddings=True)
    return emb.tolist()


def chunk_text(text: str, chunk_size_words: int = 350, overlap_words: int = 50) -> List[str]:
    """
    Splits text into chunks of approximately chunk_size_words (500-900 tokens)
    with overlap_words overlap between consecutive chunks to preserve semantic context.
    """
    if not text or not text.strip():
        return []
    words = text.split()
    if len(words) <= chunk_size_words:
        return [text.strip()]
    
    chunks = []
    start = 0
    step = max(1, chunk_size_words - overlap_words)
    while start < len(words):
        chunk_words = words[start:start + chunk_size_words]
        chunk_str = " ".join(chunk_words).strip()
        if chunk_str:
            chunks.append(chunk_str)
        if start + chunk_size_words >= len(words):
            break
        start += step
    return chunks


def index_document(document_id: int, db: Session) -> int:
    """
    Indexes an extracted document:
    1. Fetches all DocumentPages ordered by page_number.
    2. Determines source_format (pdf or docx) and is_full_document_citation.
    3. Chunks page text using chunk_text().
    4. Generates local dense embeddings and calculates PostgreSQL TSVECTOR.
    5. Cleans previous chunks and saves new DocumentChunk rows.
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
    is_full_document_citation = (source_format == "docx")

    metadata = {
        "source_format": source_format,
        "is_full_document_citation": is_full_document_citation
    }
    metadata_json = json.dumps(metadata)

    pages = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number.asc())
        .all()
    )

    chunk_index = 0
    created_count = 0

    for page in pages:
        page_text = (page.extracted_text or "").strip()
        if not page_text:
            continue

        chunks = chunk_text(page_text, chunk_size_words=350, overlap_words=50)
        for piece in chunks:
            emb = embed_text(piece)
            chunk_obj = DocumentChunk(
                document_id=doc.id,
                page_start=page.page_number,
                page_end=page.page_number,
                chunk_index=chunk_index,
                content=piece,
                embedding=emb,
                search_vector=func.to_tsvector("french", piece),
                metadata_json=metadata_json
            )
            db.add(chunk_obj)
            chunk_index += 1
            created_count += 1

    db.commit()
    return created_count
