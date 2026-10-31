"""Tes scripts/sinkron-sheets.py — CLI sinkron Buku Kas ↔ Google Sheets, dengan klien palsu.

    python3 -m unittest tests/test_sinkron_sheets.py
"""
import contextlib
import csv
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import resi  # noqa: E402
import sheets_google  # noqa: E402
import sheets_sync  # noqa: E402

spec = importlib.util.spec_from_file_location("cli", AKAR / "scripts" / "sinkron-sheets.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class Klien:
    def __init__(self, isi=None, gagal=False):
        self.sheets = dict(isi or {})
        self.gagal = gagal

    def baca(self, nama):
        if self.gagal:
            raise ConnectionError("jaringan putus")
        return [list(b) for b in self.sheets.get(nama, [])]

    def tulis(self, nama, grid):
        self.sheets[nama] = [list(b) for b in grid]


class CLI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = Path(self._tmp.name)
        self.config, self.snapshot, self.bills = d / "sheets.json", d / "snap.json", d / "bills.csv"
        with open(self.bills, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(sheets_sync.KOLOM)
            w.writerow(["2026-09-01", "pengeluaran", "food", "Nasi", "25000", "", "whatsapp", "Eryanto",
                        "", "", "08:00", "TRX-1"])
        self.klien = Klien()
        for obj, nama, nilai in [(cli, "CONFIG", self.config), (cli, "SNAPSHOT", self.snapshot),
                                 (resi, "BILLS_CSV", self.bills)]:
            p = mock.patch.object(obj, nama, nilai)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(sheets_google, "dari_konfigurasi", lambda *a, **kw: self.klien)
        p.start()
        self.addCleanup(p.stop)

    def jalan(self, *argv):
        keluar, galat = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(keluar), contextlib.redirect_stderr(galat):
            kode = cli.main(list(argv))
        self.stderr = galat.getvalue()
        return kode, keluar.getvalue() + galat.getvalue()

    def tulis_config(self):
        self.config.write_text(json.dumps({"spreadsheet_id": "X", "kunci_akun_layanan": "k.json"}))

    def test_tanpa_konfigurasi_keluar_2_dengan_petunjuk_contoh(self):
        kode, teks = self.jalan("--uji")

        self.assertEqual(kode, 2)
        self.assertIn("sheets.json.example", teks)

    def test_uji_melapor_tanpa_menulis_ke_sheet_atau_snapshot(self):
        self.tulis_config()

        kode, teks = self.jalan("--uji")

        self.assertEqual(kode, 0)
        self.assertIn("uji", teks)
        self.assertIn("Didorong ke Sheet: 1 baris.", teks)
        self.assertEqual(self.klien.sheets, {})
        self.assertFalse(self.snapshot.exists())

    def test_inisialisasi_mengisi_sheet_dan_menulis_snapshot(self):
        self.tulis_config()

        kode, teks = self.jalan("--inisialisasi")

        self.assertEqual(kode, 0)
        self.assertIn("Didorong ke Sheet: 1 baris.", teks)
        self.assertEqual(len(self.klien.sheets["Buku Kas"]), 2)
        self.assertTrue(self.snapshot.exists())

    def test_sheet_berisi_data_tanpa_snapshot_ditolak_dengan_kode_1(self):
        self.tulis_config()
        self.klien.sheets["Buku Kas"] = [sheets_sync.KOLOM, ["2026-01-01"] + [""] * 11]

        kode, teks = self.jalan()

        self.assertEqual(kode, 1)
        self.assertIn("DITOLAK", teks)
        self.assertIn("inisialisasi", teks)

    def test_klien_google_gagal_disiapkan_keluar_2_dengan_pesannya(self):
        self.tulis_config()
        with mock.patch.object(sheets_google, "dari_konfigurasi",
                               side_effect=RuntimeError("google-auth belum terpasang")):
            kode, teks = self.jalan("--uji")

        self.assertEqual(kode, 2)
        self.assertIn("google-auth belum terpasang", teks)

    def test_jaringan_putus_saat_sinkron_keluar_2_agar_cron_tercatat_error(self):
        self.tulis_config()
        self.klien.gagal = True

        kode, teks = self.jalan()

        self.assertEqual(kode, 2)
        self.assertIn("GAGAL", teks)
        self.assertIn("ConnectionError", teks)
        self.assertIn("GAGAL", self.stderr)  # kegagalan ke stderr, supaya pembungkus cron menangkapnya

    def test_ditolak_dicetak_ke_stderr(self):
        self.tulis_config()
        self.klien.sheets["Buku Kas"] = [sheets_sync.KOLOM, ["2026-01-01"] + [""] * 11]

        self.jalan()

        self.assertIn("DITOLAK", self.stderr)

    def test_id_spreadsheet_disamarkan_dari_pesan_kegagalan(self):
        id_ = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
        self.config.write_text(json.dumps({"spreadsheet_id": id_, "kunci_akun_layanan": "k.json"}))
        self.klien.baca = mock.Mock(side_effect=ConnectionError(f"https://sheets.googleapis.com/v4/spreadsheets/{id_}/values"))

        kode, teks = self.jalan()

        self.assertEqual(kode, 2)
        self.assertNotIn(id_, teks)
        self.assertIn("<id>", teks)

    def test_klien_dibuat_dengan_kolom_angka_tanggal_dan_waktu(self):
        self.tulis_config()
        panggilan = {}

        def pabrik(config, akar, kolom_angka=None, kolom_tanggal=None, kolom_waktu=None):
            panggilan.update(angka=kolom_angka, tanggal=kolom_tanggal, waktu=kolom_waktu)
            return self.klien

        with mock.patch.object(sheets_google, "dari_konfigurasi", pabrik):
            self.jalan("--uji")

        K = sheets_sync.KOLOM
        self.assertEqual(panggilan, {"angka": {"Buku Kas": {K.index("jumlah")}},
                                     "tanggal": {"Buku Kas": {K.index("tanggal")}},
                                     "waktu": {"Buku Kas": {K.index("waktu")}}})


if __name__ == "__main__":
    unittest.main()
