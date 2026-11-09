#!/usr/bin/env python3
"""Rekonsiliasi per Akun (ADR-0027, spec 0006): Saldo Akun menurut Buku Kas vs Saldo Nyata.

    python3 scripts/rekonsiliasi.py cek    --akun "Mandiri Ryan" --saldo 5230000 [--per 2026-11-30]
    python3 scripts/rekonsiliasi.py simpan --akun "Mandiri Ryan" --saldo 5230000 --cara cocok|dibiarkan
    python3 scripts/rekonsiliasi.py tutup  --akun "Mandiri Ryan" --saldo 5230000 --channel whatsapp \\
                                           --pencatat Eryanto [--uji]

`cek` hanya membaca. `simpan` menulis satu baris ke data/rekonsiliasi.csv (cocok hanya bila
selisih Rp 0). `tutup` membuat Transaksi Selisih Rekonsiliasi lewat catat.py (`--uji` = Pratinjau)
lalu mencatat Rekonsiliasinya. Titik = saat ini (`--sekarang` untuk uji) atau akhir hari `--per`.

Saldo Akun per titik memakai aturan akun.saldo_per_akun: saldo_awal + baris sejak cutover yang
(tanggal, waktu) ≤ titik; waktu kosong = awal hari (ikut dihitung, dan disebut bila hari titik).

Kode keluar: 0 berhasil, 2 masukan ditolak (tidak ada yang ditulis).
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import akun  # noqa: E402
import buku_kas  # noqa: E402
import resi  # noqa: E402
from tampilan import rp  # noqa: E402
from validasi import kunci_berkas  # noqa: E402

KOLOM = ["waktu_cek", "titik", "akun", "saldo_nyata", "saldo_akun", "selisih", "cara", "no_resi"]
CARA = ("cocok", "dibiarkan", "selisih_ditutup")
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
              "Oktober", "November", "Desember"]
KANDIDAT_MAKS = 10


class Ditolak(Exception):
    pass


def path_catatan() -> Path:
    return Path(resi.BILLS_CSV).with_name("rekonsiliasi.csv")


def path_akun() -> Path:
    return Path(resi.BILLS_CSV).with_name("akun.json")


def muat_akun(path: Path | None = None):
    try:
        isi = json.loads((path or path_akun()).read_text(encoding="utf-8"))
        return isi if isinstance(isi, dict) else None
    except (OSError, ValueError):
        return None


def aktif(cfg) -> bool:
    try:
        return isinstance(cfg, dict) and akun.aktif(cfg)
    except (KeyError, TypeError, AttributeError):
        return False


def muat_catatan(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tgl_tampil(d) -> str:
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def titik(per: str | None, sekarang: datetime) -> datetime:
    """Tanpa `per`: saat ini. Dengan `per` (YYYY-MM-DD): akhir hari itu."""
    if not per:
        return sekarang.replace(microsecond=0)
    try:
        return datetime.combine(date.fromisoformat(per), time(23, 59, 59))
    except ValueError:
        raise Ditolak(f"--per harus YYYY-MM-DD, dapat {per!r}") from None


def _alias(cfg) -> dict:
    hasil = {a["nama"].strip().lower(): a["id"] for a in cfg["akun"]}
    hasil.update({a["id"]: a["id"] for a in cfg["akun"]})
    return hasil


def cari_akun(cfg, nama: str) -> dict:
    id_ = _alias(cfg).get((nama or "").strip().lower())
    if id_ is None:
        raise Ditolak(f"Akun {nama!r} tidak dikenal. Akun yang ada: "
                      f"{', '.join(a['nama'] for a in cfg['akun'])}")
    return next(a for a in cfg["akun"] if a["id"] == id_)


def waktu_baris(r: dict):
    tgl = buku_kas.tanggal(r)
    if tgl is None:
        return None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", (r.get("waktu") or "").strip())
    jam = time(int(m.group(1)) % 24, int(m.group(2)) % 60) if m else time(0, 0)
    return datetime.combine(tgl, jam)


def _efek(r: dict, alias: dict, id_akun: str) -> int:
    """Pengaruh satu baris ke Saldo Akun `id_akun` (aturan akun.saldo_per_akun)."""
    a, t = buku_kas.arah(r), buku_kas.jumlah(r)
    dari = alias.get((r.get("akun") or "").strip().lower())
    if a == "transfer":
        ke = alias.get((r.get("akun_tujuan") or "").strip().lower())
        if not (dari and ke):
            return 0
        return (-t if dari == id_akun else 0) + (t if ke == id_akun else 0)
    if a is None or dari != id_akun:
        return 0
    return t if a == "pemasukan" else -t


def _di_rentang(r: dict, cutover: date, mulai: datetime | None, akhir: datetime) -> bool:
    w = waktu_baris(r)
    return w is not None and w.date() >= cutover and w <= akhir and (mulai is None or w > mulai)


def efek(rows: list, cfg, id_akun: str, akhir: datetime) -> int:
    cutover, alias = date.fromisoformat(cfg["cutover"]), _alias(cfg)
    return sum(_efek(r, alias, id_akun) for r in rows if _di_rentang(r, cutover, None, akhir))


def saldo_akun(rows: list, cfg, id_akun: str, akhir: datetime) -> int:
    awal = next(a for a in cfg["akun"] if a["id"] == id_akun)["saldo_awal"]
    return int(float(awal)) + efek(rows, cfg, id_akun, akhir)


def terakhir(catatan: list, nama: str):
    milik = [c for c in catatan if c.get("akun") == nama]
    return milik[-1] if milik else None


def selisih_terbuka(catatan: list, nama: str) -> int:
    c = terakhir(catatan, nama)
    return int(c["selisih"]) if c and c.get("cara") == "dibiarkan" else 0


def cek(rows: list, cfg, catatan: list, nama: str, saldo_nyata: int, akhir: datetime) -> dict:
    if not aktif(cfg):
        raise Ditolak("Fitur akun belum aktif: saldo_awal tiap Akun di data/akun.json belum lengkap (ADR-0010).")
    a = cari_akun(cfg, nama)
    cutover = date.fromisoformat(cfg["cutover"])
    if akhir.date() < cutover:
        raise Ditolak(f"Titik {tgl_tampil(akhir)} sebelum cutover {tgl_tampil(cutover)}; Saldo Akun baru "
                      "bermakna sejak cutover (ADR-0010).")
    lalu = terakhir(catatan, a["nama"])
    mulai = datetime.fromisoformat(lalu["titik"]) if lalu else None
    alias = _alias(cfg)
    s = saldo_akun(rows, cfg, a["id"], akhir)
    akhir_hari = akhir.time() == time(23, 59, 59)
    tanpa_jam = [] if akhir_hari else [
        r for r in rows if buku_kas.tanggal(r) == akhir.date() and not (r.get("waktu") or "").strip()
        and _efek(r, alias, a["id"])]
    tanpa_akun = [r for r in rows if _di_rentang(r, cutover, mulai, akhir) and buku_kas.arah(r)
                  and (alias.get((r.get("akun") or "").strip().lower()) is None
                       or (buku_kas.arah(r) == "transfer"
                           and alias.get((r.get("akun_tujuan") or "").strip().lower()) is None))]
    return {"akun": a["nama"], "id": a["id"], "titik": akhir, "saldo_nyata": int(saldo_nyata),
            "saldo_akun": s, "selisih": int(saldo_nyata) - s, "tanpa_jam": tanpa_jam,
            "tanpa_akun": tanpa_akun, "terakhir": lalu}


def _baris(r: dict) -> str:
    return f"  • {r.get('tanggal')} {r.get('waktu') or '--:--'} {r.get('item') or '-'} {rp(buku_kas.jumlah(r))}"


def teks_cek(h: dict) -> str:
    t = h["titik"]
    jam = "" if t.time() == time(23, 59, 59) else f" {t:%H:%M}"
    out = [f"🏦 Rekonsiliasi {h['akun']} — per {tgl_tampil(t)}{jam}",
           f"Saldo Nyata: {rp(h['saldo_nyata'])}",
           f"Saldo Akun (Buku Kas): {rp(h['saldo_akun'])}"]
    if h["selisih"] == 0:
        out.append("✅ Cocok")
    else:
        arah = "lebih kecil" if h["selisih"] < 0 else "lebih besar"
        out.append(f"Selisih: {rp(h['selisih'])} (Saldo Nyata {arah} dari Buku Kas)")
    if h["tanpa_jam"]:
        out += [f"ℹ️ {len(h['tanpa_jam'])} transaksi hari ini tanpa jam ikut dihitung:"]
        out += [_baris(r) for r in h["tanpa_jam"][:KANDIDAT_MAKS]]
    if h["selisih"] and h["tanpa_akun"]:
        sejak = f"rekonsiliasi {tgl_tampil(datetime.fromisoformat(h['terakhir']['titik']))}" \
            if h["terakhir"] else "cutover"
        out += [f"🔎 Kandidat penyebab — {len(h['tanpa_akun'])} transaksi tanpa akun sejak {sejak}:"]
        out += [_baris(r) for r in h["tanpa_akun"][:KANDIDAT_MAKS]]
        if len(h["tanpa_akun"]) > KANDIDAT_MAKS:
            out.append(f"  … dan {len(h['tanpa_akun']) - KANDIDAT_MAKS} lainnya")
    if h["selisih"]:
        out.append("Pilihan: 1) catat transaksi yang terlupa lalu cek lagi · 2) tutup sebagai Selisih "
                   "Rekonsiliasi · 3) biarkan terbuka")
    return "\n".join(out)


def simpan(path: Path, h: dict, cara: str, sekarang: datetime, no_resi: str = "") -> None:
    if cara not in CARA:
        raise Ditolak(f"--cara harus salah satu dari {', '.join(CARA)}")
    if cara == "cocok" and h["selisih"] != 0:
        raise Ditolak(f"Tidak cocok: selisih {rp(h['selisih'])}. Catat transaksi yang terlupa, tutup, "
                      "atau simpan dengan --cara dibiarkan.")
    with kunci_berkas(path):
        baru = not path.exists() or not path.read_text(encoding="utf-8").strip()
        with open(path, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=KOLOM, lineterminator="\n")
            if baru:
                w.writeheader()
            w.writerow({"waktu_cek": sekarang.replace(microsecond=0).isoformat(),
                        "titik": h["titik"].isoformat(), "akun": h["akun"],
                        "saldo_nyata": h["saldo_nyata"], "saldo_akun": h["saldo_akun"],
                        "selisih": h["selisih"], "cara": cara, "no_resi": no_resi})


def tx_selisih(h: dict, channel: str, pencatat: str) -> dict:
    """Transaksi Selisih Rekonsiliasi: arah mengikuti selisih, bertanggal di titik, pada Akun itu."""
    t = h["titik"]
    return {"tanggal": t.date().isoformat(), "waktu": t.strftime("%H:%M"),
            "tipe": "pengeluaran" if h["selisih"] < 0 else "pemasukan",
            "channel": channel, "pencatat": pencatat, "akun": h["akun"],
            "catatan": f"Rekonsiliasi: Saldo Nyata {rp(h['saldo_nyata'])}, Buku Kas {rp(h['saldo_akun'])}",
            "items": [{"kategori": buku_kas.KATEGORI_REKONSILIASI,
                       "item": f"Selisih rekonsiliasi {h['akun']}", "jumlah": abs(h["selisih"])}]}


def tutup(h: dict, channel: str, pencatat: str, uji: bool, sekarang: datetime) -> tuple:
    import catat  # catat memakai modul ini untuk peringatan; impor di sini menghindari siklus
    if h["selisih"] == 0:
        raise Ditolak("Tidak ada selisih untuk ditutup; simpan dengan --cara cocok.")
    kode, pesan = catat.catat(tx_selisih(h, channel, pencatat), uji=uji, rekonsiliasi=True)
    if kode != 0 or uji:
        return kode, pesan
    no_resi = re.search(r"no_resi (\S+)", pesan).group(1)
    simpan(path_catatan(), h, "selisih_ditutup", sekarang, no_resi)
    return 0, pesan


# ── Peringatan, laporan, Cermin ───────────────────────────────────────────
def peringatan(catatan: list, cfg, lama: list, baru: list) -> list:
    """Baris ⚠️ untuk tiap Akun yang Saldo Akun-nya per Rekonsiliasi terakhir bergeser karena
    perubahan `lama` → `baru` (baris yang diubah/dihapus/ditambah saja)."""
    if not catatan or not aktif(cfg):
        return []
    hasil = []
    for a in cfg["akun"]:
        c = terakhir(catatan, a["nama"])
        if not c:
            continue
        t = datetime.fromisoformat(c["titik"])
        geser = efek(baru, cfg, a["id"], t) - efek(lama, cfg, a["id"], t)
        if geser:
            hasil.append(f"⚠️ Transaksi ini bertanggal sebelum rekonsiliasi {a['nama']} {tgl_tampil(t)} "
                         f"({c['cara']}); Saldo Akun per titik itu bergeser {rp(geser)}.")
    return hasil


def peringatan_dari_berkas(bills_path: Path, lama: list, baru: list) -> list:
    """Untuk catat.py dan buku.py: peringatan tidak pernah memblokir atau menggagalkan penulisan."""
    try:
        return peringatan(muat_catatan(Path(bills_path).with_name("rekonsiliasi.csv")),
                          muat_akun(Path(bills_path).with_name("akun.json")), lama, baru)
    except (OSError, ValueError, KeyError, TypeError):
        return []


def baris_laporan(catatan: list, cfg, bulan: str):
    """Satu baris Laporan Bulanan: Akun tanpa Rekonsiliasi bertanggal di `bulan`, dan selisih terbuka."""
    if not aktif(cfg) or cfg["cutover"][:7] > bulan:
        return None
    dicek = {c["akun"] for c in catatan if c.get("titik", "")[:7] == bulan}
    belum = [a["nama"] for a in cfg["akun"] if a["nama"] not in dicek]
    terbuka = [(a["nama"], selisih_terbuka(catatan, a["nama"])) for a in cfg["akun"]]
    terbuka = [f"{n} {rp(s)}" for n, s in terbuka if s]
    nb = NAMA_BULAN[int(bulan[5:]) - 1]
    if not belum and not terbuka:
        return f"🏦 Rekonsiliasi {nb}: semua akun sudah dicek"
    bagian = ([f"belum dicek {', '.join(belum)}"] if belum else []) + \
             ([f"selisih terbuka {', '.join(terbuka)}"] if terbuka else [])
    return f"🏦 Rekonsiliasi {nb}: {' · '.join(bagian)}"


def ringkasan_akun(rows: list, cfg, catatan: list, hari_ini: date) -> list:
    """Tab Saldo per Akun: [nama, Saldo Akun hari ini, Terakhir Dicek, Saldo Nyata terakhir, Selisih Terbuka]."""
    akhir = datetime.combine(hari_ini, time(23, 59, 59))
    hasil = []
    for a in cfg["akun"]:
        c = terakhir(catatan, a["nama"])
        hasil.append([a["nama"], saldo_akun(rows, cfg, a["id"], akhir),
                      tgl_tampil(datetime.fromisoformat(c["titik"])) if c else "belum",
                      int(c["saldo_nyata"]) if c else "", selisih_terbuka(catatan, a["nama"])])
    return hasil


# ── CLI ───────────────────────────────────────────────────────────────────
def _rupiah(teks: str) -> int:
    t = re.sub(r"(?i)^rp\s*", "", str(teks).strip()).replace(".", "").replace(",", "")
    if not re.fullmatch(r"-?\d+", t):
        raise Ditolak(f"--saldo harus rupiah bulat (mis. 5230000 atau 5.230.000), dapat {teks!r}")
    return int(t)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Rekonsiliasi per Akun (ADR-0027)")
    p.add_argument("aksi", choices=("cek", "simpan", "tutup"))
    p.add_argument("--akun", required=True)
    p.add_argument("--saldo", required=True, help="Saldo Nyata, rupiah bulat")
    p.add_argument("--per", help="YYYY-MM-DD: Saldo Nyata per akhir hari itu (bawaan: saat ini)")
    p.add_argument("--cara", choices=("cocok", "dibiarkan"), help="untuk simpan")
    p.add_argument("--channel", help="untuk tutup")
    p.add_argument("--pencatat", help="untuk tutup")
    p.add_argument("--uji", action="store_true", help="tutup: Pratinjau, tidak menulis")
    p.add_argument("--sekarang", help=argparse.SUPPRESS)  # uji: anggap sekarang (ISO)
    a = p.parse_args(argv)
    sekarang = datetime.fromisoformat(a.sekarang) if a.sekarang else datetime.now()
    try:
        catatan = muat_catatan(path_catatan())
        h = cek(buku_kas.muat(Path(resi.BILLS_CSV)), muat_akun(), catatan, a.akun, _rupiah(a.saldo),
                titik(a.per, sekarang))
        if a.aksi == "cek":
            print(teks_cek(h))
            return 0
        if a.aksi == "simpan":
            if not a.cara:
                raise Ditolak("simpan butuh --cara cocok|dibiarkan")
            simpan(path_catatan(), h, a.cara, sekarang)
            print(f"OK rekonsiliasi dicatat | akun {h['akun']} | cara {a.cara} | selisih {rp(h['selisih'])}")
            return 0
        if not (a.channel and a.pencatat):
            raise Ditolak("tutup butuh --channel dan --pencatat")
        kode, pesan = tutup(h, a.channel, a.pencatat, a.uji, sekarang)
        print(f"🔁 Selisih Rekonsiliasi {h['akun']}: {rp(abs(h['selisih']))} "
              f"({'pengeluaran' if h['selisih'] < 0 else 'pemasukan'})\n{pesan}")
        return kode
    except Ditolak as e:
        print(f"ERROR {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
