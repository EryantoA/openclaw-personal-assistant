"""Tes scripts/sheets_sync.py — sinkron Buku Kas ke Google Sheets, lewat interface module saja.

Klien Sheets-nya palsu (memori); tidak ada tes yang memanggil Google.

    python3 -m unittest tests/test_sheets_sync.py
"""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import sheets_sync  # noqa: E402

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


class KlienPalsu:
    """Sheets di memori: nama worksheet → grid. Mencatat tiap tulisan."""

    def __init__(self, isi=None):
        self.sheets = {k: [list(r) for r in v] for k, v in (isi or {}).items()}
        self.tulisan = []

    def baca(self, nama):
        return [list(r) for r in self.sheets.get(nama, [])]

    def tulis(self, nama, grid):
        self.sheets[nama] = [list(r) for r in grid]
        self.tulisan.append(nama)


class Dasar(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.bills = self.dir / "bills.csv"
        self.snapshot = self.dir / "sheets-snapshot.json"
        self.klien = KlienPalsu()

    def tulis_csv(self, rows):
        with open(self.bills, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEADER, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in HEADER})

    def sinkron(self, **kw):
        return sheets_sync.sinkron(self.bills, self.klien, self.snapshot, **kw)


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


if __name__ == "__main__":
    unittest.main()
