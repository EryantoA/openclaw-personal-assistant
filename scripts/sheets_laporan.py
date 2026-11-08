"""Tab Laporan Cermin (ADR-0026): hanya-baca, dihitung skrip, ditimpa tiap sinkron.

Tidak ada definisi angka baru: Arus Kas Bulanan dan jumlah Transaksi dari buku_kas.ringkas, Saldo
Bersama dari buku_kas.saldo, Budget dari budget.pemakaian, saldo per Akun dari akun.saldo_per_akun.
Uang ditulis sebagai angka; formatnya diatur klien lewat `tata_*`.
"""
# Cron memakai /usr/bin/python3 3.9 — lihat catatan yang sama di resi.py.
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import akun  # noqa: E402
import budget  # noqa: E402
import buku_kas  # noqa: E402
import periode  # noqa: E402
from tampilan import nama_bulan, rp  # noqa: E402

SHEET_RINGKASAN = "Ringkasan Bulanan"
SHEET_AKUN = "Saldo per Akun"
SHEET_BUKU = "Buku Kas"
BULAN_PENDEK = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def sheet_kategori(tahun: int) -> str:
    return f"Per Kategori {tahun}"


def sheet_budget(tahun: int) -> str:
    return f"Budget {tahun}"


def _tanggal_sah(rows: list) -> list:
    return sorted(t for t in (buku_kas.tanggal(r) for r in rows) if t is not None)


def tahun_data(rows: list) -> list:
    """Tahun yang punya Transaksi bertanggal sah, terbaru dulu."""
    return sorted({t.year for t in _tanggal_sah(rows)}, reverse=True)


def urutan_tab(rows: list) -> list:
    tahunan = [n for t in tahun_data(rows) for n in (sheet_kategori(t), sheet_budget(t))]
    return [SHEET_RINGKASAN] + tahunan + [SHEET_AKUN, SHEET_BUKU]


def _bulan(d: date) -> str:
    return d.strftime("%Y-%m")


def _rentang(rows: list, hari_ini: date) -> tuple:
    """(bulan pertama pencatatan, bulan terakhir yang ditampilkan) sebagai 'YYYY-MM'."""
    tgl = _tanggal_sah(rows)
    return _bulan(tgl[0]), max(_bulan(hari_ini), _bulan(tgl[-1]))


# ── Ringkasan Bulanan ─────────────────────────────────────────────────────
def grid_ringkasan_bulanan(rows: list) -> list:
    """Satu baris per bulan yang punya baris terhitung. Jumlah Transaksi = No Resi unik tanpa
    Transfer dan Saldo Awal (ADR-0023), sama dengan laporan bot."""
    tak = {id(r) for r, _ in buku_kas.tak_terhitung(rows)}
    bulan_ada = sorted({_bulan(buku_kas.tanggal(r)) for r in rows if id(r) not in tak})
    grid = [["Bulan", "Jumlah Transaksi", "Pemasukan", "Pengeluaran", "Arus Kas Bulanan", "Saldo Awal",
             "Saldo Bersama Akhir Bulan"]]
    for b in bulan_ada:
        h = buku_kas.ringkas(rows, *periode.rentang_bulan(b))
        grid.append([nama_bulan(b), h["transaksi_pemasukan"] + h["transaksi_pengeluaran"], h["pemasukan"],
                     h["pengeluaran"], h["pemasukan"] - h["pengeluaran"], h["saldo_awal"] or "",
                     buku_kas.saldo(rows, per=periode.akhir_bulan(b))])
    return grid


# ── Per Kategori <tahun> ──────────────────────────────────────────────────
def _per_kategori(rows: list, arah: str, bulan: str) -> dict:
    """Total per Kategori (slug) satu arah dalam satu bulan; aturannya sama dengan buku_kas.ringkas."""
    mulai, akhir = periode.rentang_bulan(bulan)
    hasil: dict = {}
    for r in rows:
        tgl = buku_kas.tanggal(r)
        if tgl is None or buku_kas.arah(r) != arah or buku_kas.saldo_awal(r) or not mulai <= tgl <= akhir:
            continue
        k = (r.get("kategori") or "").strip().lower() or "other"
        hasil[k] = hasil.get(k, 0) + buku_kas.jumlah(r)
    return hasil


def grid_per_kategori(rows: list, tahun: int, label: dict, hari_ini: date) -> list:
    awal, akhir = _rentang(rows, hari_ini)
    bulan = [f"{tahun}-{m:02d}" for m in range(1, 13)]
    ada = [awal <= b <= akhir for b in bulan]
    header = [n + ("*" if b == awal else "") for n, b in zip(BULAN_PENDEK, bulan)]
    grid = [["Kategori"] + header + ["Total Tahun"]]

    def baris(judul, per_bulan):
        nilai = [v if a else "" for v, a in zip(per_bulan, ada)]
        return [judul] + nilai + [sum(v for v in nilai if v != "")]

    total = {}
    for arah, judul in (("pemasukan", "Pemasukan"), ("pengeluaran", "Pengeluaran")):
        per = [_per_kategori(rows, arah, b) if a else {} for b, a in zip(bulan, ada)]
        slug = {k for p in per for k in p}
        isi = [baris(label.get(k, k), [p.get(k, 0) for p in per]) for k in slug]
        grid += [[judul]] + sorted(isi, key=lambda b: (-b[-1], b[0]))
        total[arah] = [sum(p.values()) for p in per]
        grid += [baris(f"Total {judul}", total[arah]), []]
    grid.append(baris("Arus Kas Bulanan", [a - b for a, b in zip(total["pemasukan"], total["pengeluaran"])]))
    if awal[:4] == str(tahun):
        pertama = _tanggal_sah(rows)[0]
        grid += [[], [f"* Pencatatan dimulai {pertama.day} {BULAN_PENDEK[pertama.month - 1]} {pertama.year}; "
                      "bulan itu tidak penuh."]]
    return grid


# ── Budget <tahun> ────────────────────────────────────────────────────────
def _status(p: dict, alert: float) -> str:
    if p["persen"] is None:
        return "Budget belum diset"
    if p["persen"] >= 100:
        return "Lewat"
    return "Mendekati" if p["persen"] >= alert else "Aman"


def grid_budget(rows: list, tahun: int, atur: dict, hari_ini: date) -> list:
    """Semua bulan dibandingkan dengan batas yang berlaku sekarang; riwayat batas tidak disimpan."""
    batas = float(atur.get("budget_bulanan") or 0)
    if batas > 0:
        catatan = (f"Batas Budget saat ini {rp(batas)} dipakai sebagai acuan untuk semua bulan; "
                   "riwayat batas tidak disimpan, jadi status bulan lama bisa berbeda dari peringatan "
                   "yang dulu dikirim bot (ADR-0026).")
    else:
        catatan = "Budget belum diset di data/budget.json (budget_bulanan)."
    grid = [[catatan], ["Bulan", "Pengeluaran Rutin", "Budget", "Persen", "Di Luar Budget", "Status"]]
    awal, akhir = _rentang(rows, hari_ini) if _tanggal_sah(rows) else ("", "")
    alert = float(atur.get("alert_persen") or 80)
    for m in range(1, 13):
        b = f"{tahun}-{m:02d}"
        if not awal <= b <= akhir:
            grid.append([nama_bulan(b), "", "", "", "", ""])
            continue
        p = budget.pemakaian(rows, *periode.rentang_bulan(b), atur)
        grid.append([nama_bulan(b), p["rutin"], int(batas) if batas > 0 else "",
                     p["persen"] / 100 if p["persen"] is not None else "", p["besar"], _status(p, alert)])
    return grid


# ── Saldo per Akun ────────────────────────────────────────────────────────
def grid_saldo_akun(rows: list, cfg, hari_ini: date) -> list:
    """Hanya pemberitahuan sampai data/akun.json lengkap; angka per Akun tidak pernah ditebak
    (ADR-0010). Selisih dengan Saldo Bersama ditampilkan terbuka."""
    try:
        siap = isinstance(cfg, dict) and akun.aktif(cfg)
    except (KeyError, TypeError, AttributeError):
        siap = False
    if not siap:
        return [["Saldo per Akun belum aktif: saldo awal tiap Akun belum diisi di data/akun.json "
                 "(ADR-0010). Tab ini terisi sendiri setelah itu."]]
    nama = [a["nama"] for a in cfg["akun"]]
    grid = [["Bulan"] + nama + ["Jumlah Semua Akun", "Saldo Bersama", "Selisih", "Baris Tanpa Akun"]]
    mulai = cfg["cutover"][:7]
    akhir = max(_bulan(hari_ini), *(_bulan(t) for t in _tanggal_sah(rows)))
    b = mulai
    while b <= akhir:
        batas = periode.akhir_bulan(b)
        sampai = [r for r in rows if (buku_kas.tanggal(r) or date.max) <= batas]
        saldo, _, tanpa = akun.saldo_per_akun(sampai, cfg)
        per_akun = [int(saldo[a["id"]]) for a in cfg["akun"]]
        bersama = buku_kas.saldo(rows, per=batas)
        grid.append([nama_bulan(b)] + per_akun + [sum(per_akun), bersama, sum(per_akun) - bersama, tanpa])
        b = f"{int(b[:4]) + (b[5:] == '12')}-{int(b[5:]) % 12 + 1:02d}"
    return grid


# ── Tata letak (dipasang klien Google) ────────────────────────────────────
def tata_laporan(nama: str, grid: list) -> dict:
    """Tab Laporan: seluruhnya hanya-baca; uang berformat rupiah, persen untuk kolom Persen."""
    header = 1 if nama.startswith("Budget ") else 0
    judul = grid[header] if len(grid) > header else []
    fmt = {}
    for i, j in enumerate(judul):
        if i == 0 or j in ("Status", "Jumlah Transaksi", "Baris Tanpa Akun"):
            continue
        fmt[i] = "persen" if j == "Persen" else "rupiah"
    return {"baris_header": header, "beku_kolom": 1, "format": fmt, "hanya_baca": "semua"}
