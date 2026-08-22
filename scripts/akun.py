#!/usr/bin/env python3
"""Saldo per akun + penegakan aturan konsistensi cutover.

Saldo global (ADR-0001) tetap satu-satunya kebenaran kas keluarga. Fitur akun
memecahnya jadi beberapa kantong, tapi HANYA sejak tanggal cutover — 357 baris
sebelum itu tidak menyebut akun, jadi saldo per akun tidak bisa dihitung mundur.

    python3 scripts/akun.py            # saldo per akun + pemeriksaan
    python3 scripts/akun.py --cek      # hanya pemeriksaan konsistensi (exit 1 bila gagal)

Aturan yang ditegakkan: jumlah semua `saldo_awal` HARUS sama dengan Saldo global
pada tanggal cutover. Selisih dilaporkan terbuka, tidak pernah diserap diam-diam
(ADR-0010).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BILLS = ROOT / "data" / "bills.csv"
AKUN = ROOT / "data" / "akun.json"
SALDO_AWAL_RESI = "SALDO-AWAL"


def rupiah(n):
    return f"Rp {n:,.0f}".replace(",", ".")


def jumlah(row):
    try:
        return float(row.get("jumlah") or 0)
    except (ValueError, TypeError):
        return 0.0


def muat():
    rows = list(csv.DictReader(BILLS.open(encoding="utf-8", newline="")))
    cfg = json.loads(AKUN.read_text(encoding="utf-8"))
    return rows, cfg


def saldo_global(rows, sampai=None):
    """Saldo kumulatif hingga `sampai` (eksklusif). Transfer tidak pernah ikut."""
    s = 0.0
    for r in rows:
        if sampai and r.get("tanggal", "") >= sampai:
            continue
        tipe = (r.get("tipe") or "pengeluaran").strip().lower()
        if tipe == "transfer":
            continue
        s += jumlah(r) if tipe == "pemasukan" else -jumlah(r)
    return s


def aktif(cfg):
    return all(a.get("saldo_awal") is not None for a in cfg["akun"]) and \
           cfg.get("saldo_global_saat_cutover") is not None


def periksa(rows, cfg):
    """Return (ok, list pesan)."""
    pesan = []
    if not aktif(cfg):
        kosong = [a["nama"] for a in cfg["akun"] if a.get("saldo_awal") is None]
        pesan.append("Fitur akun BELUM aktif — saldo_awal masih kosong: " + ", ".join(kosong))
        pesan.append("Isi data/akun.json dulu (lihat akun.json.example).")
        return False, pesan

    cutover = cfg["cutover"]
    nyata = saldo_global(rows, sampai=cutover)
    tercatat = float(cfg["saldo_global_saat_cutover"])
    total = sum(float(a["saldo_awal"]) for a in cfg["akun"])

    if abs(tercatat - nyata) > 0.5:
        pesan.append(
            f"⚠️ saldo_global_saat_cutover ({rupiah(tercatat)}) TIDAK sama dengan "
            f"Saldo global sungguhan pada {cutover} ({rupiah(nyata)}). "
            f"Selisih {rupiah(tercatat - nyata)}."
        )
    if abs(total - tercatat) > 0.5:
        pesan.append(
            f"⚠️ Jumlah saldo_awal semua akun ({rupiah(total)}) TIDAK sama dengan "
            f"saldo_global_saat_cutover ({rupiah(tercatat)}). "
            f"Selisih {rupiah(total - tercatat)}. Perbaiki di data/akun.json — "
            f"jangan dibiarkan, saldo per akun jadi tidak bermakna."
        )
    return (not pesan), (pesan or [f"✅ Konsisten: {rupiah(total)} pada {cutover}"])


def saldo_per_akun(rows, cfg):
    cutover = cfg["cutover"]
    nama = {a["id"]: a["nama"] for a in cfg["akun"]}
    alias = {a["nama"].lower(): a["id"] for a in cfg["akun"]}
    alias.update({a["id"]: a["id"] for a in cfg["akun"]})

    saldo = {a["id"]: float(a["saldo_awal"]) for a in cfg["akun"]}
    tanpa_akun = 0
    for r in rows:
        if r.get("tanggal", "") < cutover:
            continue
        tipe = (r.get("tipe") or "pengeluaran").strip().lower()
        a = alias.get((r.get("akun") or "").strip().lower())
        if tipe == "transfer":
            tuj = alias.get((r.get("akun_tujuan") or "").strip().lower())
            if a and tuj:
                saldo[a] -= jumlah(r)
                saldo[tuj] += jumlah(r)
            else:
                tanpa_akun += 1
            continue
        if not a:
            tanpa_akun += 1
            continue
        saldo[a] += jumlah(r) if tipe == "pemasukan" else -jumlah(r)
    return saldo, nama, tanpa_akun


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cek", action="store_true", help="hanya pemeriksaan konsistensi")
    a = ap.parse_args()

    rows, cfg = muat()
    ok, pesan = periksa(rows, cfg)
    for m in pesan:
        print(m)
    if a.cek or not ok:
        return 0 if ok else 1

    saldo, nama, tanpa = saldo_per_akun(rows, cfg)
    print(f"\nSaldo per akun (sejak cutover {cfg['cutover']}):")
    for i, s in saldo.items():
        print(f"  {nama[i]:14s} {rupiah(s):>18s}")
    print(f"  {'TOTAL':14s} {rupiah(sum(saldo.values())):>18s}")

    glob = saldo_global(rows)
    if abs(glob - sum(saldo.values())) > 0.5:
        print(f"\n⚠️ Total akun tidak sama dengan Saldo global ({rupiah(glob)}). "
              f"Selisih {rupiah(sum(saldo.values()) - glob)}.")
    if tanpa:
        print(f"\n⚠️ {tanpa} transaksi sejak cutover belum menyebut akun — "
              f"tidak masuk hitungan mana pun. Lengkapi kolom `akun`-nya.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
