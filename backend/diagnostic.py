import os
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.schemas import Document, DocumentChunk

def run_diagnostic():
    db = SessionLocal()
    report = {}
    try:
        # A. État du document
        doc = db.query(Document).filter(Document.title.ilike("%Formation_Java%")).first()
        if doc:
            report['document'] = {
                'exists': True,
                'id': doc.id,
                'title': doc.title,
                'status': doc.status,
                'department': doc.department,
                'category': doc.category,
                'security_groups': [sg.name for sg in doc.security_groups]
            }
        else:
            report['document'] = {'exists': False}
            print(json.dumps(report, indent=2))
            return
            
        # B & C. Extraction & Chunks
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        report['chunks'] = {
            'count': len(chunks),
            'heritage_mention': False,
            'heritage_chunks': []
        }
        
        for c in chunks:
            if 'heritage' in c.content.lower() or 'héritage' in c.content.lower():
                report['chunks']['heritage_mention'] = True
                report['chunks']['heritage_chunks'].append(c.content[:100] + "...")
                
        # D. Embeddings
        report['embeddings'] = {
            'all_have_embeddings': all(c.embedding is not None for c in chunks) if chunks else False,
            'embedding_dim': len(chunks[0].embedding) if chunks and chunks[0].embedding else None
        }
        
        # E. Résultat hybrid_search() direct test
        from app.models.schemas import User
        user = db.query(User).filter(User.email == "docadmin@camrail.net").first()
        if user:
            report['user'] = {
                'email': user.email,
                'role': user.role,
                'department': user.department,
                'security_groups': [sg.name for sg in user.security_groups]
            }
        else:
            report['user'] = {'exists': False}

        from app.services.retrieval import hybrid_search
        query_text = "a quoi sert l'heritage en java"
        
        # Test exact behavior of assistant_query
        try:
            results_auth = hybrid_search(
                db=db, 
                query=query_text, 
                top_k=5,
                security_groups=report['user'].get('security_groups', [])
            )
            report['hybrid_search_with_auth'] = [{
                'doc_title': r.get('document_title'),
                'score': r.get('score'),
                'vector_distance': r.get('vector_distance')
            } for r in results_auth]
        except Exception as e:
            report['hybrid_search_with_auth'] = f"Error: {str(e)}"
            
    finally:
        db.close()
        
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    run_diagnostic()
