"""Periode — Pekan dan bulan, satu definisi untuk semua laporan (CONTEXT.md → Pekan, ADR-0013).

Pekan = Senin 00:00 – Minggu 23:59 WIB, dan baru dilaporkan setelah tutup.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta


def awal_pekan(d: date) -> date:
    return d - timedelta(days=d.weekday())


def pilih_pekan(hari_ini: date, pekan: date | None = None, berjalan: bool = False) -> tuple:
    """(mulai, akhir, tutup) untuk satu permintaan laporan.

    Bawaan: Pekan tutup terakhir (yang memuat hari_ini − 7 hari). `pekan`: Pekan yang memuat
    tanggal itu — ValueError kalau Minggu-nya belum lewat. `berjalan`: Senin Pekan ini s.d. hari ini.
    """
    if berjalan:
        return awal_pekan(hari_ini), hari_ini, False
    mulai = awal_pekan(pekan or hari_ini - timedelta(days=7))
    akhir = mulai + timedelta(days=6)
    if akhir >= hari_ini:
        raise ValueError(f"Pekan {mulai}–{akhir} belum tutup; pakai --berjalan")
    return mulai, akhir, True


def akhir_bulan(bulan: str) -> date:
    """Hari terakhir bulan 'YYYY-MM'."""
    t, b = map(int, bulan.split("-"))
    return date(t, b, calendar.monthrange(t, b)[1])


def bulan_sebelum(bulan: str) -> str:
    t, b = map(int, bulan.split("-"))
    return f"{t - 1}-12" if b == 1 else f"{t}-{b - 1:02d}"


def rentang_bulan(bulan: str) -> tuple:
    """(tanggal 1, hari terakhir) bulan 'YYYY-MM'; ValueError kalau bulannya tidak sah."""
    t = datetime.strptime(bulan, "%Y-%m")
    return date(t.year, t.month, 1), akhir_bulan(f"{t.year:04d}-{t.month:02d}")


def bulan_dalam(mulai: date, akhir: date) -> list:
    """(tahun, bulan) yang disentuh rentang ini, urut."""
    hasil, d = [], mulai
    while d <= akhir:
        if (d.year, d.month) not in hasil:
            hasil.append((d.year, d.month))
        d += timedelta(days=1)
    return hasil
