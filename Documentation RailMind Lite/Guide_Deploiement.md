# 🚆 CAMRAIL RailMind Lite - Guide Officiel de Déploiement en Production

> **Version : 2.0 (100% Souverain, Déconnecté & Multi-Profils)**  
> **Auteurs : Équipe Technique CAMRAIL**  
> Ce document constitue la référence exhaustive pour installer, configurer, sécuriser et exploiter **RailMind Lite** sur les infrastructures internes de CAMRAIL.

---

## 📑 Sommaire
1. [Architecture & Souveraineté 100% Locale](#1-architecture--souveraineté-100-locale)
2. [Prérequis Système & Utilitaires Tiers (Poppler & Tesseract)](#2-prérequis-système--utilitaires-tiers)
3. [Les 3 Profils Matériels d'Environnement](#3-les-3-profils-matériels-denvironnement)
4. [Préparation des Modèles en Mode Hors-Ligne](#4-préparation-des-modèles-en-mode-hors-ligne)
5. [Base de Données PostgreSQL & Indexation Sémantique](#5-base-de-données-postgresql--indexation-sémantique)
6. [Frontend Next.js & L'Avertissement Critique du Build](#6-frontend-nextjs--lavertissement-critique-du-build)
7. [Reverse Proxy Nginx & Sécurisation HTTPS](#7-reverse-proxy-nginx--sécurisation-https)
8. [Déploiement Multi-Workers & Docker Compose](#8-déploiement-multi-workers--docker-compose)
9. [Stratégie de Sauvegardes Automatisées (pg_dump)](#9-stratégie-de-sauvegardes-automatisées-pg_dump)
10. [Authentification Unique Microsoft Entra ID (Azure AD)](#10-authentification-unique-microsoft-entra-id-azure-ad)
11. [Checklist : Questions à poser à la DSI / Équipe IT de CAMRAIL](#11-checklist--questions-à-poser-à-la-dsi--équipe-it-de-camrail)

---

## 1. Architecture & Souveraineté 100% Locale

Le cahier des charges de CAMRAIL stipule une **étanchéité réseau absolue** :
- **Zéro appel cloud externe** : Aucun composant ne contacte d'API tierce (pas de Gemini, OpenAI, Claude ou HuggingFace Hub en production).
- **Inférence LLM locale** : Assurée exclusivement par le moteur local **Ollama** (`llama3.2:3b` ou `llama3.1:8b`).
- **Embeddings locaux** : Générés via `SentenceTransformer` depuis les fichiers locaux de `MODELS_DIR` (`multilingual-e5-small` ou `bge-m3`).
- **Protection des données ferroviaires** : Tout document téléversé, tout chunk et tout échange conversationnel reste confiné au serveur interne de CAMRAIL.

---

## 2. Prérequis Système & Utilitaires Tiers

### A. Spécifications minimales et recommandées
- **Système d'exploitation** : Ubuntu Server 22.04/24.04 LTS ou Windows Server 2019/2022.
- **Python** : 3.12+ (64-bit).
- **Node.js** : 20.x LTS ou supérieur.
- **PostgreSQL** : 16+ avec extension `pgvector` compilée.

### B. Outils OCR & Rendu PDF : Poppler et Tesseract
RailMind Lite extrait le texte brut, les métadonnées et effectue l'OCR sur les documents scannés :

1. **Poppler (`poppler-utils`) :** Indispensable pour la conversion page par page des PDF et la découpe d'extraits (`pdftoppm`, `pdfinfo`).
   - **Linux (Ubuntu/Debian) :**
     ```bash
     sudo apt-get update && sudo apt-get install -y poppler-utils
     ```
   - **Windows :**
     - Téléchargez les binaires Poppler for Windows (ex: release GitHub `oschwartz10612/poppler-windows`).
     - Extrayez l'archive dans `C:\Program Files\poppler`.
     - Ajoutez `C:\Program Files\poppler\Library\bin` à la variable d'environnement système `PATH`.

2. **Tesseract OCR :** Utilisé pour la reconnaissance optique des caractères sur les documents numérisés.
   - **Linux :**
     ```bash
     sudo apt-get install -y tesseract-ocr tesseract-ocr-fra
     ```
   - **Windows :**
     - Installez Tesseract via l'installateur officiel Windows (UB-Mannheim).
     - Installez le paquet linguistique français (`fra.traineddata`).
     - Ajoutez le dossier (ex: `C:\Program Files\Tesseract-OCR`) au `PATH`, ou spécifiez son chemin exact dans `.env` :
       ```env
       TESSERACT_CMD_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
       ```

---

## 3. Les 3 Profils Matériels d'Environnement

Le système dispose d'une gestion modulaire de configuration via 3 profils prédéfinis situés dans `backend/env-profiles/`.

| Profil | Cible Matérielle | RAM Recommandée | Inférence LLM | Concurrence | Workers |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Profil A (`profile-A-cpu.env`)** | CPU Modeste (Core i3 / PC bureautique) | 4 à 8 Go RAM | `llama3.2:3b` (ou 1b) | 1 à 3 users simultanés | 1 worker |
| **Profil B (`profile-B-cpu-puissant.env`)** | CPU Puissant (Xeon / Core i7-i9 / 8-16 cœurs) | 16 à 32 Go RAM | `llama3.2:3b` | 5 à 15 users simultanés | 3 workers |
| **Profil C (`profile-C-gpu.env`)** | Serveur GPU (NVIDIA RTX 3090/4090 ou A-Series) | 32 à 64 Go RAM + VRAM | `llama3.1:8b` | 15 à 30 users simultanés | 4 workers |

### Activation d'un profil :
Utilisez le script dédié :
```bash
python scripts/select_profile.py A
# ou pour le serveur CPU puissant :
python scripts/select_profile.py B
# ou pour le serveur avec GPU :
python scripts/select_profile.py C
```
Le script configure immédiatement `backend/.env` avec les paramètres adéquats (taille du pool DB, nombre de workers, concurrence max, modèles et timeouts).

---

## 4. Préparation des Modèles en Mode Hors-Ligne

Avant de basculer la machine en réseau isolé / DMZ interne :

1. **Poids d'Embedding (`prepare_models.py`) :**
   ```bash
   python scripts/prepare_models.py
   ```
   Ce script télécharge `intfloat/multilingual-e5-small` et prépare les structures de tokens dans `backend/models/`. En production, `HF_HUB_OFFLINE=1` et `TRANSFORMERS_OFFLINE=1` garantissent qu'aucune requête n'est émise vers l'extérieur.

2. **Modèles LLM Ollama :**
   ```bash
   # Sur la machine connectée :
   ollama pull llama3.2:3b
   # Si serveur GPU (Profil C) :
   ollama pull llama3.1:8b
   ```
   *(Pour un transfert vers un serveur 100% étanche sans Internet, consultez `scripts/prepare_ollama.md` pour la procédure d'export/import des blobs Ollama).*

---

## 5. Base de Données PostgreSQL & Indexation Sémantique

1. **Création de la base et extension :**
   ```sql
   CREATE DATABASE railmind;
   \c railmind;
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Migrations de schéma & Index HNSW/GIN :**
   ```bash
   cd backend
   alembic upgrade head
   ```
   Cette migration applique :
   - La table `document_chunks` avec colonne vectorielle dimensionnée selon `EMBEDDING_DIM` (384 par défaut).
   - L'index HNSW `ix_document_chunks_embedding_hnsw` (`m=16, ef_construction=64`).
   - L'index plein texte GIN `ix_document_chunks_search_vector`.

3. **Injection des données de démonstration :**
   ```bash
   python seed_demo.py
   ```

4. **Vérification de la Sonde de Santé (`/health`) :**
   Sans authentification requise, testez l'état opérationnel du système :
   ```bash
   curl -s http://localhost:8000/health
   ```
   Réponse attendue (HTTP 200) :
   ```json
   {
     "status": "healthy",
     "database": "ok",
     "ollama": "ok",
     "embedding_model": "ok"
   }
   ```
   *Si un composant est indisponible, l'endpoint renvoie HTTP 503 avec l'erreur correspondante.*

---

## 6. Frontend Next.js & L'Avertissement Critique du Build

> ⚠️ **AVERTISSEMENT FONDAMENTAL :**  
> Les variables préfixées par `NEXT_PUBLIC_*` (notamment `NEXT_PUBLIC_API_URL`) sont **compilées et figées en dur dans le code JavaScript au moment du build (`npm run build`)**.  
> **Conséquence :** Si vous modifiez l'adresse IP du serveur ou le nom de domaine de l'API dans `.env.local`, cela n'aura **AUCUN EFFET** en production tant que vous n'aurez pas relancé `npm run build` !

### Procédure de build frontend :
```bash
cd frontend/camrail-rda

# 1. Spécifier l'adresse publique d'accès à l'API backend
echo "NEXT_PUBLIC_API_URL=http://192.168.1.50:8000" > .env.local
# Ou si Nginx reverse proxy HTTPS est utilisé :
# echo "NEXT_PUBLIC_API_URL=https://railmind.camrail.net/api/v1" > .env.local

# 2. Compiler l'application pour la production
npm run build

# 3. Lancer le service frontend
npm run start -- -p 3000
```

---

## 7. Reverse Proxy Nginx & Sécurisation HTTPS

Pour un déploiement d'entreprise conforme aux normes CAMRAIL, installez un reverse proxy Nginx gérant les certificats SSL/TLS.

### Exemple de configuration Nginx (`/etc/nginx/sites-available/railmind.conf`) :
```nginx
server {
    listen 80;
    server_name railmind.camrail.net;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name railmind.camrail.net;

    ssl_certificate /etc/ssl/certs/camrail_wildcard.crt;
    ssl_certificate_key /etc/ssl/private/camrail_wildcard.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Taille max des documents téléversés (alignée sur MAX_UPLOAD_MB)
    client_max_body_size 50M;

    # 1. Frontend Next.js
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 2. Backend FastAPI & Streaming SSE
    location ~ ^/(api|docs|openapi.json|health) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Configuration critique pour le Streaming SSE (Server-Sent Events)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

---

## 8. Déploiement Multi-Workers & Docker Compose

### Option A : Déploiement Natif Multi-Workers
Chaque worker Uvicorn instancie son propre modèle d'embedding SentenceTransformer en mémoire (~400 Mo de RAM par worker) :
```bash
# Lancement sous Linux :
./scripts/start_server.sh

# Lancement sous Windows :
.\scripts\start_server.bat
```

### Option B : Déploiement Conteneurisé avec Docker Compose
Le fichier `docker-compose.yml` orchestre automatiquement PostgreSQL avec pgvector, le backend (avec healthcheck et migrations automatiques), le frontend et optionnellement Ollama :
```bash
# Démarrer la pile standard (DB + Backend + Frontend)
docker compose up -d

# Inclure également le conteneur Ollama managé
docker compose --profile ollama up -d
```

---

## 9. Stratégie de Sauvegardes Automatisées (pg_dump)

La perte de données documentaires ou conversationnelles est inacceptable. Mettez en place une sauvegarde quotidienne planifiée.

### Script de sauvegarde Linux (`/opt/railmind/backup.sh`) :
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/railmind"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"

# Sauvegarde compressée de la base de données
pg_dump -U railmind -h localhost -F c -b -v -f "$BACKUP_DIR/railmind_$TIMESTAMP.dump" railmind

# Sauvegarde des documents téléversés
tar -czf "$BACKUP_DIR/storage_$TIMESTAMP.tar.gz" -C /opt/railmind/backend storage

# Conservation des 30 derniers jours
find "$BACKUP_DIR" -type f -mtime +30 -delete
```

### Planification Cron :
```text
0 2 * * * /opt/railmind/backup.sh >> /var/log/railmind_backup.log 2>&1
```

### Procédure de Restauration :
```bash
pg_restore -U railmind -h localhost -d railmind -v "/var/backups/railmind/railmind_FICHIER.dump"
```

---

## 10. Authentification Unique Microsoft Entra ID (Azure AD)

Pour connecter RailMind Lite à l'annuaire d'entreprise CAMRAIL :
1. Sur le portail Azure Entra ID, inscrivez une nouvelle application : **"CAMRAIL RailMind Lite"**.
2. Déclarez l'URI de redirection Web :
   ```text
   https://railmind.camrail.net/api/v1/auth/callback/microsoft
   ```
3. Créez un secret client et notez l'ID client, le secret et l'ID de locataire (Tenant ID).
4. Renseignez ces valeurs dans votre fichier `.env` :
   ```env
   MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   MICROSOFT_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   MICROSOFT_TENANT_ID=common
   ```
5. Si ces variables sont vides, le SSO est formellement désactivé (erreur HTTP 503 explicite en production, aucun mock silencieux).

---

## 11. Checklist : Questions à poser à la DSI / Équipe IT de CAMRAIL

Avant l'installation définitive sur le serveur de production, validez impérativement les points suivants avec l'équipe informatique :

| N° | Domaine | Question Clé | Valeur Recommandée / Observation |
| :---: | :--- | :--- | :--- |
| **1** | **Accélération Matérielle** | Le serveur dispose-t-il d'un GPU NVIDIA ? Si oui, quel modèle et quelle quantité de VRAM ? | Idéal : RTX 3090/4090 ou A4000/A5000 (16-24 Go VRAM) pour le Profil C. Sinon : Profil B (CPU). |
| **2** | **Ressources VM (CPU & RAM)** | Combien de cœurs vCPU et quelle quantité de mémoire vive RAM sont alloués à la machine ? | Min : 8 Go (Profil A). Recommandé : 16 à 32 Go (Profil B). Idéal : 64 Go. |
| **3** | **Volume d'utilisateurs** | Quel est le nombre estimé d'utilisateurs connectés simultanément aux heures de pointe ? | Si 1 à 3 users -> Profil A. Si 5 à 15 users -> Profil B. Si > 15 users -> Profil C. |
| **4** | **Stockage Disque** | Quel espace disque est alloué pour PostgreSQL, les modèles et les documents téléversés ? | Minimum 100 Go SSD (dont ~15 Go pour les modèles Ollama et vecteurs). |
| **5** | **Réseau & FQDN** | Quel est le nom de domaine interne (FQDN) et l'adresse IP fixe attribués au serveur ? | Ex: `railmind.camrail.net` (nécessaire pour CORS, FRONTEND_URL et NEXT_PUBLIC_API_URL). |
| **6** | **Sécurité & Certificats HTTPS** | Disposez-vous d'un certificat SSL d'entreprise (Wildcard CAMRAIL ou Autorité Interne) ? | Requis pour déployer Nginx en HTTPS port 443 sans alertes de sécurité navigateur. |
| **7** | **Annuaire d'Entreprise** | L'organisation utilise-t-elle Microsoft Entra ID (Azure AD) ou un annuaire LDAP local ? | Pour obtenir le `MICROSOFT_CLIENT_ID` et autoriser le SSO des agents CAMRAIL. |
| **8** | **Plan de Sauvegarde DSI** | Un agent de sauvegarde centralisé (ex: Veeam, Commvault) sauvegarde-t-il la machine virtuelle ? | Définir l'emplacement où déposer le `pg_dump` pour inclusion dans la sauvegarde DSI. |
