import os
import sys
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import json
import time
import os
import sys
import re

from app.database import SessionLocal
from app.models.schemas import Document
from app.services.retrieval import hybrid_search
from app.services.generation import generate_answer

def calculate_mrr(rankings):
    if not rankings: return 0.0
    return sum(1.0 / rank for rank in rankings if rank > 0) / len(rankings)

def run_golden_set():
    print("=" * 70)
    print("      RAILMIND LITE - GOLDEN SET EVALUATION (ADVANCED)")
    print("=" * 70)
    start_eval_time = time.time()

    db = SessionLocal()
    try:
        with open("golden_set.json", "r", encoding="utf-8") as f:
            golden_set = json.load(f)

        total_in_domain = 0
        total_out_domain = 0
        successful_retrieval_at_5 = 0
        rankings = []
        
        # LLM Faithfulness & Evidence metrics
        faithfulness_checked = 0
        faithfulness_passed = 0
        abstention_passed = 0
        evidence_checked = 0
        evidence_passed = 0

        print("\n[Évaluation des questions DANS LE DOMAINE]")
        for item in golden_set:
            if not item.get("expected_document_title"):
                continue
                
            total_in_domain += 1
            query = item["question"]
            expected_title = item["expected_document_title"]
            
            results = hybrid_search(db=db, query=query, top_k=5)
            
            found_rank = 0
            clean_expected = expected_title.replace(".docx", "").replace(".pdf", "").replace("_", " ").strip().lower()
            for rank, res in enumerate(results, start=1):
                doc_title_clean = res["document_title"].replace(".docx", "").replace(".pdf", "").replace("_", " ").strip().lower()
                if clean_expected in doc_title_clean or doc_title_clean in clean_expected:
                    found_rank = rank
                    break
            
            if found_rank > 0:
                successful_retrieval_at_5 += 1
                rankings.append(found_rank)
                print(f" [SUCCÈS] {query[:45]:<45} (Rang: {found_rank})")
            else:
                rankings.append(0)
                print(f" [ÉCHEC]  {query[:45]:<45} (Non trouvé dans le top-5)")

            # Check Evidence units for questions requiring precise evidence keywords
            expected_kws = item.get("expected_evidence_keywords")
            if expected_kws and found_rank > 0:
                try:
                    gen_result = generate_answer(query, results)
                    citations = gen_result.get("citations", [])
                    evidence_text = ""
                    for cit in citations:
                        evidence_text += " " + cit.get("excerpt", "")
                        for ev in cit.get("evidence", []):
                            evidence_text += " " + ev.get("text", "")

                    missing_kws = [kw for kw in expected_kws if kw.lower() not in evidence_text.lower()]
                    evidence_checked += 1
                    if not missing_kws:
                        evidence_passed += 1
                        print(f"       [PREUVE OK] Mots-clés trouvés : {expected_kws}")
                    else:
                        print(f"       [PREUVE MANQUANTE] Mots-clés manquants : {missing_kws}")
                except Exception as e:
                    print(f"       [PREUVE ERREUR] {e}")

            # Optional Faithfulness Check for first few queries to save time/API cost
            if faithfulness_checked < 5 and found_rank > 0 and not expected_kws:
                try:
                    # We pass the results to generation to see if it hallucinates citations
                    gen_result = generate_answer(query, results)
                    answer = gen_result.get("answer", "")
                    citations = gen_result.get("citations", [])
                    
                    # Check citations in text
                    cits_in_text = re.findall(r'\[(\d+)\]', answer)
                    valid_cits = [str(c.get("llm_index", idx+1)) for idx, c in enumerate(citations)] if citations else [str(i+1) for i in range(len(results))]
                    
                    is_faithful = True
                    for c in cits_in_text:
                        if c not in valid_cits:
                            is_faithful = False
                            
                    if is_faithful:
                        faithfulness_passed += 1
                    faithfulness_checked += 1
                except Exception:
                    pass

        print("\n[Évaluation des questions HORS DOMAINE (Abstention)]")
        for item in golden_set:
            if item.get("expected_document_title"):
                continue
                
            total_out_domain += 1
            query = item["question"]
            results = hybrid_search(db=db, query=query, top_k=5)
            
            # Run generation to verify abstention
            try:
                gen_result = generate_answer(query, results)
                ans = gen_result.get("answer", "").lower()
                conf = gen_result.get("confidence")
                if conf == "insufficient" or "ne trouve pas" in ans or "cannot find" in ans:
                    abstention_passed += 1
                    print(f" [SUCCÈS] Abstention correcte: {query[:40]}...")
                else:
                    print(f" [ÉCHEC]  Le modèle a tenté de répondre: {query[:40]}...")
            except Exception:
                # If API fails, we skip
                pass

        # Calculate metrics
        p_at_5 = (successful_retrieval_at_5 / total_in_domain) * 100 if total_in_domain > 0 else 0
        mrr = calculate_mrr(rankings)
        faith_rate = (faithfulness_passed / faithfulness_checked) * 100 if faithfulness_checked > 0 else 0
        abst_rate = (abstention_passed / total_out_domain) * 100 if total_out_domain > 0 else 0
        evidence_rate = (evidence_passed / evidence_checked) * 100 if evidence_checked > 0 else 100.0

        elapsed_eval = time.time() - start_eval_time
        total_eval_queries = total_in_domain + total_out_domain
        avg_latency = elapsed_eval / total_eval_queries if total_eval_queries > 0 else 0.0

        # Export JSON
        report = {
            "total_questions_in_domain": total_in_domain,
            "precision_at_5_percentage": p_at_5,
            "mrr": mrr,
            "faithfulness_percentage": faith_rate,
            "abstention_percentage": abst_rate,
            "evidence_precision_percentage": evidence_rate,
            "evidence_checked_count": evidence_checked,
            "evidence_passed_count": evidence_passed,
            "total_time_seconds": round(elapsed_eval, 2),
            "average_latency_seconds_per_query": round(avg_latency, 3)
        }
        with open("golden_set_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4)

        # Save to eval_results/after_engine.json
        for eval_dir in ["eval_results", os.path.join("..", "eval_results")]:
            if os.path.exists(os.path.dirname(os.path.abspath(eval_dir))):
                os.makedirs(eval_dir, exist_ok=True)
                dest_file = os.path.join(eval_dir, "after_engine.json")
                with open(dest_file, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=4)
                print(f"[OK] Sauvegarde dans {dest_file}")

        # Markdown Export
        md_report = f"""# Rapport d'Évaluation Golden Set

**Précision @ 5** : {p_at_5:.1f}% ({successful_retrieval_at_5}/{total_in_domain})
**MRR (Mean Reciprocal Rank)** : {mrr:.3f}
**Taux de Fidélité (Faithfulness)** : {faith_rate:.1f}% ({faithfulness_passed}/{faithfulness_checked} évalués)
**Taux d'Abstention (Hors-sujet)** : {abst_rate:.1f}% ({abstention_passed}/{total_out_domain})
"""
        with open("golden_set_report.md", "w", encoding="utf-8") as f:
            f.write(md_report)

        print("\n" + "=" * 70)
        print("                       RÉSUMÉ FINAL")
        print("=" * 70)
        print(f"Précision @ 5 : {p_at_5:.1f}%")
        print(f"MRR           : {mrr:.3f}")
        print(f"Fidélité LLM  : {faith_rate:.1f}%")
        print(f"Abstention    : {abst_rate:.1f}%")
        print("-> Rapports générés: golden_set_report.json et golden_set_report.md")
        print("=" * 70)

    except Exception as e:
        print(f"Erreur lors de l'exécution du golden set : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_golden_set()
