"""Sinkron Buku Kas ke Google Sheets (spec #20). Dua arah: perubahan di Sheets masuk ke CSV
lewat jalan tulis resmi (buku.py untuk ubah, catat.py untuk baris baru), lalu CSV disalin kembali ke Sheets.

Buku Kas tetap satu-satunya sumber (ADR-0005). Sheets adalah tabel salinan: worksheet "Buku Kas"
(12 kolom persis bills.csv) dan "Ringkasan" (Arus Kas Bulan & Saldo per bulan, dihitung buku_kas,
bukan rumus Sheets — satu arti Saldo). Klien Sheets disuntikkan:

    klien.baca(nama_worksheet) -> list[list]      # grid; kosong = []
    klien.tulis(nama_worksheet, grid) -> None     # mengganti seluruh isi worksheet

Seluruh aturan hidup di sini; adaptor Google yang sungguhan hanya memenuhi dua metode itu.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku  # noqa: E402
import buku_kas  # noqa: E402
import catat  # noqa: E402
import periode  # noqa: E402
import resi  # noqa: E402
from validasi import kunci_berkas  # noqa: E402

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
    dilewati: bool = False  # sinkron lain masih berjalan; tidak ada yang dikerjakan
    # Sheet diedit di antara pembacaan awal dan penulisan akhir: tidak ada yang ditimpa dan snapshot
    # tidak maju, sehingga edit itu ditangkap sinkron berikutnya.
    berubah_saat_sinkron: bool = False
    didorong: int = 0  # baris Transaksi yang ditulis ke Sheet pada sinkron ini
    # (no_resi, alasan) baris yang tampil di "Buku Kas" tetapi tidak ikut Ringkasan — tidak pernah hilang diam-diam
    tak_terhitung: list = field(default_factory=list)
    ditambah: list = field(default_factory=list)    # No Resi Transaksi baru yang dibuat dari baris baru Sheet
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


def _tulis_atomik(path: Path, teks: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sementara = path.with_name(path.name + ".tmp")
    sementara.write_text(teks, encoding="utf-8")
    os.replace(sementara, path)


def _simpan_snapshot(path: Path, isi: dict) -> None:
    teks = json.dumps(isi, ensure_ascii=False, indent=1)
    if not (path.exists() and path.read_text(encoding="utf-8") == teks):
        _tulis_atomik(path, teks)


# ── Arah masuk: Sheets → CSV ──────────────────────────────────────────────
OLEH = "sheets"  # Sheets tidak memberi tahu siapa pengubahnya; Jejak Perubahan mencatat asalnya saja
ASAL = "sheets"  # Asal baris yang dibuat dari Sheets (nilai kolom `channel`)
TINGKAT_TRANSAKSI = ("tanggal", "tipe", "pencatat", "waktu", "akun", "akun_tujuan")
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
    for n, r in enumerate(permintaan):
        kode, pesan = _jalankan_ubah(skema, r, uji)
        laporan.peringatan += [b for b in pesan.splitlines() if b.startswith("⚠️")]
        if kode != 0:  # uji tadi memakai keadaan sebelum permintaan pertama; yang kedua bisa gagal
            sudah = ", ".join(c for x in permintaan[:n] for c in x["set"])
            laporan.ditolak.append((no_resi, item_ke, (f"sebagian sudah masuk ({sudah}); " if n else "")
                                    + _alasan(pesan)))
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


class _Jurnal:
    """Baris baru yang sudah dibuatkan No Resi-nya, dicatat SEBELUM catat.catat menulis CSV.

    Tanpa ini, sinkron yang gagal menulis Sheet sesudah catat berhasil akan melihat baris yang sama
    lagi (Sheet belum bernomor, snapshot lama) dan membuat Transaksi kedua; Lapis 2 tidak
    menangkapnya karena waktu kosong berarti jam sekarang. Dengan jurnal, ulangannya memakai No
    Resi yang sama dan jatuh ke Lapis 1. Dikosongkan setelah snapshot tertulis."""

    def __init__(self, path: Path, aktif: bool):
        self.path, self.aktif = path, aktif
        try:
            isi = json.loads(path.read_text(encoding="utf-8"))
            self.isi = isi if isinstance(isi, dict) else {}
        except (OSError, ValueError):
            self.isi = {}

    def get(self, kunci: str):
        return self.isi.get(kunci)

    def simpan(self, kunci: str, no_resi: str) -> None:
        self.isi[kunci] = no_resi
        if self.aktif:
            _tulis_atomik(self.path, json.dumps(self.isi, ensure_ascii=False))

    def hapus(self, kunci: str) -> None:
        if self.isi.pop(kunci, None) is not None and self.aktif:
            _tulis_atomik(self.path, json.dumps(self.isi, ensure_ascii=False))

    def kosongkan(self) -> None:
        self.isi = {}
        if self.aktif and self.path.exists():
            self.path.unlink()


def _gagal_baru(laporan: Laporan, no_resi: str, baris: list, alasan: str) -> None:
    """Baris baru yang ditolak hilang dari Sheet pada penulisan ulang, jadi isinya ikut dilaporkan."""
    isi = "; ".join(f"{b[KOLOM.index('tanggal')]} {b[KOLOM.index('item')]} {b[KOLOM.index('jumlah')]}"
                    for b in baris)
    laporan.ditolak.append((no_resi, 1, f"{alasan} — baris: {isi}"))


def _buat_transaksi(bills_path: Path, no_resi: str, baris: list, kunci: str, uji: bool,
                    laporan: Laporan, jurnal: _Jurnal) -> None:
    """Baris baru ber-No Resi sama = satu Transaksi multi-Item; tanpa No Resi = satu Transaksi
    sendiri. Ditulis lewat catat.catat (validasi, Duplikat Lapis 1 & 2, No Resi `TRX-…`)."""
    for k in TINGKAT_TRANSAKSI:
        if len({b[KOLOM.index(k)] for b in baris}) > 1:
            return _gagal_baru(laporan, no_resi, baris,
                               f"kolom `{k}` harus sama untuk semua baris Transaksi {no_resi}")
    for b in baris:  # validasi.cek_baris membaca "88500.5" sebagai 885005, jadi desimal dicegat di sini
        jumlah = b[KOLOM.index("jumlah")]
        if not _JUMLAH_SAH.fullmatch(jumlah.strip()):
            return _gagal_baru(laporan, no_resi, baris, f"jumlah harus bilangan bulat rupiah, dapat {jumlah!r}")
    pertama = baris[0]
    tx = {k: pertama[KOLOM.index(k)] for k in TINGKAT_TRANSAKSI}
    tx["channel"] = ASAL
    tx["items"] = [{k: b[KOLOM.index(k)] for k in ("kategori", "item", "jumlah", "catatan")} for b in baris]

    pernah = jurnal.get(kunci)
    pakai = no_resi or pernah
    if not pakai:
        try:  # No Resi dibuat di sini (bukan di catat) supaya bisa dijurnalkan sebelum CSV ditulis
            pakai = resi.gen_resi(buku_kas.muat(bills_path), date.fromisoformat(tx["tanggal"].strip()))
        except ValueError:
            pakai = ""  # tanggal tidak sah: biarkan catat menolaknya dengan pesannya sendiri
    if pakai:
        tx["no_resi"] = pakai
        if not uji and not pernah:
            jurnal.simpan(kunci, pakai)
    kode, pesan = catat.catat(tx, uji=uji)
    if kode == 1 and pernah and any(r.get("no_resi") == pakai for r in buku_kas.muat(bills_path)):
        kode = 0  # sudah dibuat oleh sinkron sebelumnya yang gagal sebelum sempat menulis Sheet
    if kode != 0:
        jurnal.hapus(kunci)  # tidak ada yang dibuat; entri basi bisa menelan baris lain nanti
        return _gagal_baru(laporan, no_resi, baris, _alasan(pesan))
    laporan.ditambah.append(pakai or re.search(r"no_resi (\S+)", pesan).group(1))


def _tambah_baris_baru(bills_path: Path, dasar: dict, sheet: dict, dari_csv: dict, dijelaskan: set,
                       uji: bool, laporan: Laporan, jurnal: _Jurnal) -> None:
    # Baris lama tanpa No Resi yang diedit tampak seperti satu baris hilang + satu baris baru.
    # Selama ada yang hilang, baris baru tanpa No Resi tidak dibuat: jangan menggandakan suntingan.
    lama_hilang = sum(max(0, len(d) - len(sheet.get(i, []))) for i, d in dasar.items() if i.startswith("\0"))
    for id_, s in sheet.items():
        if id_ in dasar:
            continue
        no_resi = _resi_dari(id_)
        if no_resi:
            baris = [sel for i, sel in enumerate(s) if ("baru", id_, i) not in dijelaskan]
            if not baris:
                continue
            kunci = f"resi:{no_resi}"
            if id_ in dari_csv:
                if jurnal.get(kunci):  # dibuat oleh sinkron sebelumnya yang gagal sebelum menulis Sheet
                    laporan.ditambah.append(no_resi)
                elif s != dari_csv[id_]:  # No Resi yang sudah ada = Duplikat Lapis 1
                    _gagal_baru(laporan, no_resi, baris, "No Resi sudah ada di Buku Kas (Duplikat)")
                continue
            _buat_transaksi(bills_path, no_resi, baris, kunci, uji, laporan, jurnal)
        else:
            for ke, sel in enumerate(s, 1):
                if lama_hilang:
                    _gagal_baru(laporan, "", [sel], "baris tanpa no_resi tidak bisa ditunjuk atau diubah "
                                "dari Sheets; ada baris lama tanpa no_resi yang berubah")
                else:  # baris identik diberi urutan, supaya yang kedua tidak dianggap "sudah dibuat"
                    kunci = hashlib.sha1("\x1f".join(sel).encode("utf-8")).hexdigest() + f"#{ke}"
                    _buat_transaksi(bills_path, "", [sel], kunci, uji, laporan, jurnal)


def _terapkan_masuk(bills_path: Path, sheet_grid: list, snapshot: dict, uji: bool, laporan: Laporan,
                    jurnal: _Jurnal) -> None:
    """Diff tiga arah per Transaksi: snapshot (dasar) vs Sheet sekarang vs CSV sekarang."""
    dasar, sheet = _struk(snapshot["buku_kas"]), _struk(sheet_grid)
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
                _gagal_baru(laporan, no_resi, sisa, "baris ditambah, dihapus, atau diubah bersamaan pada "
                            "Transaksi yang sudah ada tidak didukung dari Sheets (No Resi yang sama "
                            "dianggap Duplikat); tidak diterapkan")
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

    _tambah_baris_baru(bills_path, dasar, sheet, dari_csv, dijelaskan, uji, laporan, jurnal)


def _berisi_data(grid: list[list]) -> bool:
    """Ada baris selain header? Sheet kosong atau hanya berisi header dianggap kosong."""
    return len(grid) > 1


@contextlib.contextmanager
def _satu_sinkron(snapshot_path: Path):
    """Hanya satu sinkron berjalan sekaligus. Yield False bila yang lain masih berjalan."""
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path.with_name(snapshot_path.name + ".lock"), "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True


def _muat_snapshot(path: Path):
    if not path.exists():
        return None
    try:
        isi = json.loads(path.read_text(encoding="utf-8"))
        grid = isi.get("buku_kas")
        if isinstance(grid, list) and grid[:1] == [KOLOM] and all(isinstance(b, list) for b in grid):
            return isi
    except (OSError, ValueError, AttributeError):
        pass
    raise SinkronDitolak(f"Snapshot {path} rusak atau tidak terbaca. Hapus berkasnya lalu jalankan "
                         "dengan inisialisasi (CSV menang).")


def sinkron(bills_path: Path, klien, snapshot_path: Path, uji: bool = False,
            inisialisasi: bool = False) -> Laporan:
    """Sinkron dua arah. `uji` melapor tanpa menulis apa pun. Sheet yang sudah berisi data tetapi
    belum punya snapshot ditolak (SinkronDitolak) kecuali `inisialisasi`: CSV menang.

    Urutan: baca Sheet (jaringan, tanpa kunci) → di bawah kunci CSV yang sama dengan catat/buku:
    baca CSV dan terapkan perubahan masuk (tanpa jaringan) → tulis Sheet (jaringan, tanpa kunci)
    → snapshot. Pencatatan lewat chat tidak pernah menunggu Google. Snapshot ditulis paling akhir,
    jadi kegagalan di mana pun membuat sinkron berikutnya mengulang bagian yang belum selesai."""
    with _satu_sinkron(snapshot_path) as giliran:
        if not giliran:
            return Laporan(dilewati=True)
        return _sinkron(Path(bills_path), klien, snapshot_path, uji, inisialisasi)


def _sinkron(bills_path: Path, klien, snapshot_path: Path, uji: bool, inisialisasi: bool) -> Laporan:
    snapshot = None if inisialisasi else _muat_snapshot(snapshot_path)
    if not bills_path.exists():
        raise SinkronDitolak(f"{bills_path} tidak ada; Sheet tidak ditimpa dengan tabel kosong.")
    if snapshot is not None and bills_path.resolve() != Path(resi.BILLS_CSV).resolve():
        # catat.catat tidak menerima path dan selalu menulis ke resi.BILLS_CSV; tolak di awal,
        # sebelum satu edit pun sempat masuk.
        raise SinkronDitolak(f"sinkron dua arah hanya untuk resi.BILLS_CSV ({resi.BILLS_CSV}), "
                             f"bukan {bills_path}")
    saat_ini = {nama: klien.baca(nama) for nama in (SHEET_BUKU, SHEET_RINGKASAN)}
    if snapshot is None and not inisialisasi and _berisi_data(saat_ini[SHEET_BUKU]):
        raise SinkronDitolak(
            f"Worksheet '{SHEET_BUKU}' sudah berisi data tetapi belum pernah disinkronkan dari sini. "
            "Jalankan dengan inisialisasi untuk menimpanya dari bills.csv.")

    laporan = Laporan()
    jurnal = _Jurnal(snapshot_path.with_name(snapshot_path.stem + ".jurnal.json"), aktif=not uji)
    with kunci_berkas(bills_path):
        if snapshot is not None:
            _terapkan_masuk(bills_path, saat_ini[SHEET_BUKU], snapshot, uji, laporan, jurnal)
        rows = buku_kas.muat(bills_path)
    target = {SHEET_BUKU: grid_buku(rows), SHEET_RINGKASAN: grid_ringkasan(rows)}
    laporan.tak_terhitung = [(r.get("no_resi") or "", alasan)
                             for r, alasan in buku_kas.tak_terhitung(rows)]
    for nama, grid in target.items():
        if _norm(saat_ini[nama]) == _norm(grid):
            continue
        if not uji:
            if _norm(klien.baca(nama)) != _norm(saat_ini[nama]):
                laporan.berubah_saat_sinkron = True  # jangan menimpa edit yang baru masuk; ulangi nanti
                return laporan
            klien.tulis(nama, grid)
        if nama == SHEET_BUKU:
            laporan.didorong = len(grid) - 1
    if not uji:
        # Snapshot = apa yang kini tertulis di Sheet, jadi tidak perlu kunci CSV (sinkron sudah serial).
        _simpan_snapshot(snapshot_path,
                         {"buku_kas": target[SHEET_BUKU], "ringkasan": target[SHEET_RINGKASAN]})
        jurnal.kosongkan()
    return laporan
