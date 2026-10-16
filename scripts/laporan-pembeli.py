#!/usr/bin/env python3
"""
laporan-pembeli.py — pengeluaran per Pembeli untuk satu Pekan atau bulan, tanpa model
(spec docs/specs/0001, ADR-0015).

Pembeli = kolom `pencatat` (CONTEXT.md). Hanya pengeluaran; Pemasukan dan transfer tidak
ikut. Baris tanpa pencatat dikelompokkan "Tanpa nama". Satu struk berbanyak item = satu
transaksi (dihitung dari `no_resi`). Read-only: tidak menulis apa pun, tidak mengirim.

Usage:
  python3 scripts/laporan-pembeli.py                    # Pekan tutup terakhir
  python3 scripts/laporan-pembeli.py --berjalan         # Pekan berjalan s.d. hari ini
  python3 scripts/laporan-pembeli.py --pekan 2026-10-14 # Pekan yang memuat tanggal itu
  python3 scripts/laporan-pembeli.py --bulan 2026-09    # satu bulan kalender
"""

import argparse
import calendar
import csv
import importlib.util
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _muat_modul(nama, file):
    spec = importlib.util.spec_from_file_location(nama, SCRIPTS / file)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


akun = _muat_modul("akun", "akun.py")
resi = _muat_modul("resi", "resi.py")
_mingguan = _muat_modul("laporan_mingguan", "laporan-mingguan.py")  # satu definisi Pekan
rupiah = akun.rupiah
jumlah = akun.jumlah

BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
TANPA_NAMA = "Tanpa nama"


def rentang_pekan(d):
    mulai = _mingguan.awal_pekan(d)
    return mulai, mulai + timedelta(days=6)


def rentang_bulan(bulan):
    t = datetime.strptime(bulan, "%Y-%m")
    return date(t.year, t.month, 1), date(t.year, t.month, calendar.monthrange(t.year, t.month)[1])


def susun(rows, mulai, akhir, judul, peta=None):
    peta = resi.peta_pembeli() if peta is None else peta
    a, b = mulai.isoformat(), akhir.isoformat()
    per = defaultdict(float)
    per_resi = defaultdict(set)
    for i, r in enumerate(rows):
        if (r.get("tipe") or "pengeluaran").strip().lower() != "pengeluaran":
            continue
        if not a <= (r.get("tanggal") or "") <= b:
            continue
        nama = resi.kanon_pembeli(r.get("pencatat"), peta) or TANPA_NAMA
        per[nama] += jumlah(r)
        per_resi[nama].add((r.get("no_resi") or "").strip() or f"baris-{i}")
    baris = [f"👥 PENGELUARAN PER PEMBELI — {judul}", ""]
    if not per:
        return "\n".join(baris + ["(tidak ada pengeluaran tercatat)"])
    semua = sum(per.values())
    for nama, v in sorted(per.items(), key=lambda kv: (-kv[1], kv[0])):
        n = len(per_resi[nama])
        baris.append(f"{nama}  {rupiah(v)} ({v / semua * 100:.0f}%) · {n} transaksi")
    baris += ["", f"Total: {rupiah(semua)}"]
    return "\n".join(baris)


def _tgl(d):
    return f"{d.day} {BULAN[d.month]}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pengeluaran per Pembeli, tanpa model")
    pilih = ap.add_mutually_exclusive_group()
    pilih.add_argument("--pekan", metavar="YYYY-MM-DD", help="Pekan yang memuat tanggal ini")
    pilih.add_argument("--berjalan", action="store_true", help="Pekan berjalan s.d. hari ini")
    pilih.add_argument("--bulan", metavar="YYYY-MM", help="satu bulan kalender")
    ap.add_argument("--hari-ini", metavar="YYYY-MM-DD", help="anggap hari ini tanggal segini (uji)")
    a = ap.parse_args(argv)

    hari_ini = date.fromisoformat(a.hari_ini) if a.hari_ini else date.today()
    if a.bulan:
        try:
            mulai, akhir = rentang_bulan(a.bulan)
        except ValueError:
            ap.error(f"--bulan tidak valid: {a.bulan}")
        if mulai > hari_ini:
            ap.error(f"{a.bulan} belum dimulai")
        judul = f"Bulan {BULAN[mulai.month]} {mulai.year}"
        if akhir >= hari_ini:  # bulan berjalan: angkanya belum final
            akhir = hari_ini
            judul += f" (s.d. {_tgl(hari_ini)})"
    else:
        if a.berjalan:
            mulai, _ = rentang_pekan(hari_ini)
            akhir = hari_ini
        else:
            acuan = date.fromisoformat(a.pekan) if a.pekan else hari_ini - timedelta(days=7)
            mulai, akhir = rentang_pekan(acuan)
            if akhir >= hari_ini:
                ap.error(f"Pekan {mulai}–{akhir} belum tutup; pakai --berjalan")
        judul = f"Pekan {_tgl(mulai)}–{_tgl(akhir)} {akhir.year}"

    if not akun.BILLS.exists():
        rows = []
    else:
        with akun.BILLS.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    print(susun(rows, mulai, akhir, judul))
    return 0


if __name__ == "__main__":
    sys.exit(main())
