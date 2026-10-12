import unittest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.evidence import select_evidence, _split_into_units
from app.services.generation import extract_and_filter_citations

class TestEvidenceSelection(unittest.TestCase):

    def test_split_into_units_sentences_and_tables(self):
        content = (
            "Article 1. Les circulations sont reglementees.\n"
            "| Train | Vitesse Max | Ligne |\n"
            "| 101 | 90 km/h | Douala-Yaounde |\n"
            "| 102 | 70 km/h | Belabo-Ngaoundere |\n"
            "Fin de l'article."
        )
        units = _split_into_units(content)
        unit_texts = [u for u, _ in units]
        
        # Check table rows are separate atomic units
        self.assertIn("| 101 | 90 km/h | Douala-Yaounde |", unit_texts)
        self.assertIn("| 102 | 70 km/h | Belabo-Ngaoundere |", unit_texts)
        # Check sentence with Article prefix is kept as a single atomic unit
        self.assertTrue(any("Article 1. Les circulations sont reglementees." in u for u in unit_texts))

    def test_select_evidence_substring_and_cross_page(self):
        # Chunk spanning across page 4 and page 5
        p4_text = "Chapitre 1. Le personnel de traction respecte la signalisation lumineuse."
        p5_text = " En cas de franchissement indu d'un signal d'arret, le conducteur declenche immediatement l'arret d'urgence."
        full_content = p4_text + p5_text
        
        chunk = {
            "content": full_content,
            "page_start": 4,
            "page_end": 5,
            "segments": [
                {"char_start": 0, "char_end": len(p4_text), "page_number": 4},
                {"char_start": len(p4_text) + 1, "char_end": len(full_content), "page_number": 5}
            ]
        }
        
        claim = "Le conducteur declenche l'arret d'urgence en cas de franchissement d'un signal d'arret."
        evidence = select_evidence(chunk, claim, max_units=2)
        
        self.assertGreaterEqual(len(evidence), 1)
        for ev in evidence:
            # 1. Evidence text must be an exact substring of the original chunk content
            self.assertIn(ev["text"], full_content)
            # 2. Must not end with "..."
            self.assertFalse(ev["text"].endswith("..."))
        
        # Unit containing the specific claim about arret d'urgence on page 5
        p5_ev = next((e for e in evidence if "arret d'urgence" in e["text"].lower()), None)
        self.assertIsNotNone(p5_ev)
        self.assertEqual(p5_ev["page_number"], 5)

    def test_select_evidence_table_row_unit(self):
        table_content = (
            "Prescriptions de vitesse :\n"
            "| Type Engin | Vitesse Limite |\n"
            "| CC 2200 | 80 km/h |\n"
            "| BB 1200 | 60 km/h |\n"
        )
        chunk = {
            "content": table_content,
            "page_start": 3,
            "page_end": 3,
            "segments": [{"char_start": 0, "char_end": len(table_content), "page_number": 3}]
        }
        
        claim = "Quelle est la vitesse limite pour les engins BB 1200 ?"
        evidence = select_evidence(chunk, claim, max_units=1)
        
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["text"], "| BB 1200 | 60 km/h |")
        self.assertEqual(evidence[0]["page_number"], 3)
        self.assertFalse(evidence[0]["text"].endswith("..."))

    def test_citation_never_adds_ellipsis(self):
        content = "Le present reglement s'applique a l'ensemble du reseau ferroviaire national gere par CAMRAIL."
        chunk = {
            "content": content,
            "page_start": 1,
            "page_end": 1,
            "segments": [{"char_start": 0, "char_end": len(content), "page_number": 1}]
        }
        evidence = select_evidence(chunk, "reseau ferroviaire", max_units=1)
        self.assertEqual(len(evidence), 1)
        self.assertNotIn("...", evidence[0]["text"])

if __name__ == "__main__":
    unittest.main()
