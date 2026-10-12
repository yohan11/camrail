#!/usr/bin/env python3
"""
Script de réindexation globale de tous les documents actifs dans RailMind Lite.
Pour chaque document actif :
1. Supprime les chunks existants.
2. Relance process_document (avec pagination virtuelle DOCX si applicable).
3. Met à jour les DocumentPages en base.
4. Relance index_document (chunking multi-pages fidèle sans coupe de blocs).
5. Affiche un récapitulatif clair et non-interactif.
"""

import os
import sys
import time

# Ensure backend root is on sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.database import SessionLocal
from app.models.schemas import Document, DocumentChunk, DocumentPage
from app.services.document_processor import process_document
from app.services.indexing import index_document


def reindex_all_active_documents():
    db = SessionLocal()
    start_time = time.time()
    
    print("=" * 70)
    print("      RAILMIND LITE - REINDEXATION GLOBALE DES DOCUMENTS ACTIFS")
    print("=" * 70)

    active_docs = (
        db.query(Document)
        .filter(Document.status == "active")
        .order_by(Document.id.asc())
        .all()
    )

    total_active = len(active_docs)
    print(f"[*] Documents actifs détectés : {total_active}")

    processed_count = 0
    total_chunks_created = 0
    errors = []

    for i, doc in enumerate(active_docs, start=1):
        doc_id = doc.id
        doc_title = doc.title
        file_path = doc.file_url

        print(f"\n[{i}/{total_active}] Traitement Doc ID {doc_id} : '{doc_title}'...")

        if not file_path or not os.path.exists(file_path):
            err_msg = f"Fichier introuvable sur le disque : {file_path}"
            print(f"  [!] ERREUR : {err_msg}")
            errors.append((doc_id, doc_title, err_msg))
            continue

        try:
            # 1. Supprimer les chunks existants
            deleted_chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
            # 2. Supprimer les pages existantes pour reconstruire la pagination virtuelle
            deleted_pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc_id).delete()
            db.commit()

            # 3. Relancer process_document
            ext = os.path.splitext(file_path)[1]
            pages_data = process_document(file_path, ext)
            
            # 4. Enregistrer les nouvelles DocumentPages
            for p in pages_data:
                page_obj = DocumentPage(
                    document_id=doc_id,
                    page_number=p["page_number"],
                    extracted_text=p["text"],
                    extraction_method=p.get("method", "native")
                )
                db.add(page_obj)
            db.commit()

            # 5. Relancer index_document
            created_chunks = index_document(doc_id, db)

            processed_count += 1
            total_chunks_created += created_chunks
            print(f"  -> OK : {len(pages_data)} page(s) extraite(s), {created_chunks} chunk(s) indexé(s).")

        except Exception as e:
            db.rollback()
            err_msg = str(e)
            print(f"  [!] ERREUR lors de la réindexation : {err_msg}")
            errors.append((doc_id, doc_title, err_msg))

    db.close()
    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("                     RÉCAPITULATIF DE RÉINDEXATION")
    print("=" * 70)
    print(f"Documents actifs trouvés   : {total_active}")
    print(f"Documents traités avec succès: {processed_count}")
    print(f"Total chunks créés en base : {total_chunks_created}")
    print(f"Total erreurs rencontrées  : {len(errors)}")
    print(f"Temps d'exécution total    : {elapsed:.2f} secondes")
    
    if errors:
        print("\nDétail des erreurs :")
        for err_id, err_title, err_desc in errors:
            print(f"  - Doc ID {err_id} ({err_title}) : {err_desc}")
    print("=" * 70)

    return {
        "total_active": total_active,
        "processed_count": processed_count,
        "total_chunks_created": total_chunks_created,
        "errors": errors
    }


if __name__ == "__main__":
    reindex_all_active_documents()
