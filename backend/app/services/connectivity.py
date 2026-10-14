"""
Module de connectivité : le système CAMRAIL fonctionne en mode 100% souverain et local.
Aucune requête externe n'est émise.
"""

def is_online(timeout_seconds: float = 2.0) -> bool:
    """Retourne toujours False : exécution 100% locale sans appel externe."""
    return False
