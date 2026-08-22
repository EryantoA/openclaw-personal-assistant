#!/usr/bin/env python3
"""Penjaga kesehatan gateway — supaya kegagalan tidak lagi senyap.

    python3 scripts/periksa-kesehatan.py            # periksa & cetak saja (aman)
    python3 scripts/periksa-kesehatan.py --kirim    # kirim peringatan kalau ada masalah
    python3 scripts/periksa-kesehatan.py --paksa    # abaikan peredam ulangan
    python3 scripts/periksa-kesehatan.py --uji-kirim  # buktikan jalur kirim hidup

KENAPA ADA. Pada 21 Agustus 2026 OAuth `claude-cli` berhenti bisa disegarkan.
Akibatnya SETIAP giliran agent gagal — termasuk pencatatan bill-tracker lewat
WhatsApp — dan `cek_budget_malam` berstatus `error` selama dua hari **tanpa
mengabari siapa pun**. Cron yang gagal hanya mencatat error di dirinya sendiri.
Ini persis kelas kegagalan yang ADR-0009 tulis untuk dihindari, muncul lagi di
tempat lain.

PRINSIP: penjaga ini TIDAK BOLEH butuh model. Ia hanya membaca status dan
mengirim lewat `openclaw message send`, yang berjalan lewat channel plugin
Gateway — jadi ia justru hidup saat model mati. Kalau penjaga ini butuh model,
ia akan ikut mati bersama hal yang seharusnya ia laporkan.

BATASNYA, dan ini harus jujur disebut: penjaga ini berjalan DI DALAM Gateway.
Kalau Gateway sendiri mati total, ia ikut mati dan tidak ada yang mengabari.
Sinyal cadangan untuk kasus itu adalah `backup_harian` — kalau berkas backup
harian berhenti bertambah, Gateway-nya yang bermasalah.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
BILLS = AKAR / "data" / "bills.csv"
JEJAK = AKAR / "data" / "kesehatan-terakhir.json"
OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
AUTH_DB = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "openclaw-agent.sqlite"

CRON_MANDEK_JAM = 3        # cron dianggap mandek kalau lewat jadwal sekian jam
BILLS_DIAM_HARI = 3        # buku kas tidak bertambah sekian hari = mencurigakan
REDAM_JAM = 12             # jangan ulangi peringatan yang sama sebelum sekian jam


def jalankan(argv, timeout=25):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # noqa: BLE001
        return 1, "", str(e)


def waktu(ms):
    return datetime.fromtimestamp(ms / 1000) if ms else None


# ── Pemeriksaan ───────────────────────────────────────────────────────────
def periksa_cron():
    masalah = []
    kode, keluaran, galat = jalankan(["openclaw", "cron", "list", "--json"])
    if kode != 0:
        return [("KRITIS", "Tidak bisa membaca daftar cron", (galat or keluaran).strip()[:200])]
    try:
        jobs = json.loads(keluaran)["jobs"]
    except Exception as e:  # noqa: BLE001
        return [("KRITIS", "Keluaran cron list tidak terbaca", str(e))]

    sekarang = datetime.now()
    for j in jobs:
        nama = j.get("name", "?")
        if not j.get("enabled", True):
            masalah.append(("PERINGATAN", f"Cron '{nama}' nonaktif", "Sengaja dimatikan?"))
            continue
        if j.get("lastRunStatus") == "error":
            err = (j.get("lastRunError") or "").strip()
            kapan = waktu(j.get("lastRunAtMs"))
            masalah.append((
                "KRITIS",
                f"Cron '{nama}' GAGAL" + (f" ({kapan:%d %b %H:%M})" if kapan else ""),
                err[:220] or "tanpa keterangan",
            ))
        nr = waktu(j.get("nextRunAtMs"))
        lr = waktu(j.get("lastRunAtMs"))
        if nr and nr < sekarang - timedelta(hours=CRON_MANDEK_JAM):
            masalah.append((
                "KRITIS",
                f"Cron '{nama}' MANDEK",
                f"jadwal berikutnya {nr:%d %b %H:%M} sudah lewat "
                f"{int((sekarang - nr).total_seconds() // 3600)} jam; "
                f"terakhir jalan {lr:%d %b %H:%M}" if lr else "belum pernah jalan",
            ))
    return masalah


def profil_oauth():
    """Masa berlaku profil OAuth, dibaca sesegar mungkin.

    `openclaw models auth list` memaksa Gateway membaca ulang kredensial dari
    keychain Claude CLI, jadi angkanya kondisi sekarang. Membaca sqlite langsung
    lebih murah tapi bisa BASI: 22 Agu 2026 simpanan itu masih menyimpan catatan
    kedaluwarsa 01 Agu padahal token di keychain sudah disegarkan — pembacaan
    lewat CLI-lah yang menyamakannya. Sqlite cuma dipakai kalau CLI gagal.
    """
    kode, keluaran, _ = jalankan(["openclaw", "models", "auth", "list"])
    if kode == 0:
        hasil = []
        for nama, jenis, iso in re.findall(
            r"^-\s*(\S+)\s*\[([^;\]]+);\s*expires\s+(\S+)\]", keluaran, re.M
        ):
            if "oauth" not in jenis:
                continue
            try:
                exp = datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000
            except ValueError:
                continue
            hasil.append((nama, exp))
        if hasil:
            return hasil

    if not AUTH_DB.exists():
        return []
    kode, keluaran, _ = jalankan(["sqlite3", str(AUTH_DB), "select * from auth_profile_store;"])
    if kode != 0:
        return []
    hasil = []
    for potong in re.findall(r"\{.*\}", keluaran):
        try:
            d = json.loads(potong)
        except Exception:  # noqa: BLE001
            continue
        for nama, p in (d.get("profiles") or {}).items():
            if p.get("type") == "oauth" and p.get("expires"):
                hasil.append((nama, p["expires"]))
    return hasil


def periksa_oauth():
    """Token yang sudah lewat masa berlaku = penyegaran otomatis berhenti jalan.

    TIDAK ADA peringatan dini di sini, dan itu disengaja. Token akses OAuth cuma
    hidup hitungan jam lalu disegarkan sendiri, jadi ambang "hampir habis" dalam
    satuan hari akan menyala pada SETIAP pemeriksaan yang sehat — persis
    peringatan palsu yang ADR-0011 bilang mematikan kepercayaan. Yang benar-benar
    berarti hanya satu: masa berlakunya sudah lewat dan tidak ada yang
    memperbaruinya, seperti pada kejadian 21 Agustus 2026.
    """
    masalah = []
    sekarang = time.time() * 1000
    for nama, exp in profil_oauth():
        if exp >= sekarang:
            continue
        lewat = (sekarang - exp) / 86400000
        kapan = waktu(exp)
        masalah.append((
            "KRITIS",
            f"OAuth '{nama}' KEDALUWARSA",
            f"habis {kapan:%d %b %Y %H:%M} "
            f"({'kurang dari sehari' if lewat < 1 else f'{int(lewat)} hari'} lalu). "
            f"Penyegaran otomatis berhenti — jalankan `claude` lalu login ulang.",
        ))
    return masalah


def periksa_bills():
    """Buku kas yang berhenti bertambah = gejala jalur WhatsApp mati."""
    if not BILLS.exists():
        return [("PERINGATAN", "bills.csv tidak ditemukan", str(BILLS))]
    try:
        baris = BILLS.read_text(encoding="utf-8").strip().split("\n")
        kolom = baris[0].split(",")
        i = kolom.index("tanggal")
        tanggal = sorted(b.split(",")[i] for b in baris[1:] if b.strip())
        terakhir = datetime.strptime(tanggal[-1], "%Y-%m-%d")
    except Exception as e:  # noqa: BLE001
        return [("PERINGATAN", "bills.csv tidak terbaca", str(e)[:120])]
    diam = (datetime.now() - terakhir).days
    if diam >= BILLS_DIAM_HARI:
        return [("PERINGATAN", f"Buku kas diam {diam} hari",
                 f"transaksi terakhir {terakhir:%d %b %Y}. Kalau biasanya tiap hari, "
                 f"ini gejala jalur WhatsApp mati — bukan cuma sepi.")]
    return []


# ── Peredam ulangan ───────────────────────────────────────────────────────
def sidik(masalah):
    inti = "|".join(f"{t}:{j}" for t, j, _ in sorted(masalah))
    return hashlib.sha256(inti.encode()).hexdigest()[:16]


def boleh_kirim(s, paksa):
    if paksa:
        return True
    try:
        j = json.loads(JEJAK.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return True
    if j.get("sidik") != s:
        return True  # masalahnya berubah -> layak dikabari lagi
    return (time.time() - j.get("ts", 0)) > REDAM_JAM * 3600


def catat(s):
    JEJAK.write_text(json.dumps({"sidik": s, "ts": time.time(),
                                 "waktu": datetime.now().isoformat(timespec="seconds")},
                                indent=2), encoding="utf-8")


# ── Pengiriman ────────────────────────────────────────────────────────────
def tujuan_baku():
    """Nomor pemilik dari config — tidak ditulis keras di repo."""
    try:
        d = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
        n = d["channels"]["whatsapp"]["allowFrom"][0]
        return [("whatsapp", n)]
    except Exception:  # noqa: BLE001
        return []


def kirim(pesan, tujuan, kering=False):
    hasil = []
    for kanal, ke in tujuan:
        argv = ["openclaw", "message", "send", "--channel", kanal, "--target", ke, "-m", pesan]
        if kering:
            argv.append("--dry-run")
        kode, keluaran, galat = jalankan(argv, timeout=40)
        hasil.append((kanal, ke, kode == 0, (galat or keluaran).strip()[:160]))
    return hasil


def susun(masalah):
    kritis = [m for m in masalah if m[0] == "KRITIS"]
    baris = [f"🚨 *Gateway bermasalah* — {len(kritis)} kritis, "
             f"{len(masalah) - len(kritis)} peringatan",
             f"_{datetime.now():%d %b %Y %H:%M}_", ""]
    for tingkat, judul, rinci in sorted(masalah, key=lambda m: m[0] != "KRITIS"):
        baris.append(f"{'🔴' if tingkat == 'KRITIS' else '🟡'} *{judul}*")
        if rinci:
            baris.append(f"   {rinci}")
        baris.append("")
    baris.append("_Dikirim penjaga kesehatan, tanpa model — lihat scripts/periksa-kesehatan.py_")
    return "\n".join(baris).strip()


def main():
    ap = argparse.ArgumentParser(description="Penjaga kesehatan gateway (tanpa model)")
    ap.add_argument("--kirim", action="store_true", help="kirim peringatan kalau ada masalah")
    ap.add_argument("--paksa", action="store_true", help="abaikan peredam ulangan")
    ap.add_argument("--uji-kirim", action="store_true",
                    help="kirim pesan uji (--dry-run) untuk membuktikan jalur kirim hidup")
    ap.add_argument("--ke", action="append", metavar="KANAL:TUJUAN",
                    help="tujuan peringatan, bisa diulang (mis. telegram:12345678)")
    a = ap.parse_args()

    tujuan = ([tuple(x.split(":", 1)) for x in a.ke] if a.ke else tujuan_baku())

    if a.uji_kirim:
        if not tujuan:
            print("Tidak ada tujuan. Pakai --ke kanal:tujuan"); return 2
        for kanal, ke, ok, ket in kirim("uji penjaga kesehatan", tujuan, kering=True):
            print(f"{'✅' if ok else '❌'} {kanal} -> {ke}: {ket or 'siap'}")
        return 0

    masalah = periksa_cron() + periksa_oauth() + periksa_bills()

    if not masalah:
        print(f"✅ Sehat — {datetime.now():%d %b %H:%M}. Cron jalan, OAuth berlaku, buku kas hidup.")
        return 0

    laporan = susun(masalah)
    print(laporan)

    if not a.kirim:
        print("\n(tidak dikirim — tambahkan --kirim)")
        return 1

    s = sidik(masalah)
    if not boleh_kirim(s, a.paksa):
        print(f"\n(sudah dikabari <{REDAM_JAM} jam lalu dengan isi sama — tidak diulang)")
        return 1
    if not tujuan:
        print("\n❌ Tidak ada tujuan pengiriman."); return 2

    for kanal, ke, ok, ket in kirim(laporan, tujuan):
        print(f"\n{'✅ terkirim' if ok else '❌ GAGAL'} {kanal} -> {ke}" + (f": {ket}" if ket else ""))
    catat(s)
    return 1


if __name__ == "__main__":
    sys.exit(main())
