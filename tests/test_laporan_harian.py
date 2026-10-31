"""Tes scripts/laporan-harian.py — pengeluaran satu hari, dihitung skrip bukan model.

    python3 -m unittest tests/test_laporan_harian.py
"""
import importlib.util
import unittest
from datetime import date
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("laporan_harian", AKAR / "scripts" / "laporan-harian.py")
lh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lh)

HARI = date(2026, 10, 31)


def b(tanggal, tipe, kategori, jumlah, resi):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah),
            "no_resi": resi}


ROWS = [
    b("2026-10-31", "pengeluaran", "food", 25_000, "A"),
    b("2026-10-31", "pengeluaran", "food", 15_000, "B"),
    b("2026-10-31", "pengeluaran", "groceries", 60_000, "C"),
    b("2026-10-31", "pengeluaran", "groceries", 40_000, "C"),   # struk sama: 1 transaksi
    b("2026-10-31", "pemasukan", "salary", 9_000_000, "D"),      # bukan pengeluaran
    b("2026-10-31", "transfer", "transfer", 1_000_000, "E"),     # bukan pengeluaran
    b("2026-10-30", "pengeluaran", "food", 999_999, "F"),        # hari lain
    b("2026-11-01", "pengeluaran", "food", 999_999, "G"),        # hari lain
]


class Susun(unittest.TestCase):
    def test_per_kategori_terbesar_dulu_dengan_total_dan_jumlah_transaksi(self):
        teks = lh.susun(ROWS, HARI)
        self.assertIn("📊 Pengeluaran Hari Ini — 31 Okt 2026", teks)
        self.assertLess(teks.index("groceries"), teks.index("food"))
        self.assertIn("groceries", teks)
        self.assertIn("Rp 100.000", teks)   # groceries
        self.assertIn("Rp 40.000", teks)    # food
        self.assertIn("Total:", teks)
        self.assertIn("Rp 140.000", teks)
        self.assertIn("3 transaksi tercatat", teks)  # A, B, C — struk C dihitung sekali

    def test_pemasukan_transfer_dan_hari_lain_tidak_ikut(self):
        teks = lh.susun(ROWS, HARI)
        self.assertNotIn("999.999", teks)
        self.assertNotIn("9.000.000", teks)
        self.assertNotIn("1.000.000", teks)
        self.assertNotIn("salary", teks)

    def test_hari_tanpa_pengeluaran_dijawab_apa_adanya(self):
        teks = lh.susun(ROWS, date(2026, 10, 29))
        self.assertIn("tidak ada pengeluaran tercatat", teks)
        self.assertNotIn("Total:", teks)

    def test_baris_tak_terhitung_diperingatkan_dan_tidak_ikut_total(self):
        kotor = ROWS + [b("", "pengeluaran", "food", 777_000, "H")]
        teks = lh.susun(kotor, HARI)
        self.assertIn("⚠️ 1 transaksi tidak terhitung", teks)
        self.assertNotIn("tidak terhitung", lh.susun(ROWS, HARI))
        self.assertIn("Rp 140.000", teks)

    def test_penutup_menyebut_dihitung_skrip(self):
        self.assertIn("Dihitung scripts/laporan-harian.py, tanpa model", lh.susun(ROWS, HARI))


if __name__ == "__main__":
    unittest.main()
