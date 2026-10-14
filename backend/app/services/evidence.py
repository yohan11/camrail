import re
import numpy as np
from typing import List, Dict, Any
from app.services.indexing import get_embedding_model
from app.config import settings

FRENCH_ABBREVIATIONS = [
    "M.", "Mme.", "Mlle.", "Dr.", "Pr.", "Prof.", "av.", "al.", "art.",
    "cf.", "ex.", "etc.", "vol.", "p.", "pp.", "tel.", "approx.", "min.",
    "max.", "St.", "Ste.", "chap.", "fig.", "ref.", "v."
]

def _split_into_units(content: str) -> List[tuple[str, int]]:
    """
    Splits chunk content into atomic units:
    - A single sentence (split on . ! ? followed by whitespace/uppercase, accounting for French abbreviations)
    - OR a single markdown table row ('| ... |')
    Returns list of (unit_text, char_offset_in_content).
    """
    if not content:
        return []

    lines = content.split("\n")
    units: List[tuple[str, int]] = []
    current_offset = 0

    for line in lines:
        stripped_line = line.strip()
        line_offset = content.find(line, current_offset)
        if line_offset == -1:
            line_offset = current_offset

        # Detect markdown table rows
        if stripped_line.startswith("|") and stripped_line.endswith("|"):
            # Exclude table header delimiter rows like |---|---|
            if not all(c in "| -:\t" for c in stripped_line):
                unit_text = stripped_line[:600]
                units.append((unit_text, line_offset))
        elif stripped_line:
            # Paragraph text: protect abbreviations
            protected = stripped_line
            for abbrev in FRENCH_ABBREVIATIONS:
                safe = abbrev.replace(".", "@@DOT@@")
                pattern = r'\b' + re.escape(abbrev[:-1]) + r'\.'
                protected = re.sub(pattern, safe, protected, flags=re.IGNORECASE)

            # Protect article/chapter/numeric prefixes from being split (e.g. Article 1., 2., etc.)
            protected = re.sub(r'(\b(?:Article|Art|Chapitre|Section|Al|Par)\s+\d+)\.', r'\1@@DOT@@', protected, flags=re.IGNORECASE)
            protected = re.sub(r'(?<=\b\d)\.(?=\s)', '@@DOT@@', protected)

            # Split on sentence terminators (. ! ?) followed by whitespace and an uppercase letter or number/quote
            raw_sents = re.split(r'(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-ß0-9«"\'\n])', protected)
            
            sent_search_pos = line_offset
            for s in raw_sents:
                clean_s = s.replace("@@DOT@@", ".").strip()
                if clean_s:
                    s_offset = content.find(clean_s, sent_search_pos)
                    if s_offset == -1:
                        s_offset = sent_search_pos
                    units.append((clean_s[:600], s_offset))
                    sent_search_pos = s_offset + len(clean_s)

        current_offset = line_offset + len(line) + 1  # accounts for newline

    return units


def select_evidence(chunk: Any, claim_text: str, max_units: int = 2) -> List[Dict[str, Any]]:
    """
    Selects the most relevant evidence units (sentences or table rows) from a chunk.
    - Embeds all units in a single batch call and compares with claim_text via cosine similarity.
    - Returns top units sorted in original textual order.
    - Deduces page_number from chunk segments using unit character offset.
    - Never appends artificial '...' to units.
    """
    if isinstance(chunk, dict):
        content = chunk.get("content") or chunk.get("excerpt") or chunk.get("text") or ""
        segments = chunk.get("segments") or []
        fallback_page = chunk.get("page_start", 1)
    else:
        content = getattr(chunk, "content", "") or ""
        segments = getattr(chunk, "segments", []) or []
        fallback_page = getattr(chunk, "page_start", 1)

    # If segments were stored as JSON string in chunk object
    if isinstance(segments, str):
        import json
        try:
            segments = json.loads(segments)
        except Exception:
            segments = []

    raw_units = _split_into_units(content)
    if not raw_units:
        return []

    # Filter out empty or trivially short units
    valid_units = [(u, offset) for u, offset in raw_units if len(u.strip()) > 5]
    if not valid_units:
        return []

    unit_texts = [u for u, _ in valid_units]
    
    # Batch encode all candidate units plus the claim text in a single model forward pass
    # e5 requires 'passage: ' for document text and 'query: ' for claims/queries
    clean_claim = claim_text.strip() if claim_text else "information"
    all_texts = [f"passage: {u}" for u in unit_texts] + [f"query: {clean_claim}"]
    model = get_embedding_model()
    embeddings = model.encode(all_texts, normalize_embeddings=True)

    unit_embs = embeddings[:-1]
    claim_emb = embeddings[-1]

    # Normalized dot product equals cosine similarity
    scores = np.dot(unit_embs, claim_emb)

    min_score = getattr(settings, "EVIDENCE_MIN_SCORE", 0.20)

    scored_units: List[Dict[str, Any]] = []
    for idx, ((u_text, offset), score) in enumerate(zip(valid_units, scores)):
        score_val = float(score)
        if score_val >= min_score:
            # Deduce page_number from segments
            page_num = fallback_page
            for seg in segments:
                if seg.get("char_start", 0) <= offset <= seg.get("char_end", 999999):
                    page_num = seg.get("page_number", fallback_page)
                    break
            scored_units.append({
                "text": u_text,
                "page_number": page_num,
                "score": round(score_val, 4),
                "offset": offset
            })

    # If all units scored below min_score, fallback to the highest scoring unit
    if not scored_units:
        best_idx = int(np.argmax(scores))
        best_u, best_off = valid_units[best_idx]
        page_num = fallback_page
        for seg in segments:
            if seg.get("char_start", 0) <= best_off <= seg.get("char_end", 999999):
                page_num = seg.get("page_number", fallback_page)
                break
        scored_units = [{
            "text": best_u,
            "page_number": page_num,
            "score": round(float(scores[best_idx]), 4),
            "offset": best_off
        }]

    # Pick top max_units by similarity score
    scored_units.sort(key=lambda x: x["score"], reverse=True)
    top_units = scored_units[:max_units]

    # Re-sort in textual appearance order
    top_units.sort(key=lambda x: x["offset"])

    # Remove internal offset key
    for u in top_units:
        del u["offset"]

    return top_units
