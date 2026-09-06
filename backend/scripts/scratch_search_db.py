from app.database import SessionLocal
from app.models.schemas import Document, DocumentChunk

db = SessionLocal()
docs = db.query(Document).all()
print("Documents in DB:")
for d in docs:
    print(f"- {d.id} : {d.title}")

chunks = db.query(DocumentChunk).filter(DocumentChunk.content.ilike("%vitesse%")).all()
print("\nChunks containing 'vitesse':")
for c in chunks:
    print(f"- Doc {c.document_id}, Page {c.page_start}: {c.content[:200]}...")

chunks_en = db.query(DocumentChunk).filter(DocumentChunk.content.ilike("%speed%")).all()
print("\nChunks containing 'speed':")
for c in chunks_en:
    print(f"- Doc {c.document_id}, Page {c.page_start}: {c.content[:200]}...")
