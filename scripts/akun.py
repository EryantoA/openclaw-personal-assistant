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
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BILLS = ROOT / "data" / "bills.csv"
AKUN = ROOT / "data" / "akun.json"
SALDO_AWAL_RESI = "SALDO-AWAL"


def rupiah(n):
    return f"Rp {n:,.0f}".replace(",", ".")


def muat():
    rows = buku_kas.muat(BILLS)
    cfg = json.loads(AKUN.read_text(encoding="utf-8"))
    return rows, cfg


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
    nyata = buku_kas.saldo(rows, per=date.fromisoformat(cutover) - timedelta(days=1))
    tercatat = float(cfg["saldo_global_saat_cutover"])
    total = sum(float(a["saldo_awal"]) for a in cfg["akun"])

    if abs(tercatat - nyata) > 0.5:
        pesan.append(
            f"⚠️ saldo_global_saat_cutover ({rupiah(tercatat)}) TIDAK sama dengan "
            f"Saldo Bersama sungguhan pada {cutover} ({rupiah(nyata)}). "
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
    mulai = date.fromisoformat(cutover)
    for r in rows:
        tgl, tipe = buku_kas.tanggal(r), buku_kas.arah(r)
        if tgl is None or tipe is None or tgl < mulai:  # tak terhitung: dilaporkan main()
            continue
        a = alias.get((r.get("akun") or "").strip().lower())
        jumlah = buku_kas.jumlah(r)
        if tipe == "transfer":
            tuj = alias.get((r.get("akun_tujuan") or "").strip().lower())
            if a and tuj:
                saldo[a] -= jumlah
                saldo[tuj] += jumlah
            else:
                tanpa_akun += 1
            continue
        if not a:
            tanpa_akun += 1
            continue
        saldo[a] += jumlah if tipe == "pemasukan" else -jumlah
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
    print(f"\nSaldo Akun (sejak cutover {cfg['cutover']}):")
    for i, s in saldo.items():
        print(f"  {nama[i]:14s} {rupiah(s):>18s}")
    print(f"  {'TOTAL':14s} {rupiah(sum(saldo.values())):>18s}")

    glob = buku_kas.saldo(rows, per=date.max)
    if abs(glob - sum(saldo.values())) > 0.5:
        print(f"\n⚠️ Total akun tidak sama dengan Saldo Bersama ({rupiah(glob)}). "
              f"Selisih {rupiah(sum(saldo.values()) - glob)}.")
    if tanpa:
        print(f"\n⚠️ {tanpa} transaksi sejak cutover belum menyebut akun — "
              f"tidak masuk hitungan mana pun. Lengkapi kolom `akun`-nya.")
    tak = buku_kas.tak_terhitung(rows)
    if tak:
        print(f"\n⚠️ {len(tak)} transaksi tidak terhitung di saldo mana pun "
              f"(tanggal tidak sah / tipe tidak dikenal).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
