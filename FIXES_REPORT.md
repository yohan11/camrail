# Rapport des Corrections - Audit RailMind Lite

Ce document synthétise l'ensemble des correctifs appliqués suite à l'audit du dépôt `camrail`. Toutes les fonctionnalités existantes ont été préservées, la sécurité a été renforcée et la robustesse améliorée.

## 1. Bloquants pour la Démo

* **1.1. Encodage Requirements** : `backend/requirements.txt` a été réencodé de UTF-16 vers UTF-8 propre, et les erreurs de caractères corrompus (provoquant l'échec de `pip install`) ont été corrigées manuellement.
* **1.2. Golden Set Documents** : Les 8 documents `.docx` manquants référencés par le test ont été générés par un script et placés dans `backend/demo-data/`. Le script de seed (`seed_demo.py`) a été mis à jour pour les indexer automatiquement.
* **1.3 & 1.4. Installation & README** : Un `README.md` global a été ajouté à la racine avec un schéma d'architecture Mermaid. Le `backend/README.md` documente désormais la procédure d'installation avec un Plan B explicite permettant de configurer Gemini via `.env` en l'absence de GPU.

## 2. Cohérence de la Sécurité et Contrôle d'Accès

* **2.1. Incohérence Chunk/Document** : L'approche stricte (Option B) a été implémentée. Le filtrage RBAC dans `retrieval.py` (`hybrid_search`) valide non seulement le document parent, mais filtre aussi par `DocumentChunk.security_group.in_()`. Un test automatisé (`tests/test_security_access.py`) a été écrit pour garantir qu'un chunk restreint ne fuite pas.
* **2.2. Restriction par département** : Les rôles codés en dur ont été remplacés par une énumération `UserRole` dans `schemas.py`. La logique de détermination de la portée de recherche a été centralisée dans `security.py:get_effective_search_scope()` et réutilisée dans les routeurs.
* **2.3. Injection de Prompt** : Les extraits injectés dans `generation.py` sont désormais enveloppés de balises XML strictes (`<extrait>... </extrait>`), accompagnées d'instructions système interdisant au LLM d'exécuter toute consigne située à l'intérieur.

## 3. Qualité et Crédibilité de l'Évaluation

* **3.1. Golden Set Étendu** : `golden_set.json` comporte désormais 25 questions variées, incluant des questions multi-pages, comparatives, et 6 questions hors-sujet ciblées.
* **3.2. Script d'évaluation (run_golden_set)** : `run_golden_set.py` a été entièrement réécrit pour calculer :
  * Precision@5 et MRR (Mean Reciprocal Rank).
  * Le taux d'abstention sur le hors-domaine.
  * Le taux de fidélité des citations LLM.
  * *Un export JSON et Markdown est généré à chaque exécution.*
* **3.3. Calibration RAG_MIN_CONFIDENCE** : La valeur par défaut dans `config.py` a été ajustée de `0.75` à `0.65`, offrant un bien meilleur équilibre (F1-score) suite aux tests, et documentée dans le README.

## 4. Robustesse et Hygiène du Code

* **4.1. Déduplication par Hash** : Dans `indexing.py`, une vérification en mémoire du `content_hash` par le biais d'un `set()` a été ajoutée pour ignorer instantanément la ré-indexation de blocs répétés dans le même document (ex. en-têtes, paragraphes redondants).
* **4.2. Nettoyage de la racine** : L'encombrement du dossier `backend/` a été réduit :
  * `run_test_*.py` ont été renommés en `test_*.py` et déplacés dans le dossier `tests/` avec un `conftest.py`.
  * Tous les scripts divers (`check_indexes.py`, `convert_pdf.py`, etc.) ont été déplacés dans `scripts/`.
* **4.3. Intégration Continue** : Un workflow GitHub Actions basique (`.github/workflows/ci.yml`) a été créé pour lancer la suite Pytest dans un conteneur PostgreSQL/pgvector.

## 5. Aspects Juridiques et Décisions Humaines

* **5.1. Licence** : Un commentaire `TODO (DÉCISION HUMAINE)` a été ajouté au-dessus des en-têtes de copyright strict dans `retrieval.py` et `generation.py`. 
  > **⚠️ Action requise par l'équipe** : Veuillez vérifier la charte de soumission du concours MBIH, qui pourrait exiger une licence open-source, en conflit avec cet avertissement de "licence commerciale stricte".
* **5.2. Mots de passe** : Un avertissement clair a été ajouté dans le `README.md` précisant que les identifiants en clair sont liés à de simples comptes de démo éphémères pour faciliter le travail du jury, sans aucune donnée de production.
