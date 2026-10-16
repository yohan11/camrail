# CAMRAIL - RailMind Lite

Bienvenue dans le dépôt du projet **RailMind Lite** développé pour CAMRAIL. Il s'agit d'un système de Retrieval-Augmented Generation (RAG) 100% local, souverain et sécurisé, permettant l'interrogation intelligente du corpus documentaire de CAMRAIL (procédures, sécurité, manuels d'exploitation, etc.).

---

## Confidentialité et Exécution 100% Locale

Conformément aux exigences strictes du cahier des charges de CAMRAIL :
- **Intelligence Artificielle Locale (Ollama)** : La génération de réponses s'effectue exclusivement en local via Ollama (`llama3.2:3b`). Aucun appel vers des API d'IA externes (Gemini, OpenAI, Anthropic) n'est effectué. En cas d'indisponibilité du service Ollama, une erreur 503 claire est renvoyée sans aucun repli externe.
- **Embeddings et Recherche Vectorielle Locaux** : Les représentations vectorielles (`intfloat/multilingual-e5-small`) et le reranker optionnel sont chargés directement depuis le dossier local `MODELS_DIR` (`./models`), avec interdiction absolue d'appels réseau (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`).
- **Souveraineté des Données** : Aucune donnée documentaire, aucune métadonnée et aucune requête utilisateur ne quitte le serveur.
- **Circuit Réseau Fermé (Air-Gapped)** : Le système ne réalise aucun appel réseau sortant en production (garanti et vérifié par tests automatisés sous monkeypatching strict).

### Préparation des Modèles Hors-Ligne
Avant de déployer sur un serveur de production isolé d'Internet :
1. **Modèles d'Embedding & Reranker** : Sur une machine connectée, exécutez une seule fois :
   ```bash
   python scripts/prepare_models.py
   ```
   Ce script télécharge les poids dans le dossier `backend/models`. Transférez ensuite ce dossier sur le serveur cible.
2. **Guide Complet d'Installation** : Consultez le document maître [GUIDE_INSTALLATION.md](GUIDE_INSTALLATION.md) pour le guide pas-à-pas (Windows & Linux, modèles, base de données, profils matériels et mode déconnecté).

---

## Architecture du Projet

Le dépôt est structuré en deux parties principales :

1. **[Backend (FastAPI)](backend/)**
   - **Rôle :** Moteur RAG, ingestion documentaire, base de données vectorielle (pgvector) et génération locale de réponses (Ollama).
   - **Stack :** Python 3.12+, FastAPI, SQLAlchemy, pgvector.
   - **Sécurité :** Contrôle d'accès basé sur les rôles (RBAC) et filtrage par département.

2. **[Frontend (Next.js)](frontend/camrail-rda/)**
   - **Rôle :** Interface utilisateur moderne pour interagir avec l'assistant, visualiser les documents et gérer les requêtes.
   - **Stack :** Next.js (App Router), React, TailwindCSS (100% local, aucun CDN ou police externe).

```mermaid
graph TD
    User([Utilisateur CAMRAIL]) --> Front[Frontend Next.js (Local)]
    Front --> API[Backend FastAPI (Local)]
    API --> DB[(PostgreSQL + pgvector)]
    API --> LLM((Ollama Local - llama3.2:3b))
```

---

## Démarrage Rapide

### 1. Démarrer le Backend
Consultez le [**README du backend**](backend/README.md) pour les instructions détaillées :

```bash
cd backend
cp env.example .env
pip install -r requirements.txt
python ../scripts/prepare_models.py
alembic upgrade head
python seed_demo.py
uvicorn app.main:app --reload
```

### 2. Démarrer le Frontend
Consultez le [**README du frontend**](frontend/camrail-rda/README.md) :

```bash
cd frontend/camrail-rda
npm install
npm run dev
```

L'application est accessible sur [http://localhost:3000](http://localhost:3000).

---

## Fonctionnalités Clés
- **Recherche Hybride Optimisée CPU** : Sémantique (vectorielle e5) et Lexicale avec fusion RRF.
- **Sécurité et Droits d'Accès** : Les résultats sont strictement filtrés selon les départements et les habilitations de l'agent.
- **Génération Documentaire avec Preuves** : Réponses factuelles avec citations claires, extraits exacts et score de confiance.
- **Résilience et Mode Déconnecté** : Déploiement sans Internet clé en main.

---

## Scalabilite, Resilience et Haute Concurrence (~1000 Utilisateurs)

Pour repondre aux exigences de production (5 a 15 generations simultanees et ~1000 utilisateurs quotidiens) :
- **Pool de Connexions DB :** Parametre via `DB_POOL_SIZE` (10), `DB_MAX_OVERFLOW` (20), `DB_POOL_TIMEOUT` (30), `pool_pre_ping=True` et `pool_recycle=1800`.
- **Decouplage Session DB :** Aucune connexion PostgreSQL n'est mobilisee pendant l'inference Ollama (fermeture de session avant le LLM et reouverture courte en post-traitement).
- **Index Vectoriel HNSW & Full-Text GIN :** Acceleration sub-milliseconde des requetes avec index HNSW (`m=16, ef_construction=64`) et `SET hnsw.ef_search = 64`.
- **Streaming SSE Temps Reel :** Endpoint `POST /api/v1/assistant/query/stream` emettant sequentiellement `sources` -> `token` -> `done`, avec bouton "Arreter" interactif (`AbortController`) et citations `[n]` cliquables.
- **Regulation & File d'Attente :** Semaphore limitant a `MAX_CONCURRENT_GENERATIONS` (4) les inferences paralleles, file d'attente avec timeout `QUEUE_TIMEOUT_SECONDS` (60s -> 503) et rate limiting glissant `RATE_LIMIT_PER_MINUTE` (10 req/min/user -> 429).
- **Cache Memoire LRU :** Mise en cache des embeddings des questions frequentes sans fuite inter-utilisateurs.
- **Sonde de Sante Publique :** Endpoint `GET /health` verifiant l'etat de la DB, d'Ollama et du modele d'embedding (200 / 503).
- **Deploiement Multi-Workers :** Scripts `scripts/start_server.sh` et `scripts/start_server.bat` avec gestion de la RAM.
- **Tests de Charge :** Suite Locust disponible dans `scripts/loadtest/` pour des scenarios a 10, 30 et 100 utilisateurs virtuels.
