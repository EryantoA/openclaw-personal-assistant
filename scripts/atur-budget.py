#!/usr/bin/env python3
"""Mengubah Budget, ambang alert, dan Batas Kategori di data/budget.json (ADR-0024, ADR-0029).

Satu-satunya jalan bot menulis Pengaturan Budget — bot tidak mengedit budget.json dengan tangan.

    python3 scripts/atur-budget.py total 8jt
    python3 scripts/atur-budget.py alert 80
    python3 scripts/atur-budget.py kategori "Makan & Minum" 2,1jt     # label atau slug
    python3 scripts/atur-budget.py kategori food --hapus

Kode keluar: 0 tersimpan, 2 ditolak (berkas tidak diubah).
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resi  # noqa: E402
from tampilan import rp  # noqa: E402
from validasi import kunci_berkas  # noqa: E402

KHUSUS = {"opening_balance", "reconciliation", "transfer"}  # bukan belanja rutin
_SATUAN = {"jt": 1_000_000, "juta": 1_000_000, "rb": 1_000, "ribu": 1_000, "k": 1_000}


class Ditolak(Exception):
    pass


def nominal(teks: str) -> int:
    """'2,1 jt' / '2.1jt' / '600rb' / 'Rp 2.100.000' / '2100000' → rupiah bulat."""
    t = re.sub(r"(?i)^rp\.?\s*", "", str(teks).strip()).lower()
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(jt|juta|rb|ribu|k)", t)
    if m:
        return round(float(m.group(1).replace(",", ".")) * _SATUAN[m.group(2)])
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+|\d+", t):
        return int(t.replace(".", ""))
    raise Ditolak(f"nominal tidak terbaca: {teks!r} (contoh: 2100000, 2.100.000, 2,1jt, 600rb)")


def _muat(path: Path) -> tuple:
    teks = path.read_text(encoding="utf-8")
    return json.loads(teks), teks


def _tulis(path: Path, isi: dict, asli: str) -> None:
    teks = json.dumps(isi, ensure_ascii=False, indent=2) + ("\n" if asli.endswith("\n") else "")
    sementara = path.with_name(path.name + ".tmp")
    sementara.write_text(teks, encoding="utf-8")
    os.replace(sementara, path)


def cari_kategori(isi: dict, teks: str) -> str:
    label = isi.get("label_kategori") or {}
    t = teks.strip().casefold()
    sah = [k for k in isi.get("kategori_custom") or [] if k not in KHUSUS]
    slug = next((k for k in sah if t in (k.casefold(), str(label.get(k, "")).casefold())), None)
    if slug is None:
        if t in KHUSUS:
            raise Ditolak(f"{teks} bukan belanja rutin; tidak bisa diberi Batas Kategori")
        raise Ditolak(f"kategori {teks!r} tidak dikenal. Pilihan: "
                      f"{', '.join(label.get(k, k) for k in sah)}")
    return slug


def jalankan(a) -> str:
    path = Path(resi.BUDGET_JSON)
    with kunci_berkas(path):
        isi, asli = _muat(path)
        label = isi.get("label_kategori") or {}
        if a.aksi == "total":
            isi["budget_bulanan"] = nominal(a.nilai)
            pesan = f"OK Budget bulanan diset: {rp(isi['budget_bulanan'])}/bulan (belanja rutin)"
        elif a.aksi == "alert":
            m = re.fullmatch(r"(\d{1,3})\s*%?", (a.nilai or "").strip())
            if not m or not 1 <= int(m.group(1)) <= 100:
                raise Ditolak(f"alert harus 1–100 (persen), dapat {a.nilai!r}")
            isi["alert_persen"] = int(m.group(1))
            pesan = f"OK Alert diset: {isi['alert_persen']}% dari Budget dan dari tiap Batas Kategori"
        else:
            slug = cari_kategori(isi, a.kategori)
            nama = f"{label.get(slug, slug)} ({slug})"
            batas = dict(isi.get("budget_kategori") or {})
            if a.hapus:
                if slug not in batas:
                    raise Ditolak(f"{nama} tidak punya Batas Kategori")
                del batas[slug]
                pesan = f"OK Batas Kategori dihapus: {nama}; tetap dihitung ke Budget total"
            else:
                if not a.nilai:
                    raise Ditolak("sebutkan nominalnya, atau --hapus")
                batas[slug] = nominal(a.nilai)
                pesan = f"OK Batas Kategori diset: {nama}: {rp(batas[slug])}/bulan (belanja rutin)"
            isi["budget_kategori"] = batas
        _tulis(path, isi, asli)
    return pesan


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Atur Budget, alert, dan Batas Kategori (ADR-0029)")
    sub = p.add_subparsers(dest="aksi", required=True)
    for nama in ("total", "alert"):
        sub.add_parser(nama).add_argument("nilai")
    k = sub.add_parser("kategori")
    k.add_argument("kategori", help="label atau slug, mis. 'Makan & Minum' atau food")
    k.add_argument("nilai", nargs="?")
    k.add_argument("--hapus", action="store_true")
    a = p.parse_args(argv)
    try:
        print(jalankan(a))
        return 0
    except Ditolak as e:
        print(f"ERROR {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
