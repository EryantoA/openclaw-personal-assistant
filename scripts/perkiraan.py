"""Perkiraan — Transaksi yang diharapkan berulang tiap bulan (CONTEXT.md → Perkiraan, ADR-0006).

Berkasnya data/perkiraan.json. Baris Buku Kas dan Pengaturan diberikan pemanggil, jadi cek
malam, Laporan Bulanan, dan Laporan Mingguan memakai satu aturan pencocokan yang sama.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import calendar
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402

PERKIRAAN_JSON = Path(__file__).resolve().parent.parent / "data" / "perkiraan.json"


def muat(path: Path | None = None) -> list[dict]:
    """Perkiraan yang aktif. Berkas tidak ada atau rusak = daftar kosong."""
    path = path or PERKIRAAN_JSON
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f).get("perkiraan", [])
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(entries, list):
        return []
    return [e for e in entries if e.get("aktif", True)]


def absen(daftar: list[dict], rows: list[dict], tahun: int, bulan: int, today: date | None = None,
          pengaturan: dict | None = None) -> list[dict]:
    """Perkiraan di `daftar` yang tidak muncul di `rows` pada bulan `tahun`-`bulan`.

    `today` None berarti bulannya sudah tutup: semua Perkiraan diperiksa. Kalau diisi, yang
    tanggalnya belum lewat toleransi dilewati — belum waktunya dipertanyakan.

    Pencocokan sengaja longgar (kategori + arah + nominal dalam toleransi): nominal ikut kurs
    (Anthropic 366.588 vs 366.751) dan pemasukan kadang tercatat sebagai satu baris gabungan.
    Salah tebak di sini cuma berujung pertanyaan, bukan klaim utang.
    """
    if not daftar:
        return []
    pengaturan = pengaturan or {}
    toleransi_hari = int(pengaturan.get("perkiraan_toleransi_hari", 3))
    toleransi_persen = float(pengaturan.get("perkiraan_toleransi_persen", 10))

    kunci = f"{tahun:04d}-{bulan:02d}"
    rows = [r for r in rows if (t := buku_kas.tanggal(r)) is not None and t.strftime("%Y-%m") == kunci]

    hasil = []
    for e in daftar:
        try:
            hari = int(e.get("tanggal_biasanya", 0))
            nominal = float(e.get("nominal", 0))
        except (ValueError, TypeError):
            continue
        if not 1 <= hari <= 31 or nominal <= 0:
            continue

        # Bulan pendek: tanggal 31 jatuh di hari terakhir bulan itu.
        tanggal_harap = date(tahun, bulan, min(hari, calendar.monthrange(tahun, bulan)[1]))
        if today is not None and (today - tanggal_harap).days <= toleransi_hari:
            continue  # belum waktunya dipertanyakan

        arah = (e.get("arah") or "keluar").strip().lower()
        tipe_dicari = "pemasukan" if arah == "masuk" else "pengeluaran"
        kategori = (e.get("kategori") or "").strip().lower()
        # Toleransi bisa diperketat per entri. Perlu ketika dua perkiraan berbagi kategori
        # dengan nominal berdekatan — dua gaji di `salary` cuma beda 1,4%, dan toleransi
        # longgar membuat gaji yang satu menutupi absennya gaji yang lain.
        try:
            persen = float(e.get("toleransi_persen", toleransi_persen))
        except (ValueError, TypeError):
            persen = toleransi_persen
        batas = nominal * persen / 100

        if not any(buku_kas.arah(r) == tipe_dicari
                   and (r.get("kategori") or "").strip().lower() == kategori
                   and abs(buku_kas.jumlah(r) - nominal) <= batas
                   for r in rows):
            hasil.append(e)
    return hasil
