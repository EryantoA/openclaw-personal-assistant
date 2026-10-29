"""Pengaturan — isi data/budget.json (CONTEXT.md → Pengaturan).

Dibaca di sini untuk check-bills, Laporan Bulanan, dan Laporan Mingguan. Kategori dan aturan
Duplikat masih dibaca lewat resi.BUDGET_JSON (ADR-0020).
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import copy
import json
from pathlib import Path

BUDGET_JSON = Path(__file__).resolve().parent.parent / "data" / "budget.json"
BAWAAN = {"budget_bulanan": 0, "alert_persen": 80, "kategori_custom": []}


def muat(path: Path | None = None) -> dict:
    """Nilai bawaan digabung isi berkas; bawaan saja kalau berkas tidak ada atau rusak."""
    path = path or BUDGET_JSON
    if not path.exists():
        return copy.deepcopy(BAWAAN)
    try:
        with open(path, encoding="utf-8") as f:
            return {**copy.deepcopy(BAWAAN), **json.load(f)}
    except Exception:  # noqa: BLE001
        return copy.deepcopy(BAWAAN)
