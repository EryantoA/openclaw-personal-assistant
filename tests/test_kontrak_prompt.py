"""Tes kontrak prompt: AGENTS.md selalu masuk prompt bot, jadi aturannya harus ada di sana.

    python3 -m unittest tests/test_kontrak_prompt.py

Hanya membuktikan teks kontrak ada dan tidak bertentangan, bukan bahwa model patuh (ADR-0014).
"""
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
AGENTS = (AKAR / "AGENTS.md").read_text(encoding="utf-8")
SKILL = (AKAR / "skills" / "bill-tracker" / "SKILL.md").read_text(encoding="utf-8")

KERANGKA_AKHIR = "✅ Sudah dicatat!"
KERANGKA_KONFIRMASI = "🧾 Bukti transfer terbaca (belum dicatat)"


class KontrakBuktiTransfer(unittest.TestCase):
    def test_konfirmasi_dan_balasan_akhir_didefinisikan_di_agents(self):
        self.assertEqual(AGENTS.count(KERANGKA_KONFIRMASI), 1)
        self.assertIn(KERANGKA_AKHIR, AGENTS)

    def test_ada_pengecualian_untuk_aturan_langsung_catat(self):
        self.assertIn("Bukti Transfer: PENGECUALIAN", AGENTS)
        self.assertIn("kecuali Bukti Transfer", AGENTS)
        self.assertIn("JANGAN jalankan `catat.py`", AGENTS)

    def test_larangan_tertulis(self):
        self.assertIn("nama orang bukan akun", AGENTS)
        self.assertIn("MENANG-", AGENTS)  # contoh awalan karangan yang dilarang
        self.assertIn("N entri tercatat", AGENTS)
        self.assertIn("STRUK-<nomor referensi>", AGENTS)

    def test_skill_tidak_mendefinisikan_kerangka_konfirmasi_sendiri(self):
        self.assertNotIn(KERANGKA_KONFIRMASI, SKILL)
        self.assertIn("hanya di `AGENTS.md`", SKILL)

    def test_kerangka_akhir_sama_di_skill_dan_agents(self):
        for teks in (AGENTS, SKILL):
            self.assertIn(KERANGKA_AKHIR + "\n\nStruk: ", teks)


if __name__ == "__main__":
    unittest.main()
