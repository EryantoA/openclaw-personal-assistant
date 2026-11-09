"""Tes scripts/sheets_laporan.py — Tab Laporan Cermin (ADR-0026): hanya-baca, dihitung skrip.

    python3 -m unittest tests/test_sheets_laporan.py
"""
import sys
import unittest
from datetime import date
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import sheets_laporan as sl  # noqa: E402

LABEL = {"food": "Makan & Minum", "salary": "Gaji"}
ATUR = {"budget_bulanan": 1_000_000, "alert_persen": 80, "pengeluaran_besar_mulai": 500_000}
HARI_INI = date(2026, 9, 15)


def tx(tanggal, tipe, jumlah, kategori="food", item="x", no_resi="", akun="", akun_tujuan=""):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "item": item, "jumlah": str(jumlah),
            "no_resi": no_resi, "akun": akun, "akun_tujuan": akun_tujuan}


ROWS = [
    tx("2026-03-26", "pemasukan", 1_000_000, "opening_balance", no_resi="SALDO-AWAL"),
    tx("2026-07-05", "pengeluaran", 20_000, item="Susu", no_resi="S1"),
    tx("2026-07-05", "pengeluaran", 5_000, item="Roti", no_resi="S1"),
    tx("2026-07-28", "pemasukan", 500_000, "salary", no_resi="G1"),
    tx("2026-08-03", "pengeluaran", 600_000, "transport", no_resi="B1"),
    tx("2026-08-04", "pengeluaran", 850_000, no_resi="B2"),
    tx("2026-08-12", "transfer", 100_000, "other", no_resi="T1"),
]


class RingkasanBulanan(unittest.TestCase):
    def test_header_istilah_glosarium_dan_transaksi_dihitung_per_no_resi(self):
        self.assertEqual(sl.grid_ringkasan_bulanan(ROWS), [
            ["Bulan", "Jumlah Transaksi", "Pemasukan", "Pengeluaran", "Arus Kas Bulanan", "Saldo Awal",
             "Saldo Bersama Akhir Bulan"],
            ["Maret 2026", 0, 0, 0, 0, 1_000_000, 1_000_000],
            ["Juli 2026", 2, 500_000, 25_000, 475_000, "", 1_475_000],
            ["Agustus 2026", 2, 0, 1_450_000, -1_450_000, "", 25_000],
        ])


class PerKategori(unittest.TestCase):
    def setUp(self):
        self.grid = sl.grid_per_kategori(ROWS, 2026, LABEL, HARI_INI)

    def baris(self, judul):
        return next(b for b in self.grid if b and b[0] == judul)

    def test_kolom_jan_des_dan_bulan_pertama_ditandai_parsial(self):
        self.assertEqual(self.grid[0], ["Kategori", "Jan", "Feb", "Mar*", "Apr", "Mei", "Jun", "Jul", "Agu",
                                        "Sep", "Okt", "Nov", "Des", "Total Tahun"])
        self.assertEqual(self.grid[-1], ["* Pencatatan dimulai 26 Mar 2026; bulan itu tidak penuh."])

    def test_baris_per_label_bulan_di_luar_rentang_kosong(self):
        kosong3 = ["", "", 0, 0, 0, 0]  # Jan–Feb sebelum pencatatan, Mar–Jun tanpa transaksi
        self.assertEqual(self.baris("Gaji"), ["Gaji"] + kosong3 + [500_000, 0, 0] + ["", "", "", 500_000])
        self.assertEqual(self.baris("Makan & Minum"),
                         ["Makan & Minum"] + kosong3 + [25_000, 850_000, 0] + ["", "", "", 875_000])
        self.assertEqual(self.baris("transport")[13], 600_000)  # tanpa label: slug

    def test_pengeluaran_urut_total_terbesar_dan_saldo_awal_serta_transfer_tidak_ikut(self):
        judul = [b[0] for b in self.grid if b]
        i = judul.index("Pengeluaran")
        self.assertEqual(judul[i + 1:i + 3], ["Makan & Minum", "transport"])
        self.assertNotIn("opening_balance", judul)
        self.assertNotIn("other", judul)

    def test_total_dan_arus_kas_bulanan(self):
        self.assertEqual(self.baris("Total Pemasukan")[13], 500_000)
        self.assertEqual(self.baris("Total Pengeluaran")[7:9], [25_000, 1_450_000])
        self.assertEqual(self.baris("Arus Kas Bulanan")[7:10], [475_000, -1_450_000, 0])

    def test_tahun_tanpa_bulan_pertama_tidak_bertanda(self):
        grid = sl.grid_per_kategori(ROWS + [tx("2027-01-02", "pengeluaran", 1)], 2027, LABEL, date(2027, 1, 5))
        self.assertEqual(grid[0][1], "Jan")
        self.assertNotIn("*", grid[-1][0] if grid[-1] else "")


class Budget(unittest.TestCase):
    def test_batas_sekarang_dipakai_untuk_semua_bulan_dengan_keterangan(self):
        grid = sl.grid_budget(ROWS, 2026, ATUR, HARI_INI)
        self.assertIn("Rp 1.000.000", grid[0][0])
        self.assertIn("acuan", grid[0][0])
        self.assertEqual(grid[1], ["Bulan", "Pengeluaran Rutin", "Budget", "Persen", "Di Luar Budget", "Status"])
        bulan = {b[0]: b[1:] for b in grid[2:]}
        self.assertEqual(len(bulan), 12)
        self.assertEqual(bulan["Januari 2026"], ["", "", "", "", ""])
        self.assertEqual(bulan["Juli 2026"], [25_000, 1_000_000, 0.025, 0, "Aman"])
        self.assertEqual(bulan["Agustus 2026"], [0, 1_000_000, 0.0, 1_450_000, "Aman"])
        self.assertEqual(bulan["September 2026"][4], "Aman")
        self.assertEqual(bulan["Oktober 2026"], ["", "", "", "", ""])

    def test_status_mendekati_dan_lewat(self):
        rows = [tx("2026-09-01", "pengeluaran", 400_000, no_resi="A"),
                tx("2026-09-02", "pengeluaran", 400_000, no_resi="B"),
                tx("2026-10-01", "pengeluaran", 499_999, no_resi="C"),
                tx("2026-10-02", "pengeluaran", 499_999, no_resi="D"),
                tx("2026-10-03", "pengeluaran", 499_999, no_resi="E")]
        bulan = {b[0]: b[1:] for b in sl.grid_budget(rows, 2026, ATUR, date(2026, 10, 9))[2:]}
        self.assertEqual(bulan["September 2026"][4], "Mendekati")
        self.assertEqual(bulan["Oktober 2026"][4], "Lewat")

    def test_budget_belum_diset(self):
        grid = sl.grid_budget(ROWS, 2026, {**ATUR, "budget_bulanan": 0}, HARI_INI)
        self.assertIn("belum diset", grid[0][0])
        self.assertEqual({b[0]: b[1:] for b in grid[2:]}["Juli 2026"], [25_000, "", "", 0, "Budget belum diset"])


class SaldoPerAkun(unittest.TestCase):
    def test_belum_aktif_hanya_pemberitahuan_tanpa_angka(self):
        for cfg in (None, {"cutover": "2026-08-01", "saldo_global_saat_cutover": None,
                           "akun": [{"id": "kas", "nama": "Kas", "saldo_awal": None}]}):
            grid = sl.grid_saldo_akun(ROWS, cfg, HARI_INI)
            self.assertEqual(len(grid), 1)
            self.assertIn("belum aktif", grid[0][0])

    def test_aktif_saldo_tiap_akun_per_akhir_bulan_dan_selisih_terbuka(self):
        cfg = {"cutover": "2026-08-01", "saldo_global_saat_cutover": 1_475_000,
               "akun": [{"id": "kas", "nama": "Kas", "saldo_awal": 475_000},
                        {"id": "bank", "nama": "Bank", "saldo_awal": 1_000_000}]}
        rows = ROWS + [tx("2026-09-01", "pengeluaran", 10_000, akun="Kas", no_resi="K1"),
                       tx("2026-09-02", "transfer", 200_000, "other", akun="Bank", akun_tujuan="Kas",
                          no_resi="T2")]
        grid = sl.grid_saldo_akun(rows, cfg, HARI_INI)
        self.assertEqual(grid[0], ["Bulan", "Kas", "Bank", "Jumlah Semua Akun", "Saldo Bersama", "Selisih",
                                   "Baris Tanpa Akun"])
        # Agustus: B1, B2 tanpa akun (selisih terbuka), T1 transfer tanpa akun
        self.assertEqual(grid[1], ["Agustus 2026", 475_000, 1_000_000, 1_475_000, 25_000, 1_450_000, 3])
        self.assertEqual(grid[2], ["September 2026", 665_000, 800_000, 1_465_000, 15_000, 1_450_000, 3])


class DaftarTab(unittest.TestCase):
    def test_urutan_tab_tahun_terbaru_dulu_dan_buku_kas_terakhir(self):
        rows = ROWS + [tx("2027-01-02", "pengeluaran", 1)]
        self.assertEqual(sl.urutan_tab(rows), [
            "Ringkasan Bulanan", "Per Kategori 2027", "Budget 2027", "Per Kategori 2026", "Budget 2026",
            "Saldo per Akun", "Buku Kas"])

    def test_tanpa_transaksi_tidak_ada_tab_tahunan(self):
        self.assertEqual(sl.urutan_tab([]), ["Ringkasan Bulanan", "Saldo per Akun", "Buku Kas"])


if __name__ == "__main__":
    unittest.main()
