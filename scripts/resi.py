#!/usr/bin/env python3
"""
resi.py — Helper No Resi & Deteksi Duplikat untuk Family Bill Tracker.

Dipanggil oleh AI agent via tool `code_execution`, atau manual dari terminal.

Mode:
  --gen
      Generate no resi otomatis untuk transaksi dari CHAT.
      Format: TRX-YYYYMMDD-XXXX (XXXX = 4 digit acak). Dijamin tidak bentrok
      dengan no_resi yang sudah ada di bills.csv.

  --fingerprint --merchant "<toko>" --date <YYYY-MM-DD> --total <angka>
      Hitung no resi deterministik untuk STRUK TANPA nomor tercetak.
      Format: STRUK-<hash8> dari (merchant + tanggal + total) yang dinormalisasi.
      Struk dengan isi sama -> hash sama -> bisa dideteksi saat dikirim ulang.

  --check "<no_resi>"
      LAPIS 1: cek apakah no_resi persis sudah ada di bills.csv.
      Ada -> print "DUPLICATE ..." (exit 1). Tidak -> print "OK ..." (exit 0).

  --check-dup --tanggal <tgl> --waktu <jam> --total <angka> [--item .. --kategori .. --catatan .. --pengirim ..]
      LAPIS 2: cek duplikat berbasis aturan multi-field yang dikonfigurasi di
      data/budget.json -> duplicate_check.match_fields. Semua field yang
      dikonfigurasi harus cocok baru dianggap duplikat.
      Duplikat -> print "DUPLICATE ..." (exit 1). Tidak -> print "OK ..." (exit 0).

  --find-dup
      Laporkan baris DUPLIKAT di bills.csv (isi identik, semua kolom sama kecuali no_resi).
      Ada -> print daftar grup duplikat (exit 1). Bersih -> "OK tidak ada duplikat" (exit 0).

  --backfill
      Isi no_resi (TRX-<tanggal baris>-XXXX unik) untuk baris lama yang belum punya.
      Menulis ulang bills.csv dengan header lengkap, membuat cadangan bills.csv.bak.
      Idempotent: baris yang sudah punya no_resi tidak diubah.

Exit code: 0 = OK / tidak duplikat, 1 = DUPLICATE ditemukan, 2 = error argumen.
"""

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from datetime import date, datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
BILLS_CSV = DATA_DIR / "bills.csv"
BUDGET_JSON = DATA_DIR / "budget.json"

# Header lengkap (kolom baru `waktu` & `no_resi` di akhir demi kompatibilitas data lama)
COLUMNS = [
    "tanggal",
    "tipe",
    "kategori",
    "item",
    "jumlah",
    "catatan",
    "channel",
    "pengirim",
    "jatuh_tempo",
    "waktu",
    "no_resi",
]

DEFAULT_DUPLICATE_CHECK = {
    "aktif": True,
    "match_fields": ["tanggal", "waktu", "jumlah"],
    "aksi": "tolak",
}

# Field yang valid untuk match_fields (harus nama kolom CSV yang bisa dibandingkan)
VALID_MATCH_FIELDS = {"tanggal", "waktu", "jumlah", "item", "kategori", "catatan", "pengirim"}


# ── Loaders ──────────────────────────────────────────────────
def load_bills() -> list[dict]:
    """Load semua baris dari bills.csv (list kosong jika belum ada / error)."""
    if not BILLS_CSV.exists():
        return []
    try:
        with open(BILLS_CSV, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def load_duplicate_config() -> dict:
    """Ambil konfigurasi duplicate_check dari budget.json (merge dengan default)."""
    if not BUDGET_JSON.exists():
        return dict(DEFAULT_DUPLICATE_CHECK)
    try:
        with open(BUDGET_JSON, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dict(DEFAULT_DUPLICATE_CHECK)

    cfg = {**DEFAULT_DUPLICATE_CHECK, **(data.get("duplicate_check") or {})}
    # Bersihkan match_fields: hanya field valid, buang duplikat, jaga urutan
    fields = []
    for fld in cfg.get("match_fields") or []:
        f = str(fld).strip().lower()
        if f == "total":  # alias ramah-user untuk kolom jumlah
            f = "jumlah"
        if f in VALID_MATCH_FIELDS and f not in fields:
            fields.append(f)
    cfg["match_fields"] = fields or list(DEFAULT_DUPLICATE_CHECK["match_fields"])
    return cfg


# ── Normalisasi ──────────────────────────────────────────────
def norm_total(value) -> str:
    """Normalisasi nominal ke string angka bulat. 'Rp 88.500' / '88,500' -> '88500'."""
    if value is None:
        return ""
    s = str(value)
    s = re.sub(r"[^\d,.-]", "", s)  # buang 'Rp', spasi, dll
    s = s.replace(".", "").replace(",", "")  # buang pemisah ribuan
    s = re.sub(r"[^\d-]", "", s)
    if not s or s == "-":
        return ""
    try:
        return str(int(float(s)))
    except (ValueError, TypeError):
        return ""


def norm_text(value) -> str:
    """Normalisasi teks: lowercase + buang non-alfanumerik (untuk merchant/item)."""
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def norm_field(field: str, value) -> str:
    """Normalisasi nilai per nama field untuk perbandingan duplikat."""
    if field == "jumlah":
        return norm_total(value)
    if field in ("item", "kategori", "catatan", "pengirim"):
        return norm_text(value)
    # tanggal, waktu: bandingkan apa adanya (trim)
    return str(value or "").strip()


# ── No Resi ──────────────────────────────────────────────────
def existing_resi(bills: list[dict]) -> set[str]:
    return {(r.get("no_resi") or "").strip() for r in bills if (r.get("no_resi") or "").strip()}


def gen_resi(bills: list[dict], for_date: date | None = None) -> str:
    """Generate TRX-YYYYMMDD-XXXX yang unik terhadap no_resi yang sudah ada."""
    taken = existing_resi(bills)
    d = (for_date or date.today()).strftime("%Y%m%d")
    for _ in range(10000):
        candidate = f"TRX-{d}-{random.randint(0, 9999):04d}"
        if candidate not in taken:
            return candidate
    # Sangat tidak mungkin: fallback pakai microsecond
    return f"TRX-{d}-{datetime.now().strftime('%H%M%S%f')}"


def fingerprint_resi(merchant: str, tanggal: str, total: str) -> str:
    """Kunci deterministik STRUK-<hash8> dari merchant+tanggal+total (dinormalisasi)."""
    basis = f"{norm_text(merchant)}|{str(tanggal or '').strip()}|{norm_total(total)}"
    h = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:8]
    return f"STRUK-{h}"


def row_summary(row: dict) -> str:
    """Ringkasan singkat sebuah baris untuk pesan duplikat."""
    tgl = (row.get("tanggal") or "").strip()
    jam = (row.get("waktu") or "").strip()
    item = (row.get("item") or "").strip()
    jumlah = norm_total(row.get("jumlah"))
    jumlah_fmt = f"Rp {int(jumlah):,}".replace(",", ".") if jumlah else "-"
    parts = [p for p in [tgl, jam, item, jumlah_fmt] if p]
    resi = (row.get("no_resi") or "").strip()
    prefix = f"[{resi}] " if resi else ""
    return prefix + " • ".join(parts)


# ── Modes ────────────────────────────────────────────────────
def do_gen() -> int:
    print(gen_resi(load_bills()))
    return 0


def do_fingerprint(args) -> int:
    if args.merchant is None or args.date is None or args.total is None:
        print("ERROR: --fingerprint butuh --merchant, --date, --total", file=sys.stderr)
        return 2
    print(fingerprint_resi(args.merchant, args.date, args.total))
    return 0


def do_check(no_resi: str) -> int:
    target = (no_resi or "").strip()
    if not target:
        print("ERROR: --check butuh nilai no_resi", file=sys.stderr)
        return 2
    for row in load_bills():
        if (row.get("no_resi") or "").strip() == target:
            print(f"DUPLICATE {row_summary(row)}")
            return 1
    print(f"OK belum tercatat: {target}")
    return 0


def do_check_dup(args) -> int:
    cfg = load_duplicate_config()
    if not cfg.get("aktif", True):
        print("OK duplicate_check nonaktif")
        return 0

    fields = cfg["match_fields"]
    # Kumpulkan nilai kandidat dari argumen (--total dipetakan ke kolom jumlah)
    candidate = {
        "tanggal": args.tanggal,
        "waktu": args.waktu,
        "jumlah": args.total,
        "item": args.item,
        "kategori": args.kategori,
        "catatan": args.catatan,
        "pengirim": args.pengirim,
    }

    missing = [f for f in fields if candidate.get(f) in (None, "")]
    if missing:
        print(
            f"ERROR: field wajib untuk aturan duplikat belum diisi: {', '.join(missing)} "
            f"(match_fields={fields})",
            file=sys.stderr,
        )
        return 2

    cand_norm = {f: norm_field(f, candidate.get(f)) for f in fields}

    for row in load_bills():
        if all(norm_field(f, row.get(f)) == cand_norm[f] for f in fields):
            print(f"DUPLICATE {row_summary(row)} | cocok pada: {', '.join(fields)}")
            return 1

    print(f"OK tidak ada duplikat (cek: {', '.join(fields)})")
    return 0


# Kolom penentu "duplikat": semua kolom data KECUALI no_resi (lihat export-excel.py).
DUP_KEY_COLUMNS = [c for c in COLUMNS if c != "no_resi"]


def _dup_value(col: str, value) -> str:
    return norm_total(value) if col == "jumlah" else str(value or "").strip()


def do_find_dup() -> int:
    """Laporkan baris yang isinya identik (semua kolom sama kecuali no_resi)."""
    bills = load_bills()
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for row in bills:
        key = tuple(_dup_value(col, row.get(col)) for col in DUP_KEY_COLUMNS)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    dup = [groups[k] for k in order if len(groups[k]) > 1]
    if not dup:
        print("OK tidak ada duplikat.")
        return 0

    total = sum(len(g) for g in dup)
    print(f"DUPLICATE {total} baris dalam {len(dup)} grup:")
    for gi, group in enumerate(dup, start=1):
        print(f"  Grup {gi} ({len(group)} baris):")
        for row in group:
            print(f"    - {row_summary(row)}")
    return 1


def do_backfill() -> int:
    if not BILLS_CSV.exists():
        print("OK tidak ada bills.csv, tidak ada yang di-backfill.")
        return 0

    bills = load_bills()
    if not bills:
        print("OK bills.csv kosong, tidak ada yang di-backfill.")
        return 0

    taken = existing_resi(bills)
    added = 0
    for row in bills:
        if (row.get("no_resi") or "").strip():
            continue
        # Tanggal baris untuk bagian YYYYMMDD (fallback ke hari ini bila invalid)
        tgl = (row.get("tanggal") or "").strip()
        try:
            for_date = datetime.strptime(tgl, "%Y-%m-%d").date()
        except ValueError:
            for_date = date.today()
        d = for_date.strftime("%Y%m%d")
        # generate unik terhadap yang sudah ada + yang baru dibuat
        candidate = None
        for _ in range(10000):
            c = f"TRX-{d}-{random.randint(0, 9999):04d}"
            if c not in taken:
                candidate = c
                break
        if candidate is None:
            candidate = f"TRX-{d}-{datetime.now().strftime('%H%M%S%f')}"
        row["no_resi"] = candidate
        taken.add(candidate)
        added += 1

    if added == 0:
        print("OK semua baris sudah punya no_resi (idempotent, tidak ada perubahan).")
        return 0

    # Cadangan lalu tulis ulang dengan header lengkap
    backup = BILLS_CSV.with_suffix(".csv.bak")
    backup.write_bytes(BILLS_CSV.read_bytes())

    with open(BILLS_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in bills:
            writer.writerow({col: row.get(col, "") for col in COLUMNS})

    print(f"OK backfill selesai: {added} baris diberi no_resi. Cadangan: {backup.name}")
    return 0


# ── Main ─────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Helper No Resi & Deteksi Duplikat")
    parser.add_argument("--gen", action="store_true", help="Generate no resi otomatis (chat)")
    parser.add_argument("--fingerprint", action="store_true", help="Hitung no resi struk (STRUK-<hash8>)")
    parser.add_argument("--check", metavar="NO_RESI", help="Cek no_resi sama persis (Lapis 1)")
    parser.add_argument("--check-dup", action="store_true", dest="check_dup",
                        help="Cek duplikat multi-field configurable (Lapis 2)")
    parser.add_argument("--find-dup", action="store_true", dest="find_dup",
                        help="Laporkan baris duplikat di bills.csv (isi identik kecuali no_resi)")
    parser.add_argument("--backfill", action="store_true", help="Isi no_resi baris lama")

    # Argumen data
    parser.add_argument("--merchant")
    parser.add_argument("--date")
    parser.add_argument("--total")
    parser.add_argument("--tanggal")
    parser.add_argument("--waktu")
    parser.add_argument("--item")
    parser.add_argument("--kategori")
    parser.add_argument("--catatan")
    parser.add_argument("--pengirim")

    args = parser.parse_args()

    if args.gen:
        return do_gen()
    if args.fingerprint:
        return do_fingerprint(args)
    if args.check is not None:
        return do_check(args.check)
    if args.check_dup:
        return do_check_dup(args)
    if args.find_dup:
        return do_find_dup()
    if args.backfill:
        return do_backfill()

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
