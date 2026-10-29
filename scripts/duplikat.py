"""Duplikat — satu tempat untuk tiga lapisnya (CONTEXT.md → Duplikat).

  Lapis 1  No Resi sama persis. Tidak bisa dilewati `paksa`.
  Lapis 2  Field `match_fields` (budget.json → duplicate_check) sama. Bisa dilewati `paksa`
           hanya setelah pengguna menegaskan itu transaksi baru.
  Audit    Baris tersimpan yang isinya sama di semua kolom kecuali no_resi (laporan saja).

Satu arti "sama" untuk satu nilai, di ketiganya (resi.norm_field): jumlah dibaca sebagai angka
bulat, teks dibandingkan tanpa huruf besar-kecil dan tanda baca, tanggal/waktu apa adanya.

Normalisasi dan pembacaan konfigurasi masih di resi.py; di sini hanya dipakai.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resi  # noqa: E402

KOLOM_AUDIT = [c for c in resi.COLUMNS if c != "no_resi"]


def cek(baris: list[dict], ada: list[dict], paksa: bool = False, saran_paksa: bool = True,
        lapis_1: bool = True) -> str | None:
    """Pesan DUPLICATE bila `baris` (satu Transaksi, boleh berbanyak item) mengulang salah satu
    baris di `ada`, None bila lolos. `ada` tidak boleh memuat baris Transaksi yang sama.

    `lapis_1=False` untuk mengubah Transaksi yang sudah tercatat: No Resi-nya memang sudah ada.
    """
    if lapis_1:
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
                saran = ("; ulangi dengan --paksa hanya bila pengguna menegaskan ini transaksi baru"
                         if saran_paksa else "")
                return (f"DUPLICATE {resi.row_summary(row)} | cocok pada: {', '.join(fields)} "
                        f"(aksi={cfg.get('aksi', 'tolak')}{saran})")
    return None


def kelompok(semua: list[dict]) -> list[list[dict]]:
    """Grup (>1 baris) yang isinya sama di semua kolom kecuali no_resi, urut kemunculan pertama.
    Laporan saja; tidak ada baris yang dibuang. Item berbeda dalam satu struk bukan kembar."""
    grup: dict[tuple, list[dict]] = {}
    for row in semua:
        kunci = tuple(resi.norm_field(c, row.get(c)) for c in KOLOM_AUDIT)
        grup.setdefault(kunci, []).append(row)
    return [g for g in grup.values() if len(g) > 1]
