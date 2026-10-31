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

Aturan hitung (Transfer, Saldo Awal, baris tanpa tanggal/tipe tak dikenal) ada di
scripts/buku_kas.py, satu untuk semua laporan.
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import buku_kas  # noqa: E402
import pengaturan  # noqa: E402
import pengirim  # noqa: E402
import periode  # noqa: E402
import perkiraan  # noqa: E402

AKAR = Path(__file__).resolve().parent.parent
DATA = AKAR / "data"
BILLS = DATA / "bills.csv"
SIMPANAN = DATA / "laporan-bulanan.json"

KATEGORI_TERATAS = 5
NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
              "Agustus", "September", "Oktober", "November", "Desember"]


# ── Membaca ───────────────────────────────────────────────────────────────
def muat_baris(path=None):
    return buku_kas.muat(path or BILLS)


def muat_json(path, bawaan):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return bawaan


def saldo_akhir(baris, bulan):
    """Saldo per akhir `bulan`."""
    return buku_kas.saldo(baris, per=periode.akhir_bulan(bulan))


def cari_koreksi(baris, simpanan, bulan_laporan):
    """Bulan yang pernah dilaporkan dan Pemasukan/Pengeluarannya berubah sejak itu.

    Hanya bulan asal perubahan yang disebut: Saldo akhir bulan-bulan sesudahnya memang ikut
    bergeser, tapi itu akibat, bukan koreksi tersendiri (CONTEXT.md → Koreksi).
    """
    koreksi = []
    for b, lama in sorted(simpanan.get("bulan", {}).items()):
        if b == bulan_laporan:
            continue
        kini = buku_kas.arus_kas_bulan(baris, b)
        d_in = round(kini["pemasukan"] - lama["pemasukan"])
        d_out = round(kini["pengeluaran"] - lama["pengeluaran"])
        if d_in or d_out:
            koreksi.append({"bulan": b, "pemasukan": d_in, "pengeluaran": d_out,
                            "saldo_akhir": saldo_akhir(baris, b)})
    return koreksi


def perkiraan_absen(bulan, today=None):
    """Pakai aturan pencocokan yang sama dengan cek malam, bukan salinannya.

    `today` None = bulannya sudah tutup, semua Perkiraan diperiksa. Untuk bulan berjalan,
    Perkiraan yang tanggalnya belum lewat toleransi tidak ikut disebut — gaji tanggal 26 belum
    bisa dibilang "tidak masuk" pada tanggal 21.
    """
    t, b = map(int, bulan.split("-"))
    return perkiraan.absen(perkiraan.muat(), muat_baris(), t, b, today, pengaturan.muat())


# ── Menyusun ──────────────────────────────────────────────────────────────
def rp(x):
    return ("-" if x < 0 else "") + f"Rp {abs(x):,.0f}".replace(",", ".")


def nama_bulan(bulan):
    t, b = map(int, bulan.split("-"))
    return f"{NAMA_BULAN[b - 1]} {t}"


def susun(bulan, baris, budget, simpanan, absen, berjalan_per=None):
    h = buku_kas.ringkas(baris, *periode.rentang_bulan(bulan))
    arus_kas = h["pemasukan"] - h["pengeluaran"]
    lalu = periode.bulan_sebelum(bulan)
    nb, nl = nama_bulan(bulan), NAMA_BULAN[int(lalu[5:]) - 1]

    judul = f"📊 *LAPORAN BULANAN — {nb}*"
    if berjalan_per:
        # Bukan Laporan Bulanan dalam arti CONTEXT.md — bulannya belum tutup. Tandai terang-terangan.
        judul += f" _(berjalan, per {berjalan_per.day} {NAMA_BULAN[berjalan_per.month - 1][:3]})_"
    out = [judul, "",
           f"📥 Pemasukan:   {rp(h['pemasukan'])}",
           f"📤 Pengeluaran: {rp(h['pengeluaran'])}  ({h['transaksi_pengeluaran']} transaksi)",
           f"{'💚' if arus_kas >= 0 else '🔴'} Arus Kas Bulan: {rp(arus_kas)}",
           f"🏦 Saldo akhir {NAMA_BULAN[int(bulan[5:]) - 1]}: {rp(saldo_akhir(baris, bulan))}"]

    batas = float(budget.get("budget_bulanan") or 0)
    if batas > 0:
        out += ["", f"💰 Budget: {rp(h['pengeluaran'])} dari {rp(batas)} "
                    f"({h['pengeluaran'] / batas * 100:.0f}%)"]

    kini = h["per_kategori"]
    dulu = buku_kas.ringkas(baris, *periode.rentang_bulan(lalu))["per_kategori"]
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

    for k in cari_koreksi(baris, simpanan, bulan):
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

    tak = buku_kas.tak_terhitung(baris)
    if tak:
        out += ["", f"⚠️ {len(tak)} transaksi tidak terhitung (tanggal tidak sah / tipe tidak "
                    f"dikenal) — periksa bills.csv."]

    out += ["", "_Dihitung scripts/laporan-bulanan.py, tanpa model_"]
    return "\n".join(out)


def simpanan_baru(simpanan, bulan, baris):
    """Catat angka bulan yang dilaporkan, dan perbarui bulan yang Koreksinya baru disebut."""
    kini = datetime.now().isoformat(timespec="seconds")
    isi = {"bulan": dict(simpanan.get("bulan", {}))}
    for k in cari_koreksi(baris, simpanan, bulan):
        h = buku_kas.arus_kas_bulan(baris, k["bulan"])
        isi["bulan"][k["bulan"]] = {**isi["bulan"][k["bulan"]],
                                    "pemasukan": round(h["pemasukan"]),
                                    "pengeluaran": round(h["pengeluaran"]),
                                    "dikoreksi": kini}
    h = buku_kas.arus_kas_bulan(baris, bulan)
    isi["bulan"][bulan] = {"pemasukan": round(h["pemasukan"]),
                           "pengeluaran": round(h["pengeluaran"]),
                           "saldo_akhir": round(saldo_akhir(baris, bulan)),
                           "dilaporkan": kini}
    return isi


# ── Mengirim ──────────────────────────────────────────────────────────────
# Lewat scripts/pengirim.py, bersama Laporan Mingguan dan cek budget malam. Dirujuk lewat
# nama modul ini supaya tes bisa menggantinya tanpa mengirim sungguhan.
tujuan_baku = pengirim.tujuan_baku
kirim = pengirim.kirim


def main(argv=None):
    ap = argparse.ArgumentParser(description="Laporan Bulanan, tanpa model (ADR-0012)")
    ap.add_argument("--bulan", metavar="YYYY-MM", help="bulan yang dilaporkan (bawaan: bulan lalu)")
    ap.add_argument("--kirim", action="store_true", help="kirim, lalu simpan angka yang dilaporkan")
    ap.add_argument("--ke", action="append", metavar="KANAL:TUJUAN",
                    help="tujuan, bisa diulang (bawaan: nomor pemilik dari config)")
    ap.add_argument("--hari-ini", metavar="YYYY-MM-DD", help="anggap hari ini tanggal segini (uji)")
    a = ap.parse_args(argv)

    try:
        hari_ini = date.fromisoformat(a.hari_ini) if a.hari_ini else date.today()
    except ValueError:
        ap.error(f"--hari-ini tidak valid: {a.hari_ini}")
    bulan = a.bulan or periode.bulan_sebelum(hari_ini.strftime("%Y-%m"))
    try:
        datetime.strptime(bulan, "%Y-%m")
    except ValueError:
        ap.error(f"--bulan tidak valid: {bulan}")
    if bulan > hari_ini.strftime("%Y-%m"):
        ap.error(f"{bulan} belum dimulai")
    berjalan = bulan == hari_ini.strftime("%Y-%m")

    baris = muat_baris()
    simpanan = muat_json(SIMPANAN, {"bulan": {}})
    pesan = susun(bulan, baris, pengaturan.muat(), simpanan,
                  perkiraan_absen(bulan, hari_ini if berjalan else None),
                  hari_ini if berjalan else None)
    print(pesan)

    if not a.kirim:
        return 0
    if berjalan:
        # Menyimpan angka setengah bulan akan membuat setiap transaksi sesudahnya tampil
        # sebagai Koreksi palsu di laporan berikutnya.
        print("\n❌ Bulan berjalan tidak dikirim sebagai Laporan Bulanan — angkanya belum final.",
              file=sys.stderr)
        return 2

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

    SIMPANAN.write_text(json.dumps(simpanan_baru(simpanan, bulan, baris),
                                   indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
