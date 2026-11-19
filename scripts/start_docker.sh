#!/bin/bash
# ==============================================================================
# CAMRAIL RailMind Lite - Script de Déploiement Conteneurisé Clé en Main (Docker)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=============================================================================="
echo "  CAMRAIL RailMind Lite - Démarrage de la Pile Docker Compose"
echo "=============================================================================="

# 1. Vérification de la disponibilité de Docker
if ! command -v docker >/dev/null 2>&1; then
    echo "[ERREUR CRITIQUE] Docker n'est pas installé ou n'est pas dans le PATH."
    echo "Installez Docker : https://docs.docker.com/engine/install/"
    exit 1
fi

# 2. Préparation automatique des fichiers d'environnement
if [ ! -f "backend/.env" ]; then
    echo "[INFO] Création automatique de backend/.env à partir du modèle..."
    cp backend/.env.example backend/.env
fi

if [ ! -f "frontend/camrail-rda/.env.local" ] && [ -f "frontend/camrail-rda/.env.local.example" ]; then
    echo "[INFO] Création automatique de frontend/camrail-rda/.env.local..."
    cp frontend/camrail-rda/.env.local.example frontend/camrail-rda/.env.local
fi

# 3. Vérification des dossiers persistants
mkdir -p backend/storage/documents backend/models

# 4. Choix du profil
PROFILE_ARG=""
if [ "$1" = "https" ]; then
    echo "[INFO] Profil activé : HTTPS (Reverse-Proxy Nginx durci)..."
    PROFILE_ARG="--profile https"
elif [ "$1" = "full" ]; then
    echo "[INFO] Profil activé : Full (Nginx HTTPS + Service Ollama intégré)..."
    PROFILE_ARG="--profile ollama --profile https"
elif [ "$1" = "ollama" ]; then
    echo "[INFO] Profil activé : Ollama conteneurisé..."
    PROFILE_ARG="--profile ollama"
else
    echo "[INFO] Profil standard : Base de données pgvector + Backend FastAPI + Frontend Next.js"
fi

# 5. Lancement de la composition Docker
echo "[INFO] Construction et démarrage des conteneurs en arrière-plan..."
docker compose $PROFILE_ARG up -d --build

echo ""
echo "=============================================================================="
echo "  Déploiement Conteneurisé Réussi !"
echo "=============================================================================="
echo "  - Interface Web (Frontend) : http://localhost:3000"
echo "  - API Swagger (Backend)    : http://localhost:8000/docs"
echo "  - Vérification Santé       : http://localhost:8000/health"
if [ "$1" = "https" ] || [ "$1" = "full" ]; then
    echo "  - Accès Sécurisé HTTPS     : https://localhost"
fi
echo ""
echo "  Comptes de démonstration préconfigurés :"
echo "    * Administrateur : admin@camrail.net    / adminpassword"
echo "    * Doc Admin      : docadmin@camrail.net / docadminpassword"
echo ""
echo "  Commandes utiles :"
echo "    * Voir les logs        : docker compose logs -f"
echo "    * Arrêter les services : docker compose down"
echo "=============================================================================="

