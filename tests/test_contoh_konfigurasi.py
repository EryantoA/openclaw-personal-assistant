"""openclaw.json.example harus tetap JSON sah dan memuat pengaturan yang kita butuhkan (ADR-0025).

    python3 -m unittest tests/test_contoh_konfigurasi.py
"""
import json
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
CONTOH = json.loads((AKAR / "openclaw.json.example").read_text(encoding="utf-8"))


class ResetSesiGrup(unittest.TestCase):
    def test_sesi_grup_reset_setelah_dua_jam_tak_aktif(self):
        # Sesi grup yang panjang membuat bot meniru balasan lamanya dan mengabaikan AGENTS.md.
        # Skema OpenClaw menolak kunci komentar di blok session, jadi alasannya ada di ADR-0025.
        grup = CONTOH["session"]["resetByType"]["group"]
        self.assertEqual(grup, {"mode": "idle", "idleMinutes": 120})

    def test_alasan_tercatat_di_adr(self):
        adr = list((AKAR / "docs" / "adr").glob("0025-*.md"))
        self.assertEqual(len(adr), 1)
        self.assertIn("idleMinutes", adr[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
