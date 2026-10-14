#!/usr/bin/env bash
# ==============================================================================
# CAMRAIL RailMind Lite - Script de Démarrage Multi-Workers en Production
# ==============================================================================
#
# NOTE IMPORTANTE SUR LA GESTION DE LA MÉMOIRE RAM :
# Chaque processus worker Uvicorn charge son propre modèle d'embedding SentenceTransformer
# en mémoire vive (environ 400 Mo de RAM par worker) et maintient son propre pool
# de connexions SQLAlchemy vers PostgreSQL.
#
# Dimensionnement recommandé selon la RAM du serveur :
#   - 2 workers (défaut) : ~800 Mo à 1.2 Go de RAM totale allouée au backend.
#   - 4 workers          : ~1.6 Go à 2.4 Go de RAM totale.
#
# Pour modifier le nombre de workers, définissez UVICORN_WORKERS dans votre environnement
# ou dans le fichier .env (ex: export UVICORN_WORKERS=4).
# ==============================================================================

set -e

# Se positionner dans le dossier backend
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR/backend"

# Charger les variables d'environnement si .env existe
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

UVICORN_WORKERS="${UVICORN_WORKERS:-2}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "=============================================================================="
echo "  Démarrage de CAMRAIL RailMind Lite Backend avec $UVICORN_WORKERS workers"
echo "  Écoute sur http://$HOST:$PORT"
echo "=============================================================================="

# Vérification préalable des modèles hors-ligne
python ../scripts/prepare_models.py

# Démarrage du serveur ASGI multi-workers
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --workers "$UVICORN_WORKERS"
