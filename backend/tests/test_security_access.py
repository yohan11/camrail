import sys
import os

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal, Base, engine
from app.models.schemas import User, Document, DocumentChunk, SecurityGroup, UserRole
from app.services.retrieval import hybrid_search

def run_test():
    db = SessionLocal()
    try:
        # 1. Setup mock data
        # Create groups
        group_hr = SecurityGroup(name="HR")
        group_finance = SecurityGroup(name="Finance")
        db.add_all([group_hr, group_finance])
        db.commit()

        # Create user with ONLY HR group
        test_user = User(
            email="test_rbac@camrail.net",
            password_hash="mock",
            role=UserRole.READ_ONLY,
            department="HR"
        )
        test_user.security_groups.append(group_hr)
        db.add(test_user)
        db.commit()

        # Create Document with BOTH groups (partially accessible)
        doc = Document(
            title="Mixed Confidential Doc",
            version="1.0",
            category="procedure",
            department="HQ",
            checksum="mock_checksum_rbac",
            status="active",
            uploaded_by=test_user.id
        )
        doc.security_groups.extend([group_hr, group_finance])
        db.add(doc)
        db.commit()

        # Create Chunk belonging ONLY to Finance
        chunk_finance = DocumentChunk(
            document_id=doc.id,
            page_start=1,
            page_end=1,
            chunk_index=0,
            content="SECRET FINANCE DATA: The budget is 10M.",
            security_group="Finance"
        )
        # Create Chunk belonging to HR
        chunk_hr = DocumentChunk(
            document_id=doc.id,
            page_start=2,
            page_end=2,
            chunk_index=1,
            content="HR DATA: Employee list.",
            security_group="HR"
        )
        db.add_all([chunk_finance, chunk_hr])
        db.commit()

        # 2. Perform search as the HR user
        # User is read_only, so they can only search with their groups
        user_groups = [g.name for g in test_user.security_groups]
        
        # Test 1: Should NOT retrieve Finance chunk even though Document is accessible
        results = hybrid_search(
            db=db,
            query="SECRET FINANCE DATA budget",
            security_groups=user_groups
        )
        
        finance_leaked = any(r["chunk_id"] == chunk_finance.id for r in results)
        if finance_leaked:
            print("❌ FAIL: User retrieved a chunk they don't have access to!")
            sys.exit(1)
        else:
            print("✅ PASS: User cannot access the restricted chunk.")

        # Test 2: Should retrieve HR chunk successfully
        results2 = hybrid_search(
            db=db,
            query="HR DATA Employee",
            security_groups=user_groups
        )
        hr_retrieved = any(r["chunk_id"] == chunk_hr.id for r in results2)
        if not hr_retrieved:
            print("❌ FAIL: User could not retrieve a chunk they DO have access to!")
            sys.exit(1)
        else:
            print("✅ PASS: User successfully accessed their authorized chunk.")

    finally:
        # Cleanup
        db.rollback()
        try:
            db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
            db.query(Document).filter(Document.id == doc.id).delete()
            db.query(User).filter(User.email == "test_rbac@camrail.net").delete()
            db.query(SecurityGroup).filter(SecurityGroup.name.in_(["HR", "Finance"])).delete()
            db.commit()
        except Exception:
            pass
        db.close()

if __name__ == "__main__":
    print("Running Security RBAC Test...")
    run_test()
