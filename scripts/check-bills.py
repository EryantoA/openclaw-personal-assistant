#!/usr/bin/env python3
"""
check-bills.py — Budget, Kewajiban, dan Perkiraan
Dijalankan via openclaw cron atau code_execution tool.

Kolom `jatuh_tempo` di bills.csv tetap tidak dihidupkan (docs/adr/0003). Yang kembali adalah
konsepnya, lewat dua file terpisah: Kewajiban (tagihan pascabayar yang sudah datang) dan
Perkiraan (transaksi berulang yang diharapkan). Lihat docs/adr/0006.

Script ini TIDAK PERNAH MENULIS apa pun. Status kewajiban (aktif/lunas/kedaluwarsa) selalu
dihitung ulang dari fakta yang tersimpan — tautan `lunas_resi` — supaya tidak ada field status
yang bisa basi. Itu yang membedakannya dari fitur jatuh tempo yang mati dulu.

Semua fungsi cek mengembalikan "" kalau tidak ada yang perlu ditindak, supaya cron malam tetap
diam total di hari-hari biasa.

Usage:
  python3 scripts/check-bills.py --mode budget
  python3 scripts/check-bills.py --mode all
"""

import csv
import json
import os
import sys
import argparse
import calendar
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict

# ── Paths ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
BILLS_CSV = DATA_DIR / "bills.csv"
BUDGET_JSON = DATA_DIR / "budget.json"
KEWAJIBAN_JSON = DATA_DIR / "kewajiban.json"
PERKIRAAN_JSON = DATA_DIR / "perkiraan.json"


def load_budget() -> Dict:
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


def load_bills() -> List[Dict]:
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


def load_list(path: Path, key: str) -> List[Dict]:
    """Load daftar dari file JSON berbentuk {"<key>": [...]}. Kosong kalau belum ada/rusak."""
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get(key, [])
        return entries if isinstance(entries, list) else []
    except Exception:
        return []


def format_rupiah(amount: float) -> str:
    """Format angka ke format Rupiah."""
    return f"Rp {amount:,.0f}".replace(",", ".")


def parse_tanggal(value: str) -> Optional[date]:
    """Parse YYYY-MM-DD. None kalau kosong atau tidak valid."""
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


# ── Mode: Cek Budget ─────────────────────────────────────────
def check_budget(today: Optional[date] = None) -> str:
    """Cek total pengeluaran bulan ini vs budget."""
    budget_data = load_budget()
    budget_bulanan = budget_data.get("budget_bulanan", 0)
    alert_persen = budget_data.get("alert_persen", 80)

    if budget_bulanan <= 0:
        return ""  # Budget belum diset, tidak perlu alert

    bills = load_bills()
    today = today or date.today()
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


# ── Mode: Cek Kewajiban ──────────────────────────────────────
def check_kewajiban(today: Optional[date] = None) -> str:
    """Ingatkan Kewajiban yang belum lunas, hanya di H-n dan hari-H.

    Sebuah Kewajiban dianggap lunas kalau `lunas_resi`-nya menunjuk baris yang benar-benar ada
    di bills.csv. Tautan yang menunjuk ke baris tak ada diperlakukan BELUM lunas — itu justru
    kasus yang paling mungkin terjadi (bot salah/lupa menautkan), dan lebih baik ditanyakan
    daripada dianggap beres diam-diam.
    """
    today = today or date.today()
    entries = load_list(KEWAJIBAN_JSON, "kewajiban")
    if not entries:
        return ""

    budget_data = load_budget()
    h_minus = int(budget_data.get("kewajiban_ingat_h_minus", 2))
    kedaluwarsa = int(budget_data.get("kewajiban_kedaluwarsa_hari", 5))

    resi_ada = {(r.get("no_resi") or "").strip() for r in load_bills()}
    resi_ada.discard("")

    baris = []
    for e in entries:
        jt = parse_tanggal(e.get("jatuh_tempo", ""))
        if jt is None:
            continue

        resi = (e.get("lunas_resi") or "").strip()
        if resi and resi in resi_ada:
            continue  # sudah dibayar dan tertaut — tidak perlu diingatkan

        sisa = (jt - today).days
        # Bunyi hanya di dua titik. Lewat kedaluwarsa → berhenti dilaporkan (bukan lunas,
        # tapi tidak diketahui) supaya tidak menumpuk jadi notifikasi yang diabaikan.
        if sisa not in (h_minus, 0):
            continue

        try:
            nominal = format_rupiah(float(e.get("nominal", 0)))
        except (ValueError, TypeError):
            nominal = "Rp ?"

        kapan = "HARI INI" if sisa == 0 else f"{sisa} hari lagi ({jt.strftime('%d %b')})"
        nama = e.get("nama") or e.get("id") or "(tanpa nama)"
        catatan = ""
        if resi and resi not in resi_ada:
            catatan = f"\n   ⚠️ tertaut ke {resi}, tapi barisnya tidak ada di bills.csv"
        baris.append(f"• {nama} — {nominal}, jatuh tempo {kapan}{catatan}")

    if not baris:
        return ""

    return "\n".join(
        [
            "🧾 TAGIHAN BELUM DIBAYAR",
            "",
            *baris,
            "",
            f"Setelah {kedaluwarsa} hari lewat jatuh tempo, pengingat ini berhenti sendiri.",
        ]
    )


# ── Mode: Cek Perkiraan ──────────────────────────────────────
def check_perkiraan(today: Optional[date] = None) -> str:
    """Laporkan Perkiraan yang belum muncul di bills.csv padahal tanggalnya sudah lewat.

    Pencocokan sengaja longgar (kategori + arah + nominal dalam toleransi): nominal ikut kurs
    (Anthropic 366.588 vs 366.751) dan pemasukan kadang tercatat sebagai satu baris gabungan.
    Salah tebak di sini cuma berujung pertanyaan, bukan klaim utang.
    """
    today = today or date.today()
    entries = [e for e in load_list(PERKIRAAN_JSON, "perkiraan") if e.get("aktif", True)]
    if not entries:
        return ""

    budget_data = load_budget()
    toleransi_hari = int(budget_data.get("perkiraan_toleransi_hari", 3))
    toleransi_persen = float(budget_data.get("perkiraan_toleransi_persen", 10))

    bulan_ini = today.strftime("%Y-%m")
    rows = [r for r in load_bills() if (r.get("tanggal") or "").startswith(bulan_ini)]

    baris = []
    for e in entries:
        try:
            hari = int(e.get("tanggal_biasanya", 0))
            nominal = float(e.get("nominal", 0))
        except (ValueError, TypeError):
            continue
        if not 1 <= hari <= 31 or nominal <= 0:
            continue

        # Bulan pendek: tanggal 31 jatuh di hari terakhir bulan itu.
        akhir_bulan = calendar.monthrange(today.year, today.month)[1]
        tanggal_harap = date(today.year, today.month, min(hari, akhir_bulan))
        if (today - tanggal_harap).days <= toleransi_hari:
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

        ketemu = False
        for r in rows:
            if (r.get("tipe") or "pengeluaran").strip().lower() != tipe_dicari:
                continue
            if (r.get("kategori") or "").strip().lower() != kategori:
                continue
            try:
                if abs(float(r.get("jumlah", 0)) - nominal) <= batas:
                    ketemu = True
                    break
            except (ValueError, TypeError):
                continue

        if ketemu:
            continue

        panah = "📥 belum masuk" if arah == "masuk" else "📤 belum keluar"
        nama = e.get("nama") or e.get("id") or "(tanpa nama)"
        baris.append(
            f"• {nama} — {format_rupiah(nominal)}, biasanya tgl {hari} — {panah}"
        )

    if not baris:
        return ""

    return "\n".join(
        [
            "🔮 PERKIRAAN YANG BELUM MUNCUL",
            "",
            *baris,
            "",
            "Mungkin memang belum terjadi, mungkin cuma belum dicatat — cek sebentar.",
        ]
    )


# ── Mode: All (untuk cron harian) ────────────────────────────
def check_all(today: Optional[date] = None) -> str:
    """Budget + Kewajiban + Perkiraan. Lihat docs/adr/0006."""
    bagian = [check_budget(today), check_kewajiban(today), check_perkiraan(today)]
    terisi = [b for b in bagian if b]
    if not terisi:
        return "✅ Semua lancar! Budget aman, tidak ada tagihan jatuh tempo."
    return "\n\n─────────────────────────\n\n".join(terisi)


# ── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Budget checker untuk Family Bill Tracker")
    parser.add_argument(
        "--mode",
        choices=["budget", "all"],
        default="all",
        help="Mode pengecekan",
    )
    parser.add_argument(
        "--tanggal",
        metavar="YYYY-MM-DD",
        help="Anggap hari ini tanggal segini. Untuk menguji pengingat tanpa menunggu; "
        "tidak dipakai cron.",
    )
    args = parser.parse_args()

    today = parse_tanggal(args.tanggal) if args.tanggal else None
    if args.tanggal and today is None:
        parser.error(f"--tanggal tidak valid: {args.tanggal}")

    result = check_budget(today) if args.mode == "budget" else check_all(today)

    if result:
        print(result)
    else:
        print("✅ Semua lancar!")


if __name__ == "__main__":
    main()
