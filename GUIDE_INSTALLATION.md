# 🚆 Guide Universel d'Installation & Déploiement — CAMRAIL RailMind Lite

> **Statut : Document de référence unique pour l'installation intégrale**  
> **Cible : Environnements Linux (Ubuntu/Debian) et Windows (Server/Desktop)**  
> **Architecture : 100 % Souverain, Local & Déconnecté (Air-Gapped)**

---

## 📑 Sommaire Général

1. [Principes d'Architecture & Conventions de Chemins](#1-principes-darchitecture--conventions-de-chemins)
2. [Inventaire Exhaustif des Poids, Modèles IA et Binaires Tiers](#2-inventaire-exhaustif-des-poids-modèles-ia-et-binaires-tiers)
3. [Étape 1 : Prérequis Système Fondamentaux](#3-étape-1--prérequis-système-fondamentaux)
   - [A. Python 3.12+](#a-python-312)
   - [B. Node.js 20+ / 22+ LTS](#b-nodejs-20--22-lts)
   - [C. PostgreSQL 16+ et pgvector](#c-postgresql-16-et-pgvector)
   - [D. Utilitaires OCR & PDF : Poppler et Tesseract](#d-utilitaires-ocr--pdf--poppler-et-tesseract)
4. [Étape 2 : Moteur LLM Local — Ollama & Téléchargement des Poids](#4-étape-2--moteur-llm-local--ollama--téléchargement-des-poids)
5. [Étape 3 : Modèle d'Embedding Sémantique — Téléchargement & Emplacement](#5-étape-3--modèle-dembedding-sémantique--téléchargement--emplacement)
6. [Étape 4 : Configuration des Variables d'Environnement (.env)](#6-étape-4--configuration-des-variables-denvironnement-env)
   - [Les 3 Profils Matériels Prédéfinis (A, B, C)](#les-3-profils-matériels-prédéfinis-a-b-c)
   - [Dictionnaire des Variables Critiques](#dictionnaire-des-variables-critiques)
7. [Étape 5 : Initialisation de la Base de Données (Alembic & Seed)](#7-étape-5--initialisation-de-la-base-de-données-alembic--seed)
8. [Étape 6 : Démarrage du Backend FastAPI](#8-étape-6--démarrage-du-backend-fastapi)
9. [Étape 7 : Installation & Démarrage du Frontend Next.js](#9-étape-7--installation--démarrage-du-frontend-nextjs)
10. [Étape 8 : Déploiement Conteneurisé Clé en Main (Docker Compose)](#10-étape-8--déploiement-conteneurisé-clé-en-main-docker-compose)
11. [Procédure de Transfert 100 % Hors-Ligne (Serveur Air-Gapped)](#11-procédure-de-transfert-100--hors-ligne-serveur-air-gapped)
12. [Guide de Dépannage & Erreurs Fréquentes](#12-guide-de-dépannage--erreurs-fréquentes)

---

## 1. Principes d'Architecture & Conventions de Chemins

### A. Souveraineté et Étancheité Réseau
RailMind Lite est conçu pour respecter les contraintes strictes de confidentialité de **CAMRAIL** :
- **Zéro appel cloud externe** : Aucun flux réseau sortant vers OpenAI, Google, Anthropic ou Hugging Face en production.
- **Inférence 100 % locale** : Génération textuelle opérée par **Ollama** et vectorisation sémantique opérée par **SentenceTransformers** depuis des fichiers locaux.
- **Circuit fermé (Air-Gapped)** : Le système fonctionne sans connexion Internet active une fois les modèles et dépendances installés.

### B. Conventions de Chemins d'Accès
Les chemins d'installation varient d'une machine à l'autre (utilisateurs différents, lettres de disques `C:`, `D:`, arborescences `/home/` ou `/opt/`).  
Dans ce guide :
- `<racine_projet>` désigne le dossier racine où le code source est déposé.
  - *Exemple Linux :* `/opt/camrail/railmind` ou `~/camrail-main`
  - *Exemple Windows :* `D:\camrail-main` ou `C:\Projets\camrail`
- Chaque section présente les commandes **Linux (Bash)** et **Windows (PowerShell / CMD)** côte-à-côte.

---

## 2. Inventaire Exhaustif des Poids, Modèles IA et Binaires Tiers

Voici le tableau de synthèse des éléments externes à installer, leur raison d'être, leur taille et leur emplacement précis :

| Composant | Rôle dans RailMind Lite | Taille | Emplacement Cible (Linux) | Emplacement Cible (Windows) | Commande de Test / Validation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ollama (Binaire)** | Moteur d'inférence LLM local exécutant les modèles de langage | ~100 Mo | `/usr/local/bin/ollama` | `C:\Users\<user>\AppData\Local\Programs\Ollama` | `ollama --version` |
| **Poids LLM `llama3.2:3b`** | Modèle de langage générant les réponses argumentées de l'assistant | ~2.0 Go | `/usr/share/ollama/.ollama/models/` ou `~/.ollama/models/` | `%USERPROFILE%\.ollama\models\` | `ollama list` |
| **Modèle d'Embedding `multilingual-e5-small`** | Vectorisation des documents et requêtes (384 dimensions) | ~450 Mo | `<racine_projet>/backend/models/multilingual-e5-small/` | `<racine_projet>\backend\models\multilingual-e5-small\` | Présence des fichiers `model.safetensors` et `tokenizer.json` |
| **Poppler (`poppler-utils`)** | Découpage des PDF en pages individuelles et génération de vignettes | ~30 Mo | `/usr/bin/pdftoppm` | Dossier choisi + ajouté au `PATH` (ex: `C:\Program Files\poppler\Library\bin`) | `pdftoppm -v` |
| **Tesseract OCR** | Reconnaissance optique de texte sur les scans ou documents numérisés | ~50 Mo | `/usr/bin/tesseract` | `C:\Program Files\Tesseract-OCR\tesseract.exe` | `tesseract --version` |
| **Fichier `fra.traineddata`** | Dictionnaire linguistique français pour l'OCR Tesseract | ~15 Mo | `/usr/share/tesseract-ocr/5/tessdata/fra.traineddata` | `C:\Program Files\Tesseract-OCR\tessdata\fra.traineddata` | `tesseract --list-langs` (doit afficher `fra`) |
| **Extension `pgvector`** | Permet à PostgreSQL d'indexer et rechercher des vecteurs (index HNSW) | ~5 Mo | Extension installée dans le cluster PostgreSQL | Extension compilée dans PostgreSQL | Requête SQL : `CREATE EXTENSION IF NOT EXISTS vector;` |

---

## 3. Étape 1 : Prérequis Système Fondamentaux

### A. Python 3.12+

#### 🐧 Linux (Ubuntu / Debian) :
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev
python3 --version  # Doit être >= 3.12
```

#### 🪟 Windows :
1. Téléchargez l'installateur officiel Python 3.12+ x64 depuis [python.org](https://www.python.org/downloads/).
2. **Important :** Cochez impérativement la case **"Add python.exe to PATH"** lors de l'installation.
3. Vérifiez dans PowerShell :
```powershell
python --version
```

---

### B. Node.js 20+ / 22+ LTS

#### 🐧 Linux :
```bash
# Installation via NodeSource (version 22 LTS recommandée)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v
```

#### 🪟 Windows :
```powershell
# Option 1 : Via Winget
winget install OpenJS.NodeJS.22 --accept-package-agreements --accept-source-agreements

# Option 2 : Téléchargement manuel du .msi sur nodejs.org
# Vérification dans PowerShell :
node -v
npm -v
```

---

### C. PostgreSQL 16+ et pgvector

RailMind Lite utilise PostgreSQL pour le stockage transactionnel et l'extension `pgvector` pour l'indexation sémantique HNSW des chunks de documents.

#### 🐧 Linux :
```bash
sudo apt install -y postgresql postgresql-contrib
# Installation de pgvector (paquet officiel PostgreSQL)
sudo apt install -y postgresql-16-pgvector

# Démarrage du service
sudo systemctl enable --now postgresql

# Création de la base et de l'utilisateur
sudo -u postgres psql -c "CREATE USER camrail_user WITH PASSWORD 'camrail_secure_password';"
sudo -u postgres psql -c "CREATE DATABASE camrail_rda OWNER camrail_user;"
sudo -u postgres psql -d camrail_rda -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 🪟 Windows :
1. Installez PostgreSQL 16+ via l'installateur officiel EDB.
2. Téléchargez la release de `pgvector` pour Windows correspondant à votre version de PostgreSQL (ex: release GitHub `pgvector/pgvector`).
3. Copiez :
   - `vector.dll` dans `C:\Program Files\PostgreSQL\16\lib\`
   - `vector.control` et `vector--*.sql` dans `C:\Program Files\PostgreSQL\16\share\extension\`
4. Dans `psql` (ou pgAdmin) :
```sql
CREATE DATABASE camrail_rda;
\c camrail_rda;
CREATE EXTENSION IF NOT EXISTS vector;
```

---

### D. Utilitaires OCR & PDF : Poppler et Tesseract

#### 🐧 Linux :
```bash
# Poppler pour la découpe de documents PDF
sudo apt install -y poppler-utils

# Tesseract OCR et son modèle linguistique français
sudo apt install -y tesseract-ocr tesseract-ocr-fra

# Vérification :
pdftoppm -v
tesseract --list-langs  # Doit lister 'fra' et 'eng'
```

#### 🪟 Windows :

1. **Poppler :**
   - Téléchargez l'archive binaire `poppler-windows` (depuis GitHub releases `oschwartz10612/poppler-windows`).
   - Décompressez-la dans un dossier fixe, par exemple : `C:\Program Files\poppler`.
   - Ajoutez le dossier `C:\Program Files\poppler\Library\bin` à votre variable d'environnement système `PATH`.
   - Testez dans un **nouveau** terminal PowerShell : `pdftoppm -v`.

2. **Tesseract OCR :**
   - Téléchargez l'installateur Windows `tesseract-ocr-w64-setup` (UB-Mannheim).
   - Lors de l'installation, cochez le composant de données linguistiques additionnelles : **French (`fra.traineddata`)**.
   - Si le modèle français n'a pas été coché, téléchargez `fra.traineddata` depuis le dépôt GitHub `tesseract-ocr/tessdata` et déposez-le dans :  
     `C:\Program Files\Tesseract-OCR\tessdata\fra.traineddata`
   - Ajoutez `C:\Program Files\Tesseract-OCR` au `PATH`, ou déclarez son chemin dans le fichier `.env` :
     ```env
     TESSERACT_CMD_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
     ```

---

## 4. Étape 2 : Moteur LLM Local — Ollama & Téléchargement des Poids

### Pourquoi installer Ollama et ses poids ?
Ollama est le moteur d'inférence qui exécute localement le Grand Modèle de Langage (LLM). Il lit les fragments de documents retrouvés par la recherche sémantique et rédige la réponse structurée en français pour l'agent CAMRAIL, **sans jamais envoyer de données à l'extérieur**.

### A. Installation d'Ollama

#### 🐧 Linux :
```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
```

#### 🪟 Windows :
Téléchargez et exécutez l'installateur officiel : [https://ollama.com/download/windows](https://ollama.com/download/windows).  
Ollama démarre automatiquement en tâche de fond (icône dans la barre des tâches).

---

### B. Téléchargement du Modèle LLM

Exécutez dans votre terminal :
```bash
# Modèle standard recommandé pour RailMind Lite (compromis parfait rapidité/qualité) :
ollama pull llama3.2:3b

# Si vous disposez d'un serveur puissant ou avec GPU (Profil C) :
ollama pull llama3.1:8b
```

### C. Où sont stockés les poids téléchargés ?
Ollama stocke les tenseurs binaires dans un dossier système :
- **Linux :** `/usr/share/ollama/.ollama/models` (ou `~/.ollama/models`)
- **Windows :** `%USERPROFILE%\.ollama\models` (généralement `C:\Users\<VotreUtilisateur>\.ollama\models`)

### D. Vérification :
```bash
ollama list
# Doit afficher :
# NAME            ID              SIZE      MODIFIED
# llama3.2:3b     a80c4f17acd5    2.0 GB    ...
```

---

## 5. Étape 3 : Modèle d'Embedding Sémantique — Téléchargement & Emplacement

### Pourquoi installer le modèle d'embedding ?
Le modèle d'embedding (SentenceTransformer) convertit chaque paragraphe documentaire et chaque question en un vecteur mathématique de 384 dimensions. C'est ce qui permet au moteur de retrouver instantanément la bonne procédure même si l'utilisateur formule sa question avec des mots différents.

### A. Emplacement Cible
Le dossier cible est défini par la variable `MODELS_DIR` dans le fichier `.env` :
```text
<racine_projet>/backend/models/multilingual-e5-small/
```
Ce dossier doit contenir les fichiers suivants :
- `model.safetensors` (ou `pytorch_model.bin`) — Poids des neurones
- `tokenizer.json`, `tokenizer_config.json`, `vocab.txt` — Vocabulaire multilingue
- `config.json`, `modules.json` — Configuration d'architecture

---

### B. Téléchargement Automatisé via le script fourni

Depuis la racine du projet, exécutez :

#### 🐧 Linux :
```bash
cd <racine_projet>/backend
source venv/bin/activate
python scripts/prepare_models.py
```

#### 🪟 Windows (PowerShell) :
```powershell
cd <racine_projet>\backend
.\venv\Scripts\Activate.ps1
python scripts\prepare_models.py
```

Le script télécharge automatiquement `intfloat/multilingual-e5-small` et l'enregistre dans `<racine_projet>/backend/models/multilingual-e5-small`.  
Une fois le téléchargement terminé, l'application est configurée avec `TRANSFORMERS_OFFLINE=1` et `HF_HUB_OFFLINE=1` : **aucun accès Internet ne sera plus jamais sollicité**.

---

## 6. Étape 4 : Configuration des Variables d'Environnement (.env)

### A. Les 3 Profils Matériels Prédéfinis

Pour adapter RailMind Lite aux capacités de votre serveur sans configuration manuelle fastidieuse, 3 profils sont préconfigurés dans `backend/env-profiles/` :

| Profil | Cible Matérielle | RAM Conseillée | Modèle LLM | Concurrence simultanée | Workers Backend |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Profil A** | Machine bureautique / CPU modeste (Core i3/i5) | 8 Go | `llama3.2:3b` | 1 à 3 requêtes | 1 worker |
| **Profil B** | Serveur d'entreprise CPU (Xeon / Core i7-i9, 8-16 cœurs) | 16 à 32 Go | `llama3.2:3b` | 5 à 15 requêtes | 2 à 3 workers |
| **Profil C** | Serveur dédié avec carte graphique (GPU NVIDIA RTX/A-Series) | 32 à 64 Go | `llama3.1:8b` | 15 à 30 requêtes | 4 workers |

#### Activation du profil choisi :

##### 🐧 Linux :
```bash
cd <racine_projet>
python backend/scripts/select_profile.py B  # Active le profil B (recommandé en production)
```

##### 🪟 Windows (PowerShell) :
```powershell
cd <racine_projet>
python backend\scripts\select_profile.py B
```

---

### B. Dictionnaire des Variables Critiques (`backend/.env`)

Le fichier `backend/.env` contient la configuration du backend. Ajustez les variables suivantes selon votre infrastructure :

```env
# ==========================================
# BASE DE DONNÉES POSTGRESQL
# ==========================================
# Format : postgresql://<utilisateur>:<mot_de_passe>@<hote>:<port>/<nom_base>
DATABASE_URL=postgresql://camrail_user:camrail_secure_password@localhost:5432/camrail_rda
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# ==========================================
# SÉCURITÉ & AUTHENTIFICATION
# ==========================================
# Générez une clé secrète aléatoire : openssl rand -hex 32
SECRET_KEY=9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f
ACCESS_TOKEN_EXPIRE_MINUTES=480

# ==========================================
# MODÈLES IA LOCAUX (AIR-GAPPED)
# ==========================================
# Chemin relatif ou absolu vers le dossier des modèles
MODELS_DIR=./models
EMBEDDING_MODEL=multilingual-e5-small

# Moteur LLM Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=120

# ==========================================
# URLs PUBLIQUES & SÉCURITÉ CORS
# ==========================================
# Remplacer "localhost" par l'IP ou le nom DNS du serveur CAMRAIL
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
FRONTEND_URL=http://localhost:3000
API_PUBLIC_URL=http://localhost:8000
```

---

### C. Configuration du Frontend (`frontend/camrail-rda/.env.local`)

Dans `frontend/camrail-rda/.env.local` :
```env
# URL de l'API Backend accessible depuis le navigateur client
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Activer ou désactiver le bouton SSO Microsoft (true / false)
NEXT_PUBLIC_MICROSOFT_SSO_ENABLED=false
```

---

## 7. Étape 5 : Initialisation de la Base de Données (Alembic & Seed)

Une fois PostgreSQL configuré et accessible avec `DATABASE_URL` :

### 1. Appliquer les migrations de schéma et index vectoriels HNSW :

#### 🐧 Linux :
```bash
cd <racine_projet>/backend
source venv/bin/activate
alembic upgrade head
```

#### 🪟 Windows :
```powershell
cd <racine_projet>\backend
.\venv\Scripts\Activate.ps1
alembic upgrade head
```

### 2. Injecter les données de démonstration et comptes utilisateurs initiaux :

#### 🐧 Linux :
```bash
python seed_demo.py
```

#### 🪟 Windows :
```powershell
python seed_demo.py
```

Cette commande initialise :
- **Compte Super-Administrateur :** `admin@camrail.net` / `AdminCamrail2026!`
- **Compte Gestionnaire Documentaire :** `doc.admin@camrail.net` / `DocAdmin2026!`
- **Compte Agent d'Exploitation :** `agent.exploitation@camrail.net` / `Agent2026!`
- **5 documents techniques ferroviaires de référence** indexés avec leurs extraits vectoriels.

---

## 8. Étape 6 : Démarrage du Backend FastAPI

### Option 1 : Mode Développement Manuel (avec rechargement à chaud)

#### 🐧 Linux :
```bash
cd <racine_projet>/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 🪟 Windows (PowerShell) :
```powershell
cd <racine_projet>\backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

### Option 2 : Mode Production Multi-Workers (Hautes Performances)

Ce mode lance plusieurs processus Uvicorn parallèles pour absorber la charge de centaines d'utilisateurs simultanés :

#### 🐧 Linux :
```bash
cd <racine_projet>
chmod +x scripts/start_server.sh
./scripts/start_server.sh
```

#### 🪟 Windows :
Double-cliquez sur `scripts\start_server.bat` ou lancez dans l'invite de commande :
```cmd
cd <racine_projet>
scripts\start_server.bat
```

> **Validation :** Ouvrez votre navigateur sur **http://localhost:8000/docs** pour vérifier que l'API Swagger s'affiche.

---

## 9. Étape 7 : Installation & Démarrage du Frontend Next.js

### A. Installation des dépendances Node.js

#### 🐧 Linux :
```bash
cd <racine_projet>/frontend/camrail-rda
npm install
```

#### 🪟 Windows (PowerShell) :
```powershell
cd <racine_projet>\frontend\camrail-rda
npm install
```

---

### B. Mode Développement

#### 🐧 Linux & 🪟 Windows :
```bash
npm run dev
```
L'application est immédiatement accessible sur **http://localhost:3000**.

---

### C. Mode Production (Optimisé & Haute Vitesse)

En production, compilez les bundles statiques avec Turbopack pour des performances maximales :

#### 🐧 Linux & 🪟 Windows :
```bash
npm run build
npm run start -- -p 3000
```

---

## 10. Étape 8 : Déploiement Conteneurisé Clé en Main (Docker Compose)

Si votre serveur CAMRAIL dispose de **Docker** et **Docker Compose**, le déploiement est entièrement automatisable :

```bash
cd <racine_projet>

# 1. Copier les variables d'environnement
cp env.example .env

# 2. Construire et lancer l'ensemble des conteneurs
docker compose up -d --build

# 3. Vérifier l'état des conteneurs (db, backend, frontend)
docker compose ps
```

---

## 11. Procédure de Transfert 100 % Hors-Ligne (Serveur Air-Gapped)

Dans le cas où le serveur final de CAMRAIL n'a **aucun accès Internet** :

### Étape 1 : Sur une machine connectée (votre poste de travail)
1. **Cloner le projet** et installer les dépendances.
2. **Télécharger le modèle Ollama :**
   ```bash
   ollama pull llama3.2:3b
   ```
3. **Archiver le dossier des modèles Ollama :**
   - *Linux :* `tar -czvf ollama_models.tar.gz -C ~/.ollama models`
   - *Windows (PowerShell) :* `Compress-Archive -Path "$env:USERPROFILE\.ollama\models" -DestinationPath "ollama_models.zip"`
4. **Préparer les modèles d'embedding :**
   ```bash
   python backend/scripts/prepare_models.py
   ```
   (Cela peuple le dossier `backend/models/multilingual-e5-small`).
5. **Télécharger les packages Python (wheels) :**
   ```bash
   pip download -r backend/requirements.txt -d ./python_wheels
   ```
6. **Copier l'ensemble** sur un support amovible sécurisé (clé USB ou disque externe).

---

### Étape 2 : Sur le serveur isolé CAMRAIL
1. **Copier les fichiers du projet** à l'emplacement cible (ex: `/opt/camrail/railmind` ou `D:\camrail`).
2. **Restaurer les modèles Ollama :**
   - *Linux :* `sudo tar -xzvf ollama_models.tar.gz -C /usr/share/ollama/.ollama/`
   - *Windows :* Décompresser `ollama_models.zip` dans `C:\Users\<CompteSession>\.ollama\models`
3. **Installer les packages Python hors-ligne :**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # ou .\venv\Scripts\Activate.ps1 sous Windows
   pip install --no-index --find-links=../python_wheels -r requirements.txt
   ```
4. **Initialiser la base et lancer** les serveurs selon les sections 7, 8 et 9.

---

## 12. Guide de Dépannage & Erreurs Fréquentes

| Symptôme / Message d'erreur | Cause Probable | Solution Immédiate |
| :--- | :--- | :--- |
| `'uvicorn' n'est pas reconnu...` | L'environnement virtuel Python n'est pas activé dans le terminal. | Sous Windows : `.\venv\Scripts\Activate.ps1`. Sous Linux : `source venv/bin/activate`. |
| `'npm' n'est pas reconnu...` | Le dossier de Node.js n'est pas dans la variable `PATH` de Windows. | Vérifiez l'installation de Node.js ou lancez `node -v` pour diagnostiquer. |
| `HTTP 503 : Le modèle LLM local (Ollama) est indisponible` | Le service Ollama n'est pas démarré ou le modèle n'a pas été téléchargé. | Lancez Ollama (`ollama serve` ou démarrez l'application Windows) et vérifiez `ollama list`. |
| `fe_sendauth: no password supplied` ou erreur de connexion DB | Identifiants incorrects dans `DATABASE_URL` du fichier `.env`. | Vérifiez le mot de passe et le port (5432) dans `backend/.env`. |
| `extension "vector" is not available` | L'extension pgvector n'a pas été compilée ou activée dans PostgreSQL. | Exécutez `CREATE EXTENSION vector;` avec l'utilisateur postgres après avoir installé le paquet `postgresql-16-pgvector`. |
| `pdftoppm: command not found` | Poppler n'est pas installé ou absent du `PATH`. | Sous Linux : `sudo apt install poppler-utils`. Sous Windows : installez `poppler-windows` et ajoutez le dossier `bin` au `PATH`. |
| Avertissement d'infobulle de confiance insuffisante | L'assistant estime que les documents internes ne répondent pas avec certitude à la question. | Comportement normal de protection contre les hallucinations. Cliquez sur **Reformuler** ou enrichissez la base documentaire. |

---

*Document maintenu par l'équipe technique CAMRAIL — RailMind Lite v2.0.*
