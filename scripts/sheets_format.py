"""Tampilan worksheet "Buku Kas" di Cermin (ADR-0026) dan pembacaan baliknya.

Mesin sinkron (sheets_sync) membandingkan Transaksi dalam **bentuk ternormal**: 12 kolom bills.csv
(`KOLOM`), tipe sudah berupa Arah, jumlah rupiah bulat. Modul ini satu-satunya yang tahu bentuk
tampilan (`KOLOM_TAMPIL`):

- Pemasukan / Pengeluaran / Transfer menggantikan `tipe` + `jumlah`; tepat satu terisi.
- Kategori tampil sebagai Label Kategori; label atau slug yang diketik dibaca balik jadi slug.
- Tanggal dikirim sebagai serial tanggal Sheets; dibaca dari serial, ISO, atau hari/bulan/tahun.
- Saldo Bersama per Item dihitung di sini dan diabaikan saat dibaca.

Aturan bakunya: baca_baris(tampil(r)) == baris_norm(r) untuk setiap baris yang bisa ditampilkan.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402

KOLOM = ["tanggal", "tipe", "kategori", "item", "jumlah", "catatan", "channel", "pencatat",
         "akun", "akun_tujuan", "waktu", "no_resi"]
KOLOM_TAMPIL = ["Tanggal", "Waktu", "No Resi", "Item", "Kategori", "Akun", "Akun Tujuan", "Pemasukan",
                "Pengeluaran", "Transfer", "Saldo Bersama", "Catatan", "Pencatat", "Asal"]
# kolom tampilan → kolom CSV untuk yang dipindah apa adanya
_TEKS = {"Waktu": "waktu", "No Resi": "no_resi", "Item": "item", "Akun": "akun",
         "Akun Tujuan": "akun_tujuan", "Catatan": "catatan", "Pencatat": "pencatat", "Asal": "channel"}
KOLOM_UANG = {"Pemasukan": "pemasukan", "Pengeluaran": "pengeluaran", "Transfer": "transfer"}
I_SALDO = KOLOM_TAMPIL.index("Saldo Bersama")
EPOCH_SERIAL = date(1899, 12, 30)  # serial tanggal Google Sheets
_HARI_BULAN = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
SATU_KOLOM_UANG = "isi tepat satu dari Pemasukan, Pengeluaran, Transfer"


def label_sah(label) -> tuple[dict, list]:
    """(peta slug → label yang dipakai, label kembar). Label harus unik supaya bisa dibaca balik ke
    tepat satu slug; label kembar tidak dipakai (slug-nya tampil apa adanya) dan dilaporkan."""
    if not isinstance(label, dict):
        return {}, []
    hitung: dict = {}
    for v in label.values():
        if isinstance(v, str) and v.strip():
            hitung[v.strip().casefold()] = hitung.get(v.strip().casefold(), 0) + 1
    sah = {k: v.strip() for k, v in label.items()
           if isinstance(v, str) and v.strip() and hitung[v.strip().casefold()] == 1}
    kembar = sorted({v.strip() for v in label.values()
                     if isinstance(v, str) and v.strip() and hitung[v.strip().casefold()] > 1})
    return sah, kembar


def label_balik(label: dict) -> dict:
    """Label (huruf kecil) → slug."""
    return {v.casefold(): k for k, v in label.items()}


def _teks(sel) -> str:
    if isinstance(sel, bool):
        return str(sel)
    if isinstance(sel, float) and sel.is_integer():
        return str(int(sel))
    return "" if sel is None else str(sel)


def kosong(baris: list) -> bool:
    """Baris tanpa isi selain kolom Saldo Bersama (yang diisi skrip)."""
    return not any(_teks(s).strip() for i, s in enumerate(baris) if i != I_SALDO)


# ── Keluar: CSV → tampilan ────────────────────────────────────────────────
def baris_norm(r: dict) -> list:
    """Satu baris CSV dalam bentuk ternormal: tipe = Arah (tipe tak dikenal apa adanya), jumlah bulat."""
    nilai = {k: (r.get(k) or "") for k in KOLOM}
    nilai["tipe"] = buku_kas.arah(r) or nilai["tipe"]
    nilai["jumlah"] = str(buku_kas.jumlah(r))
    return [nilai[k] for k in KOLOM]


def _kunci_urut(r: dict):
    tgl = buku_kas.tanggal(r)
    if tgl is None:
        return (1, r.get("tanggal") or "", "", "")
    return (0, tgl.isoformat(), (r.get("waktu") or "").strip(), r.get("no_resi") or "")


def urut(rows: list) -> list:
    """Kronologis, terlama di atas; Item satu Transaksi tetap berurutan (sort stabil)."""
    return sorted(rows, key=_kunci_urut)


def grid_norm(rows: list) -> list:
    return [list(KOLOM)] + [baris_norm(r) for r in urut(rows)]


def tampil(norm: list, saldo, label: dict) -> list:
    n = dict(zip(KOLOM, norm))
    baris = {k: n[v] for k, v in _TEKS.items()}
    try:
        baris["Tanggal"] = (date.fromisoformat(n["tanggal"].strip()) - EPOCH_SERIAL).days
    except ValueError:
        baris["Tanggal"] = n["tanggal"]
    baris["Kategori"] = label.get(n["kategori"], n["kategori"])
    for k, arah in KOLOM_UANG.items():
        baris[k] = int(n["jumlah"]) if n["tipe"] == arah else ""
    baris["Saldo Bersama"] = saldo
    return [baris[k] for k in KOLOM_TAMPIL]


def grid_tampil(rows: list, label: dict) -> list:
    """Worksheet "Buku Kas": header + satu baris per Item, dengan Saldo Bersama setelah tiap Item
    (aturan buku_kas.saldo: Saldo Awal menambah, Transfer dan baris tak terhitung tidak menggeser)."""
    grid, s = [list(KOLOM_TAMPIL)], 0
    for r in urut(rows):
        tgl, a = buku_kas.tanggal(r), buku_kas.arah(r)
        if tgl is not None and a in ("pemasukan", "pengeluaran"):
            s += buku_kas.jumlah(r) if buku_kas.saldo_awal(r) or a == "pemasukan" else -buku_kas.jumlah(r)
        grid.append(tampil(baris_norm(r), s if tgl is not None and a else "", label))
    return grid


# ── Masuk: tampilan → bentuk ternormal ────────────────────────────────────
def _baca_tanggal(sel) -> str | None:
    if isinstance(sel, (int, float)) and not isinstance(sel, bool):
        return (EPOCH_SERIAL + timedelta(days=int(sel))).isoformat()
    t = _teks(sel).strip()
    try:
        return date.fromisoformat(t).isoformat()
    except ValueError:
        pass
    m = _HARI_BULAN.fullmatch(t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def baca_baris(baris: list, balik: dict) -> tuple:
    """(baris ternormal, None) atau (None, alasan). Kolom Saldo Bersama diabaikan."""
    sel = list(baris) + [""] * (len(KOLOM_TAMPIL) - len(baris))
    t = dict(zip(KOLOM_TAMPIL, sel))
    n = {v: _teks(t[k]) for k, v in _TEKS.items()}
    tanggal = _baca_tanggal(t["Tanggal"])
    if tanggal is None:
        return None, f"tanggal tidak terbaca: {_teks(t['Tanggal'])!r} (tulis mis. 5/9/2026)"
    n["tanggal"] = tanggal
    terisi = [(arah, t[k]) for k, arah in KOLOM_UANG.items() if _teks(t[k]).strip()]
    if len(terisi) != 1:
        return None, SATU_KOLOM_UANG
    n["tipe"], jumlah = terisi[0]
    n["jumlah"] = _teks(jumlah).strip()
    kategori = _teks(t["Kategori"]).strip()
    n["kategori"] = balik.get(kategori.casefold(), kategori)
    return [n[k] for k in KOLOM], None


# ── Tata letak (dipasang klien Google) ────────────────────────────────────
def tata_buku(opsi_kategori: list) -> dict:
    """Worksheet "Buku Kas": kolom hanya-baca abu-abu dan dilindungi `warningOnly`, Kategori
    berdropdown (tidak ketat: slug yang diketik tetap diterima), Waktu dan Asal terlipat."""
    i = KOLOM_TAMPIL.index
    fmt = {k: "teks" for k in range(len(KOLOM_TAMPIL))}
    fmt[i("Tanggal")] = "tanggal"
    for k in ("Pemasukan", "Pengeluaran", "Transfer", "Saldo Bersama"):
        fmt[i(k)] = "rupiah"
    return {
        "baris_header": 0, "beku_kolom": i("Item") + 1, "format": fmt, "locale": LOCALE,
        "hanya_baca": [i("No Resi"), i("Saldo Bersama"), i("Asal")],
        "catatan": {
            i("No Resi"): "Diisi otomatis untuk baris baru. Tidak bisa diubah dari Sheets.",
            i("Saldo Bersama"): "Dihitung otomatis setiap sinkron; isian di sini ditimpa.",
            i("Asal"): "Diisi otomatis (whatsapp, sheets, ...). Tidak bisa diubah dari Sheets.",
            i("Pemasukan"): SATU_KOLOM_UANG[0].upper() + SATU_KOLOM_UANG[1:] + ".",
            i("Kategori"): "Pilih dari daftar; slug Inggris juga diterima.",
            i("Item"): "Barang + toko, mis. Susu UHT - Budiman Swalayan. Cara bayar di Catatan.",
        },
        "pilihan": {i("Kategori"): list(opsi_kategori)},
        "grup": [(i("Waktu"), i("Waktu") + 1), (i("Asal"), i("Asal") + 1)],
    }


LOCALE = "id_ID"
