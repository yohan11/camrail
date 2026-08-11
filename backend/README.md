# CAMRAIL RailMind Lite - Backend

## Démarrage Rapide pour la Démo (Local)

### 1. Prérequis
- **Python 3.12+**
- **PostgreSQL** avec l'extension `pgvector` activée (ou utilisez Docker).
- **Ollama** installé localement avec le modèle par défaut téléchargé (`llama3.2:3b` ou celui défini dans `.env`).
- *(Optionnel)* **Tesseract OCR** pour démontrer le fallback OCR.

### 2. Commandes de lancement
Exécutez ces commandes dans l'ordre à la racine du dossier `backend` :

```bash
# 1. Configurer l'environnement (Ajuster DATABASE_URL si besoin)
cp env.example .env

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Mettre à jour la base de données (Schémas)
alembic upgrade head

# 4. Préparer l'environnement de démo (Création des comptes et documents)
python seed_demo.py

# 5. Lancer l'API
uvicorn app.main:app --reload
```

L'API est maintenant disponible sur `http://localhost:8000` et la documentation interactive sur `http://localhost:8000/docs`.

### 3. Comptes de Démo

Ces comptes sont automatiquement créés par le script de reset :

- **Administrateur (Vue globale)** :
  - Email : `admin@camrail.net`
  - Mot de passe : `adminpassword`
- **Gestionnaire Documentaire (Vue globale)** :
  - Email : `docadmin@camrail.net`
  - Mot de passe : `docadminpassword`
- **Utilisateur Standard (Restreint au département "Formation")** :
  - Email : `readonly@camrail.net`
  - Mot de passe : `readonlypassword`

---

## 🚨 BOUTON PANIQUE : Reset Rapide 🚨

En cas de problème pendant la répétition ou la démo (données corrompues, documents supprimés par erreur), voici la séquence magique pour repartir d'un environnement propre en 30 secondes :

**Si vous utilisez PostgreSQL localement :**
```bash
dropdb railmind && createdb railmind && alembic upgrade head && python seed_demo.py
```

**Si vous utilisez Docker Compose :**
```bash
docker compose down -v && docker compose up -d && docker compose exec api python seed_demo.py
```

---

## Déploiement avec Docker Compose (Optionnel)

Si vous préférez lancer l'API et la base de données via Docker :

> **Note :** Ollama n'est pas conteneurisé pour préserver l'accélération GPU. L'API Docker communiquera avec votre Ollama local via `host.docker.internal:11434`.

```bash
docker compose up -d
docker compose logs -f api
```
