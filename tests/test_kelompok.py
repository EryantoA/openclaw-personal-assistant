"""Tes scripts/kelompok.py — Kelompok Kategori untuk tampilan (ADR-0030).

    python3 -m unittest tests/test_kelompok.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import kelompok  # noqa: E402

ATUR = {"kelompok_kategori": {"Kebutuhan Pokok": ["food", "groceries"], "Gaya Hidup": ["shopping"]}}


class Komposisi(unittest.TestCase):
    def test_persen_per_kelompok_dan_sisanya_lainnya(self):
        per = {"food": 500_000, "groceries": 300_000, "shopping": 150_000, "other": 50_000}
        self.assertEqual(kelompok.komposisi(per, ATUR),
                         [("Kebutuhan Pokok", 800_000), ("Gaya Hidup", 150_000), ("Lainnya", 50_000)])
        self.assertEqual(kelompok.baris_laporan(per, ATUR),
                         "🧭 Kebutuhan Pokok 80% · Gaya Hidup 15% · Lainnya 5%")

    def test_kelompok_tanpa_pengeluaran_tidak_disebut(self):
        self.assertEqual(kelompok.baris_laporan({"food": 100}, ATUR), "🧭 Kebutuhan Pokok 100%")

    def test_tanpa_pengaturan_atau_tanpa_pengeluaran_tidak_ada_baris(self):
        self.assertIsNone(kelompok.baris_laporan({"food": 100}, {}))
        self.assertIsNone(kelompok.baris_laporan({}, ATUR))

    def test_slug_di_dua_kelompok_ikut_yang_pertama(self):
        atur = {"kelompok_kategori": {"A": ["food"], "B": ["food"]}}
        self.assertEqual(kelompok.peta(atur), {"food": "A"})


if __name__ == "__main__":
    unittest.main()
