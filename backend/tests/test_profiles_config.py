"""
Test unitaire validant l'intégrité et la conformité des profils d'environnement.
Vérifie que :
1. Chaque profil (profile-A-cpu.env, profile-B-cpu-puissant.env, profile-C-gpu.env) existe.
2. Toutes les variables définies dans chaque profil existent réellement dans Settings (app.config).
3. Aucune variable obsolète ou orpheline n'est présente.
4. Aucun token d'API cloud externe (OpenAI, Claude, Google) n'est présent.
"""

import os
import unittest
from app.config import Settings

class TestProfilesConfig(unittest.TestCase):
    def setUp(self):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.profiles_dir = os.path.join(backend_dir, "env-profiles")
        self.profile_files = [
            "profile-A-cpu.env",
            "profile-B-cpu-puissant.env",
            "profile-C-gpu.env"
        ]
        self.allowed_fields = set(Settings.model_fields.keys())

    def test_profiles_exist(self):
        """Vérifie l'existence physique des 3 fichiers de profil."""
        for pf in self.profile_files:
            p_path = os.path.join(self.profiles_dir, pf)
            self.assertTrue(os.path.exists(p_path), f"Le profil {pf} doit exister dans {self.profiles_dir}")

    def test_all_profile_vars_exist_in_settings(self):
        """Vérifie que chaque variable de chaque profil est déclarée dans Settings."""
        for pf in self.profile_files:
            p_path = os.path.join(self.profiles_dir, pf)
            with open(p_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        var_name = line.split("=", 1)[0].strip()
                        self.assertIn(
                            var_name,
                            self.allowed_fields,
                            f"Variable inconnue '{var_name}' trouvée dans {pf}:{line_num}. "
                            f"Elle doit être déclarée dans Settings (config.py)."
                        )

    def test_no_external_cloud_keys(self):
        """Vérifie l'absence absolue de clés ou mentions d'API externes dans les profils."""
        forbidden_keywords = ["openai", "anthropic", "google_api_key", "claude"]
        for pf in self.profile_files:
            p_path = os.path.join(self.profiles_dir, pf)
            with open(p_path, "r", encoding="utf-8") as f:
                content = f.read().lower()
                for kw in forbidden_keywords:
                    self.assertNotIn(
                        kw,
                        content,
                        f"Mot-clé interdit '{kw}' trouvé dans le profil souverain {pf}."
                    )

if __name__ == "__main__":
    unittest.main()
