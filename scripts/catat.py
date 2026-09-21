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

TIPE = {"pengeluaran", "pemasukan", "transfer"}
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


class Tolak(Exception):
    """Masukan tidak valid (exit 2)."""


def kategori_sah() -> set[str]:
    try:
        return set(json.loads(resi.BUDGET_JSON.read_text(encoding="utf-8"))["kategori_custom"])
    except Exception:
        return set()


def susun_baris(tx: dict, sekarang: datetime) -> list[dict]:
    """Validasi transaksi dan kembalikan baris-baris 12 kolom (no_resi belum diisi bila kosong)."""
    asing = sorted(set(tx) - KUNCI_TX)
    if asing:
        raise Tolak(f"kunci tidak dikenal {asing}; kunci yang sah: {sorted(KUNCI_TX)}")
    for f in ("tanggal", "tipe", "channel", "pencatat"):
        if not str(tx.get(f) or "").strip():
            raise Tolak(f"field `{f}` wajib diisi")
    tanggal = str(tx["tanggal"]).strip()
    try:
        date.fromisoformat(tanggal)
    except ValueError:
        raise Tolak(f"tanggal harus YYYY-MM-DD, dapat {tanggal!r}")
    tipe = str(tx["tipe"]).strip()
    if tipe not in TIPE:
        raise Tolak(f"tipe harus salah satu {sorted(TIPE)}, dapat {tipe!r}")
    waktu = str(tx.get("waktu") or "").strip() or sekarang.strftime("%H:%M")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", waktu):
        raise Tolak(f"waktu harus HH:MM, dapat {waktu!r}")
    akun_tujuan = str(tx.get("akun_tujuan") or "").strip()
    if akun_tujuan and tipe != "transfer":
        raise Tolak("akun_tujuan hanya untuk tipe=transfer")
    if tipe == "transfer" and not (str(tx.get("akun") or "").strip() and akun_tujuan):
        raise Tolak("tipe=transfer wajib mengisi akun (asal) dan akun_tujuan")

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
        kategori = str(it.get("kategori") or "").strip()
        if kategori == "opening_balance":
            raise Tolak("kategori opening_balance tidak boleh dibuat (ADR-0008)")
        if tipe == "transfer" or kategori == "transfer":
            # Transfer punya kategorinya sendiri, di luar kategori_custom (SKILL.md → Akun & Transfer)
            if tipe != kategori:
                raise Tolak(f"item {i}: tipe=transfer wajib berkategori transfer, dan sebaliknya")
        elif sah and kategori not in sah:
            raise Tolak(f"item {i}: kategori {kategori!r} tidak ada di budget.json kategori_custom")
        item = str(it.get("item") or "").strip()
        if not item:
            raise Tolak(f"item {i}: `item` kosong")
        jumlah = resi.norm_total(it.get("jumlah"))
        if not jumlah or int(jumlah) <= 0:
            raise Tolak(f"item {i}: jumlah harus angka rupiah > 0, dapat {it.get('jumlah')!r}")
        baris.append({
            "tanggal": tanggal,
            "tipe": tipe,
            "kategori": kategori,
            "item": item,
            "jumlah": jumlah,
            "catatan": str(it.get("catatan", tx.get("catatan")) or "").strip(),
            "channel": str(tx["channel"]).strip(),
            "pencatat": str(tx["pencatat"]).strip(),
            "akun": str(tx.get("akun") or "").strip(),
            "akun_tujuan": akun_tujuan,
            "waktu": waktu,
            "no_resi": str(tx.get("no_resi") or "").strip(),
        })
    return baris


def cek_duplikat(baris: list[dict], ada: list[dict], paksa: bool) -> str | None:
    """Pesan DUPLICATE bila tertolak, None bila lolos."""
    resi_baru = baris[0]["no_resi"]
    for row in ada:
        if (row.get("no_resi") or "").strip() == resi_baru:
            return (f"DUPLICATE no_resi {resi_baru} sudah ada: {resi.row_summary(row)} "
                    f"(Lapis 1 — tidak bisa dipaksa; struk yang sama sudah tercatat)")

    cfg = resi.load_duplicate_config()
    if paksa or not cfg.get("aktif", True):
        return None
    fields = cfg["match_fields"]
    for b in baris:
        kunci = {f: resi.norm_field(f, b.get(f)) for f in fields}
        for row in ada:
            if all(resi.norm_field(f, row.get(f)) == kunci[f] for f in fields):
                return (f"DUPLICATE {resi.row_summary(row)} | cocok pada: {', '.join(fields)} "
                        f"(aksi={cfg.get('aksi', 'tolak')}; ulangi dengan --paksa hanya bila "
                        f"pengguna menegaskan ini transaksi baru)")
    return None


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
            return 0, f"OK lolos cek (tidak ditulis): no_resi {baris[0]['no_resi']} waktu {baris[0]['waktu']}"

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
               f"waktu {baris[0]['waktu']}\n" + "\n".join(ditulis))


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
