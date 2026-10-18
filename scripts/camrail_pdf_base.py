import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path

# Add backend directory to path
backend_dir = Path("D:/camrail-main/backend").resolve()
sys.path.insert(0, str(backend_dir))

from fpdf import FPDF
from app.database import SessionLocal
from app.models.schemas import Document, DocumentPage, DocumentChunk, SecurityGroup, User
from app.services.indexing import index_document
from app.services.document_processor import process_document

class CAMRAILManualPDF(FPDF):
    def __init__(self, doc_code: str, doc_title: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_code = self.clean_text(doc_code)
        self.doc_title = self.clean_text(doc_title)
        self.set_auto_page_break(auto=False)
        self.set_margins(left=18, top=22, right=18)

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        replacements = {
            "œ": "oe", "Œ": "OE",
            "æ": "ae", "Æ": "AE",
            "’": "'", "‘": "'",
            "“": '"', "”": '"',
            "«": '"', "»": '"',
            "—": "-", "–": "-",
            "…": "...", "•": "-",
            " ": " ",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text.encode("latin-1", "replace").decode("latin-1")

    def header(self):
        self.set_font("helvetica", "B", 8)
        self.set_text_color(100, 116, 139) # slate-500
        self.set_xy(18, 10)
        self.cell(100, 5, self.clean_text("CAMRAIL - DIRECTION GÉNÉRALE DE L'EXPLOITATION FERROVIAIRE"), border=0, align="L")
        self.set_xy(120, 10)
        self.cell(72, 5, self.doc_code, border=0, align="R")
        
        # Red line
        self.set_draw_color(224, 0, 16) # #E00010
        self.set_line_width(0.6)
        self.line(18, 16, 192, 16)

    def footer(self):
        self.set_draw_color(203, 213, 225) # slate-300
        self.set_line_width(0.3)
        self.line(18, 282, 192, 282)
        
        self.set_font("helvetica", "I", 7.5)
        self.set_text_color(100, 116, 139)
        self.set_xy(18, 284)
        self.cell(110, 5, self.clean_text("DOCUMENT OFFICIEL CAMRAIL - RÉFÉRENTIEL TECHNIQUE RÉGLEMENTAIRE INTERNE"), border=0, align="L")
        self.set_xy(130, 284)
        self.cell(62, 5, f"Page {self.page_no()} sur 8", border=0, align="R")

    def render_page_header(self, page_num: int, title: str, subtitle: str = ""):
        self.set_y(24)
        self.set_font("helvetica", "B", 13)
        self.set_text_color(153, 0, 0) # dark red
        self.cell(0, 7, self.clean_text(f"PAGE {page_num} : {title.upper()}"), ln=True)
        if subtitle:
            self.set_font("helvetica", "I", 9)
            self.set_text_color(71, 85, 105)
            self.cell(0, 5, self.clean_text(subtitle), ln=True)
        self.ln(2)

    def render_section(self, title: str):
        self.set_font("helvetica", "B", 10.5)
        self.set_text_color(15, 23, 42) # slate-900
        self.cell(0, 6, self.clean_text(title), ln=True)
        self.ln(1)

    def render_paragraph(self, text: str):
        self.set_font("helvetica", "", 8.8)
        self.set_text_color(30, 41, 59) # slate-800
        self.multi_cell(0, 4.8, self.clean_text(text.strip()))
        self.ln(2.5)

    def render_callout(self, title: str, text: str):
        title = self.clean_text(title)
        text = self.clean_text(text.strip())
        
        self.set_fill_color(254, 242, 242) # red-50
        self.set_draw_color(224, 0, 16) # camrail red
        self.set_line_width(0.8)
        
        x = self.get_x()
        y = self.get_y()
        w = 174
        
        lines = len(text) // 85 + 2
        h = max(14, lines * 4.5 + 6)
        
        self.rect(x, y, w, h, style="F")
        self.line(x, y, x, y + h)
        
        self.set_xy(x + 4, y + 2)
        self.set_font("helvetica", "B", 8.5)
        self.set_text_color(185, 28, 28) # red-700
        self.cell(w - 8, 4.5, f"RÈGLE IMPÉRATIVE DE SÉCURITÉ : {title}", ln=True)
        
        self.set_xy(x + 4, y + 7)
        self.set_font("helvetica", "", 8)
        self.set_text_color(30, 41, 59)
        self.multi_cell(w - 8, 4.2, text)
        self.set_y(y + h + 3)

    def render_table(self, headers, rows, col_widths):
        self.set_font("helvetica", "B", 8)
        self.set_fill_color(15, 23, 42)
        self.set_text_color(255, 255, 255)
        self.set_draw_color(203, 213, 225)
        self.set_line_width(0.2)
        
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 6, self.clean_text(h), border=1, align="C", fill=True)
        self.ln()
        
        self.set_font("helvetica", "", 7.8)
        self.set_text_color(15, 23, 42)
        for r_idx, row in enumerate(rows):
            fill = (r_idx % 2 == 1)
            self.set_fill_color(248, 250, 252) if fill else self.set_fill_color(255, 255, 255)
            for i, val in enumerate(row):
                align = "C" if i == 0 or i == len(row)-1 else "L"
                self.cell(col_widths[i], 5.2, self.clean_text(str(val)), border=1, align=align, fill=True)
            self.ln()
        self.ln(2.5)

print("FPDF robust class defined with Latin-1 text sanitization.")
