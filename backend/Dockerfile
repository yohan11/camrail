# ==============================================================================
# CAMRAIL RailMind Lite - Backend Dockerfile Durci (Non-Root, Multi-Workers)
# ==============================================================================
# Image officielle Python 3.12 slim épinglée (vérifiée le 2026-10-18)
FROM python:3.12.7-slim

WORKDIR /app

# Installation minimale des dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Création de l'utilisateur non-root 'app' (UID 1001)
RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --gid 1001 --no-create-home app

# Copie de l'ensemble du code source
COPY . .

# Préparation des répertoires pour l'exécution non-root
RUN mkdir -p /app/storage /app/models /tmp && \
    chown -R app:app /app /tmp

USER app

# Lancement des migrations de base de données puis démarrage du serveur Uvicorn avec prise en compte des reverse-proxies
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${TRUSTED_PROXIES:-*}\""]
