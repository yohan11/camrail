# CAMRAIL RailMind Lite - Backend (100% Local, Souverain & Haute Concurrence)

Ce sous-projet contient l'API REST FastAPI de **RailMind Lite**, le moteur RAG documentaire souverain développé pour CAMRAIL.

> 📖 **Document de Référence Unique pour l'Installation** :  
> Pour la procédure complète, exhaustive et détaillée pas-à-pas (Windows & Linux côte à côte, gestion des poids d'embedding, Ollama, pgvector, Poppler, Tesseract OCR), consultez le document maître **[GUIDE_INSTALLATION.md](../GUIDE_INSTALLATION.md)** ou sa version PDF **[GUIDE_INSTALLATION.pdf](../GUIDE_INSTALLATION.pdf)**.

---

## 1. Caractéristiques d'Architecture

- **100 % Local & Souverain** : Aucune dépendance vers des API cloud externes (zéro appel sortant).
- **Moteur d'Embedding Local** : `intfloat/multilingual-e5-small` (384 dimensions) ou `BAAI/bge-m3` (1024 dimensions) stocké dans `MODELS_DIR`.
- **Moteur LLM Local (Ollama)** : `qwen2.5:3b` (**modèle de référence actif**, recommandé pour CAMRAIL en raison de sa fidélité au français technique et aux acronymes métiers) ou `llama3.2:3b` (alternatif léger).
- **Ingestion & Recherche RAG Hybride** :
  - Traitement PDF (Poppler + Tesseract OCR) et DOCX avec **pagination virtuelle** proportionnelle.
  - Recherche combinée dense (pgvector HNSW) et lexicale (GIN) avec fusion RRF.
  - Déduplication automatique des contenus identiques et service d'extraction de preuves contextuelles ([EvidenceExtractor](app/services/evidence.py)).
- **Haute Concurrence (~1000 utilisateurs quotidiens)** :
  - Découplage strict des sessions DB (zéro connexion occupée pendant l'inférence LLM).
  - Sémaphore de concurrence avec file d'attente temporisée (60s -> HTTP 503).
  - Rate Limiter glissant par utilisateur (10 requêtes/min -> HTTP 429).
  - Streaming temps réel Server-Sent Events (`POST /api/v1/assistant/query/stream`).
  - Déploiement multi-workers Uvicorn (`scripts/start_server.sh` et `.bat`).

---

## 2. Démarrage Rapide

### Étape 1 : Choisir et activer un profil matériel
Depuis la racine du projet ou du dossier `backend`, exécutez le sélecteur de profil :
```bash
# Sélection interactive ou directe (Profils A, B ou C)
python scripts/select_profile.py A
```
Le profil copiera la configuration optimale dans `backend/.env`.

### Étape 2 : Installer les dépendances Python
Dans un environnement virtuel Python 3.12+ :
```bash
cd backend
pip install -r requirements.txt
```

### Étape 3 : Télécharger le modèle LLM local
```bash
# Modèle de référence recommandé pour CAMRAIL :
ollama pull qwen2.5:3b

# Modèle alternatif standard :
ollama pull llama3.2:3b
```

### Étape 4 : Préparer les modèles d'embedding hors-ligne
```bash
python scripts/prepare_models.py
```

### Étape 5 : Initialiser la base de données PostgreSQL
Assurez-vous que PostgreSQL est démarré avec l'extension `pgvector` :
```bash
# Appliquer les migrations de schéma et index HNSW/GIN
alembic upgrade head

# Injecter les comptes et documents de démonstration
python seed_demo.py
```

### Étape 6 : Lancer le serveur backend
- **En mode développement (avec rechargement à chaud) :**
  ```bash
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```
- **En mode production multi-workers :**
  ```bash
  # Linux / macOS
  ../scripts/start_server.sh

  # Windows
  ..\scripts\start_server.bat
  ```

L'API est accessible sur `http://localhost:8000`, la documentation sur `http://localhost:8000/docs` et la sonde de santé sur `http://localhost:8000/health`.

---

## 3. Déploiement avec Docker Compose

Pour déployer la pile complète (PostgreSQL pgvector, Backend, Frontend et optionnellement Ollama) :
```bash
# Depuis la racine du projet
docker compose up -d

# Avec le conteneur Ollama inclus :
docker compose --profile ollama up -d
```

---

## 4. Comptes de Démonstration

> ⚠️ **AVERTISSEMENT** : Comptes créés par `seed_demo.py` pour l'évaluation interne.

| Rôle | Email | Mot de passe | Périmètre |
| :--- | :--- | :--- | :--- |
| **Administrateur** | `admin@camrail.net` | `adminpassword` | Accès global & supervision |
| **Gestionnaire Documentaire** | `docadmin@camrail.net` | `docadminpassword` | Téléversement & gestion |
| **Agent / Utilisateur Standard** | `readonly@camrail.net` | `readonlypassword` | Restreint au département Formation |

---

## 5. Changement de Modèle d'Embedding & Calibration

### Changer de modèle d'embedding (ex: bascule vers BGE-M3) :
```bash
python scripts/change_embedding_model.py --model BAAI/bge-m3 --dim 1024
```
Ce script modifie la colonne PostgreSQL via `ALTER TABLE`, recrée l'index HNSW et réindexe tous les documents actifs.

### Calibrer le seuil de confiance RAG :
Après tout changement de modèle, recalibrez le seuil :
```bash
python scripts/calibrate_threshold.py
```
Le résultat optimal est automatiquement enregistré dans `eval_results/calibration.json`.

---

## 6. Tests Automatisés

```bash
# Vérifier l'étanchéité et l'absence totale de trafic sortant
python -m unittest tests.test_no_outbound_network

# Vérifier la scalabilité, la résilience et les limites (503, 429, SSE, /health)
python -m unittest tests.test_scalability_and_resilience

# Vérifier la conformité des profils d'environnement
python -m unittest tests.test_profiles_config

# Exécuter les tests du moteur RAG
pytest tests/test_engine_optimization.py -v
```
