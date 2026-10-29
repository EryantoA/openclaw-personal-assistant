"""Tes scripts/periode.py — Pekan (CONTEXT.md, ADR-0013) dan bulan.

    python3 -m unittest tests/test_periode.py
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import periode  # noqa: E402

RABU = date(2026, 10, 28)


class Pekan(unittest.TestCase):
    def test_awal_pekan_senin(self):
        self.assertEqual(periode.awal_pekan(date(2026, 10, 25)), date(2026, 10, 19))  # Minggu
        self.assertEqual(periode.awal_pekan(date(2026, 10, 19)), date(2026, 10, 19))

    def test_bawaan_pekan_tutup_terakhir(self):
        self.assertEqual(periode.pilih_pekan(RABU), (date(2026, 10, 19), date(2026, 10, 25), True))
        # Senin pagi (cron 07:00): Pekan yang baru saja tutup
        self.assertEqual(periode.pilih_pekan(date(2026, 10, 26)),
                         (date(2026, 10, 19), date(2026, 10, 25), True))

    def test_pekan_yang_memuat_tanggal(self):
        self.assertEqual(periode.pilih_pekan(RABU, pekan=date(2026, 10, 14)),
                         (date(2026, 10, 12), date(2026, 10, 18), True))

    def test_pekan_belum_tutup_ditolak(self):
        with self.assertRaises(ValueError) as e:
            periode.pilih_pekan(RABU, pekan=date(2026, 10, 27))
        self.assertEqual(str(e.exception), "Pekan 2026-10-26–2026-11-01 belum tutup; pakai --berjalan")

    def test_pekan_yang_minggunya_hari_ini_belum_tutup(self):
        with self.assertRaises(ValueError):
            periode.pilih_pekan(date(2026, 10, 25), pekan=date(2026, 10, 21))

    def test_pekan_berjalan(self):
        self.assertEqual(periode.pilih_pekan(RABU, berjalan=True),
                         (date(2026, 10, 26), RABU, False))


class Bulan(unittest.TestCase):
    def test_akhir_bulan(self):
        self.assertEqual(periode.akhir_bulan("2026-02"), date(2026, 2, 28))
        self.assertEqual(periode.akhir_bulan("2028-02"), date(2028, 2, 29))
        self.assertEqual(periode.akhir_bulan("2026-12"), date(2026, 12, 31))

    def test_bulan_sebelum_melewati_tahun(self):
        self.assertEqual(periode.bulan_sebelum("2027-01"), "2026-12")
        self.assertEqual(periode.bulan_sebelum("2026-10"), "2026-09")

    def test_rentang_bulan(self):
        self.assertEqual(periode.rentang_bulan("2026-09"), (date(2026, 9, 1), date(2026, 9, 30)))
        self.assertEqual(periode.rentang_bulan("2026-02"), (date(2026, 2, 1), date(2026, 2, 28)))
        with self.assertRaises(ValueError):
            periode.rentang_bulan("2026-13")

    def test_bulan_dalam_rentang_lintas_bulan(self):
        self.assertEqual(periode.bulan_dalam(date(2026, 9, 28), date(2026, 10, 4)),
                         [(2026, 9), (2026, 10)])
        self.assertEqual(periode.bulan_dalam(date(2026, 12, 28), date(2027, 1, 3)),
                         [(2026, 12), (2027, 1)])
        self.assertEqual(periode.bulan_dalam(date(2026, 10, 19), date(2026, 10, 25)), [(2026, 10)])


if __name__ == "__main__":
    unittest.main()
