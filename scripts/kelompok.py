"""Kelompok Kategori (ADR-0030): tingkat di atas Kategori, hanya untuk tampilan dan ringkasan.

`budget.json` → `kelompok_kategori`: {nama Kelompok: [slug, ...]}, urutannya urutan tampil. Kategori
yang tidak ada di Kelompok mana pun (mis. `other`, `reconciliation`) masuk "Lainnya". Data tetap slug
(ADR-0002); Budget dan Batas Kategori tidak memakai Kelompok.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

LAINNYA = "Lainnya"


def urutan(atur: dict) -> list:
    isi = atur.get("kelompok_kategori")
    return list(isi) if isinstance(isi, dict) else []


def peta(atur: dict) -> dict:
    """slug → nama Kelompok; slug yang tercantum di dua Kelompok ikut yang pertama."""
    hasil = {}
    isi = atur.get("kelompok_kategori")
    for nama, slug in (isi.items() if isinstance(isi, dict) else []):
        for s in slug or []:
            hasil.setdefault(s, nama)
    return hasil


def komposisi(per_kategori: dict, atur: dict) -> list:
    """[(Kelompok, jumlah)] berurutan seperti pengaturan, "Lainnya" terakhir; yang nol dilewati."""
    p = peta(atur)
    total = {}
    for slug, jumlah in per_kategori.items():
        k = p.get(slug, LAINNYA)
        total[k] = total.get(k, 0) + jumlah
    return [(k, total[k]) for k in urutan(atur) + [LAINNYA] if total.get(k)]


def baris_laporan(per_kategori: dict, atur: dict):
    """Satu baris Laporan Bulanan: porsi tiap Kelompok dari seluruh Pengeluaran; None bila tak ada."""
    if not urutan(atur):
        return None
    isi = komposisi(per_kategori, atur)
    semua = sum(j for _, j in isi)
    if not semua:
        return None
    return "🧭 " + " · ".join(f"{k} {j / semua * 100:.0f}%" for k, j in isi)
