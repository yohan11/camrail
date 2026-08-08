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


def extract_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text and tables page by page from a PDF document using pdfplumber.
    Tables are converted to markdown and appended to the text of the corresponding page.
    If a page returns less than 20 characters, it is flagged as 'ocr_needed'.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    pages_data = []
    with pdfplumber.open(file_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text() or ""
            tables = page.extract_tables() or []
            
            table_markdowns = []
            for t in tables:
                md = _format_table_as_markdown(t)
                if md:
                    table_markdowns.append(md)
            
            parts = []
            if raw_text.strip():
                parts.append(raw_text.strip())
            if table_markdowns:
                parts.extend(table_markdowns)
            
            full_page_text = "\n\n".join(parts)
            
            # If page text is very sparse (< 20 chars), flag for future OCR
            method = "ocr_needed" if len(full_page_text.strip()) < 20 else "native"
            
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
