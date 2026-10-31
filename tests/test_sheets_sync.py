"""Tes scripts/sheets_sync.py — sinkron Buku Kas ke Google Sheets, lewat interface module saja.

Klien Sheets-nya palsu (memori); tidak ada tes yang memanggil Google.

    python3 -m unittest tests/test_sheets_sync.py
"""
import csv
import fcntl
import json
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import resi  # noqa: E402
import sheets_sync  # noqa: E402
import validasi  # noqa: E402

HEADER = ["tanggal", "tipe", "kategori", "item", "jumlah", "catatan", "channel", "pencatat",
          "akun", "akun_tujuan", "waktu", "no_resi"]
HEADER_RINGKASAN = ["Bulan", "Jumlah Transaksi", "Total Pemasukan", "Total Pengeluaran",
                    "Arus Kas Bulan", "Saldo Awal Tercatat", "Saldo Akhir"]


def tx(tanggal, tipe, jumlah, kategori="food", item="x", no_resi="", pencatat="Eryanto"):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "item": item,
            "jumlah": str(jumlah), "pencatat": pencatat, "channel": "whatsapp", "no_resi": no_resi}


DASAR = [
    tx("2026-03-26", "pemasukan", 20_500_000, "opening_balance", "Saldo awal", "SALDO-AWAL"),
    tx("2026-07-05", "pengeluaran", 100_000, item="Nasi", no_resi="TRX-1"),
    tx("2026-07-28", "pemasukan", 5_000_000, "salary", "Gaji", "TRX-2"),
    tx("2026-08-03", "pengeluaran", 300_000, item="Listrik", no_resi="TRX-3"),
    tx("2026-08-12", "transfer", 1_000_000, "other", "Tabung", "TRX-4"),
    tx("2026-08-31", "pengeluaran", 50_000, item="Kopi", no_resi="TRX-5"),
]


def pulihkan_resi(asli):
    resi.BILLS_CSV, resi.BUDGET_JSON, resi.PEMBELI_JSON = asli


class KlienPalsu:
    """Sheets di memori: nama worksheet → grid. Mencatat tiap panggilan; `gagal` berisi nama
    metode ("baca"/"tulis") yang harus melempar ConnectionError; `saat_jaringan(nama)` dipanggil
    di tiap panggilan jaringan (untuk memeriksa keadaan di luar klien)."""

    def __init__(self, isi=None):
        self.sheets = {k: [list(r) for r in v] for k, v in (isi or {}).items()}
        self.tulisan = []
        self.bacaan = 0
        self.gagal = set()
        self.saat_jaringan = None

    def _jaringan(self, metode, nama):
        if self.saat_jaringan:
            self.saat_jaringan(nama)
        if metode in self.gagal:
            raise ConnectionError(f"{metode} {nama} gagal")

    def baca(self, nama):
        self._jaringan("baca", nama)
        self.bacaan += 1
        return [list(r) for r in self.sheets.get(nama, [])]

    def tulis(self, nama, grid):
        self._jaringan("tulis", nama)
        self.sheets[nama] = [list(r) for r in grid]
        self.tulisan.append(nama)


def kunci_dipegang(path):
    """True bila ada pemegang lain kunci `<path>.lock` (flock pada berkas yang dibuka terpisah)."""
    with open(path.with_name(path.name + ".lock"), "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
        return False


class Dasar(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.bills = self.dir / "bills.csv"
        self.snapshot = self.dir / "sheets-snapshot.json"
        self.klien = KlienPalsu()
        (self.dir / "budget.json").write_text(json.dumps({
            "kategori_custom": ["food", "groceries", "transport", "salary", "other", "opening_balance"],
            "duplicate_check": {"aktif": True, "match_fields": ["tanggal", "waktu", "jumlah"],
                                "aksi": "tolak"},
        }), encoding="utf-8")
        (self.dir / "pembeli.json").write_text("{}", encoding="utf-8")
        asli = (resi.BILLS_CSV, resi.BUDGET_JSON, resi.PEMBELI_JSON)
        resi.BILLS_CSV, resi.BUDGET_JSON, resi.PEMBELI_JSON = (
            self.bills, self.dir / "budget.json", self.dir / "pembeli.json")
        self.addCleanup(lambda: pulihkan_resi(asli))

    def tulis_csv(self, rows):
        with open(self.bills, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEADER, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in HEADER})

    def sinkron(self, **kw):
        return sheets_sync.sinkron(self.bills, self.klien, self.snapshot, **kw)

    def baca_csv(self):
        with open(self.bills, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def jejak(self):
        j = self.dir / "riwayat-ubah.csv"
        if not j.exists():
            return []
        with open(j, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def baris_sheet(self, no_resi, item_ke=1):
        """Indeks baris di worksheet "Buku Kas" untuk Item ke-`item_ke` dari Transaksi itu."""
        cocok = [i for i, b in enumerate(self.klien.sheets["Buku Kas"]) if i and b[11] == no_resi]
        return cocok[item_ke - 1]

    def ubah_sheet(self, no_resi, kolom, nilai, item_ke=1):
        self.klien.sheets["Buku Kas"][self.baris_sheet(no_resi, item_ke)][HEADER.index(kolom)] = nilai


class SinkronKeluarPertama(Dasar):
    def test_sheet_kosong_menerima_semua_transaksi_dan_ringkasan(self):
        self.tulis_csv(DASAR)

        laporan = self.sinkron()

        buku = self.klien.sheets["Buku Kas"]
        self.assertEqual(buku[0], HEADER)
        self.assertEqual(len(buku), 1 + 6)
        self.assertEqual(buku[1], ["2026-03-26", "pemasukan", "opening_balance", "Saldo awal",
                                   20_500_000, "", "whatsapp", "Eryanto", "", "", "", "SALDO-AWAL"])
        self.assertEqual(laporan.didorong, 6)
        self.assertEqual(self.klien.sheets["Ringkasan"], [
            HEADER_RINGKASAN,
            ["2026-03", 1, 0, 0, 0, 20_500_000, 20_500_000],
            ["2026-07", 2, 5_000_000, 100_000, 4_900_000, "", 25_400_000],
            ["2026-08", 3, 0, 350_000, -350_000, "", 25_050_000],
        ])

    def test_struk_multi_item_tampil_sebagai_beberapa_baris_berresi_sama(self):
        self.tulis_csv([
            tx("2026-09-01", "pengeluaran", 20_000, item="Susu", no_resi="STRUK-9"),
            tx("2026-09-01", "pengeluaran", 5_000, item="Roti", no_resi="STRUK-9"),
        ])

        self.sinkron()

        buku = self.klien.sheets["Buku Kas"]
        self.assertEqual([(b[3], b[4], b[11]) for b in buku[1:]],
                         [("Susu", 20_000, "STRUK-9"), ("Roti", 5_000, "STRUK-9")])

    def test_jumlah_berformat_rupiah_dikirim_sebagai_angka(self):
        self.tulis_csv([tx("2026-09-01", "pengeluaran", "Rp 88.500", no_resi="TRX-1")])

        self.sinkron()

        self.assertEqual(self.klien.sheets["Buku Kas"][1][4], 88_500)


class SinkronBerulang(Dasar):
    def test_sinkron_kedua_tanpa_perubahan_tidak_menulis_apa_pun(self):
        self.tulis_csv(DASAR)
        self.sinkron()
        self.klien.tulisan.clear()
        snapshot_sebelum = self.snapshot.read_text()

        laporan = self.sinkron()

        self.assertEqual(self.klien.tulisan, [])
        self.assertEqual(self.snapshot.read_text(), snapshot_sebelum)
        self.assertEqual(laporan.didorong, 0)

    def test_transaksi_baru_di_csv_muncul_di_sheet_pada_sinkron_berikutnya(self):
        self.tulis_csv(DASAR)
        self.sinkron()
        self.tulis_csv(DASAR + [tx("2026-09-02", "pengeluaran", 75_000, item="Bensin", no_resi="TRX-6")])

        laporan = self.sinkron()

        buku = self.klien.sheets["Buku Kas"]
        self.assertEqual(buku[-1][3:5], ["Bensin", 75_000])
        self.assertEqual(laporan.didorong, 7)
        self.assertEqual(self.klien.sheets["Ringkasan"][-1],
                         ["2026-09", 1, 0, 75_000, -75_000, "", 24_975_000])

    def test_transaksi_yang_diubah_di_csv_menimpa_sel_di_sheet(self):
        self.tulis_csv(DASAR)
        self.sinkron()
        ubah = [dict(r) for r in DASAR]
        ubah[1]["jumlah"] = "120000"
        self.tulis_csv(ubah)

        self.sinkron()

        self.assertEqual(self.klien.sheets["Buku Kas"][2][4], 120_000)

    def test_snapshot_menyimpan_isi_yang_baru_disinkronkan(self):
        self.tulis_csv(DASAR)

        self.sinkron()

        isi = json.loads(self.snapshot.read_text())
        self.assertEqual(isi["buku_kas"], self.klien.sheets["Buku Kas"])
        self.assertEqual(isi["ringkasan"], self.klien.sheets["Ringkasan"])


class ModeUjiDanInisialisasi(Dasar):
    def test_uji_melapor_tanpa_menulis_ke_sheet_maupun_snapshot(self):
        self.tulis_csv(DASAR)

        laporan = self.sinkron(uji=True)

        self.assertEqual(laporan.didorong, 6)
        self.assertEqual(self.klien.tulisan, [])
        self.assertFalse(self.snapshot.exists())

    def test_sheet_berisi_data_tanpa_snapshot_ditolak_dan_tidak_disentuh(self):
        self.tulis_csv(DASAR)
        orang = [HEADER, ["2026-01-01", "pengeluaran", "food", "Punya orang", 1, "", "", "", "", "", "", "X-1"]]
        self.klien = KlienPalsu({"Buku Kas": orang})

        with self.assertRaises(sheets_sync.SinkronDitolak):
            self.sinkron()

        self.assertEqual(self.klien.tulisan, [])
        self.assertEqual(self.klien.sheets["Buku Kas"], orang)
        self.assertFalse(self.snapshot.exists())

    def test_inisialisasi_menimpa_sheet_dari_csv(self):
        self.tulis_csv(DASAR)
        orang = [HEADER, ["2026-01-01", "pengeluaran", "food", "Punya orang", 1, "", "", "", "", "", "", "X-1"]]
        self.klien = KlienPalsu({"Buku Kas": orang})

        self.sinkron(inisialisasi=True)

        self.assertEqual(len(self.klien.sheets["Buku Kas"]), 1 + 6)
        self.assertTrue(self.snapshot.exists())

    def test_sheet_hanya_berisi_header_dianggap_kosong(self):
        self.tulis_csv(DASAR)
        self.klien = KlienPalsu({"Buku Kas": [HEADER]})

        self.sinkron()

        self.assertEqual(len(self.klien.sheets["Buku Kas"]), 1 + 6)

    def test_sheet_berisi_data_dengan_snapshot_tidak_ditolak(self):
        self.tulis_csv(DASAR)
        self.sinkron()
        self.klien.sheets["Buku Kas"][1][3] = "Diubah di Sheet"
        self.tulis_csv(DASAR + [tx("2026-09-02", "pengeluaran", 1_000, no_resi="TRX-6")])

        self.sinkron()

        self.assertEqual(len(self.klien.sheets["Buku Kas"]), 1 + 7)


class KetahananBacaan(Dasar):
    def test_sel_kosong_di_ujung_kanan_yang_dipangkas_sheets_tidak_memicu_tulis_ulang(self):
        self.tulis_csv(DASAR + [tx("2026-09-01", "pengeluaran", 9_000, item="Baris lama tanpa resi")])
        self.sinkron()
        # Google menghapus sel kosong di ujung kanan tiap baris saat dibaca.
        for nama, grid in self.klien.sheets.items():
            for baris in grid:
                while baris and baris[-1] == "":
                    baris.pop()
        self.assertEqual(len(self.klien.sheets["Buku Kas"][-1]), 8)  # prasyarat: benar-benar terpangkas
        self.klien.tulisan.clear()

        laporan = self.sinkron()

        self.assertEqual(self.klien.tulisan, [])
        self.assertEqual(laporan.didorong, 0)

    def test_csv_hilang_menolak_dan_tidak_menimpa_sheet(self):
        self.tulis_csv(DASAR)
        self.sinkron()
        self.bills.unlink()
        self.klien.tulisan.clear()

        with self.assertRaises(sheets_sync.SinkronDitolak):
            self.sinkron()

        self.assertEqual(self.klien.tulisan, [])
        self.assertEqual(len(self.klien.sheets["Buku Kas"]), 1 + 6)

    def test_baris_tak_terhitung_tampil_di_sheet_dan_dilaporkan_beserta_alasannya(self):
        self.tulis_csv(DASAR + [tx("rusak", "pengeluaran", 1_000, no_resi="TRX-9"),
                                tx("2026-09-01", "ngawur", 2_000, no_resi="TRX-10")])

        laporan = self.sinkron()

        self.assertEqual(len(self.klien.sheets["Buku Kas"]), 1 + 8)
        self.assertEqual(laporan.tak_terhitung, [
            ("TRX-9", "tanggal tidak sah: 'rusak'"),
            ("TRX-10", "tipe tidak dikenal: 'ngawur'"),
        ])
        self.assertNotIn("2026-09", [b[0] for b in self.klien.sheets["Ringkasan"]])


class SinkronMasuk(Dasar):
    def setUp(self):
        super().setUp()
        self.tulis_csv(DASAR)
        self.sinkron()
        self.csv_awal = self.bills.read_bytes()
        self.klien.tulisan.clear()

    def test_sel_valid_yang_diubah_di_sheet_masuk_ke_csv_lewat_jalan_resmi(self):
        self.ubah_sheet("TRX-1", "jumlah", 120_000)

        laporan = self.sinkron()

        self.assertEqual([r["jumlah"] for r in self.baca_csv() if r["no_resi"] == "TRX-1"], ["120000"])
        self.assertEqual(laporan.diterima, [("TRX-1", 1, ["jumlah"])])
        self.assertEqual(laporan.ditolak, [])
        self.assertEqual([(j["aksi"], j["no_resi"], j["oleh"]) for j in self.jejak()],
                         [("ubah", "TRX-1", "sheets")])
        self.assertTrue(list((self.dir / "backups").glob("bills_sebelum-*")))
        # Ringkasan ikut mengikuti CSV yang baru, dan sinkron berikutnya sunyi
        self.assertEqual(self.klien.sheets["Ringkasan"][2][3], 120_000)
        self.klien.tulisan.clear()
        self.sinkron()
        self.assertEqual(self.klien.tulisan, [])

    def test_nilai_tidak_sah_ditolak_sheet_dikembalikan_csv_tak_berubah(self):
        for kolom, nilai in [("kategori", "kategori-asing"), ("jumlah", "banyak"),
                             ("tanggal", "kemarin sore")]:
            with self.subTest(kolom=kolom):
                asli = self.klien.sheets["Buku Kas"][self.baris_sheet("TRX-1")][HEADER.index(kolom)]
                self.ubah_sheet("TRX-1", kolom, nilai)

                laporan = self.sinkron()

                self.assertEqual(self.bills.read_bytes(), self.csv_awal)
                self.assertEqual(self.klien.sheets["Buku Kas"][self.baris_sheet("TRX-1")][HEADER.index(kolom)],
                                 asli)
                self.assertEqual([(r, k) for r, k, _ in laporan.ditolak], [("TRX-1", 1)])
                self.assertTrue(laporan.ditolak[0][2])
                self.assertEqual(laporan.diterima, [])

    def test_satu_baris_semua_atau_tidak_sama_sekali(self):
        self.ubah_sheet("TRX-1", "jumlah", 120_000)
        self.ubah_sheet("TRX-1", "kategori", "kategori-asing")

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(len(laporan.ditolak), 1)

    def test_kolom_terkunci_dan_saldo_awal_ditolak_dan_dikembalikan(self):
        kasus = [("TRX-1", "channel", "telegram"), ("SALDO-AWAL", "jumlah", 1)]
        for no_resi, kolom, nilai in kasus:
            with self.subTest(no_resi=no_resi, kolom=kolom):
                self.ubah_sheet(no_resi, kolom, nilai)

                laporan = self.sinkron()

                self.assertEqual(self.bills.read_bytes(), self.csv_awal)
                self.assertEqual([r for r, _, _ in laporan.ditolak], [no_resi])
                self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))

    def test_no_resi_yang_diubah_di_sheet_tidak_mengubah_csv_dan_dipulihkan(self):
        self.ubah_sheet("TRX-1", "no_resi", "TRX-SALAH")

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))
        self.assertEqual(laporan.dipulihkan, [])
        self.assertEqual([(r, k) for r, k, _ in laporan.ditolak], [("TRX-1", 1)])
        self.assertIn("no_resi", laporan.ditolak[0][2])
        self.assertIn("terkunci", laporan.ditolak[0][2])

    def test_baris_yang_dihapus_dari_sheet_dipulihkan_dan_csv_utuh(self):
        del self.klien.sheets["Buku Kas"][self.baris_sheet("TRX-1")]

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(len(self.klien.sheets["Buku Kas"]), 1 + 6)
        self.assertEqual(laporan.dipulihkan, [("TRX-1", 1)])

    def test_baris_yang_berubah_di_kedua_sisi_dimenangkan_csv(self):
        csv_baru = [dict(r) for r in DASAR]
        csv_baru[1]["jumlah"] = "111000"
        self.tulis_csv(csv_baru)
        self.ubah_sheet("TRX-1", "jumlah", 120_000)

        laporan = self.sinkron()

        self.assertEqual([r["jumlah"] for r in self.baca_csv() if r["no_resi"] == "TRX-1"], ["111000"])
        self.assertEqual(self.klien.sheets["Buku Kas"][self.baris_sheet("TRX-1")][4], 111_000)
        self.assertEqual([(r, k) for r, k, _ in laporan.ditolak], [("TRX-1", 1)])
        self.assertIn("konflik", laporan.ditolak[0][2])

    def test_sheet_dan_csv_yang_sama_sama_berubah_ke_nilai_sama_tidak_dianggap_konflik(self):
        csv_baru = [dict(r) for r in DASAR]
        csv_baru[1]["jumlah"] = "120000"
        self.tulis_csv(csv_baru)
        self.ubah_sheet("TRX-1", "jumlah", 120_000)

        laporan = self.sinkron()

        self.assertEqual(laporan.ditolak, [])
        self.assertEqual(laporan.diterima, [])

    def test_edit_di_ringkasan_ditimpa(self):
        self.klien.sheets["Ringkasan"][1][6] = 999

        self.sinkron()

        self.assertEqual(self.klien.sheets["Ringkasan"][1][6], 20_500_000)
        self.assertEqual(self.bills.read_bytes(), self.csv_awal)

    def test_bulan_yang_sudah_dilaporkan_berubah_muncul_sebagai_peringatan_koreksi(self):
        (self.dir / "laporan-bulanan.json").write_text(
            json.dumps({"bulan": {"2026-07": {"pemasukan": 5_000_000, "pengeluaran": 100_000}}}),
            encoding="utf-8")
        self.ubah_sheet("TRX-1", "jumlah", 120_000)

        laporan = self.sinkron()

        self.assertTrue(any("2026-07" in p and "Koreksi" in p for p in laporan.peringatan))

    def test_uji_melapor_perubahan_masuk_tanpa_menulis_apa_pun(self):
        self.ubah_sheet("TRX-1", "jumlah", 120_000)
        snapshot_sebelum = self.snapshot.read_text()

        laporan = self.sinkron(uji=True)

        self.assertEqual(laporan.diterima, [("TRX-1", 1, ["jumlah"])])
        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(self.klien.tulisan, [])
        self.assertEqual(self.snapshot.read_text(), snapshot_sebelum)
        self.assertEqual(self.jejak(), [])

    def test_baris_tanpa_no_resi_tidak_bisa_diubah_dari_sheet(self):
        self.tulis_csv(DASAR + [tx("2026-09-01", "pengeluaran", 9_000, item="Baris lama")])
        self.sinkron()
        csv_sebelum = self.bills.read_bytes()
        self.klien.sheets["Buku Kas"][-1][4] = 10_000

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), csv_sebelum)
        self.assertEqual(len(laporan.ditolak), 1)
        self.assertIn("no_resi", laporan.ditolak[0][2])
        self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))

    def test_sheet_diurutkan_ulang_tidak_dianggap_perubahan_apa_pun(self):
        self.tulis_csv(DASAR + [tx("2026-09-01", "pengeluaran", 9_000, item="Baris lama")])
        self.sinkron()
        csv_sebelum = self.bills.read_bytes()
        isi = self.klien.sheets["Buku Kas"]
        isi[1:] = sorted(isi[1:], key=lambda b: int(b[4]))

        laporan = self.sinkron()

        self.assertEqual((laporan.diterima, laporan.ditolak, laporan.dipulihkan), ([], [], []))
        self.assertEqual(self.bills.read_bytes(), csv_sebelum)
        self.assertEqual(self.jejak(), [])
        self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))

    def test_jumlah_desimal_ditolak_bukan_dibaca_sebagai_ribuan(self):
        self.ubah_sheet("TRX-1", "jumlah", 88_500.5)

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual([(r, k) for r, k, _ in laporan.ditolak], [("TRX-1", 1)])
        self.assertIn("jumlah", laporan.ditolak[0][2])

    def test_jumlah_berformat_rupiah_diterima(self):
        self.ubah_sheet("TRX-1", "jumlah", "Rp 88.500")

        laporan = self.sinkron()

        self.assertEqual([r["jumlah"] for r in self.baca_csv() if r["no_resi"] == "TRX-1"], ["88500"])
        self.assertEqual(laporan.ditolak, [])


class SinkronMasukMultiItem(Dasar):
    def setUp(self):
        super().setUp()
        self.tulis_csv([
            tx("2026-09-01", "pengeluaran", 20_000, item="Susu", no_resi="STRUK-9"),
            tx("2026-09-01", "pengeluaran", 5_000, item="Roti", no_resi="STRUK-9"),
        ])
        self.sinkron()

    def test_kolom_item_hanya_mengubah_item_yang_diedit(self):
        self.ubah_sheet("STRUK-9", "jumlah", 6_000, item_ke=2)

        laporan = self.sinkron()

        self.assertEqual([r["jumlah"] for r in self.baca_csv()], ["20000", "6000"])
        self.assertEqual(laporan.diterima, [("STRUK-9", 2, ["jumlah"])])

    def test_kolom_tingkat_transaksi_berlaku_untuk_semua_item(self):
        self.ubah_sheet("STRUK-9", "tanggal", "2026-09-02", item_ke=1)

        laporan = self.sinkron()

        self.assertEqual([r["tanggal"] for r in self.baca_csv()], ["2026-09-02", "2026-09-02"])
        self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))
        self.assertEqual(laporan.ditolak, [])

    def test_tingkat_transaksi_dan_item_dalam_satu_baris_sama_sama_masuk(self):
        self.ubah_sheet("STRUK-9", "tanggal", "2026-09-02", item_ke=2)
        self.ubah_sheet("STRUK-9", "jumlah", 6_000, item_ke=2)

        laporan = self.sinkron()

        self.assertEqual([(r["tanggal"], r["jumlah"]) for r in self.baca_csv()],
                         [("2026-09-02", "20000"), ("2026-09-02", "6000")])
        self.assertEqual(laporan.ditolak, [])

    def test_dua_baris_satu_struk_diubah_ke_tanggal_sama_tidak_dilaporkan_ditolak(self):
        self.ubah_sheet("STRUK-9", "tanggal", "2026-09-02", item_ke=1)
        self.ubah_sheet("STRUK-9", "tanggal", "2026-09-02", item_ke=2)

        laporan = self.sinkron()

        self.assertEqual([r["tanggal"] for r in self.baca_csv()], ["2026-09-02", "2026-09-02"])
        self.assertEqual(laporan.ditolak, [])

    def test_item_pertama_yang_dihapus_dari_sheet_dipulihkan_tanpa_menimpa_item_lain(self):
        del self.klien.sheets["Buku Kas"][self.baris_sheet("STRUK-9", 1)]
        csv_awal = self.bills.read_bytes()

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), csv_awal)
        self.assertEqual(laporan.dipulihkan, [("STRUK-9", 1)])
        self.assertEqual((laporan.diterima, laporan.ditolak), ([], []))
        self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))
        self.assertEqual(self.jejak(), [])

    def test_item_dihapus_sambil_item_lain_diedit_tidak_diterapkan(self):
        del self.klien.sheets["Buku Kas"][self.baris_sheet("STRUK-9", 1)]
        self.ubah_sheet("STRUK-9", "jumlah", 6_000, item_ke=1)  # kini Item "Roti" di baris pertama
        csv_awal = self.bills.read_bytes()

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), csv_awal)
        self.assertEqual(laporan.diterima, [])
        self.assertEqual(len(laporan.ditolak), 1)

    def test_item_ditukar_urutannya_di_sheet_tidak_mengubah_csv(self):
        buku = self.klien.sheets["Buku Kas"]
        buku[1], buku[2] = buku[2], buku[1]
        csv_awal = self.bills.read_bytes()

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), csv_awal)
        self.assertEqual((laporan.diterima, laporan.ditolak, laporan.dipulihkan), ([], [], []))
        self.assertEqual(self.jejak(), [])

    def test_uji_dua_baris_satu_struk_diubah_ke_tanggal_sama_dilaporkan_sekali(self):
        self.ubah_sheet("STRUK-9", "tanggal", "2026-09-02", item_ke=1)
        self.ubah_sheet("STRUK-9", "tanggal", "2026-09-02", item_ke=2)

        laporan = self.sinkron(uji=True)

        self.assertEqual(laporan.diterima, [("STRUK-9", 1, ["tanggal"])])


class BarisBaruDariSheets(Dasar):
    def setUp(self):
        super().setUp()
        (self.dir / "pembeli.json").write_text(json.dumps({"Elsi": ["istri"]}), encoding="utf-8")
        ada_waktu = dict(tx("2026-08-20", "pengeluaran", 40_000, item="Bakso", no_resi="TRX-7"), waktu="09:00")
        self.tulis_csv(DASAR + [ada_waktu])
        self.sinkron()
        self.csv_awal = self.bills.read_bytes()
        self.klien.tulisan.clear()

    def tambah(self, **sel):
        isi = dict(tanggal="2026-09-05", tipe="pengeluaran", kategori="food", item="Baru", jumlah=1_000,
                   catatan="", channel="", pencatat="Eryanto", akun="", akun_tujuan="", waktu="",
                   no_resi="")
        isi.update(sel)
        self.klien.sheets["Buku Kas"].append([isi[k] for k in HEADER])

    def test_baris_tanpa_no_resi_menjadi_transaksi_ber_trx_dan_channel_sheets(self):
        self.tambah(item="Parkir", jumlah=3_000)

        laporan = self.sinkron()

        baru = [r for r in self.baca_csv() if r["item"] == "Parkir"]
        self.assertEqual(len(baru), 1)
        self.assertRegex(baru[0]["no_resi"], r"^TRX-20260905-\d{4}$")
        self.assertEqual((baru[0]["channel"], baru[0]["jumlah"]), ("sheets", "3000"))
        self.assertEqual(laporan.ditambah, [baru[0]["no_resi"]])
        self.assertEqual(laporan.ditolak, [])
        baris_sheet = [b for b in self.klien.sheets["Buku Kas"] if b[3] == "Parkir"]
        self.assertEqual([b[11] for b in baris_sheet], [baru[0]["no_resi"]])  # No Resi ditulis balik
        self.assertRegex(baris_sheet[0][10], r"^\d\d:\d\d$")
        self.klien.tulisan.clear()
        self.sinkron()
        self.assertEqual(self.klien.tulisan, [])

    def test_alias_pencatat_dibakukan(self):
        self.tambah(pencatat="istri")

        self.sinkron()

        self.assertEqual([r["pencatat"] for r in self.baca_csv() if r["item"] == "Baru"], ["Elsi"])

    def test_beberapa_baris_ber_no_resi_sama_menjadi_satu_transaksi_multi_item(self):
        self.tambah(no_resi="NOTA-1", item="Susu", jumlah=20_000, waktu="10:00")
        self.tambah(no_resi="NOTA-1", item="Roti", jumlah=5_000, waktu="10:00")

        laporan = self.sinkron()

        baru = [(r["no_resi"], r["item"], r["jumlah"]) for r in self.baca_csv() if r["no_resi"] == "NOTA-1"]
        self.assertEqual(baru, [("NOTA-1", "Susu", "20000"), ("NOTA-1", "Roti", "5000")])
        self.assertEqual(laporan.ditambah, ["NOTA-1"])

    def test_dua_baris_baru_tanpa_no_resi_menjadi_dua_transaksi_terpisah(self):
        self.tambah(item="A", jumlah=1_000, waktu="10:00")
        self.tambah(item="B", jumlah=2_000, waktu="10:01")

        laporan = self.sinkron()

        resi_ = {r["item"]: r["no_resi"] for r in self.baca_csv() if r["item"] in ("A", "B")}
        self.assertEqual(len(set(resi_.values())), 2)
        self.assertEqual(len(laporan.ditambah), 2)

    def test_baris_kembar_lapis_2_ditolak_dan_hilang_dari_sheet_dengan_alasan_dan_isinya(self):
        self.tambah(tanggal="2026-08-20", waktu="09:00", jumlah=40_000, item="Bakso lagi")

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(len(laporan.ditolak), 1)
        self.assertIn("Bakso lagi", laporan.ditolak[0][2])
        self.assertEqual(laporan.ditambah, [])
        self.assertNotIn("Bakso lagi", [b[3] for b in self.klien.sheets["Buku Kas"]])

    def test_no_resi_yang_sudah_ada_ditolak_lapis_1(self):
        self.tambah(no_resi="TRX-2", item="Gaji kedua", jumlah=1_000)

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(len(laporan.ditolak), 1)
        self.assertEqual(laporan.ditambah, [])
        self.assertIn("Gaji kedua", laporan.ditolak[0][2])  # isi baris ikut dilaporkan
        self.assertIn("Duplikat", laporan.ditolak[0][2])

    def test_path_buku_kas_yang_bukan_resi_bills_csv_ditolak_sebelum_ada_yang_ditulis(self):
        self.ubah_sheet("TRX-1", "jumlah", 120_000)  # edit valid yang tidak boleh sempat tertulis
        self.tambah(item="Parkir")
        lain = self.dir / "lain.csv"
        lain.write_bytes(self.bills.read_bytes())

        with self.assertRaises(sheets_sync.SinkronDitolak):
            sheets_sync.sinkron(lain, self.klien, self.snapshot)

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(lain.read_bytes(), self.csv_awal)
        self.assertEqual(self.klien.tulisan, [])

    def test_baris_baru_tidak_sah_ditolak_dengan_alasan_dan_isinya_dan_hilang_dari_sheet(self):
        kasus = [dict(kategori="kategori-asing"), dict(jumlah="banyak"), dict(jumlah=88_500.5),
                 dict(tanggal=""), dict(pencatat=""), dict(tipe="ngawur")]
        for ubah in kasus:
            with self.subTest(ubah=ubah):
                self.tambah(item="Salah", **ubah)

                laporan = self.sinkron()

                self.assertEqual(self.bills.read_bytes(), self.csv_awal)
                self.assertEqual(len(laporan.ditolak), 1)
                self.assertIn("Salah", laporan.ditolak[0][2])
                self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))

    def test_transaksi_baru_yang_kolom_tingkat_transaksinya_tidak_sama_ditolak_seluruhnya(self):
        self.tambah(no_resi="NOTA-2", item="Susu", tanggal="2026-09-05")
        self.tambah(no_resi="NOTA-2", item="Roti", tanggal="2026-09-06")

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(len(laporan.ditolak), 1)
        self.assertEqual(laporan.ditambah, [])

    def test_transfer_baru_dari_sheet_diterima(self):
        self.tambah(tipe="transfer", kategori="transfer", item="Setor", jumlah=500_000,
                    akun="Kas", akun_tujuan="Bank")

        laporan = self.sinkron()

        self.assertEqual(laporan.ditolak, [])
        self.assertEqual([r["tipe"] for r in self.baca_csv() if r["item"] == "Setor"], ["transfer"])

    def test_baris_kosong_di_sheet_diabaikan(self):
        self.klien.sheets["Buku Kas"].append([""] * 12)

        laporan = self.sinkron()

        self.assertEqual((laporan.ditambah, laporan.ditolak), ([], []))

    def test_uji_melapor_transaksi_yang_akan_ditambah_tanpa_menulis(self):
        self.tambah(item="Parkir", jumlah=3_000)

        laporan = self.sinkron(uji=True)

        self.assertEqual(len(laporan.ditambah), 1)
        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(self.klien.tulisan, [])

    def test_baris_baru_tanpa_no_resi_ditolak_bila_ada_baris_lama_tanpa_no_resi_yang_berubah(self):
        # Baris lama tanpa No Resi yang diedit tampak seperti baris hilang + baris baru; jangan
        # membuat Transaksi ganda dari suntingan itu.
        self.tulis_csv(DASAR + [tx("2026-09-01", "pengeluaran", 9_000, item="Baris lama")])
        self.sinkron()
        csv_sebelum = self.bills.read_bytes()
        self.klien.sheets["Buku Kas"][-1][4] = 10_000

        laporan = self.sinkron()

        self.assertEqual(self.bills.read_bytes(), csv_sebelum)
        self.assertEqual(laporan.ditambah, [])
        self.assertEqual(len(laporan.ditolak), 1)


class KunciBerkas(unittest.TestCase):
    def test_kunci_yang_sama_boleh_dimasuki_ulang_oleh_proses_yang_memegangnya(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bills.csv"

            def macet(*_):
                raise AssertionError("kunci_berkas bersarang menunggu dirinya sendiri")

            signal.signal(signal.SIGALRM, macet)
            signal.alarm(3)
            try:
                with validasi.kunci_berkas(path):
                    with validasi.kunci_berkas(path):
                        self.assertTrue(kunci_dipegang(path))
                self.assertFalse(kunci_dipegang(path))  # dilepas setelah blok terluar selesai
            finally:
                signal.alarm(0)


class KetahananSinkron(Dasar):
    def setUp(self):
        super().setUp()
        self.tulis_csv(DASAR)
        self.sinkron()
        self.csv_awal = self.bills.read_bytes()
        self.klien.tulisan.clear()

    def tambah(self, **sel):
        isi = dict(tanggal="2026-09-05", tipe="pengeluaran", kategori="food", item="Parkir", jumlah=3_000,
                   catatan="", channel="", pencatat="Eryanto", akun="", akun_tujuan="", waktu="",
                   no_resi="")
        isi.update(sel)
        self.klien.sheets["Buku Kas"].append([isi[k] for k in HEADER])

    def n_baris(self, item):
        return len([r for r in self.baca_csv() if r["item"] == item])

    def test_kunci_tidak_dipegang_selama_panggilan_jaringan(self):
        dipegang = []
        self.klien.saat_jaringan = lambda nama: dipegang.append(kunci_dipegang(self.bills))
        self.ubah_sheet("TRX-1", "jumlah", 120_000)
        self.tambah()

        self.sinkron()

        self.assertGreaterEqual(len(dipegang), 3)  # baca, baca, tulis…
        self.assertEqual(set(dipegang), {False})

    def test_kunci_dipegang_selama_membaca_csv_dan_menerapkan_perubahan(self):
        dipegang = []
        asli = sheets_sync.buku_kas.muat

        def muat(*a, **kw):
            dipegang.append(kunci_dipegang(self.bills))
            return asli(*a, **kw)

        self.ubah_sheet("TRX-1", "jumlah", 120_000)
        self.tambah()
        with mock.patch.object(sheets_sync.buku_kas, "muat", muat):
            self.sinkron()

        self.assertTrue(dipegang)
        self.assertEqual(set(dipegang), {True})

    def test_sinkron_yang_masih_berjalan_membuat_pemanggilan_kedua_keluar_tanpa_kerja(self):
        self.ubah_sheet("TRX-1", "jumlah", 120_000)
        with open(self.snapshot.with_name(self.snapshot.name + ".lock"), "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # sinkron lain sedang jalan
            bacaan_sebelum = self.klien.bacaan

            laporan = self.sinkron()

        self.assertTrue(laporan.dilewati)
        self.assertEqual(self.klien.bacaan, bacaan_sebelum)
        self.assertEqual(self.klien.tulisan, [])
        self.assertEqual(self.bills.read_bytes(), self.csv_awal)

    def test_tulis_gagal_csv_konsisten_snapshot_tak_berubah_dan_sinkron_berikutnya_menyelesaikan(self):
        self.ubah_sheet("TRX-1", "jumlah", 120_000)
        snapshot_sebelum = self.snapshot.read_text()
        self.klien.gagal = {"tulis"}

        with self.assertRaises(ConnectionError):
            self.sinkron()

        self.assertEqual([r["jumlah"] for r in self.baca_csv() if r["no_resi"] == "TRX-1"], ["120000"])
        self.assertEqual(self.snapshot.read_text(), snapshot_sebelum)
        self.klien.gagal = set()

        laporan = self.sinkron()

        self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))
        self.assertEqual(laporan.ditolak, [])
        self.assertEqual(len(self.jejak()), 1)  # edit yang sama tidak diterapkan dua kali
        self.assertNotEqual(self.snapshot.read_text(), snapshot_sebelum)
        self.klien.tulisan.clear()
        self.sinkron()
        self.assertEqual(self.klien.tulisan, [])

    def test_baca_gagal_tidak_mengubah_apa_pun(self):
        self.ubah_sheet("TRX-1", "jumlah", 120_000)
        snapshot_sebelum = self.snapshot.read_text()
        self.klien.gagal = {"baca"}

        with self.assertRaises(ConnectionError):
            self.sinkron()

        self.assertEqual(self.bills.read_bytes(), self.csv_awal)
        self.assertEqual(self.snapshot.read_text(), snapshot_sebelum)

    def test_baris_baru_tanpa_no_resi_tidak_jadi_ganda_bila_tulis_gagal_lalu_diulang(self):
        self.tambah()  # waktu kosong → jam sekarang; Lapis 2 tidak akan menangkap ulangannya
        self.klien.gagal = {"tulis"}
        with self.assertRaises(ConnectionError):
            self.sinkron()
        pertama = [r["no_resi"] for r in self.baca_csv() if r["item"] == "Parkir"]
        self.assertEqual(len(pertama), 1)
        self.klien.gagal = set()

        laporan = self.sinkron()

        self.assertEqual([r["no_resi"] for r in self.baca_csv() if r["item"] == "Parkir"], pertama)
        self.assertEqual((laporan.ditambah, laporan.ditolak), (pertama, []))
        self.assertEqual([b[11] for b in self.klien.sheets["Buku Kas"] if b[3] == "Parkir"], pertama)

    def test_baris_baru_ber_no_resi_tidak_dilaporkan_duplikat_setelah_gagal(self):
        self.tambah(no_resi="NOTA-9", waktu="10:00", jumlah="Rp 3.000")  # format beda dari yang tersimpan
        self.klien.gagal = {"tulis"}
        with self.assertRaises(ConnectionError):
            self.sinkron()
        self.klien.gagal = set()

        laporan = self.sinkron()

        self.assertEqual(self.n_baris("Parkir"), 1)
        self.assertEqual((laporan.ditambah, laporan.ditolak), (["NOTA-9"], []))

    def test_dua_baris_identik_tetap_ditolak_yang_kedua_bukan_dianggap_sudah_dibuat(self):
        self.tambah(waktu="10:00")
        self.tambah(waktu="10:00")

        laporan = self.sinkron()

        self.assertEqual(self.n_baris("Parkir"), 1)
        self.assertEqual(len(laporan.ditambah), 1)
        self.assertEqual(len(laporan.ditolak), 1)

    def test_jurnal_dibersihkan_setelah_sinkron_sukses(self):
        self.tambah()
        self.sinkron()

        self.assertEqual(list(self.dir.glob("*.jurnal.json")), [])

    def test_snapshot_rusak_ditolak_dengan_petunjuk_dan_tidak_mengubah_apa_pun(self):
        for isi in ("{", "", "{}", "[]"):
            with self.subTest(isi=isi):
                self.snapshot.write_text(isi, encoding="utf-8")

                with self.assertRaises(sheets_sync.SinkronDitolak) as ctx:
                    self.sinkron()

                self.assertIn("inisialisasi", str(ctx.exception))
                self.assertEqual(self.bills.read_bytes(), self.csv_awal)
                self.assertEqual(self.klien.tulisan, [])

    def test_kegagalan_separuh_jalan_pada_dua_permintaan_dilaporkan_sebagian_dan_csv_tetap_sah(self):
        self.tulis_csv([
            tx("2026-09-01", "pengeluaran", 20_000, item="Susu", no_resi="STRUK-9"),
            tx("2026-09-01", "pengeluaran", 5_000, item="Roti", no_resi="STRUK-9"),
            tx("2026-09-02", "pengeluaran", 6_000, item="Lain", no_resi="TRX-X"),
        ])
        self.sinkron(inisialisasi=True)
        # tanggal (semua Item) lolos; jumlah 6000 lalu menyamai TRX-X pada tanggal baru itu
        self.ubah_sheet("STRUK-9", "tanggal", "2026-09-02", item_ke=2)
        self.ubah_sheet("STRUK-9", "jumlah", 6_000, item_ke=2)

        laporan = self.sinkron()

        self.assertEqual([(r["tanggal"], r["jumlah"]) for r in self.baca_csv() if r["no_resi"] == "STRUK-9"],
                         [("2026-09-02", "20000"), ("2026-09-02", "5000")])
        self.assertEqual(len(laporan.ditolak), 1)
        self.assertIn("sebagian", laporan.ditolak[0][2])
        self.assertEqual(self.klien.sheets["Buku Kas"], sheets_sync.grid_buku(self.baca_csv()))


if __name__ == "__main__":
    unittest.main()
