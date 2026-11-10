"""Klien Google Sheets untuk sheets_sync — adaptor tipis, tanpa logika bisnis (spec #20, ADR-0021).

Memenuhi antarmuka yang diminta sheets_sync:

    klien.baca(nama_worksheet) -> list[list]   # grid; worksheet belum ada = []
    klien.tulis(nama_worksheet, grid, tata)    # mengganti seluruh isi; membuat worksheet bila belum ada
    klien.hapus(nama_worksheet)                # tidak ada = tidak apa-apa
    klien.urutkan([nama_worksheet, ...])       # urutan tab; tab lain di belakangnya

Bicara dengan Sheets API v4 lewat sesi HTTP yang disuntikkan (`sesi.request(metode, url, params=,
json=, timeout=)` → objek dengan `status_code`, `json()`, `text`), jadi aturannya bisa diuji tanpa
Google. Sesi sungguhan dibuat `dari_konfigurasi`: akun layanan Google (kunci di luar git) lewat
`google-auth` + `requests`, yang harus terpasang untuk interpreter yang dipakai cron:

    /usr/bin/python3 -m pip install --user google-auth requests

Tulis memakai valueInputOption=RAW: tanggal dikirim sheets_sync sebagai serial dan tampil lewat format
DATE, teks tetap teks. Baca memakai UNFORMATTED_VALUE (angka kembali sebagai angka) dan
mengembalikan serial waktu yang tetap lolos (mis. hasil tempel) di kolom waktu sebagai HH:MM.

`tata` (ADR-0026) dipasang sebelum isi ditulis, dalam satu batchUpdate: format angka per kolom,
kolom/baris beku, latar Olive pucat + perlindungan `warningOnly` untuk bagian hanya-baca (perlindungan
lama, bertanda PENANDA, dihapus dulu supaya tidak menumpuk), catatan header, dropdown tidak ketat,
dan grup kolom (dilipat hanya saat pertama dibuat, supaya pilihan pengguna membukanya bertahan).
Tema warna (ADR-0032): warna teks lama di bagian hanya-baca dibersihkan tiap tulis, lalu warna teks
per kolom (`warna_teks`) dan gaya per sel (`sel`: minus, aman, mendekati, lewat) dipasang ulang; header
Indigo/Olive tebal dipasang terakhir agar tidak tertimpa latar hanya-baca.
Tulis melebarkan grid worksheet bila perlu (worksheet baru hanya 1000 baris × 26 kolom; menulis di
luarnya ditolak Google), menimpa isi dulu baru membersihkan sisa lama (PUT yang gagal tidak
meninggalkan Sheet kosong), dan mengulang 429/5xx dengan jeda naik.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import json
import re
import time
import warnings
from pathlib import Path
from urllib.parse import quote

API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TIMEOUT = 60                      # detik per panggilan; tanpa ini jaringan macet menahan sinkron
JEDA = (1, 2, 4)                  # detik sebelum percobaan ulang ke-1, 2, 3
ULANG = {429, 500, 502, 503, 504}
PENYANGGA_BARIS = 200             # baris kosong cadangan di bawah isi, untuk baris yang diketik pengguna
PENANDA = "bill-tracker: hanya-baca (ADR-0026)"  # deskripsi perlindungan yang dipasang skrip ini


def _rgb(hex_: str) -> dict:
    return {k: int(hex_[i:i + 2], 16) / 255 for k, i in (("red", 1), ("green", 3), ("blue", 5))}


WARNA = {nama: _rgb(h) for nama, h in {  # palet ADR-0032
    "indigo": "#1A1831", "olive": "#DECE9C", "hijau": "#20615B", "bordeaux": "#A21232",
    "hanya_baca": "#F5F0DC", "putih": "#FFFFFF"}.items()}
GAYA = {  # gaya per sel (`tata["sel"]`); "lewat" satu-satunya sel berlatar Bordeaux
    "minus": {"textFormat": {"foregroundColor": WARNA["bordeaux"]}},
    "aman": {"textFormat": {"foregroundColor": WARNA["hijau"]}},
    "mendekati": {"textFormat": {"foregroundColor": WARNA["bordeaux"]}},
    "lewat": {"backgroundColor": WARNA["bordeaux"],
              "textFormat": {"bold": True, "foregroundColor": WARNA["putih"]}},
}
POLA = {
    "tanggal": {"type": "DATE", "pattern": "d mmm yyyy"},
    "rupiah": {"type": "NUMBER", "pattern": '"Rp "#,##0;-"Rp "#,##0'},
    "persen": {"type": "PERCENT", "pattern": "0%"},
    "teks": {"type": "TEXT"},
}


class GagalGoogle(RuntimeError):
    """Sheets API menjawab bukan 2xx. Sinkron berhenti; snapshot tidak maju (spec #26)."""


def huruf_kolom(n: int) -> str:
    """Nomor kolom 1-based → huruf A1 (1 → A, 27 → AA)."""
    hasil = ""
    while n:
        n, sisa = divmod(n - 1, 26)
        hasil = chr(65 + sisa) + hasil
    return hasil


class KlienGoogle:
    def __init__(self, spreadsheet_id: str, sesi, kolom_waktu: dict | None = None, tidur=time.sleep):
        """`kolom_waktu`: {nama worksheet: {indeks kolom 0-based}}; serial waktu di sana dikembalikan
        sebagai teks HH:MM saat dibaca."""
        self.url = f"{API}/{spreadsheet_id}"
        self.sesi = sesi
        self.kolom_waktu = kolom_waktu or {}
        self.tidur = tidur
        self._sheets: dict | None = None

    # ── HTTP ──────────────────────────────────────────────────────────────
    def _panggil(self, metode: str, url: str, **kw):
        for percobaan in range(len(JEDA) + 1):
            jawab = self.sesi.request(metode, url, timeout=TIMEOUT, **kw)
            if jawab.status_code in ULANG and percobaan < len(JEDA):
                self.tidur(JEDA[percobaan])
                continue
            break
        if not 200 <= jawab.status_code < 300:
            raise GagalGoogle(f"{metode} {url.replace(self.url, '…')} → HTTP {jawab.status_code}: "
                              f"{(jawab.text or '')[:200]}")
        return jawab.json() if jawab.text else {}

    @staticmethod
    def _a1(nama: str, sel: str = "") -> str:
        return "'" + nama.replace("'", "''") + "'" + (f"!{sel}" if sel else "")

    def _rentang(self, nama: str, sel: str = "") -> str:
        return quote(self._a1(nama, sel), safe="")

    # ── Worksheet ─────────────────────────────────────────────────────────
    def _daftar(self, segar: bool = False) -> dict:
        if self._sheets is None or segar:
            isi = self._panggil("GET", self.url, params={
                "fields": "sheets(properties(sheetId,title,index,gridProperties),"
                          "protectedRanges(protectedRangeId,description),columnGroups(range))"})
            self._sheets = {}
            for s in isi.get("sheets", []):
                p = s["properties"]
                grid = p.get("gridProperties", {})
                self._sheets[p["title"]] = {
                    "id": p["sheetId"], "baris": grid.get("rowCount", 1000), "kolom": grid.get("columnCount", 26),
                    "index": p.get("index", 0),
                    "lindung": [r["protectedRangeId"] for r in s.get("protectedRanges", [])
                                if r.get("description") == PENANDA],
                    "grup": {(g["range"].get("startIndex", 0), g["range"].get("endIndex", 0))
                             for g in s.get("columnGroups", [])}}
        return self._sheets

    def _pastikan(self, nama: str) -> dict:
        daftar = self._daftar()
        if nama not in daftar:
            isi = self._panggil("POST", f"{self.url}:batchUpdate", json={
                "requests": [{"addSheet": {"properties": {"title": nama}}}]})
            daftar[nama] = {"id": isi["replies"][0]["addSheet"]["properties"]["sheetId"],
                            "baris": 1000, "kolom": 26, "index": len(daftar), "lindung": [], "grup": set()}
        return daftar[nama]

    def _lebarkan(self, info: dict, baris: int, kolom: int) -> None:
        """Grid worksheet baru hanya 1000×26 dan menulis di luarnya ditolak; lebarkan dulu."""
        if baris <= info["baris"] and kolom <= info["kolom"]:
            return
        n_baris = max(info["baris"], baris + PENYANGGA_BARIS)
        n_kolom = max(info["kolom"], kolom)
        self._panggil("POST", f"{self.url}:batchUpdate", json={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": info["id"],
                           "gridProperties": {"rowCount": n_baris, "columnCount": n_kolom}},
            "fields": "gridProperties.rowCount,gridProperties.columnCount"}}]})
        info["baris"], info["kolom"] = n_baris, n_kolom

    # ── Antarmuka sheets_sync ─────────────────────────────────────────────
    def baca(self, nama: str) -> list:
        if nama not in self._daftar(segar=True):
            return []
        isi = self._panggil("GET", f"{self.url}/values/{self._rentang(nama)}",
                            params={"valueRenderOption": "UNFORMATTED_VALUE"})
        return self._ke_teks(nama, isi.get("values", []))

    def _ke_teks(self, nama: str, grid: list) -> list:
        """Serial waktu di kolom yang terdaftar (selain header) → "HH:MM"."""
        waktu = self.kolom_waktu.get(nama, set())
        hasil = []
        for i, baris in enumerate(grid):
            baris = list(baris)
            for k, sel in enumerate(baris):
                if i == 0 or isinstance(sel, bool) or not isinstance(sel, (int, float)):
                    continue
                if k in waktu:
                    menit = round((sel % 1) * 24 * 60)
                    baris[k] = f"{menit // 60 % 24:02d}:{menit % 60:02d}"
            hasil.append(baris)
        return hasil

    def tulis(self, nama: str, grid: list, tata: dict | None = None) -> None:
        self._daftar(segar=True)  # pengguna bisa menghapus/mengganti nama worksheet di antara dua sinkron
        info = self._pastikan(nama)
        if not grid:
            self._panggil("POST", f"{self.url}/values/{self._rentang(nama)}:clear", json={})
            return
        lebar = max(len(b) for b in grid)
        grid = [list(b) + [""] * (lebar - len(b)) for b in grid]  # baris pendek menimpa sel lama di kanannya
        self._lebarkan(info, len(grid), lebar)
        if tata:
            self._panggil("POST", f"{self.url}:batchUpdate", json={"requests": self._tata(info, tata, lebar)})
            if tata.get("locale"):
                self._pastikan_locale(tata["locale"])
        self._panggil("PUT", f"{self.url}/values/{self._rentang(nama, 'A1')}",
                      params={"valueInputOption": "RAW"},
                      json={"majorDimension": "ROWS", "values": grid})
        # Sisa isi lama dibersihkan SESUDAH isi baru tertulis: PUT yang gagal tidak mengosongkan Sheet.
        sisa = []
        if len(grid) < info["baris"]:
            sisa.append(self._a1(nama, f"A{len(grid) + 1}:{huruf_kolom(info['kolom'])}{info['baris']}"))
        if lebar < info["kolom"]:
            sisa.append(self._a1(nama, f"{huruf_kolom(lebar + 1)}1:{huruf_kolom(info['kolom'])}{len(grid)}"))
        if sisa:
            self._panggil("POST", f"{self.url}/values:batchClear", json={"ranges": sisa})

    def _tata(self, info: dict, tata: dict, lebar: int) -> list:
        sid, h = info["id"], tata.get("baris_header", 0)

        def kolom(c, baris_mulai=None):
            r = {"sheetId": sid, "startColumnIndex": c, "endColumnIndex": c + 1}
            return {**r, "startRowIndex": baris_mulai} if baris_mulai is not None else r

        def sel(rentang, format_, medan):
            return {"repeatCell": {"range": rentang, "cell": {"userEnteredFormat": format_}, "fields": medan}}

        req = [{"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {
                "frozenRowCount": h + 1, "frozenColumnCount": tata.get("beku_kolom", 0)}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}}]
        for c, jenis in sorted(tata.get("format", {}).items()):
            req.append(sel(kolom(c, h + 1), {"numberFormat": POLA[jenis]}, "userEnteredFormat.numberFormat"))
        req += [{"deleteProtectedRange": {"protectedRangeId": i}} for i in info["lindung"]]
        hanya = tata.get("hanya_baca") or []
        rentang = [{"sheetId": sid}] if hanya == "semua" else [kolom(c) for c in hanya]
        for r in rentang:
            # textFormat ikut di mask tanpa nilai → warna teks/tebal lama (gaya per sel sinkron lalu) dihapus
            req.append(sel(r, {"backgroundColor": WARNA["hanya_baca"]},
                           "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat"))
            req.append({"addProtectedRange": {"protectedRange": {
                "range": r, "description": PENANDA, "warningOnly": True}}})
        for c, warna in sorted(tata.get("warna_teks", {}).items()):
            req.append(sel(kolom(c, h + 1), {"textFormat": {"foregroundColor": WARNA[warna]}},
                           "userEnteredFormat.textFormat.foregroundColor"))
        for b, c, gaya in tata.get("sel", []):
            req.append(sel({"sheetId": sid, "startRowIndex": b, "endRowIndex": b + 1,
                            "startColumnIndex": c, "endColumnIndex": c + 1}, GAYA[gaya],
                           ",".join(f"userEnteredFormat.{k}" for k in GAYA[gaya])))
        req.append(sel({"sheetId": sid, "startRowIndex": h, "endRowIndex": h + 1,  # sesudah latar hanya-baca
                        "startColumnIndex": 0, "endColumnIndex": lebar},
                       {"backgroundColor": WARNA["indigo"],
                        "textFormat": {"bold": True, "foregroundColor": WARNA["olive"]}},
                       "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat"))
        for c, teks in sorted(tata.get("catatan", {}).items()):
            req.append({"updateCells": {"range": {**kolom(c, h), "endRowIndex": h + 1},
                                        "rows": [{"values": [{"note": teks}]}], "fields": "note"}})
        for c, opsi in sorted(tata.get("pilihan", {}).items()):
            if opsi:
                req.append({"setDataValidation": {"range": kolom(c, h + 1), "rule": {
                    "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in opsi]},
                    "strict": False, "showCustomUi": True}}})
        for a, b in tata.get("grup", []):
            if (a, b) in info["grup"]:
                continue
            r = {"sheetId": sid, "dimension": "COLUMNS", "startIndex": a, "endIndex": b}
            req += [{"addDimensionGroup": {"range": r}},
                    {"updateDimensionGroup": {"dimensionGroup": {"range": r, "depth": 1, "collapsed": True},
                                              "fields": "collapsed"}}]
        return req

    def _pastikan_locale(self, locale: str) -> None:
        """Locale menentukan cara Sheets membaca tanggal yang diketik (5/9/2026 = 5 September)."""
        isi = self._panggil("GET", self.url, params={"fields": "properties.locale"})
        if isi.get("properties", {}).get("locale") != locale:
            self._panggil("POST", f"{self.url}:batchUpdate", json={"requests": [{"updateSpreadsheetProperties": {
                "properties": {"locale": locale}, "fields": "locale"}}]})

    def hapus(self, nama: str) -> None:
        daftar = self._daftar(segar=True)
        if nama in daftar:
            self._panggil("POST", f"{self.url}:batchUpdate", json={
                "requests": [{"deleteSheet": {"sheetId": daftar.pop(nama)["id"]}}]})

    def urutkan(self, nama: list) -> None:
        """Tab yang disebut ditaruh paling depan sesuai urutan; tab lain (mis. buatan pengguna) di belakang."""
        daftar = self._daftar(segar=True)
        ada = [n for n in nama if n in daftar]
        if any(daftar[n]["index"] != i for i, n in enumerate(ada)):
            # Memindah satu tab menggeser tab lain, jadi semuanya dikirim berurutan dari depan.
            req = [{"updateSheetProperties": {"properties": {"sheetId": daftar[n]["id"], "index": i},
                                              "fields": "index"}} for i, n in enumerate(ada)]
            self._panggil("POST", f"{self.url}:batchUpdate", json={"requests": req})


def dari_konfigurasi(config: dict, akar: Path, kolom_waktu: dict | None = None) -> KlienGoogle:
    """Klien sungguhan dari `data/sheets.json`: {"spreadsheet_id": ..., "kunci_akun_layanan": ...}."""
    if not re.fullmatch(r"[\w-]{20,}", str(config.get("spreadsheet_id") or "")):
        raise RuntimeError("spreadsheet_id di data/sheets.json kosong atau belum diisi dengan ID "
                           "sebenarnya (bagian <ID> dari docs.google.com/spreadsheets/d/<ID>/edit)")
    if not config.get("kunci_akun_layanan"):
        raise RuntimeError("kunci_akun_layanan di data/sheets.json belum diisi (jalur berkas kunci "
                           "akun layanan Google)")
    try:
        with warnings.catch_warnings():  # Python 3.9 sudah EOL: pustaka Google/urllib3 berisik di log cron
            warnings.simplefilter("ignore")
            from google.auth.transport.requests import AuthorizedSession
            from google.oauth2 import service_account
    except ImportError as e:
        raise RuntimeError(f"google-auth dan requests belum terpasang untuk interpreter ini ({e}). "
                           "Jalankan: /usr/bin/python3 -m pip install --user google-auth requests") from e
    kunci = Path(config["kunci_akun_layanan"])
    kunci = kunci if kunci.is_absolute() else akar / kunci
    info = json.loads(kunci.read_text(encoding="utf-8"))
    kredensial = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
    return KlienGoogle(config["spreadsheet_id"], AuthorizedSession(kredensial), kolom_waktu)
