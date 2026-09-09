import os
import hashlib
from fastapi.testclient import TestClient
from fpdf import FPDF
import warnings

from app.main import app
from app.database import SessionLocal
from app.models.schemas import Document, User
from app.seed import seed_database

warnings.filterwarnings("ignore", category=DeprecationWarning)

DEMO_DIR = "demo-data"

def generate_mock_pdfs():
    """Generates mock PDFs if the demo_documents directory is empty."""
    if not os.path.exists(DEMO_DIR):
        os.makedirs(DEMO_DIR)
        
    print(f"[{DEMO_DIR}] Checking demo documents... Generating 10-page mock documents...")
    
    # 1. Consigne RH 04
    pdf1 = FPDF()
    for i in range(10):
        pdf1.add_page()
        pdf1.set_font("Arial", size=12)
        if i == 5:
            pdf1.multi_cell(0, 10, text="REGLEMENTATION DU TRAVAIL ET TEMPS DE REPOS\nLe repos minimum entre deux services est de douze heures. Cette regle est strictement appliquee a l ensemble du personnel roulant et des agents de conduite de CAMRAIL pour garantir la securite des circulations ferroviaires.")
        else:
            pdf1.multi_cell(0, 10, text=f"Page {i+1}\n" + "Contenu de remplissage standard pour les consignes RH. Ceci est utilise pour tester l extraction de texte sur de longs documents. " * 30)
    pdf1.output(os.path.join(DEMO_DIR, "Consigne_RH_04.pdf"))
    
    # 2. Programmation Java
    pdf2 = FPDF()
    for i in range(10):
        pdf2.add_page()
        pdf2.set_font("Arial", size=12)
        if i == 8:
            pdf2.multi_cell(0, 10, text="Chapitre 2: Introduction a Java\nJava est un langage oriente objet tres utilise en entreprise. Chapitre 3: L'heritage permet de creer des hierarchies de classes. Chapitre 4: Le polymorphisme.")
        else:
            pdf2.multi_cell(0, 10, text=f"Page {i+1}\n" + "Texte de remplissage pour le manuel de programmation Java. " * 40)
    pdf2.output(os.path.join(DEMO_DIR, "Formation_Java_Chap_2_4.pdf"))

    # 3. Golden Set DOCX files
    try:
        from docx import Document
        docs = {
            '01_histoire_chemin_de_fer.docx': 'Les premières voies ferrées sont apparues au XIXe siècle, révolutionnant le transport de marchandises et de passagers.',
            '02_infrastructure_voie_ferree.docx': 'Une voie ferrée classique est composée de rails, de traverses et de ballast.',
            '03_signalisation_ferroviaire.docx': 'Le rôle premier de la signalisation ferroviaire est de garantir la sécurité des circulations.',
            '04_trains_grande_vitesse.docx': 'Un train est qualifié de grande vitesse lorsqu\'il dépasse 250 km/h sur une ligne nouvelle.',
            '05_securite_ferroviaire_reglementation.docx': 'En France, c\'est l\'EPSF qui est chargé de délivrer les autorisations de circulation.',
            'RailMind_Test_03_Maintenance_FR.docx': 'La maintenance préventive consiste à intervenir sur le matériel avant qu\'une panne ne survienne.',
            'RailMind_Test_02_Securite_FR.docx': 'La sécurité ferroviaire générale dépend d\'un ensemble de facteurs: infrastructures, contrôle.',
            'RailMind_Test_01_Operations_FR.docx': 'La gestion de la circulation des trains consiste à planifier et réguler le trafic.'
        }
        for filename, content in docs.items():
            doc = Document()
            doc.add_heading(filename.replace('.docx', ''), 0)
            
            for i in range(10):
                if i == 7:
                    doc.add_paragraph(content)
                else:
                    doc.add_paragraph(f"Page {i+1}\n" + "Texte générique ferroviaire de remplissage pour tester les performances du système RAG sur de grands documents avec beaucoup de bruit. " * 30)
                
                if i < 9:
                    doc.add_page_break()
                    
            doc.save(os.path.join(DEMO_DIR, filename))
    except ImportError:
        print("python-docx non installé, impossible de générer les fichiers .docx pour le golden set.")
    
def calculate_checksum(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def seed_demo():
    print("=" * 60)
    print("       RAILMIND LITE - DEMO ENVIRONMENT RESET")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        print("[1] Ensuring demo users and security groups exist...")
        seed_database(db)
        
        # Verify users
        admin = db.query(User).filter(User.email == "admin@camrail.net").first()
        docadmin = db.query(User).filter(User.email == "docadmin@camrail.net").first()
        readonly = db.query(User).filter(User.email == "readonly@camrail.net").first()
        
        if not (admin and docadmin and readonly):
            print("ERROR: Users were not seeded correctly.")
            return
            
        print("[2] Checking demo documents...")
        generate_mock_pdfs()
        
        client = TestClient(app)
        
        # Authenticate as docadmin
        login_resp = client.post(
            "/auth/login",
            data={"username": "docadmin@camrail.net", "password": "docadminpassword"}
        )
        if login_resp.status_code != 200:
            print("ERROR: Failed to authenticate docadmin.")
            return
            
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        files_to_process = [f for f in os.listdir(DEMO_DIR) if f.endswith('.pdf') or f.endswith('.docx')]
        
        print(f"[3] Processing {len(files_to_process)} documents from {DEMO_DIR}...")
        
        for filename in files_to_process:
            filepath = os.path.join(DEMO_DIR, filename)
            checksum = calculate_checksum(filepath)
            
            # Check if document already exists
            existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
            if existing_doc:
                print(f"  -> Skipping {filename} (Already exists, ID: {existing_doc.id})")
                
                # Activate if not active
                if existing_doc.status == "indexed":
                    client.post(f"/documents/{existing_doc.id}/activate", headers=headers)
                    print(f"     Activated existing document {existing_doc.id}.")
                continue
                
            # Mapping logic
            title = filename.replace(".pdf", "").replace(".docx", "").replace("_", " ")
            category = "procedure"
            department = "Operations"
            
            if "Consigne" in filename or "RH" in filename:
                category = "procedure"
                department = "Safety"
            elif "Formation" in filename or "Java" in filename:
                category = "manuel"
                department = "Formation"
            elif "histoire" in filename:
                category = "Histoire"
            elif "infrastructure" in filename:
                category = "Infrastructure"
            elif "signalisation" in filename:
                category = "Signalisation"
            elif "grande_vitesse" in filename:
                category = "Matériel Roulant"
            elif "reglementation" in filename:
                category = "Réglementation"
            elif "Maintenance" in filename:
                category = "Maintenance"
            elif "Securite" in filename:
                category = "Sécurité"
            elif "Operations" in filename:
                category = "Exploitation"
                
            print(f"  -> Uploading {filename} (Category: {category}, Dept: {department})...")
            
            with open(filepath, "rb") as f:
                upload_resp = client.post(
                    "/documents",
                    headers=headers,
                    data={
                        "title": title,
                        "version": "1.0",
                        "category": category,
                        "department": department,
                        "effective_date": "2026-08-01"
                    },
                    files={"file": (filename, f, "application/pdf" if filename.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                )
                
            if upload_resp.status_code == 200:
                doc_id = upload_resp.json()["id"]
                print(f"     Upload successful. Activating document {doc_id}...")
                act_resp = client.post(f"/documents/{doc_id}/activate", headers=headers)
                if act_resp.status_code == 200:
                    print(f"     Document {doc_id} activated.")
                else:
                    print(f"     Failed to activate document {doc_id}: {act_resp.text}")
            else:
                print(f"     Failed to upload {filename}: {upload_resp.text}")
                
        # Final Summary
        active_docs = db.query(Document).filter(Document.status == "active").count()
        users_count = db.query(User).count()
        
        print("\n" + "=" * 60)
        print("                 DEMO RESET COMPLETE")
        print("=" * 60)
        print(f" Users ready            : {users_count}")
        print(f" Active documents       : {active_docs}")
        print(f" Test Accounts:")
        print(f"   Admin (Global)       : admin@camrail.net / adminpassword")
        print(f"   DocAdmin (Global)    : docadmin@camrail.net / docadminpassword")
        print(f"   Read-Only (Formation): readonly@camrail.net / readonlypassword")
        print("=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo()
