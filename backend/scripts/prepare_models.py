#!/usr/bin/env python3
"""
Script de préparation des modèles IA pour déploiement 100% hors-ligne (Air-Gapped).
À exécuter UNE FOIS sur une machine connectée à Internet avant transfert sur le serveur CAMRAIL.

Télécharge et sauvegarde :
1. Le modèle d'embedding (ex: intfloat/multilingual-e5-small)
2. Le modèle de reranking (si configuré / demandé)
dans le dossier MODELS_DIR local (ex: ./models).
"""

import os
import sys
import argparse
from pathlib import Path

# Ajouter backend au path pour importer la configuration
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.config import settings
    DEFAULT_MODELS_DIR = getattr(settings, "MODELS_DIR", "./models")
    DEFAULT_EMBEDDING_MODEL = getattr(settings, "EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    DEFAULT_RERANKER_MODEL = getattr(settings, "RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
except Exception as e:
    print(f"[AVERTISSEMENT] Impossible de charger app.config ({e}), utilisation des valeurs par défaut.")
    DEFAULT_MODELS_DIR = str(BACKEND_DIR / "models")
    DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
    DEFAULT_RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

def prepare_models(models_dir: str, embedding_model: str, reranker_model: str, include_reranker: bool = False):
    # Résoudre le chemin absolu
    if not os.path.isabs(models_dir):
        resolved_models_dir = os.path.abspath(os.path.join(str(BACKEND_DIR), models_dir))
    else:
        resolved_models_dir = models_dir

    os.makedirs(resolved_models_dir, exist_ok=True)
    print("=" * 70)
    print("  CAMRAIL RailMind Lite - Préparation des modèles hors-ligne")
    print("=" * 70)
    print(f"Dossier de destination : {resolved_models_dir}")
    print(f"Modèle d'embedding     : {embedding_model}")
    if include_reranker:
        print(f"Modèle de reranking    : {reranker_model}")
    print("=" * 70)

    # 1. Modèle d'embedding
    embedding_target = os.path.join(resolved_models_dir, embedding_model.split("/")[-1])
    print(f"\n[1/2] Téléchargement / Sauvegarde du modèle d'embedding dans : {embedding_target}")
    from sentence_transformers import SentenceTransformer
    
    # Autoriser le téléchargement pour la préparation
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    
    model = SentenceTransformer(embedding_model)
    model.save(embedding_target)
    print(f"  -> Modèle d'embedding sauvegardé avec succès dans : {embedding_target}")

    # 2. Modèle de reranking (optionnel ou si configuré)
    if include_reranker:
        reranker_target = os.path.join(resolved_models_dir, reranker_model.split("/")[-1])
        print(f"\n[2/2] Téléchargement / Sauvegarde du modèle de reranking dans : {reranker_target}")
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder(reranker_model)
        reranker.save(reranker_target)
        print(f"  -> Modèle de reranking sauvegardé avec succès dans : {reranker_target}")
    else:
        print("\n[2/2] Reranker non demandé (RERANKER_ENABLED=False par défaut).")

    print("\n" + "=" * 70)
    print("  SUCCÈS : Tous les modèles locaux sont prêts pour le mode 100% hors-ligne.")
    print(f"  Vous pouvez maintenant transférer le dossier '{resolved_models_dir}' vers le serveur.")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Préparer les modèles pour exécution 100% locale sans Internet.")
    parser.add_argument("--models-dir", default=DEFAULT_MODELS_DIR, help="Dossier de destination des modèles")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="Identifiant du modèle d'embedding")
    parser.add_argument("--reranker-model", default=DEFAULT_RERANKER_MODEL, help="Identifiant du modèle de reranking")
    parser.add_argument("--include-reranker", action="store_true", help="Télécharger également le reranker")
    args = parser.parse_args()

    prepare_models(args.models_dir, args.embedding_model, args.reranker_model, args.include_reranker)

if __name__ == "__main__":
    main()
