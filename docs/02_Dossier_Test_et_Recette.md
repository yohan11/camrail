# Dossier de Test & Recette : RailMind Lite

## 1. Objet du document
Ce dossier définit les tests de recette de RailMind Lite. Il valide le bon fonctionnement de l'authentification, la recherche RAG, la gestion des sources, les droits, la déduplication et l'historique. La gestion du roulement du personnel est explicitement hors périmètre.

## 2. Matrice des Tests de Validation

L'ensemble des tests ci-dessous ont été validés sur le système en développement (Août 2026).

| ID | Domaine | Action (Scénario de test) | Résultat attendu | Statut de Recette |
| :--- | :--- | :--- | :--- | :--- |
| **TR-01** | Connexion | Se connecter avec des identifiants valides | Session créée et accès accordé | ✅ Fonctionnel |
| **TR-02** | Sécurité | Ouvrir une route protégée sans être connecté | Accès refusé (Redirection ou Erreur 401) | ✅ Fonctionnel |
| **TR-03** | RAG | Poser une question connue | Réponse générée et fondée sur le document | ✅ Fonctionnel |
| **TR-04** | Abstention | Poser une question hors corpus | L'IA indique une "Information insuffisante" et s'abstient d'inventer | ✅ Fonctionnel |
| **TR-05** | Sources | Observer les citations sous une réponse | Seules les sources pertinentes ayant servi sont affichées | ✅ Fonctionnel |
| **TR-06** | Sources | Poser une question couverte par un seul document | Une seule source est affichée (Dédoublonnage des citations) | ✅ Fonctionnel |
| **TR-07** | Confiance | Poser une question sur un sujet non couvert | Le badge de confiance ne doit pas être « élevé » (Rouge/Insuffisant) | ✅ Fonctionnel |
| **TR-08** | Statut document | Interroger l'assistant sur un document inactif | Le document n'est pas utilisé par la recherche | ✅ Fonctionnel |
| **TR-09** | Activation | Activer un document puis rechercher | Le document devient instantanément disponible | ✅ Fonctionnel |
| **TR-10** | Droits | Poser la même question (Admin vs ReadOnly) | Chaque profil voit seulement la réponse issue des documents qui lui sont autorisés | ✅ Fonctionnel |
| **TR-11** | Admin | Faire une recherche globale | L'admin accède aux documents de toutes les directions | ✅ Fonctionnel |
| **TR-12** | Upload | Téléverser un PDF valide | Extraction, création des chunks, embeddings et indexation réussies | ✅ Fonctionnel |
| **TR-13** | Fichier vide | Téléverser un fichier non valide | Erreur contrôlée et rejet | ✅ Fonctionnel |
| **TR-14** | Doublon | Téléverser exactement le même fichier | Rejet de l'upload grâce à la vérification d'empreinte SHA-256 | ✅ Fonctionnel |
| **TR-15** | Recherche | Recherche par mot-clé spécifique | Document pertinent retrouvé (Recherche Lexicale) | ✅ Fonctionnel |
| **TR-16** | Sémantique | Poser une question formulée différemment du texte | Passage sémantiquement pertinent retrouvé (pgvector) | ✅ Fonctionnel |
| **TR-17** | LLM | Poser une question RAG | Réponse rapide générée par Gemini Flash Lite avec contexte local | ✅ Fonctionnel |
| **TR-18** | Historique | Se déconnecter puis se reconnecter | La conversation est conservée dans l'historique | ✅ Fonctionnel |
| **TR-19** | Historique | Cliquer sur une ancienne conversation | Le bon contexte et les messages précédents sont restaurés | ✅ Fonctionnel |
| **TR-20** | Responsive | Utiliser l'application sur un écran étroit | Interface utilisable sans cassure majeure (Tailwind CSS) | ✅ Fonctionnel |
| **TR-21** | KALATI | Vérifier le couplage du système documentaire | Le prototype reste autonome (L'absence de KALATI ne bloque pas l'outil) | ✅ Fonctionnel |
| **TR-22** | Audit | Consulter les traces depuis le tableau de bord | Les actions prévues (uploads, questions) sont traçables (ID, Date) | ✅ Fonctionnel |

## 3. Détails des points critiques validés

### 3.1 Dédoublonnage des documents (TR-14)
La déduplication a été confirmée en testant l'envoi de deux fichiers PDF identiques mais renommés différemment. Le système ne se fie pas au nom du fichier, mais génère un *checksum* unique lors de la lecture des octets du fichier. Le deuxième upload a été bloqué au niveau de la base de données, évitant ainsi l'indexation redondante.

### 3.2 Confidentialité croisée RAG / Profil (TR-10)
Un compte utilisateur avec le département "Ressources Humaines" (Read Only) a tenté de trouver une information technique via le chat. La base vectorielle, configurée pour appliquer un filtre de département et de sécurité avant même de calculer la pertinence, a retourné zéro résultat. Le LLM s'est donc abstenu de répondre, confirmant l'imperméabilité des données entre directions.

### 3.3 Abstention et Confiance (TR-04 & TR-07)
Testé en posant la question : *"Quelle est la recette de la tarte aux pommes ?"*
Résultat : L'IA répond qu'elle ne trouve pas l'information dans les documents indexés, et le niveau de confiance affiché est "Information insuffisante" (Badge Rouge). L'intégrité de l'assistant métier est ainsi garantie.
