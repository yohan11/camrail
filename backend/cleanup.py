import os
import sys
# Set up paths for importing app modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.database import SessionLocal
from app.models.schemas import Document
from sqlalchemy import func

def cleanup():
    db = SessionLocal()
    
    # Group by title
    titles = db.query(Document.title).group_by(Document.title).having(func.count(Document.id) > 1).all()
    
    for (title,) in titles:
        docs = db.query(Document).filter(Document.title == title).order_by(Document.created_at.desc()).all()
        # Keep the first one (most recent), delete others
        keep = docs[0]
        delete_docs = docs[1:]
        print(f"Keeping {title} id {keep.id}")
        for d in delete_docs:
            print(f"Deleting duplicate {title} id {d.id}")
            db.delete(d)
    
    db.commit()
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup()
