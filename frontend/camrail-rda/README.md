# CAMRAIL RailMind Lite - Interface Utilisateur (Frontend)

Interface web moderne pour l'assistant documentaire et la recherche intelligente CAMRAIL RailMind Lite.

> 📖 **Document de Référence Unique pour l'Installation** :  
> Pour la procédure complète et exhaustive d'installation et de déploiement (Windows & Linux, Node.js, variables d'environnement, démarrage dev & production), consultez le document maître **[GUIDE_INSTALLATION.md](../../GUIDE_INSTALLATION.md)** ou sa version PDF **[GUIDE_INSTALLATION.pdf](../../GUIDE_INSTALLATION.pdf)**.

## Caractéristiques Techniques
- **Framework** : Next.js 16 (App Router), React 19, TypeScript.
- **Styling** : TailwindCSS v4, thème corporate aux couleurs officielles de CAMRAIL (#d71920).
- **100% Autonome et Local** :
  - Aucune police Google Fonts distante (polices système et locales uniquement via `@fontsource-variable/inter`).
  - Aucun CDN externe pour les icônes ou les scripts.
  - Toutes les requêtes API s'adressent exclusivement au backend local configuré par `NEXT_PUBLIC_API_URL`.

## Démarrage Rapide

### 1. Configuration
Créez un fichier `.env.local` dans le dossier `frontend/camrail-rda` :
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
# Activer le micro pour la dictée vocale si autorisé par la DSI (désactivé par défaut) :
NEXT_PUBLIC_VOICE_INPUT_ENABLED=false
```

### 2. Installation et Lancement
```bash
# Installer les dépendances
npm install

# Démarrer le serveur de développement local
npm run dev
```

L'application est disponible sur [http://localhost:3000](http://localhost:3000).

## Fonctionnalités Clés de l'Interface
- **Assistant Conversationnel Streaming** : Interface temps réel avec Server-Sent Events (SSE), frappe adaptative, bouton « Arrêter » interactif (`AbortController`) et cartes de citations sourcées.
- **Gestion Complète des Conversations** : Historique latéral persistant avec sélection de session et bouton de **suppression directe** avec invite de confirmation.
- **Synthèse Vocale Locale (TTS)** : Écoute audio de la réponse générée via l'API locale du navigateur (`SpeechSynthesis`) avec assainissement des balises et numéros de citations.
- **Visualiseur Documentaire Dynamique** : Affichage haute fidélité page par page avec défilement automatique et surlignage visuel jaune via paramètres URL (`/documents/[id]?page=X&highlight=...`).
- **Gestion Documentaire RBAC** : Téléversement (PDF & DOCX), filtrage par département et groupes de sécurité, activation / archivage.
- **Mode Bilingue (Français / Anglais)** : Traduction instantanée locale de la conversation via le moteur Ollama.
