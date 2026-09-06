import os
os.environ["HF_HUB_OFFLINE"] = "1"
from app.database import SessionLocal
from app.models.schemas import Document

def test():
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == 36).first()
    if doc:
        print(f"Doc 36 groups: {[g.name for g in doc.security_groups]}")
        print(f"Doc 36 status: {doc.status}")
    else:
        print("Doc 36 not found")

if __name__ == "__main__":
    test()
