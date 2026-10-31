"""Buku Kas — membaca & menghitung. Mengubah/menghapus ada di buku.py, menambah di catat.py.

Satu tempat untuk aturan CONTEXT.md yang dipakai semua laporan:
  - jumlah dibaca seperti saat ditulis (resi.norm_total), hasilnya int rupiah;
  - Arah hanya pemasukan / pengeluaran / transfer; tipe kosong = pengeluaran (data lama);
  - Transfer tidak ikut Saldo maupun Arus Kas Bulan (ADR-0010);
  - Saldo Awal (`opening_balance`) ikut Saldo, bukan Pemasukan (ADR-0008);
  - baris tanpa tanggal ISO yang sah atau dengan tipe tak dikenal tidak dihitung,
    tapi dilaporkan lewat tak_terhitung() — tidak pernah hilang diam-diam.

Sengaja tidak dipakai scripts/periksa-kesehatan.py (ADR-0011).
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import periode  # noqa: E402
import resi  # noqa: E402

BILLS = Path(__file__).resolve().parent.parent / "data" / "bills.csv"
KATEGORI_SALDO_AWAL = "opening_balance"
ARAH = ("pemasukan", "pengeluaran", "transfer")
KOLOM_WAJIB = {"tanggal", "tipe", "kategori", "jumlah"}


def muat(path: Path | None = None) -> list[dict]:
    """Semua baris Buku Kas. File tidak ada = daftar kosong; header rusak = ValueError."""
    path = path or BILLS
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        kurang = KOLOM_WAJIB - set(reader.fieldnames or [])
        if kurang:
            raise ValueError(f"{path}: kolom wajib tidak ada: {', '.join(sorted(kurang))}")
        return list(reader)


def jumlah(tx: dict) -> int:
    return int(resi.norm_total(tx.get("jumlah")) or 0)


def arah(tx: dict) -> str | None:
    """'pemasukan' / 'pengeluaran' / 'transfer', atau None bila tipe tidak dikenal."""
    t = (tx.get("tipe") or "pengeluaran").strip().lower()
    return t if t in ARAH else None


def tanggal(tx: dict) -> date | None:
    try:
        return date.fromisoformat((tx.get("tanggal") or "").strip())
    except ValueError:
        return None


def saldo_awal(tx: dict) -> bool:
    return (tx.get("kategori") or "").strip().lower() == KATEGORI_SALDO_AWAL


def tak_terhitung(rows: list[dict]) -> list[tuple[dict, str]]:
    """Baris yang tidak ikut Saldo maupun Arus Kas Bulan, beserta alasannya."""
    hasil = []
    for r in rows:
        if tanggal(r) is None:
            hasil.append((r, f"tanggal tidak sah: {r.get('tanggal')!r}"))
        elif arah(r) is None:
            hasil.append((r, f"tipe tidak dikenal: {r.get('tipe')!r}"))
    return hasil


def _terhitung(rows: list[dict]):
    """(tanggal, arah, tx) untuk baris yang ikut hitungan; Transfer dilewati."""
    for r in rows:
        tgl, a = tanggal(r), arah(r)
        if tgl is not None and a in ("pemasukan", "pengeluaran"):
            yield tgl, a, r


def saldo(rows: list[dict], per: date) -> int:
    """Saldo per akhir hari `per` (tanggal itu ikut dihitung)."""
    s = 0
    for tgl, a, r in _terhitung(rows):
        if tgl > per:
            continue
        s += jumlah(r) if saldo_awal(r) or a == "pemasukan" else -jumlah(r)
    return s


def ringkas(rows: list[dict], mulai: date, akhir: date) -> dict:
    """Satu aturan hitung untuk rentang tanggal `mulai`..`akhir` (inklusif): hari, Pekan, atau bulan.

    {pemasukan, pengeluaran, saldo_awal}: total uang. Transfer dilewati; Saldo Awal terpisah dari
    Pemasukan (ADR-0008, ADR-0010).
    {transaksi_pemasukan, transaksi_pengeluaran}: jumlah **Transaksi** = No Resi unik di antara
    baris yang jatuh di rentang itu, bukan jumlah baris (ADR-0023). Baris tanpa No Resi dihitung
    satu Transaksi per baris. Transfer dan Saldo Awal tidak dihitung.
    per_kategori: total Pengeluaran per Kategori (slug huruf kecil; kosong jadi `other`).
    """
    h = {"pemasukan": 0, "pengeluaran": 0, "saldo_awal": 0,
         "transaksi_pemasukan": 0, "transaksi_pengeluaran": 0, "per_kategori": {}}
    resi = {"pemasukan": set(), "pengeluaran": set()}
    for i, r in enumerate(rows):
        tgl, a = tanggal(r), arah(r)
        if tgl is None or a not in resi or not mulai <= tgl <= akhir:
            continue
        if saldo_awal(r):
            h["saldo_awal"] += jumlah(r)
            continue
        h[a] += jumlah(r)
        resi[a].add((r.get("no_resi") or "").strip() or f"baris-{i}")
        if a == "pengeluaran":
            k = (r.get("kategori") or "").strip().lower() or "other"
            h["per_kategori"][k] = h["per_kategori"].get(k, 0) + jumlah(r)
    h["transaksi_pemasukan"] = len(resi["pemasukan"])
    h["transaksi_pengeluaran"] = len(resi["pengeluaran"])
    return h


def arus_kas_bulan(rows: list[dict], bulan: str) -> dict:
    """{pemasukan, pengeluaran, saldo_awal} untuk bulan 'YYYY-MM' — ringkas() satu bulan penuh."""
    h = ringkas(rows, *periode.rentang_bulan(bulan))
    return {k: h[k] for k in ("pemasukan", "pengeluaran", "saldo_awal")}
