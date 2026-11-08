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
import sheets_format  # noqa: E402
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
        self.sheets = {}      # judul → {"id", "baris", "rowCount", "colCount", "lindung", "grup", ...}
        self.panggilan = []   # (metode, sisa url, params, json)
        self.format = []      # request repeatCell yang diterima
        self.locale = "en_US"
        self._id_lindung = 0
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
        if metode == "GET" and sisa == "" and params["fields"].startswith("properties"):
            return Jawaban(200, {"properties": {"locale": self.locale}})
        if metode == "GET" and sisa == "":
            return Jawaban(200, {"sheets": [{
                "properties": {"sheetId": s["id"], "title": t, "index": s["index"],
                               "gridProperties": {"rowCount": s["rowCount"], "columnCount": s["colCount"]}},
                "protectedRanges": [{"protectedRangeId": i, "description": d} for i, d in s["lindung"].items()],
                "columnGroups": [{"range": {"startIndex": a, "endIndex": b}} for a, b in s["grup"]]}
                for t, s in sorted(self.sheets.items(), key=lambda x: x[1]["index"])]})
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

    def _sheet(self, sid):
        return next((x for x in self.sheets.values() if x["id"] == sid), None)

    def _ubah(self, r):
        (jenis, isi), = r.items()
        if jenis == "addSheet":
            judul = isi["properties"]["title"]
            if judul in self.sheets:
                return Jawaban(400, {"error": {"message": "judul sudah ada"}})
            self.sheets[judul] = {"id": 100 + len(self.sheets), "baris": [], "rowCount": 1000, "colCount": 26,
                                  "index": len(self.sheets), "lindung": {}, "grup": set(), "beku": None,
                                  "validasi": {}, "catatan": {}}
            return {"addSheet": {"properties": {"sheetId": self.sheets[judul]["id"], "title": judul}}}
        if jenis == "updateSpreadsheetProperties":
            self.locale = isi["properties"]["locale"]
            return {}
        sid = (isi.get("properties") or isi.get("range") or isi.get("dimensionGroup", {}).get("range")
               or isi.get("protectedRange", {}).get("range") or {}).get("sheetId", isi.get("sheetId"))
        sheet = self._sheet(sid)
        if sheet is None and jenis != "deleteProtectedRange":
            return Jawaban(400, {"error": {"message": f"{jenis}: sheetId tidak ada"}})
        if jenis == "updateSheetProperties":
            g = isi["properties"].get("gridProperties", {})
            if isi["fields"] == "gridProperties.rowCount,gridProperties.columnCount":
                sheet["rowCount"], sheet["colCount"] = g["rowCount"], g["columnCount"]
            elif isi["fields"] == "gridProperties.frozenRowCount,gridProperties.frozenColumnCount":
                sheet["beku"] = (g["frozenRowCount"], g["frozenColumnCount"])
            elif isi["fields"] == "index":
                lain = sorted((x for x in self.sheets.values() if x is not sheet), key=lambda x: x["index"])
                lain.insert(isi["properties"]["index"], sheet)
                for i, x in enumerate(lain):
                    x["index"] = i
            else:
                return Jawaban(400, {"error": {"message": "updateSheetProperties salah"}})
            return {}
        if jenis == "repeatCell":
            if not isi["fields"].startswith("userEnteredFormat."):
                return Jawaban(400, {"error": {"message": "field mask salah"}})
            self.format.append(isi)
            return {}
        if jenis == "addProtectedRange":
            self._id_lindung += 1
            sheet["lindung"][self._id_lindung] = isi["protectedRange"]["description"]
            sheet.setdefault("rentang_lindung", []).append(isi["protectedRange"])
            return {"addProtectedRange": {"protectedRange": {"protectedRangeId": self._id_lindung}}}
        if jenis == "deleteProtectedRange":
            for x in self.sheets.values():
                if x["lindung"].pop(isi["protectedRangeId"], None) is not None:
                    return {}
            return Jawaban(400, {"error": {"message": "protectedRangeId tidak ada"}})
        if jenis == "updateCells":
            sheet["catatan"][isi["range"]["startColumnIndex"]] = isi["rows"][0]["values"][0]["note"]
            return {}
        if jenis == "setDataValidation":
            sheet["validasi"][isi["range"]["startColumnIndex"]] = isi["rule"]
            return {}
        if jenis == "addDimensionGroup":
            sheet["grup"].add((isi["range"]["startIndex"], isi["range"]["endIndex"]))
            return {}
        if jenis == "updateDimensionGroup":
            return {}
        if jenis == "deleteSheet":
            judul = next(t for t, x in self.sheets.items() if x is sheet)
            del self.sheets[judul]
            return {}
        raise AssertionError(f"request tak dikenal: {jenis}")

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
        self.klien = sheets_google.KlienGoogle(ID, self.sesi, tidur=lambda detik: None)

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

    TATA = {"baris_header": 0, "beku_kolom": 2, "format": {0: "tanggal", 1: "teks", 2: "rupiah"},
            "hanya_baca": [2], "catatan": {2: "otomatis"}, "pilihan": {1: ["Gaji", "food"]},
            "grup": [(1, 2)], "locale": "id_ID"}

    def test_tata_dipasang_sebelum_isi_ditulis(self):
        self.klien.tulis("Buku Kas", [["Tanggal", "Kategori", "Saldo"], [46270, "Gaji", 5]], self.TATA)

        pola = {f["range"]["startColumnIndex"]: f["cell"]["userEnteredFormat"]["numberFormat"]
                for f in self.sesi.format if "numberFormat" in f["cell"]["userEnteredFormat"]}
        self.assertEqual(pola[0], {"type": "DATE", "pattern": "d mmm yyyy"})
        self.assertEqual(pola[1], {"type": "TEXT"})
        self.assertIn("Rp", pola[2]["pattern"])
        self.assertTrue(all(f["range"]["startRowIndex"] == 1 for f in self.sesi.format
                            if "numberFormat" in f["cell"]["userEnteredFormat"]))  # header tetap teks
        urutan = [(m, sisa) for m, sisa, _, _ in self.sesi.panggilan if m in ("PUT", "POST")]
        i_isi = next(i for i, (m, _) in enumerate(urutan) if m == "PUT")
        self.assertTrue(all(sisa == ":batchUpdate" for _, sisa in urutan[:i_isi]))  # tata & locale dulu
        sheet = self.sesi.sheets["Buku Kas"]
        self.assertEqual(sheet["beku"], (1, 2))
        self.assertEqual(list(sheet["lindung"].values()), [sheets_google.PENANDA])
        self.assertTrue(sheet["rentang_lindung"][0]["warningOnly"])
        self.assertEqual(sheet["catatan"], {2: "otomatis"})
        aturan = sheet["validasi"][1]
        self.assertFalse(aturan["strict"])
        self.assertEqual([v["userEnteredValue"] for v in aturan["condition"]["values"]], ["Gaji", "food"])
        self.assertEqual(sheet["grup"], {(1, 2)})
        self.assertEqual(self.sesi.locale, "id_ID")

    def test_tata_diulang_tidak_menumpuk_perlindungan_atau_grup(self):
        for _ in range(3):
            self.klien.tulis("Buku Kas", [["Tanggal", "Kategori", "Saldo"]], self.TATA)

        sheet = self.sesi.sheets["Buku Kas"]
        self.assertEqual(len(sheet["lindung"]), 1)
        jenis = [next(iter(r)) for _, sisa, _, j in self.sesi.panggilan if sisa == ":batchUpdate"
                 for r in j["requests"]]
        self.assertEqual(jenis.count("addDimensionGroup"), 1)
        self.assertEqual(jenis.count("updateSpreadsheetProperties"), 1)

    def test_perlindungan_buatan_pengguna_tidak_dihapus(self):
        self.klien.tulis("Buku Kas", [["a"]], self.TATA)
        self.sesi.sheets["Buku Kas"]["lindung"][99] = "punya pemilik"

        self.klien.tulis("Buku Kas", [["a"]], self.TATA)

        self.assertIn(99, self.sesi.sheets["Buku Kas"]["lindung"])

    def test_seluruh_tab_hanya_baca(self):
        self.klien.tulis("Ringkasan Bulanan", [["Bulan"]], {"hanya_baca": "semua"})

        rentang = self.sesi.sheets["Ringkasan Bulanan"]["rentang_lindung"][0]["range"]
        self.assertEqual(set(rentang), {"sheetId"})

    def test_tulis_tanpa_tata_tidak_memformat(self):
        self.klien.tulis("Ringkasan", [["Bulan", "Saldo"], ["2026-07", 1]])

        self.assertEqual(self.sesi.format, [])

    def test_hapus_worksheet_dan_yang_tidak_ada_diabaikan(self):
        self.klien.tulis("Ringkasan", [["a"]])

        self.klien.hapus("Ringkasan")
        self.klien.hapus("Tidak Ada")

        self.assertEqual(self.sesi.sheets, {})

    def test_urutkan_menaruh_tab_sesuai_daftar_dan_tab_lain_di_belakang(self):
        for nama in ("Sheet1", "Buku Kas", "Ringkasan Bulanan"):
            self.klien.tulis(nama, [["a"]])

        self.klien.urutkan(["Ringkasan Bulanan", "Saldo per Akun", "Buku Kas"])

        urut = sorted(self.sesi.sheets, key=lambda t: self.sesi.sheets[t]["index"])
        self.assertEqual(urut, ["Ringkasan Bulanan", "Buku Kas", "Sheet1"])
        self.sesi.panggilan.clear()
        self.klien.urutkan(["Ringkasan Bulanan", "Buku Kas"])
        self.assertEqual([m for m, *_ in self.sesi.panggilan if m == "POST"], [])  # sudah urut: diam

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
        self.klien = sheets_google.KlienGoogle(ID, self.sesi, kolom_waktu={"Buku Kas": {2}},
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

    def test_waktu_serial_dikembalikan_sebagai_teks_tanggal_tetap_serial(self):
        self.klien.tulis("Buku Kas", [["tanggal", 1, "waktu"], ["x", 0, ""]])
        self.sesi.sheets["Buku Kas"]["baris"][1] = [46270, 5, 0.375]  # sel tanpa format teks: serial
        self.sesi.sheets["Buku Kas"]["baris"].append(["2026-09-06", 7, "17:30"])  # sudah teks: apa adanya

        isi = self.klien.baca("Buku Kas")

        self.assertEqual(isi[1], [46270, 5, "09:00"])  # serial tanggal dibaca sheets_format
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
        # budget.json/akun.json dibaca di sebelah resi.BUDGET_JSON; arahkan ke folder sementara
        (d / "budget.json").write_text(json.dumps({"kategori_custom": ["food"], "duplicate_check": {
            "aktif": True, "match_fields": ["tanggal", "waktu", "jumlah"], "aksi": "tolak"}}))
        asli_budget = resi.BUDGET_JSON
        resi.BUDGET_JSON = d / "budget.json"
        self.addCleanup(lambda: setattr(resi, "BUDGET_JSON", asli_budget))
        self.sesi = SesiPalsu()
        self.klien = sheets_google.KlienGoogle(ID, self.sesi, tidur=lambda detik: None)

    def test_sinkron_pertama_lalu_kedua_tidak_menulis_ulang(self):
        sheets_sync.sinkron(self.bills, self.klien, self.snapshot)
        self.sesi.panggilan.clear()

        laporan = sheets_sync.sinkron(self.bills, self.klien, self.snapshot)

        self.assertEqual([m for m, *_ in self.sesi.panggilan if m in ("PUT", "POST")], [])
        self.assertEqual(laporan.didorong, 0)
        self.assertEqual(self.klien.baca("Buku Kas")[1][sheets_format.KOLOM_TAMPIL.index("Pengeluaran")], 25_000)
        self.assertEqual(self.sesi.locale, "id_ID")
        self.assertEqual(sorted(self.sesi.sheets, key=lambda t: self.sesi.sheets[t]["index"]),
                         ["Ringkasan Bulanan", "Per Kategori 2026", "Budget 2026", "Saldo per Akun", "Buku Kas"])

    def test_edit_di_sheet_lewat_adaptor_masuk_ke_csv(self):
        sheets_sync.sinkron(self.bills, self.klien, self.snapshot)
        self.sesi.sheets["Buku Kas"]["baris"][1][sheets_format.KOLOM_TAMPIL.index("Pengeluaran")] = 30_000

        laporan = sheets_sync.sinkron(self.bills, self.klien, self.snapshot)

        self.assertEqual(laporan.diterima, [("TRX-1", 1, ["jumlah"])])
        with open(self.bills, newline="", encoding="utf-8") as f:
            self.assertEqual(next(csv.DictReader(f))["jumlah"], "30000")


if __name__ == "__main__":
    unittest.main()
