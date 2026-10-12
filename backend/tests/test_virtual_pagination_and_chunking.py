import os
import sys
import random
from docx import Document as DocxDocument

# Ensure backend root is on sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.database import SessionLocal
from app.models.schemas import Document, DocumentPage
from app.services.document_processor import extract_docx
from app.services.indexing import chunk_pages_across_boundaries


def test_docx_virtual_pagination_large():
    print("\n--- TEST 1: DOCX > 900 mots (multiples pages virtuelles, tableau intact) ---")
    tmp_path = os.path.join(backend_root, "scratch", "tmp_test_large.docx")
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
    
    doc = DocxDocument()
    # Add paragraphs totaling ~700 words
    for i in range(7):
        doc.add_paragraph(f"Paragraphe {i}: " + ("Ce texte ferroviaire est concu pour enrichir le document avec de nombreux termes techniques. " * 8))
        
    # Add a table with ~150 words
    table = doc.add_table(rows=4, cols=3)
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.text = f"Donnee Ferroviaire Ligne {r_idx} Col {c_idx} avec details et specifications precises"
            
    # Add another paragraph ~200 words
    doc.add_paragraph("Dernier paragraphe de cloture : " + ("Verification des procedes et consignes reglementaires de securite en gare et sur voie. " * 15))
    doc.save(tmp_path)

    pages = extract_docx(tmp_path)
    print(f"Pages générées : {len(pages)}")
    assert len(pages) > 1, f"Attendu > 1 page, obtenu {len(pages)}"
    
    for p in pages:
        assert p["method"] == "virtual_pagination", f"Attendu 'virtual_pagination', obtenu {p['method']}"
        assert p["page_number"] >= 1
        
    # Vérifier que le tableau markdown n'est pas coupé en morceaux sur deux pages différentes
    table_start = "Donnee Ferroviaire Ligne 0 Col 0"
    table_end = "Donnee Ferroviaire Ligne 3 Col 2"
    
    table_found_on_page = None
    for p in pages:
        if table_start in p["text"]:
            assert table_end in p["text"], "Le tableau a été coupé entre plusieurs pages virtuelles !"
            table_found_on_page = p["page_number"]
            
    assert table_found_on_page is not None, "Tableau non trouvé dans les pages extraites !"
    print(f"-> Succès : {len(pages)} pages virtuelles générées, tableau complet préservé sur la page {table_found_on_page}.")

    if os.path.exists(tmp_path):
        os.remove(tmp_path)


def test_docx_virtual_pagination_small():
    print("\n--- TEST 2: DOCX < 450 mots (1 page, method == 'native') ---")
    tmp_path = os.path.join(backend_root, "scratch", "tmp_test_small.docx")
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
    
    doc = DocxDocument()
    # Add paragraphs totaling ~150 words
    doc.add_paragraph("Document court pour tester la pagination native : " + ("Voici un contenu concis pour l'aiguillage ferroviaire. " * 15))
    doc.save(tmp_path)

    pages = extract_docx(tmp_path)
    print(f"Pages générées : {len(pages)}")
    assert len(pages) == 1, f"Attendu 1 page, obtenu {len(pages)}"
    assert pages[0]["method"] == "native", f"Attendu 'native', obtenu {pages[0]['method']}"
    assert pages[0]["page_number"] == 1
    print("-> Succès : 1 page générée avec method == 'native'.")

    if os.path.exists(tmp_path):
        os.remove(tmp_path)


def test_chunking_cross_page_boundaries():
    print("\n--- TEST 3: Phrase / bloc traversant deux pages (page_start=1, page_end=2) ---")
    mock_pages = [
        {"page_number": 1, "text": "Premiere page avec une introduction ferroviaire sur la ligne Douala Yaounde."},
        {"page_number": 2, "text": "Seconde page contenant la suite directe des procedures d'exploitation et de signalisation."}
    ]
    # Chunk size large enough to hold both short blocks (150 words)
    chunks = chunk_pages_across_boundaries(mock_pages, chunk_size_words=150, overlap_words=30)
    print(f"Chunks générés : {len(chunks)}")
    
    cross_page_chunk = None
    for c in chunks:
        if c["page_start"] == 1 and c["page_end"] == 2:
            cross_page_chunk = c
            break

    assert cross_page_chunk is not None, "Aucun chunk n'a traversé les deux pages (page_start=1, page_end=2) !"
    assert "Premiere page" in cross_page_chunk["text"]
    assert "Seconde page" in cross_page_chunk["text"]
    print("-> Succès : Chunk multi-pages trouvé avec page_start=1 et page_end=2.")


def test_substring_fidelity_and_segments():
    print("\n--- TEST 4: Fidélité de sous-chaîne exacte et couverture des segments ---")
    # Créer du contenu suffisant pour générer au moins 4-5 chunks avec chunk_size_words=50
    mock_pages = [
        {
            "page_number": 1,
            "text": "Paragraphe Alpha concernant les consignes strictes de maintenance ferroviaire sur le troncon central.\n\n"
                    "Paragraphe Beta decrivant les seuils d'alerte et de vitesse maximale autorisee pour les trains de fret lourd."
        },
        {
            "page_number": 2,
            "text": "Paragraphe Gamma sur l'inspection visuelle des traverses en beton arme et des rails eclisses.\n\n"
                    "| Equipement | Etat | Observation |\n|---|---|---|\n| Aiguillage A1 | Conforme | Verification mensuelle validee |\n| Signal S3 | Fonctionnel | Lampe remplacee en gare |"
        },
        {
            "page_number": 3,
            "text": "Paragraphe Delta relatif aux communications d'urgence par radio VHF entre conducteurs et chefs de gare.\n\n"
                    "Paragraphe Epsilon resumant les regles de securite du personnel travaillant a proximite des voies principales.\n\n"
                    "Paragraphe Zeta pour la transmission des rapports d'incidents d'exploitation a la direction technique."
        }
    ]

    chunks = chunk_pages_across_boundaries(mock_pages, chunk_size_words=40, overlap_words=15)
    print(f"Total chunks générés : {len(chunks)}")
    assert len(chunks) >= 3, f"Attendu >= 3 chunks, obtenu {len(chunks)}"

    # Tester 3 chunks au hasard
    sample_chunks = random.sample(chunks, 3)

    page_map = {p["page_number"]: p["text"] for p in mock_pages}

    for idx, c in enumerate(sample_chunks, start=1):
        c_text = c["text"]
        segments = c["segments"]
        assert len(segments) > 0, f"Le chunk {idx} ne possède aucun segment !"

        reconstructed_blocks = []
        for seg in segments:
            p_num = seg["page_number"]
            start = seg["char_start"]
            end = seg["char_end"]
            
            # 1. Vérifier que les bornes de caractères sont valides dans le chunk
            assert 0 <= start < end <= len(c_text), f"Bornes de segment invalides : {start} -> {end} (len {len(c_text)})"
            
            # 2. Vérifier que la tranche dans le chunk est une sous-chaîne exacte du texte de la page d'origine
            block_in_chunk = c_text[start:end]
            reconstructed_blocks.append(block_in_chunk)
            
            orig_page_text = page_map[p_num]
            assert block_in_chunk in orig_page_text, (
                f"Le bloc '{block_in_chunk}' n'est pas une sous-chaîne exacte de la page {p_num} !\n"
                f"Texte d'origine : '{orig_page_text}'"
            )

        # 3. Vérifier que la concaténation par "\n\n" correspond exactement au texte du chunk
        assert "\n\n".join(reconstructed_blocks) == c_text, "La couverture des segments ne reconstitue pas exactement le chunk !"

    print("-> Succès : Tous les blocs des 3 chunks testés au hasard sont des sous-chaînes exactes et les segments couvrent fidèlement le texte.")


def test_document_pages_order_by():
    print("\n--- TEST 5: Document.pages toujours trié par page_number.asc() ---")
    db = SessionLocal()
    try:
        # Créer un document temporaire
        doc = Document(
            title="Temp Test Ordering",
            version="1.0",
            category="test",
            department="Operations",
            checksum="test_order_checksum_" + str(random.randint(100000, 999999)),
            uploaded_by=1,
            status="testing"
        )
        db.add(doc)
        db.flush()

        # Insérer les pages volontairement dans le désordre (4, 1, 3, 2)
        pages_to_add = [
            DocumentPage(document_id=doc.id, page_number=4, extracted_text="Page 4"),
            DocumentPage(document_id=doc.id, page_number=1, extracted_text="Page 1"),
            DocumentPage(document_id=doc.id, page_number=3, extracted_text="Page 3"),
            DocumentPage(document_id=doc.id, page_number=2, extracted_text="Page 2")
        ]
        db.add_all(pages_to_add)
        db.commit()

        # Recharger le document et inspecter l'ordre des pages via la relationship
        doc_reloaded = db.query(Document).filter(Document.id == doc.id).first()
        page_numbers = [p.page_number for p in doc_reloaded.pages]
        print(f"Ordre récupéré : {page_numbers}")
        assert page_numbers == [1, 2, 3, 4], f"Attendu [1, 2, 3, 4], obtenu {page_numbers}"
        print("-> Succès : Document.pages est rigoureusement trié par page_number ascendant.")

        # Nettoyage
        db.delete(doc_reloaded)
        db.commit()
    finally:
        db.close()


def run_all_tests():
    print("=" * 70)
    print("   TESTS PAGINATION VIRTUELLE DOCX & CHUNKING MULTI-PAGES FIDÈLE")
    print("=" * 70)
    test_docx_virtual_pagination_large()
    test_docx_virtual_pagination_small()
    test_chunking_cross_page_boundaries()
    test_substring_fidelity_and_segments()
    test_document_pages_order_by()
    print("\n" + "=" * 70)
    print("   TOUS LES 5 TESTS DE VALIDATION ONT RÉUSSI AVEC SUCCÈS (5/5) !")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
