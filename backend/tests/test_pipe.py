from app.database import SessionLocal
from app.services.retrieval import hybrid_search
from app.services.generation import generate_answer

def test():
    db = SessionLocal()
    query = "En quoi consiste la maintenance préventive selon les procédures ?"
    
    print("1. Testing Hybrid Search...")
    search_results = hybrid_search(
        db=db,
        query=query,
        top_k=5,
        department=None,
        category=None,
        security_groups=["public", "engineering", "admin"]
    )
    
    print(f"Found {len(search_results)} results.")
    if len(search_results) > 0:
        print(f"Top result score: {search_results[0].get('score')} | vector_dist: {search_results[0].get('vector_distance')}")
    else:
        print("No results found. This explains empty answers.")
        return

    print("2. Testing Generation...")
    try:
        gen_result = generate_answer(
            query=query,
            search_results=search_results,
            language="fr"
        )
        print("Generation successful.")
        print("Answer:", gen_result.get("answer"))
        print("Confidence:", gen_result.get("confidence"))
        print("Citations:", gen_result.get("citations"))
    except Exception as e:
        print("Generation failed:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
