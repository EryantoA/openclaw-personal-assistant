#!/usr/bin/env python3
"""
check-bills.py — Scanner tagihan jatuh tempo & budget alert
Dijalankan via openclaw cron atau code_execution tool.

Usage:
  python3 scripts/check-bills.py --mode jatuh_tempo
  python3 scripts/check-bills.py --mode budget
  python3 scripts/check-bills.py --mode all
"""

import csv
import json
import os
import sys
import argparse
from datetime import datetime, date, timedelta
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


def days_label(days: int) -> str:
    """Buat label hari yang ramah."""
    if days == 0:
        return "Hari ini"
    elif days == 1:
        return "Besok"
    elif days < 0:
        return f"{abs(days)} hari lalu (TERLEWAT!)"
    else:
        return f"{days} hari lagi"


def status_emoji(days: int) -> str:
    """Emoji status berdasarkan jarak hari."""
    if days < 0:
        return "⛔"
    elif days <= 3:
        return "🔴"
    elif days <= 7:
        return "🟡"
    else:
        return "🟢"


# ── Mode: Cek Jatuh Tempo ────────────────────────────────────
def check_jatuh_tempo(days_ahead: int = 7) -> str:
    """Scan tagihan yang jatuh tempo dalam N hari ke depan."""
    bills = load_bills()
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    upcoming = []
    overdue = []

    for row in bills:
        jatuh_tempo_str = row.get("jatuh_tempo", "").strip()
        if not jatuh_tempo_str:
            continue
        try:
            jt_date = datetime.strptime(jatuh_tempo_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        days_diff = (jt_date - today).days
        item = row.get("item", "Tagihan")
        try:
            jumlah = float(row.get("jumlah", 0))
        except (ValueError, TypeError):
            jumlah = 0

        entry = {
            "item": item,
            "jumlah": jumlah,
            "jatuh_tempo": jt_date,
            "days": days_diff,
        }

        if days_diff < 0:
            overdue.append(entry)
        elif days_diff <= days_ahead:
            upcoming.append(entry)

    # Sort berdasarkan hari
    overdue.sort(key=lambda x: x["days"])
    upcoming.sort(key=lambda x: x["days"])

    all_items = overdue + upcoming

    if not all_items:
        return f"✅ Tidak ada tagihan jatuh tempo dalam {days_ahead} hari ke depan."

    lines = ["⏰ REMINDER TAGIHAN JATUH TEMPO", ""]

    if overdue:
        lines.append("⛔ SUDAH TERLEWAT:")
        for item in overdue:
            label = days_label(item["days"])
            lines.append(
                f"  ⛔ {label:20s} — {item['item']:<20s}  {format_rupiah(item['jumlah'])}"
            )
        lines.append("")

    if upcoming:
        lines.append(f"📋 Jatuh tempo {days_ahead} hari ke depan:")
        for item in upcoming:
            emoji = status_emoji(item["days"])
            label = days_label(item["days"])
            lines.append(
                f"  {emoji} {label:20s} — {item['item']:<20s}  {format_rupiah(item['jumlah'])}"
            )
        lines.append("")

    total = sum(i["jumlah"] for i in all_items)
    lines.append(f"💰 Total perlu dibayar: {format_rupiah(total)}")

    return "\n".join(lines)


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
    """Jalankan semua checks, gabungkan hasilnya."""
    parts = []

    # Jatuh tempo (7 hari ke depan untuk cron harian)
    jt_result = check_jatuh_tempo(days_ahead=7)
    if jt_result:
        parts.append(jt_result)

    # Budget
    budget_result = check_budget()
    if budget_result:
        parts.append(budget_result)

    if not parts:
        return "✅ Semua lancar! Tidak ada tagihan jatuh tempo dan budget masih aman."

    return "\n\n─────────────────────\n\n".join(parts)


# ── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Bill checker untuk Family Bill Tracker")
    parser.add_argument(
        "--mode",
        choices=["jatuh_tempo", "budget", "all"],
        default="all",
        help="Mode pengecekan",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Jumlah hari ke depan untuk cek jatuh tempo (default: 7)",
    )
    args = parser.parse_args()

    if args.mode == "jatuh_tempo":
        result = check_jatuh_tempo(days_ahead=args.days)
    elif args.mode == "budget":
        result = check_budget()
    else:
        result = check_all()

    if result:
        print(result)
    else:
        print("✅ Semua lancar!")


if __name__ == "__main__":
    main()
