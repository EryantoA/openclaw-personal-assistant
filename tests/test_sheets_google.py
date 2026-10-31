"""Tes scripts/sheets_google.py — adaptor Google Sheets, lewat sesi HTTP palsu (tanpa jaringan).

Sesi palsu menirukan perilaku Sheets API yang relevan: sel kosong di ujung kanan dan baris kosong
di ujung bawah dipangkas saat dibaca, angka tetap angka dan teks tetap teks pada isian RAW.

    python3 -m unittest tests/test_sheets_google.py
"""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import resi  # noqa: E402
import sheets_google  # noqa: E402
import sheets_sync  # noqa: E402

ID = "ID-SHEET"
BASIS = f"{sheets_google.API}/{ID}"


class Jawaban:
    def __init__(self, status=200, isi=None):
        self.status_code = status
        self.text = "" if isi is None else json.dumps(isi)
        self._isi = isi

    def json(self):
        return self._isi


class SesiPalsu:
    """Spreadsheet di memori di balik Sheets API v4 (hanya endpoint yang dipakai adaptor)."""

    def __init__(self):
        self.sheets = {}      # judul → {"id": int, "baris": [[...]]}
        self.panggilan = []   # (metode, sisa url, params, json)
        self.format = []      # request repeatCell yang diterima
        self.status = {}      # metode → status error yang dipaksakan

    def request(self, metode, url, params=None, json=None):
        sisa = unquote(url[len(BASIS):])
        self.panggilan.append((metode, sisa, params, json))
        if metode in self.status:
            return Jawaban(self.status[metode], {"error": {"message": "ditolak"}})
        if metode == "GET" and sisa == "":
            return Jawaban(200, {"sheets": [{"properties": {"sheetId": s["id"], "title": t}}
                                            for t, s in self.sheets.items()]})
        if metode == "POST" and sisa == ":batchUpdate":
            balasan = []
            for r in json["requests"]:
                if "addSheet" in r:
                    judul = r["addSheet"]["properties"]["title"]
                    self.sheets[judul] = {"id": 100 + len(self.sheets), "baris": []}
                    balasan.append({"addSheet": {"properties": {"sheetId": self.sheets[judul]["id"],
                                                                 "title": judul}}})
                else:
                    self.format.append(r["repeatCell"])
                    balasan.append({})
            return Jawaban(200, {"replies": balasan})
        judul = sisa.split("/values/")[1].split("'")[1]
        if metode == "GET":
            return Jawaban(200, {"values": self._terpangkas(self.sheets[judul]["baris"])})
        if sisa.endswith(":clear"):
            self.sheets[judul]["baris"] = []
            return Jawaban(200, {})
        if metode == "PUT":  # menimpa sel dari A1; sisa isi lama yang lebih panjang tetap ada
            baris = self.sheets[judul]["baris"]
            for i, b in enumerate(json["values"]):
                if i < len(baris):
                    baris[i][:len(b)] = b
                else:
                    baris.append(list(b))
            return Jawaban(200, {})
        raise AssertionError(f"endpoint tak dikenal: {metode} {sisa}")

    @staticmethod
    def _terpangkas(baris):
        hasil = []
        for b in baris:
            b = list(b)
            while b and b[-1] == "":
                b.pop()
            hasil.append(b)
        while hasil and not hasil[-1]:
            hasil.pop()
        return hasil


class Adaptor(unittest.TestCase):
    def setUp(self):
        self.sesi = SesiPalsu()
        self.klien = sheets_google.KlienGoogle(ID, self.sesi, {"Buku Kas": {1}})

    def test_membaca_worksheet_yang_belum_ada_mengembalikan_kosong_tanpa_membuatnya(self):
        self.assertEqual(self.klien.baca("Buku Kas"), [])
        self.assertEqual(self.sesi.sheets, {})

    def test_tulis_membuat_worksheet_dan_baca_mengembalikan_isi_yang_sama(self):
        grid = [["tanggal", "jumlah"], ["2026-09-05", 20_500_000], ["2026-09-06", 5]]

        self.klien.tulis("Buku Kas", grid)

        self.assertEqual(self.klien.baca("Buku Kas"), grid)
        self.assertEqual(list(self.sesi.sheets), ["Buku Kas"])

    def test_tulis_memakai_raw_supaya_tanggal_tidak_diubah_dan_baca_tanpa_format(self):
        self.klien.tulis("Buku Kas", [["tanggal", "jumlah"], ["2026-09-05", 1]])
        self.klien.baca("Buku Kas")

        params = [p for m, _, p, _ in self.sesi.panggilan if m in ("PUT", "GET") and p]
        self.assertIn({"valueInputOption": "RAW"}, params)
        self.assertIn({"valueRenderOption": "UNFORMATTED_VALUE"}, params)

    def test_tulis_mengganti_seluruh_isi_tanpa_sisa_dari_isi_yang_lebih_panjang(self):
        self.klien.tulis("Buku Kas", [["a", 1, "x"], ["b", 2, "y"], ["c", 3, "z"]])

        self.klien.tulis("Buku Kas", [["a", 1]])

        self.assertEqual(self.klien.baca("Buku Kas"), [["a", 1]])

    def test_kolom_angka_diformat_number_dan_sisanya_text_sebelum_diisi(self):
        self.klien.tulis("Buku Kas", [["tanggal", "jumlah", "item"]])

        jenis = {f["range"]["startColumnIndex"]: f["cell"]["userEnteredFormat"]["numberFormat"]["type"]
                 for f in self.sesi.format}
        self.assertEqual(jenis, {0: "TEXT", 1: "NUMBER", 2: "TEXT"})
        urutan = [m for m, s, _, _ in self.sesi.panggilan if s.startswith(("/values", ":batchUpdate"))]
        self.assertEqual(urutan[-1], "PUT")  # format dikirim sebelum isi

    def test_worksheet_tanpa_pendaftaran_kolom_tidak_diformat(self):
        self.klien.tulis("Ringkasan", [["Bulan", "Saldo"], ["2026-07", 1]])

        self.assertEqual(self.sesi.format, [])

    def test_nama_worksheet_berspasi_dikutip_dan_dikodekan_dalam_url(self):
        self.klien.tulis("Buku Kas", [["a"]])

        urls = [s for _, s, _, _ in self.sesi.panggilan]
        self.assertIn("/values/'Buku Kas'!A1", urls)
        self.assertIn("/values/'Buku Kas':clear", urls)

    def test_jawaban_bukan_2xx_menjadi_gagalgoogle_bukan_diam(self):
        self.sesi.status = {"GET": 403}

        with self.assertRaises(sheets_google.GagalGoogle) as ctx:
            self.klien.baca("Buku Kas")

        self.assertIn("403", str(ctx.exception))

    def test_kegagalan_menulis_tidak_dianggap_berhasil(self):
        self.klien.tulis("Buku Kas", [["a"]])
        self.sesi.status = {"PUT": 500}

        with self.assertRaises(sheets_google.GagalGoogle):
            self.klien.tulis("Buku Kas", [["b"]])


class DenganSinkron(unittest.TestCase):
    """Adaptor + sheets_sync: sel kosong terpangkas dan angka-vs-teks tidak memicu tulis ulang."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = Path(self._tmp.name)
        self.bills, self.snapshot = d / "bills.csv", d / "sheets-snapshot.json"
        asli = resi.BILLS_CSV
        resi.BILLS_CSV = self.bills
        self.addCleanup(lambda: setattr(resi, "BILLS_CSV", asli))
        with open(self.bills, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(sheets_sync.KOLOM)
            w.writerow(["2026-09-01", "pengeluaran", "food", "Nasi", "25000", "", "whatsapp", "Eryanto",
                        "", "", "", "TRX-1"])  # waktu kosong → sel terpangkas di ujung baris? (no_resi ada)
            w.writerow(["2026-09-02", "pengeluaran", "food", "Kopi", "9000", "", "whatsapp", "Eryanto",
                        "", "", "", ""])      # no_resi kosong → baris terpangkas saat dibaca
        self.sesi = SesiPalsu()
        self.klien = sheets_google.KlienGoogle(
            ID, self.sesi, {sheets_sync.SHEET_BUKU: {sheets_sync.KOLOM.index("jumlah")}})

    def test_sinkron_pertama_lalu_kedua_tidak_menulis_ulang(self):
        sheets_sync.sinkron(self.bills, self.klien, self.snapshot)
        self.sesi.panggilan.clear()

        laporan = sheets_sync.sinkron(self.bills, self.klien, self.snapshot)

        self.assertEqual([m for m, *_ in self.sesi.panggilan if m in ("PUT", "POST")], [])
        self.assertEqual(laporan.didorong, 0)
        self.assertEqual(self.klien.baca("Buku Kas")[1][4], 25_000)

    def test_edit_di_sheet_lewat_adaptor_masuk_ke_csv(self):
        sheets_sync.sinkron(self.bills, self.klien, self.snapshot)
        self.sesi.sheets["Buku Kas"]["baris"][1][4] = 30_000
        # budget.json asli dibaca validasi; arahkan ke berkas sementara
        d = self.bills.parent
        (d / "budget.json").write_text(json.dumps({"kategori_custom": ["food"], "duplicate_check": {
            "aktif": True, "match_fields": ["tanggal", "waktu", "jumlah"], "aksi": "tolak"}}))
        asli = resi.BUDGET_JSON
        resi.BUDGET_JSON = d / "budget.json"
        self.addCleanup(lambda: setattr(resi, "BUDGET_JSON", asli))

        laporan = sheets_sync.sinkron(self.bills, self.klien, self.snapshot)

        self.assertEqual(laporan.diterima, [("TRX-1", 1, ["jumlah"])])
        with open(self.bills, newline="", encoding="utf-8") as f:
            self.assertEqual(next(csv.DictReader(f))["jumlah"], "30000")


if __name__ == "__main__":
    unittest.main()
