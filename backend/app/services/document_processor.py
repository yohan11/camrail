import os
from typing import List, Dict, Any
import pdfplumber
from docx import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph

def _format_table_as_markdown(table: list) -> str:
    """Converts a 2D list of cells into a clean Markdown table string."""
    if not table:
        return ""
    
    cleaned_rows = []
    for row in table:
        if not row:
            continue
        cleaned_rows.append([str(cell or "").replace("\n", " ").strip() for cell in row])
    
    if not cleaned_rows:
        return ""
    
    max_cols = max(len(r) for r in cleaned_rows)
    if max_cols == 0:
        return ""
    
    for r in cleaned_rows:
        while len(r) < max_cols:
            r.append("")
    
    lines = []
    # Header row
    header = "| " + " | ".join(cleaned_rows[0]) + " |"
    separator = "| " + " | ".join(["---"] * max_cols) + " |"
    lines.append(header)
    lines.append(separator)
    
    # Body rows
    for row in cleaned_rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    
    return "\n".join(lines)


import logging
from app.config import settings

logger = logging.getLogger(__name__)

def ocr_page_image(pdf_path: str, page_number: int) -> str:
    """
    Extracts text from a single PDF page using Tesseract OCR.
    Gracefully returns empty string if Tesseract or Poppler is unavailable.
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        logger.warning("pdf2image or pytesseract missing. OCR skipped.")
        return ""

    try:
        # Set Tesseract path if configured
        if hasattr(settings, "TESSERACT_CMD_PATH") and settings.TESSERACT_CMD_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD_PATH

        # Convert only the specific page
        images = convert_from_path(pdf_path, first_page=page_number, last_page=page_number)
        if not images:
            return ""

        # Run OCR
        text = pytesseract.image_to_string(images[0], lang="fra+eng")
        return text.strip()
    except Exception as e:
        logger.warning(f"Tesseract OCR non disponible ou erreur ({e}) - la page {page_number} reste sans texte extrait.")
        return ""

def extract_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text and tables page by page from a PDF document using pdfplumber.
    Tables are converted to markdown and appended to the text of the corresponding page.
    If a page returns less than 20 characters, it is flagged as 'ocr_needed' and Tesseract OCR is attempted.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    pages_data = []
    with pdfplumber.open(file_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            table_markdowns = []
            table_bboxes = []
            
            for t in tables:
                md = _format_table_as_markdown(t.extract())
                if md:
                    table_markdowns.append(md)
                    table_bboxes.append(t.bbox)
            
            if table_bboxes:
                def not_within_bboxes(obj):
                    if "x0" not in obj or "top" not in obj or "x1" not in obj or "bottom" not in obj:
                        return True
                    obj_x0, obj_top, obj_x1, obj_bottom = obj["x0"], obj["top"], obj["x1"], obj["bottom"]
                    for (x0, top, x1, bottom) in table_bboxes:
                        if not (obj_x1 <= x0 or obj_x0 >= x1 or obj_bottom <= top or obj_top >= bottom):
                            return False
                    return True
                
                filtered_page = page.filter(not_within_bboxes)
                raw_text = filtered_page.extract_text() or ""
            else:
                raw_text = page.extract_text() or ""
            
            parts = []
            if raw_text.strip():
                parts.append(raw_text.strip())
            if table_markdowns:
                parts.extend(table_markdowns)
            
            full_page_text = "\n\n".join(parts)
            
            # If page text is very sparse (< 20 chars), flag for future OCR
            if len(full_page_text.strip()) < 20:
                method = "ocr_needed"
                ocr_text = ocr_page_image(file_path, idx)
                if ocr_text:
                    full_page_text = ocr_text
            else:
                method = "native"
            
            pages_data.append({
                "page_number": idx,
                "text": full_page_text,
                "method": method
            })
            
    return pages_data


def extract_docx(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text and tables from a DOCX document using python-docx.
    
    NOTE ON DOCX PAGE SEGMENTATION LIMITATION:
    The DOCX (.docx) file format is based on OpenXML flow documents and does not store
    pre-rendered physical page boundaries. Physical pagination depends entirely on
    rendering parameters (fonts, margins, target paper size). Without a heavy layout engine,
    the entire DOCX document is extracted as a single logical page (page_number=1).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    doc = DocxDocument(file_path)
    body_elements = []
    
    # Iterate through body elements preserving sequential order of paragraphs and tables
    for child in doc.element.body:
        if child.tag.endswith('p'):
            p = Paragraph(child, doc)
            if p.text.strip():
                body_elements.append(p.text.strip())
        elif child.tag.endswith('tbl'):
            t = Table(child, doc)
            table_data = []
            for row in t.rows:
                table_data.append([cell.text.strip() for cell in row.cells])
            md = _format_table_as_markdown(table_data)
            if md:
                body_elements.append(md)
    
    full_text = "\n\n".join(body_elements)
    method = "ocr_needed" if len(full_text.strip()) < 20 else "native"
    
    return [{
        "page_number": 1,
        "text": full_text,
        "method": method
    }]


def process_document(file_path: str, file_extension: str) -> List[Dict[str, Any]]:
    """
    Dispatches document processing based on file extension (.pdf or .docx).
    Raises ValueError if extension is unsupported.
    """
    ext = file_extension.lower() if file_extension.startswith(".") else f".{file_extension.lower()}"
    
    if ext == ".pdf":
        return extract_pdf(file_path)
    elif ext == ".docx":
        return extract_docx(file_path)
    else:
        raise ValueError(f"Unsupported file extension: '{file_extension}'. Only .pdf and .docx are supported.")
