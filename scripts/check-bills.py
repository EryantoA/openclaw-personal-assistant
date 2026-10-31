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
  python3 scripts/check-bills.py --mode status        # sisa budget sesuai permintaan (chat)
  python3 scripts/check-bills.py --mode all
  python3 scripts/check-bills.py --mode all --kirim   # cron cek_budget_malam: kirim HANYA kalau ada isi
"""

import os
import sys
import argparse
import importlib.util
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict

# ── Paths ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.resolve()))
import buku_kas  # noqa: E402
import kewajiban  # noqa: E402
import pengaturan  # noqa: E402
import periode  # noqa: E402
import perkiraan  # noqa: E402
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
BILLS_CSV = DATA_DIR / "bills.csv"


def load_bills() -> List[Dict]:
    """Baris bills.csv lewat buku_kas: kosong kalau belum ada, gagal jelas kalau rusak —
    cek malam yang diam karena file rusak terbaca kosong lebih buruk daripada cron error."""
    return buku_kas.muat(BILLS_CSV)


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
def _pengeluaran_bulan(today: date) -> float:
    """Total pengeluaran bulan `today`. Pemasukan dan Transfer tidak ikut: memindahkan uang dari
    Bank ke Kas tidak boleh memakan jatah budget bulan itu (aturan ada di buku_kas.ringkas)."""
    return buku_kas.ringkas(load_bills(), *periode.rentang_bulan(today.strftime("%Y-%m")))["pengeluaran"]


def _bar(persen: float) -> str:
    """Progress bar 20 karakter."""
    bar_filled = min(20, int(persen / 5))
    return "█" * bar_filled + "░" * (20 - bar_filled)


def status_budget(today: Optional[date] = None) -> str:
    """Sisa budget bulan ini sesuai permintaan: selalu menjawab, tidak menunggu ambang alert.

    Dipakai bot untuk "sisa budget" supaya angkanya tidak dihitung model; check_budget tetap
    diam di bawah ambang supaya cron malam tidak berisik.
    """
    budget_bulanan = pengaturan.muat().get("budget_bulanan", 0)
    if budget_bulanan <= 0:
        return ("⚠️ Budget belum diset!\n"
                "Ketik: set budget [nominal]\n"
                "Contoh: set budget 3 juta")
    today = today or date.today()
    total_bulan = _pengeluaran_bulan(today)
    persen = (total_bulan / budget_bulanan) * 100
    sisa = budget_bulanan - total_bulan
    return "\n".join([
        "💰 Status Budget Bulan Ini",
        "",
        f"📊 Budget:    {format_rupiah(budget_bulanan)}",
        f"💸 Terpakai:  {format_rupiah(total_bulan)} ({persen:.0f}%)",
        f"{'💚' if sisa > 0 else '🔴'} Sisa:      {format_rupiah(abs(sisa))}{'  (MINUS!)' if sisa < 0 else ''}",
        "",
        f"{_bar(persen)}  {persen:.0f}%",
        "",
        "_Dihitung scripts/check-bills.py, tanpa model_",
    ])


def check_budget(today: Optional[date] = None) -> str:
    """Cek total pengeluaran bulan ini vs budget."""
    budget_data = pengaturan.muat()
    budget_bulanan = budget_data.get("budget_bulanan", 0)
    alert_persen = budget_data.get("alert_persen", 80)

    if budget_bulanan <= 0:
        return ""  # Budget belum diset, tidak perlu alert

    today = today or date.today()
    total_bulan = _pengeluaran_bulan(today)

    persen = (total_bulan / budget_bulanan) * 100

    if persen < alert_persen:
        return ""  # Belum mencapai threshold, tidak perlu alert

    sisa = budget_bulanan - total_bulan
    bulan_label = today.strftime("%B %Y")
    bar = _bar(persen)

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
    """Ingatkan Kewajiban yang belum lunas, hanya di H-n dan hari-H (aturannya di kewajiban.py)."""
    today = today or date.today()
    daftar = kewajiban.muat()
    if not daftar:
        return ""

    atur = pengaturan.muat()
    kedaluwarsa = int(atur.get("kewajiban_kedaluwarsa_hari", 5))

    baris = []
    for e, sisa, tautan in kewajiban.diingatkan(daftar, load_bills(), today, atur):
        n = kewajiban.nominal(e)
        nominal = "Rp ?" if n is None else format_rupiah(n)
        jt = kewajiban.jatuh_tempo(e)
        kapan = "HARI INI" if sisa == 0 else f"{sisa} hari lagi ({jt.strftime('%d %b')})"
        catatan = f"\n   ⚠️ tertaut ke {tautan}, tapi barisnya tidak ada di bills.csv" if tautan else ""
        baris.append(f"• {kewajiban.nama(e)} — {nominal}, jatuh tempo {kapan}{catatan}")

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
    """Laporkan Perkiraan bulan ini yang belum muncul padahal tanggalnya sudah lewat."""
    today = today or date.today()
    baris = []
    for e in perkiraan.absen(perkiraan.muat(), load_bills(), today.year, today.month, today,
                             pengaturan.muat()):
        arah = (e.get("arah") or "keluar").strip().lower()
        panah = "📥 belum masuk" if arah == "masuk" else "📤 belum keluar"
        nama = e.get("nama") or e.get("id") or "(tanpa nama)"
        baris.append(
            f"• {nama} — {format_rupiah(float(e['nominal']))}, "
            f"biasanya tgl {int(e['tanggal_biasanya'])} — {panah}"
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
def temuan_all(today: Optional[date] = None) -> str:
    """Budget + Kewajiban + Perkiraan yang perlu ditindak; "" kalau tidak ada. Lihat docs/adr/0006."""
    bagian = [check_budget(today), check_kewajiban(today), check_perkiraan(today)]
    return "\n\n─────────────────────────\n\n".join(b for b in bagian if b)


def check_all(today: Optional[date] = None) -> str:
    return temuan_all(today) or "✅ Semua lancar! Budget aman, tidak ada tagihan jatuh tempo."


# ── Main ─────────────────────────────────────────────────────
# ── Pengiriman (cron, tanpa model) ──────────────────────────
def kirim_kalau_ada(isi: str) -> int:
    """Kirim ke nomor pemilik hanya kalau ada yang perlu ditindak. 0 = beres, 1 = gagal kirim.

    Cron cek_budget_malam dulu giliran agent; 12 dari 53 malam gagal sebelum sempat mengecek
    (OAuth mati, kuota, timeout) dan peringatan 26 Agu 2026 tidak pernah terkirim. Sekarang
    command payload, sama dengan Laporan Mingguan/Bulanan (docs/adr/0013). kirim() dari
    scripts/pengirim.py. Dimuat di sini saja karena dulu laporan bulanan dan mingguan meminjam
    fungsi cek dari file ini; sejak Perkiraan/Kewajiban pindah ke module sendiri tidak ada lagi
    yang meminjam, jadi ini boleh menjadi impor biasa.
    """
    if not isi:
        print("\n(tidak ada yang perlu dikirim)")
        return 0
    spec = importlib.util.spec_from_file_location("pengirim", SCRIPT_DIR / "pengirim.py")
    pengirim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pengirim)
    tujuan = pengirim.tujuan_baku()
    if not tujuan:
        print("\n❌ Tidak ada tujuan pengiriman (channels.whatsapp.allowFrom kosong).")
        return 1
    semua_ok = True
    for kanal, ke in tujuan:
        ok, ket = pengirim.kirim(isi, kanal, ke)
        print(f"\n{'✅ terkirim' if ok else '❌ GAGAL'} {kanal} -> {ke}" + (f": {ket}" if ket else ""))
        semua_ok = semua_ok and ok
    return 0 if semua_ok else 1


def main():
    parser = argparse.ArgumentParser(description="Budget checker untuk Family Bill Tracker")
    parser.add_argument(
        "--mode",
        choices=["budget", "status", "all"],
        default="all",
        help="Mode pengecekan",
    )
    parser.add_argument(
        "--tanggal",
        metavar="YYYY-MM-DD",
        help="Anggap hari ini tanggal segini. Untuk menguji pengingat tanpa menunggu; "
        "tidak dipakai cron.",
    )
    parser.add_argument(
        "--kirim",
        action="store_true",
        help="kirim ke nomor pemilik kalau ada isi; gagal kirim = exit 1 (dipakai cron)",
    )
    args = parser.parse_args()

    today = parse_tanggal(args.tanggal) if args.tanggal else None
    if args.tanggal and today is None:
        parser.error(f"--tanggal tidak valid: {args.tanggal}")

    if args.mode == "status":
        if args.kirim:
            parser.error("--mode status hanya menampilkan; tidak untuk --kirim")
        print(status_budget(today))
        return 0

    result = check_budget(today) if args.mode == "budget" else check_all(today)

    if args.kirim:
        # "Ada isi" diputuskan dari bagian-bagiannya, bukan dari teks "✅ Semua lancar" —
        # teks ramah itu boleh berubah tanpa membuat cron diam-diam mengirim tiap malam.
        isi = check_budget(today) if args.mode == "budget" else temuan_all(today)
        print(isi or "✅ Semua lancar!")
        return kirim_kalau_ada(isi)

    if result:
        print(result)
    else:
        print("✅ Semua lancar!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
