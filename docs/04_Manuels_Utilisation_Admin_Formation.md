# Manuels Utilisateur, Administrateur et Guide Formateur

Ce document compile les instructions nécessaires pour utiliser et administrer RailMind Lite, ainsi que le guide d'acculturation à destination des formateurs CAMRAIL.

---

## 1. Manuel Utilisateur (Interface et Navigation)

L'utilisation de RailMind Lite est conçue pour être aussi simple qu'une conversation, favorisant ainsi son utilisation quotidienne par l'ensemble du personnel.

### 1.1 Se connecter
- Rendez-vous sur la page d'accueil de l'application.
- **Utilisateurs standards :** Cliquez sur le bouton "Se connecter avec Microsoft" pour utiliser vos identifiants d'ordinateur (SSO), ou entrez votre adresse email et votre mot de passe si la connexion classique est requise.

### 1.2 Poser une question à l'Assistant IA
- Dans le menu latéral (Sidebar), cliquez sur **Nouvelle conversation**.
- Au centre de l'écran, saisissez votre question dans la barre de recherche (ex: *"Quelle est la procédure en cas de retard d'un train fret ?"*).
- **Lire la réponse et vérifier les sources :**
  L'intelligence artificielle rédige sa réponse. Juste en dessous, vous verrez des encarts (Citations) indiquant le titre du document source et la page exacte. Vous pouvez cliquer dessus pour approfondir.

### 1.3 Comprendre le niveau de confiance
RailMind Lite évalue lui-même la qualité de sa réponse :
- **Vert (Confiance élevée) :** L'IA a trouvé le texte exact dans les documents.
- **Jaune (Confiance moyenne) :** L'IA a dû croiser des mots-clés ou le texte n'était pas parfaitement explicite.
- **Rouge (Information insuffisante) :** L'IA s'abstient de répondre car vos documents autorisés ne contiennent pas la réponse.

### 1.4 Consulter l'historique
Dans la barre latérale gauche (Sidebar), vos anciennes conversations sont listées sous la section **Historique**. Cliquez sur n'importe quel titre pour restaurer le contexte exact de votre discussion passée.

---

## 2. Manuel Administrateur

Le panneau d'administration est réservé aux profils `Admin` et `Document Admin`. Il permet de garantir la fiabilité de la base de connaissances.

### 2.1 Gestion Documentaire
- Allez dans l'onglet **Documents**.
- **Ajout d'un document :** Cliquez sur "Téléverser" et sélectionnez un PDF. 
  *Note sur les doublons :* Le système vérifiera l'empreinte mathématique du fichier (Hash). S'il a déjà été téléversé, l'action sera refusée pour éviter de polluer la recherche de l'IA.
- **Activation :** Tout nouveau document est en statut *Indexé*. Vous devez l'éditer et le passer en *Actif* pour qu'il soit utilisé par l'IA.
- **Catégorisation et Sécurité :** Attribuez le document au bon département et aux groupes de sécurité appropriés. Cette étape est cruciale pour le cloisonnement des informations.

### 2.2 Surveiller l'Audit et la Traçabilité
- Allez dans l'onglet **Tableau de Bord (Dashboard)**.
- Le widget **Sécurité & Audit** vous affiche le journal d'activité (qui s'est connecté, qui a téléchargé quel document, et l'horodatage précis).

---

## 3. Manuel Formateur (Acculturation à l'IA)

Ce module est destiné aux formateurs internes de CAMRAIL pour accompagner le changement lors du déploiement de RailMind Lite.

### Module 1 : Comprendre RailMind Lite
- **L'objectif :** Expliquer que RailMind n'est pas "ChatGPT" ni un moteur de recherche internet. C'est un assistant métier strictement limité aux procédures internes de CAMRAIL.

### Module 2 : Poser une bonne question
- **La règle d'or :** Soyez précis. 
- *Mauvais exemple :* "Retard de train."
- *Bon exemple :* "Quelles sont les obligations légales de communication aux passagers si un train voyageur a un retard de plus de 30 minutes ?"

### Module 3 : Comprendre et vérifier les sources
- Former les employés à ne pas faire une confiance aveugle à la machine. La responsabilité finale appartient à l'humain.
- La bonne pratique : Toujours lire la citation affichée en bas de la réponse pour s'assurer du contexte.

### Module 4 : Comprendre les limites de l'IA
- L'IA ne peut pas deviner une information manquante. 
- L'IA ne fait pas de calculs mathématiques complexes ni de prédictions, elle restitue de l'information documentée.
- Expliquer le badge rouge "Information insuffisante". Ce n'est pas un bug, c'est une sécurité anti-hallucination.

### Module 5 : Sécurité et confidentialité
- Assurer le personnel que leurs questions restent en interne (traitement local ou API d'entreprise sécurisée).
- Rappeler que le système filtre automatiquement les documents : ce qu'un employé ne doit pas voir ne lui sera jamais révélé par l'IA.
