# Comparatif des Performances du Moteur RAG : Avant vs Après Optimisation

Ce rapport compare les métriques du moteur documentaire CAMRAIL RailMind Lite avant et après l'application du chantier d'optimisation (modèle d'embedding `intfloat/multilingual-e5-small`, batching, lazy loading, prompt direct 2-5 phrases, et seuil de confiance recalibré).

---

## 1. Tableau Synthétique Avant / Après

| Indicateur | Baseline (MiniLM-L12-v2) | Après Optimisation (e5-small) | Évolution | Statut |
| :--- | :---: | :---: | :---: | :---: |
| **Taux de réussite retrieval (@ 5)** | **86.4%** (19/22) | **90.9%** (20/22) | **+4.5%** | 🟢 Progression |
| **MRR (Mean Reciprocal Rank)** | **0.773** | **0.848** | **+0.075** | 🟢 Progression |
| **Fidélité LLM (Faithfulness)** | **80.0%** | **100.0%** | **+20.0%** | 🟢 Progression |
| **Précision Preuve / Citations** | **100.0%** (3/3) | **100.0%** (3/3) | **0.0%** | 🟢 Maintien optimal |
| **Taux d'Abstention (Hors-sujet)** | **100.0%** (6/6) | **83.3%** (5/6) | **-16.7%** | 🟡 Analyse & Correctif ci-dessous |
| **Latence moyenne par requête** | **17.31 s** | **9.80 s** | **-43.4%** | 🟢 Gain majeur de vitesse |
| **Temps total Golden Set** | **484.53 s** (8m 04s) | **274.27 s** (4m 34s) | **-210.26 s** | 🟢 Réduction de 43% |

---

## 2. Analyse Détaillée des Évolutions

### A. Qualité de la Recherche Sémantique (Retrieval & MRR)
- **Modèle de recherche asymétrique :** L'ancien modèle `paraphrase-multilingual-MiniLM-L12-v2` était conçu pour la similarité phrase-à-phrase et limité à 128 tokens. Le nouveau modèle `intfloat/multilingual-e5-small` avec préfixes obligatoires (`query: ` et `passage: `) et fenêtre de 512 tokens capture fidèlement les chunks longs.
- **Top-1 Hits :** 18 des 22 questions métier retournent le document exact en **Rang 1** direct, faisant progresser le MRR de **0.773 à 0.848**.

### B. Latence et Efficacité CPU (i3, sans GPU)
- **Chargement paresseux (*Lazy Loading*) :** Les modules `indexing`, `retrieval` et `generation` démarrent instantanément sans bloquer le serveur.
- **Batching d'embeddings :** L'indexation traite tous les chunks d'un document en une seule passe matricielle (`embed_texts`).
- **Génération ciblée :** Le nouveau system prompt direct (2 à 5 phrases concises sans formules d'introduction telles que *"D'après les extraits"*) réduit drastiquement le nombre de tokens générés par Ollama sur CPU, faisant chuter la latence moyenne de **17.3s à 9.8s par requête**.

### C. Analyse de l'Indicateur d'Abstention (83.3%) et Correctif Proposé
- **Constat :** 5 questions hors-sujet sur 6 sont parfaitement rejetées dès le seuil de confiance vectoriel (Capitale de l'Australie, Gâteau au chocolat, Film de science-fiction, Pattes d'araignée, Tour Eiffel).
- Une seule question hors-sujet (*"Peux-tu me donner la recette de la tarte aux pommes ?"*) a produit une distance vectorielle de `0.1793` avec e5, passant juste sous le seuil `0.20`.
- **Analyse du compromis :** 
  - Si l'on durcit le seuil à `0.17`, l'abstention repasse à 100%, mais la rétention des questions métier légitimes chute à 63.6% (rejet de questions in-domain valides).
  - Le seuil `0.20` calibré via `scripts/calibrate_threshold.py` optimise le compromis F1-score (76.9%) avec 95.5% de rétention métier.
- **Correctif recommandé en production :**
  Ajouter un classificateur de domaine léger ou un filtre guardrail par mots-clés/intentions ferroviaires en amont du RAG pour rejeter immédiatement les requêtes culinaires ou non professionnelles sans dégrader le seuil vectoriel des questions techniques.

---

## 3. Reranker Optionnel (Cross-Encoder)
- Le reranker `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` a été implémenté avec lazy loading dans `app/services/retrieval.py` (`RERANKER_ENABLED = False`).
- Sur CPU modeste (i3), son activation réordonne les 15 premiers candidats au prix d'un surcoût de latence de **+1.5s à +2.5s** par requête.
- Il est désactivé par défaut conformément aux spécifications afin de préserver la réactivité maximale.

---

*Évaluation réalisée sur le Golden Set officiel de 28 requêtes (22 in-domain, 6 out-of-domain).*
