"""Tes scripts/rekap-bulanan.py — rekap semua bulan, dihitung skrip bukan model.

    python3 -m unittest tests/test_rekap_bulanan.py
"""
import importlib.util
import unittest
from datetime import date
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("rekap_bulanan", AKAR / "scripts" / "rekap-bulanan.py")
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)

HARI = date(2026, 10, 31)


def b(tanggal, tipe, jumlah, kategori="food"):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah)}


ROWS = [
    b("2026-08-01", "pemasukan", 20_500_000, "opening_balance"),  # Saldo Awal: ikut Saldo, bukan Pemasukan
    b("2026-08-05", "pengeluaran", 500_000),
    b("2026-08-25", "pemasukan", 5_000_000, "salary"),
    b("2026-08-26", "transfer", 3_000_000, "transfer"),            # tidak ikut apa pun
    # September tidak ada transaksi sama sekali
    b("2026-10-02", "pengeluaran", 6_200_000),
    b("2026-10-03", "pengeluaran", 300_000),
]


class Susun(unittest.TestCase):
    def teks(self, rows=ROWS, **kw):
        return rb.susun(rows, HARI, **kw)

    def test_bulan_kronologis_dengan_arus_kas_dan_saldo_terpisah(self):
        t = self.teks()
        self.assertLess(t.index("Agustus 2026"), t.index("September 2026"))
        self.assertLess(t.index("September 2026"), t.index("Oktober 2026"))
        # Agustus: masuk 5.000.000, keluar 500.000 → arus 4.500.000, saldo 20.500.000 + 4.500.000
        self.assertIn("Rp 5.000.000", t)
        self.assertIn("Rp 4.500.000", t)
        self.assertIn("Rp 25.000.000", t)

    def test_saldo_awal_bukan_pemasukan_tapi_ikut_saldo(self):
        agustus = self.teks().split("▸")[1]
        self.assertIn(f"{'Pemasukan:':<18}Rp 5.000.000", agustus)  # bukan 25.500.000
        self.assertIn("(2 transaksi)", agustus)               # saldo awal tidak dihitung transaksi

    def test_transfer_tidak_ikut_apa_pun(self):
        self.assertNotIn("3.000.000", self.teks())

    def test_bulan_kosong_di_tengah_tetap_tampil_dan_saldo_dibawa(self):
        september = self.teks().split("▸")[2]
        self.assertIn("September 2026", september)
        self.assertIn("(0 transaksi)", september)
        self.assertIn(f"{'Saldo Bersama:':<18}Rp 25.000.000", september)

    def test_arus_kas_negatif_ditandai_dan_saldo_kumulatif_turun(self):
        oktober = self.teks().split("▸")[3]
        self.assertIn(f"🔴 {'Arus Kas Bulanan:':<18}-Rp 6.500.000", oktober)
        self.assertIn(f"{'Saldo Bersama:':<18}Rp 18.500.000", oktober)

    def test_bulan_berjalan_ditandai(self):
        t = self.teks()
        self.assertIn("Oktober 2026 (berjalan)", t)
        self.assertNotIn("Agustus 2026 (berjalan)", t)

    def test_penutup_menyebut_saldo_terakhir(self):
        # bulan terakhir masih berjalan: saldo per hari ini, bukan "akhir bulan"
        self.assertIn("Saldo Bersama terakhir (per 31 Okt 2026): Rp 18.500.000", self.teks())
        tutup = rb.susun(ROWS, date(2026, 11, 15))
        self.assertIn("Saldo Bersama terakhir (akhir Oktober 2026): Rp 18.500.000", tutup)
        self.assertNotIn("(berjalan)", tutup.split("▸")[3])  # Oktober sudah tutup

    def test_dari_sampai_membatasi_tampilan_tapi_saldo_tetap_kumulatif(self):
        t = self.teks(dari="2026-10", sampai="2026-10")
        self.assertNotIn("Agustus 2026", t)
        self.assertIn("Oktober 2026", t)
        self.assertIn(f"{'Saldo Bersama:':<18}Rp 18.500.000", t)  # dibawa dari bulan-bulan sebelumnya

    def test_baris_tak_terhitung_diperingatkan(self):
        kotor = ROWS + [b("", "pengeluaran", 777_000)]
        self.assertIn("⚠️ 1 transaksi tidak terhitung", self.teks(kotor))
        self.assertNotIn("tidak terhitung", self.teks())

    def test_buku_kosong(self):
        self.assertIn("belum ada transaksi", self.teks([]))

    def test_penutup_menyebut_dihitung_skrip(self):
        self.assertIn("Dihitung scripts/rekap-bulanan.py, tanpa model", self.teks())


if __name__ == "__main__":
    unittest.main()
