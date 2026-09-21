#!/usr/bin/env python3
"""
laporan-mingguan.py — Laporan Mingguan untuk satu Pekan, tanpa model (docs/adr/0013).

Pekan = Senin 00:00 – Minggu 23:59 WIB (CONTEXT.md). Default: Pekan terakhir yang sudah tutup.
Cron menjalankannya Senin 07:00 dengan --kirim; permintaan lewat chat menjalankan
--berjalan dan meneruskan output apa adanya.

Aturan hitung sengaja dipinjam, bukan ditulis ulang:
  - Saldo           → akun.saldo_global (transfer tak ikut, Saldo Awal ikut)
  - Perkiraan       → check-bills.perkiraan_absen (sama dengan Laporan Bulanan, ADR 0012)
  - Tujuan          → periksa-kesehatan.tujuan_baku (nomor pemilik dari config)
  - Kirim           → laporan-bulanan.kirim (3 percobaan, jeda 60 dtk — kirim WA gagal acak ±23%)

"Pekan lalu" dihitung ulang dari catatan hari ini — tidak ada simpanan, tidak ada Koreksi.

Usage:
  python3 scripts/laporan-mingguan.py                       # Pekan tutup terakhir, cetak saja
  python3 scripts/laporan-mingguan.py --pekan 2026-09-14    # Pekan yang memuat tanggal itu
  python3 scripts/laporan-mingguan.py --berjalan            # Pekan berjalan s.d. hari ini
  python3 scripts/laporan-mingguan.py --kirim               # cetak + kirim (dipakai cron)
"""

import argparse
import calendar
import importlib.util
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _muat_modul(nama, file):
    spec = importlib.util.spec_from_file_location(nama, SCRIPTS / file)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


akun = _muat_modul("akun", "akun.py")
cek = _muat_modul("check_bills", "check-bills.py")
kesehatan = _muat_modul("periksa_kesehatan", "periksa-kesehatan.py")
bulanan = _muat_modul("laporan_bulanan", "laporan-bulanan.py")

rupiah = akun.rupiah
jumlah = akun.jumlah

BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
EMOJI = {
    "food": "🍚", "groceries": "🛒", "shopping": "🛍️", "transport": "🚗", "utilities": "⚡",
    "health": "💊", "entertainment": "🎬", "clothing": "👕", "donation": "🤲", "pet": "🐾",
    "personal_care": "🧴", "communication": "📱", "beauty": "💄", "subscription": "🔁",
    "insurance": "🛡️", "event": "🎉", "education": "📚",
}
ITEM_MAKS = 60  # struk gabungan bisa ratusan karakter
HARI_KOSONG_MIN = 2  # berturut-turut, dalam satu Pekan (ADR 0013)
KATEGORI_BUKAN_PEMASUKAN = {"opening_balance"}  # Saldo Awal bukan Pemasukan (CONTEXT.md)


def tipe(r):
    return (r.get("tipe") or "pengeluaran").strip().lower()


def tgl(d):
    return f"{d.day} {BULAN[d.month]}"


def awal_pekan(d):
    return d - timedelta(days=d.weekday())


def di_antara(rows, mulai, akhir):
    """Baris bertanggal mulai..akhir (inklusif)."""
    a, b = mulai.isoformat(), akhir.isoformat()
    return [r for r in rows if a <= (r.get("tanggal") or "") <= b]


def pengeluaran(rows):
    return [r for r in rows if tipe(r) == "pengeluaran"]


def pemasukan(rows):
    return [r for r in rows if tipe(r) == "pemasukan"
            and (r.get("kategori") or "").strip().lower() not in KATEGORI_BUKAN_PEMASUKAN]


def total(rows):
    return sum(jumlah(r) for r in rows)


# ── Bagian-bagian laporan ────────────────────────────────────────────────
def bagian_kategori(keluar):
    per = defaultdict(float)
    for r in keluar:
        per[(r.get("kategori") or "other").strip().lower()] += jumlah(r)
    semua = total(keluar)
    urut = sorted(per.items(), key=lambda kv: -kv[1])
    lebar = max((len(k) for k, _ in urut), default=0)
    baris = ["💸 PENGELUARAN PER KATEGORI"]
    for k, v in urut:
        persen = v / semua * 100 if semua else 0
        baris.append(f"{EMOJI.get(k, '📦')} {k.ljust(lebar)}  {rupiah(v)}  ({persen:.0f}%)")
    if not urut:
        baris.append("(tidak ada pengeluaran tercatat)")
    return baris


def bagian_banding(keluar, keluar_lalu):
    ini, lalu = total(keluar), total(keluar_lalu)
    baris = [f"Total: {rupiah(ini)} · {len(keluar)} transaksi"]
    selisih = ini - lalu
    tanda = "+" if selisih > 0 else "-" if selisih < 0 else "±"
    persen = f" ({tanda}{abs(selisih) / lalu * 100:.0f}%)" if lalu else ""
    baris.append(f"vs pekan lalu: {tanda}{rupiah(abs(selisih))}{persen}")
    baris.append("  (pekan lalu dihitung dari catatan hari ini)")
    return baris


def bagian_terbesar(keluar, n=3):
    urut = sorted(keluar, key=lambda r: -jumlah(r))[:n]
    baris = [f"🏆 {n} TERBESAR"]
    for i, r in enumerate(urut, 1):
        d = date.fromisoformat(r["tanggal"])
        item = r.get("item") or "(tanpa item)"
        if len(item) > ITEM_MAKS:
            item = item[:ITEM_MAKS - 1].rstrip() + "…"
        baris.append(f"{i}. {item} — {rupiah(jumlah(r))} ({tgl(d)})")
    if not urut:
        baris.append("(tidak ada)")
    return baris


def bulan_dalam(mulai, akhir):
    """(tahun, bulan) yang disentuh rentang ini, urut."""
    hasil, d = [], mulai
    while d <= akhir:
        if (d.year, d.month) not in hasil:
            hasil.append((d.year, d.month))
        d += timedelta(days=1)
    return hasil


def bagian_budget(rows, mulai, akhir, pekan_tutup):
    """Budget tiap bulan yang disentuh Pekan. Bulan yang berakhir di dalam Pekan = (tutup)."""
    anggaran = float(cek.load_budget().get("budget_bulanan", 0) or 0)
    baris = []
    for th, bl in bulan_dalam(mulai, akhir):
        akhir_bulan = date(th, bl, calendar.monthrange(th, bl)[1])
        tutup = akhir_bulan <= akhir and (pekan_tutup or akhir_bulan < akhir)
        batas = min(akhir, akhir_bulan)
        pakai = total(pengeluaran(di_antara(rows, date(th, bl, 1), batas)))
        label = f"Budget {BULAN[bl]}{' (tutup)' if tutup else ''}"
        if anggaran > 0:
            baris.append(f"📅 {label}: {rupiah(pakai)} dari {rupiah(anggaran)} ({pakai / anggaran * 100:.0f}%)")
        else:
            baris.append(f"📅 {label}: {rupiah(pakai)} (budget belum diset)")
    return baris


def bagian_kewajiban(rows):
    resi_ada = {(r.get("no_resi") or "").strip() for r in rows} - {""}
    baris = []
    for e in cek.load_list(cek.KEWAJIBAN_JSON, "kewajiban"):
        resi = (e.get("lunas_resi") or "").strip()
        if resi and resi in resi_ada:
            continue
        jt = cek.parse_tanggal(e.get("jatuh_tempo", ""))
        nama = e.get("nama") or e.get("id") or "(tanpa nama)"
        try:
            nominal = rupiah(float(e.get("nominal", 0)))
        except (ValueError, TypeError):
            nominal = "Rp ?"
        baris.append(f"• {nama} — {nominal}, jatuh tempo {tgl(jt) if jt else '?'}")
    if not baris:
        return ["🧾 Kewajiban belum lunas: tidak ada"]
    return ["🧾 Kewajiban belum lunas:", *baris]


def bagian_perkiraan(mulai, akhir, pekan_tutup):
    """Tiap bulan yang disentuh Pekan. Bulan tutup: yang absen = tidak muncul.
    Bulan berjalan: yang absen = belum muncul (≈tgl), atau belum waktunya kalau tanggalnya
    masih sesudah akhir Pekan."""
    semua = [e for e in cek.load_list(cek.PERKIRAAN_JSON, "perkiraan") if e.get("aktif", True)]
    if not semua:
        return []
    baris = []
    for th, bl in bulan_dalam(mulai, akhir):
        akhir_bulan = date(th, bl, calendar.monthrange(th, bl)[1])
        tutup = akhir_bulan <= akhir and (pekan_tutup or akhir_bulan < akhir)
        absen_nama = {(e.get("id") or e.get("nama")) for e in cek.perkiraan_absen(th, bl, None)}
        item = []
        for e in semua:
            nama = e.get("nama") or e.get("id") or "(tanpa nama)"
            try:
                hari = min(int(e.get("tanggal_biasanya", 0)), akhir_bulan.day)
            except (ValueError, TypeError):
                continue
            if (e.get("id") or e.get("nama")) not in absen_nama:
                item.append(f"{nama} ✓")
            elif tutup:
                item.append(f"{nama} (≈{hari}) tidak muncul")
            elif date(th, bl, hari) > akhir:
                item.append(f"{nama} (≈{hari}) belum waktunya")
            else:
                item.append(f"{nama} (≈{hari}) belum muncul")
        label = f"🔮 Perkiraan {BULAN[bl]}{' (tutup)' if tutup else ''}:"
        baris.append(label)
        baris.extend(f"  • {i}" for i in item)
    return baris


def hari_kosong(rows, mulai, akhir):
    """Deret ≥HARI_KOSONG_MIN hari tanpa Pengeluaran di dalam [mulai, akhir]."""
    ada = {r["tanggal"] for r in pengeluaran(di_antara(rows, mulai, akhir))}
    deret, kini, d = [], [], mulai
    while d <= akhir:
        if d.isoformat() in ada:
            if len(kini) >= HARI_KOSONG_MIN:
                deret.append(kini)
            kini = []
        else:
            kini.append(d)
        d += timedelta(days=1)
    if len(kini) >= HARI_KOSONG_MIN:
        deret.append(kini)
    return deret


# ── Susun ────────────────────────────────────────────────────────────────
def susun(rows, mulai, akhir, pekan_tutup):
    minggu = mulai + timedelta(days=6)
    keluar = pengeluaran(di_antara(rows, mulai, akhir))
    keluar_lalu = pengeluaran(di_antara(rows, mulai - timedelta(days=7), mulai - timedelta(days=1)))

    judul = "📊 LAPORAN MINGGUAN" if pekan_tutup else "📊 LAPORAN MINGGUAN — Pekan berjalan"
    periode = f"Pekan: Senin {tgl(mulai)} – Minggu {tgl(minggu)} {minggu.year}"
    if not pekan_tutup:
        periode += f" (sampai {HARI[akhir.weekday()]} {tgl(akhir)})"

    baris = [judul, periode, ""]

    for deret in hari_kosong(rows, mulai, akhir):
        nama = ", ".join(f"{HARI[d.weekday()]} {d.day}" for d in deret)
        baris += [f"⚠️ Tidak ada catatan pada {nama} {BULAN[deret[-1].month]} — "
                  "angka pekan ini mungkin kurang", ""]

    baris += bagian_kategori(keluar)
    baris += bagian_banding(keluar, keluar_lalu)
    baris += [""] + bagian_terbesar(keluar)

    saldo = akun.saldo_global(rows, sampai=(akhir + timedelta(days=1)).isoformat())
    baris += [
        "",
        f"💰 Pemasukan pekan ini: {rupiah(total(pemasukan(di_antara(rows, mulai, akhir))))}",
        f"🏦 Saldo {'akhir Pekan' if pekan_tutup else 'per ' + tgl(akhir)}: {rupiah(saldo)}",
    ]
    baris += bagian_budget(rows, mulai, akhir, pekan_tutup)
    baris += [""] + bagian_kewajiban(rows)
    perkiraan = bagian_perkiraan(mulai, akhir, pekan_tutup)
    if perkiraan:
        baris += perkiraan
    return "\n".join(baris)


def main():
    ap = argparse.ArgumentParser(description="Laporan Mingguan (tanpa model, ADR 0013)")
    pilih = ap.add_mutually_exclusive_group()
    pilih.add_argument("--pekan", metavar="YYYY-MM-DD", help="Pekan yang memuat tanggal ini")
    pilih.add_argument("--berjalan", action="store_true", help="Pekan berjalan s.d. hari ini")
    ap.add_argument("--hari-ini", metavar="YYYY-MM-DD", help="anggap hari ini tanggal segini (uji)")
    ap.add_argument("--kirim", action="store_true", help="kirim ke nomor pemilik; gagal = exit 1")
    a = ap.parse_args()

    hari_ini = date.fromisoformat(a.hari_ini) if a.hari_ini else date.today()
    if a.berjalan:
        mulai, akhir, tutup = awal_pekan(hari_ini), hari_ini, False
    else:
        acuan = date.fromisoformat(a.pekan) if a.pekan else hari_ini - timedelta(days=7)
        mulai = awal_pekan(acuan)
        akhir = mulai + timedelta(days=6)
        if akhir >= hari_ini:
            ap.error(f"Pekan {mulai}–{akhir} belum tutup; pakai --berjalan")
        tutup = True

    rows, _ = akun.muat()
    laporan = susun(rows, mulai, akhir, tutup)
    print(laporan)

    if not a.kirim:
        return 0
    tujuan = kesehatan.tujuan_baku()
    if not tujuan:
        print("\n❌ Tidak ada tujuan pengiriman (channels.whatsapp.allowFrom kosong).")
        return 1
    semua_ok = True
    for kanal, ke in tujuan:
        ok, ket = bulanan.kirim(laporan, kanal, ke)
        print(f"\n{'✅ terkirim' if ok else '❌ GAGAL'} {kanal} -> {ke}" + (f": {ket}" if ket else ""))
        semua_ok = semua_ok and ok
    return 0 if semua_ok else 1


if __name__ == "__main__":
    sys.exit(main())
