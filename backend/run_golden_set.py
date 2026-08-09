import json
import time
import os
import sys

from app.database import SessionLocal
from app.models.schemas import Document
from app.services.retrieval import hybrid_search

def run_golden_set():
    print("=" * 70)
    print("      RAILMIND LITE - GOLDEN SET EVALUATION")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Check if enough documents exist
        doc_count = db.query(Document).filter(Document.status == "active").count()
        if doc_count < 2:
            print(f"ATTENTION: Pas assez de documents indexés pour évaluer le golden set correctement. (Nombre actuel: {doc_count})")
            print("Veuillez d'abord exécuter run_test_search.py ou uploader des documents via l'API.")
            return

        with open("golden_set.json", "r", encoding="utf-8") as f:
            golden_set = json.load(f)

        total_questions_with_answer = 0
        successful_questions = 0
        total_latency_ms = 0
        latencies = []

        print("\n[Évaluation des questions avec réponse attendue]")
        for item in golden_set:
            if not item.get("expected_document_title"):
                continue
                
            total_questions_with_answer += 1
            query = item["question"]
            expected_title = item["expected_document_title"]
            
            start_time = time.perf_counter()
            results = hybrid_search(db=db, query=query, top_k=5)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            total_latency_ms += duration_ms
            latencies.append(duration_ms)
            
            # Check if expected document is in top 5
            found = False
            for rank, res in enumerate(results, start=1):
                if expected_title.lower() in res["document_title"].lower():
                    found = True
                    break
            
            if found:
                successful_questions += 1
                print(f" [SUCCÈS] {query[:50]}... (Trouvé dans le top-5)")
            else:
                print(f" [ÉCHEC]  {query[:50]}... (Non trouvé)")

        print("\n[Évaluation des questions SANS réponse attendue (abstention)]")
        for item in golden_set:
            if item.get("expected_document_title"):
                continue
                
            query = item["question"]
            start_time = time.perf_counter()
            results = hybrid_search(db=db, query=query, top_k=5)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            total_latency_ms += duration_ms
            latencies.append(duration_ms)
            
            top_score = results[0]["score"] if results else 0.0
            print(f" [INFO] Requête hors-sujet: {query[:50]}... -> Score max retourné: {top_score:.4f}")

        # Summary
        if total_questions_with_answer > 0:
            success_rate = (successful_questions / total_questions_with_answer) * 100
            avg_latency = total_latency_ms / len(golden_set)
            latencies.sort()
            p95_index = int(len(latencies) * 0.95) - 1
            p95_latency = latencies[max(0, p95_index)]
            
            print("\n" + "=" * 70)
            print("                       RÉSUMÉ FINAL")
            print("=" * 70)
            print(f"Taux de succès : {successful_questions}/{total_questions_with_answer} questions avec réponse trouvées dans le top-5 ({success_rate:.1f}%)")
            print("  (Cible officielle à terme : > 85%)")
            print(f"Latence moyenne : {avg_latency:.0f} ms par requête")
            print(f"Latence p95     : {p95_latency:.0f} ms par requête (Cible < 1000 ms hors LLM)")
            print("=" * 70)

    except Exception as e:
        print(f"Erreur lors de l'exécution du golden set : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_golden_set()
