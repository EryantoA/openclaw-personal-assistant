#!/usr/bin/env python3
"""
laporan-mingguan.py — Laporan Mingguan untuk satu Pekan, tanpa model (docs/adr/0013).

Pekan = Senin 00:00 – Minggu 23:59 WIB (CONTEXT.md). Default: Pekan terakhir yang sudah tutup.
Cron menjalankannya Senin 07:00 dengan --kirim; permintaan lewat chat menjalankan
--berjalan dan meneruskan output apa adanya.

Aturan hitung sengaja dipinjam, bukan ditulis ulang:
  - Arah, jumlah, Saldo → buku_kas (transfer tak ikut, Saldo Awal ikut Saldo, bukan Pemasukan)
  - Pekan, bulan    → periode (satu definisi Pekan untuk semua laporan)
  - Perkiraan       → perkiraan.absen (sama dengan Laporan Bulanan dan cek malam, ADR 0012)
  - Kewajiban       → kewajiban.belum_lunas (lunas = lunas_resi menunjuk baris yang ada)
  - Budget          → pengaturan (data/budget.json)
  - Tujuan          → pengirim.tujuan_baku (nomor pemilik dari config)
  - Kirim           → pengirim.kirim (3 percobaan, jeda 60 dtk — kirim WA gagal acak ±23%)

"Pekan lalu" dihitung ulang dari catatan hari ini — tidak ada simpanan, tidak ada Koreksi.

Usage:
  python3 scripts/laporan-mingguan.py                       # Pekan tutup terakhir, cetak saja
  python3 scripts/laporan-mingguan.py --pekan 2026-09-14    # Pekan yang memuat tanggal itu
  python3 scripts/laporan-mingguan.py --berjalan            # Pekan berjalan s.d. hari ini
  python3 scripts/laporan-mingguan.py --kirim               # cetak + kirim (dipakai cron)
"""

import argparse
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import akun  # noqa: E402
import buku_kas  # noqa: E402
import kewajiban  # noqa: E402
import pengaturan  # noqa: E402
import pengirim  # noqa: E402
import periode  # noqa: E402
import perkiraan  # noqa: E402

rupiah = akun.rupiah
jumlah = buku_kas.jumlah

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


def tgl(d):
    return f"{d.day} {BULAN[d.month]}"


def di_antara(rows, mulai, akhir):
    """Baris bertanggal mulai..akhir (inklusif)."""
    return [r for r in rows if (t := buku_kas.tanggal(r)) is not None and mulai <= t <= akhir]


def pengeluaran(rows):
    return [r for r in rows if buku_kas.arah(r) == "pengeluaran"]


def pemasukan(rows):
    return [r for r in rows if buku_kas.arah(r) == "pemasukan" and not buku_kas.saldo_awal(r)]


def total(rows):
    return sum(jumlah(r) for r in rows)


# ── Bagian-bagian laporan ────────────────────────────────────────────────
def bagian_kategori(keluar):
    per = defaultdict(int)
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
        d = buku_kas.tanggal(r)
        item = r.get("item") or "(tanpa item)"
        if len(item) > ITEM_MAKS:
            item = item[:ITEM_MAKS - 1].rstrip() + "…"
        baris.append(f"{i}. {item} — {rupiah(jumlah(r))} ({tgl(d)})")
    if not urut:
        baris.append("(tidak ada)")
    return baris


def bagian_budget(rows, mulai, akhir, pekan_tutup):
    """Budget tiap bulan yang disentuh Pekan. Bulan yang berakhir di dalam Pekan = (tutup)."""
    anggaran = float(pengaturan.muat().get("budget_bulanan", 0) or 0)
    baris = []
    for th, bl in periode.bulan_dalam(mulai, akhir):
        akhir_bulan = periode.akhir_bulan(f"{th:04d}-{bl:02d}")
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
    baris = []
    for e, _ in kewajiban.belum_lunas(kewajiban.muat(), rows):
        jt = kewajiban.jatuh_tempo(e)
        n = kewajiban.nominal(e)
        nominal = "Rp ?" if n is None else rupiah(n)
        baris.append(f"• {kewajiban.nama(e)} — {nominal}, jatuh tempo {tgl(jt) if jt else '?'}")
    if not baris:
        return ["🧾 Kewajiban belum lunas: tidak ada"]
    return ["🧾 Kewajiban belum lunas:", *baris]


def bagian_perkiraan(rows, mulai, akhir, pekan_tutup):
    """Tiap bulan yang disentuh Pekan. Bulan tutup: yang absen = tidak muncul.
    Bulan berjalan: yang absen = belum muncul (≈tgl), atau belum waktunya kalau tanggalnya
    masih sesudah akhir Pekan."""
    semua = perkiraan.muat()
    if not semua:
        return []
    atur = pengaturan.muat()
    baris = []
    for th, bl in periode.bulan_dalam(mulai, akhir):
        akhir_bulan = periode.akhir_bulan(f"{th:04d}-{bl:02d}")
        tutup = akhir_bulan <= akhir and (pekan_tutup or akhir_bulan < akhir)
        absen_nama = {(e.get("id") or e.get("nama"))
                      for e in perkiraan.absen(semua, rows, th, bl, None, atur)}
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
    ada = {buku_kas.tanggal(r) for r in pengeluaran(di_antara(rows, mulai, akhir))}
    deret, kini, d = [], [], mulai
    while d <= akhir:
        if d in ada:
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
    rentang = f"Pekan: Senin {tgl(mulai)} – Minggu {tgl(minggu)} {minggu.year}"
    if not pekan_tutup:
        rentang += f" (sampai {HARI[akhir.weekday()]} {tgl(akhir)})"

    baris = [judul, rentang, ""]

    for deret in hari_kosong(rows, mulai, akhir):
        nama = ", ".join(f"{HARI[d.weekday()]} {d.day}" for d in deret)
        baris += [f"⚠️ Tidak ada catatan pada {nama} {BULAN[deret[-1].month]} — "
                  "angka pekan ini mungkin kurang", ""]
    tak = buku_kas.tak_terhitung(rows)
    if tak:
        baris += [f"⚠️ {len(tak)} transaksi tidak terhitung (tanggal tidak sah / tipe tidak "
                  "dikenal) — periksa bills.csv", ""]

    baris += bagian_kategori(keluar)
    baris += bagian_banding(keluar, keluar_lalu)
    baris += [""] + bagian_terbesar(keluar)

    saldo = buku_kas.saldo(rows, per=akhir)
    baris += [
        "",
        f"💰 Pemasukan pekan ini: {rupiah(total(pemasukan(di_antara(rows, mulai, akhir))))}",
        f"🏦 Saldo {'akhir Pekan' if pekan_tutup else 'per ' + tgl(akhir)}: {rupiah(saldo)}",
    ]
    baris += bagian_budget(rows, mulai, akhir, pekan_tutup)
    baris += [""] + bagian_kewajiban(rows)
    baris += bagian_perkiraan(rows, mulai, akhir, pekan_tutup)
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
    acuan = date.fromisoformat(a.pekan) if a.pekan else None
    try:
        mulai, akhir, tutup = periode.pilih_pekan(hari_ini, acuan, a.berjalan)
    except ValueError as e:
        ap.error(str(e))

    rows = buku_kas.muat()
    laporan = susun(rows, mulai, akhir, tutup)
    print(laporan)

    if not a.kirim:
        return 0
    tujuan = pengirim.tujuan_baku()
    if not tujuan:
        print("\n❌ Tidak ada tujuan pengiriman (channels.whatsapp.allowFrom kosong).")
        return 1
    semua_ok = True
    for kanal, ke in tujuan:
        ok, ket = pengirim.kirim(laporan, kanal, ke)
        print(f"\n{'✅ terkirim' if ok else '❌ GAGAL'} {kanal} -> {ke}" + (f": {ket}" if ket else ""))
        semua_ok = semua_ok and ok
    return 0 if semua_ok else 1


if __name__ == "__main__":
    sys.exit(main())
