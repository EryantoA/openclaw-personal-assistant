#!/usr/bin/env python3
"""
validasi.py — aturan satu baris transaksi, dipakai bersama oleh catat.py (tambah) dan buku.py
(ubah). Aturannya hanya didefinisikan di sini supaya baris yang diubah lolos cek yang sama
dengan baris yang baru dicatat.
"""

# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import contextlib
import fcntl
import json
import re
from datetime import date
from pathlib import Path

import resi

TIPE = {"pengeluaran", "pemasukan", "transfer"}


class Tolak(Exception):
    """Masukan tidak valid (exit 2)."""


def kategori_sah() -> set[str]:
    try:
        return set(json.loads(resi.BUDGET_JSON.read_text(encoding="utf-8"))["kategori_custom"])
    except Exception:
        return set()


def cek_baris(b: dict, sah: set[str], awalan: str = "", ubah: set | None = None) -> dict:
    """Validasi satu baris 12 kolom dan kembalikan salinan yang sudah dinormalisasi.

    `awalan` ("item 2: ") hanya disisipkan pada galat tingkat-item supaya pesan lama tetap sama.
    `ubah` (kumpulan nama kolom) membatasi cek pada kolom yang memang sedang diubah: baris lama
    yang sudah ada sebelum aturan ini (waktu kosong, kategori usang) tetap bisa dikoreksi di
    kolom lain. None = semua kolom (baris baru).
    """
    def perlu(*kolom):
        return ubah is None or any(k in ubah for k in kolom)

    for f in ("tanggal", "tipe", "channel", "pencatat"):
        if perlu(f) and not str(b.get(f) or "").strip():
            raise Tolak(f"field `{f}` wajib diisi")
    tanggal = str(b.get("tanggal") or "").strip()
    if perlu("tanggal"):
        try:
            date.fromisoformat(tanggal)
        except ValueError:
            raise Tolak(f"tanggal harus YYYY-MM-DD, dapat {tanggal!r}")
    tipe = str(b.get("tipe") or "").strip()
    if perlu("tipe") and tipe not in TIPE:
        raise Tolak(f"tipe harus salah satu {sorted(TIPE)}, dapat {tipe!r}")
    waktu = str(b.get("waktu") or "").strip()
    if perlu("waktu") and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", waktu):
        raise Tolak(f"waktu harus HH:MM, dapat {waktu!r}")
    akun = str(b.get("akun") or "").strip()
    akun_tujuan = str(b.get("akun_tujuan") or "").strip()
    if perlu("tipe", "akun", "akun_tujuan"):
        if akun_tujuan and tipe != "transfer":
            raise Tolak("akun_tujuan hanya untuk tipe=transfer")
        if tipe == "transfer" and not (akun and akun_tujuan):
            raise Tolak("tipe=transfer wajib mengisi akun (asal) dan akun_tujuan")

    kategori = str(b.get("kategori") or "").strip()
    if perlu("kategori", "tipe"):
        if kategori == "opening_balance":
            raise Tolak("kategori opening_balance tidak boleh dibuat (ADR-0008)")
        if tipe == "transfer" or kategori == "transfer":
            # Transfer punya kategorinya sendiri, di luar kategori_custom (SKILL.md → Akun & Transfer)
            if tipe != kategori:
                raise Tolak(f"{awalan}tipe=transfer wajib berkategori transfer, dan sebaliknya")
        elif sah and perlu("kategori") and kategori not in sah:
            raise Tolak(f"{awalan}kategori {kategori!r} tidak ada di budget.json kategori_custom")
    item = str(b.get("item") or "").strip()
    if perlu("item") and not item:
        raise Tolak(f"{awalan}`item` kosong")
    jumlah = resi.norm_total(b.get("jumlah"))
    if perlu("jumlah") and (not jumlah or int(jumlah) <= 0):
        raise Tolak(f"{awalan}jumlah harus angka rupiah > 0, dapat {b.get('jumlah')!r}")
    return {
        "tanggal": tanggal,
        "tipe": tipe,
        "kategori": kategori,
        "item": item,
        "jumlah": jumlah,
        "catatan": str(b.get("catatan") or "").strip(),
        "channel": str(b.get("channel") or "").strip(),
        "pencatat": resi.kanon_pembeli(b.get("pencatat")),
        "akun": akun,
        "akun_tujuan": akun_tujuan,
        "waktu": waktu,
        "no_resi": str(b.get("no_resi") or "").strip(),
    }


def cek_duplikat_lapis2(baris: list[dict], ada: list[dict], paksa: bool = False,
                        saran_paksa: bool = True) -> str | None:
    """Pesan DUPLICATE bila salah satu baris cocok (match_fields budget.json) dengan baris di
    `ada`, None bila lolos. `ada` tidak boleh memuat baris Transaksi yang sama."""
    cfg = resi.load_duplicate_config()
    if paksa or not cfg.get("aktif", True):
        return None
    fields = cfg["match_fields"]
    for b in baris:
        kunci = {f: resi.norm_field(f, b.get(f)) for f in fields}
        for row in ada:
            if all(resi.norm_field(f, row.get(f)) == kunci[f] for f in fields):
                saran = ("; ulangi dengan --paksa hanya bila pengguna menegaskan ini transaksi baru"
                         if saran_paksa else "")
                return (f"DUPLICATE {resi.row_summary(row)} | cocok pada: {', '.join(fields)} "
                        f"(aksi={cfg.get('aksi', 'tolak')}{saran})")
    return None


@contextlib.contextmanager
def kunci_berkas(path: Path):
    """Kunci eksklusif untuk satu CSV, lewat berkas `<nama>.lock` di sampingnya.

    Bukan mengunci CSV-nya sendiri: buku.py mengganti CSV dengan rename atomik, dan kunci pada
    inode lama tidak melindungi penulis yang menunggu (tulisannya jatuh ke berkas yang sudah
    tak terpakai). catat.py dan buku.py sama-sama lewat sini.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
