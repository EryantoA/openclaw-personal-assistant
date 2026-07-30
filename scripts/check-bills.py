#!/usr/bin/env python3
"""
check-bills.py — Budget alert
Dijalankan via openclaw cron atau code_execution tool.

Fitur jatuh tempo dibuang: 0 dari 272 baris pernah memakainya selama 4 bulan, dan seluruh
tagihan keluarga ini prabayar. Lihat docs/adr/0003-buku-kas-bukan-perencana-tagihan.md.

Usage:
  python3 scripts/check-bills.py --mode budget
  python3 scripts/check-bills.py --mode all
"""

import csv
import json
import os
import sys
import argparse
from datetime import date
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
BILLS_CSV = DATA_DIR / "bills.csv"
BUDGET_JSON = DATA_DIR / "budget.json"


def load_budget() -> dict:
    """Load budget.json, return default jika belum ada."""
    default = {"budget_bulanan": 0, "alert_persen": 80, "kategori_custom": []}
    if not BUDGET_JSON.exists():
        return default
    try:
        with open(BUDGET_JSON, encoding="utf-8") as f:
            data = json.load(f)
        # Merge with default for missing keys
        return {**default, **data}
    except Exception:
        return default


def load_bills() -> list[dict]:
    """Load data dari bills.csv."""
    if not BILLS_CSV.exists():
        return []
    rows = []
    try:
        with open(BILLS_CSV, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        pass
    return rows


def format_rupiah(amount: float) -> str:
    """Format angka ke format Rupiah."""
    return f"Rp {amount:,.0f}".replace(",", ".")


# ── Mode: Cek Budget ─────────────────────────────────────────
def check_budget() -> str:
    """Cek total pengeluaran bulan ini vs budget."""
    budget_data = load_budget()
    budget_bulanan = budget_data.get("budget_bulanan", 0)
    alert_persen = budget_data.get("alert_persen", 80)

    if budget_bulanan <= 0:
        return ""  # Budget belum diset, tidak perlu alert

    bills = load_bills()
    today = date.today()
    bulan_ini = today.strftime("%Y-%m")

    total_bulan = 0.0
    for row in bills:
        tanggal_str = row.get("tanggal", "")
        if not tanggal_str.startswith(bulan_ini):
            continue
        # Budget hanya menghitung pengeluaran; pemasukan (income) diabaikan.
        # Data lama tanpa kolom `tipe` dianggap pengeluaran.
        if (row.get("tipe") or "pengeluaran").strip().lower() != "pengeluaran":
            continue
        try:
            total_bulan += float(row.get("jumlah", 0))
        except (ValueError, TypeError):
            pass

    persen = (total_bulan / budget_bulanan) * 100

    if persen < alert_persen:
        return ""  # Belum mencapai threshold, tidak perlu alert

    sisa = budget_bulanan - total_bulan
    bulan_label = today.strftime("%B %Y")

    # Progress bar (20 karakter)
    bar_filled = min(20, int(persen / 5))
    bar_empty = 20 - bar_filled
    bar = "█" * bar_filled + "░" * bar_empty

    if persen >= 100:
        status = "🚨 BUDGET HABIS!"
        pesan = f"Pengeluaran sudah melebihi budget bulan {bulan_label}!"
    else:
        status = "⚠️ PERINGATAN BUDGET!"
        pesan = f"Pengeluaran bulan {bulan_label} sudah mencapai {persen:.0f}% dari budget"

    lines = [
        status,
        pesan,
        "",
        f"📊 Budget:    {format_rupiah(budget_bulanan)}",
        f"💸 Terpakai:  {format_rupiah(total_bulan)} ({persen:.0f}%)",
        f"{'💚' if sisa > 0 else '🔴'} Sisa:      {format_rupiah(abs(sisa))}{'  (MINUS!)' if sisa < 0 else ''}",
        "",
        f"{bar}  {persen:.0f}%",
    ]

    return "\n".join(lines)


# ── Mode: All (untuk cron harian) ────────────────────────────
def check_all() -> str:
    """Jalankan semua checks. Saat ini hanya budget — lihat docs/adr/0003."""
    result = check_budget()
    return result if result else "✅ Semua lancar! Budget masih aman."


# ── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Budget checker untuk Family Bill Tracker")
    parser.add_argument(
        "--mode",
        choices=["budget", "all"],
        default="all",
        help="Mode pengecekan",
    )
    args = parser.parse_args()

    result = check_budget() if args.mode == "budget" else check_all()

    if result:
        print(result)
    else:
        print("✅ Semua lancar!")


if __name__ == "__main__":
    main()
