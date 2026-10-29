import os
import subprocess
from pathlib import Path
from markdown_it import MarkdownIt

def generate_pdf():
    root_dir = Path(__file__).resolve().parent.parent
    md_file = root_dir / "GUIDE_INSTALLATION.md"
    pdf_file = root_dir / "GUIDE_INSTALLATION.pdf"
    doc_dir = root_dir / "Documentation RailMind Lite"
    doc_pdf = doc_dir / "GUIDE_INSTALLATION.pdf"
    temp_html = root_dir / "_temp_guide.html"

    with open(md_file, "r", encoding="utf-8") as f:
        md_text = f.read()

    md = MarkdownIt().enable("table").enable("strikethrough")
    html_content = md.render(md_text)

    # High-end CSS for executive PDF styling
    css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    @page {
        size: A4;
        margin: 18mm 14mm 18mm 14mm;
        @bottom-right {
            content: "Page " counter(page);
            font-family: 'Inter', sans-serif;
            font-size: 8pt;
            color: #64748b;
        }
    }

    * {
        box-sizing: border-box;
    }

    body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 9.5pt;
        line-height: 1.55;
        color: #1e293b;
        background-color: #ffffff;
        margin: 0;
        padding: 0;
    }

    h1, h2, h3, h4 {
        color: #0f172a;
        font-weight: 700;
        page-break-after: avoid;
        break-after: avoid;
    }

    h1 {
        font-size: 20pt;
        font-weight: 800;
        color: #990000;
        border-bottom: 2.5px solid #E00010;
        padding-bottom: 8px;
        margin-top: 0;
        margin-bottom: 16px;
    }

    h2 {
        font-size: 13pt;
        border-left: 4px solid #E00010;
        padding-left: 10px;
        margin-top: 24px;
        margin-bottom: 12px;
        background: #fef2f2;
        padding-top: 4px;
        padding-bottom: 4px;
        border-radius: 0 6px 6px 0;
    }

    h3 {
        font-size: 11pt;
        color: #1e293b;
        margin-top: 18px;
        margin-bottom: 8px;
    }

    h4 {
        font-size: 10pt;
        color: #334155;
        margin-top: 14px;
        margin-bottom: 6px;
    }

    p {
        margin-top: 0;
        margin-bottom: 10px;
    }

    blockquote {
        margin: 14px 0;
        padding: 10px 14px;
        background: #f8fafc;
        border-left: 4px solid #0284c7;
        border-radius: 0 6px 6px 0;
        font-size: 9pt;
        color: #334155;
    }

    blockquote p {
        margin: 0;
    }

    /* Tables */
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 14px 0;
        font-size: 8pt;
        page-break-inside: avoid;
        break-inside: avoid;
    }

    th, td {
        border: 1px solid #cbd5e1;
        padding: 6px 8px;
        text-align: left;
        vertical-align: top;
    }

    th {
        background-color: #0f172a;
        color: #ffffff;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 7.5pt;
        letter-spacing: 0.5px;
    }

    tbody tr:nth-child(even) {
        background-color: #f8fafc;
    }

    tbody tr:hover {
        background-color: #f1f5f9;
    }

    /* Code & Pre */
    code {
        font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
        font-size: 8.5pt;
        background-color: #f1f5f9;
        color: #b91c1c;
        padding: 1.5px 4px;
        border-radius: 4px;
        border: 1px solid #e2e8f0;
    }

    pre {
        background-color: #0f172a;
        color: #f8fafc;
        padding: 10px 12px;
        border-radius: 6px;
        overflow-x: auto;
        font-size: 8pt;
        line-height: 1.45;
        margin: 10px 0;
        page-break-inside: avoid;
        break-inside: avoid;
        border: 1px solid #334155;
    }

    pre code {
        background-color: transparent;
        color: #f8fafc;
        padding: 0;
        border: none;
        font-size: 8pt;
    }

    ul, ol {
        margin-top: 0;
        margin-bottom: 10px;
        padding-left: 20px;
    }

    li {
        margin-bottom: 4px;
    }

    img {
        max-width: 100%;
        height: auto;
        border-radius: 8px;
        margin: 12px 0;
        border: 1px solid #e2e8f0;
    }

    hr {
        border: none;
        border-top: 1px solid #e2e8f0;
        margin: 20px 0;
    }

    /* Print Specific */
    @media print {
        body {
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        h2 {
            page-break-after: avoid;
        }
        table, pre, blockquote {
            page-break-inside: avoid;
        }
    }
    """

    full_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>CAMRAIL RailMind Lite - Guide Officiel d'Installation</title>
    <style>
        {css}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""

    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(full_html)

    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]

    edge_bin = None
    for p in edge_paths:
        if os.path.exists(p):
            edge_bin = p
            break

    if not edge_bin:
        raise RuntimeError("Microsoft Edge introuvable pour la conversion PDF.")

    cmd = [
        edge_bin,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_file}",
        str(temp_html.resolve().as_uri())
    ]

    print(f"Conversion en cours via Edge Headless...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Erreur Edge: {res.stderr}")
        raise RuntimeError("Échec de la génération PDF via Edge.")

    print(f"PDF généré avec succès : {pdf_file}")

    # Copie dans Documentation RailMind Lite si le dossier existe
    if doc_dir.exists():
        import shutil
        shutil.copy2(pdf_file, doc_pdf)
        print(f"Copie enregistrée dans : {doc_pdf}")

    # Suppression du fichier HTML temporaire
    if temp_html.exists():
        temp_html.unlink()

if __name__ == "__main__":
    generate_pdf()
