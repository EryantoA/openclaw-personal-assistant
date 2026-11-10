"""Tes scripts/laporan-tahunan.py — bahan SPT & zakat, bukan angka SPT (ADR-0033).

    python3 -m unittest tests/test_laporan_tahunan.py
"""
import contextlib
import csv
import io
import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("laporan_tahunan", AKAR / "scripts" / "laporan-tahunan.py")
lt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lt)

KOLOM = ["tanggal", "tipe", "kategori", "item", "jumlah", "catatan", "channel",
         "pencatat", "akun", "akun_tujuan", "waktu", "no_resi"]


def b(tanggal, tipe, kategori, jumlah, item="", **lain):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah),
            "item": item, **lain}


DASAR = [
    b("2026-03-26", "pemasukan", "opening_balance", 20_500_000, "Saldo awal", no_resi="SALDO-AWAL"),
    b("2026-04-28", "pemasukan", "salary", 40_000_000, "gaji masuk", pencatat="Elsi"),
    b("2026-05-15", "pemasukan", "consulting", 1_500_000, "pengawas ujian", pencatat="Eryanto"),
    b("2026-09-01", "pemasukan", "bonus", 2_000_000, "Menang julajula", pencatat="Eryanto"),
    b("2026-06-01", "transfer", "other", 1_000_000, "tarik tunai"),
    b("2026-07-10", "pengeluaran", "donation", 50_000, "Infaq"),
    b("2026-08-16", "pengeluaran", "travel", 900_000, "Hotel", no_resi="H1"),
    b("2026-08-16", "pengeluaran", "food", 200_000, "Makan hotel", no_resi="H1"),
    b("2026-10-01", "pengeluaran", "jewelry", 300_000, "Cincin emas", no_resi="J1"),
    b("2026-10-02", "pengeluaran", "food", 30_000, "Nasi goreng"),
    b("2026-12-20", "pengeluaran", "zakat", 100_000, "Zakat penghasilan - BAZNAS"),
    b("2027-01-05", "pemasukan", "salary", 9_999_000, "gaji tahun depan"),
]

AKUN = {"cutover": "2026-11-01", "saldo_global_saat_cutover": 1,
        "akun": [{"id": "tunai_a", "nama": "Tunai A", "aktif": True, "saldo_awal": 1_000_000},
                 {"id": "bank_a", "nama": "Bank A", "aktif": True, "saldo_awal": 5_000_000}]}

ATUR = {"pengeluaran_besar_mulai": 1_000_000, "nisab_zakat_tahunan": {"2026": 91_681_728},
        "label_kategori": {"salary": "Gaji", "zakat": "Zakat"}}


def susun(rows=DASAR, tahun=2026, atur=ATUR, akun=None, rekon=(), hari_ini=None):
    return lt.susun(tahun, rows, atur, akun, list(rekon), hari_ini)


class Cakupan(unittest.TestCase):
    def test_mulai_sesudah_1_januari_disebut(self):
        self.assertIn("Buku Kas mulai 26 Mar 2026: 1 Jan–25 Mar 2026 tidak tercatat", susun())

    def test_mulai_1_januari_tidak_ada_peringatan(self):
        rows = [b("2025-12-31", "pemasukan", "salary", 1)] + DASAR
        self.assertNotIn("tidak tercatat", susun(rows))

    def test_tahun_tanpa_transaksi(self):
        self.assertIn("Tidak ada transaksi tercatat di 2025", susun(tahun=2025))

    def test_judul_bukan_angka_spt(self):
        self.assertIn("bukan angka SPT", susun())


class Pemasukan(unittest.TestCase):
    def test_saldo_awal_transfer_dan_tahun_lain_tidak_jadi_pemasukan(self):
        self.assertIn("📥 Pemasukan 2026: Rp 43.500.000", susun())

    def test_per_kategori_memakai_label(self):
        self.assertIn("Gaji: Rp 40.000.000", susun())

    def test_selain_gaji_didaftar_per_item_dengan_pencatat(self):
        pesan = susun()
        self.assertIn("15 Mei  Rp 1.500.000  pengawas ujian (consulting, Eryanto)", pesan)
        self.assertIn("Menang julajula", pesan)
        self.assertNotIn("gaji masuk", pesan)
        self.assertNotIn("Saldo awal", pesan)


class Harta(unittest.TestCase):
    def test_saldo_akun_per_31_des_mengabaikan_tahun_berikutnya(self):
        rows = DASAR + [b("2026-12-01", "pengeluaran", "food", 200_000, "x", akun="Tunai A"),
                        b("2027-01-02", "pengeluaran", "food", 999, "y", akun="Bank A")]
        pesan = susun(rows, akun=AKUN)
        self.assertIn("Tunai A: Rp 800.000", pesan)
        self.assertIn("Bank A: Rp 5.000.000", pesan)
        self.assertIn("Saldo per 31 Des 2026", pesan)

    def test_rekonsiliasi_terakhir_sebelum_akhir_tahun(self):
        rekon = [{"titik": "2026-11-20T10:00:00", "akun": "Bank A"},
                 {"titik": "2027-01-03T10:00:00", "akun": "Bank A"}]
        pesan = susun(akun=AKUN, rekon=rekon)
        self.assertIn("Bank A: Rp 5.000.000  (dicek 20 Nov 2026)", pesan)
        self.assertIn("Tunai A: Rp 1.000.000  (belum pernah dicek)", pesan)

    def test_akun_belum_aktif_disebut_bukan_dihitung(self):
        belum = {**AKUN, "akun": [dict(AKUN["akun"][0], saldo_awal=None)]}
        self.assertIn("Saldo per Akun belum tersedia", susun(akun=belum))
        self.assertIn("Saldo per Akun belum tersedia", susun(akun=None))

    def test_cutover_sesudah_akhir_tahun(self):
        self.assertIn("Saldo per Akun belum tersedia", susun(tahun=2026, akun={**AKUN, "cutover": "2027-01-10"}))

    def test_saldo_bersama_selalu_ada(self):
        self.assertIn("Saldo Bersama: Rp 62.420.000", susun())

    def test_kandidat_harta_per_transaksi(self):
        pesan = susun()
        self.assertIn("16 Agu  Rp 1.100.000  Hotel (+1 item)", pesan)
        self.assertIn("1 Okt  Rp 300.000  Cincin emas", pesan)
        self.assertNotIn("Nasi goreng", pesan)


class Zakat(unittest.TestCase):
    def test_nisab_dan_batas_bawah(self):
        pesan = susun()
        self.assertIn("Nisab 2026: Rp 91.681.728/tahun", pesan)
        self.assertIn("Gaji tercatat: Rp 40.000.000 — di bawah nisab", pesan)
        self.assertIn("2,5% × gaji tercatat: Rp 1.000.000", pesan)
        self.assertIn("batas bawah", pesan)
        self.assertIn("per orang", pesan)

    def test_di_atas_nisab(self):
        rows = DASAR + [b("2026-11-28", "pemasukan", "salary", 60_000_000, "gaji")]
        self.assertIn("di atas nisab", susun(rows))

    def test_nisab_tahun_itu_belum_diisi_tidak_ditebak(self):
        pesan = susun(atur={**ATUR, "nisab_zakat_tahunan": {"2025": 85_685_972}})
        self.assertIn("Nisab 2026 belum diisi", pesan)
        self.assertNotIn("Rp 85.685.972", pesan)

    def test_zakat_terpisah_dari_infak(self):
        pesan = susun()
        self.assertIn("Zakat tercatat dibayar 2026: Rp 100.000", pesan)
        self.assertIn("Infak/donasi Rp 50.000 tidak dihitung sebagai zakat", pesan)


class Dokumen(unittest.TestCase):
    def test_tenggat_dan_bukti_potong_tahun_berikutnya(self):
        pesan = susun()
        self.assertIn("31 Mar 2027", pesan)
        self.assertIn("BPA1", pesan)
        self.assertIn("31 Jan 2027", pesan)


class Berjalan(unittest.TestCase):
    def test_judul_dan_saldo_per_hari_ini(self):
        pesan = susun(akun=AKUN, hari_ini=date(2026, 11, 10))
        self.assertIn("(berjalan, per 10 Nov)", pesan)
        self.assertIn("Saldo per 10 Nov 2026", pesan)
        self.assertNotIn("Rp 100.000  Zakat", pesan)
        self.assertIn("Zakat tercatat dibayar 2026: Rp 0", pesan)


class Main(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.asli = {k: getattr(lt, k) for k in ("BILLS", "AKUN", "REKON", "tujuan_baku", "kirim")}
        self.asli_budget = lt.pengaturan.BUDGET_JSON
        lt.BILLS, lt.AKUN, lt.REKON = self.tmp / "bills.csv", self.tmp / "akun.json", self.tmp / "r.csv"
        lt.pengaturan.BUDGET_JSON = self.tmp / "budget.json"
        lt.pengaturan.BUDGET_JSON.write_text(json.dumps(ATUR), encoding="utf-8")
        lt.tujuan_baku = lambda: [("whatsapp", "+0")]
        with open(lt.BILLS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=KOLOM, restval="")
            w.writeheader()
            w.writerows(DASAR)
        self.terkirim = []
        self.diam = contextlib.ExitStack()
        self.diam.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.diam.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.diam.close()
        for k, v in self.asli.items():
            setattr(lt, k, v)
        lt.pengaturan.BUDGET_JSON = self.asli_budget

    def test_bawaan_tahun_lalu_tanpa_menulis(self):
        sebelum = sorted(p.name for p in self.tmp.iterdir())
        self.assertEqual(lt.main(["--hari-ini", "2027-02-02"]), 0)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), sebelum)

    def test_kirim_tahun_lalu(self):
        lt.kirim = lambda pesan, kanal, ke: (self.terkirim.append(pesan) or True, "")
        self.assertEqual(lt.main(["--hari-ini", "2027-02-02", "--kirim"]), 0)
        self.assertIn("LAPORAN TAHUNAN 2026", self.terkirim[0])

    def test_kirim_gagal_keluar_1(self):
        lt.kirim = lambda pesan, kanal, ke: (False, "No active WhatsApp Web listener")
        self.assertEqual(lt.main(["--hari-ini", "2027-02-02", "--kirim"]), 1)

    def test_tahun_berjalan_tidak_bisa_dikirim(self):
        lt.kirim = lambda pesan, kanal, ke: (True, "")
        self.assertEqual(lt.main(["--tahun", "2026", "--hari-ini", "2026-11-10", "--kirim"]), 2)

    def test_tahun_belum_dimulai_ditolak(self):
        with self.assertRaises(SystemExit):
            lt.main(["--tahun", "2027", "--hari-ini", "2026-11-10"])


if __name__ == "__main__":
    unittest.main()
