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


class Ringkas(unittest.TestCase):
    """ringkas(rows, mulai, akhir): satu aturan hitung untuk hari, Pekan, dan bulan (ADR-0023)."""

    @staticmethod
    def b(tanggal, tipe, jumlah, kategori="food", resi=None):
        r = tx(tanggal, tipe, jumlah, kategori)
        if resi is not None:
            r["no_resi"] = resi
        return r

    def hitung(self, rows, mulai="2026-10-01", akhir="2026-10-31"):
        return buku_kas.ringkas(rows, date.fromisoformat(mulai), date.fromisoformat(akhir))

    def test_satu_struk_banyak_item_satu_transaksi_jumlah_uang_semua_item(self):
        h = self.hitung([self.b("2026-10-05", "pengeluaran", 30_000, resi="A"),
                         self.b("2026-10-05", "pengeluaran", 20_000, resi="A"),
                         self.b("2026-10-06", "pengeluaran", 10_000, resi="B")])
        self.assertEqual(h["pengeluaran"], 60_000)
        self.assertEqual(h["transaksi_pengeluaran"], 2)

    def test_hitungan_dipisah_per_arah(self):
        h = self.hitung([self.b("2026-10-05", "pengeluaran", 1, resi="A"),
                         self.b("2026-10-06", "pemasukan", 9, "salary", resi="B"),
                         self.b("2026-10-07", "pemasukan", 9, "bonus", resi="C")])
        self.assertEqual((h["transaksi_pengeluaran"], h["transaksi_pemasukan"]), (1, 2))
        self.assertEqual((h["pengeluaran"], h["pemasukan"]), (1, 18))

    def test_transfer_dan_saldo_awal_tidak_dihitung_apa_pun(self):
        h = self.hitung([self.b("2026-10-05", "transfer", 5_000_000, "transfer", resi="T"),
                         self.b("2026-10-01", "pemasukan", 20_500_000, "opening_balance", resi="SALDO-AWAL")])
        self.assertEqual(h["pemasukan"], 0)
        self.assertEqual(h["saldo_awal"], 20_500_000)
        self.assertEqual((h["transaksi_pemasukan"], h["transaksi_pengeluaran"]), (0, 0))
        self.assertEqual(h["per_kategori"], {})

    def test_batas_rentang_inklusif_dan_di_luar_rentang_diabaikan(self):
        h = self.hitung([self.b("2026-09-30", "pengeluaran", 1, resi="A"),
                         self.b("2026-10-01", "pengeluaran", 10, resi="B"),
                         self.b("2026-10-31", "pengeluaran", 100, resi="C"),
                         self.b("2026-11-01", "pengeluaran", 1000, resi="D")])
        self.assertEqual((h["pengeluaran"], h["transaksi_pengeluaran"]), (110, 2))

    def test_transaksi_terbelah_dua_periode_dihitung_di_keduanya(self):
        rows = [self.b("2026-10-31", "pengeluaran", 10, resi="X"),
                self.b("2026-11-01", "pengeluaran", 20, resi="X")]
        self.assertEqual(self.hitung(rows, "2026-10-01", "2026-10-31")["transaksi_pengeluaran"], 1)
        self.assertEqual(self.hitung(rows, "2026-11-01", "2026-11-30")["transaksi_pengeluaran"], 1)
        self.assertEqual(self.hitung(rows, "2026-10-01", "2026-11-30")["transaksi_pengeluaran"], 1)

    def test_baris_tanpa_no_resi_masing_masing_satu_transaksi(self):
        h = self.hitung([self.b("2026-10-05", "pengeluaran", 1), self.b("2026-10-05", "pengeluaran", 2)])
        self.assertEqual(h["transaksi_pengeluaran"], 2)

    def test_per_kategori_hanya_pengeluaran_kategori_dibakukan(self):
        h = self.hitung([self.b("2026-10-05", "pengeluaran", 10, "Food", resi="A"),
                         self.b("2026-10-05", "pengeluaran", 5, " food ", resi="B"),
                         self.b("2026-10-05", "pengeluaran", 7, "", resi="C"),
                         self.b("2026-10-05", "pengeluaran", 3, "   ", resi="D"),
                         self.b("2026-10-05", "pemasukan", 99, "salary", resi="E")])
        self.assertEqual(h["per_kategori"], {"food": 15, "other": 10})

    def test_baris_tak_terhitung_diabaikan(self):
        h = self.hitung([self.b("", "pengeluaran", 1, resi="A"),
                         self.b("2026-10-05", "pemasukkan", 2, resi="B"),
                         self.b("2026-10-05", "pengeluaran", 4, resi="C")])
        self.assertEqual((h["pengeluaran"], h["transaksi_pengeluaran"]), (4, 1))

    def test_rentang_kosong_semua_nol(self):
        self.assertEqual(self.hitung([]), {"pemasukan": 0, "pengeluaran": 0, "saldo_awal": 0,
                                           "transaksi_pemasukan": 0, "transaksi_pengeluaran": 0,
                                           "per_kategori": {}})

    def test_arus_kas_bulan_sama_dengan_ringkas_satu_bulan_penuh(self):
        h = buku_kas.ringkas(DASAR, date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(buku_kas.arus_kas_bulan(DASAR, "2026-08"),
                         {k: h[k] for k in ("pemasukan", "pengeluaran", "saldo_awal")})


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
