#!/usr/bin/env python3
"""Laporan Bulanan — satu bulan yang sudah tutup, disusun tanpa model (ADR-0012).

    python3 scripts/laporan-bulanan.py                   # bulan lalu, tampilkan saja
    python3 scripts/laporan-bulanan.py --bulan 2026-08   # bulan tertentu, tampilkan saja
    python3 scripts/laporan-bulanan.py --kirim           # kirim, lalu simpan angkanya (cron)

Tanpa --kirim, skrip ini TIDAK PERNAH MENULIS apa pun. Itu yang dipakai bot saat seseorang
meminta `laporan bulan lalu` lewat chat: angkanya identik dengan versi tanggal 6, tapi tidak
menghabiskan Koreksi yang belum sempat disebut laporan resmi.

Dengan --kirim, angka yang dilaporkan disimpan di data/laporan-bulanan.json HANYA setelah
pesannya terkirim. Kalau pengiriman gagal, skrip keluar dengan kode 1 supaya cron tercatat
`error` dan penjaga kesehatan menangkapnya — dan tidak ada yang disimpan, supaya Koreksi bulan
depan tidak dihitung terhadap angka yang tak pernah diterima siapa pun.

Aturan hitung (sama dengan scripts/export-excel.py dan SKILL.md):
  - `transfer` dilewati seluruhnya — uangnya cuma pindah akun.
  - `opening_balance` ikut Saldo, tapi tidak ikut Pemasukan maupun Arus Kas Bulan.
  - Saldo kumulatif dari baris pertama; baris tanpa tanggal valid tidak ikut apa pun.
  - Baris tanpa `tipe` dianggap pengeluaran (data lama).
"""
import argparse
import csv
import importlib.util
import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
DATA = AKAR / "data"
BILLS = DATA / "bills.csv"
BUDGET = DATA / "budget.json"
SIMPANAN = DATA / "laporan-bulanan.json"
OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"

KATEGORI_SALDO_AWAL = "opening_balance"
KATEGORI_TERATAS = 5
NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
              "Agustus", "September", "Oktober", "November", "Desember"]


# ── Membaca ───────────────────────────────────────────────────────────────
def muat_baris(path=None):
    path = path or BILLS
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def muat_json(path, bawaan):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return bawaan


def tipe(r):
    return (r.get("tipe") or "pengeluaran").strip().lower()


def jumlah(r):
    try:
        return float(r.get("jumlah") or 0)
    except (TypeError, ValueError):
        return 0.0


def kunci_bulan(r):
    """'YYYY-MM' dari kolom tanggal, atau None kalau tanggalnya tidak valid."""
    try:
        return date.fromisoformat((r.get("tanggal") or "").strip()).strftime("%Y-%m")
    except ValueError:
        return None


# ── Menghitung ────────────────────────────────────────────────────────────
def arus_per_bulan(baris):
    """{bulan: {pemasukan, pengeluaran, saldo_awal}} untuk semua bulan bertanggal."""
    hasil = {}
    for r in baris:
        b = kunci_bulan(r)
        t = tipe(r)
        if b is None or t == "transfer":
            continue
        h = hasil.setdefault(b, {"pemasukan": 0.0, "pengeluaran": 0.0, "saldo_awal": 0.0})
        if (r.get("kategori") or "").strip().lower() == KATEGORI_SALDO_AWAL:
            h["saldo_awal"] += jumlah(r)
        elif t == "pemasukan":
            h["pemasukan"] += jumlah(r)
        elif t == "pengeluaran":
            h["pengeluaran"] += jumlah(r)
    return hasil


def saldo_akhir(arus, bulan):
    """Saldo kumulatif per akhir `bulan`."""
    return sum(h["saldo_awal"] + h["pemasukan"] - h["pengeluaran"]
               for b, h in arus.items() if b <= bulan)


def per_kategori(baris, bulan):
    total = {}
    for r in baris:
        if kunci_bulan(r) == bulan and tipe(r) == "pengeluaran":
            k = (r.get("kategori") or "other").strip().lower() or "other"
            total[k] = total.get(k, 0.0) + jumlah(r)
    return total


def jumlah_transaksi(baris, bulan):
    return sum(1 for r in baris if kunci_bulan(r) == bulan and tipe(r) != "transfer"
               and (r.get("kategori") or "").strip().lower() != KATEGORI_SALDO_AWAL)


def bulan_sebelum(bulan):
    t, b = map(int, bulan.split("-"))
    return f"{t - 1}-12" if b == 1 else f"{t}-{b - 1:02d}"


def cari_koreksi(arus, simpanan, bulan_laporan):
    """Bulan yang pernah dilaporkan dan Pemasukan/Pengeluarannya berubah sejak itu.

    Hanya bulan asal perubahan yang disebut: Saldo akhir bulan-bulan sesudahnya memang ikut
    bergeser, tapi itu akibat, bukan koreksi tersendiri (CONTEXT.md → Koreksi).
    """
    koreksi = []
    for b, lama in sorted(simpanan.get("bulan", {}).items()):
        if b == bulan_laporan:
            continue
        kini = arus.get(b, {"pemasukan": 0.0, "pengeluaran": 0.0})
        d_in = round(kini["pemasukan"] - lama["pemasukan"])
        d_out = round(kini["pengeluaran"] - lama["pengeluaran"])
        if d_in or d_out:
            koreksi.append({"bulan": b, "pemasukan": d_in, "pengeluaran": d_out,
                            "saldo_akhir": saldo_akhir(arus, b)})
    return koreksi


def perkiraan_absen(bulan):
    """Pakai aturan pencocokan yang sama dengan cek malam, bukan salinannya."""
    spec = importlib.util.spec_from_file_location("check_bills", AKAR / "scripts" / "check-bills.py")
    cb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cb)
    t, b = map(int, bulan.split("-"))
    return cb.perkiraan_absen(t, b, None)


# ── Menyusun ──────────────────────────────────────────────────────────────
def rp(x):
    return ("-" if x < 0 else "") + f"Rp {abs(x):,.0f}".replace(",", ".")


def nama_bulan(bulan):
    t, b = map(int, bulan.split("-"))
    return f"{NAMA_BULAN[b - 1]} {t}"


def susun(bulan, baris, budget, simpanan, absen):
    arus = arus_per_bulan(baris)
    h = arus.get(bulan, {"pemasukan": 0.0, "pengeluaran": 0.0, "saldo_awal": 0.0})
    arus_kas = h["pemasukan"] - h["pengeluaran"]
    lalu = bulan_sebelum(bulan)
    nb, nl = nama_bulan(bulan), NAMA_BULAN[int(lalu[5:]) - 1]

    out = [f"📊 *LAPORAN BULANAN — {nb}*", "",
           f"📥 Pemasukan:   {rp(h['pemasukan'])}",
           f"📤 Pengeluaran: {rp(h['pengeluaran'])}  ({jumlah_transaksi(baris, bulan)} transaksi)",
           f"{'💚' if arus_kas >= 0 else '🔴'} Arus Kas Bulan: {rp(arus_kas)}",
           f"🏦 Saldo akhir {NAMA_BULAN[int(bulan[5:]) - 1]}: {rp(saldo_akhir(arus, bulan))}"]

    batas = float(budget.get("budget_bulanan") or 0)
    if batas > 0:
        out += ["", f"💰 Budget: {rp(h['pengeluaran'])} dari {rp(batas)} "
                    f"({h['pengeluaran'] / batas * 100:.0f}%)"]

    kini, dulu = per_kategori(baris, bulan), per_kategori(baris, lalu)
    if kini:
        out += ["", f"🏷️ {min(KATEGORI_TERATAS, len(kini))} kategori terbesar"]
        for k, v in sorted(kini.items(), key=lambda kv: -kv[1])[:KATEGORI_TERATAS]:
            pct = v / h["pengeluaran"] * 100 if h["pengeluaran"] else 0
            if k not in dulu:
                banding = f"baru, tidak ada di {nl}"
            else:
                d = v - dulu[k]
                banding = f"{'▲' if d >= 0 else '▼'} {rp(abs(d))} dari {nl}"
            out.append(f"  {k}  {rp(v)}  ({pct:.0f}%)  {banding}")

    if absen:
        out += ["", "📅 Perkiraan yang tidak muncul"]
        for e in absen:
            arah = "masuk" if (e.get("arah") or "keluar").strip().lower() == "masuk" else "keluar"
            out.append(f"  • {e.get('nama') or e.get('id')} — {rp(float(e['nominal']))}, "
                       f"biasanya tgl {int(e['tanggal_biasanya'])}, tidak {arah}")

    for k in cari_koreksi(arus, simpanan, bulan):
        bagian = []
        if k["pengeluaran"]:
            bagian.append(f"pengeluaran {'naik' if k['pengeluaran'] > 0 else 'turun'} "
                          f"{rp(abs(k['pengeluaran']))}")
        if k["pemasukan"]:
            bagian.append(f"pemasukan {'naik' if k['pemasukan'] > 0 else 'turun'} "
                          f"{rp(abs(k['pemasukan']))}")
        out += ["", f"⚠️ Koreksi {nama_bulan(k['bulan'])}: {', '.join(bagian)} sejak dilaporkan. "
                    f"Saldo akhir {NAMA_BULAN[int(k['bulan'][5:]) - 1]} sekarang "
                    f"{rp(k['saldo_akhir'])}."]

    out += ["", "_Dihitung scripts/laporan-bulanan.py, tanpa model_"]
    return "\n".join(out)


def simpanan_baru(simpanan, bulan, arus):
    """Catat angka bulan yang dilaporkan, dan perbarui bulan yang Koreksinya baru disebut."""
    kini = datetime.now().isoformat(timespec="seconds")
    isi = {"bulan": dict(simpanan.get("bulan", {}))}
    for k in cari_koreksi(arus, simpanan, bulan):
        h = arus.get(k["bulan"], {"pemasukan": 0.0, "pengeluaran": 0.0})
        isi["bulan"][k["bulan"]] = {**isi["bulan"][k["bulan"]],
                                    "pemasukan": round(h["pemasukan"]),
                                    "pengeluaran": round(h["pengeluaran"]),
                                    "dikoreksi": kini}
    h = arus.get(bulan, {"pemasukan": 0.0, "pengeluaran": 0.0})
    isi["bulan"][bulan] = {"pemasukan": round(h["pemasukan"]),
                           "pengeluaran": round(h["pengeluaran"]),
                           "saldo_akhir": round(saldo_akhir(arus, bulan)),
                           "dilaporkan": kini}
    return isi


# ── Mengirim ──────────────────────────────────────────────────────────────
def tujuan_baku():
    """Nomor pemilik dari config — tidak ditulis keras di repo (ADR-0011)."""
    try:
        d = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
        return [("whatsapp", d["channels"]["whatsapp"]["allowFrom"][0])]
    except Exception:  # noqa: BLE001
        return []


def kirim_sekali(pesan, kanal, ke):
    argv = ["openclaw", "message", "send", "--channel", kanal, "--target", ke, "-m", pesan]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        return p.returncode == 0, (p.stderr or p.stdout).strip()[:200]
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def kirim(pesan, kanal, ke, coba=3, jeda=60):
    """Coba ulang: koneksi WhatsApp sesekali putus sesaat.

    Riwayat penjaga kesehatan 5–21 Sep 2026 mencatat 9 kegagalan kirim acak ("Connection
    Closed", "No active WhatsApp Web listener") di antara ~60 run, sementara run sebelum dan
    sesudahnya terkirim. Pesan yang terbit sebulan sekali tidak boleh bergantung pada menit
    yang kebetulan buruk. Risikonya pesan ganda kalau "gagal" ternyata sampai — lebih murah
    daripada laporan yang tidak sampai.
    """
    ket = ""
    for i in range(coba):
        if i:
            time.sleep(jeda)
        ok, ket = kirim_sekali(pesan, kanal, ke)
        if ok:
            return True, ket
        print(f"(percobaan {i + 1}/{coba} gagal: {ket[:120]})", file=sys.stderr)
    return False, ket


def main(argv=None):
    ap = argparse.ArgumentParser(description="Laporan Bulanan, tanpa model (ADR-0012)")
    ap.add_argument("--bulan", metavar="YYYY-MM", help="bulan yang dilaporkan (bawaan: bulan lalu)")
    ap.add_argument("--kirim", action="store_true", help="kirim, lalu simpan angka yang dilaporkan")
    ap.add_argument("--ke", action="append", metavar="KANAL:TUJUAN",
                    help="tujuan, bisa diulang (bawaan: nomor pemilik dari config)")
    a = ap.parse_args(argv)

    bulan = a.bulan or bulan_sebelum(date.today().strftime("%Y-%m"))
    try:
        datetime.strptime(bulan, "%Y-%m")
    except ValueError:
        ap.error(f"--bulan tidak valid: {bulan}")

    baris = muat_baris()
    simpanan = muat_json(SIMPANAN, {"bulan": {}})
    pesan = susun(bulan, baris, muat_json(BUDGET, {}), simpanan, perkiraan_absen(bulan))
    print(pesan)

    if not a.kirim:
        return 0

    tujuan = [tuple(x.split(":", 1)) for x in a.ke] if a.ke else tujuan_baku()
    if not tujuan:
        print("\n❌ Tidak ada tujuan pengiriman.", file=sys.stderr)
        return 2

    semua_ok = True
    for kanal, ke in tujuan:
        ok, ket = kirim(pesan, kanal, ke)
        print(f"\n{'✅ terkirim' if ok else '❌ GAGAL'} {kanal} -> {ke}" + (f": {ket}" if ket else ""))
        semua_ok = semua_ok and ok
    if not semua_ok:
        print("Angka TIDAK disimpan — laporan ini belum diterima.", file=sys.stderr)
        return 1

    SIMPANAN.write_text(json.dumps(simpanan_baru(simpanan, bulan, arus_per_bulan(baris)),
                                   indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
