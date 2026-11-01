"""Tampilan — format yang dipakai bersama oleh pesan dan laporan (rupiah, nama bulan).

Mulai dari module Budget; skrip laporan lama masih membawa salinannya sendiri (lihat review
arsitektur: satu module presentasi laporan) dan boleh pindah ke sini bertahap.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
              "Agustus", "September", "Oktober", "November", "Desember"]


def rp(x) -> str:
    """Rp dengan titik ribuan; minus di depan: -Rp 432.771."""
    return ("-" if x < 0 else "") + f"Rp {abs(x):,.0f}".replace(",", ".")


def nama_bulan(bulan: str) -> str:
    """'2026-10' -> 'Oktober 2026'."""
    t, b = map(int, bulan.split("-"))
    return f"{NAMA_BULAN[b - 1]} {t}"
