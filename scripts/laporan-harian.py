#!/usr/bin/env python3
"""Pengeluaran satu hari per Kategori, dihitung skrip — bot hanya menyalin keluarannya.

    python3 scripts/laporan-harian.py                      # hari ini
    python3 scripts/laporan-harian.py --tanggal 2026-10-30  # hari tertentu

Read-only. Aturan hitung (Transfer, Saldo Awal, baris tanpa tanggal/tipe tak dikenal) ada di
scripts/buku_kas.py, satu untuk semua laporan.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402

BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def rupiah(n):
    return f"Rp {n:,.0f}".replace(",", ".")


def susun(rows, hari):
    h = buku_kas.ringkas(rows, hari, hari)
    per = h["per_kategori"]
    baris = [f"📊 Pengeluaran Hari Ini — {hari.day} {BULAN[hari.month]} {hari.year}", ""]
    tak = buku_kas.tak_terhitung(rows)
    if tak:
        baris += [f"⚠️ {len(tak)} transaksi tidak terhitung (tanggal tidak sah / tipe tidak "
                  "dikenal) — periksa bills.csv", ""]
    if not per:
        baris.append("(tidak ada pengeluaran tercatat)")
    else:
        lebar = max(len(k) for k in per) + 1
        for k, v in sorted(per.items(), key=lambda kv: (-kv[1], kv[0])):
            baris.append(f"{k + ':':<{lebar}} {rupiah(v)}")
        baris += ["", f"Total: {rupiah(h['pengeluaran'])}", "",
                  f"📝 {h['transaksi_pengeluaran']} transaksi tercatat"]
    baris += ["", "_Dihitung scripts/laporan-harian.py, tanpa model_"]
    return "\n".join(baris)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pengeluaran satu hari, tanpa model")
    ap.add_argument("--tanggal", metavar="YYYY-MM-DD", help="hari yang dilaporkan (bawaan: hari ini)")
    a = ap.parse_args(argv)
    try:
        hari = date.fromisoformat(a.tanggal) if a.tanggal else date.today()
    except ValueError:
        ap.error(f"--tanggal tidak valid: {a.tanggal}")
    print(susun(buku_kas.muat(), hari))
    return 0


if __name__ == "__main__":
    sys.exit(main())
