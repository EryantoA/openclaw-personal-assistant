"""Tes scripts/buku_kas.py — aturan baca & hitung Buku Kas, lewat interface module saja.

    python3 -m unittest tests/test_buku_kas.py
"""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import buku_kas  # noqa: E402

HEADER = "tanggal,tipe,kategori,item,jumlah,catatan,channel,pencatat,akun,akun_tujuan,waktu,no_resi"


def tx(tanggal, tipe, jumlah, kategori="food"):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah)}


DASAR = [
    tx("2026-03-26", "pemasukan", 20_500_000, "opening_balance"),
    tx("2026-07-05", "pengeluaran", 100_000),
    tx("2026-07-28", "pemasukan", 5_000_000, "salary"),
    tx("2026-08-03", "pengeluaran", 300_000),
    tx("2026-08-12", "transfer", 1_000_000, "other"),
    tx("2026-08-31", "pengeluaran", 50_000),
]


class Jumlah(unittest.TestCase):
    def test_format_rupiah_dibaca_sebagai_angka_bulat(self):
        self.assertEqual(buku_kas.jumlah({"jumlah": "Rp 88.500"}), 88_500)
        self.assertEqual(buku_kas.jumlah({"jumlah": "88,500"}), 88_500)
        self.assertEqual(buku_kas.jumlah({"jumlah": "66000"}), 66_000)

    def test_kosong_atau_bukan_angka_jadi_nol(self):
        self.assertEqual(buku_kas.jumlah({"jumlah": ""}), 0)
        self.assertEqual(buku_kas.jumlah({}), 0)
        self.assertEqual(buku_kas.jumlah({"jumlah": "abc"}), 0)

    def test_hasilnya_int(self):
        self.assertIsInstance(buku_kas.jumlah({"jumlah": "1000"}), int)


class Arah(unittest.TestCase):
    def test_tiga_nilai_sah_tanpa_peduli_huruf_dan_spasi(self):
        self.assertEqual(buku_kas.arah({"tipe": " Pemasukan "}), "pemasukan")
        self.assertEqual(buku_kas.arah({"tipe": "TRANSFER"}), "transfer")
        self.assertEqual(buku_kas.arah({"tipe": "pengeluaran"}), "pengeluaran")

    def test_tipe_kosong_dianggap_pengeluaran(self):
        self.assertEqual(buku_kas.arah({"tipe": ""}), "pengeluaran")
        self.assertEqual(buku_kas.arah({}), "pengeluaran")

    def test_tipe_tidak_dikenal_none(self):
        self.assertIsNone(buku_kas.arah({"tipe": "pemasukkan"}))


class Saldo(unittest.TestCase):
    def test_transfer_tidak_ikut_saldo_awal_ikut(self):
        self.assertEqual(buku_kas.saldo(DASAR, per=date(2026, 8, 31)),
                         20_500_000 - 100_000 + 5_000_000 - 300_000 - 50_000)

    def test_tanggal_per_ikut_dihitung(self):
        self.assertEqual(buku_kas.saldo(DASAR, per=date(2026, 7, 5)), 20_500_000 - 100_000)
        self.assertEqual(buku_kas.saldo(DASAR, per=date(2026, 7, 4)), 20_500_000)

    def test_baris_tak_terhitung_tidak_mengubah_saldo(self):
        kotor = DASAR + [tx("", "pengeluaran", 999), tx("2026-08-01", "pemasukkan", 999),
                         tx("31-08-2026", "pemasukan", 999)]
        self.assertEqual(buku_kas.saldo(kotor, per=date(2026, 8, 31)),
                         buku_kas.saldo(DASAR, per=date(2026, 8, 31)))


class ArusKasBulan(unittest.TestCase):
    def test_saldo_awal_terpisah_dari_pemasukan(self):
        self.assertEqual(buku_kas.arus_kas_bulan(DASAR, "2026-03"),
                         {"pemasukan": 0, "pengeluaran": 0, "saldo_awal": 20_500_000})

    def test_transfer_tidak_ikut(self):
        self.assertEqual(buku_kas.arus_kas_bulan(DASAR, "2026-08"),
                         {"pemasukan": 0, "pengeluaran": 350_000, "saldo_awal": 0})

    def test_bulan_kosong_nol(self):
        self.assertEqual(buku_kas.arus_kas_bulan(DASAR, "2026-01"),
                         {"pemasukan": 0, "pengeluaran": 0, "saldo_awal": 0})


class TakTerhitung(unittest.TestCase):
    def test_baris_bermasalah_dilaporkan_dengan_alasan(self):
        tanpa_tgl = tx("", "pengeluaran", 1)
        salah_tipe = tx("2026-08-01", "pemasukkan", 2)
        hasil = buku_kas.tak_terhitung(DASAR + [tanpa_tgl, salah_tipe])
        self.assertEqual([r for r, _ in hasil], [tanpa_tgl, salah_tipe])
        self.assertIn("tanggal", hasil[0][1])
        self.assertIn("pemasukkan", hasil[1][1])

    def test_data_bersih_kosong(self):
        self.assertEqual(buku_kas.tak_terhitung(DASAR), [])


class Muat(unittest.TestCase):
    def test_file_tidak_ada_daftar_kosong(self):
        self.assertEqual(buku_kas.muat(Path("/tidak/ada/bills.csv")), [])

    def test_membaca_baris(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bills.csv"
            p.write_text(HEADER + "\r\n2026-09-14,pengeluaran,food,Momoyo,66000,,WhatsApp,Eryanto,,,,X\r\n",
                         encoding="utf-8")
            rows = buku_kas.muat(p)
        self.assertEqual(len(rows), 1)
        self.assertEqual(buku_kas.jumlah(rows[0]), 66_000)

    def test_header_rusak_gagal_jelas(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bills.csv"
            p.write_text("foo,bar\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                buku_kas.muat(p)


if __name__ == "__main__":
    unittest.main()
