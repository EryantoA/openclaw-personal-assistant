"""Kewajiban — tagihan pascabayar yang sudah datang tapi belum dibayar (CONTEXT.md, ADR-0006).

Berkasnya data/kewajiban.json. Status tidak pernah disimpan: sebuah Kewajiban lunas kalau
`lunas_resi`-nya menunjuk baris yang benar-benar ada di Buku Kas. Tautan ke baris yang tidak ada
dianggap BELUM lunas — kasus yang paling mungkin terjadi (bot salah/lupa menautkan), dan lebih
baik ditanyakan daripada dianggap beres diam-diam.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

KEWAJIBAN_JSON = Path(__file__).resolve().parent.parent / "data" / "kewajiban.json"


def muat(path: Path | None = None) -> list[dict]:
    """Semua Kewajiban. Berkas tidak ada atau rusak = daftar kosong."""
    path = path or KEWAJIBAN_JSON
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f).get("kewajiban", [])
    except Exception:  # noqa: BLE001
        return []
    return entries if isinstance(entries, list) else []


def nama(e: dict) -> str:
    return e.get("nama") or e.get("id") or "(tanpa nama)"


def jatuh_tempo(e: dict) -> date | None:
    try:
        return date.fromisoformat((e.get("jatuh_tempo") or "").strip())
    except ValueError:
        return None


def nominal(e: dict) -> float | None:
    """Nominal sebagai angka, atau None kalau isinya bukan angka."""
    try:
        return float(e.get("nominal", 0))
    except (ValueError, TypeError):
        return None


def belum_lunas(daftar: list[dict], rows: list[dict]) -> list[tuple[dict, str | None]]:
    """(Kewajiban, no_resi tautan yang barisnya tidak ada atau None) untuk yang belum lunas."""
    resi_ada = {(r.get("no_resi") or "").strip() for r in rows} - {""}
    hasil = []
    for e in daftar:
        resi = (e.get("lunas_resi") or "").strip()
        if resi and resi in resi_ada:
            continue
        hasil.append((e, resi or None))
    return hasil


def diingatkan(daftar: list[dict], rows: list[dict], today: date,
               pengaturan: dict | None = None) -> list[tuple[dict, int, str | None]]:
    """(Kewajiban, sisa hari, tautan hilang) yang perlu diingatkan hari ini: hanya di H-n dan
    hari-H. Lewat jatuh tempo berhenti sendiri, supaya tidak menumpuk jadi notifikasi yang
    diabaikan."""
    h_minus = int((pengaturan or {}).get("kewajiban_ingat_h_minus", 2))
    hasil = []
    for e, tautan in belum_lunas(daftar, rows):
        jt = jatuh_tempo(e)
        if jt is None:
            continue
        sisa = (jt - today).days
        if sisa in (h_minus, 0):
            hasil.append((e, sisa, tautan))
    return hasil


def tertaut(daftar: list[dict], no_resi: str) -> list[dict]:
    """Kewajiban yang `lunas_resi`-nya menunjuk Transaksi `no_resi`."""
    nomor = (no_resi or "").strip()
    return [e for e in daftar if nomor and (e.get("lunas_resi") or "").strip() == nomor]
