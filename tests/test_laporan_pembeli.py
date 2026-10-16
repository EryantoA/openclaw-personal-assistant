"""Tes scripts/laporan-pembeli.py — pengeluaran per Pembeli, dihitung skrip (spec 0001).

    python3 -m unittest tests/test_laporan_pembeli.py
"""
import importlib.util
import unittest
from datetime import date
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("laporan_pembeli", AKAR / "scripts" / "laporan-pembeli.py")
lp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lp)


def b(tanggal, tipe, pencatat, jumlah, resi, kategori="food"):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah),
            "pencatat": pencatat, "no_resi": resi}


PEKAN = (date(2026, 10, 12), date(2026, 10, 18))
ROWS = [
    b("2026-10-12", "pengeluaran", "Eryanto", 100_000, "A"),
    b("2026-10-12", "pengeluaran", "Eryanto", 50_000, "A"),     # struk sama: 1 transaksi
    b("2026-10-14", "pengeluaran", "Elsi", 200_000, "B"),
    b("2026-10-15", "pengeluaran", "", 50_000, "C"),            # tanpa pencatat
    b("2026-10-15", "pemasukan", "Eryanto", 9_000_000, "D", "salary"),  # bukan pengeluaran
    b("2026-10-16", "transfer", "Eryanto", 1_000_000, "E", "transfer"),  # bukan pengeluaran
    b("2026-10-11", "pengeluaran", "Eryanto", 999_999, "F"),    # di luar Pekan
    b("2026-10-19", "pengeluaran", "Elsi", 999_999, "G"),       # di luar Pekan
]


class PerPembeli(unittest.TestCase):
    def setUp(self):
        self.teks = lp.susun(ROWS, *PEKAN, "Pekan 12–18 Okt 2026")

    def test_total_per_pembeli_hanya_pengeluaran_dalam_rentang(self):
        self.assertIn("Eryanto", self.teks)
        self.assertIn("Rp 150.000", self.teks)   # Eryanto: 100.000 + 50.000
        self.assertIn("Elsi", self.teks)
        self.assertNotIn("9.000.000", self.teks)
        self.assertNotIn("999.999", self.teks)
        self.assertNotIn("1.000.000", self.teks)

    def test_baris_tanpa_pencatat_jadi_tanpa_nama(self):
        self.assertIn("Tanpa nama", self.teks)

    def test_struk_banyak_item_dihitung_satu_transaksi(self):
        baris = next(l for l in self.teks.splitlines() if l.startswith("Eryanto"))
        self.assertIn("1 transaksi", baris)

    def test_urut_terbesar_dan_total_keseluruhan(self):
        urut = [l.split()[0] for l in self.teks.splitlines() if l.startswith(("Eryanto", "Elsi", "Tanpa"))]
        self.assertEqual(urut, ["Elsi", "Eryanto", "Tanpa"])
        self.assertIn("Total: Rp 400.000", self.teks)

    def test_keluaran_sama_bila_dijalankan_dua_kali(self):
        self.assertEqual(self.teks, lp.susun(ROWS, *PEKAN, "Pekan 12–18 Okt 2026"))

    def test_tanpa_pengeluaran(self):
        self.assertIn("tidak ada pengeluaran", lp.susun([], *PEKAN, "Pekan X"))


class Alias(unittest.TestCase):
    PETA = lp.resi.bangun_peta({"Eryanto": ["Teikoku", "ryan", "suami"], "Elsi": ["istri", "Elsea"]})

    def test_satu_orang_berbagai_nama_digabung(self):
        rows = [b("2026-10-12", "pengeluaran", n, 10_000, f"R{i}")
                for i, n in enumerate(["Eryanto", "eryanto", "ryan", "Ryan", "Teikoku", "teikoku", "suami",
                                       "Elsi", "elsi", "istri", "Elsea"])]
        teks = lp.susun(rows, *PEKAN, "Pekan X", peta=self.PETA)
        baris = [l for l in teks.splitlines() if l.startswith(("Eryanto", "Elsi"))]
        self.assertEqual(len(baris), 2)
        self.assertIn("Rp 70.000", baris[0])
        self.assertIn("7 transaksi", baris[0])
        self.assertIn("Rp 40.000", baris[1])
        self.assertNotIn("Tanpa nama", teks)


class Rentang(unittest.TestCase):
    def test_pekan_senin_sampai_minggu(self):
        self.assertEqual(lp.rentang_pekan(date(2026, 10, 15)), (date(2026, 10, 12), date(2026, 10, 18)))

    def test_bulan_kalender(self):
        self.assertEqual(lp.rentang_bulan("2026-02"), (date(2026, 2, 1), date(2026, 2, 28)))


class Penjaga(unittest.TestCase):
    def test_pekan_belum_tutup_ditolak(self):
        with self.assertRaises(SystemExit):
            lp.main(["--pekan", "2026-10-14", "--hari-ini", "2026-10-15"])

    def test_bulan_depan_ditolak(self):
        with self.assertRaises(SystemExit):
            lp.main(["--bulan", "2030-01", "--hari-ini", "2026-10-15"])


if __name__ == "__main__":
    unittest.main()
