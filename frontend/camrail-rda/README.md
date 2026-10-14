# CAMRAIL RailMind Lite - Interface Utilisateur (Frontend)

Interface web moderne pour l'assistant documentaire et la recherche intelligente CAMRAIL RailMind Lite.

## Caractéristiques Techniques
- **Framework** : Next.js 15 (App Router), React 19, TypeScript.
- **Styling** : TailwindCSS v4, thème corporate aux couleurs de CAMRAIL (#d71920).
- **100% Autonome et Local** :
  - Aucune police Google Fonts distante (polices système et locales uniquement).
  - Aucun CDN externe pour les icônes ou les scripts.
  - Toutes les requêtes API s'adressent exclusivement au backend local configuré par `NEXT_PUBLIC_API_URL`.

## Démarrage Rapide

### 1. Configuration
Créez un fichier `.env.local` dans le dossier `frontend/camrail-rda` :
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Installation et Lancement
```bash
# Installer les dépendances
npm install

# Démarrer le serveur de développement local
npm run dev
```

L'application est disponible sur [http://localhost:3000](http://localhost:3000).

## Fonctionnalités de l'Interface
- **Assistant Documentaire** : Interface conversationnelle avec suivi de session, affichage des citations précises et surlignage des extraits sources.
- **Visualiseur Documentaire** : Affichage page par page avec défilement automatique vers le passage pertinent cité par l'IA.
- **Gestion Documentaire** : Téléversement, filtrage par statut et département, contrôle d'accès.
- **Mode Bilingue (Français / Anglais)** : Traduction instantanée locale de la conversation via le moteur Ollama.
