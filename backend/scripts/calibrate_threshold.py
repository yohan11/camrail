import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
#!/usr/bin/env python3
"""
Script de calibration automatique du seuil de confiance (RAG_MIN_CONFIDENCE).
Adapté au modèle multilingual-e5-small dont les similarités cosinus sont compressées.

Balaye RAG_MIN_CONFIDENCE sur le golden set (in-domain et out-of-domain / hors-sujet),
calcule la Précision, le Rappel et le F1-score de l'abstention,
affiche un tableau récapitulatif clair et recommande la valeur optimale.
Enregistre les résultats dans eval_results/calibration.json.
"""

import os
import sys
import json
import numpy as np

# Ensure backend root is on sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.database import SessionLocal
from app.services.retrieval import hybrid_search
from app.config import settings


def calibrate_threshold(golden_set_path: str = None, output_json_path: str = None):
    if golden_set_path is None:
        # Check standard locations
        candidates = [
            os.path.join(backend_root, "golden_set.json"),
            os.path.join(backend_root, "..", "golden_set.json"),
            "golden_set.json"
        ]
        for c in candidates:
            if os.path.exists(c):
                golden_set_path = c
                break

    if not golden_set_path or not os.path.exists(golden_set_path):
        raise FileNotFoundError(f"Fichier golden_set.json introuvable. Emplacements testés : {candidates}")

    if output_json_path is None:
        eval_dir = os.path.join(backend_root, "eval_results")
        os.makedirs(eval_dir, exist_ok=True)
        output_json_path = os.path.join(eval_dir, "calibration.json")

    print("=" * 80)
    print("      CALIBRATION DU SEUIL DE CONFIANCE RAG_MIN_CONFIDENCE")
    print(f"      Modèle d'embedding : {getattr(settings, 'EMBEDDING_MODEL', 'intfloat/multilingual-e5-small')}")
    print("=" * 80)

    with open(golden_set_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    db = SessionLocal()
    query_data = []

    print(f"\n[*] Évaluation des distances pour les {len(golden_set)} requêtes du Golden Set...")

    try:
        for idx, item in enumerate(golden_set, start=1):
            query = item["question"]
            is_out_domain = not bool(item.get("expected_document_title"))
            
            # Hybrid search with top_k=5
            results = hybrid_search(db=db, query=query, top_k=5)
            
            # Best vector distance among retrieved candidates
            if results and results[0].get("vector_distance") is not None:
                min_dist = float(results[0]["vector_distance"])
            else:
                # If no chunks retrieved or no distance, distance is max (1.0)
                min_dist = 1.0

            query_data.append({
                "index": idx,
                "question": query,
                "is_out_domain": is_out_domain,
                "min_vector_distance": min_dist,
                "top_result_title": results[0]["document_title"] if results else None
            })
            
            label_str = "HORS-DOMAINE" if is_out_domain else "IN-DOMAIN"
            print(f"  [{idx:2d}/{len(golden_set):2d}] [{label_str:12s}] Dist={min_dist:.4f} | Q: {query[:45]}")

    finally:
        db.close()

    total_queries = len(query_data)
    total_out_domain = sum(1 for q in query_data if q["is_out_domain"])
    total_in_domain = total_queries - total_out_domain

    print(f"\n[*] Total requêtes : {total_queries} (In-domain: {total_in_domain}, Hors-sujet: {total_out_domain})")

    # Sweep thresholds from 0.10 to 0.50 by step 0.01
    thresholds = [round(t, 3) for t in np.arange(0.10, 0.51, 0.01)]
    sweep_results = []

    best_threshold = None
    best_f1 = -1.0
    best_retention = -1.0
    best_stats = None

    print("\n" + "-" * 88)
    print(f"{'Seuil':>7} | {'TP':>4} | {'FP':>4} | {'FN':>4} | {'TN':>4} | {'Précision':>10} | {'Rappel':>8} | {'F1-Score':>8} | {'In-Domain Ret.':>14}")
    print("-" * 88)

    for T in thresholds:
        # A query triggers abstention if min_vector_distance >= T
        # Ground truth: Positive = is_out_domain (should abstain)
        # Negative = not is_out_domain (in-domain, should answer)
        tp = 0  # correctly abstained on out-of-domain
        fp = 0  # incorrectly abstained on in-domain
        fn = 0  # incorrectly answered out-of-domain
        tn = 0  # correctly answered in-domain

        for q in query_data:
            abstained = (q["min_vector_distance"] >= T)
            if q["is_out_domain"]:
                if abstained:
                    tp += 1
                else:
                    fn += 1
            else:
                if abstained:
                    fp += 1
                else:
                    tn += 1

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        in_domain_retention = (tn / (tn + fp)) if (tn + fp) > 0 else 0.0

        sweep_item = {
            "threshold": T,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "abstention_precision": round(precision, 4),
            "abstention_recall": round(recall, 4),
            "abstention_f1": round(f1, 4),
            "in_domain_retention": round(in_domain_retention, 4)
        }
        sweep_results.append(sweep_item)

        # Highlight candidates with high retention (>90%) and optimal F1
        # Recommendation criteria: maximize F1 with priority on in_domain_retention >= 90%
        if (f1 > best_f1) or (abs(f1 - best_f1) < 1e-4 and in_domain_retention > best_retention):
            # Only consider if retention is acceptable (>= 80%)
            if in_domain_retention >= 0.80:
                best_f1 = f1
                best_retention = in_domain_retention
                best_threshold = T
                best_stats = sweep_item

        # Print sampled rows or notable thresholds
        if round(T * 100) % 2 == 0 or T in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45):
            print(f"{T:7.2f} | {tp:4d} | {fp:4d} | {fn:4d} | {tn:4d} | {precision*100:9.1f}% | {recall*100:7.1f}% | {f1*100:7.1f}% | {in_domain_retention*100:13.1f}%")

    print("-" * 88)

    # Fallback if no threshold met the retention condition
    if best_threshold is None:
        best_stats = max(sweep_results, key=lambda x: x["abstention_f1"])
        best_threshold = best_stats["threshold"]
        best_f1 = best_stats["abstention_f1"]
        best_retention = best_stats["in_domain_retention"]

    print("\n" + "=" * 80)
    print("                      RECOMMANDATION FINALE")
    print("=" * 80)
    print(f"[*] Seuil optimal recommandé : RAG_MIN_CONFIDENCE = {best_threshold:.2f}")
    print(f"    - F1-Score Abstention    : {best_stats['abstention_f1']*100:.1f}%")
    print(f"    - Précision Abstention   : {best_stats['abstention_precision']*100:.1f}%")
    print(f"    - Rappel Abstention      : {best_stats['abstention_recall']*100:.1f}%")
    print(f"    - Rétention In-Domain    : {best_stats['in_domain_retention']*100:.1f}% ({best_stats['tn']}/{total_in_domain})")
    print("=" * 80)

    # Export to JSON
    calibration_data = {
        "embedding_model": getattr(settings, "EMBEDDING_MODEL", "intfloat/multilingual-e5-small"),
        "total_queries": total_queries,
        "total_in_domain": total_in_domain,
        "total_out_domain": total_out_domain,
        "recommended_threshold": best_threshold,
        "recommended_stats": best_stats,
        "sweep": sweep_results,
        "queries_detail": query_data
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(calibration_data, f, indent=4, ensure_ascii=False)

    print(f"\n[OK] Résultats sauvegardés dans : {output_json_path}")

    # Also save to root eval_results if backend root differs
    root_eval_dir = os.path.abspath(os.path.join(backend_root, "..", "eval_results"))
    if os.path.exists(os.path.dirname(root_eval_dir)):
        os.makedirs(root_eval_dir, exist_ok=True)
        root_json_path = os.path.join(root_eval_dir, "calibration.json")
        with open(root_json_path, "w", encoding="utf-8") as f:
            json.dump(calibration_data, f, indent=4, ensure_ascii=False)
        print(f"[OK] Copie synchronisée dans : {root_json_path}")

    return best_threshold, best_stats


if __name__ == "__main__":
    calibrate_threshold()
