import pytest
import numpy as np
import importlib
import sys

def test_lazy_loading_embedding_model():
    """
    Vérifie que le modèle SentenceTransformer n'est PAS chargé à l'import des modules
    indexing, retrieval ou generation, mais uniquement lors du premier appel d'embedding.
    """
    # Réinitialiser _model si déjà chargé pour le test d'isolation
    import app.services.indexing as idx_mod
    idx_mod._model = None
    
    # Importer retrieval et generation ne doit pas charger _model
    import app.services.retrieval as ret_mod
    import app.services.generation as gen_mod
    
    assert idx_mod._model is None, "Le modèle SentenceTransformer ne doit pas être chargé à l'import !"
    
    # Le premier appel à get_embedding_model() charge le modèle
    model = idx_mod.get_embedding_model()
    assert model is not None, "Le modèle doit être chargé après get_embedding_model()"
    assert idx_mod._model is not None, "Le singleton _model doit être mis en cache"
    
    # Assertions dimension et max_seq_length
    assert model.get_sentence_embedding_dimension() == 384, "La dimension doit être exactement 384"
    assert model.max_seq_length == 512, "max_seq_length doit être fixé à 512 pour e5"

def test_embed_text_prefixes_and_normalization():
    """
    Vérifie que embed_text et embed_texts préfixent obligatoirement query/passage,
    retournent 384 dimensions, et que les vecteurs sont strictement normalisés (norme L2 == 1.0).
    """
    from app.services.indexing import embed_text, embed_texts
    
    # 1. Test passage embedding
    passage_emb = embed_text("Une voie ferrée se compose de rails et de traverses.", kind="passage")
    assert isinstance(passage_emb, list)
    assert len(passage_emb) == 384
    norm_p = np.linalg.norm(passage_emb)
    assert np.isclose(norm_p, 1.0, atol=1e-3), f"Le vecteur passage doit être normalisé, norme = {norm_p}"
    
    # 2. Test query embedding
    query_emb = embed_text("Quels éléments composent une voie ferrée ?", kind="query")
    assert isinstance(query_emb, list)
    assert len(query_emb) == 384
    norm_q = np.linalg.norm(query_emb)
    assert np.isclose(norm_q, 1.0, atol=1e-3), f"Le vecteur query doit être normalisé, norme = {norm_q}"
    
    # 3. Test invalid kind raises ValueError
    with pytest.raises(ValueError):
        embed_text("texte sans prefixe valide", kind="invalide")
        
    # 4. Test batch embed_texts
    texts = ["Premier chunk documentaire ferroviaire.", "Second chunk relatif à la signalisation."]
    batch_embs = embed_texts(texts, kind="passage")
    assert len(batch_embs) == 2
    for emb in batch_embs:
        assert len(emb) == 384
        assert np.isclose(np.linalg.norm(emb), 1.0, atol=1e-3)

def test_evidence_selection_e5_compatible():
    """
    Vérifie que select_evidence fonctionne avec le nouveau modèle lazy loading et les préfixes e5.
    """
    from app.services.evidence import select_evidence
    
    chunk_dict = {
        "content": "La vitesse maximale sur LGV est de 320 km/h. En voie classique, elle est limitée à 160 km/h.",
        "page_start": 2,
        "segments": [
            {"page_number": 2, "char_start": 0, "char_end": 120}
        ]
    }
    
    units = select_evidence(chunk_dict, "Quelle est la vitesse sur ligne à grande vitesse ?")
    assert len(units) > 0, "select_evidence doit renvoyer au moins une unité"
    assert "LGV" in units[0]["text"] or "320" in units[0]["text"]
    assert units[0]["page_number"] == 2
    assert not units[0]["text"].endswith("..."), "L'unité ne doit pas comporter de points de suspension artificiels"

def test_pipeline_e2e_search_and_generation():
    """
    Vérifie le pipeline complet (recherche hybride -> génération avec citations)
    sur la base de données de démo active.
    """
    from app.database import SessionLocal
    from app.services.retrieval import hybrid_search
    from app.services.generation import generate_answer
    
    db = SessionLocal()
    try:
        results = hybrid_search(db=db, query="voie ferrée", top_k=5)
        assert len(results) > 0, "hybrid_search doit renvoyer des résultats sur le corpus indexé"
        
        top_res = results[0]
        assert "document_title" in top_res
        assert top_res.get("vector_distance") is not None
        
        # Test generation
        gen_res = generate_answer("Qu'est-ce qu'une voie ferrée ?", results, language="fr")
        assert "answer" in gen_res
        assert "citations" in gen_res
        assert gen_res["confidence"] in ["high", "medium"]
    finally:
        db.close()
