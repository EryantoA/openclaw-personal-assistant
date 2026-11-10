#!/usr/bin/env python3
"""Laporan Tahunan — bahan persiapan SPT & zakat untuk satu tahun, tanpa model (ADR-0033).

    python3 scripts/laporan-tahunan.py                   # tahun lalu, tampilkan saja
    python3 scripts/laporan-tahunan.py --tahun 2026      # tahun tertentu (tahun ini = berjalan)
    python3 scripts/laporan-tahunan.py --kirim           # cron 2 Februari: kirim tahun lalu

Bukan angka SPT: gaji di Buku Kas neto, sedangkan penghasilan bruto dan PPh terpotong hanya ada di
bukti potong kantor. Skrip ini tidak menghitung pajak dan tidak memutuskan zakat wajib atau tidak.
Tidak pernah menulis berkas apa pun, juga dengan --kirim. Aturan pajak & zakat yang dikutip:
docs/research/spt-tahunan-dan-zakat-penghasilan.md.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402
import pengaturan  # noqa: E402
import pengirim  # noqa: E402
import rekonsiliasi  # noqa: E402
from tampilan import rp  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
BILLS = DATA / "bills.csv"
AKUN = DATA / "akun.json"
REKON = DATA / "rekonsiliasi.csv"

KADAR_ZAKAT = 0.025  # PMA 52/2014 Pasal 26 jo. PMA 31/2019
BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def tgl(d: date, tahun: bool = True) -> str:
    return f"{d.day} {BLN[d.month - 1]}" + (f" {d.year}" if tahun else "")


def label(atur: dict, slug: str) -> str:
    return (atur.get("label_kategori") or {}).get(slug) or slug


# ── Bagian ────────────────────────────────────────────────────────────────
def cakupan(rows: list, tahun: int, akhir: date) -> list:
    """Kalimat cakupan data: catatan pertama dibanding 1 Januari (ADR-0033)."""
    semua = sorted(d for d in (buku_kas.tanggal(r) for r in rows) if d is not None)
    di_tahun = [d for d in semua if date(tahun, 1, 1) <= d <= akhir]
    if not di_tahun:
        return [f"🗓️ Tidak ada transaksi tercatat di {tahun}."]
    mulai = semua[0]
    if mulai > date(tahun, 1, 1):
        kemarin = date.fromordinal(mulai.toordinal() - 1)
        return [f"🗓️ Buku Kas mulai {tgl(mulai)}: 1 Jan–{tgl(kemarin)} tidak tercatat. "
                f"Angka setahun di bawah ini tidak lengkap."]
    return []


def pemasukan(rows: list, tahun: int, akhir: date, atur: dict) -> list:
    h = buku_kas.ringkas(rows, date(tahun, 1, 1), akhir)
    out = [f"📥 Pemasukan {tahun}: {rp(h['pemasukan'])}  (Saldo Awal dan Transfer tidak ikut)"]
    for k, v in sorted(h["pemasukan_per_kategori"].items(), key=lambda kv: -kv[1]):
        out.append(f"  {label(atur, k)}: {rp(v)}")
    out.append(f"📤 Pengeluaran {tahun}: {rp(h['pengeluaran'])}")

    lain = [r for r in rows
            if buku_kas.arah(r) == "pemasukan" and not buku_kas.saldo_awal(r)
            and not buku_kas.selisih_rekonsiliasi(r)
            and (r.get("kategori") or "").strip().lower() != "salary"
            and buku_kas.tanggal(r) is not None and date(tahun, 1, 1) <= buku_kas.tanggal(r) <= akhir]
    if lain:
        out += ["", "🔎 Pemasukan selain Gaji — pilah sendiri: honor (cari bukti potong BP21), "
                    "hadiah keluarga, uang arisan. Kategori di bawah apa adanya dari catatan."]
        for r in sorted(lain, key=buku_kas.tanggal):
            k = (r.get("kategori") or "").strip().lower() or "other"
            siapa = (r.get("pencatat") or "").strip()
            out.append(f"  {tgl(buku_kas.tanggal(r), False)}  {rp(buku_kas.jumlah(r))}  "
                       f"{(r.get('item') or '').strip()} ({k}{', ' + siapa if siapa else ''})")
    return out


def harta(rows: list, tahun: int, akhir: date, atur: dict, akun_cfg, catatan: list) -> list:
    out = [f"🏦 Saldo per {tgl(akhir)} — bahan \"kas dan setara kas\" (nilai nominal; "
           f"cocokkan dengan rekening koran):"]
    if rekonsiliasi.aktif(akun_cfg) and date.fromisoformat(akun_cfg["cutover"]) <= akhir:
        batas = datetime.combine(akhir, time(23, 59, 59))
        for a in akun_cfg["akun"]:
            dicek = [c for c in catatan if c.get("akun") == a["nama"]
                     and (c.get("titik") or "")[:10] <= akhir.isoformat()]
            ket = (f"dicek {tgl(datetime.fromisoformat(dicek[-1]['titik']).date())}"
                   if dicek else "belum pernah dicek")
            out.append(f"  {a['nama']}: {rp(rekonsiliasi.saldo_akun(rows, akun_cfg, a['id'], batas))}  ({ket})")
    else:
        out.append("  Saldo per Akun belum tersedia (fitur Akun belum aktif pada tanggal itu).")
    out.append(f"  Saldo Bersama: {rp(buku_kas.saldo(rows, per=akhir))}")

    ambang = int(atur.get("pengeluaran_besar_mulai") or 0)
    kandidat = []
    for items in buku_kas.transaksi_pengeluaran(rows, date(tahun, 1, 1), akhir).values():
        total = sum(buku_kas.jumlah(r) for r in items)
        perhiasan = any((r.get("kategori") or "").strip().lower() == "jewelry" for r in items)
        if (ambang and total >= ambang) or perhiasan:
            lebih = f" (+{len(items) - 1} item)" if len(items) > 1 else ""
            kandidat.append((buku_kas.tanggal(items[0]), total,
                             f"{(items[0].get('item') or '').strip()}{lebih}"))
    if kandidat:
        out += ["", "🧾 Kandidat harta baru — cek (harta dicatat dengan harga perolehan): "
                    "Pengeluaran Besar dan perhiasan"]
        for d, total, nama in sorted(kandidat):
            out.append(f"  {tgl(d, False)}  {rp(total)}  {nama}")
    out.append("Utang/cicilan tidak dicatat Buku Kas — cek sendiri saldo per 31 Des dari pemberi pinjaman.")
    return out


def zakat(rows: list, tahun: int, akhir: date, atur: dict) -> list:
    h = buku_kas.ringkas(rows, date(tahun, 1, 1), akhir)
    gaji = h["pemasukan_per_kategori"].get("salary", 0)
    out = ["🕌 Zakat penghasilan"]
    nisab = (atur.get("nisab_zakat_tahunan") or {}).get(str(tahun))
    if nisab:
        nisab = int(nisab)
        posisi = "di atas nisab" if gaji >= nisab else "di bawah nisab"
        out += [f"  Nisab {tahun}: {rp(nisab)}/tahun ({rp(round(nisab / 12))}/bulan) · kadar 2,5%",
                f"  Gaji tercatat: {rp(gaji)} — {posisi}"]
    else:
        out += [f"  Nisab {tahun} belum diisi (nisab_zakat_tahunan di data/budget.json, dari SK BAZNAS "
                f"tahun itu) · kadar 2,5%",
                f"  Gaji tercatat: {rp(gaji)}"]
    out += [f"  2,5% × gaji tercatat: {rp(round(gaji * KADAR_ZAKAT))} — batas bawah. Gaji di Buku Kas neto "
            f"(keluarga); BAZNAS menghitung dari gaji bruto di bukti potong, dan nisab berlaku per orang.",
            f"  Zakat tercatat dibayar {tahun}: {rp(h['per_kategori'].get('zakat', 0))} (kategori zakat). "
            f"Infak/donasi {rp(h['per_kategori'].get('donation', 0))} tidak dihitung sebagai zakat."]
    return out


def dokumen(tahun: int) -> list:
    t = tahun + 1
    return [f"📎 Untuk SPT {tahun} (lapor paling lambat 31 Mar {t}):",
            f"  • Bukti potong BPA1 (dulu 1721-A1) dari tiap kantor — paling lambat 31 Jan {t}, cek di Coretax",
            "  • Bukti potong honor (BP21) bila ada",
            "  • Bukti setor zakat dari BAZNAS/LAZ resmi (pengurang penghasilan); zakat lewat potongan gaji "
            "sudah ada di BPA1",
            "  • Rekening koran per 31 Des tiap rekening; data cicilan/pinjaman"]


# ── Menyusun ──────────────────────────────────────────────────────────────
def susun(tahun: int, rows: list, atur: dict, akun_cfg, catatan: list, berjalan_per: date | None = None) -> str:
    akhir = berjalan_per or date(tahun, 12, 31)
    judul = f"📒 *LAPORAN TAHUNAN {tahun}*"
    if berjalan_per:
        judul += f" _(berjalan, per {tgl(berjalan_per, False)})_"
    out = [judul, "_Bahan persiapan SPT & zakat — bukan angka SPT. Keputusan tetap di tangan Anda._", ""]
    out += cakupan(rows, tahun, akhir)
    out += [""] + pemasukan(rows, tahun, akhir, atur)
    out += [""] + harta(rows, tahun, akhir, atur, akun_cfg, catatan)
    out += [""] + zakat(rows, tahun, akhir, atur)
    out += [""] + dokumen(tahun)
    tak = buku_kas.tak_terhitung(rows)
    if tak:
        out += ["", f"⚠️ {len(tak)} transaksi tidak terhitung (tanggal tidak sah / tipe tidak dikenal) — "
                    f"periksa bills.csv."]
    out += ["", "_Dihitung scripts/laporan-tahunan.py, tanpa model. Bukan nasihat pajak._"]
    return "\n".join(out)


# ── Mengirim ──────────────────────────────────────────────────────────────
# Dirujuk lewat nama modul ini supaya tes bisa menggantinya tanpa mengirim sungguhan.
tujuan_baku = pengirim.tujuan_baku
kirim = pengirim.kirim


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Laporan Tahunan, tanpa model (ADR-0033)")
    ap.add_argument("--tahun", type=int, metavar="YYYY", help="tahun yang dilaporkan (bawaan: tahun lalu)")
    ap.add_argument("--kirim", action="store_true", help="kirim ke tujuan (cron 2 Februari)")
    ap.add_argument("--ke", action="append", metavar="KANAL:TUJUAN",
                    help="tujuan, bisa diulang (bawaan: tujuan Laporan Bulanan)")
    ap.add_argument("--hari-ini", metavar="YYYY-MM-DD", help="anggap hari ini tanggal segini (uji)")
    a = ap.parse_args(argv)

    try:
        hari_ini = date.fromisoformat(a.hari_ini) if a.hari_ini else date.today()
    except ValueError:
        ap.error(f"--hari-ini tidak valid: {a.hari_ini}")
    tahun = a.tahun or hari_ini.year - 1
    if tahun > hari_ini.year:
        ap.error(f"{tahun} belum dimulai")
    berjalan = tahun == hari_ini.year

    pesan = susun(tahun, buku_kas.muat(BILLS), pengaturan.muat(), rekonsiliasi.muat_akun(AKUN),
                  rekonsiliasi.muat_catatan(REKON), hari_ini if berjalan else None)
    print(pesan)
    if not a.kirim:
        return 0
    if berjalan:
        print("\n❌ Tahun berjalan tidak dikirim sebagai Laporan Tahunan — angkanya belum final.",
              file=sys.stderr)
        return 2

    tujuan = [tuple(x.split(":", 1)) for x in a.ke] if a.ke else tujuan_baku()
    if not tujuan:
        print("\n❌ Tidak ada tujuan pengiriman.", file=sys.stderr)
        return 2
    hasil = pengirim.kirim_ke_semua(pesan, tujuan, kirim)
    gagal = [kanal for kanal, _, ok, _ in hasil if not ok]
    if gagal:
        print(f"Laporan Tahunan gagal terkirim ke: {', '.join(gagal)}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
