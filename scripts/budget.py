"""Budget — batas belanja rutin sebulan (CONTEXT.md → Budget, ADR-0024).

Budget hanya menghitung Pengeluaran **rutin**: Transaksi yang jumlahnya di bawah ambang
(`pengeluaran_besar_mulai` di data/budget.json). Pengeluaran Besar tampil terpisah sebagai
"Di luar budget"; Selisih Rekonsiliasi juga tidak ikut dan tampil terpisah (ADR-0027). Pemasukan
tidak ikut: kecukupan uang dijawab Arus Kas Bulanan.

Satu perhitungan untuk pesan peringatan, "sisa budget", Laporan Mingguan, dan Laporan Bulanan.
Semua teks disusun di sini tanpa model, termasuk kalimat saran.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402
import periode  # noqa: E402
from tampilan import nama_bulan, rp  # noqa: E402

AMBANG_BAWAAN = 1_000_000
LEBAR = 20  # kolom label pesan


def pemakaian(rows, mulai: date, akhir: date, atur: dict) -> dict:
    """{batas, ambang, rutin, besar, transaksi_besar, rekonsiliasi, pengeluaran, pemasukan,
    per_kategori, persen}.

    `per_kategori` = Pengeluaran rutin per Kategori; `persen` = rutin dari batas (None bila batas 0).
    """
    batas = float(atur.get("budget_bulanan") or 0)
    ambang = int(atur.get("pengeluaran_besar_mulai") or AMBANG_BAWAAN)
    h = buku_kas.ringkas(rows, mulai, akhir)
    b = buku_kas.pengeluaran_besar(rows, mulai, akhir, ambang)
    rekon = h["per_kategori"].get(buku_kas.KATEGORI_REKONSILIASI, 0)
    per = {k: v - b["per_kategori"].get(k, 0) for k, v in h["per_kategori"].items()
           if k != buku_kas.KATEGORI_REKONSILIASI}
    rutin = h["pengeluaran"] - b["jumlah"] - rekon
    return {"batas": batas, "ambang": ambang, "rutin": rutin, "besar": b["jumlah"],
            "transaksi_besar": b["transaksi"], "rekonsiliasi": rekon, "pengeluaran": h["pengeluaran"],
            "pemasukan": h["pemasukan"], "per_kategori": {k: v for k, v in per.items() if v > 0},
            "persen": rutin / batas * 100 if batas > 0 else None}


def _di_luar(p: dict) -> str:
    return f"{rp(p['besar'])} ({p['transaksi_besar']} transaksi ≥ {rp(p['ambang'])})"


def baris_laporan(p: dict) -> list:
    """Dua baris untuk Laporan Bulanan: Budget rutin dan Di luar budget."""
    if p["batas"] <= 0:
        utama = f"💰 Budget: {rp(p['rutin'])} (budget belum diset)"
    else:
        utama = f"💰 Budget: {rp(p['rutin'])} dari {rp(p['batas'])} ({p['persen']:.0f}%)"
    hasil = [utama, f"📦 Di luar budget: {_di_luar(p)}"]
    if p.get("rekonsiliasi"):
        hasil.append(f"🔁 Selisih rekonsiliasi: {rp(p['rekonsiliasi'])} (tidak dihitung ke budget)")
    return hasil


def _bar(persen: float) -> str:
    isi = min(20, int(persen / 5))
    return "█" * isi + "░" * (20 - isi)


def _saran(p: dict, hari_ini: date, alert: float, tutup: bool = False) -> str:
    masih = p["batas"] - p["rutin"]
    if tutup and p["persen"] < 100:
        return f"💡 Saran: bulan sudah tutup di {p['persen']:.0f}% dari batas."
    if p["persen"] >= 100:
        kalimat = f"sudah lewat {rp(-masih)}."
        if p["per_kategori"]:
            k, v = max(p["per_kategori"].items(), key=lambda kv: kv[1])
            kalimat += f" Kategori terbesar bulan ini {k} ({rp(v)}, {v / p['rutin'] * 100:.0f}%)."
            if not tutup:
                kalimat += " Tunda belanja yang bisa ditunda ke bulan depan."
        return "💡 Saran: " + kalimat
    hari = periode.akhir_bulan(hari_ini.strftime("%Y-%m")).day - hari_ini.day + 1
    per_hari = rp(int(masih // hari))
    if p["persen"] < alert:
        return f"💡 Saran: masih aman. Sisa {hari} hari, rata-rata sebaiknya tidak lebih dari {per_hari} per hari."
    if hari == 1:
        return f"💡 Saran: sisa 1 hari, jadi belanja rutin hari ini sebaiknya tidak lebih dari {per_hari}."
    return f"💡 Saran: sisa {hari} hari, rata-rata sebaiknya tidak lebih dari {per_hari} per hari."


def pesan(rows, hari_ini: date, atur: dict, selalu: bool, bulan: str | None = None) -> str:
    """Pesan Budget untuk `bulan` ('YYYY-MM', bawaan bulan `hari_ini`).

    `selalu` False (cek malam, setelah pencatatan): "" kecuali persen sudah mencapai `alert_persen`;
    pada bulan yang sudah tutup (pencatatan mundur) hanya bila sudah lewat batas, karena sisa hari
    dan peringatan "mendekati" tak berarti lagi. True ("sisa budget" lewat chat): selalu menjawab.
    """
    sekarang = hari_ini.strftime("%Y-%m")
    bulan = bulan or sekarang
    tutup = bulan < sekarang
    p = pemakaian(rows, *periode.rentang_bulan(bulan), atur)
    if p["persen"] is None:
        return ("⚠️ Budget belum diset!\nKetik: set budget [nominal]\nContoh: set budget 3 juta"
                if selalu else "")
    alert = float(atur.get("alert_persen", 80))
    if p["persen"] >= 100:
        judul = "🚨 Lewat batas Budget"
    elif p["persen"] >= alert and not tutup:
        judul = "⚠️ Mendekati batas Budget"
    elif selalu:
        judul = "💰 Status Budget"
    else:
        return ""
    masih = p["batas"] - p["rutin"]
    baris_masih = (f"💚 {'Masih bisa:':<{LEBAR}}{rp(masih)}" if masih >= 0
                   else f"🔴 {'Lewat:':<{LEBAR}}{rp(-masih)}")
    arus = p["pemasukan"] - p["pengeluaran"]
    out = [f"{judul} — {nama_bulan(bulan)}{' (sudah tutup)' if tutup else ''}", "",
           f"📊 {'Batas rutin:':<{LEBAR}}{rp(p['batas'])}",
           f"💸 {'Terpakai (rutin):':<{LEBAR}}{rp(p['rutin'])} ({p['persen']:.0f}%)",
           baris_masih,
           f"📦 {'Di luar budget:':<{LEBAR}}{_di_luar(p)}", "",
           f"{_bar(p['persen'])}  {p['persen']:.0f}%", "",
           f"💰 Arus Kas Bulanan {nama_bulan(bulan).split()[0]}: {rp(arus)}",
           f"   (masuk {rp(p['pemasukan'])}, keluar {rp(p['pengeluaran'])})", "",
           _saran(p, hari_ini, alert, tutup)]
    if selalu:
        out += ["", "_Dihitung scripts/check-bills.py, tanpa model_"]
    return "\n".join(out)
