"""Tes scripts/rekonsiliasi.py — Rekonsiliasi per Akun dan Selisih Rekonsiliasi (ADR-0027).

Semua berkas di folder sementara; tidak ada data sungguhan.

    python3 -m unittest tests/test_rekonsiliasi.py
"""
import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import buku  # noqa: E402
import catat  # noqa: E402
import rekonsiliasi as rk  # noqa: E402
import resi  # noqa: E402
import sheets_laporan  # noqa: E402

AKUN = {"cutover": "2026-11-09", "saldo_global_saat_cutover": 5_100_000,
        "akun": [{"id": "tunai", "nama": "Tunai Ryan", "saldo_awal": 100_000},
                 {"id": "mandiri", "nama": "Mandiri Ryan", "saldo_awal": 5_000_000}]}


def tx(tanggal, tipe, jumlah, akun="", waktu="", kategori="food", item="x", no_resi="", akun_tujuan=""):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "item": item, "jumlah": str(jumlah),
            "catatan": "", "channel": "whatsapp", "pencatat": "Eryanto", "akun": akun,
            "akun_tujuan": akun_tujuan, "waktu": waktu, "no_resi": no_resi}


ROWS = [
    tx("2026-11-01", "pengeluaran", 999, no_resi="LAMA"),  # sebelum cutover: tidak ikut Saldo Akun
    tx("2026-11-10", "pengeluaran", 20_000, "Mandiri Ryan", "10:00", no_resi="A1"),
    tx("2026-11-11", "pengeluaran", 15_000, "", "12:00", item="Bakso", no_resi="A2"),
    tx("2026-11-12", "transfer", 100_000, "Mandiri Ryan", "09:00", "transfer", no_resi="A3",
       akun_tujuan="Tunai Ryan"),
    tx("2026-11-12", "pengeluaran", 5_000, "mandiri ryan", "", item="Parkir", no_resi="A4"),
]


class Dasar(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.bills = self.dir / "bills.csv"
        (self.dir / "akun.json").write_text(json.dumps(AKUN), encoding="utf-8")
        (self.dir / "budget.json").write_text(json.dumps({
            "kategori_custom": ["food", "transfer", "reconciliation"],
            "duplicate_check": {"aktif": True, "match_fields": ["tanggal", "waktu", "jumlah"], "aksi": "tolak"},
        }), encoding="utf-8")
        (self.dir / "pembeli.json").write_text("{}", encoding="utf-8")
        asli = (resi.BILLS_CSV, resi.BUDGET_JSON, resi.PEMBELI_JSON)
        resi.BILLS_CSV, resi.BUDGET_JSON, resi.PEMBELI_JSON = (
            self.bills, self.dir / "budget.json", self.dir / "pembeli.json")
        self.addCleanup(lambda: setattr(resi, "BILLS_CSV", asli[0]) or setattr(resi, "BUDGET_JSON", asli[1])
                        or setattr(resi, "PEMBELI_JSON", asli[2]))
        self.tulis(ROWS)

    def tulis(self, rows):
        with open(self.bills, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=resi.COLUMNS, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in resi.COLUMNS})

    def baca(self):
        with open(self.bills, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def catatan(self):
        return rk.muat_catatan(rk.path_catatan())

    def jalan(self, *argv, sekarang="2026-11-12T08:00"):
        keluar = io.StringIO()
        with redirect_stdout(keluar):
            kode = rk.main(list(argv) + ["--sekarang", sekarang])
        return kode, keluar.getvalue()


class SaldoAkunPerTitik(Dasar):
    def test_baris_sebelum_titik_ikut_dan_tanpa_jam_dianggap_awal_hari(self):
        rows = self.baca()
        self.assertEqual(rk.saldo_akun(rows, AKUN, "mandiri", datetime(2026, 11, 12, 8, 0)), 4_975_000)
        self.assertEqual(rk.saldo_akun(rows, AKUN, "mandiri", datetime(2026, 11, 12, 23, 59)), 4_875_000)
        self.assertEqual(rk.saldo_akun(rows, AKUN, "tunai", datetime(2026, 11, 12, 23, 59)), 200_000)

    def test_titik_dari_tanggal_adalah_akhir_hari(self):
        self.assertEqual(rk.titik("2026-11-30", datetime(2026, 12, 1, 9)), datetime(2026, 11, 30, 23, 59, 59))
        self.assertEqual(rk.titik(None, datetime(2026, 12, 1, 9, 5)), datetime(2026, 12, 1, 9, 5))


class Cek(Dasar):
    def test_cocok(self):
        kode, out = self.jalan("cek", "--akun", "Mandiri Ryan", "--saldo", "4.975.000")
        self.assertEqual(kode, 0)
        self.assertIn("✅ Cocok", out)
        self.assertEqual(self.catatan(), [])  # cek tidak pernah menulis

    def test_selisih_dengan_kandidat_tanpa_akun_dan_tanpa_jam(self):
        kode, out = self.jalan("cek", "--akun", "mandiri ryan", "--saldo", "4725000")
        self.assertEqual(kode, 0)
        self.assertIn("Selisih: -Rp 250.000", out)
        self.assertIn("Saldo Nyata lebih kecil", out)
        self.assertIn("Parkir", out)          # hari ini tanpa jam, ikut dihitung
        self.assertIn("Bakso", out)           # tanpa akun sejak cutover
        self.assertNotIn("x Rp 999", out)     # sebelum cutover bukan kandidat

    def test_per_tanggal(self):
        h = rk.cek(self.baca(), AKUN, [], "Mandiri Ryan", 4_875_000, rk.titik("2026-11-12", datetime(2026, 11, 20)))
        self.assertEqual(h["selisih"], 0)
        self.assertEqual(h["tanpa_jam"], [])  # titik akhir hari: tidak ada yang "belum lewat"

    def test_akun_tak_dikenal_menyebut_daftar_akun(self):
        kode, out = self.jalan("cek", "--akun", "BCA", "--saldo", "1")
        self.assertEqual(kode, 2)
        self.assertIn("Tunai Ryan, Mandiri Ryan", out)

    def test_titik_sebelum_cutover_ditolak(self):
        kode, out = self.jalan("cek", "--akun", "Mandiri Ryan", "--saldo", "1", "--per", "2026-11-01")
        self.assertEqual(kode, 2)
        self.assertIn("cutover", out)

    def test_fitur_akun_belum_aktif(self):
        (self.dir / "akun.json").write_text(json.dumps({**AKUN, "saldo_global_saat_cutover": None}))
        kode, out = self.jalan("cek", "--akun", "Mandiri Ryan", "--saldo", "1")
        self.assertEqual(kode, 2)
        self.assertIn("belum aktif", out)


class Simpan(Dasar):
    def test_cocok_dicatat_lengkap(self):
        kode, out = self.jalan("simpan", "--akun", "Mandiri Ryan", "--saldo", "4975000", "--cara", "cocok")
        self.assertEqual(kode, 0, out)
        (c,) = self.catatan()
        self.assertEqual((c["akun"], c["saldo_nyata"], c["saldo_akun"], c["selisih"], c["cara"]),
                         ("Mandiri Ryan", "4975000", "4975000", "0", "cocok"))
        self.assertEqual(c["titik"], "2026-11-12T08:00:00")

    def test_cocok_ditolak_bila_ada_selisih(self):
        kode, out = self.jalan("simpan", "--akun", "Mandiri Ryan", "--saldo", "1", "--cara", "cocok")
        self.assertEqual(kode, 2)
        self.assertEqual(self.catatan(), [])

    def test_dibiarkan_menjadi_selisih_terbuka(self):
        self.jalan("simpan", "--akun", "Mandiri Ryan", "--saldo", "4725000", "--cara", "dibiarkan")
        self.assertEqual(rk.selisih_terbuka(self.catatan(), "Mandiri Ryan"), -250_000)
        self.jalan("simpan", "--akun", "Mandiri Ryan", "--saldo", "4975000", "--cara", "cocok",
                   sekarang="2026-11-12T08:05")
        self.assertEqual(rk.selisih_terbuka(self.catatan(), "Mandiri Ryan"), 0)

    def test_kandidat_tanpa_akun_hanya_sejak_rekonsiliasi_terakhir(self):
        self.jalan("simpan", "--akun", "Mandiri Ryan", "--saldo", "4975000", "--cara", "cocok")
        h = rk.cek(self.baca(), AKUN, self.catatan(), "Mandiri Ryan", 1, datetime(2026, 11, 13))
        self.assertEqual([r["item"] for r in h["tanpa_akun"]], [])


class Tutup(Dasar):
    def test_uji_adalah_pratinjau_tanpa_menulis(self):
        sebelum = self.bills.read_bytes()
        kode, out = self.jalan("tutup", "--akun", "Mandiri Ryan", "--saldo", "4725000", "--uji",
                               "--channel", "whatsapp", "--pencatat", "Eryanto")
        self.assertEqual(kode, 0, out)
        self.assertIn("OK lolos", out)
        self.assertIn("Selisih Rekonsiliasi", out)
        self.assertEqual(self.bills.read_bytes(), sebelum)
        self.assertEqual(self.catatan(), [])

    def test_saldo_nyata_lebih_kecil_menjadi_pengeluaran_lalu_cocok(self):
        kode, out = self.jalan("tutup", "--akun", "Mandiri Ryan", "--saldo", "4725000",
                               "--channel", "whatsapp", "--pencatat", "Eryanto")
        self.assertEqual(kode, 0, out)
        baru = [r for r in self.baca() if r["kategori"] == "reconciliation"]
        self.assertEqual([(r["tipe"], r["jumlah"], r["akun"], r["tanggal"], r["waktu"]) for r in baru],
                         [("pengeluaran", "250000", "Mandiri Ryan", "2026-11-12", "08:00")])
        (c,) = self.catatan()
        self.assertEqual((c["cara"], c["no_resi"], c["selisih"]), ("selisih_ditutup", baru[0]["no_resi"], "-250000"))
        self.assertEqual(rk.saldo_akun(self.baca(), AKUN, "mandiri", datetime(2026, 11, 12, 8, 0)), 4_725_000)

    def test_saldo_nyata_lebih_besar_menjadi_pemasukan(self):
        self.jalan("tutup", "--akun", "Tunai Ryan", "--saldo", "230000", "--channel", "whatsapp",
                   "--pencatat", "Eryanto", sekarang="2026-11-13T07:00")
        (r,) = [r for r in self.baca() if r["kategori"] == "reconciliation"]
        self.assertEqual((r["tipe"], r["jumlah"], r["akun"]), ("pemasukan", "30000", "Tunai Ryan"))

    def test_tanpa_selisih_tidak_ada_yang_ditutup(self):
        kode, out = self.jalan("tutup", "--akun", "Mandiri Ryan", "--saldo", "4975000",
                               "--channel", "whatsapp", "--pencatat", "Eryanto")
        self.assertEqual(kode, 2)
        self.assertEqual(self.catatan(), [])


class KategoriKhusus(Dasar):
    def test_pencatatan_biasa_tidak_boleh_memakai_reconciliation(self):
        kode, pesan = catat.catat({"tanggal": "2026-11-12", "tipe": "pengeluaran", "channel": "whatsapp",
                                   "pencatat": "Eryanto", "items": [{"kategori": "reconciliation",
                                                                      "item": "x", "jumlah": 1}]})
        self.assertEqual(kode, 2)
        self.assertIn("rekonsiliasi.py tutup", pesan)


    def test_mengubah_kategori_menjadi_reconciliation_ditolak(self):
        kode, pesan = buku.jalankan(buku.skema_bills(), "ubah", {"no_resi": "A1", "oleh": "Eryanto",
                                                                  "set": {"kategori": "reconciliation"}}, uji=True)
        self.assertNotEqual(kode, 0)
        self.assertIn("rekonsiliasi.py tutup", pesan)


class PeringatanSebelumRekonsiliasi(Dasar):
    def setUp(self):
        super().setUp()
        self.jalan("simpan", "--akun", "Mandiri Ryan", "--saldo", "4975000", "--cara", "cocok")

    def test_mengubah_transaksi_sebelum_rekonsiliasi_menyebut_geserannya(self):
        skema = buku.skema_bills()
        kode, pesan = buku.jalankan(skema, "ubah", {"no_resi": "A1", "set": {"jumlah": "50000"},
                                                    "oleh": "Eryanto"}, uji=True)
        self.assertEqual(kode, 0, pesan)
        self.assertIn("⚠️ Transaksi ini bertanggal sebelum rekonsiliasi Mandiri Ryan 12 Nov 2026", pesan)
        self.assertIn("bergeser -Rp 30.000", pesan)

    def test_menambah_transaksi_sebelum_rekonsiliasi_diperingatkan(self):
        kode, pesan = catat.catat({"tanggal": "2026-11-11", "tipe": "pengeluaran", "channel": "whatsapp",
                                   "pencatat": "Eryanto", "akun": "Mandiri Ryan", "waktu": "15:00",
                                   "items": [{"kategori": "food", "item": "Kopi", "jumlah": 12_000}]})
        self.assertEqual(kode, 0, pesan)
        self.assertIn("bergeser -Rp 12.000", pesan)

    def test_transaksi_sesudah_rekonsiliasi_tidak_diperingatkan(self):
        kode, pesan = catat.catat({"tanggal": "2026-11-13", "tipe": "pengeluaran", "channel": "whatsapp",
                                   "pencatat": "Eryanto", "akun": "Mandiri Ryan", "waktu": "15:00",
                                   "items": [{"kategori": "food", "item": "Kopi", "jumlah": 12_000}]})
        self.assertNotIn("rekonsiliasi", pesan)

    def test_akun_lain_tidak_diperingatkan(self):
        self.assertEqual(rk.peringatan(self.catatan(), AKUN, [], [tx("2026-11-11", "pengeluaran", 1, "Tunai Ryan")]),
                         [])


class LaporanDanCermin(Dasar):
    def test_baris_laporan_bulanan_belum_dicek_dan_selisih_terbuka(self):
        self.jalan("simpan", "--akun", "Mandiri Ryan", "--saldo", "4725000", "--cara", "dibiarkan")
        self.assertEqual(rk.baris_laporan(self.catatan(), AKUN, "2026-11"),
                         "🏦 Rekonsiliasi November: belum dicek Tunai Ryan · selisih terbuka Mandiri Ryan -Rp 250.000")

    def test_semua_dicek(self):
        for akun, saldo in (("Mandiri Ryan", "4975000"), ("Tunai Ryan", "100000")):
            self.jalan("simpan", "--akun", akun, "--saldo", saldo, "--cara", "cocok")
        self.assertEqual(rk.baris_laporan(self.catatan(), AKUN, "2026-11"),
                         "🏦 Rekonsiliasi November: semua akun sudah dicek")

    def test_bulan_sebelum_cutover_dan_akun_belum_aktif_tanpa_baris(self):
        self.assertIsNone(rk.baris_laporan([], AKUN, "2026-10"))
        self.assertIsNone(rk.baris_laporan([], {**AKUN, "saldo_global_saat_cutover": None}, "2026-11"))

    def test_tab_saldo_per_akun_mendapat_bagian_rekonsiliasi(self):
        self.jalan("simpan", "--akun", "Mandiri Ryan", "--saldo", "4725000", "--cara", "dibiarkan")
        grid = sheets_laporan.grid_saldo_akun(self.baca(), AKUN, date(2026, 11, 12), self.catatan())
        i = next(i for i, b in enumerate(grid) if b and b[0] == "Akun")
        self.assertEqual(grid[i], ["Akun", "Saldo Akun", "Terakhir Dicek", "Saldo Nyata Terakhir", "Selisih Terbuka"])
        self.assertEqual(grid[i + 1], ["Tunai Ryan", 200_000, "belum", "", 0])
        self.assertEqual(grid[i + 2], ["Mandiri Ryan", 4_875_000, "12 Nov 2026", 4_725_000, -250_000])


if __name__ == "__main__":
    unittest.main()
