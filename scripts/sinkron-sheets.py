#!/usr/bin/env python3
"""Sinkron dua arah Buku Kas ↔ Google Sheets (spec #20, ADR-0021).

    python3 scripts/sinkron-sheets.py --uji            # lapor apa yang akan terjadi, tidak menulis
    python3 scripts/sinkron-sheets.py --inisialisasi   # sekali: isi Sheet dari bills.csv (CSV menang)
    python3 scripts/sinkron-sheets.py                  # sinkron biasa (cron)

Pertama kali: salin data/sheets.json.example ke data/sheets.json dan isi; jalankan --uji, lalu
--inisialisasi. bills.csv tetap satu-satunya Buku Kas: edit di Sheets masuk lewat jalan tulis yang
sama dengan bot, dan menghapus Transaksi tetap hanya lewat bot.

Kode keluar: 0 selesai (termasuk bila ada baris yang ditolak — itu ada di laporan); 1 ditolak
(mis. Sheet berisi data tanpa snapshot, atau snapshot rusak); 2 gagal (konfigurasi, klien, atau
jaringan) — cron harus tercatat error supaya penjaga kesehatan menangkapnya.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resi  # noqa: E402
import sheets_google  # noqa: E402
import sheets_sync  # noqa: E402

AKAR = Path(__file__).resolve().parent.parent
CONFIG = AKAR / "data" / "sheets.json"
SNAPSHOT = AKAR / "data" / "sheets-snapshot.json"


def _samar(teks: str, config: dict) -> str:
    """ID spreadsheet ikut di URL pesan error jaringan; jangan sampai masuk log cron."""
    id_ = str(config.get("spreadsheet_id") or "")
    return teks.replace(id_, "<id>") if id_ else teks


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Sinkron Buku Kas ↔ Google Sheets")
    p.add_argument("--uji", action="store_true", help="lapor saja, tidak menulis apa pun")
    p.add_argument("--inisialisasi", action="store_true",
                   help="isi/timpa Sheet dari bills.csv (CSV menang); dipakai sekali")
    a = p.parse_args(argv)

    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"GAGAL membaca {CONFIG}: {e}\nSalin data/sheets.json.example ke data/sheets.json lalu isi.",
              file=sys.stderr)
        return 2
    K, buku = sheets_sync.KOLOM, sheets_sync.SHEET_BUKU
    try:
        klien = sheets_google.dari_konfigurasi(
            config, AKAR, {buku: {K.index("jumlah")}}, {buku: {K.index("tanggal")}}, {buku: {K.index("waktu")}})
    except (RuntimeError, KeyError, OSError, ValueError) as e:
        print(f"GAGAL menyiapkan klien Google: {_samar(str(e), config)}", file=sys.stderr)
        return 2

    try:
        laporan = sheets_sync.sinkron(resi.BILLS_CSV, klien, SNAPSHOT, uji=a.uji, inisialisasi=a.inisialisasi)
    except sheets_sync.SinkronDitolak as e:
        print(f"DITOLAK: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001  jaringan, API, disk: apa pun yang menggagalkan sinkron
        print(f"GAGAL: {type(e).__name__}: {_samar(str(e), config)}", file=sys.stderr)
        return 2
    print(sheets_sync.teks_laporan(laporan, uji=a.uji))
    return 0


if __name__ == "__main__":
    sys.exit(main())
