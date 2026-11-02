"""Pengirim pesan WhatsApp untuk cron tanpa model.

Dipakai tiga pesan otomatis: laporan-bulanan.py (ADR-0012), laporan-mingguan.py (ADR-0013),
dan check-bills.py --kirim (cron cek_budget_malam). Hidup di file sendiri supaya ketiganya
tidak saling bergantung — kalau satu skrip laporan rusak, pesan yang lain tetap terkirim.

Pengiriman lewat `openclaw message send`, channel plugin Gateway yang tidak menyentuh model.
periksa-kesehatan.py sengaja TIDAK memakai modul ini: penjaga harus berdiri sendiri (ADR-0011).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
# ID tujuan Kanal selain WhatsApp (config OpenClaw tidak menyimpannya). Data pribadi, di luar git;
# bentuknya ada di data/tujuan.json.example. Lihat docs/adr/0023.
TUJUAN_JSON = Path(__file__).resolve().parent.parent / "data" / "tujuan.json"
KANAL_LAIN = ("telegram", "discord")  # urutan kirim sesudah WhatsApp


def tujuan_baku():
    """Tujuan laporan otomatis, dari config — tidak ditulis keras di repo (ADR-0011).

    WhatsApp: nomor pertama `allowFrom` di config OpenClaw. Kanal lain: `data/tujuan.json`.
    Setiap tujuan yang dilewati (belum diisi, berkas rusak, isian tak sah, WhatsApp tak
    terbaca) disebut di stderr, tanpa menjatuhkan tujuan yang masih sah.
    """
    tujuan = []
    try:
        d = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
        tujuan.append(("whatsapp", d["channels"]["whatsapp"]["allowFrom"][0]))
    except Exception:  # noqa: BLE001
        # Tanpa peringatan, Telegram yang sukses menutupi hilangnya WhatsApp.
        print("(whatsapp tidak terbaca dari config OpenClaw, dilewati)", file=sys.stderr)
    lain = {}
    if TUJUAN_JSON.exists():
        try:
            lain = json.loads(TUJUAN_JSON.read_text(encoding="utf-8"))
            if not isinstance(lain, dict):
                raise ValueError("harus objek {kanal: id}")
        except Exception as e:  # noqa: BLE001
            print(f"(tujuan.json dilewati: {e})", file=sys.stderr)
            return tujuan
    for kanal in KANAL_LAIN:
        if kanal not in lain:
            print(f"(tujuan {kanal} belum dikonfigurasi, dilewati)", file=sys.stderr)
            continue
        ke = lain[kanal]
        if isinstance(ke, str) and ke.strip():
            tujuan.append((kanal, ke.strip()))
        else:
            print(f"(tujuan {kanal} di tujuan.json dilewati: harus teks tak kosong)", file=sys.stderr)
    return tujuan
    try:
        lain = json.loads(TUJUAN_JSON.read_text(encoding="utf-8"))
        if not isinstance(lain, dict):
            raise ValueError("harus objek {kanal: id}")
    except Exception as e:  # noqa: BLE001
        print(f"(tujuan.json dilewati: {e})", file=sys.stderr)
        return tujuan
    for kanal in KANAL_LAIN:
        if kanal not in lain:
            continue
        ke = lain[kanal]
        if isinstance(ke, str) and ke.strip():
            tujuan.append((kanal, ke.strip()))
        else:
            print(f"(tujuan {kanal} di tujuan.json dilewati: harus teks tak kosong)", file=sys.stderr)
    return tujuan


def kirim_sekali(pesan, kanal, ke):
    argv = ["openclaw", "message", "send", "--channel", kanal, "--target", ke, "-m", pesan]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        return p.returncode == 0, (p.stderr or p.stdout).strip()[:200]
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def kirim(pesan, kanal, ke, coba=None, jeda=60):
    """Coba ulang untuk WhatsApp (3 kali); Kanal lain sekali coba.

    Koneksi WhatsApp sesekali putus sesaat.

    Riwayat penjaga kesehatan 5–21 Sep 2026: 9 dari 39 run yang mencoba mengirim gagal secara
    acak ("Connection Closed", "No active WhatsApp Web listener"), sementara run sebelum dan
    sesudahnya terkirim. Risikonya pesan ganda kalau "gagal" ternyata sampai — lebih murah
    daripada pesan yang tidak sampai. Waktu terburuk WhatsApp ±300 dtk (3 x 60 dtk batas kirim
    + 2 jeda 60 dtk); Telegram dan Discord API biasa dan tidak diulang, supaya tiga tujuan
    tetap muat di batas waktu cron (docs/adr/0023).
    """
    if coba is None:
        coba = 3 if kanal == "whatsapp" else 1
    ket = ""
    for i in range(coba):
        if i:
            time.sleep(jeda)
        ok, ket = kirim_sekali(pesan, kanal, ke)
        if ok:
            return True, ket
        print(f"(percobaan {i + 1}/{coba} gagal: {ket[:120]})", file=sys.stderr)
    return False, ket


def kirim_ke_semua(pesan, tujuan, pakai=None):
    """Kirim ke tiap tujuan, satu per satu; yang gagal tidak menghentikan yang berikutnya.

    Mencetak satu baris per tujuan (dibaca log cron) dan mengembalikan
    [(kanal, ke, ok, keterangan), ...] sesuai urutan. Penelepon yang memutuskan apa arti
    "terkirim" dari hasil itu. `pakai` mengganti pengirim sekali jalan (tes laporan menimpa
    `kirim` di modulnya); bawaannya `kirim` modul ini, dicari saat dipanggil.
    """
    pakai = pakai or kirim
    hasil = []
    for kanal, ke in tujuan:
        ok, ket = pakai(pesan, kanal, ke)
        print(f"\n{'✅ terkirim' if ok else '❌ GAGAL'} {kanal} -> {ke}" + (f": {ket}" if ket else ""))
        hasil.append((kanal, ke, ok, ket))
    return hasil
