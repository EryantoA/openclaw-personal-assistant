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


def kolom_ke_angka(huruf):
    n = 0
    for c in huruf:
        n = n * 26 + ord(c) - 64
    return n


class SesiPalsu:
    """Spreadsheet di memori di balik Sheets API v4 (hanya endpoint yang dipakai adaptor).
    Meniru: grid default 1000x26 (menulis di luar grid → 400), isian tanpa valueInputOption ditolak,
    repeatCell harus menunjuk sheetId yang ada, sel kosong di ujung dipangkas saat dibaca."""

    def __init__(self):
        self.sheets = {}      # judul → {"id", "baris", "rowCount", "colCount"}
        self.panggilan = []   # (metode, sisa url, params, json)
        self.format = []      # request repeatCell yang diterima
        self.status = {}      # metode → status error permanen
        self.gagal_dulu = {}  # metode → daftar status yang dikembalikan satu per satu, lalu normal
        self.timeout = []     # timeout yang dikirim tiap panggilan

    def request(self, metode, url, params=None, json=None, timeout=None):
        sisa = unquote(url[len(BASIS):])
        self.panggilan.append((metode, sisa, params, json))
        self.timeout.append(timeout)
        if self.gagal_dulu.get(metode):
            return Jawaban(self.gagal_dulu[metode].pop(0), {"error": {"message": "sibuk"}})
        if metode in self.status:
            return Jawaban(self.status[metode], {"error": {"message": "ditolak"}})
        if metode == "GET" and sisa == "":
            return Jawaban(200, {"sheets": [{"properties": {
                "sheetId": s["id"], "title": t,
                "gridProperties": {"rowCount": s["rowCount"], "columnCount": s["colCount"]}}}
                for t, s in self.sheets.items()]})
        if metode == "POST" and sisa == ":batchUpdate":
            balasan = []
            for r in json["requests"]:
                balasan.append(self._ubah(r))
                if isinstance(balasan[-1], Jawaban):
                    return balasan[-1]
            return Jawaban(200, {"replies": balasan})
        if sisa == "/values:batchClear":
            for rentang in json["ranges"]:
                self._hapus(rentang)
            return Jawaban(200, {})
        judul = self._judul(sisa.split("/values/")[1]) if "/values/" in sisa else None
        if metode == "GET":
            return Jawaban(200, {"values": self._terpangkas(self.sheets[judul]["baris"])})
        if sisa.endswith("':clear"):
            self.sheets[judul]["baris"] = []
            return Jawaban(200, {})
        if metode == "PUT":
            return self._isi(judul, params, json)
        raise AssertionError(f"endpoint tak dikenal: {metode} {sisa}")

    def _ubah(self, r):
        if "addSheet" in r:
            judul = r["addSheet"]["properties"]["title"]
            if judul in self.sheets:
                return Jawaban(400, {"error": {"message": "judul sudah ada"}})
            self.sheets[judul] = {"id": 100 + len(self.sheets), "baris": [], "rowCount": 1000, "colCount": 26}
            return {"addSheet": {"properties": {"sheetId": self.sheets[judul]["id"], "title": judul}}}
        if "updateSheetProperties" in r:
            u = r["updateSheetProperties"]
            sheet = next((x for x in self.sheets.values() if x["id"] == u["properties"]["sheetId"]), None)
            if sheet is None or u["fields"] != "gridProperties.rowCount,gridProperties.columnCount":
                return Jawaban(400, {"error": {"message": "updateSheetProperties salah"}})
            sheet["rowCount"] = u["properties"]["gridProperties"]["rowCount"]
            sheet["colCount"] = u["properties"]["gridProperties"]["columnCount"]
            return {}
        rc = r["repeatCell"]
        if not any(x["id"] == rc["range"]["sheetId"] for x in self.sheets.values()):
            return Jawaban(400, {"error": {"message": "sheetId tidak ada"}})
        if rc["fields"] != "userEnteredFormat.numberFormat":
            return Jawaban(400, {"error": {"message": "field mask salah"}})
        self.format.append(rc)
        return {}

    def _isi(self, judul, params, json):
        if not params or params.get("valueInputOption") not in ("RAW", "USER_ENTERED"):
            return Jawaban(400, {"error": {"message": "valueInputOption wajib"}})
        sheet = self.sheets[judul]
        lebar = max((len(b) for b in json["values"]), default=0)
        if len(json["values"]) > sheet["rowCount"] or lebar > sheet["colCount"]:
            return Jawaban(400, {"error": {"message": "Range exceeds grid limits"}})
        baris = sheet["baris"]  # menimpa sel dari A1; sisa isi lama yang lebih panjang tetap ada
        for i, b in enumerate(json["values"]):
            if i < len(baris):
                baris[i][:len(b)] = b
            else:
                baris.append(list(b))
        return Jawaban(200, {})

    @staticmethod
    def _judul(rentang):
        """Nama worksheet dari rentang A1 `'nama'!sel`; petik di dalam nama ditulis dua kali."""
        i, nama = 1, ""
        while True:
            if rentang[i] == "'":
                if rentang[i + 1:i + 2] == "'":
                    nama, i = nama + "'", i + 2
                    continue
                return nama
            nama, i = nama + rentang[i], i + 1

    def _hapus(self, rentang):
        judul = self._judul(rentang)
        a1 = rentang.rsplit("!", 1)[1]
        (c1, r1), (c2, r2) = [self._sel(x) for x in a1.split(":")]
        baris = self.sheets[judul]["baris"]
        for i in range(r1 - 1, min(r2, len(baris))):
            for j in range(c1 - 1, c2):
                if j < len(baris[i]):
                    baris[i][j] = ""

    @staticmethod
    def _sel(a1):
        huruf = "".join(c for c in a1 if c.isalpha())
        return kolom_ke_angka(huruf), int("".join(c for c in a1 if c.isdigit()))

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
        self.klien = sheets_google.KlienGoogle(ID, self.sesi, {"Buku Kas": {1}}, tidur=lambda detik: None)

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
        urutan = [(m, sisa) for m, sisa, _, _ in self.sesi.panggilan if m in ("PUT", "POST")]
        i_format = next(i for i, (m, sisa) in enumerate(urutan) if sisa == ":batchUpdate" and
                        i > 0)  # batchUpdate sesudah addSheet
        i_isi = next(i for i, (m, _) in enumerate(urutan) if m == "PUT")
        self.assertLess(i_format, i_isi)  # format dikirim sebelum isi

    def test_worksheet_tanpa_pendaftaran_kolom_tidak_diformat(self):
        self.klien.tulis("Ringkasan", [["Bulan", "Saldo"], ["2026-07", 1]])

        self.assertEqual(self.sesi.format, [])

    def test_nama_worksheet_berspasi_dikutip_dan_dikodekan_dalam_url(self):
        self.klien.tulis("Buku Kas", [["a"]])

        self.klien.tulis("Buku Kas", [])
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


class KetahananAdaptor(unittest.TestCase):
    def setUp(self):
        self.sesi = SesiPalsu()
        self.tidur = []
        self.klien = sheets_google.KlienGoogle(
            ID, self.sesi, {"Buku Kas": {1}}, kolom_tanggal={"Buku Kas": {0}}, kolom_waktu={"Buku Kas": {2}},
            tidur=self.tidur.append)

    def test_menulis_lebih_dari_1000_baris_dan_26_kolom_melebarkan_grid_dulu(self):
        grid = [["tanggal", 1, "w"] + [""] * 27] + [[f"r{i}", i, ""] + [""] * 27 for i in range(1, 1500)]

        self.klien.tulis("Buku Kas", grid)

        self.assertEqual(len(self.klien.baca("Buku Kas")), 1500)
        self.assertGreaterEqual(self.sesi.sheets["Buku Kas"]["rowCount"], 1500)
        self.assertGreaterEqual(self.sesi.sheets["Buku Kas"]["colCount"], 30)

    def test_put_yang_gagal_tidak_mengosongkan_isi_lama(self):
        self.klien.tulis("Ringkasan", [["a", 1], ["b", 2]])
        self.sesi.status = {"PUT": 500}

        with self.assertRaises(sheets_google.GagalGoogle):
            self.klien.tulis("Ringkasan", [["c", 3]])

        self.assertEqual(self.klien.baca("Ringkasan"), [["a", 1], ["b", 2]])

    def test_isi_lama_yang_lebih_lebar_dan_lebih_panjang_dibersihkan_setelah_isi_baru(self):
        self.klien.tulis("Ringkasan", [["a", 1, "x", "y"], ["b", 2, "x", "y"], ["c", 3, "x", "y"]])

        self.klien.tulis("Ringkasan", [["a", 1]])

        self.assertEqual(self.klien.baca("Ringkasan"), [["a", 1]])

    def test_baris_pendek_diisi_kosong_agar_sel_lama_di_kanannya_tertimpa(self):
        self.klien.tulis("Ringkasan", [["a", 1, "x"], ["b", 2, "y"]])

        self.klien.tulis("Ringkasan", [["a", 1, "x"], ["b"]])

        self.assertEqual(self.klien.baca("Ringkasan"), [["a", 1, "x"], ["b"]])

    def test_daftar_worksheet_dimuat_ulang_sebelum_menulis_bila_pengguna_menghapusnya(self):
        self.klien.tulis("Ringkasan", [["a"]])
        del self.sesi.sheets["Ringkasan"]  # pengguna menghapus worksheet di antara dua sinkron

        self.klien.tulis("Ringkasan", [["b"]])

        self.assertEqual(self.klien.baca("Ringkasan"), [["b"]])

    def test_429_dan_5xx_diulang_dengan_jeda_naik_lalu_berhasil(self):
        self.sesi.gagal_dulu = {"GET": [429, 503]}

        self.assertEqual(self.klien.baca("Tidak ada"), [])

        self.assertEqual(self.tidur, [1, 2])

    def test_gagal_terus_menyerah_setelah_beberapa_percobaan(self):
        self.sesi.status = {"GET": 503}

        with self.assertRaises(sheets_google.GagalGoogle):
            self.klien.baca("Buku Kas")

        self.assertEqual(len(self.tidur), 3)

    def test_error_klien_tidak_diulang(self):
        self.sesi.status = {"GET": 403}

        with self.assertRaises(sheets_google.GagalGoogle):
            self.klien.baca("Buku Kas")

        self.assertEqual(self.tidur, [])

    def test_setiap_panggilan_membawa_timeout(self):
        self.klien.tulis("Ringkasan", [["a"]])

        self.assertTrue(self.sesi.timeout)
        self.assertNotIn(None, self.sesi.timeout)

    def test_tanggal_dan_waktu_serial_dikembalikan_sebagai_teks(self):
        self.klien.tulis("Buku Kas", [["tanggal", 1, "waktu"], ["x", 0, ""]])
        self.sesi.sheets["Buku Kas"]["baris"][1] = [46270, 5, 0.375]  # sel tanpa format teks: serial
        self.sesi.sheets["Buku Kas"]["baris"].append(["2026-09-06", 7, "17:30"])  # sudah teks: apa adanya

        isi = self.klien.baca("Buku Kas")

        self.assertEqual(isi[1], ["2026-09-05", 5, "09:00"])
        self.assertEqual(isi[2], ["2026-09-06", 7, "17:30"])
        self.assertEqual(isi[0], ["tanggal", 1, "waktu"])

    def test_nama_worksheet_dengan_petik_di_escape(self):
        self.klien.tulis("Kas 'Ani'", [["a"]])

        urls = [s for _, s, _, _ in self.sesi.panggilan]
        self.assertIn("/values/'Kas ''Ani'''!A1", urls)


class Konfigurasi(unittest.TestCase):
    def test_spreadsheet_id_yang_masih_placeholder_atau_kosong_ditolak_sebelum_menyentuh_jaringan(self):
        for id_ in ("", "ID spreadsheet dari URL docs.google.com/spreadsheets/d/<ID>/edit", "pendek"):
            with self.subTest(id_=id_):
                with self.assertRaises(RuntimeError) as ctx:
                    sheets_google.dari_konfigurasi(
                        {"spreadsheet_id": id_, "kunci_akun_layanan": "k.json"}, Path("/tmp"))
                self.assertIn("spreadsheet_id", str(ctx.exception))

    def test_kunci_konfigurasi_yang_hilang_dijelaskan(self):
        with self.assertRaises(RuntimeError) as ctx:
            sheets_google.dari_konfigurasi({"spreadsheet_id": "a" * 40}, Path("/tmp"))
        self.assertIn("kunci_akun_layanan", str(ctx.exception))


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
            ID, self.sesi, {sheets_sync.SHEET_BUKU: {sheets_sync.KOLOM.index("jumlah")}},
            tidur=lambda detik: None)

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
