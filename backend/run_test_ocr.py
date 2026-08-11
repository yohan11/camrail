import time
import os
import io
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
from app.main import app
from app.database import SessionLocal
from app.models.schemas import Document, DocumentChunk


def is_tesseract_available():
    try:
        import pytesseract
        from app.config import settings
        if hasattr(settings, "TESSERACT_CMD_PATH") and settings.TESSERACT_CMD_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD_PATH
        # Basic check
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False

def create_scanned_pdf(filename: str):
    """
    Creates a 'scanned' PDF: an image of text embedded into a PDF without native text.
    """
    # 1. Create an image with text using Pillow
    img = Image.new('RGB', (800, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    # Use default font
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
        
    text = "Ceci est un document scanné.\nLa reconnaissance optique de caractères (OCR)\ndoit être capable d'extraire ce texte.\nRailMind Lite OCR Test."
    d.text((50, 50), text, fill=(0, 0, 0), font=font)
    
    img_path = "temp_scan.png"
    img.save(img_path)
    
    # 2. Embed into a PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.image(img_path, x=10, y=10, w=150)
    pdf.output(filename)
    
    # Clean up image
    if os.path.exists(img_path):
        os.remove(img_path)


def test_ocr():
    with TestClient(app) as client:
        print("=" * 70)
        print("      RAILMIND LITE - OCR FALLBACK EVALUATION (DAY 5)")
        print("=" * 70)
        
        if not is_tesseract_available():
            print("[INFO] Tesseract OCR non détecté ou mal configuré sur cette machine.")
            print("[INFO] Ce test sera ignoré. L'OCR est un stretch du jour 5, pas un bloquant.")
            print("=" * 70)
            return
            
        print("[INFO] Tesseract OCR détecté. Démarrage du test...")
        
        # 1. Login
        login_data = {
            "username": "docadmin@camrail.net",
            "password": "docadminpassword"
        }
        login_res = client.post("/auth/login", data=login_data)
        assert login_res.status_code == 200, "Login failed"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create Scanned PDF
        pdf_filename = "test_scanned_ocr.pdf"
        create_scanned_pdf(pdf_filename)
        
        # 3. Upload Document
        print(f"\n[Step 1] Uploading scanned document '{pdf_filename}'...")
        with open(pdf_filename, "rb") as f:
            upload_res = client.post(
                "/documents",
                headers=headers,
                files={"file": (pdf_filename, f, "application/pdf")},
                data={"title": "Test OCR Scan", "department": "IT", "category": "Tests", "version": "1.0"}
            )
        assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
        doc_id = upload_res.json()["id"]
        
        # Wait for indexing
        db = SessionLocal()
        max_wait = 20
        start_wait = time.time()
        while time.time() - start_wait < max_wait:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc and doc.status in ["indexed", "failed"]:
                break
            time.sleep(1)
            
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc and doc.status == "indexed", f"Document indexing failed or timed out. Status: {doc.status if doc else 'None'}"
        print(f"-> Indexed successfully (ID: {doc_id})")
        
        # 4. Check Extracted Text in DB
        print("\n[Step 2] Verifying OCR text extraction in database...")
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
        assert chunks, "No chunks found for the document"
        
        extracted_text = chunks[0].content
        print(f"-> Extracted text snippet: '{extracted_text[:100]}...'")
        
        # The OCR text might have minor errors, so check for keywords
        assert "reconnaissance" in extracted_text.lower() or "optique" in extracted_text.lower() or "railmind" in extracted_text.lower(), "OCR failed to extract key recognizable words."
        
        # Check method is correctly saved if possible (metadata might not have it explicitly depending on implementation, but text presence is proof)
        
        print("\n-> Success! Scanned PDF was successfully converted to text via OCR.")
        
        print("\n" + "=" * 70)
        print("        ALL OCR TESTS COMPLETED SUCCESSFULLY! (1/1 PASSED)")
        print("=" * 70)
        
        db.close()


if __name__ == "__main__":
    test_ocr()
