import httpx
import logging
import re
from typing import List, Dict, Any

from app.config import settings
from app.services.connectivity import is_online

logger = logging.getLogger(__name__)

def extract_and_filter_citations(answer_text: str, all_citations: list) -> list:
    # Find all [X] in the answer
    matches = re.findall(r'\[(\d+)\]', answer_text)
    used_indices = {int(m) for m in matches}
    
    # If no citations were used or found, return empty
    if not used_indices:
        return []
        
    final_citations = []
    seen_front = set()
    for cit in all_citations:
        if cit["llm_index"] in used_indices:
            key = (cit["document_id"], cit["page_start"])
            if key not in seen_front:
                seen_front.add(key)
                # Remove internal llm_index for the frontend
                cit_copy = cit.copy()
                del cit_copy["llm_index"]
                final_citations.append(cit_copy)
                
    return final_citations

def _generate_with_gemini(system_prompt: str, user_message: str) -> str:
    """Génère la réponse avec Gemini. Lève une exception explicite en cas d'échec."""
    import google.generativeai as genai
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY non configurée")
        
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-flash-lite-latest')
    
    prompt = f"{system_prompt}\n\n{user_message}"
    
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.0,
            max_output_tokens=400,
        )
    )
    return response.text.strip()

def _generate_with_ollama(system_prompt: str, user_message: str) -> str:
    """Génère la réponse avec Ollama. Lève une exception explicite en cas d'échec.
    Note: llama3.2:3b gère mieux les instructions dans un seul bloc que via le rôle 'system'.
    """
    # On fusionne les deux dans un seul message user pour une compatibilité maximale avec llama3.2
    full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"
    
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "user", "content": full_prompt}
        ],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 400}
    }
    
    ollama_url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    with httpx.Client(timeout=180.0) as client:
        response = client.post(ollama_url, json=payload)
        response.raise_for_status()
        data = response.json()
        
    return data.get("message", {}).get("content", "").strip()

def generate_answer(query: str, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a natural language answer based on hybrid_search results.
    Implémente un basculement automatique entre Gemini (online) et Ollama (offline).
    """
    if not search_results:
        return {
            "answer": "Je ne trouve pas cette information dans les documents indexés.",
            "confidence": "insufficient",
            "citations": [],
            "provider": None
        }

    # Evaluate confidence based on vector distance
    top_result = search_results[0]
    vector_distance = top_result.get("vector_distance")

    if vector_distance is None:
        confidence = "medium"
    elif vector_distance < 0.5:
        confidence = "high"
    elif vector_distance < settings.RAG_MIN_CONFIDENCE:
        confidence = "medium"
    else:
        confidence = "insufficient"
        
    if confidence == "insufficient":
        return {
            "answer": "Je ne trouve pas cette information dans les documents indexés.",
            "confidence": "insufficient",
            "citations": [],
            "provider": None
        }

    system_prompt = (
        "Tu es l'assistant documentaire de CAMRAIL RailMind Lite. Réponds UNIQUEMENT à partir "
        "des extraits fournis ci-dessous. N'invente jamais une politique, un seuil, une date ou "
        "une procédure qui n'apparaît pas explicitement dans les extraits. "
        "Si la question concerne un tableau ou une comparaison, fais très attention à ne pas mélanger "
        "les lignes, les colonnes ou les extraits entre eux. "
        "Si les extraits ne permettent pas de répondre clairement à la question, dis explicitement que l'information "
        "ne peut pas être confirmée par les documents indexés. "
        "Réponds dans la langue de la question. Reste concis, deux ou trois phrases maximum. N'utilise "
        "jamais de connaissance générale extérieure. N'utilise pas de symboles mathématiques spéciaux comme les signes dollar ($) pour tes équations. "
        "IMPORTANT : Si tu utilises un extrait pour construire ta réponse, tu DOIS obligatoirement inclure son numéro à la fin de la phrase correspondante sous la forme [1], [2], etc. "
        "N'inclus QUE les numéros des extraits que tu as réellement utilisés."
    )

    user_message = f"Question : {query}\n\n"
    all_citations = []
    filtered_results = []
    
    # 1. Filter irrelevant results based on vector_distance
    for res in search_results:
        v_dist = res.get("vector_distance")
        if v_dist is not None and v_dist >= settings.RAG_MIN_CONFIDENCE:
            continue
        filtered_results.append(res)
        
    if not filtered_results:
        return {
            "answer": "Je ne trouve pas cette information dans les documents indexés.",
            "confidence": "insufficient",
            "citations": [],
            "provider": None
        }
    
    # 2. Build citations and LLM context
    for i, res in enumerate(filtered_results, start=1):
        title = res.get("document_title", "Document inconnu")
        page = res.get("page_start", "?")
        excerpt = res.get("excerpt", "")
        
        user_message += f"Extrait {i} (source : {title}, page {page}) :\n{excerpt}\n\n"
        
        doc_id = res.get("document_id", 0)
        
        all_citations.append({
            "llm_index": i,
            "document_id": doc_id,
            "document_title": title,
            "document_version": res.get("document_version", "1.0"),
            "page_start": page,
            "page_end": res.get("page_end", page),
            "section": res.get("section"),
            "excerpt": excerpt[:200] + "..." if len(excerpt) > 200 else excerpt,
            "score": res.get("score")
        })
        
    user_message += "Réponds à la question en te basant uniquement sur ces extraits."
    
    # --- AUTOMATIC ROUTER ---
    answer_text = None
    provider_used = None
    
    if is_online():
        try:
            answer_text = _generate_with_gemini(system_prompt, user_message)
            provider_used = "gemini"
        except Exception as e:
            logger.error(f"Gemini indisponible malgré une connexion détectée, bascule sur Ollama en secours. Détail: {e}")
            
    # Si offline OU erreur avec Gemini, on passe par Ollama
    if answer_text is None:
        try:
            answer_text = _generate_with_ollama(system_prompt, user_message)
            provider_used = "ollama"
        except Exception as e:
            logger.error(f"Erreur avec Ollama (secours): {e}")
            return {
                "answer": "Service temporairement indisponible (erreur locale).",
                "confidence": "insufficient",
                "citations": [],
                "provider": None
            }

    final_citations = extract_and_filter_citations(answer_text, all_citations)
    
    return {
        "answer": answer_text,
        "confidence": confidence,
        "citations": final_citations,
        "provider": provider_used
    }
