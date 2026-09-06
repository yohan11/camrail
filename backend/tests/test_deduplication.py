import os
import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.schemas import Document

def run_deduplication_test():
    print("=" * 60)
    print("      RAILMIND LITE - DEDUPLICATION TEST")
    print("=" * 60)

    client = TestClient(app)
    db = SessionLocal()

    # Login as admin
    login_resp = client.post(
        "/auth/login",
        data={"username": "admin@camrail.net", "password": "adminpassword"}
    )
    if login_resp.status_code != 200:
        print("-> FAILED: Could not authenticate as admin")
        return
        
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Prepare dummy file content
    file_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog /Unique deduplication_test_123\n>>\nendobj\n"
    
    # 2. Upload file A
    print("[1] Uploading 'document_A.pdf'...")
    res1 = client.post(
        "/documents",
        headers=headers,
        data={
            "title": "Document Unique",
            "version": "1.0",
            "category": "manuel",
            "department": "Operations",
            "security_groups": ["default"]
        },
        files={"file": ("document_A.pdf", file_content, "application/pdf")}
    )
    
    if res1.status_code == 200:
        print("-> OK: File uploaded successfully.")
        doc_id = res1.json()["id"]
    else:
        print(f"-> FAILED: {res1.text}")
        return

    # 3. Check db total docs
    initial_count = db.query(Document).count()
    
    # 4. Upload exactly the same file A a second time
    print("\n[2] Uploading 'document_A.pdf' again...")
    res2 = client.post(
        "/documents",
        headers=headers,
        data={
            "title": "Document Unique Bis",
            "version": "1.1",
            "category": "manuel",
            "department": "Safety",
            "security_groups": ["default"]
        },
        files={"file": ("document_A.pdf", file_content, "application/pdf")}
    )
    
    if res2.status_code == 409:
        print(f"-> OK: Blocked successfully with message: {res2.json()['detail']}")
        if "Ce document existe déjà dans RailMind" in res2.json()['detail']:
            print("-> OK: Correct error message format.")
        else:
            print("-> FAILED: Incorrect error message format.")
    else:
        print(f"-> FAILED: Expected 409 Conflict, got {res2.status_code}")
        
    # 5. Check db total docs again
    final_count = db.query(Document).count()
    if initial_count == final_count:
        print("-> OK: Database doc count did not increase.")
    else:
        print("-> FAILED: Database doc count increased!")
        
    # 6. Upload the same file content with a different name
    print("\n[3] Uploading the same content as 'document_B.pdf'...")
    res3 = client.post(
        "/documents",
        headers=headers,
        data={
            "title": "Document Completement Different",
            "version": "1.0",
            "category": "manuel",
            "department": "Operations",
            "security_groups": ["default"]
        },
        files={"file": ("document_B.pdf", file_content, "application/pdf")}
    )
    
    if res3.status_code == 409:
        print(f"-> OK: Blocked successfully (content duplicate detected) with message: {res3.json()['detail']}")
    else:
        print(f"-> FAILED: Expected 409 Conflict, got {res3.status_code}")
        
    # 7. Upload a truly different file
    print("\n[4] Uploading a genuinely different file 'document_C.pdf'...")
    diff_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Page\n>>\nendobj\n"
    res4 = client.post(
        "/documents",
        headers=headers,
        data={
            "title": "Document C",
            "version": "1.0",
            "category": "manuel",
            "department": "Operations",
            "security_groups": ["default"]
        },
        files={"file": ("document_C.pdf", diff_content, "application/pdf")}
    )
    
    if res4.status_code == 200:
        print("-> OK: Different file uploaded successfully.")
        doc_c_id = res4.json()["id"]
    else:
        print(f"-> FAILED: {res4.text}")
        
    # Cleanup
    db.query(Document).filter(Document.id.in_([doc_id, doc_c_id])).delete(synchronize_session=False)
    db.commit()
    db.close()
    
    print("=" * 60)
    print("      ALL DEDUPLICATION TESTS COMPLETED!")
    print("=" * 60)

if __name__ == "__main__":
    run_deduplication_test()
