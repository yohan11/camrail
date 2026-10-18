#!/usr/bin/env bash
# ==============================================================================
# CAMRAIL RailMind Lite - Génération de Certificat SSL/TLS Auto-Signé de Test
# ==============================================================================
# Ce script génère une paire de clés (certificat X.509 et clé privée RSA 2048)
# pour le développement local et la validation du profil HTTPS Nginx.
#
# UTILISATION EN PRODUCTION AVEC UNE AUTORITÉ INTERNE CAMRAIL (PKI / AD CS) :
# 1. En environnement de production ferroviaire, N'UTILISEZ PAS ce certificat auto-signé.
# 2. Faites émettre un certificat serveur officiel auprès de la PKI interne CAMRAIL :
#    - Nom de domaine (CN) : ex. railmind.camrail.net ou ip_serveur
#    - Déposez la clé privée serveur dans : deploy/certs/privkey.pem (chmod 600)
#    - Déposez la chaîne complète de certificats (certificat serveur + certificats
#      intermédiaires de l'autorité racine CAMRAIL) dans : deploy/certs/fullchain.pem
# 3. Assurez-vous que l'autorité racine CAMRAIL est bien installée dans le magasin
#    de certificats des postes de travail des agents ferroviaires pour éviter les
#    avertissements de sécurité du navigateur.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="$ROOT_DIR/deploy/certs"

mkdir -p "$CERTS_DIR"

echo "=============================================================================="
echo "  Génération du certificat auto-signé CAMRAIL RailMind Lite (Test/Dev)..."
echo "  Emplacement cible : $CERTS_DIR"
echo "=============================================================================="

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERTS_DIR/privkey.pem" \
    -out "$CERTS_DIR/fullchain.pem" \
    -subj "/C=CM/ST=Littoral/L=Douala/O=CAMRAIL/OU=Direction des Systemes d Information/CN=railmind.camrail.net" \
    -addext "subjectAltName=DNS:localhost,DNS:railmind.camrail.net,IP:127.0.0.1"

# Durcissement des permissions sur la clé privée
chmod 600 "$CERTS_DIR/privkey.pem"
chmod 644 "$CERTS_DIR/fullchain.pem"

echo ""
echo "[OK] Certificats générés avec succès :"
echo "  - Clé privée   : $CERTS_DIR/privkey.pem"
echo "  - Certificat   : $CERTS_DIR/fullchain.pem"
echo ""
echo "Note : Pour lancer Docker Compose en HTTPS avec Nginx :"
echo "  docker compose --profile https up -d"
