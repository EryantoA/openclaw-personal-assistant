"""README dan contoh konfigurasi mengikuti setup yang berjalan: login Claude, bukan kunci API.

    python3 -m unittest tests/test_readme_model.py

Sebelumnya keduanya menulis Groq llama sebagai model utama dengan DeepSeek dan Claude Sonnet sebagai
cadangan, padahal `openclaw models status` menunjukkan Claude Haiku 4.5 dan Opus 4.7 (1 Nov 2026).
"""
import json
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
CONTOH = json.loads((AKAR / "openclaw.json.example").read_text(encoding="utf-8"))
README = (AKAR / "README.md").read_text(encoding="utf-8")


class ModelSebenarnya(unittest.TestCase):
    def test_contoh_memakai_model_dan_cadangan_yang_berjalan(self):
        model = CONTOH["agents"]["defaults"]["model"]
        self.assertEqual(model["primary"], "anthropic/claude-haiku-4-5")
        self.assertEqual(model["fallbacks"], ["anthropic/claude-opus-4-7"])

    def test_contoh_tanpa_kunci_api_lama(self):
        self.assertEqual(CONTOH.get("env", {}), {})

    def test_readme_tidak_lagi_menyebut_kunci_atau_model_lama(self):
        for lama in ("GROQ_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "llama-3.3-70b-versatile",
                     "deepseek-chat", "claude-sonnet-4-6", "console.groq.com"):
            self.assertNotIn(lama, README)

    def test_readme_menyebut_model_dan_login_yang_berjalan(self):
        self.assertIn("anthropic/claude-haiku-4-5", README)
        self.assertIn("anthropic/claude-opus-4-7", README)
        self.assertIn("login Claude", README)
        self.assertIn("openclaw models status", README)

    def test_nomor_langkah_berurutan(self):
        import re
        nomor = [int(n) for n in re.findall(r"^### Step (\d+) ", README, flags=re.M)]
        self.assertEqual(nomor, list(range(1, len(nomor) + 1)))


if __name__ == "__main__":
    unittest.main()
