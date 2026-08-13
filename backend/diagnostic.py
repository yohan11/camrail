import os
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.schemas import Document, DocumentChunk

def run_diagnostic():
    db = SessionLocal()
    report = {}
    try:
        doc = db.query(Document).filter(Document.title.ilike("%Consigne%RH%04%")).first()
        if not doc:
            doc = db.query(Document).filter(Document.title.ilike("%Consigne RH 04%")).first()
        
        if doc:
            chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
            report['content'] = []
            for c in chunks:
                report['content'].append(c.content)
        else:
            report['error'] = "Document not found"

    finally:
        db.close()
        
    with open("doc_content.txt", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("Done")

if __name__ == "__main__":
    run_diagnostic()
