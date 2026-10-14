#!/usr/bin/env python3
"""
Script de migration et de bascule du modèle d'embedding dans CAMRAIL RailMind Lite.
Usage :
    python scripts/change_embedding_model.py --model BAAI/bge-m3 --dim 1024 --yes
    python scripts/change_embedding_model.py --model intfloat/multilingual-e5-small --dim 384 --yes
"""

import os
import sys
import argparse
import json
from sqlalchemy import text

# Positionner le sys.path sur le backend
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir) if os.path.basename(script_dir) == "scripts" else script_dir
backend_dir = os.path.join(root_dir, "backend") if os.path.exists(os.path.join(root_dir, "backend")) else root_dir

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import settings
from app.database import engine, SessionLocal
from scripts.reindex_all import reindex_all_active_documents


KNOWN_MODELS = {
    "intfloat/multilingual-e5-small": {"dim": 384, "query_prefix": "query: ", "passage_prefix": "passage: "},
    "intfloat/multilingual-e5-base": {"dim": 768, "query_prefix": "query: ", "passage_prefix": "passage: "},
    "intfloat/multilingual-e5-large": {"dim": 1024, "query_prefix": "query: ", "passage_prefix": "passage: "},
    "BAAI/bge-m3": {"dim": 1024, "query_prefix": "", "passage_prefix": ""},
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": {"dim": 384, "query_prefix": "", "passage_prefix": ""}
}


def detect_dimension(model_name: str, models_dir: str) -> int:
    """Tente de détecter la dimension depuis le fichier config.json local ou le dictionnaire de modèles connus."""
    model_basename = model_name.split("/")[-1]
    candidates = [
        os.path.join(models_dir, model_basename, "config.json"),
        os.path.join(models_dir, model_name, "config.json"),
        os.path.join(models_dir, model_name.replace("/", "_"), "config.json")
    ]
    for cp in candidates:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if "hidden_size" in cfg:
                        return cfg["hidden_size"]
                    if "dim" in cfg:
                        return cfg["dim"]
            except Exception:
                pass

    if model_name in KNOWN_MODELS:
        return KNOWN_MODELS[model_name]["dim"]

    # Fallback par défaut
    return 384


def main():
    parser = argparse.ArgumentParser(description="Changement du modèle d'embedding RailMind Lite")
    parser.add_argument("--model", type=str, required=True, help="Nom ou chemin du modèle HuggingFace (ex: BAAI/bge-m3)")
    parser.add_argument("--dim", type=int, default=None, help="Dimension des vecteurs (auto-détectée si omise)")
    parser.add_argument("--query-prefix", type=str, default=None, help="Préfixe pour les requêtes utilisateur")
    parser.add_argument("--passage-prefix", type=str, default=None, help="Préfixe pour les passages de documents")
    parser.add_argument("-y", "--yes", action="store_true", help="Confirmation automatique sans invite interactive")
    args = parser.parse_args()

    model_name = args.model
    models_dir = getattr(settings, "MODELS_DIR", "./models")
    if not os.path.isabs(models_dir):
        models_dir = os.path.abspath(os.path.join(backend_dir, models_dir))

    # 1. Vérification de la dimension
    new_dim = args.dim or detect_dimension(model_name, models_dir)
    print("=" * 80)
    print(f"      CHANGEMENT DU MODÈLE D'EMBEDDING RAILMIND LITE")
    print(f"      Modèle cible : {model_name}")
    print(f"      Dimension     : {new_dim}")
    print("=" * 80)

    # 2. Avertissement et demande de confirmation
    if not args.yes:
        print("\n[!] ATTENTION : Cette opération va modifier le type de la colonne vectorielle")
        print("    'document_chunks.embedding' en base de données PostgreSQL, recréer l'index HNSW")
        print("    et relancer la réindexation de tous les documents actifs.")
        print("    Assurez-vous d'avoir sauvegardé la base au préalable (ex: pg_dump -U railmind railmind).")
        response = input("\nVoulez-vous continuer ? [o/N] : ").strip().lower()
        if response not in ("o", "oui", "y", "yes"):
            print("Opération annulée par l'administrateur.")
            sys.exit(0)

    # 3. Modification de la base de données (ALTER TABLE + Recréation Index HNSW)
    print("\n[*] Application des modifications de schéma en base de données...")
    try:
        with engine.begin() as conn:
            # PostgreSQL pgvector ALTER TYPE
            print(f"  -> Altération de la colonne 'document_chunks.embedding' vers vector({new_dim})...")
            conn.execute(text("SET statement_timeout = 60000;"))
            conn.execute(text(f"ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector({new_dim});"))
            
            print("  -> Suppression de l'ancien index HNSW...")
            conn.execute(text("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;"))
            
            print("  -> Recréation de l'index HNSW adapté à la nouvelle dimension...")
            conn.execute(text(f"""
                CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw 
                ON document_chunks USING hnsw (embedding vector_cosine_ops) 
                WITH (m=16, ef_construction=64);
            """))
            print("  -> Schéma PostgreSQL mis à jour avec succès.")
    except Exception as e:
        print(f"\n[!] ERREUR lors de la modification de la base : {e}")
        print("Vérifiez que la base PostgreSQL et l'extension pgvector sont bien démarrées.")
        sys.exit(1)

    # 4. Réindexation globale des documents
    print("\n[*] Lancement de la réindexation globale des documents actifs...")
    # Injecter temporairement les paramètres dans settings
    settings.EMBEDDING_MODEL = model_name
    settings.EMBEDDING_DIM = new_dim
    if args.query_prefix is not None:
        settings.EMBEDDING_QUERY_PREFIX = args.query_prefix
    elif model_name in KNOWN_MODELS:
        settings.EMBEDDING_QUERY_PREFIX = KNOWN_MODELS[model_name]["query_prefix"]
        
    if args.passage_prefix is not None:
        settings.EMBEDDING_PASSAGE_PREFIX = args.passage_prefix
    elif model_name in KNOWN_MODELS:
        settings.EMBEDDING_PASSAGE_PREFIX = KNOWN_MODELS[model_name]["passage_prefix"]

    reindex_res = reindex_all_active_documents()

    # 5. Rappel de calibration obligatoire
    print("\n" + "=" * 80)
    print("                      OPÉRATION TERMINÉE AVEC SUCCÈS")
    print("=" * 80)
    print(f"[*] Modèle actif     : {model_name} ({new_dim} dimensions)")
    print(f"[*] Documents traités: {reindex_res.get('processed_count', 0)}")
    print(f"[*] Chunks générés   : {reindex_res.get('total_chunks_created', 0)}")
    print("\n[⚠️ AVERTISSEMENT CRITIQUE]")
    print(f"Les propriétés de similarité cosinus de '{model_name}' diffèrent de l'ancien modèle.")
    print("Vous DEVEZ impérativement exécuter le script de calibration pour réajuster RAG_MIN_CONFIDENCE :")
    print("\n    python scripts/calibrate_threshold.py\n")
    print("N'oubliez pas également de mettre à jour votre fichier .env :")
    print(f"    EMBEDDING_MODEL={model_name}")
    print(f"    EMBEDDING_DIM={new_dim}")
    print(f"    EMBEDDING_QUERY_PREFIX={settings.EMBEDDING_QUERY_PREFIX}")
    print(f"    EMBEDDING_PASSAGE_PREFIX={settings.EMBEDDING_PASSAGE_PREFIX}")
    print("=" * 80)


if __name__ == "__main__":
    main()
