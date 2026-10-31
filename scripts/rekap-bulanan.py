#!/usr/bin/env python3
"""Rekap per bulan untuk semua bulan, dihitung skrip — bot hanya menyalin keluarannya.

    python3 scripts/rekap-bulanan.py                                # semua bulan
    python3 scripts/rekap-bulanan.py --dari 2026-08 --sampai 2026-10  # sebagian saja

Read-only. Tiap bulan: Pemasukan, Pengeluaran, Arus Kas Bulan (berdiri sendiri), dan Saldo
(kumulatif, dibawa antar bulan). Saldo tetap dihitung dari awal walau tampilan dibatasi
--dari/--sampai. Aturan hitung (Transfer, Saldo Awal, baris tanpa tanggal/tipe tak dikenal)
ada di scripts/buku_kas.py, satu untuk semua laporan; jumlah transaksi dihitung per baris,
sama dengan Laporan Bulanan.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402
import periode  # noqa: E402

NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
              "Agustus", "September", "Oktober", "November", "Desember"]
BULAN_PENDEK = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def rp(x):
    return ("-" if x < 0 else "") + f"Rp {abs(x):,.0f}".replace(",", ".")


def nama(bulan):
    t, b = map(int, bulan.split("-"))
    return f"{NAMA_BULAN[b - 1]} {t}"


def _bulan_berikut(bulan):
    t, b = map(int, bulan.split("-"))
    return f"{t + 1}-01" if b == 12 else f"{t}-{b + 1:02d}"


def _rentang(rows):
    """(bulan pertama, bulan terakhir) yang punya Pemasukan/Pengeluaran; None bila kosong."""
    bulan = [tgl.strftime("%Y-%m") for r in rows
             if (tgl := buku_kas.tanggal(r)) is not None and buku_kas.arah(r) in ("pemasukan", "pengeluaran")]
    return (min(bulan), max(bulan)) if bulan else None


def _transaksi(rows, bulan):
    return sum(1 for r in rows
               if (tgl := buku_kas.tanggal(r)) is not None and tgl.strftime("%Y-%m") == bulan
               and buku_kas.arah(r) in ("pemasukan", "pengeluaran") and not buku_kas.saldo_awal(r))


def susun(rows, hari_ini, dari=None, sampai=None):
    baris = ["📅 REKAP PER BULAN", ""]
    tak = buku_kas.tak_terhitung(rows)
    if tak:
        baris += [f"⚠️ {len(tak)} transaksi tidak terhitung (tanggal tidak sah / tipe tidak "
                  "dikenal) — periksa bills.csv", ""]
    rentang = _rentang(rows)
    if rentang is None:
        return "\n".join(baris + ["(belum ada transaksi tercatat)", "",
                                  "_Dihitung scripts/rekap-bulanan.py, tanpa model_"])

    ini = hari_ini.strftime("%Y-%m")
    bulan, terakhir = rentang
    terakhir_tampil, saldo_terakhir = None, 0
    while bulan <= terakhir:
        if (dari and bulan < dari) or (sampai and bulan > sampai):
            bulan = _bulan_berikut(bulan)
            continue
        h = buku_kas.arus_kas_bulan(rows, bulan)
        arus = h["pemasukan"] - h["pengeluaran"]
        per = min(periode.akhir_bulan(bulan), hari_ini) if bulan == ini else periode.akhir_bulan(bulan)
        saldo = buku_kas.saldo(rows, per)
        judul = nama(bulan) + (" (berjalan)" if bulan == ini else "")
        baris += [f"▸ {judul}",
                  f"  📥 Pemasukan:   {rp(h['pemasukan'])}",
                  f"  📤 Pengeluaran: {rp(h['pengeluaran'])}",
                  f"  {'💚' if arus >= 0 else '🔴'} Arus Kas:    {rp(arus)}  "
                  f"({_transaksi(rows, bulan)} transaksi)",
                  f"  🏦 Saldo:       {rp(saldo)}", ""]
        terakhir_tampil, saldo_terakhir = bulan, saldo
        bulan = _bulan_berikut(bulan)

    if terakhir_tampil is None:
        return "\n".join(baris + ["(tidak ada bulan pada rentang itu)", "",
                                  "_Dihitung scripts/rekap-bulanan.py, tanpa model_"])
    if terakhir_tampil == ini:
        kapan = f"per {hari_ini.day} {BULAN_PENDEK[hari_ini.month - 1]} {hari_ini.year}"
    else:
        kapan = f"akhir {nama(terakhir_tampil)}"
    baris += ["─────────────────────────", f"Saldo terakhir ({kapan}): {rp(saldo_terakhir)}", "",
              "_Dihitung scripts/rekap-bulanan.py, tanpa model_"]
    return "\n".join(baris)


def _bulan_sah(ap, nilai):
    try:
        datetime.strptime(nilai, "%Y-%m")
    except ValueError:
        ap.error(f"bulan tidak valid: {nilai} (format YYYY-MM)")
    return nilai


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rekap per bulan, tanpa model")
    ap.add_argument("--dari", metavar="YYYY-MM", help="bulan pertama yang ditampilkan")
    ap.add_argument("--sampai", metavar="YYYY-MM", help="bulan terakhir yang ditampilkan")
    ap.add_argument("--hari-ini", metavar="YYYY-MM-DD", help="anggap hari ini tanggal segini (uji)")
    a = ap.parse_args(argv)
    try:
        hari_ini = date.fromisoformat(a.hari_ini) if a.hari_ini else date.today()
    except ValueError:
        ap.error(f"--hari-ini tidak valid: {a.hari_ini}")
    dari = _bulan_sah(ap, a.dari) if a.dari else None
    sampai = _bulan_sah(ap, a.sampai) if a.sampai else None
    print(susun(buku_kas.muat(), hari_ini, dari, sampai))
    return 0


if __name__ == "__main__":
    sys.exit(main())
