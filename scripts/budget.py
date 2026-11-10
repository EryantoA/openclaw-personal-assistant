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
    per_kategori, persen, kategori}.

    `per_kategori` = Pengeluaran rutin per Kategori; `persen` = rutin dari batas (None bila batas 0).
    `kategori` = Batas Kategori (ADR-0029), urut seperti `budget_kategori`:
    [{slug, label, rutin, batas, persen}].
    """
    batas = float(atur.get("budget_bulanan") or 0)
    ambang = int(atur.get("pengeluaran_besar_mulai") or AMBANG_BAWAAN)
    h = buku_kas.ringkas(rows, mulai, akhir)
    b = buku_kas.pengeluaran_besar(rows, mulai, akhir, ambang)
    rekon = h["per_kategori"].get(buku_kas.KATEGORI_REKONSILIASI, 0)
    per = {k: v - b["per_kategori"].get(k, 0) for k, v in h["per_kategori"].items()
           if k != buku_kas.KATEGORI_REKONSILIASI}
    rutin = h["pengeluaran"] - b["jumlah"] - rekon
    label = atur.get("label_kategori") or {}
    kategori = [{"slug": k, "label": label.get(k, k), "rutin": per.get(k, 0), "batas": int(v),
                 "persen": per.get(k, 0) / v * 100}
                for k, v in (atur.get("budget_kategori") or {}).items() if v and float(v) > 0]
    return {"kategori": kategori, "batas": batas, "ambang": ambang, "rutin": rutin, "besar": b["jumlah"],
            "transaksi_besar": b["transaksi"], "rekonsiliasi": rekon, "pengeluaran": h["pengeluaran"],
            "pemasukan": h["pemasukan"], "per_kategori": {k: v for k, v in per.items() if v > 0},
            "persen": rutin / batas * 100 if batas > 0 else None}


def _di_luar(p: dict) -> str:
    return f"{rp(p['besar'])} ({p['transaksi_besar']} transaksi ≥ {rp(p['ambang'])})"


def baris_laporan(p: dict) -> list:
    """Baris Laporan Bulanan: Budget rutin, Di luar budget, Selisih Rekonsiliasi bila ada, lalu satu
    baris per Batas Kategori."""
    if p["batas"] <= 0:
        utama = f"💰 Budget: {rp(p['rutin'])} (budget belum diset)"
    else:
        utama = f"💰 Budget: {rp(p['rutin'])} dari {rp(p['batas'])} ({p['persen']:.0f}%)"
    hasil = [utama, f"📦 Di luar budget: {_di_luar(p)}"]
    if p.get("rekonsiliasi"):
        hasil.append(f"🔁 Selisih rekonsiliasi: {rp(p['rekonsiliasi'])} (tidak dihitung ke budget)")
    hasil += [f"   • {k['label']}: {rp(k['rutin'])} dari {rp(k['batas'])} ({k['persen']:.0f}%)"
              for k in p.get("kategori", [])]
    return hasil


def _baris_kategori(k: dict, alert: float) -> str:
    tanda = "🚨" if k["persen"] >= 100 else "⚠️" if k["persen"] >= alert else "✅"
    sisa = k["batas"] - k["rutin"]
    ekor = f" · masih bisa {rp(sisa)}" if sisa > 0 else f" · lewat {rp(-sisa)}" if sisa < 0 else ""
    return f"{tanda} {k['label']}: {rp(k['rutin'])} dari {rp(k['batas'])} ({k['persen']:.0f}%){ekor}"


def _slug(teks: str, p: dict) -> str:
    """Slug atau label (huruf besar-kecil diabaikan) → slug Batas Kategori; selain itu apa adanya."""
    t = (teks or "").strip().casefold()
    return next((k["slug"] for k in p["kategori"] if t in (k["slug"].casefold(), k["label"].casefold())), t)


def _kategori_disebut(p: dict, alert: float, selalu: bool, tutup: bool, kategori) -> list:
    """Batas Kategori yang disebut: semua bila `selalu`; selain itu yang mencapai ambang (bulan tutup:
    hanya yang lewat), dan bila `kategori` diberikan, hanya kategori Transaksi itu."""
    if selalu:
        return p["kategori"]
    ambang = 100 if tutup else alert
    pilih = None if kategori is None else {_slug(k, p) for k in kategori}
    return [k for k in p["kategori"] if k["persen"] >= ambang and (pilih is None or k["slug"] in pilih)]


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


def pesan(rows, hari_ini: date, atur: dict, selalu: bool, bulan: str | None = None,
          kategori: list | None = None) -> str:
    """Pesan Budget untuk `bulan` ('YYYY-MM', bawaan bulan `hari_ini`).

    `selalu` False (cek malam, setelah pencatatan): "" kecuali persen sudah mencapai `alert_persen`;
    pada bulan yang sudah tutup (pencatatan mundur) hanya bila sudah lewat batas, karena sisa hari
    dan peringatan "mendekati" tak berarti lagi. True ("sisa budget" lewat chat): selalu menjawab.

    Batas Kategori (ADR-0029) disebut berdiri sendiri: total di bawah ambang tidak membungkam
    kategori yang sudah sampai ambang. `kategori` (slug/label Transaksi yang baru dicatat) membatasi
    peringatan ke kategori itu saja; tanpa `kategori` (cek malam) semua yang sampai ambang.
    """
    sekarang = hari_ini.strftime("%Y-%m")
    bulan = bulan or sekarang
    tutup = bulan < sekarang
    p = pemakaian(rows, *periode.rentang_bulan(bulan), atur)
    alert = float(atur.get("alert_persen", 80))
    disebut = _kategori_disebut(p, alert, selalu, tutup, kategori)
    blok_kategori = ["🏷️ Batas Kategori"] + [_baris_kategori(k, alert) for k in disebut] if disebut else []
    if p["persen"] is None:
        if selalu:
            return "\n\n".join(["⚠️ Budget belum diset!\nKetik: set budget [nominal]\nContoh: set budget 3 juta"]
                               + (["\n".join(blok_kategori)] if blok_kategori else []))
        judul = None
    elif p["persen"] >= 100:
        judul = "🚨 Lewat batas Budget"
    elif p["persen"] >= alert and not tutup:
        judul = "⚠️ Mendekati batas Budget"
    elif selalu:
        judul = "💰 Status Budget"
    else:
        judul = None
    nama = f"{nama_bulan(bulan)}{' (sudah tutup)' if tutup else ''}"
    if judul is None:
        if not disebut:
            return ""
        lewat = any(k["persen"] >= 100 for k in disebut)
        return "\n".join([f"{'🚨 Lewat' if lewat else '⚠️ Mendekati'} Batas Kategori — {nama}", "",
                          *[_baris_kategori(k, alert) for k in disebut]])
    masih = p["batas"] - p["rutin"]
    baris_masih = (f"💚 {'Masih bisa:':<{LEBAR}}{rp(masih)}" if masih >= 0
                   else f"🔴 {'Lewat:':<{LEBAR}}{rp(-masih)}")
    arus = p["pemasukan"] - p["pengeluaran"]
    out = [f"{judul} — {nama}", "",
           f"📊 {'Batas rutin:':<{LEBAR}}{rp(p['batas'])}",
           f"💸 {'Terpakai (rutin):':<{LEBAR}}{rp(p['rutin'])} ({p['persen']:.0f}%)",
           baris_masih,
           f"📦 {'Di luar budget:':<{LEBAR}}{_di_luar(p)}", "",
           f"{_bar(p['persen'])}  {p['persen']:.0f}%", ""]
    if blok_kategori:
        out += blok_kategori + [""]
    out += [f"💰 Arus Kas Bulanan {nama_bulan(bulan).split()[0]}: {rp(arus)}",
            f"   (masuk {rp(p['pemasukan'])}, keluar {rp(p['pengeluaran'])})", "",
            _saran(p, hari_ini, alert, tutup)]
    if selalu:
        out += ["", "_Dihitung scripts/check-bills.py, tanpa model_"]
    return "\n".join(out)
