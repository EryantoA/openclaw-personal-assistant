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
_JUMLAH_SAH = re.compile(r"(?:Rp\s*)?(?:\d+|\d{1,3}(?:[.,]\d{3})+)")
_I_RESI = KOLOM.index("no_resi")


def _struk(grid: list[list]) -> dict:
    """Baris Sheet dikelompokkan per Transaksi (No Resi), urutan Item dipertahankan. Baris tanpa
    No Resi tidak bisa ditunjuk; ia dikelompokkan menurut isinya, jadi diurutkan ulang pun tetap
    sama. Mencocokkan per kelompok, bukan per nomor urut baris: menghapus satu Item tidak boleh
    menggeser Item lain menjadi 'Item yang diedit'."""
    hasil = {}
    for baris in _norm(grid)[1:]:
        sel = baris + [""] * (len(KOLOM) - len(baris))
        if any(sel):
            hasil.setdefault(sel[_I_RESI] or "\0" + "\x1f".join(sel), []).append(sel)
    return hasil


def _resi_dari(id_: str) -> str:
    return "" if id_.startswith("\0") else id_


def _jalankan_ubah(skema, req: dict, uji: bool):
    """(kode, pesan) dari buku.jalankan. Menulis butuh sidik dari pemanggilan --uji yang sama."""
    kode, pesan = buku.jalankan(skema, "ubah", req, uji=True)
    if uji or kode != 0:
        return kode, pesan
    sidik = re.search(r"sidik (\w+)", pesan).group(1)
    return buku.jalankan(skema, "ubah", {**req, "sidik": sidik})


def _alasan(pesan: str) -> str:
    return re.sub(r"^ERROR ", "", pesan.splitlines()[0])


def _permintaan_ubah(skema, no_resi: str, item_ke: int, nilai: dict, banyak: bool) -> list:
    """Satu Transaksi satu Item: satu permintaan. Banyak Item: kolom tingkat Transaksi (berlaku
    untuk semua Item) dan kolom Item (butuh item_ke) dipisah, karena buku.py menolak campurannya."""
    if banyak:
        bagian = [{"set": {c: v for c, v in nilai.items() if c in skema.tingkat_transaksi}},
                  {"set": {c: v for c, v in nilai.items() if c not in skema.tingkat_transaksi},
                   "item_ke": item_ke}]
    else:
        bagian = [{"set": nilai}]
    return [{"no_resi": no_resi, "oleh": OLEH, **b} for b in bagian if b["set"]]


def _terapkan_baris(skema, no_resi: str, item_ke: int, nilai: dict, banyak: bool, uji: bool,
                    laporan: Laporan, terapan: set) -> None:
    """Satu baris masuk seluruhnya atau ditolak seluruhnya (diuji dulu sebelum satu pun ditulis)."""
    nilai = {c: v for c, v in nilai.items()
             if (no_resi, c, v) not in terapan or c not in skema.tingkat_transaksi}
    if not nilai:
        return  # Item lain dari struk yang sama sudah membawa perubahan tingkat Transaksi ini
    if "jumlah" in nilai and not _JUMLAH_SAH.fullmatch(nilai["jumlah"].strip()):
        laporan.ditolak.append((no_resi, item_ke, f"jumlah harus bilangan bulat rupiah, dapat {nilai['jumlah']!r}"))
        return
    permintaan = _permintaan_ubah(skema, no_resi, item_ke, nilai, banyak)
    gagal = next((m for k, m in (_jalankan_ubah(skema, r, True) for r in permintaan) if k != 0), None)
    if gagal:
        laporan.ditolak.append((no_resi, item_ke, _alasan(gagal)))
        return
    for r in permintaan:
        kode, pesan = _jalankan_ubah(skema, r, uji)
        laporan.peringatan += [b for b in pesan.splitlines() if b.startswith("⚠️")]
        if kode != 0:
            laporan.ditolak.append((no_resi, item_ke, _alasan(pesan)))
            return
    laporan.diterima.append((no_resi, item_ke, list(nilai)))
    terapan.update((no_resi, c, v) for c, v in nilai.items())


def _no_resi_diubah(dasar: dict, sheet: dict, laporan: Laporan) -> set:
    """No Resi terkunci. Mengedit selnya membuat baris tampak hilang sekaligus baru; pasangkan
    keduanya (isi lain sama persis) supaya alasannya jujur. Mengembalikan baris yang sudah
    dijelaskan, sebagai (id, nomor) di dasar dan (id, nomor) di sheet."""
    hilang = {}
    for id_, d in dasar.items():
        if id_ not in sheet and not id_.startswith("\0"):
            for i, sel in enumerate(d):
                hilang[tuple(sel[:_I_RESI] + sel[_I_RESI + 1:])] = (id_, i)
    dijelaskan = set()
    for id_, s in sheet.items():
        if id_ in dasar or id_.startswith("\0"):
            continue
        for i, sel in enumerate(s):
            lama = hilang.pop(tuple(sel[:_I_RESI] + sel[_I_RESI + 1:]), None)
            if lama:
                laporan.ditolak.append((lama[0], lama[1] + 1,
                                        "kolom `no_resi` terkunci; dikembalikan ke nilai Buku Kas"))
                dijelaskan |= {("lama",) + lama, ("baru", id_, i)}
    return dijelaskan


def _terapkan_masuk(bills_path: Path, klien, snapshot: dict, uji: bool, laporan: Laporan) -> None:
    """Diff tiga arah per Transaksi: snapshot (dasar) vs Sheet sekarang vs CSV sekarang."""
    dasar, sheet = _struk(snapshot["buku_kas"]), _struk(klien.baca(SHEET_BUKU))
    dari_csv = _struk(grid_buku(buku_kas.muat(bills_path)))
    skema = replace(buku.skema_bills(), path=lambda: Path(bills_path))
    dijelaskan = _no_resi_diubah(dasar, sheet, laporan)
    terapan = set()

    for id_, d in dasar.items():
        s, c, no_resi = sheet.get(id_, []), dari_csv.get(id_, []), _resi_dari(id_)
        if s == d:
            continue
        if len(s) != len(d):  # baris dihapus (atau ditambah) di Sheet: tidak ada yang diedit
            sisa = list(s)
            for i, sel in enumerate(d):
                if sel in sisa:
                    sisa.remove(sel)
                elif i < len(c) and ("lama", id_, i) not in dijelaskan:
                    laporan.dipulihkan.append((no_resi, i + 1))
            if sisa:
                laporan.ditolak.append((no_resi, 1, "jumlah baris Transaksi ini berubah di Sheets; "
                                        "edit pada Transaksi ini tidak diterapkan"))
            continue
        if sorted(s) == sorted(d):
            continue  # hanya diurutkan ulang
        for i, (sel, awal) in enumerate(zip(s, d)):
            if sel == awal:
                continue
            berubah = [k for k, (x, y) in enumerate(zip(sel, awal)) if x != y]
            if i >= len(c):
                laporan.ditolak.append((no_resi, i + 1, "Transaksi ini sudah dihapus dari Buku Kas"))
            elif c[i] != awal:
                if not all(sel[k] == c[i][k] for k in berubah):
                    laporan.ditolak.append((no_resi, i + 1, "konflik: baris ini juga berubah di "
                                            "Buku Kas; nilai Buku Kas yang dipakai"))
            else:
                _terapkan_baris(skema, no_resi, i + 1, {KOLOM[k]: sel[k] for k in berubah},
                                len(c) > 1, uji, laporan, terapan)

    for id_, s in sheet.items():
        if id_ in dasar:
            continue
        for i, sel in enumerate(s):
            if ("baru", id_, i) in dijelaskan or id_ in dari_csv:
                continue
            laporan.ditolak.append((_resi_dari(id_), i + 1, "baris tanpa no_resi tidak bisa ditunjuk "
                                    "atau diubah dari Sheets" if id_.startswith("\0")
                                    else "baris baru dari Sheets belum didukung"))


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
