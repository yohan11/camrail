#!/usr/bin/env python3
"""
backend/scripts/verify_audit_chain.py
=====================================
Vérificateur autonome d'intégrité cryptographique du journal d'audit CAMRAIL RailMind Lite.

Ce script recalcule pour chaque ligne de la table 'audit_logs' :
1. La continuité stricte de la séquence 'seq' (détecte suppressions et insertions intermédiaires).
2. Le chaînage cryptographique 'prev_hash' (détecte réordonnancement ou substitution).
3. Le code d'authentification de message HMAC-SHA256 (détecte toute altération d'un champ quelconque).

Codes de retour :
  - 0 : La chaîne est 100% intègre et valide.
  - 1 : Altération, suppression ou rupture détectée dans la chaîne d'audit.

========================================================================================
EXEMPLES DE PLANIFICATION AUTOMATIQUE :
========================================================================================

1. CRON SOUS LINUX / DOCKER :
-----------------------------
Ajoutez la ligne suivante dans le crontab de l'administrateur système (crontab -e)
pour une vérification toutes les heures avec journalisation dans /var/log :

  0 * * * * cd /opt/camrail/backend && /opt/camrail/backend/venv/bin/python scripts/verify_audit_chain.py >> /var/log/camrail_audit_verify.log 2>&1

Pour recevoir une alerte par email uniquement en cas d'échec :
  0 * * * * /opt/camrail/backend/venv/bin/python /opt/camrail/backend/scripts/verify_audit_chain.py || mail -s "ALERTE SÉCURITÉ: Audit RailMind altéré" admin@camrail.net

2. TÂCHE PLANIFIÉE WINDOWS (Windows Task Scheduler) :
-----------------------------------------------------
Option A - Ligne de commande 'schtasks' (Invite de commandes Administrateur) :
  schtasks /create /tn "CAMRAIL_Audit_Verification" /tr "\"D:\\camrail-main\\backend\\venv\\Scripts\\python.exe\" \"D:\\camrail-main\\backend\\scripts\\verify_audit_chain.py\"" /sc HOURLY /ru SYSTEM

Option B - PowerShell (Exécuter en tant qu'Administrateur) :
  $Action = New-ScheduledTaskAction -Execute "D:\\camrail-main\\backend\\venv\\Scripts\\python.exe" -Argument "D:\\camrail-main\\backend\\scripts\\verify_audit_chain.py"
  $Trigger = New-ScheduledTaskTrigger -Hourly
  $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3
  Register-ScheduledTask -TaskName "CAMRAIL_Audit_Verification" -Action $Action -Trigger $Trigger -Settings $Settings -User "SYSTEM" -Description "Vérification horaire de l'intégrité de la chaîne d'audit RailMind Lite"

========================================================================================
LIMITE ARCHITECTURALE DU TRIGGER DOCUMENTÉE :
========================================================================================
Le trigger PostgreSQL 'prevent_audit_logs_tampering' bloque les opérations UPDATE, DELETE et TRUNCATE.
Toutefois, le super-utilisateur ou le propriétaire de la table peut désactiver les triggers
('ALTER TABLE audit_logs DISABLE TRIGGER ALL;').
C'est précisément l'exécution périodique de CE script (verify_audit_chain.py) qui permet de détecter
de façon irréfutable toute altération passée sous silence par contournement de trigger.
"""

import os
import sys
from pathlib import Path

# Ajouter backend au PYTHONPATH pour importer app.*
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Changer le répertoire courant vers backend pour charger .env
os.chdir(BACKEND_DIR)

from app.database import SessionLocal
from app.services.audit import verify_chain


def main() -> int:
    db = SessionLocal()
    try:
        ok, verified_count, first_broken_seq = verify_chain(db)
        if ok:
            print("==================================================================")
            print("[SUCCÈS] Intégrité du journal d'audit : VÉRIFIÉE")
            print(f"Nombre total d'événements cryptographiquement validés : {verified_count}")
            print("Chaîne de hachage HMAC-SHA256 intacte. Aucun trou ni altération.")
            print("==================================================================")
            return 0
        else:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
            print(f"[ALERTE SÉCURITÉ] Intégrité du journal : ALTÉRÉE à partir de l'événement {first_broken_seq}", file=sys.stderr)
            print(f"Nombre d'événements valides avant rupture : {verified_count}", file=sys.stderr)
            print(f"Numéro de séquence corrompu ou manquant : seq={first_broken_seq}", file=sys.stderr)
            print("Action immédiate requise : inspecter la table audit_logs et les sauvegardes.", file=sys.stderr)
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"[ERREUR TECHNIQUE] Impossible d'exécuter la vérification de la chaîne d'audit : {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
