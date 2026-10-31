"""Klien Google Sheets untuk sheets_sync — adaptor tipis, tanpa logika bisnis (spec #20, ADR-0021).

Memenuhi antarmuka dua metode yang diminta sheets_sync:

    klien.baca(nama_worksheet) -> list[list]   # grid; worksheet belum ada = []
    klien.tulis(nama_worksheet, grid)          # mengganti seluruh isi; membuat worksheet bila belum ada

Bicara dengan Sheets API v4 lewat sesi HTTP yang disuntikkan (`sesi.request(metode, url, params=,
json=, timeout=)` → objek dengan `status_code`, `json()`, `text`), jadi aturannya bisa diuji tanpa
Google. Sesi sungguhan dibuat `dari_konfigurasi`: akun layanan Google (kunci di luar git) lewat
`google-auth` + `requests`, yang harus terpasang untuk interpreter yang dipakai cron:

    /usr/bin/python3 -m pip install --user google-auth requests

Tulis memakai valueInputOption=RAW dan kolom teks diformat TEXT, supaya tanggal "2026-09-05" tidak
diubah Sheets menjadi tanggal; baca memakai UNFORMATTED_VALUE (jumlah kembali sebagai angka) dan
mengembalikan serial tanggal/waktu yang tetap lolos (mis. hasil tempel) sebagai teks ISO / HH:MM.
Tulis melebarkan grid worksheet bila perlu (worksheet baru hanya 1000 baris × 26 kolom; menulis di
luarnya ditolak Google), menimpa isi dulu baru membersihkan sisa lama (PUT yang gagal tidak
meninggalkan Sheet kosong), dan mengulang 429/5xx dengan jeda naik.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TIMEOUT = 60                      # detik per panggilan; tanpa ini jaringan macet menahan sinkron
JEDA = (1, 2, 4)                  # detik sebelum percobaan ulang ke-1, 2, 3
ULANG = {429, 500, 502, 503, 504}
PENYANGGA_BARIS = 200             # baris kosong cadangan di bawah isi, untuk baris yang diketik pengguna
EPOCH_SERIAL = date(1899, 12, 30)  # serial tanggal Google Sheets


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
    def __init__(self, spreadsheet_id: str, sesi, kolom_angka: dict | None = None,
                 kolom_tanggal: dict | None = None, kolom_waktu: dict | None = None, tidur=time.sleep):
        """`kolom_angka` / `kolom_tanggal` / `kolom_waktu`: {nama worksheet: {indeks kolom 0-based}}.
        Worksheet yang terdaftar di `kolom_angka` diformat per kolom (angka vs teks); yang lain
        dibiarkan apa adanya. Serial di kolom tanggal/waktu dikembalikan sebagai teks saat dibaca."""
        self.url = f"{API}/{spreadsheet_id}"
        self.sesi = sesi
        self.kolom_angka = kolom_angka or {}
        self.kolom_tanggal = kolom_tanggal or {}
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
                "fields": "sheets.properties(sheetId,title,gridProperties)"})
            self._sheets = {}
            for s in isi.get("sheets", []):
                p = s["properties"]
                grid = p.get("gridProperties", {})
                self._sheets[p["title"]] = {"id": p["sheetId"], "baris": grid.get("rowCount", 1000),
                                            "kolom": grid.get("columnCount", 26)}
        return self._sheets

    def _pastikan(self, nama: str) -> dict:
        daftar = self._daftar()
        if nama not in daftar:
            isi = self._panggil("POST", f"{self.url}:batchUpdate", json={
                "requests": [{"addSheet": {"properties": {"title": nama}}}]})
            daftar[nama] = {"id": isi["replies"][0]["addSheet"]["properties"]["sheetId"],
                            "baris": 1000, "kolom": 26}
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
        """Serial tanggal/waktu di kolom yang terdaftar (selain header) → "YYYY-MM-DD" / "HH:MM"."""
        tanggal, waktu = self.kolom_tanggal.get(nama, set()), self.kolom_waktu.get(nama, set())
        hasil = []
        for i, baris in enumerate(grid):
            baris = list(baris)
            for k, sel in enumerate(baris):
                if i == 0 or isinstance(sel, bool) or not isinstance(sel, (int, float)):
                    continue
                if k in tanggal:
                    baris[k] = (EPOCH_SERIAL + timedelta(days=int(sel))).isoformat()
                elif k in waktu:
                    menit = round((sel % 1) * 24 * 60)
                    baris[k] = f"{menit // 60 % 24:02d}:{menit % 60:02d}"
            hasil.append(baris)
        return hasil

    def tulis(self, nama: str, grid: list) -> None:
        self._daftar(segar=True)  # pengguna bisa menghapus/mengganti nama worksheet di antara dua sinkron
        info = self._pastikan(nama)
        if not grid:
            self._panggil("POST", f"{self.url}/values/{self._rentang(nama)}:clear", json={})
            return
        lebar = max(len(b) for b in grid)
        grid = [list(b) + [""] * (lebar - len(b)) for b in grid]  # baris pendek menimpa sel lama di kanannya
        self._lebarkan(info, len(grid), lebar)
        if nama in self.kolom_angka:
            self._format(info["id"], self.kolom_angka[nama], lebar)
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

    def _format(self, id_sheet: int, kolom_angka: set, lebar: int) -> None:
        """Kolom angka berformat NUMBER, sisanya TEXT (seluruh kolom, termasuk baris yang baru
        diketik pengguna) — sebelum diisi, karena format teks hanya berlaku untuk isian berikutnya."""
        permintaan = []
        for k in range(lebar):
            jenis = "NUMBER" if k in kolom_angka else "TEXT"
            permintaan.append({"repeatCell": {
                "range": {"sheetId": id_sheet, "startColumnIndex": k, "endColumnIndex": k + 1},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": jenis}}},
                "fields": "userEnteredFormat.numberFormat"}})
        if permintaan:
            self._panggil("POST", f"{self.url}:batchUpdate", json={"requests": permintaan})


def dari_konfigurasi(config: dict, akar: Path, kolom_angka: dict | None = None,
                     kolom_tanggal: dict | None = None, kolom_waktu: dict | None = None) -> KlienGoogle:
    """Klien sungguhan dari `data/sheets.json`: {"spreadsheet_id": ..., "kunci_akun_layanan": ...}."""
    if not re.fullmatch(r"[\w-]{20,}", str(config.get("spreadsheet_id") or "")):
        raise RuntimeError("spreadsheet_id di data/sheets.json kosong atau belum diisi dengan ID "
                           "sebenarnya (bagian <ID> dari docs.google.com/spreadsheets/d/<ID>/edit)")
    if not config.get("kunci_akun_layanan"):
        raise RuntimeError("kunci_akun_layanan di data/sheets.json belum diisi (jalur berkas kunci "
                           "akun layanan Google)")
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as e:
        raise RuntimeError(f"google-auth dan requests belum terpasang untuk interpreter ini ({e}). "
                           "Jalankan: /usr/bin/python3 -m pip install --user google-auth requests") from e
    kunci = Path(config["kunci_akun_layanan"])
    kunci = kunci if kunci.is_absolute() else akar / kunci
    info = json.loads(kunci.read_text(encoding="utf-8"))
    kredensial = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
    return KlienGoogle(config["spreadsheet_id"], AuthorizedSession(kredensial), kolom_angka,
                       kolom_tanggal, kolom_waktu)
