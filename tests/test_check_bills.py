"""Tes check-bills.py — status budget sesuai permintaan, dan cek budget yang tetap diam.

    python3 -m unittest tests/test_check_bills.py
"""
import importlib.util
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

AKAR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_bills", AKAR / "scripts" / "check-bills.py")
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

HARI = date(2026, 10, 31)


def b(tanggal, tipe, jumlah, kategori="food"):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah)}


ROWS = [
    b("2026-10-05", "pengeluaran", 850_000),
    b("2026-10-20", "pengeluaran", 350_000),
    b("2026-10-21", "pemasukan", 9_000_000, "salary"),        # bukan pengeluaran
    b("2026-10-22", "transfer", 2_000_000, "transfer"),       # bukan pengeluaran
    b("2026-09-30", "pengeluaran", 999_999),                  # bulan lain
]


def jalankan(fungsi, budget, rows=ROWS):
    atur = {"budget_bulanan": budget, "alert_persen": 80, "pengeluaran_besar_mulai": 1_000_000}
    with mock.patch.object(cb.pengaturan, "muat", return_value=atur), \
            mock.patch.object(cb, "load_bills", return_value=rows):
        return fungsi(HARI)


class StatusBudget(unittest.TestCase):
    """check-bills hanya meneruskan ke budget.pesan; aturan hitung dan bunyinya diuji di test_budget.py."""

    def test_selalu_menjawab_walau_di_bawah_ambang_tapi_cek_malam_tetap_diam(self):
        teks = jalankan(cb.status_budget, 7_000_000)
        self.assertIn("💰 Status Budget — Oktober 2026", teks)
        self.assertIn("Rp 1.200.000 (17%)", teks)
        self.assertEqual(jalankan(cb.check_budget, 7_000_000), "")

    def test_budget_belum_diset(self):
        self.assertIn("Budget belum diset", jalankan(cb.status_budget, 0))


class CekBudget(unittest.TestCase):
    def test_peringatan_di_atas_ambang(self):
        teks = jalankan(cb.check_budget, 1_300_000)  # 1.200.000 = 92%
        self.assertIn("Mendekati batas Budget", teks)
        self.assertIn("92%", teks)

    def test_diam_bila_budget_belum_diset(self):
        self.assertEqual(jalankan(cb.check_budget, 0), "")


if __name__ == "__main__":
    unittest.main()
