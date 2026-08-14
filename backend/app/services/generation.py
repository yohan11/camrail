import httpx
import logging
from typing import List, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)

def generate_answer(query: str, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a natural language answer based on hybrid_search results using Ollama.
    """
    if not search_results:
        return {
            "answer": "Je ne trouve pas cette information dans les documents indexés.",
            "confidence": "insufficient",
            "citations": []
        }

    # Evaluate confidence based on vector distance
    top_result = search_results[0]
    vector_distance = top_result.get("vector_distance")

    if vector_distance is None:
        # Trouvé uniquement par le lexical, pas de signal sémantique disponible :
        # traite comme confiance modérée par défaut, le match lexical reste un signal
        confidence = "medium"
    elif vector_distance < 0.5:
        # Distance cosinus faible = très similaire sémantiquement (seuil de départ)
        confidence = "high"
    elif vector_distance < settings.RAG_MIN_CONFIDENCE:
        # Distance moyenne (seuil configurable)
        confidence = "medium"
    else:
        # Distance élevée = aucun rapport sémantique réel
        confidence = "insufficient"
        
    if confidence == "insufficient":
        return {
            "answer": "Je ne trouve pas cette information dans les documents indexés.",
            "confidence": "insufficient",
            "citations": []
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
        "jamais de connaissance générale extérieure."
    )

    user_message = f"Question : {query}\n\n"
    citations = []
    seen_sources = set()
    filtered_results = []
    
    # 1. Filter irrelevant results based on vector_distance
    for res in search_results:
        v_dist = res.get("vector_distance")
        # vector_distance 0.0 is perfect match, high distance is bad.
        # Threshold: RAG_MIN_CONFIDENCE (e.g. 0.75 means distance < 0.75 is required)
        if v_dist is not None and v_dist >= settings.RAG_MIN_CONFIDENCE:
            continue
        filtered_results.append(res)
        
    if not filtered_results:
        return {
            "answer": "Je ne trouve pas cette information dans les documents indexés.",
            "confidence": "insufficient",
            "citations": []
        }
    
    # 2. Build citations and LLM context
    for i, res in enumerate(filtered_results, start=1):
        title = res.get("document_title", "Document inconnu")
        page = res.get("page_start", "?")
        excerpt = res.get("excerpt", "")
        
        user_message += f"Extrait {i} (source : {title}, page {page}) :\n{excerpt}\n\n"
        
        # Deduplicate citations by document_id and page
        doc_id = res.get("document_id", 0)
        citation_key = (doc_id, page)
        
        if citation_key not in seen_sources:
            seen_sources.add(citation_key)
            citations.append({
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
    
    # --- GEMINI PROVIDER ---
    if settings.LLM_PROVIDER.lower() == "gemini":
        try:
            import google.generativeai as genai
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY non configurée")
                
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
            # Use gemini-flash-latest as the default model
            model = genai.GenerativeModel('gemini-flash-latest')
            
            prompt = f"{system_prompt}\n\n{user_message}"
            
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0,
                    max_output_tokens=400,
                )
            )
            
            return {
                "answer": response.text.strip(),
                "confidence": confidence,
                "citations": citations
            }
        except Exception as e:
            logger.error(f"Erreur avec Gemini API: {e}")
            return {
                "answer": f"Erreur avec Gemini API. Vérifiez votre clé. (Détail: {e})",
                "confidence": "insufficient",
                "citations": citations
            }
            
    # --- OLLAMA PROVIDER (Default / Fallback) ---
    else:
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 400}
        }

        try:
            with httpx.Client(timeout=180.0) as client:
                response = client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                answer_text = data.get("message", {}).get("content", "").strip()
                
                return {
                    "answer": answer_text,
                    "confidence": confidence,
                    "citations": citations
                }
                
        except httpx.ConnectError as e:
            logger.error(f"ConnectError: Ollama ne semble pas lancé. {e}")
            return {
                "answer": "Le service de génération est temporairement indisponible. Voici les extraits.",
                "confidence": "insufficient",
                "citations": citations
            }
        except Exception as e:
            logger.error(f"Erreur lors de la génération avec Ollama: {e}")
            return {
                "answer": "Erreur interne lors de la génération de réponse.",
                "confidence": "insufficient",
                "citations": citations
            }
