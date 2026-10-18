import os
import sys
import subprocess
from pathlib import Path
from markdown_it import MarkdownIt
import pypdf

def get_edge_bin():
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in edge_paths:
        if os.path.exists(p):
            return p
    raise RuntimeError("Microsoft Edge introuvable pour la conversion PDF.")

def render_edge_pdf(html_content: str, out_pdf: Path, title: str = "Document"):
    edge_bin = get_edge_bin()
    temp_html = out_pdf.parent / f"_temp_{out_pdf.stem}.html"
    
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    cmd = [
        edge_bin,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={out_pdf.resolve()}",
        str(temp_html.resolve().as_uri())
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Erreur Edge sur {out_pdf}: {res.stderr}")
        
    if temp_html.exists():
        temp_html.unlink()
        
    print(f"[OK] Re-généré : {out_pdf.name}")

def rebuild_doc_1(target_pdf: Path):
    """Rebuild 01_Rapport_Conception_Detaillee.pdf without Gemini."""
    md_text = subprocess.check_output(
        ['git', 'show', 'd105641:docs/01_Rapport_Conception_Detaillee.md'],
        text=True, encoding='utf-8'
    )
    
    # Remplacements précis
    md_text = md_text.replace(
        '| Génération de réponses | Modèle LLM (Gemini Lite/Ollama) | Route `/assistant/query` | ✅ |',
        '| Génération de réponses | Modèle LLM local souverain (Ollama) | Route `/assistant/query` | ✅ |'
    )
    md_text = md_text.replace(
        'Le modèle (Gemini Flash Lite ou Ollama local)',
        'Le modèle (Ollama local souverain)'
    )
    
    assert 'gemini' not in md_text.lower(), "Erreur: 'gemini' encore présent dans Doc 1 !"
    
    md = MarkdownIt("commonmark").enable("table")
    body_html = md.render(md_text)
    
    css = """
    body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 30px; color: #222; }
    h1 { color: #8B0000; border-bottom: 2px solid #8B0000; padding-bottom: 10px; }
    h2 { color: #B22222; margin-top: 30px; }
    h3 { color: #CD5C5C; }
    table { width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 14px; }
    th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
    th { background-color: #f8f9fa; font-weight: bold; color: #333; }
    pre { background-color: #f1f3f5; padding: 15px; border-radius: 8px; overflow-x: auto; }
    code { font-family: Consolas, monospace; background-color: #f1f3f5; padding: 2px 5px; border-radius: 3px; font-size: 13px; }
    blockquote { border-left: 4px solid #8B0000; margin-left: 0; padding-left: 15px; color: #555; background-color: #fdfdfd; padding: 10px; }
    @media print {
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    }
    """
    
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>01_Rapport_Conception_Detaillee.md</title><style>{css}</style></head><body>{body_html}</body></html>"
    render_edge_pdf(full_html, target_pdf)

def rebuild_doc_2(target_pdf: Path):
    """Rebuild 02_Dossier_Test_et_Recette.pdf without Gemini."""
    md_text = subprocess.check_output(
        ['git', 'show', 'd105641:docs/02_Dossier_Test_et_Recette.md'],
        text=True, encoding='utf-8'
    )
    
    # Remplacements précis
    md_text = md_text.replace(
        'Réponse rapide générée par Gemini Flash Lite avec contexte local',
        'Réponse rapide générée par le modèle local Ollama avec contexte local'
    )
    
    assert 'gemini' not in md_text.lower(), "Erreur: 'gemini' encore présent dans Doc 2 !"
    
    md = MarkdownIt("commonmark").enable("table")
    body_html = md.render(md_text)
    
    css = """
    body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 30px; color: #222; }
    h1 { color: #8B0000; border-bottom: 2px solid #8B0000; padding-bottom: 10px; }
    h2 { color: #B22222; margin-top: 30px; }
    h3 { color: #CD5C5C; }
    table { width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 14px; }
    th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
    th { background-color: #f8f9fa; font-weight: bold; color: #333; }
    pre { background-color: #f1f3f5; padding: 15px; border-radius: 8px; overflow-x: auto; }
    code { font-family: Consolas, monospace; background-color: #f1f3f5; padding: 2px 5px; border-radius: 3px; font-size: 13px; }
    blockquote { border-left: 4px solid #8B0000; margin-left: 0; padding-left: 15px; color: #555; background-color: #fdfdfd; padding: 10px; }
    @media print {
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    }
    """
    
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>02_Dossier_Test_et_Recette.md</title><style>{css}</style></head><body>{body_html}</body></html>"
    render_edge_pdf(full_html, target_pdf)

def rebuild_synthese_globale(target_pdf: Path):
    """Rebuild Synthese_Globale_RailMind_Lite.pdf with exact 3-page layout and executive CAMRAIL branding."""
    html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Synthèse Globale - RailMind Lite</title>
    <style>
        @page {
            size: A4;
            margin: 12mm 12mm 14mm 12mm;
        }
        * {
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 8.5pt;
            line-height: 1.42;
            color: #1e293b;
            background: #ffffff;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        .page-sheet {
            page-break-after: always;
            position: relative;
            min-height: 98vh;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .page-sheet:last-child {
            page-break-after: avoid;
        }
        .header-title-block {
            margin-bottom: 8px;
        }
        h1.main-title {
            color: #991b1b;
            font-size: 16pt;
            font-weight: 800;
            margin: 0 0 2px 0;
        }
        .sub-program {
            color: #1e293b;
            font-size: 9pt;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .ref-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 7.5pt;
            color: #475569;
            margin-bottom: 10px;
        }
        .doc-badge {
            display: inline-block;
            background: #fee2e2;
            color: #991b1b;
            font-size: 7pt;
            font-weight: 800;
            letter-spacing: 0.5px;
            padding: 2px 6px;
            border-radius: 3px;
            margin-bottom: 4px;
        }
        .doc-title {
            color: #0f172a;
            font-size: 11pt;
            font-weight: 700;
            margin: 0 0 4px 0;
        }
        .doc-intro {
            color: #334155;
            font-size: 8pt;
            margin: 0 0 8px 0;
        }
        h2.section-h2 {
            color: #0f172a;
            font-size: 9pt;
            font-weight: 700;
            margin: 8px 0 4px 0;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 2px;
        }
        ul.bullet-list {
            margin: 0 0 8px 0;
            padding-left: 14px;
        }
        ul.bullet-list li {
            margin-bottom: 3px;
        }
        .grid-2col {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin: 6px 0;
        }
        .card-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 5px 8px;
            font-size: 8pt;
        }
        .callout-box {
            background: #fef2f2;
            border-left: 3.5px solid #b91c1c;
            border-radius: 0 4px 4px 0;
            padding: 5px 8px;
            font-size: 8pt;
            margin: 6px 0;
            color: #1e293b;
        }
        table.recette-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 7.5pt;
            margin: 6px 0;
        }
        table.recette-table th {
            background: #0f172a;
            color: #ffffff;
            font-weight: 600;
            text-align: left;
            padding: 5px 6px;
            font-size: 7.5pt;
        }
        table.recette-table td {
            border: 1px solid #cbd5e1;
            padding: 5px 6px;
            vertical-align: middle;
        }
        table.recette-table tr:nth-child(even) {
            background: #f8fafc;
        }
        .badge-success {
            display: inline-block;
            background: #dcfce7;
            color: #166534;
            font-weight: 700;
            font-size: 7pt;
            padding: 2px 6px;
            border-radius: 3px;
            text-align: center;
        }
        .badge-conf-green {
            background: #dcfce7;
            color: #166534;
            font-weight: 700;
            padding: 1.5px 5px;
            border-radius: 3px;
        }
        .badge-conf-yellow {
            background: #fef9c3;
            color: #854d0e;
            font-weight: 700;
            padding: 1.5px 5px;
            border-radius: 3px;
        }
        .badge-conf-red {
            background: #fee2e2;
            color: #991b1b;
            font-weight: 700;
            padding: 1.5px 5px;
            border-radius: 3px;
        }
        .footer-bar {
            border-top: 1px solid #e2e8f0;
            padding-top: 5px;
            margin-top: 10px;
            display: flex;
            justify-content: space-between;
            font-size: 7.5pt;
            color: #64748b;
        }
    </style>
</head>
<body>

    <!-- ==================== PAGE 1 ==================== -->
    <div class="page-sheet">
        <div>
            <div class="header-title-block">
                <h1 class="main-title">Synthèse Documentaire : RailMind Lite</h1>
                <div class="sub-program">Programme Innovation Ferroviaire — CAMRAIL (Recherche Documentaire Augmentée)</div>
                <div class="ref-box">
                    <strong>Documents de référence :</strong> Rapport de Conception Détaillée • Dossier de Test & Recette • Manuel d'Installation & Configuration • Manuels Utilisateur, Admin & Formateur
                </div>
            </div>

            <span class="doc-badge">DOCUMENT 1 / 4</span>
            <div class="doc-title">Rapport de Conception Détaillée (RDA / RAG)</div>
            <p class="doc-intro">
                <strong>Objet & Cadre :</strong> Ce rapport (v1.0 du 14 août 2026) détaille la conception de la solution de Recherche Documentaire Augmentée (RDA/RAG) pour CAMRAIL, en réponse au cahier des charges du 15 juin 2026. La gestion du roulement du personnel est strictement hors périmètre.
            </p>

            <h2 class="section-h2">1. Architecture Globale & Choix Technologiques</h2>
            <ul class="bullet-list">
                <li><strong>Frontend :</strong> Interface conversationnelle responsive sous Next.js, React et TypeScript (charte visuelle CAMRAIL : blanc et rouge).</li>
                <li><strong>Backend & IA :</strong> API développée avec FastAPI. Modèle de langage 100% local (via Ollama souverain) pour garantir la souveraineté totale et éliminer tout risque de fuite de données internes.</li>
                <li><strong>Base de Données :</strong> PostgreSQL avec l'extension pgvector pour le stockage relationnel et la recherche vectorielle (embeddings).</li>
                <li><strong>Intégration KALATI :</strong> Conception d'une couche modulaire (KALATI Adapter) pour se connecter au portail documentaire cible sans bloquer le prototype actuel.</li>
            </ul>

            <h2 class="section-h2">2. Pipeline Documentaire & Moteur Hybride</h2>
            <ul class="bullet-list">
                <li><strong>Flux d'ingestion :</strong> Téléversement → Contrôle anti-doublon (SHA-256) → Extraction textuelle → Découpage (chunking) → Vectorisation → Indexation → Validation/Activation explicite.</li>
                <li><strong>Recherche Hybride :</strong> Fusion de la recherche lexicale (mots-clés exacts) et sémantique (proximité vectorielle).</li>
                <li><strong>Sécurité amont :</strong> Filtrage par département et groupes de sécurité avant la recherche vectorielle pour empêcher l'exposition de données non autorisées.</li>
                <li><strong>Principe d'abstention :</strong> En cas de données insuffisantes dans le corpus autorisé, l'IA s'abstient plutôt que d'halluciner.</li>
            </ul>

            <h2 class="section-h2">3. Profils et Rôles Applicatifs</h2>
            <div class="grid-2col">
                <div class="card-box">
                    <strong>Administrateur :</strong> Gestion transverse de la plateforme, accès global et supervision sécurité.
                </div>
                <div class="card-box">
                    <strong>Read Only :</strong> Consultation conversationnelle strictement limitée aux groupes de sécurité assignés.
                </div>
                <div class="card-box" style="grid-column: span 2;">
                    <strong>Document Admin :</strong> Gestion, upload, indexation et activation des documents métiers.
                </div>
            </div>

            <div style="margin-top: 14px;">
                <span class="doc-badge">DOCUMENT 2 / 4</span>
                <div class="doc-title">Dossier de Test & Recette (Validation Août 2026)</div>
                <p class="doc-intro" style="margin-bottom: 0;">
                    Ce dossier valide l'ensemble des fonctionnalités opérationnelles de RailMind Lite sur le système en développement à travers 22 cas de test (TR-01 à TR-22), tous validés avec succès (<strong>100% Fonctionnel</strong>).
                </p>
            </div>
        </div>

        <div class="footer-bar">
            <span>CAMRAIL — RailMind Lite (Synthèse Documentaire)</span>
            <span>Page 1 / 3</span>
        </div>
    </div>

    <!-- ==================== PAGE 2 ==================== -->
    <div class="page-sheet">
        <div>
            <h2 class="section-h2" style="font-size: 10pt; margin-top: 0;">Synthèse de la Matrice de Recette</h2>
            <table class="recette-table">
                <thead>
                    <tr>
                        <th style="width: 18%;">Catégorie</th>
                        <th style="width: 17%;">ID Tests</th>
                        <th style="width: 53%;">Scénarios & Comportements Validés</th>
                        <th style="width: 12%; text-align: center;">Résultat</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Sécurité & Droits</strong></td>
                        <td>TR-01, TR-02, TR-10, TR-11</td>
                        <td>Authentification valide, rejet 401 sur routes non autorisées, étanchéité stricte RH vs Technique, accès transverse Admin.</td>
                        <td style="text-align: center;"><span class="badge-success">Validé</span></td>
                    </tr>
                    <tr>
                        <td><strong>RAG & IA</strong></td>
                        <td>TR-03, TR-04, TR-07, TR-17</td>
                        <td>Réponses contextualisées rapides, abstention immédiate hors corpus avec badge rouge "Information insuffisante".</td>
                        <td style="text-align: center;"><span class="badge-success">Validé</span></td>
                    </tr>
                    <tr>
                        <td><strong>Gestion Sources</strong></td>
                        <td>TR-05, TR-06, TR-08, TR-09</td>
                        <td>Dédoublonnage des citations, affichage exclusif des sources utilisées, documents inactifs ignorés jusqu'à activation.</td>
                        <td style="text-align: center;"><span class="badge-success">Validé</span></td>
                    </tr>
                    <tr>
                        <td><strong>Ingestion & Recherche</strong></td>
                        <td>TR-12, TR-13, TR-14, TR-15, TR-16</td>
                        <td>Indexation PDF complète, rejet des fichiers vides et doublons par empreinte SHA-256, recherche lexicale et sémantique (pgvector).</td>
                        <td style="text-align: center;"><span class="badge-success">Validé</span></td>
                    </tr>
                    <tr>
                        <td><strong>Système & UI</strong></td>
                        <td>TR-18, TR-19, TR-20, TR-21, TR-22</td>
                        <td>Persistance et restauration de l'historique de chat, responsive design (Tailwind), autonomie vis-à-vis de KALATI, traçabilité d'audit.</td>
                        <td style="text-align: center;"><span class="badge-success">Validé</span></td>
                    </tr>
                </tbody>
            </table>

            <div class="callout-box">
                <strong>Points critiques vérifiés :</strong> (1) Blocage des doublons PDF par hash binaire même si renommés ; (2) Cloisonnement étanche inter-directions empêchant le LLM de recevoir du contexte non autorisé ; (3) Protection anti-hallucination certifiée.
            </div>

            <div style="margin-top: 10px;">
                <span class="doc-badge">DOCUMENT 3 / 4</span>
                <div class="doc-title">Manuel d'Installation et de Configuration</div>
                <p class="doc-intro">
                    Guide technique destiné aux équipes IT pour le déploiement sur l'infrastructure serveur de CAMRAIL.
                </p>

                <div class="grid-2col">
                    <div class="card-box">
                        <strong style="color: #0f172a;">Prérequis Système</strong>
                        <ul class="bullet-list" style="margin-top: 4px; padding-left: 12px;">
                            <li>CPU / RAM : 4 Cœurs / 8 Go minimum (embeddings & modèles).</li>
                            <li>Stockage : 50 Go SSD (recommandé pour PostgreSQL).</li>
                            <li>OS : Ubuntu 22.04 LTS (recommandé) ou Windows Server.</li>
                            <li>Environnements : Python 3.10+, Node.js 18+, PostgreSQL 15+ avec pgvector.</li>
                        </ul>
                    </div>
                    <div class="card-box">
                        <strong style="color: #0f172a;">Déploiement en 4 Étapes</strong>
                        <div style="margin-top: 4px; font-size: 7.8pt;">
                            <p style="margin: 0 0 3px 0;"><strong>1. BDD :</strong> Créer <code>camrail_rda</code> et activer <code>CREATE EXTENSION vector;</code> (via apt ou DLL Windows).</p>
                            <p style="margin: 0 0 3px 0;"><strong>2. Backend :</strong> Venv Python, <code>pip install -r requirements.txt</code>, config .env (DB, Secret, Ollama), migrations Alembic (upgrade head) et seed_demo.py.</p>
                            <p style="margin: 0;"><strong>3. Frontend :</strong> <code>npm install</code>, config de NEXT_PUBLIC_API_URL dans .env.local, <code>npm run build</code> et démarrage.</p>
                        </div>
                    </div>
                </div>

                <div class="callout-box">
                    <strong>Paramètres par défaut & Exploitation :</strong> Port Backend 8000 (Uvicorn), Port Frontend 3000. Compte par défaut : <code>admin@camrail.net</code> / <code>camrail2026</code>. Sauvegarde quotidienne via <code>pg_dump</code>.
                </div>
            </div>

            <div style="margin-top: 10px;">
                <span class="doc-badge">DOCUMENT 4 / 4</span>
                <div class="doc-title">Manuels Utilisateur, Administrateur & Guide Formateur</div>
                <h2 class="section-h2" style="margin-top: 4px;">1. Manuel Utilisateur</h2>
                <ul class="bullet-list" style="margin-bottom: 0;">
                    <li><strong>Connexion :</strong> SSO Microsoft Active Directory ou identifiants internes.</li>
                    <li><strong>Assistant & Sources :</strong> Saisie en langage naturel, consultation des citations précises (document et page exacte) sous chaque réponse.</li>
                </ul>
            </div>
        </div>

        <div class="footer-bar">
            <span>CAMRAIL — RailMind Lite (Synthèse Documentaire)</span>
            <span>Page 2 / 3</span>
        </div>
    </div>

    <!-- ==================== PAGE 3 ==================== -->
    <div class="page-sheet">
        <div>
            <ul class="bullet-list" style="margin-top: 0;">
                <li><strong>Niveaux de Confiance :</strong> <span class="badge-conf-green">Vert (Élevée)</span> Texte exact trouvé • <span class="badge-conf-yellow">Jaune (Moyenne)</span> Mots-clés croisés • <span class="badge-conf-red">Rouge (Insuffisant)</span> Abstention / Absence d'information autorisée.</li>
                <li><strong>Historique :</strong> Navigation latérale permettant de retrouver et reprendre les discussions passées.</li>
            </ul>

            <h2 class="section-h2">2. Manuel Administrateur</h2>
            <ul class="bullet-list">
                <li><strong>Cycle de Vie Documentaire :</strong> Téléversement PDF (rejet automatique des doublons par hash) → Changement de statut vers Actif → Affectation des départements et groupes de sécurité.</li>
                <li><strong>Audit & Supervision :</strong> Tableau de bord affichant les logs horodatés (connexions, requêtes, uploads).</li>
            </ul>

            <h2 class="section-h2">3. Guide Formateur (Programme d'Acculturation IA en 5 Modules)</h2>
            <div class="grid-2col">
                <div class="card-box">
                    <strong>M1 - Positionnement :</strong> Outil métier interne, pas un moteur web grand public.
                </div>
                <div class="card-box">
                    <strong>M4 - Limites IA :</strong> Pas de calculs/extrapolations ; le badge rouge est une sécurité.
                </div>
                <div class="card-box">
                    <strong>M2 - Prompting :</strong> Privilégier des questions précises et contextualisées.
                </div>
                <div class="card-box">
                    <strong>M5 - Confidentialité :</strong> Traitement 100% local souverain et filtrage des droits d'accès.
                </div>
                <div class="card-box" style="grid-column: span 2;">
                    <strong>M3 - Rôle Humain :</strong> Vérifier systématiquement les sources citées.
                </div>
            </div>
        </div>

        <div class="footer-bar">
            <span>CAMRAIL — RailMind Lite (Synthèse Documentaire)</span>
            <span>Page 3 / 3</span>
        </div>
    </div>

</body>
</html>"""
    
    assert 'gemini' not in html_content.lower(), "Erreur: 'gemini' encore présent dans Synthèse Globale !"
    assert 'basculement' not in html_content.lower(), "Erreur: 'basculement' encore présent dans Synthèse Globale !"
    
    render_edge_pdf(html_content, target_pdf)

def main():
    root = Path(__file__).resolve().parent.parent
    docs_dir = root / "Documentation RailMind Lite"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    p1 = docs_dir / "01_Rapport_Conception_Detaillee.pdf"
    p2 = docs_dir / "02_Dossier_Test_et_Recette.pdf"
    p_syn = docs_dir / "Synthese_Globale_RailMind_Lite.pdf"
    
    # 1. Supprimer les anciens fichiers comme demandé explicitement par l'utilisateur
    for p in [p1, p2, p_syn]:
        if p.exists():
            print(f"Suppression de l'ancien document : {p.name}")
            p.unlink()
            
    # 2. Re-générer les nouveaux documents
    print("\nRe-création des documents assainis...")
    rebuild_doc_1(p1)
    rebuild_doc_2(p2)
    rebuild_synthese_globale(p_syn)
    
    # 3. Vérification exhaustive post-génération
    print("\nVérification d'absence totale de 'gemini' dans tous les PDFs...")
    for p in [p1, p2, p_syn]:
        reader = pypdf.PdfReader(str(p))
        full_text = ""
        for i, page in enumerate(reader.pages):
            full_text += (page.extract_text() or "") + " "
        
        assert "gemini" not in full_text.lower(), f"ALERTE: Gemini trouvé dans {p.name}!"
        print(f"  [VALIDE] {p.name} : {len(reader.pages)} pages, ZERO mention de Gemini.")

if __name__ == "__main__":
    main()
