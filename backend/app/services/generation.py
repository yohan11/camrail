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
    elif vector_distance < 0.75:
        # Distance moyenne (seuil ajusté après test manuel : tarte tatin donne ~0.79)
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
        "une procédure qui n'apparaît pas explicitement dans les extraits. Si les extraits ne "
        "permettent pas de répondre clairement à la question, dis explicitement que l'information "
        "ne peut pas être confirmée par les documents indexés, et précise ce qui manque. Réponds "
        "dans la langue de la question. Reste concis, deux ou trois phrases maximum. N'utilise "
        "jamais de connaissance générale extérieure aux extraits fournis, même si tu la connais "
        "par ailleurs."
    )

    user_message = f"Question : {query}\n\n"
    citations = []
    
    for i, res in enumerate(search_results, start=1):
        title = res.get("document_title", "Document inconnu")
        page = res.get("page_start", "?")
        excerpt = res.get("excerpt", "")
        
        user_message += f"Extrait {i} (source : {title}, page {page}) :\n{excerpt}\n\n"
        
        citations.append({
            "document_title": title,
            "page_start": page,
            "page_end": res.get("page_end", page),
            "excerpt": excerpt[:200] + "..." if len(excerpt) > 200 else excerpt
        })
        
    user_message += "Réponds à la question en te basant uniquement sur ces extraits."

    payload = {
    "model": settings.OLLAMA_MODEL,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    "stream": False,
    "options": {"temperature": 0.2, "num_predict": 150}
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
        logger.error(f"ConnectError: Ollama ne semble pas lancé - vérifier qu'il tourne en arrière-plan. {e}")
        return {
            "answer": "Le service de génération est temporairement indisponible. Voici les passages trouvés dans les documents, à consulter directement.",
            "confidence": "insufficient",
            "citations": citations
        }
    except Exception as e:
        logger.error(f"Erreur lors de la génération avec Ollama: {e}")
        return {
            "answer": "Le service de génération est temporairement indisponible. Voici les passages trouvés dans les documents, à consulter directement.",
            "confidence": "insufficient",
            "citations": citations
        }
