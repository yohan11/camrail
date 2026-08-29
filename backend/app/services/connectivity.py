import httpx
import logging

logger = logging.getLogger(__name__)

def is_online(timeout_seconds: float = 2.0) -> bool:
    """
    Vérifie rapidement si la machine a un accès Internet actif via une requête HTTP.
    On utilise le point de terminaison classique de Google qui retourne un 204 No Content.
    Cela évite les faux positifs causés par les proxys, antivirus ou portails captifs
    qui interceptent les simples requêtes TCP.
    """
    try:
        # Un appel HTTP réel échouera immédiatement ou fera un timeout à 2s si la connexion est coupée
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get("http://clients3.google.com/generate_204")
            return response.status_code == 204
    except Exception as e:
        logger.warning(f"Test de connectivité HTTP échoué. Mode hors ligne activé. Détail: {e}")
        return False
