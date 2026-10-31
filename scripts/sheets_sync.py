"""Sinkron Buku Kas ke Google Sheets (spec #20). Saat ini baru arah keluar (CSV → Sheets).

Buku Kas tetap satu-satunya sumber (ADR-0005). Sheets adalah tabel salinan: worksheet "Buku Kas"
(12 kolom persis bills.csv) dan "Ringkasan" (Arus Kas Bulan & Saldo per bulan, dihitung buku_kas,
bukan rumus Sheets — satu arti Saldo). Klien Sheets disuntikkan:

    klien.baca(nama_worksheet) -> list[list]      # grid; kosong = []
    klien.tulis(nama_worksheet, grid) -> None     # mengganti seluruh isi worksheet

Seluruh aturan hidup di sini; adaptor Google yang sungguhan hanya memenuhi dua metode itu.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402
import periode  # noqa: E402

SHEET_BUKU = "Buku Kas"
SHEET_RINGKASAN = "Ringkasan"
KOLOM = ["tanggal", "tipe", "kategori", "item", "jumlah", "catatan", "channel", "pencatat",
         "akun", "akun_tujuan", "waktu", "no_resi"]
KOLOM_RINGKASAN = ["Bulan", "Jumlah Transaksi", "Total Pemasukan", "Total Pengeluaran",
                   "Arus Kas Bulan", "Saldo Awal Tercatat", "Saldo Akhir"]


class SinkronDitolak(Exception):
    """Sinkron tidak dijalankan karena akan menebak mana yang benar."""


@dataclass
class Laporan:
    didorong: int = 0  # baris Transaksi yang ditulis ke Sheet pada sinkron ini
    # (no_resi, alasan) baris yang tampil di "Buku Kas" tetapi tidak ikut Ringkasan — tidak pernah hilang diam-diam
    tak_terhitung: list = field(default_factory=list)


def grid_buku(rows: list[dict]) -> list[list]:
    """Worksheet "Buku Kas": header + satu baris per Item, urutan CSV; jumlah sebagai angka."""
    grid = [list(KOLOM)]
    for r in rows:
        baris = [(r.get(k) or "") for k in KOLOM]
        baris[KOLOM.index("jumlah")] = buku_kas.jumlah(r)
        grid.append(baris)
    return grid


def grid_ringkasan(rows: list[dict]) -> list[list]:
    """Worksheet "Ringkasan": satu baris per bulan yang punya Transaksi terhitung."""
    tak = {id(r) for r, _ in buku_kas.tak_terhitung(rows)}
    per_bulan: dict[str, int] = {}
    for r in rows:
        if id(r) not in tak:
            bulan = buku_kas.tanggal(r).strftime("%Y-%m")
            per_bulan[bulan] = per_bulan.get(bulan, 0) + 1
    grid = [list(KOLOM_RINGKASAN)]
    for bulan in sorted(per_bulan):
        arus = buku_kas.arus_kas_bulan(rows, bulan)
        grid.append([
            bulan, per_bulan[bulan], arus["pemasukan"], arus["pengeluaran"],
            arus["pemasukan"] - arus["pengeluaran"], arus["saldo_awal"] or "",
            buku_kas.saldo(rows, per=periode.akhir_bulan(bulan)),
        ])
    return grid


def _norm(grid: list[list]) -> list[list[str]]:
    """Sel dibandingkan sebagai teks (Sheets tidak membedakan angka dan teks dengan tegas), dan
    sel kosong di ujung kanan tiap baris diabaikan karena Sheets memangkasnya saat dibaca."""
    hasil = []
    for baris in grid:
        sel = [str(c) for c in baris]
        while sel and sel[-1] == "":
            sel.pop()
        hasil.append(sel)
    return hasil


def _simpan_snapshot(path: Path, isi: dict) -> None:
    teks = json.dumps(isi, ensure_ascii=False, indent=1)
    if path.exists() and path.read_text(encoding="utf-8") == teks:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    sementara = path.with_name(path.name + ".tmp")
    sementara.write_text(teks, encoding="utf-8")
    os.replace(sementara, path)


def _berisi_data(grid: list[list]) -> bool:
    """Ada baris selain header? Sheet kosong atau hanya berisi header dianggap kosong."""
    return len(grid) > 1


def sinkron(bills_path: Path, klien, snapshot_path: Path, uji: bool = False,
            inisialisasi: bool = False) -> Laporan:
    """Salin Buku Kas ke Sheets. `uji` melapor tanpa menulis apa pun. Sheet yang sudah berisi data
    tetapi belum punya snapshot ditolak (SinkronDitolak) kecuali `inisialisasi`: CSV menang."""
    if not inisialisasi and not snapshot_path.exists() and _berisi_data(klien.baca(SHEET_BUKU)):
        raise SinkronDitolak(
            f"Worksheet '{SHEET_BUKU}' sudah berisi data tetapi belum pernah disinkronkan dari sini. "
            "Jalankan dengan inisialisasi untuk menimpanya dari bills.csv.")
    if not Path(bills_path).exists():
        raise SinkronDitolak(f"{bills_path} tidak ada; Sheet tidak ditimpa dengan tabel kosong.")
    rows = buku_kas.muat(bills_path)
    target = {SHEET_BUKU: grid_buku(rows), SHEET_RINGKASAN: grid_ringkasan(rows)}
    laporan = Laporan(tak_terhitung=[(r.get("no_resi") or "", alasan)
                                     for r, alasan in buku_kas.tak_terhitung(rows)])
    for nama, grid in target.items():
        if _norm(klien.baca(nama)) == _norm(grid):
            continue
        if not uji:
            klien.tulis(nama, grid)
        if nama == SHEET_BUKU:
            laporan.didorong = len(grid) - 1
    if not uji:
        _simpan_snapshot(snapshot_path,
                         {"buku_kas": target[SHEET_BUKU], "ringkasan": target[SHEET_RINGKASAN]})
    return laporan
