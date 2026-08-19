import socket
import logging

logger = logging.getLogger(__name__)

def is_online(timeout_seconds: float = 2.0) -> bool:
    """
    Vérifie rapidement si la machine a un accès Internet actif.
    Ce test doit être RAPIDE (2 secondes max) car il est appelé avant chaque génération LLM.
    On effectue une simple résolution DNS et une connexion TCP vers Google.
    """
    try:
        # Essai de connexion TCP sur le port HTTPS de Google
        # socket.create_connection lance à la fois une résolution DNS et l'ouverture TCP.
        with socket.create_connection(("generativelanguage.googleapis.com", 443), timeout=timeout_seconds):
            return True
    except OSError as e:
        logger.warning(f"Test de connectivité échoué, passage en mode hors ligne. Détail: {e}")
        return False
