#!/usr/bin/env python3
"""
buku.py — cari, ubah, dan hapus data yang sudah tercatat di CSV (menambah tetap lewat catat.py).

Bot tidak boleh menyentuh CSV dengan Edit/Write. Skrip ini yang mengerjakan semua yang mekanis:
mencari, memvalidasi hasil dengan aturan yang sama dengan catat.py, menyalin dulu, memproses
salinan, memverifikasinya, lalu menggantikan berkas asli sekaligus. Ubah dan hapus selalu dua
langkah (ADR-0016, ADR-0018): `--uji` menghitung Pratinjau tanpa menulis dan memberi `sidik`;
eksekusi hanya jalan bila `sidik` yang sama dikirim kembali.

    python3 scripts/buku.py cari --kata indomaret --dari 2026-10-01 --sampai 2026-10-31
    python3 scripts/buku.py ubah --uji <<'EOF'
    {"no_resi": "STRUK-000123", "item_ke": 2, "set": {"jumlah": 25000, "kategori": "groceries"},
     "oleh": "Eryanto"}
    EOF
    python3 scripts/buku.py hapus --uji <<'EOF'
    {"no_resi": "STRUK-000123", "oleh": "Eryanto"}        # tanpa item_ke = seluruh Transaksi
    EOF

  Masukan ubah : no_resi, set {kolom: nilai}, oleh (wajib); item_ke (angka | "semua"), sidik
  Masukan hapus: no_resi, oleh (wajib); item_ke (angka), sidik
  `sidik` wajib tanpa --uji dan harus berasal dari --uji dengan masukan yang sama.

Keluaran / exit code:
  0  "OK ..." (cari: hasil; --uji: "OK lolos cek (tidak ditulis)"; "OK terubah"/"OK terhapus")
  1  "DUPLICATE ..." — hasil ubah sama dengan Transaksi lain, tidak ditulis
  2  "ERROR ..." — masukan tidak valid / ditolak, tidak ada yang berubah
"""

# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).parent))
import resi  # noqa: E402
import validasi  # noqa: E402
from validasi import Tolak, kunci_berkas  # noqa: E402

TIDAK_BERUBAH = "TIDAK ADA YANG BERUBAH. Jangan membalas bahwa data sudah diubah atau dihapus."
JEJAK_KOLOM = ["waktu", "aksi", "no_resi", "item_ke", "oleh", "sebelum", "sesudah"]


class Dobel(Tolak):
    """Hasil ubah sama dengan Transaksi lain (exit 1)."""


# ── Skema ────────────────────────────────────────────────────────────────
@dataclass
class Skema:
    """Deklarasi satu CSV. CSV baru cukup mendaftarkan satu Skema untuk mendapat cari/ubah/hapus."""
    nama: str
    path: Callable[[], Path]
    kolom: list
    kunci: str                              # kolom penanda satu Transaksi (baris sekunci = satu kesatuan)
    terkunci: frozenset                     # kolom yang tidak boleh diubah
    tingkat_transaksi: frozenset            # kolom yang berlaku untuk seluruh Transaksi
    cek_baris: Callable[..., dict]          # (baris, awalan) -> baris ternormalisasi / raise Tolak
    cek_duplikat: Callable[[list, list], Optional[str]]
    terlindung: Callable[[dict], Optional[str]]   # alasan baris tak boleh disentuh
    format_cari: Callable[..., str]
    peringatan: Callable[..., list]         # (path, lama, baru) -> daftar peringatan
    append_only: bool = False
    kolom_kata: tuple = ()                  # kolom yang dicari oleh --kata


# ── Baca berkas (mempertahankan teks asli tiap rekaman) ──────────────────
@dataclass
class Rec:
    raw: str
    d: Optional[dict]        # None = baris kosong; "__rusak" bila jumlah kolom tak sama dengan header


@dataclass
class Berkas:
    kepala_raw: str
    header: list
    recs: list
    eol: str


def baca(path: Path) -> Berkas:
    isi = ""
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:  # newline="": CRLF dipertahankan apa adanya
            isi = f.read()
    if not isi.strip():
        raise Tolak(f"{path.name} kosong atau tidak ada")
    baris = list(io.StringIO(isi, newline=""))
    pembaca = csv.reader(baris)
    rekaman, awal = [], 0
    for fields in pembaca:
        akhir = pembaca.line_num
        rekaman.append((fields, "".join(baris[awal:akhir])))
        awal = akhir
    header = rekaman[0][0]
    eol = "\r\n" if "\r\n" in isi else "\n"
    recs = []
    for fields, raw in rekaman[1:]:
        if not fields:
            recs.append(Rec(raw, None))
            continue
        d = dict(zip(header, fields + [""] * (len(header) - len(fields))))
        if len(fields) != len(header):
            d["__rusak"] = f"jumlah kolom {len(fields)} (seharusnya {len(header)})"
        recs.append(Rec(raw, d))
    return Berkas(rekaman[0][1], header, recs, eol)


def serialisasi(header: list, d: dict, eol: str) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator=eol).writerow([d.get(k, "") for k in header])
    return out.getvalue()


def baris_sah(rec: Rec) -> bool:
    return rec.d is not None and "__rusak" not in rec.d


def grup(b: Berkas, kunci: str, nilai: str) -> list:
    return [i for i, r in enumerate(b.recs)
            if r.d is not None and (r.d.get(kunci) or "").strip() == nilai]


# ── Format ───────────────────────────────────────────────────────────────
def rp(n) -> str:
    try:
        return f"Rp {int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return f"Rp {n}"


def total(rows: list) -> int:
    return sum(int(resi.norm_total(r.get("jumlah")) or 0) for r in rows)


def tampil_nilai(kolom: str, nilai) -> str:
    nilai = "" if nilai is None else str(nilai)
    if kolom == "jumlah":
        return rp(nilai)
    return nilai if nilai else "-"


# ── Skema bills.csv ──────────────────────────────────────────────────────
def _cek_bills(baris: dict, awalan: str = "", ubah=None) -> dict:
    return validasi.cek_baris(baris, validasi.kategori_sah(), awalan, ubah)


def _terlindung_bills(d: dict) -> Optional[str]:
    if "__rusak" in d:
        return f"baris rusak ({d['__rusak']}); perbaiki manual atau lewat resi.py --backfill"
    if (d.get("kategori") or "").strip() == "opening_balance":
        return "baris opening_balance tidak boleh diubah atau dihapus (ADR-0008)"
    if not (d.get("no_resi") or "").strip():
        return "baris tanpa no_resi tidak bisa ditunjuk; jalankan resi.py --backfill dulu"
    return None


def _muat_json(path: Path, bawaan):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return bawaan


def _arus(rows: list) -> dict:
    """{bulan: [pemasukan, pengeluaran]}; transfer tidak ikut (CONTEXT.md → Saldo, Koreksi)."""
    hasil = {}
    for r in rows:
        bulan = (r.get("tanggal") or "")[:7]
        tipe = (r.get("tipe") or "pengeluaran").strip().lower()
        if not bulan or tipe == "transfer":
            continue
        h = hasil.setdefault(bulan, [0, 0])
        h[0 if tipe == "pemasukan" else 1] += int(resi.norm_total(r.get("jumlah")) or 0)
    return hasil


def _peringatan_bills(path: Path, lama: list, baru: list) -> list:
    """Peringatan yang tidak memblokir: Kewajiban tertaut dan bulan yang sudah dilaporkan."""
    hasil = []
    if lama and not baru:
        nomor = (lama[0].get("no_resi") or "").strip()
        for e in _muat_json(path.with_name("kewajiban.json"), {}).get("kewajiban", []):
            if nomor and (e.get("lunas_resi") or "").strip() == nomor:
                hasil.append(f"⚠️ Kewajiban {e.get('nama') or e.get('id')} ({e.get('id')}) tertaut ke "
                             f"Transaksi ini dan akan kembali belum lunas.")
    sebelum, sesudah = _arus(lama), _arus(baru)
    dilaporkan = _muat_json(path.with_name("laporan-bulanan.json"), {}).get("bulan", {})
    for bulan in sorted(set(sebelum) | set(sesudah)):
        if bulan in dilaporkan and sebelum.get(bulan, [0, 0]) != sesudah.get(bulan, [0, 0]):
            hasil.append(f"⚠️ Bulan {bulan} sudah dilaporkan; perubahan ini akan muncul sebagai "
                         f"Koreksi di Laporan Bulanan berikutnya.")
    return hasil


def _format_cari_bills(kata_kunci: str, groups: list, jumlah: int) -> str:
    """Kerangka hasil pencarian — didefinisikan di AGENTS.md (Mencari transaksi)."""
    keluar = [f"🔍 Hasil pencarian: {kata_kunci} ({jumlah} transaksi)"]
    if jumlah > len(groups):
        keluar[0] += f" — tampil {len(groups)} terbaru"
    for rows in groups:
        r0 = rows[0]
        keluar += ["", f"Struk: {r0.get('no_resi') or '-'} | Tanggal: {r0.get('tanggal') or '-'} | "
                       f"Jam: {r0.get('waktu') or '-'}",
                   f"Pembeli: {r0.get('pencatat') or '-'}"]
        for i, r in enumerate(rows, 1):
            keluar.append(f"- [{i}] {r.get('item') or '-'}: {rp(r.get('jumlah'))}")
        keluar.append(f"- Total: {rp(total(rows))}")
    return "\n".join(keluar)


def skema_bills() -> Skema:
    return Skema(
        nama="bills", path=lambda: resi.BILLS_CSV, kolom=list(resi.COLUMNS), kunci="no_resi",
        terkunci=frozenset({"no_resi", "channel"}),
        tingkat_transaksi=frozenset({"tanggal", "waktu", "tipe", "pencatat", "akun", "akun_tujuan"}),
        cek_baris=_cek_bills,
        cek_duplikat=lambda baru, lain: validasi.cek_duplikat_lapis2(baru, lain, saran_paksa=False),
        terlindung=_terlindung_bills, format_cari=_format_cari_bills, peringatan=_peringatan_bills,
        kolom_kata=("item",))


def _format_cari_umum(kata_kunci: str, groups: list, jumlah: int) -> str:
    keluar = [f"🔍 Hasil pencarian: {kata_kunci} ({jumlah} data)"]
    for rows in groups:
        keluar.append("")
        keluar += ["- " + ", ".join(f"{k}={v}" for k, v in r.items() if not k.startswith("__"))
                   for r in rows]
    return "\n".join(keluar)


def skema_jejak() -> Skema:
    """Jejak perubahan: append-only, tanpa ubah/hapus lewat chat."""
    return Skema(
        nama="riwayat", path=lambda: resi.BILLS_CSV.with_name("riwayat-ubah.csv"),
        kolom=list(JEJAK_KOLOM), kunci="no_resi", terkunci=frozenset(JEJAK_KOLOM),
        tingkat_transaksi=frozenset(), cek_baris=lambda b, awalan="": b,
        cek_duplikat=lambda baru, lain: None, terlindung=lambda d: "jejak perubahan append-only",
        format_cari=_format_cari_umum, peringatan=lambda p, l, b: [], append_only=True,
        kolom_kata=("aksi", "no_resi", "oleh", "sebelum", "sesudah"))


SKEMA = {"bills": skema_bills, "riwayat": skema_jejak}


# ── Read ─────────────────────────────────────────────────────────────────
def cari(skema: Skema, kata: str = "", resi_: str = "", tanggal: str = "", dari: str = "",
         sampai: str = "", kategori: str = "", pembeli: str = "", tipe: str = "",
         batas: int = 10, terakhir: bool = False) -> tuple:
    try:
        b = baca(skema.path())
    except Tolak as e:
        return 2, f"ERROR {e}"
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        return 2, f"ERROR tak terduga ({type(e).__name__}: {e})"
    peta = resi.peta_pembeli()  # baris lama bisa menyimpan alias; bandingkan nama bakunya
    if pembeli:
        pembeli = resi.kanon_pembeli(pembeli, peta)
    urut = {}
    for i, r in enumerate(b.recs):
        if r.d is None:
            continue
        d = r.d
        if resi_ and (d.get(skema.kunci) or "").strip() != resi_:
            continue
        t = (d.get("tanggal") or "").strip()
        if tanggal and t != tanggal:
            continue
        if dari and not (t and t >= dari):
            continue
        if sampai and not (t and t <= sampai):
            continue
        if kategori and (d.get("kategori") or "").strip().casefold() != kategori.strip().casefold():
            continue
        if pembeli and resi.kanon_pembeli(d.get("pencatat"), peta).casefold() != pembeli.casefold():
            continue
        if tipe and (d.get("tipe") or "").strip() != tipe:
            continue
        if kata and not any(kata.casefold() in (d.get(k) or "").casefold() for k in skema.kolom_kata):
            continue
        urut.setdefault((d.get(skema.kunci) or "").strip() or f"__baris{i}", []).append((i, d))
    kelompok = list(urut.values())
    if terakhir:  # dicatat terakhir = paling bawah di berkas
        kelompok.sort(key=lambda g: g[0][0], reverse=True)
    else:
        kelompok.sort(key=lambda g: ((g[0][1].get("tanggal") or ""), (g[0][1].get("waktu") or ""),
                                     g[0][0]), reverse=True)
    jumlah = len(kelompok)
    label = ", ".join(x for x in (kata, resi_, tanggal, f"{dari}..{sampai}" if dari or sampai else "",
                                  kategori, pembeli, tipe) if x) or "semua"
    if jumlah == 0:
        return 0, f"OK tidak ditemukan: {label}"
    tampil = kelompok[:max(1, batas)]
    return 0, skema.format_cari(label, [[d for _, d in g] for g in tampil], jumlah)


# ── Tulis (ubah / hapus) ─────────────────────────────────────────────────
def _sidik(aksi: str, inti: dict, lama_raw: list) -> str:
    isi = json.dumps([aksi, inti, lama_raw], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(isi.encode("utf-8")).hexdigest()[:12]


def _item_ke(req: dict, n: int, boleh_semua: bool) -> Optional[object]:
    v = req.get("item_ke")
    if v is None or v == "":
        return None
    if isinstance(v, str) and v.strip().casefold() == "semua" and boleh_semua:
        return "semua"
    try:
        i = int(v)
    except (TypeError, ValueError):
        raise Tolak(f"item_ke harus nomor 1..{n}" + (' atau "semua"' if boleh_semua else "") + f", dapat {v!r}")
    if not 1 <= i <= n:
        raise Tolak(f"item_ke {i} di luar rentang: Transaksi ini punya {n} item (1..{n})")
    return i


def _tulis_atomik(skema: Skema, b: Berkas, teks_baru: str, aksi: str, sekarang: datetime,
                  rec_utuh: list, jejak: dict) -> None:
    """Salin dulu, proses salinan, verifikasi, baru ganti berkas asli.

    rec_utuh = teks mentah rekaman lain yang HARUS tetap sama persis setelah penulisan.
    """
    path = skema.path()
    cadangan = path.parent / "backups"
    cadangan.mkdir(parents=True, exist_ok=True)
    cap = sekarang.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(path, cadangan / f"{path.stem}_sebelum-{aksi}_{cap}{path.suffix}")

    fd, nama_kerja = tempfile.mkstemp(prefix=path.name + ".", suffix=".proses", dir=str(path.parent))
    kerja = Path(nama_kerja)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(teks_baru)
            f.flush()
            os.fsync(f.fileno())
        shutil.copymode(path, kerja)
        # Verifikasi salinan: terbaca utuh, header sama, rekaman lain tak tersentuh
        cek = baca(kerja)
        if cek.header != b.header or cek.kepala_raw != b.kepala_raw:
            raise Tolak("verifikasi salinan gagal: header berubah")
        sisa = {r.raw for r in cek.recs}
        for raw in rec_utuh:
            if raw not in sisa:
                raise Tolak("verifikasi salinan gagal: ada baris lain yang berubah")
        _tambah_jejak(path, sekarang, aksi, jejak)
        try:
            os.replace(kerja, path)
        except OSError:
            # Jejak sudah ditulis lebih dulu (jejak tak boleh kurang dari perubahan): tandai gagal
            _tambah_jejak(path, sekarang, f"gagal-{aksi}", jejak)
            raise
    finally:
        if kerja.exists():
            kerja.unlink()


def _tambah_jejak(path: Path, sekarang: datetime, aksi: str, jejak: dict) -> None:
    j = path.with_name("riwayat-ubah.csv")
    baru = not j.exists() or j.stat().st_size == 0
    with open(j, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if baru:
            w.writerow(JEJAK_KOLOM)
        w.writerow([sekarang.isoformat(timespec="seconds"), aksi, jejak["no_resi"], jejak["item_ke"],
                    jejak["oleh"], json.dumps(jejak["sebelum"], ensure_ascii=False),
                    json.dumps(jejak["sesudah"], ensure_ascii=False)])
        f.flush()
        os.fsync(f.fileno())


def _siapkan(skema: Skema, aksi: str, req: dict, izinkan: set) -> tuple:
    if skema.append_only:
        raise Tolak(f"{skema.nama} bersifat append-only: tidak bisa di{aksi}")
    asing = sorted(set(req) - izinkan)
    if asing:
        raise Tolak(f"kunci tidak dikenal {asing}; kunci yang sah: {sorted(izinkan)}")
    nomor = str(req.get(skema.kunci) or "").strip()
    if not nomor:
        raise Tolak(f"`{skema.kunci}` wajib diisi (cari dulu Transaksinya dengan `cari`)")
    oleh = str(req.get("oleh") or "").strip()
    if not oleh:
        raise Tolak("`oleh` wajib diisi: nama pengirim pesan, untuk jejak perubahan")
    return nomor, resi.kanon_pembeli(oleh)


def jalankan(skema: Skema, aksi: str, req: dict, uji: bool = False,
             sekarang: Optional[datetime] = None) -> tuple:
    """aksi: 'ubah' | 'hapus'. Mengembalikan (kode, pesan)."""
    sekarang = sekarang or datetime.now()
    try:
        return _jalankan(skema, aksi, req, uji, sekarang)
    except Dobel as e:
        return 1, str(e)
    except Tolak as e:
        return 2, f"ERROR {e}"
    except Exception as e:  # noqa: BLE001  exit 1 berarti DUPLICATE; kegagalan lain harus 2
        return 2, f"ERROR tak terduga ({type(e).__name__}: {e}); berkas asli tidak diubah"


def _jalankan(skema: Skema, aksi: str, req: dict, uji: bool, sekarang: datetime) -> tuple:
    izinkan = {skema.kunci, "item_ke", "oleh", "sidik"} | ({"set"} if aksi == "ubah" else set())
    nomor, oleh = _siapkan(skema, aksi, req, izinkan)
    path = skema.path()
    with kunci_berkas(path):
        b = baca(path)
        if not set(skema.kolom) <= set(b.header):
            raise Tolak(f"header {path.name} tidak lengkap; jalankan resi.py --backfill dulu")
        idx = grup(b, skema.kunci, nomor)
        if not idx:
            raise Tolak(f"Transaksi {nomor} tidak ditemukan (cari dulu dengan `cari`)")
        lama = [b.recs[i].d for i in idx]
        for d in lama:
            alasan = skema.terlindung(d)
            if alasan:
                raise Tolak(f"{nomor}: {alasan}")
        lama_raw = [b.recs[i].raw for i in idx]

        if aksi == "hapus":
            ke = _item_ke(req, len(idx), boleh_semua=False)
            hasil = _rencana_hapus(skema, nomor, lama, ke)
        else:
            lain = [r.d for i, r in enumerate(b.recs) if baris_sah(r) and i not in idx]
            hasil = _rencana_ubah(skema, nomor, lama, req, len(idx), lain)
        baru, ke, inti, uraian = hasil

        # Peringatan memakai Transaksi utuh sebelum dan sesudah
        sesudah_utuh = [d for d in baru if d is not None]
        peringatan = skema.peringatan(path, lama, sesudah_utuh)
        sidik = _sidik(aksi, inti, lama_raw)

        if uji:
            return 0, "\n".join(
                [f"OK lolos cek (tidak ditulis) | aksi {aksi} | no_resi {nomor} | sidik {sidik}",
                 *uraian, *peringatan])

        diberi = str(req.get("sidik") or "").strip()
        if not diberi:
            raise Tolak("`sidik` wajib: jalankan dengan --uji dulu, tampilkan Pratinjau, "
                        "dan kirim sidiknya setelah pengguna menjawab ya")
        if diberi != sidik:
            raise Tolak("sidik tidak cocok: data atau permintaan sudah berbeda dari Pratinjau. "
                        "Jalankan --uji lagi dan tampilkan Pratinjau baru")

        # Susun teks baru: rekaman lain memakai teks aslinya
        potongan, lain_raw, ganti = [], [], dict(zip(idx, baru))
        for i, r in enumerate(b.recs):
            if i in ganti and ganti[i] is not r.d:
                d = ganti[i]
                if d is not None:
                    raw = serialisasi(b.header, d, b.eol)
                    if not r.raw.endswith(("\n", "\r")):
                        raw = raw.rstrip("\r\n")
                    potongan.append(raw)
            else:
                potongan.append(r.raw)
                lain_raw.append(r.raw)
        teks = b.kepala_raw + "".join(potongan)
        jejak = {"no_resi": nomor, "item_ke": "" if ke is None else ke, "oleh": oleh,
                 "sebelum": [_ringkas(d) for d in lama],
                 "sesudah": [_ringkas(d) for d in sesudah_utuh]}
        try:
            _tulis_atomik(skema, b, teks, aksi, sekarang, lain_raw, jejak)
        except Tolak:
            raise
        except OSError as e:
            raise Tolak(f"penulisan gagal ({e}); berkas asli tidak diubah")
        kata = "terubah" if aksi == "ubah" else "terhapus"
        return 0, "\n".join([f"OK {kata} | aksi {aksi} | no_resi {nomor} | oleh {oleh}", *uraian, *peringatan])


def _ringkas(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("__")}


def _rencana_hapus(skema: Skema, nomor: str, lama: list, ke) -> tuple:
    if ke is None or len(lama) == 1:
        baru, ke_catat = [None] * len(lama), None
        uraian = [f"Hapus Transaksi {nomor} ({lama[0].get('tanggal')}, {lama[0].get('waktu')}, "
                  f"Pembeli {lama[0].get('pencatat')})"]
        uraian += [f"- [{i}] {d.get('item')}: {rp(d.get('jumlah'))}" for i, d in enumerate(lama, 1)]
        uraian.append(f"Total dihapus: {rp(total(lama))}")
    else:
        baru = [None if i == ke else d for i, d in enumerate(lama, 1)]
        ke_catat = ke
        uraian = [f"Hapus Item {ke} dari Transaksi {nomor}",
                  f"- [{ke}] {lama[ke - 1].get('item')}: {rp(lama[ke - 1].get('jumlah'))}",
                  f"Total Transaksi: {rp(total(lama))} → {rp(total([d for d in baru if d]))}"]
    inti = {"no_resi": nomor, "item_ke": ke_catat}
    return baru, ke_catat, inti, uraian


def _rencana_ubah(skema: Skema, nomor: str, lama: list, req: dict, n: int, lain: list) -> tuple:
    perubahan = req.get("set")
    if not isinstance(perubahan, dict) or not perubahan:
        raise Tolak('`set` harus objek berisi minimal satu kolom, mis. {"jumlah": 25000}')
    boleh = set(skema.kolom) - skema.terkunci
    for k in perubahan:
        if k in skema.terkunci:
            raise Tolak(f"kolom `{k}` tidak boleh diubah")
        if k not in boleh:
            raise Tolak(f"kolom `{k}` tidak dikenal; kolom yang boleh diubah: {sorted(boleh)}")
    ke = _item_ke(req, n, boleh_semua=True)
    tingkat_tx = [k for k in perubahan if k in skema.tingkat_transaksi]
    tingkat_item = [k for k in perubahan if k not in skema.tingkat_transaksi]
    if isinstance(ke, int) and tingkat_tx:
        raise Tolak(f"kolom {tingkat_tx} berlaku untuk seluruh Transaksi; jangan sebut item_ke "
                    f'(atau pakai "semua")')
    if tingkat_item and ke is None and n > 1:
        raise Tolak(f"Transaksi ini punya {n} item; kolom {tingkat_item} perlu item_ke "
                    f'(nomor 1..{n} atau "semua")')

    sasaran = list(range(n)) if ke in (None, "semua") else [ke - 1]
    baru, berubah = [], []
    for i, d in enumerate(lama):
        disentuh = {k for k in perubahan if k in skema.tingkat_transaksi or i in sasaran}
        kandidat = {**d, **{k: perubahan[k] for k in disentuh}}
        if kandidat != d:
            norm = skema.cek_baris(kandidat, f"item {i + 1}: " if n > 1 else "", disentuh)
            # hanya kolom yang diubah yang dinormalisasi; kolom lama dibiarkan apa adanya
            kandidat = {**d, **{k: norm[k] for k in disentuh}}
        if kandidat != d:
            berubah.append(i)
            baru.append(kandidat)
        else:
            baru.append(d)
    if not berubah:
        raise Tolak("tidak ada yang berubah: nilai baru sama dengan nilai sekarang")

    # Duplikat hanya diperiksa bila kolom pembanding ikut berubah (jangan menghukum duplikat lama)
    cfg = resi.load_duplicate_config()
    kena = [baru[i] for i in berubah
            if any(resi.norm_field(f, baru[i].get(f)) != resi.norm_field(f, lama[i].get(f))
                   for f in cfg["match_fields"])]
    if kena:
        pesan = skema.cek_duplikat(kena, lain)
        if pesan:
            raise Dobel(pesan)

    uraian = [f"Ubah Transaksi {nomor}"]
    for k in perubahan:
        if k in skema.tingkat_transaksi:
            i = next((j for j in berubah if baru[j].get(k) != lama[j].get(k)), None)
            if i is not None:
                uraian.append(f"- {k}: {tampil_nilai(k, lama[i].get(k))} → {tampil_nilai(k, baru[i].get(k))}"
                              + (" (semua item)" if n > 1 else ""))
        else:
            for j in berubah:
                if baru[j].get(k) != lama[j].get(k):
                    uraian.append(f"- [{j + 1}] {k}: {tampil_nilai(k, lama[j].get(k))} → "
                                  f"{tampil_nilai(k, baru[j].get(k))}")
    if total(lama) != total(baru):
        uraian.append(f"Total Transaksi: {rp(total(lama))} → {rp(total(baru))}")
    inti = {"no_resi": nomor, "item_ke": ke, "set": perubahan}
    return baru, ke, inti, uraian


# ── CLI ──────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Cari, ubah, dan hapus data di CSV")
    p.add_argument("--berkas", default="bills", choices=sorted(SKEMA), help="CSV yang dituju")
    sub = p.add_subparsers(dest="perintah", required=True)
    c = sub.add_parser("cari", help="Cari Transaksi (read-only)")
    c.add_argument("--kata", default="")
    c.add_argument("--resi", default="")
    c.add_argument("--tanggal", default="")
    c.add_argument("--dari", default="")
    c.add_argument("--sampai", default="")
    c.add_argument("--kategori", default="")
    c.add_argument("--pembeli", default="")
    c.add_argument("--tipe", default="")
    c.add_argument("--batas", type=int, default=10)
    c.add_argument("--terakhir", action="store_true", help="urut berdasarkan yang terakhir dicatat")
    for nama in ("ubah", "hapus"):
        u = sub.add_parser(nama, help=f"{nama.capitalize()} (JSON di stdin)")
        u.add_argument("--uji", action="store_true", help="Pratinjau saja, tidak menulis")
    a = p.parse_args(argv)
    skema = SKEMA[a.berkas]()

    if a.perintah == "cari":
        kode, pesan = cari(skema, kata=a.kata, resi_=a.resi, tanggal=a.tanggal, dari=a.dari,
                           sampai=a.sampai, kategori=a.kategori, pembeli=a.pembeli, tipe=a.tipe,
                           batas=a.batas, terakhir=a.terakhir)
        print(pesan)
        return kode

    try:
        req = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        kode, pesan = 2, f"ERROR JSON tidak valid: {e}"
    else:
        if isinstance(req, dict):
            kode, pesan = jalankan(skema, a.perintah, req, uji=a.uji)
        else:
            kode, pesan = 2, "ERROR masukan harus satu objek JSON"
    print(pesan)
    if kode == 2:
        print('Contoh: {"no_resi": "STRUK-000123", "item_ke": 2, "set": {"jumlah": 25000}, '
              '"oleh": "Eryanto"}')
    if kode != 0:
        print(TIDAK_BERUBAH)
    return kode


if __name__ == "__main__":
    sys.exit(main())
