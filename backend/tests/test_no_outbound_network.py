"""
Test de conformité stricte et de non-fuite réseau pour CAMRAIL RailMind Lite.
Prouve qu'AUCUN appel réseau sortant vers l'extérieur n'est effectué en production.
Seuls localhost, 127.0.0.1, l'hôte de DATABASE_URL et l'hôte de OLLAMA_BASE_URL sont autorisés.
"""

import os
import socket
import unittest
from unittest.mock import patch
from urllib.parse import urlparse
import httpx
from fastapi.testclient import TestClient

# Forcer le mode hors-ligne pour Hugging Face
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.schemas import User, Document, DocumentPage, DocumentChunk
from app.services.indexing import index_document

client = TestClient(app)

class TestNoOutboundNetwork(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Calculer les hôtes autorisés
        cls.allowed_hosts = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "testserver"}
        
        db_url = getattr(settings, "DATABASE_URL", "")
        if db_url and "://" in db_url:
            try:
                db_host = urlparse(db_url).hostname
                if db_host:
                    cls.allowed_hosts.add(db_host.lower())
            except Exception:
                pass
                
        ollama_url = getattr(settings, "OLLAMA_BASE_URL", "")
        if ollama_url:
            try:
                o_host = urlparse(ollama_url).hostname
                if o_host:
                    cls.allowed_hosts.add(o_host.lower())
            except Exception:
                pass

        print(f"\n[SÉCURITÉ CAMRAIL] Hôtes réseau strictement autorisés : {cls.allowed_hosts}")

        cls.outbound_attempts = []
        cls.orig_socket_connect = socket.socket.connect
        cls.orig_create_connection = socket.create_connection
        cls.orig_httpx_send = httpx.Client.send

        def _is_host_allowed(host: str) -> bool:
            if not host:
                return True
            h = host.strip("[]").lower()
            return h in cls.allowed_hosts

        def guarded_connect(sock_self, address):
            host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
            if not _is_host_allowed(host):
                cls.outbound_attempts.append(host)
                raise PermissionError(
                    f"[VIOLATION CONFIDENTIALITÉ CAMRAIL] Appel sortant INTERDIT vers {host}:{address[1] if isinstance(address, tuple) and len(address)>1 else '?'}"
                )
            return cls.orig_socket_connect(sock_self, address)

        def guarded_create_connection(address, *args, **kwargs):
            host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
            if not _is_host_allowed(host):
                cls.outbound_attempts.append(host)
                raise PermissionError(
                    f"[VIOLATION CONFIDENTIALITÉ CAMRAIL] create_connection INTERDIT vers {host}"
                )
            return cls.orig_create_connection(address, *args, **kwargs)

        def guarded_httpx_send(client_self, request, *args, **kwargs):
            host = request.url.host
            if not _is_host_allowed(host):
                cls.outbound_attempts.append(host)
                raise PermissionError(
                    f"[VIOLATION CONFIDENTIALITÉ CAMRAIL] Requête HTTP sortante INTERDITE vers {host}"
                )
            return cls.orig_httpx_send(client_self, request, *args, **kwargs)

        # Installer les gardiens
        socket.socket.connect = guarded_connect
        socket.create_connection = guarded_create_connection
        httpx.Client.send = guarded_httpx_send

        try:
            import requests
            cls.orig_requests_send = requests.Session.send
            def guarded_requests_send(sess_self, request, *args, **kwargs):
                host = urlparse(request.url).hostname
                if not _is_host_allowed(host):
                    cls.outbound_attempts.append(host)
                    raise PermissionError(
                        f"[VIOLATION CONFIDENTIALITÉ CAMRAIL] Requête Requests sortante INTERDITE vers {host}"
                    )
                return cls.orig_requests_send(sess_self, request, *args, **kwargs)
            requests.Session.send = guarded_requests_send
        except ImportError:
            cls.orig_requests_send = None

    @classmethod
    def tearDownClass(cls):
        # Restaurer les méthodes originales
        socket.socket.connect = cls.orig_socket_connect
        socket.create_connection = cls.orig_create_connection
        httpx.Client.send = cls.orig_httpx_send
        if cls.orig_requests_send:
            import requests
            requests.Session.send = cls.orig_requests_send

    def setUp(self):
        from app.deps import get_current_user
        self.mock_user = User(id=1, email="securite@camrail.net", role="admin")
        app.dependency_overrides[get_current_user] = lambda: self.mock_user

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_1_guard_blocks_external_attempts(self):
        """Vérifie que le monkeypatch bloque immédiatement toute tentative sortante non autorisée."""
        with self.assertRaises(PermissionError):
            socket.create_connection(("google.com", 443), timeout=1.0)
        
        with self.assertRaises(PermissionError):
            with httpx.Client() as cl:
                cl.get("https://generativelanguage.googleapis.com")

        self.assertGreater(len(self.outbound_attempts), 0)
        self.outbound_attempts.clear()

    def test_2_full_nominal_pipeline_zero_outbound_network(self):
        """
        Parcours complet en circuit 100% fermé :
        1. Démarrage de l'app (déjà vérifié via client).
        2. Indexation d'un document démo (embeddings calculés localement via MODELS_DIR).
        3. Question posée à l'assistant et génération de la réponse.
        4. Vérification formelle qu'aucune tentative sortante interdite n'a eu lieu.
        """
        db = SessionLocal()
        test_doc_id = None
        try:
            # 1. Indexation d'un document de démonstration
            import uuid
            unique_token = uuid.uuid4().hex[:10]
            demo_doc = Document(
                title=f"Règlement de Sécurité Exploitation CAMRAIL Test {unique_token}",
                family_key=f"reglement_securite_test_{unique_token}",
                version="1.0",
                category="Securite",
                department="Exploitation",
                file_url=f"local://reglement_securite_test_{unique_token}.pdf",
                checksum=f"checksum_test_100_local_{unique_token}",
                uploaded_by=self.mock_user.id
            )
            db.add(demo_doc)
            db.commit()
            db.refresh(demo_doc)
            test_doc_id = demo_doc.id

            p1 = DocumentPage(
                document_id=demo_doc.id,
                page_number=1,
                extracted_text="CAMRAIL Sécurité Ferroviaire : La signalisation lumineuse commande la circulation des trains sur le réseau camerounais. "
                               "Tout agent de conduite doit respecter impérativement les signaux d'arrêt rouge absolu."
            )
            p2 = DocumentPage(
                document_id=demo_doc.id,
                page_number=2,
                extracted_text="En cas d'incident technique sur la voie ferrée entre Douala et Yaoundé, l'arrêt d'urgence est déclenché par le régulateur central."
            )
            db.add_all([p1, p2])
            db.commit()

            # Indexer le document (utilise les embeddings locaux depuis MODELS_DIR)
            num_chunks = index_document(demo_doc.id, db)
            print(f"\n  -> Document de test indexé avec succès en local ({num_chunks} chunks créés, zéro réseau).")

            # 2. Interrogation de l'assistant documentaire
            payload = {
                "query": "Quel signal commande l'arrêt absolu pour les trains CAMRAIL ?"
            }

            # Si Ollama n'est pas actif dans cet environnement de test, on mocke la réponse LLM
            # pour valider l'intégralité du pipeline applicatif sans dépendre d'un daemon externe
            def _ollama_or_mock(system_prompt, user_message):
                try:
                    r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=1.0)
                    if r.status_code == 200:
                        from app.services.generation import _generate_with_ollama
                        return _generate_with_ollama(system_prompt, user_message)
                except Exception:
                    pass
                return "Tout agent de conduite doit respecter impérativement les signaux d'arrêt rouge absolu [1]."

            with patch("app.services.generation._generate_with_ollama", side_effect=_ollama_or_mock):
                response = client.post("/assistant/query", json=payload)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertTrue(len(data["answer"]) > 0)
                self.assertIn(data.get("provider"), ["ollama", None])
                print(f"  -> Réponse générée : {data['answer'][:80]}...")
                print(f"  -> Citations trouvées : {len(data.get('citations', []))}")

            # 3. Vérification formelle : AUCUN appel sortant
            self.assertEqual(
                len(self.outbound_attempts), 0,
                f"Tentatives sortantes non autorisées détectées : {self.outbound_attempts}"
            )
            print("  -> SUCCÈS : 0 tentative réseau sortante détectée pendant tout le parcours.")

        finally:
            if test_doc_id:
                db.query(DocumentChunk).filter(DocumentChunk.document_id == test_doc_id).delete()
                db.query(DocumentPage).filter(DocumentPage.document_id == test_doc_id).delete()
                db.query(Document).filter(Document.id == test_doc_id).delete()
                db.commit()
            db.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
