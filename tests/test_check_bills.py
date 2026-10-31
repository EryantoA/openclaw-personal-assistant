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
    b("2026-10-05", "pengeluaran", 1_500_000),
    b("2026-10-20", "pengeluaran", 350_000),
    b("2026-10-21", "pemasukan", 9_000_000, "salary"),        # bukan pengeluaran
    b("2026-10-22", "transfer", 2_000_000, "transfer"),       # bukan pengeluaran
    b("2026-09-30", "pengeluaran", 999_999),                  # bulan lain
]


def jalankan(fungsi, budget, rows=ROWS):
    with mock.patch.object(cb.pengaturan, "muat", return_value={"budget_bulanan": budget, "alert_persen": 80}), \
            mock.patch.object(cb, "load_bills", return_value=rows):
        return fungsi(HARI)


class StatusBudget(unittest.TestCase):
    def test_selalu_menjawab_walau_di_bawah_ambang(self):
        teks = jalankan(cb.status_budget, 7_000_000)
        self.assertIn("💰 Status Budget Bulan Ini", teks)
        self.assertIn("Rp 7.000.000", teks)
        self.assertIn("Rp 1.850.000 (26%)", teks)
        self.assertIn("Rp 5.150.000", teks)
        self.assertEqual(jalankan(cb.check_budget, 7_000_000), "")  # cek malam tetap diam

    def test_pemasukan_transfer_dan_bulan_lain_tidak_dihitung(self):
        teks = jalankan(cb.status_budget, 7_000_000)
        self.assertNotIn("9.000.000", teks)
        self.assertNotIn("2.000.000", teks)
        self.assertNotIn("999.999", teks)

    def test_budget_belum_diset(self):
        teks = jalankan(cb.status_budget, 0)
        self.assertIn("Budget belum diset", teks)
        self.assertNotIn("Terpakai", teks)

    def test_melebihi_budget_ditandai_minus(self):
        teks = jalankan(cb.status_budget, 1_000_000)
        self.assertIn("(185%)", teks)
        self.assertIn("MINUS", teks)

    def test_penutup_menyebut_dihitung_skrip(self):
        self.assertIn("Dihitung scripts/check-bills.py, tanpa model", jalankan(cb.status_budget, 7_000_000))


class CekBudgetTetapSama(unittest.TestCase):
    def test_peringatan_di_atas_ambang(self):
        teks = jalankan(cb.check_budget, 2_000_000)  # 1.850.000 = 92%
        self.assertIn("PERINGATAN BUDGET", teks)
        self.assertIn("92%", teks)

    def test_diam_bila_budget_belum_diset(self):
        self.assertEqual(jalankan(cb.check_budget, 0), "")


if __name__ == "__main__":
    unittest.main()
