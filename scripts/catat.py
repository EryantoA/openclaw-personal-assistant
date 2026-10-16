#!/usr/bin/env python3
"""
catat.py — satu-satunya jalan bot menulis transaksi ke data/bills.csv.

Bot dulu menulis baris CSV dengan tangan (tool Edit/Write). Hasilnya: no_resi karangan
(`SS-20SEP-SOCK`), `waktu` kosong, dan — begitu `waktu` mulai diisi — baris 13 kolom karena
model menyalin pola `,,,,` dari baris lama. Skrip ini mengambil alih semua yang mekanis:
waktu default, no_resi (resi.py), cek duplikat dua lapis, validasi, dan penulisan 12 kolom.

Masukan: satu objek JSON di stdin = SATU transaksi (satu no_resi), boleh banyak item:

    python3 scripts/catat.py <<'EOF'
    {"tanggal": "2026-09-21", "tipe": "pengeluaran", "channel": "whatsapp", "pencatat": "Eryanto",
     "waktu": "14:30", "no_resi": "STRUK-000123", "catatan": "via GoPay",
     "items": [{"kategori": "food", "item": "Nasi goreng - Warung Ani", "jumlah": 25000}]}
    EOF

  Wajib : tanggal, tipe, channel, pencatat, items[].kategori, items[].item, items[].jumlah
  Opsional: waktu (default jam sekarang), no_resi (default resi.py --gen), catatan (per
            transaksi, bisa ditimpa per item), akun, akun_tujuan (hanya tipe=transfer)
  Transfer: tipe=transfer + kategori=transfer + akun + akun_tujuan wajib.

Opsi:
  --paksa   Lewati Lapis 2 (tanggal+waktu+jumlah dsb.). Hanya setelah pengguna menegaskan itu
            transaksi baru. Lapis 1 (no_resi sama persis) tidak pernah bisa dilewati.
  --uji     Validasi + cek duplikat saja, tidak menulis.

Keluaran / exit code:
  0  "OK tersimpan ..." lalu baris CSV yang ditulis (atau "OK lolos ..." dengan --uji)
  1  "DUPLICATE ..." — tidak ditulis
  2  "ERROR ..." — masukan tidak valid, tidak ditulis
"""

# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import argparse
import csv
import fcntl
import io
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import resi  # noqa: E402
from validasi import TIPE, Tolak, cek_baris, cek_duplikat_lapis2, kategori_sah  # noqa: E402,F401

KUNCI_TX = {"tanggal", "tipe", "channel", "pencatat", "items", "waktu", "no_resi", "catatan",
            "akun", "akun_tujuan"}
KUNCI_ITEM = {"kategori", "item", "jumlah", "catatan"}

CONTOH = (
    'Contoh masukan yang benar:\n'
    '{"tanggal": "2026-09-21", "tipe": "pengeluaran", "channel": "whatsapp", "pencatat": "Eryanto",\n'
    ' "items": [{"kategori": "food", "item": "Nasi goreng - Warung Ani", "jumlah": 25000}]}'
)
# Model yang menerima ERROR lalu tetap membalas "sudah dicatat" pernah terjadi (21 Sep 2026,
# resi karangan TESTBOT-21SEP). Kalimat ini ikut dicetak supaya tidak bisa terlewat.
TIDAK_TERSIMPAN = ("TIDAK ADA YANG DISIMPAN. Jangan membalas bahwa transaksi sudah dicatat; "
                   "perbaiki lalu jalankan lagi, atau sampaikan ke pengguna apa adanya.")


def susun_baris(tx: dict, sekarang: datetime) -> list[dict]:
    """Validasi transaksi dan kembalikan baris-baris 12 kolom (no_resi belum diisi bila kosong)."""
    asing = sorted(set(tx) - KUNCI_TX)
    if asing:
        raise Tolak(f"kunci tidak dikenal {asing}; kunci yang sah: {sorted(KUNCI_TX)}")
    dasar = {f: tx.get(f) for f in ("tanggal", "tipe", "channel", "pencatat", "akun", "akun_tujuan",
                                     "no_resi")}
    dasar["waktu"] = str(tx.get("waktu") or "").strip() or sekarang.strftime("%H:%M")

    items = tx.get("items")
    if not isinstance(items, list) or not items:
        raise Tolak("`items` harus daftar berisi minimal satu item")
    sah = kategori_sah()
    baris = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise Tolak(f"item {i} harus objek {{kategori, item, jumlah}}")
        asing = sorted(set(it) - KUNCI_ITEM)
        if asing:
            raise Tolak(f"item {i}: kunci tidak dikenal {asing}; kunci yang sah: {sorted(KUNCI_ITEM)}")
        baris.append(cek_baris({**dasar,
                                "kategori": it.get("kategori"),
                                "item": it.get("item"),
                                "jumlah": it.get("jumlah"),
                                "catatan": it.get("catatan", tx.get("catatan"))},
                               sah, awalan=f"item {i}: "))
    return baris


def cek_duplikat(baris: list[dict], ada: list[dict], paksa: bool) -> str | None:
    """Pesan DUPLICATE bila tertolak, None bila lolos."""
    resi_baru = baris[0]["no_resi"]
    for row in ada:
        if (row.get("no_resi") or "").strip() == resi_baru:
            return (f"DUPLICATE no_resi {resi_baru} sudah ada: {resi.row_summary(row)} "
                    f"(Lapis 1 — tidak bisa dipaksa; struk yang sama sudah tercatat)")

    return cek_duplikat_lapis2(baris, ada, paksa)


def catat(tx: dict, paksa: bool = False, uji: bool = False, sekarang: datetime | None = None) -> tuple[int, str]:
    try:
        baris = susun_baris(tx, sekarang or datetime.now())
    except Tolak as e:
        return 2, f"ERROR {e}"

    path = resi.BILLS_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8", newline="") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # dua pesan WhatsApp bersamaan tidak saling menimpa
        f.seek(0)
        isi = f.read()
        ada = list(csv.DictReader(io.StringIO(isi)))

        if not baris[0]["no_resi"]:
            resi_baru = resi.gen_resi(ada, date.fromisoformat(baris[0]["tanggal"]))
            for b in baris:
                b["no_resi"] = resi_baru

        pesan = cek_duplikat(baris, ada, paksa)
        if pesan:
            return 1, pesan
        if uji:
            return 0, (f"OK lolos cek (tidak ditulis): no_resi {baris[0]['no_resi']} waktu {baris[0]['waktu']} "
                       f"| tanggal {baris[0]['tanggal']} | pencatat {baris[0]['pencatat']}")

        # Ikuti akhir baris yang sudah dipakai file (bills.csv saat ini CRLF) supaya tidak campur
        eol = "\r\n" if "\r\n" in isi else "\n"
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=resi.COLUMNS, lineterminator=eol)
        if not isi.strip():
            w.writeheader()
        elif not isi.endswith("\n"):
            out.write(eol)
        for b in baris:
            w.writerow(b)
        f.write(out.getvalue())

    ditulis = out.getvalue().strip().splitlines()
    ditulis = [l for l in ditulis if not l.startswith("tanggal,")]
    return 0, (f"OK tersimpan {len(baris)} baris | no_resi {baris[0]['no_resi']} | "
               f"waktu {baris[0]['waktu']} | tanggal {baris[0]['tanggal']} | "
               f"pencatat {baris[0]['pencatat']}\n" + "\n".join(ditulis))


def main() -> int:
    p = argparse.ArgumentParser(description="Catat satu transaksi (JSON di stdin) ke bills.csv")
    p.add_argument("--paksa", action="store_true", help="Lewati cek duplikat Lapis 2")
    p.add_argument("--uji", action="store_true", help="Validasi + cek duplikat saja")
    args = p.parse_args()
    try:
        tx = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        kode, pesan = 2, f"ERROR JSON tidak valid: {e}"
    else:
        if isinstance(tx, dict):
            kode, pesan = catat(tx, paksa=args.paksa, uji=args.uji)
        else:
            kode, pesan = 2, "ERROR masukan harus satu objek JSON (satu transaksi)"
    print(pesan)
    if kode == 2:
        print(CONTOH)
    if kode != 0:
        print(TIDAK_TERSIMPAN)
    return kode


if __name__ == "__main__":
    sys.exit(main())
