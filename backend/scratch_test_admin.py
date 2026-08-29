import os
os.environ["HF_HUB_OFFLINE"] = "1"
from app.database import SessionLocal
from app.services.retrieval import hybrid_search

def test():
    db = SessionLocal()
    query = "At what speed is a train classified as high speed?"
    
    print("Testing Hybrid Search with None security groups...")
    search_results = hybrid_search(
        db=db,
        query=query,
        top_k=10,
        department=None,
        category=None,
        security_groups=None
    )
    
    print(f"Found {len(search_results)} results.")
    for res in search_results:
        print(f"- Doc {res.get('document_id')} | Score: {res.get('score')} | Distance: {res.get('vector_distance')} | Excerpt: {res.get('excerpt')[:100]}...")

if __name__ == "__main__":
    test()
