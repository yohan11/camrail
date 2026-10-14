#!/usr/bin/env python3
"""
Script de sélection et d'activation d'un profil matériel pour CAMRAIL RailMind Lite.
Usage :
    python scripts/select_profile.py A
    python scripts/select_profile.py B
    python scripts/select_profile.py C
    python scripts/select_profile.py (mode interactif)
"""

import os
import sys
import shutil

# Assurer l'encodage UTF-8 sous Windows
if sys.platform.startswith("win") and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Détection des répertoires
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir) if os.path.basename(script_dir) == "scripts" else script_dir
backend_dir = os.path.join(root_dir, "backend") if os.path.exists(os.path.join(root_dir, "backend")) else root_dir
profiles_dir = os.path.join(backend_dir, "env-profiles")

PROFILES = {
    "A": {
        "file": "profile-A-cpu.env",
        "title": "Profil A : CPU Modeste (Core i3 / 8 Go RAM / 1-3 users simultanés)",
        "ram": "4-6 Go RAM",
        "ollama_model": "llama3.2:3b"
    },
    "B": {
        "file": "profile-B-cpu-puissant.env",
        "title": "Profil B : CPU Puissant (Xeon ou i7-i9 / 16-32 Go RAM / 5-15 users simultanés)",
        "ram": "10-16 Go RAM",
        "ollama_model": "llama3.2:3b"
    },
    "C": {
        "file": "profile-C-gpu.env",
        "title": "Profil C : Serveur GPU Dédié (NVIDIA RTX/A-Series / 32-64 Go RAM / 15-30 users)",
        "ram": "16 Go RAM + 12-24 Go VRAM",
        "ollama_model": "llama3.1:8b"
    }
}


def parse_env_file(filepath):
    values = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip()
    return values


def main():
    print("=" * 80)
    print("      CAMRAIL RAILMIND LITE - CONFIGURATION DU PROFIL MATERIEL")
    print("=" * 80)

    chosen_key = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().upper()
        if arg in PROFILES:
            chosen_key = arg
        else:
            for k, p in PROFILES.items():
                if arg.lower() in p["file"].lower():
                    chosen_key = k
                    break

    if not chosen_key:
        print("\nVeuillez choisir le profil adapte a votre environnement materiel :")
        for k, p in PROFILES.items():
            print(f"  [{k}] {p['title']}")
            print(f"      RAM requise : {p['ram']}")
        try:
            choice = input("\nVotre choix (A, B ou C) [defaut: A] : ").strip().upper()
            chosen_key = choice if choice in PROFILES else "A"
        except (KeyboardInterrupt, EOFError):
            print("\nOperation annulee.")
            sys.exit(0)

    selected = PROFILES[chosen_key]
    src_path = os.path.join(profiles_dir, selected["file"])

    if not os.path.exists(src_path):
        print(f"[!] ERREUR : Fichier de profil introuvable : {src_path}")
        sys.exit(1)

    dst_backend_env = os.path.join(backend_dir, ".env")
    
    # Préserver le DATABASE_URL existant si déjà configuré localement
    existing_db_url = None
    if os.path.exists(dst_backend_env):
        existing_vars = parse_env_file(dst_backend_env)
        if "DATABASE_URL" in existing_vars and existing_vars["DATABASE_URL"].strip():
            existing_db_url = existing_vars["DATABASE_URL"]

    # Copier le profil
    with open(src_path, "r", encoding="utf-8") as f:
        new_content = f.read()

    if existing_db_url:
        import re
        new_content = re.sub(r"DATABASE_URL=.*", f"DATABASE_URL={existing_db_url}", new_content)

    with open(dst_backend_env, "w", encoding="utf-8") as f:
        f.write(new_content)

    env_vars = parse_env_file(dst_backend_env)
    ollama_model = env_vars.get("OLLAMA_MODEL", selected["ollama_model"])
    embedding_model = env_vars.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    workers = env_vars.get("UVICORN_WORKERS", "1")

    print(f"\n[OK] Profil selectionne avec succes : {selected['title']}")
    print(f"[OK] Fichier deploye : {dst_backend_env}")
    if existing_db_url:
        print(f"[OK] Connexion DB locale preservee : {existing_db_url[:40]}...")
    print("\n" + "-" * 80)
    print("                       COMMANDES A EXECUTER")
    print("-" * 80)
    print(f"1. Telecharger le modele Ollama requis ({ollama_model}) :")
    print(f"   >>> ollama pull {ollama_model}")
    print("\n2. Verifier et preparer les poids d'embedding hors-ligne :")
    print(f"   >>> python scripts/prepare_models.py")
    print("\n3. Mettre a jour la base de donnees :")
    print(f"   >>> alembic upgrade head")
    print("\n4. Demarrer le serveur ({workers} worker(s)) :")
    print(f"   Linux / Mac : ./scripts/start_server.sh")
    print(f"   Windows     : .\\scripts\\start_server.bat")
    print("-" * 80 + "\n")


if __name__ == "__main__":
    main()
