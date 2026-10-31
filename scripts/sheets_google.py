"""Klien Google Sheets untuk sheets_sync — adaptor tipis, tanpa logika bisnis (spec #20, ADR-0021).

Memenuhi antarmuka dua metode yang diminta sheets_sync:

    klien.baca(nama_worksheet) -> list[list]   # grid; worksheet belum ada = []
    klien.tulis(nama_worksheet, grid)          # mengganti seluruh isi; membuat worksheet bila belum ada

Bicara dengan Sheets API v4 lewat sesi HTTP yang disuntikkan (`sesi.request(metode, url, params=,
json=)` → objek dengan `status_code`, `json()`, `text`), jadi aturannya bisa diuji tanpa Google.
Sesi sungguhan dibuat `dari_konfigurasi`: akun layanan Google (kunci di luar git) lewat
`google-auth` + `requests`, yang harus terpasang untuk interpreter yang dipakai cron:

    /usr/bin/python3 -m pip install --user google-auth requests

Tulis memakai valueInputOption=RAW dan kolom teks diformat TEXT, supaya tanggal "2026-09-05" tidak
diubah Sheets menjadi tanggal; baca memakai UNFORMATTED_VALUE, jadi jumlah kembali sebagai angka.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class GagalGoogle(RuntimeError):
    """Sheets API menjawab bukan 2xx. Sinkron berhenti; snapshot tidak maju (spec #26)."""


class KlienGoogle:
    def __init__(self, spreadsheet_id: str, sesi, kolom_angka: dict | None = None):
        """`kolom_angka`: {nama worksheet: {indeks kolom 0-based yang berisi angka}}. Worksheet yang
        terdaftar di sini diformat per kolom (angka vs teks); yang lain dibiarkan apa adanya."""
        self.url = f"{API}/{spreadsheet_id}"
        self.sesi = sesi
        self.kolom_angka = kolom_angka or {}
        self._id_sheet: dict | None = None

    # ── HTTP ──────────────────────────────────────────────────────────────
    def _panggil(self, metode: str, url: str, **kw):
        jawab = self.sesi.request(metode, url, **kw)
        if not 200 <= jawab.status_code < 300:
            raise GagalGoogle(f"{metode} {url.replace(self.url, '…')} → HTTP {jawab.status_code}: "
                              f"{(jawab.text or '')[:200]}")
        return jawab.json() if jawab.text else {}

    def _rentang(self, nama: str, sel: str = "") -> str:
        return quote(f"'{nama}'" + (f"!{sel}" if sel else ""), safe="")

    # ── Worksheet ─────────────────────────────────────────────────────────
    def _daftar(self, segar: bool = False) -> dict:
        if self._id_sheet is None or segar:
            isi = self._panggil("GET", self.url, params={"fields": "sheets.properties(sheetId,title)"})
            self._id_sheet = {s["properties"]["title"]: s["properties"]["sheetId"]
                              for s in isi.get("sheets", [])}
        return self._id_sheet

    def _pastikan(self, nama: str) -> int:
        daftar = self._daftar()
        if nama not in daftar:
            isi = self._panggil("POST", f"{self.url}:batchUpdate", json={
                "requests": [{"addSheet": {"properties": {"title": nama}}}]})
            daftar[nama] = isi["replies"][0]["addSheet"]["properties"]["sheetId"]
        return daftar[nama]

    # ── Antarmuka sheets_sync ─────────────────────────────────────────────
    def baca(self, nama: str) -> list:
        if nama not in self._daftar(segar=True):
            return []
        isi = self._panggil("GET", f"{self.url}/values/{self._rentang(nama)}",
                            params={"valueRenderOption": "UNFORMATTED_VALUE"})
        return isi.get("values", [])

    def tulis(self, nama: str, grid: list) -> None:
        id_sheet = self._pastikan(nama)
        self._panggil("POST", f"{self.url}/values/{self._rentang(nama)}:clear", json={})
        if nama in self.kolom_angka:
            self._format(id_sheet, self.kolom_angka[nama], lebar=max((len(b) for b in grid), default=0))
        if grid:
            self._panggil("PUT", f"{self.url}/values/{self._rentang(nama, 'A1')}",
                          params={"valueInputOption": "RAW"},
                          json={"majorDimension": "ROWS", "values": grid})

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


def dari_konfigurasi(config: dict, akar: Path, kolom_angka: dict | None = None) -> KlienGoogle:
    """Klien sungguhan dari `data/sheets.json`: {"spreadsheet_id": ..., "kunci_akun_layanan": ...}."""
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as e:
        raise RuntimeError("google-auth dan requests belum terpasang untuk interpreter ini. Jalankan: "
                           "/usr/bin/python3 -m pip install --user google-auth requests") from e
    kunci = Path(config["kunci_akun_layanan"])
    kunci = kunci if kunci.is_absolute() else akar / kunci
    info = json.loads(kunci.read_text(encoding="utf-8"))
    kredensial = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
    return KlienGoogle(config["spreadsheet_id"], AuthorizedSession(kredensial), kolom_angka)
