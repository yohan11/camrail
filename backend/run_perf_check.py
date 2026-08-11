import os
import json
import time
import numpy as np
from fastapi.testclient import TestClient
import warnings

from app.main import app
from app.database import SessionLocal

warnings.filterwarnings("ignore", category=DeprecationWarning)

def run_performance_check():
    print("=" * 60)
    print("       RAILMIND LITE - PERFORMANCE MEASUREMENTS")
    print("=" * 60)
    
    client = TestClient(app)
    
    # 1. Authenticate to get a token
    login_resp = client.post(
        "/auth/login",
        data={"username": "docadmin@camrail.net", "password": "docadminpassword"}
    )
    if login_resp.status_code != 200:
        print("ERROR: Failed to authenticate docadmin. Run seed_demo.py first.")
        return
        
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Load questions
    questions = [
        "Quelles sont les procédures de sécurité ?",
        "Comment faire la maintenance d'une locomotive ?",
        "Quelle est la durée minimale de repos ?",
        "Quel est le tarif pour Douala ?",
        "Comment gérer un incident sur la voie ?",
        "Quels sont les EPI obligatoires ?",
        "Procédure en cas de déraillement ?",
        "Règlementation du travail de nuit ?",
        "Chapitre sur le polymorphisme en Java",
        "Quelle est la vitesse limite d'un train fret ?"
    ]
    
    # --- PHASE 1: HYBRID SEARCH ONLY (/search) ---
    print(f"\n[PHASE 1] Measuring /search (Target: < 1000ms, {len(questions)} runs)")
    search_latencies = []
    
    for q in questions:
        start_time = time.time()
        resp = client.post("/search", headers=headers, json={"query": q})
        end_time = time.time()
        
        latency_ms = (end_time - start_time) * 1000
        search_latencies.append(latency_ms)
        
        if resp.status_code != 200:
            print(f"  Warning: Search failed for '{q}'")
            
    search_avg = np.mean(search_latencies)
    search_p95 = np.percentile(search_latencies, 95)
    
    # --- PHASE 2: LLM ASSISTANT (/assistant/query) ---
    assistant_questions = questions[:5]
    print(f"\n[PHASE 2] Measuring /assistant/query (Target: < 8000ms, {len(assistant_questions)} runs)")
    print("WARNING: If Ollama runs on CPU, expect this to be severely over the target (e.g. 30s-90s)!")
    assistant_latencies = []
    
    for i, q in enumerate(assistant_questions):
        print(f"  -> Run {i+1}/{len(assistant_questions)}: '{q}' (Waiting for Ollama...)")
        start_time = time.time()
        resp = client.post("/assistant/query", headers=headers, json={"query": q})
        end_time = time.time()
        
        latency_ms = (end_time - start_time) * 1000
        assistant_latencies.append(latency_ms)
        print(f"     => {latency_ms:.0f} ms")
            
    assistant_avg = np.mean(assistant_latencies)
    assistant_p95 = np.percentile(assistant_latencies, 95)
    
    # --- SUMMARY TABLE ---
    print("\n" + "=" * 60)
    print("                 PERFORMANCE SUMMARY")
    print("=" * 60)
    print(f"{'Endpoint':<20} | {'Métrique':<10} | {'Cible':<10} | {'Mesuré':<10} | {'Statut'}")
    print("-" * 60)
    
    def get_status(measured, target):
        return "OK" if measured <= target else "A SURVEILLER EN DEMO"
        
    print(f"{'/search':<20} | {'Moyenne':<10} | {'< 1000ms':<10} | {search_avg:>5.0f} ms   | {get_status(search_avg, 1000)}")
    print(f"{'/search':<20} | {'P95':<10} | {'< 1000ms':<10} | {search_p95:>5.0f} ms   | {get_status(search_p95, 1000)}")
    print(f"{'/assistant/query':<20} | {'Moyenne':<10} | {'< 8000ms':<10} | {assistant_avg:>5.0f} ms   | {get_status(assistant_avg, 8000)}")
    print(f"{'/assistant/query':<20} | {'P95':<10} | {'< 8000ms':<10} | {assistant_p95:>5.0f} ms   | {get_status(assistant_p95, 8000)}")
    print("=" * 60)
    print("Note: En environnement de production avec GPU, /assistant/query sera de ~2000-4000ms.")

if __name__ == "__main__":
    run_performance_check()
