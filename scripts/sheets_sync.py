"""Sinkron Buku Kas ke Google Sheets (spec #20). Dua arah: perubahan di Sheets masuk ke CSV
lewat jalan tulis resmi (buku.py), lalu CSV disalin kembali ke Sheets.

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
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku  # noqa: E402
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
    diterima: list = field(default_factory=list)    # (no_resi, item_ke, [kolom]) edit Sheet yang masuk ke CSV
    ditolak: list = field(default_factory=list)     # (no_resi, item_ke, alasan) edit Sheet yang dikembalikan
    dipulihkan: list = field(default_factory=list)  # (no_resi, item_ke) baris yang hilang dari Sheet
    peringatan: list = field(default_factory=list)  # dari buku.py, mis. bulan yang sudah dilaporkan (Koreksi)


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
        sel = [str(int(c)) if isinstance(c, float) and c.is_integer() else str(c) for c in baris]
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


# ── Arah masuk: Sheets → CSV ──────────────────────────────────────────────
OLEH = "sheets"  # Sheets tidak memberi tahu siapa pengubahnya; Jejak Perubahan mencatat asalnya saja


def _indeks(grid: list[list]) -> dict:
    """Baris tiap Item menurut kuncinya: (No Resi, nomor Item) — sama dengan penunjuk buku.py.
    Baris tanpa No Resi tidak bisa ditunjuk; kuncinya ("", urutan baris)."""
    hasil, cacah = {}, {}
    for i, baris in enumerate(_norm(grid)[1:], start=1):
        sel = baris + [""] * (len(KOLOM) - len(baris))
        if not any(sel):
            continue
        resi_ = sel[KOLOM.index("no_resi")]
        if resi_:
            cacah[resi_] = cacah.get(resi_, 0) + 1
            hasil[(resi_, cacah[resi_])] = sel
        else:
            hasil[("", i)] = sel
    return hasil


def _jalankan_ubah(skema, req: dict, uji: bool):
    """(kode, pesan) dari buku.jalankan. Menulis butuh sidik dari pemanggilan --uji yang sama."""
    kode, pesan = buku.jalankan(skema, "ubah", req, uji=True)
    if uji or kode != 0:
        return kode, pesan
    sidik = re.search(r"sidik (\w+)", pesan).group(1)
    return buku.jalankan(skema, "ubah", {**req, "sidik": sidik})


def _alasan(pesan: str) -> str:
    return re.sub(r"^ERROR ", "", pesan.splitlines()[0])


def _terapkan_masuk(bills_path: Path, klien, snapshot: dict, uji: bool, laporan: Laporan) -> None:
    """Diff tiga arah per baris: snapshot (dasar) vs Sheet sekarang vs CSV sekarang."""
    dasar = _indeks(snapshot["buku_kas"])
    sheet = _indeks(klien.baca(SHEET_BUKU))
    csv_ = _indeks(grid_buku(buku_kas.muat(bills_path)))
    skema = replace(buku.skema_bills(), path=lambda: Path(bills_path))
    tx_level = skema.tingkat_transaksi

    for kunci, baris_dasar in dasar.items():
        if kunci not in sheet:
            if kunci in csv_:
                laporan.dipulihkan.append(kunci)
            continue
        berubah = [c for i, c in enumerate(KOLOM) if sheet[kunci][i] != baris_dasar[i]]
        if not berubah:
            continue
        no_resi, item_ke = kunci
        if kunci not in csv_:
            laporan.ditolak.append((no_resi, item_ke, "Transaksi ini sudah dihapus dari Buku Kas"))
            continue
        if csv_[kunci] != baris_dasar:
            if all(sheet[kunci][KOLOM.index(c)] == csv_[kunci][KOLOM.index(c)] for c in berubah):
                continue  # kedua sisi sudah sepakat
            laporan.ditolak.append((no_resi, item_ke, "konflik: baris ini juga berubah di Buku Kas; "
                                    "nilai Buku Kas yang dipakai"))
            continue
        if not no_resi:
            laporan.ditolak.append((no_resi, item_ke, "baris tanpa no_resi tidak bisa ditunjuk"))
            continue
        nilai = {c: sheet[kunci][KOLOM.index(c)] for c in berubah}
        banyak = sum(1 for k in csv_ if k[0] == no_resi) > 1
        if banyak:
            permintaan = [{"set": {c: v for c, v in nilai.items() if c in tx_level}},
                          {"set": {c: v for c, v in nilai.items() if c not in tx_level},
                           "item_ke": item_ke}]
        else:
            permintaan = [{"set": nilai}]
        permintaan = [{"no_resi": no_resi, "oleh": OLEH, **r} for r in permintaan if r["set"]]

        # Uji semuanya dulu: satu baris masuk seluruhnya atau ditolak seluruhnya.
        gagal = next((m for k, m in (_jalankan_ubah(skema, r, True) for r in permintaan) if k != 0), None)
        if gagal:
            laporan.ditolak.append((no_resi, item_ke, _alasan(gagal)))
            continue
        for r in permintaan:
            kode, pesan = _jalankan_ubah(skema, r, uji)
            laporan.peringatan += [b for b in pesan.splitlines() if b.startswith("⚠️")]
            if kode != 0:
                laporan.ditolak.append((no_resi, item_ke, _alasan(pesan)))
                break
        else:
            laporan.diterima.append((no_resi, item_ke, berubah))
            if not uji:  # baris lain dari struk yang sama harus melihat CSV yang sudah berubah
                csv_ = _indeks(grid_buku(buku_kas.muat(bills_path)))

    for kunci in sheet.keys() - dasar.keys():
        if kunci not in csv_:
            laporan.ditolak.append((kunci[0], kunci[1], "baris baru dari Sheets belum didukung"))


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
    laporan = Laporan()
    if not inisialisasi and snapshot_path.exists():
        _terapkan_masuk(bills_path, klien, json.loads(snapshot_path.read_text(encoding="utf-8")),
                        uji, laporan)
    rows = buku_kas.muat(bills_path)
    target = {SHEET_BUKU: grid_buku(rows), SHEET_RINGKASAN: grid_ringkasan(rows)}
    laporan.tak_terhitung = [(r.get("no_resi") or "", alasan)
                             for r, alasan in buku_kas.tak_terhitung(rows)]
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
