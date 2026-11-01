"""Tes scripts/tampilan.py — format yang dipakai bersama (rupiah, nama bulan).

    python3 -m unittest tests/test_tampilan.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import tampilan  # noqa: E402


class Rupiah(unittest.TestCase):
    def test_titik_ribuan_dan_tanda_minus_di_depan(self):
        self.assertEqual(tampilan.rp(7_754_771), "Rp 7.754.771")
        self.assertEqual(tampilan.rp(0), "Rp 0")
        self.assertEqual(tampilan.rp(-432_771), "-Rp 432.771")

    def test_pecahan_dibulatkan(self):
        self.assertEqual(tampilan.rp(1234.6), "Rp 1.235")


class NamaBulan(unittest.TestCase):
    def test_nama_indonesia_bukan_inggris(self):
        self.assertEqual(tampilan.nama_bulan("2026-10"), "Oktober 2026")
        self.assertEqual(tampilan.nama_bulan("2026-01"), "Januari 2026")
        self.assertEqual(tampilan.nama_bulan("2026-12"), "Desember 2026")


if __name__ == "__main__":
    unittest.main()
