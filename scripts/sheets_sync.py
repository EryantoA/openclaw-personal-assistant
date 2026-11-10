"""Sinkron Buku Kas ke Google Sheets (spec #20). Dua arah: perubahan di Sheets masuk ke CSV
lewat jalan tulis resmi (buku.py untuk ubah, catat.py untuk baris baru), lalu CSV disalin kembali ke Sheets.

Buku Kas tetap satu-satunya sumber (ADR-0005). Sheets adalah Cermin (ADR-0021, ADR-0026):
worksheet "Buku Kas" bergaya buku kas (sheets_format) yang bisa disunting, dan Tab Laporan
hanya-baca (sheets_laporan), dihitung skrip — bukan rumus Sheets, satu arti Saldo Bersama.
Diff tiga arah berjalan di atas bentuk ternormal 12 kolom bills.csv, jadi mengganti tampilan
(label, format) tidak pernah terbaca sebagai suntingan. Klien Sheets disuntikkan:

    klien.baca(nama_worksheet) -> list[list]          # grid; kosong = []
    klien.tulis(nama_worksheet, grid, tata) -> None   # mengganti seluruh isi + memasang tata letak
    klien.hapus(nama_worksheet) -> None               # tidak ada = tidak apa-apa
    klien.urutkan([nama_worksheet, ...]) -> None      # urutan tab

Seluruh aturan hidup di sini; adaptor Google yang sungguhan hanya memenuhi metode itu.
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
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku  # noqa: E402
import buku_kas  # noqa: E402
import catat  # noqa: E402
import pengaturan  # noqa: E402
import rekonsiliasi  # noqa: E402
import resi  # noqa: E402
import sheets_format as sf  # noqa: E402
import sheets_laporan as sl  # noqa: E402
from validasi import kunci_berkas  # noqa: E402

SHEET_BUKU = sl.SHEET_BUKU
SHEET_RINGKASAN_LAMA = "Ringkasan"  # format sebelum ADR-0026; dihapus saat migrasi
KOLOM = sf.KOLOM  # bentuk ternormal = kolom bills.csv; juga header "Buku Kas" format lama
FORMAT = 2  # versi Snapshot Sinkron; tanpa kunci "format" = format lama (ADR-0021)


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
    migrasi: bool = False  # Cermin dipindah dari format lama ke format ADR-0026 pada sinkron ini


def _grid_lama(rows: list[dict]) -> list[list]:
    """Worksheet "Buku Kas" format lama (12 kolom persis bills.csv, urutan CSV). Hanya dipakai
    migrasi untuk menyerap suntingan yang tertunda sebelum format berganti."""
    grid = [list(KOLOM)]
    for r in rows:
        baris = [(r.get(k) or "") for k in KOLOM]
        baris[KOLOM.index("jumlah")] = buku_kas.jumlah(r)
        grid.append(baris)
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
    laporan.peringatan += [b for b in pesan.splitlines() if b.startswith("⚠️")]


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


def _terapkan_masuk(bills_path: Path, sheet_grid: list, dasar_grid: list, csv_grid: list, uji: bool,
                    laporan: Laporan, jurnal: _Jurnal) -> None:
    """Diff tiga arah per Transaksi, semuanya dalam bentuk ternormal: snapshot (dasar) vs Sheet
    sekarang vs CSV sekarang."""
    dasar, sheet, dari_csv = _struk(dasar_grid), _struk(sheet_grid), _struk(csv_grid)
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


def _sel_tampil(baris: list) -> list:
    """Baris tampilan sebagai teks, sepanjang header, tanpa kolom Saldo Bersama (diisi skrip)."""
    sel = (_norm([baris])[0] + [""] * len(sf.KOLOM_TAMPIL))[:len(sf.KOLOM_TAMPIL)]
    sel[sf.I_SALDO] = ""
    return sel


def _baca_buku(grid: list, dasar_grid: list, label: dict, label_lama: dict, laporan: Laporan) -> list:
    """Worksheet "Buku Kas" (tampilan) → grid ternormal untuk diff tiga arah.

    Baris yang tidak terbaca (tanggal, kolom uang) tidak pernah diteruskan ke jalan tulis: baris
    yang sudah ada diganti nilai snapshot-nya — jadi tidak berubah dan dikembalikan saat Sheet
    ditulis ulang — dan baris baru dibuang. Keduanya dilaporkan, kecuali baris yang memang tidak
    bisa ditampilkan sejak awal (mis. tipe tak dikenal di CSV) dan tidak disentuh.

    Label yang tertulis pada sinkron sebelumnya (`label_lama`) tetap dikenali, jadi mengganti
    label di budget.json tidak terbaca sebagai suntingan; label sekarang menang bila bertabrakan."""
    balik, dasar = {**sf.label_balik(label_lama), **sf.label_balik(label)}, _struk(dasar_grid)
    i_resi = sf.KOLOM_TAMPIL.index("No Resi")
    hasil, posisi = [list(KOLOM)], {}
    for baris in grid[1:]:
        if sf.kosong(baris):
            continue
        no_resi = sf._teks(baris[i_resi] if len(baris) > i_resi else "").strip()
        ke = posisi.get(no_resi, 0)
        posisi[no_resi] = ke + 1
        norm, alasan = sf.baca_baris(baris, balik)
        if norm is not None:
            hasil.append(norm)
            continue
        lama = dasar.get(no_resi, []) if no_resi else []
        if ke < len(lama):
            hasil.append(lama[ke])
            if _sel_tampil(baris) != _sel_tampil(sf.tampil(lama[ke], "", label)):
                laporan.ditolak.append((no_resi, ke + 1, f"{alasan}; dikembalikan ke nilai Buku Kas"))
        else:
            t = dict(zip(sf.KOLOM_TAMPIL, _sel_tampil(baris)))
            uang = next((t[k] for k in sf.KOLOM_UANG if t[k]), "")
            laporan.ditolak.append((no_resi, 1, f"{alasan} — baris: {t['Tanggal']} {t['Item']} {uang}".rstrip()))
    return hasil


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


def _muat_akun(path: Path):
    try:
        isi = json.loads(path.read_text(encoding="utf-8"))
        return isi if isinstance(isi, dict) else None
    except (OSError, ValueError):
        return None


def sinkron(bills_path: Path, klien, snapshot_path: Path, uji: bool = False,
            inisialisasi: bool = False, migrasi: bool = False, atur: dict | None = None,
            akun_cfg=None, hari_ini: date | None = None) -> Laporan:
    """Sinkron dua arah. `uji` melapor tanpa menulis apa pun. Sheet yang sudah berisi data tetapi
    belum punya snapshot ditolak (SinkronDitolak) kecuali `inisialisasi`: CSV menang. Snapshot format
    lama ditolak kecuali `migrasi`, yang menyerap suntingan format lama lalu menulis format baru.

    `atur` (isi budget.json) dan `akun_cfg` (isi akun.json) dibaca dari sebelah resi.BUDGET_JSON
    bila tidak diberikan.

    Urutan: baca Sheet (jaringan, tanpa kunci) → di bawah kunci CSV yang sama dengan catat/buku:
    baca CSV dan terapkan perubahan masuk (tanpa jaringan) → tulis Sheet (jaringan, tanpa kunci)
    → snapshot. Pencatatan lewat chat tidak pernah menunggu Google. Snapshot ditulis paling akhir,
    jadi kegagalan di mana pun membuat sinkron berikutnya mengulang bagian yang belum selesai."""
    with _satu_sinkron(snapshot_path) as giliran:
        if not giliran:
            return Laporan(dilewati=True)
        if atur is None:
            atur = pengaturan.muat(Path(resi.BUDGET_JSON))
        if akun_cfg is None:
            akun_cfg = _muat_akun(Path(resi.BUDGET_JSON).with_name("akun.json"))
        catatan = rekonsiliasi.muat_catatan(Path(resi.BUDGET_JSON).with_name("rekonsiliasi.csv"))
        return _sinkron(Path(bills_path), klien, snapshot_path, uji, inisialisasi, migrasi, atur,
                        akun_cfg, hari_ini or date.today(), catatan)


def _target(rows: list, atur: dict, label: dict, akun_cfg, hari_ini: date, catatan: list) -> dict:
    """Semua worksheet Cermin, urut tab: nama → (grid, tata)."""
    hasil = {}
    for nama in sl.urutan_tab(rows):
        if nama == SHEET_BUKU:
            opsi = [label.get(k, k) for k in atur.get("kategori_custom") or []
                    if k != buku_kas.KATEGORI_REKONSILIASI]  # hanya lewat rekonsiliasi.py (ADR-0027)
            hasil[nama] = (sf.grid_tampil(rows, label), sf.tata_buku(opsi))
            continue
        if nama == sl.SHEET_RINGKASAN:
            grid = sl.grid_ringkasan_bulanan(rows)
        elif nama == sl.SHEET_AKUN:
            grid = sl.grid_saldo_akun(rows, akun_cfg, hari_ini, catatan)
        elif nama.startswith("Per Kategori "):
            grid = sl.grid_per_kategori(rows, int(nama[-4:]), label, hari_ini, atur)
        else:
            grid = sl.grid_budget(rows, int(nama[-4:]), atur, hari_ini)
        hasil[nama] = (grid, sl.tata_laporan(nama, grid))
    return hasil


def _sinkron(bills_path: Path, klien, snapshot_path: Path, uji: bool, inisialisasi: bool, migrasi: bool,
             atur: dict, akun_cfg, hari_ini: date, catatan: list) -> Laporan:
    snapshot = None if inisialisasi else _muat_snapshot(snapshot_path)
    lama = snapshot is not None and snapshot.get("format") != FORMAT
    if migrasi and snapshot is None:
        raise SinkronDitolak("Belum ada snapshot sinkron, jadi tidak ada format lama yang dimigrasi. "
                             "Jalankan dengan --inisialisasi untuk mengisi Sheet dari bills.csv.")
    if migrasi and not lama:
        raise SinkronDitolak("Cermin sudah berformat ADR-0026; jalankan sinkron biasa.")
    if lama and not migrasi:
        raise SinkronDitolak("Cermin masih berformat lama (sebelum ADR-0026); tidak ada yang diproses "
                             "atau ditimpa. Jalankan sekali: sinkron-sheets.py --migrasi-format --uji, "
                             "lalu sinkron-sheets.py --migrasi-format.")
    if not bills_path.exists():
        raise SinkronDitolak(f"{bills_path} tidak ada; Sheet tidak ditimpa dengan tabel kosong.")
    if snapshot is not None and bills_path.resolve() != Path(resi.BILLS_CSV).resolve():
        # catat.catat tidak menerima path dan selalu menulis ke resi.BILLS_CSV; tolak di awal,
        # sebelum satu edit pun sempat masuk.
        raise SinkronDitolak(f"sinkron dua arah hanya untuk resi.BILLS_CSV ({resi.BILLS_CSV}), "
                             f"bukan {bills_path}")
    saat_buku = klien.baca(SHEET_BUKU)
    header = KOLOM if migrasi else sf.KOLOM_TAMPIL
    awal = _norm(saat_buku)[:1]
    if snapshot is not None and awal and awal != [header]:
        # Kolom bergeser/bertukar berarti isi sel tidak bisa dipetakan; jangan menebak, jangan menimpa.
        raise SinkronDitolak(
            f"Header worksheet '{SHEET_BUKU}' berubah dari yang diharapkan ({', '.join(header)}). "
            "Kembalikan header-nya (tidak ada yang diproses atau ditimpa), atau jalankan dengan "
            "inisialisasi untuk menimpa Sheet dari bills.csv.")
    if snapshot is None and not inisialisasi and _berisi_data(saat_buku):
        raise SinkronDitolak(
            f"Worksheet '{SHEET_BUKU}' sudah berisi data tetapi belum pernah disinkronkan dari sini. "
            "Jalankan dengan inisialisasi untuk menimpanya dari bills.csv.")

    laporan = Laporan(migrasi=migrasi)
    label, kembar = sf.label_sah(atur.get("label_kategori"))
    if kembar:
        laporan.peringatan.append(f"⚠️ Label Kategori kembar tidak dipakai (slug-nya yang tampil): "
                                  f"{', '.join(kembar)}. Perbaiki label_kategori di data/budget.json.")
    jurnal = _Jurnal(snapshot_path.with_name(snapshot_path.stem + ".jurnal.json"), aktif=not uji)
    with kunci_berkas(bills_path):
        if snapshot is not None:
            rows = buku_kas.muat(bills_path)
            if migrasi:
                _terapkan_masuk(bills_path, saat_buku, snapshot["buku_kas"], _grid_lama(rows), uji,
                                laporan, jurnal)
            else:
                lama_ = snapshot.get("label") if isinstance(snapshot.get("label"), dict) else {}
                sheet = _baca_buku(saat_buku, snapshot["buku_kas"], label, lama_, laporan)
                _terapkan_masuk(bills_path, sheet, snapshot["buku_kas"], sf.grid_norm(rows), uji,
                                laporan, jurnal)
        rows = buku_kas.muat(bills_path)
    laporan.tak_terhitung = [(r.get("no_resi") or "", alasan)
                             for r, alasan in buku_kas.tak_terhitung(rows)]
    target = _target(rows, atur, label, akun_cfg, hari_ini, catatan)
    ditulis = False
    # "Buku Kas" lebih dulu: bila pengguna mengeditnya di tengah sinkron, belum ada tab yang ditulis.
    for nama in [SHEET_BUKU] + [n for n in target if n != SHEET_BUKU]:
        grid, tata = target[nama]
        sekarang = saat_buku if nama == SHEET_BUKU else klien.baca(nama)
        if _norm(sekarang) == _norm(grid):
            continue
        if not uji:
            if nama == SHEET_BUKU and _norm(klien.baca(nama)) != _norm(saat_buku):
                laporan.berubah_saat_sinkron = True  # jangan menimpa edit yang baru masuk; ulangi nanti
                return laporan
            klien.tulis(nama, grid, tata)
            ditulis = True
        if nama == SHEET_BUKU:
            laporan.didorong = len(grid) - 1
    if not uji:
        if migrasi or inisialisasi:
            klien.hapus(SHEET_RINGKASAN_LAMA)
        if ditulis or migrasi or inisialisasi:
            klien.urutkan(list(target))
        # Snapshot = apa yang kini tertulis di Sheet, jadi tidak perlu kunci CSV (sinkron sudah serial).
        _simpan_snapshot(snapshot_path, {"format": FORMAT, "buku_kas": sf.grid_norm(rows), "label": label})
        jurnal.kosongkan()
    return laporan


def teks_laporan(laporan: Laporan, uji: bool = False) -> str:
    """Laporan sinkron untuk dibaca pemilik (CLI/cron); tersusun dari angka, tanpa model."""
    if laporan.dilewati:
        return "Sinkron Sheets dilewati: sinkron lain masih berjalan."

    def daftar(judul, isi):
        return [f"{judul} ({len(isi)}):"] + [f"- {b}" for b in isi] if isi else []

    def resi_(no_resi):
        return no_resi or "(tanpa No Resi)"

    baris = ["Sinkron Sheets (uji: tidak ada yang ditulis)." if uji else "Sinkron Sheets selesai."]
    if laporan.migrasi:
        baris.append(("Akan dipindah" if uji else "Dipindah") + " ke format ADR-0026: \"Buku Kas\" bergaya buku "
                     "kas, Tab Laporan baru, tab \"Ringkasan\" lama dihapus. Filter tampilan dan catatan sel "
                     "yang dibuat sendiri di tab lama tidak ikut.")
    if laporan.berubah_saat_sinkron:
        baris.append("⚠️ Sheet diedit saat sinkron berjalan; tidak ada yang ditulis ke Sheet. "
                     "Edit itu diproses pada sinkron berikutnya.")
    elif laporan.didorong:
        baris.append(f"Didorong ke Sheet: {laporan.didorong} baris.")
    else:
        baris.append("Sheet sudah sama dengan Buku Kas.")
    baris += daftar("Masuk dari Sheet", [f"{resi_(r)} Item {i}: {', '.join(k)}" for r, i, k in laporan.diterima])
    if laporan.ditambah:
        baris.append(f"Transaksi baru dari Sheet ({len(laporan.ditambah)}): {', '.join(laporan.ditambah)}")
    baris += daftar("Ditolak", [f"{resi_(r)} Item {i}: {a}" for r, i, a in laporan.ditolak])
    baris += daftar("Dipulihkan ke Sheet", [f"{resi_(r)} Item {i}" for r, i in laporan.dipulihkan])
    baris += daftar("Tak terhitung", [f"{resi_(r)}: {a}" for r, a in laporan.tak_terhitung])
    return "\n".join(baris + laporan.peringatan)


def tulis_status(path: Path, hasil: str, pesan: str = "", laporan: Laporan | None = None,
                 sekarang: datetime | None = None) -> None:
    """Catat hasil satu sinkron untuk penjaga kesehatan (scripts/periksa-kesehatan.py).

    `hasil`: "sukses" | "tertunda" | "ditolak" | "gagal". `waktu_sukses` hanya maju pada "sukses"
    dan dipertahankan selama percobaan berikutnya gagal — dari situlah penjaga tahu sudah berapa
    lama sinkron mandek. Hanya hitungan dan pesan galat; tidak ada isi Transaksi."""
    sekarang = (sekarang or datetime.now()).isoformat(timespec="seconds")
    try:
        lama = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        lama = {}
    if not isinstance(lama, dict):
        lama = {}
    status = {"waktu": sekarang, "hasil": hasil, "pesan": pesan[:300],
              "waktu_sukses": sekarang if hasil == "sukses" else lama.get("waktu_sukses")}
    if laporan is not None:
        status.update(didorong=laporan.didorong, diterima=len(laporan.diterima),
                      ditambah=len(laporan.ditambah), ditolak=len(laporan.ditolak),
                      dipulihkan=len(laporan.dipulihkan))
    _tulis_atomik(Path(path), json.dumps(status, ensure_ascii=False, indent=1))
