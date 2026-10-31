"""Tes scripts/laporan-mingguan.py — Pekan, Saldo akhir Pekan, Hari Kosong, Pekan lintas bulan
(ADR-0013). Semua lewat susun(); tidak ada yang dikirim.

    python3 -m unittest tests/test_laporan_mingguan.py
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
spec = importlib.util.spec_from_file_location("laporan_mingguan", AKAR / "scripts" / "laporan-mingguan.py")
lm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lm)

SENIN, MINGGU = date(2026, 10, 19), date(2026, 10, 25)


def tx(tanggal, tipe, jumlah, kategori="food", item="Nasi"):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "item": item,
            "jumlah": str(jumlah), "no_resi": ""}


def tiap_hari(mulai, akhir, jumlah=10_000):
    """Satu Pengeluaran per hari, supaya tidak ada Hari Kosong kecuali yang sengaja dibuat."""
    d, hasil = mulai, []
    while d <= akhir:
        hasil.append(tx(d.isoformat(), "pengeluaran", jumlah))
        d = date.fromordinal(d.toordinal() + 1)
    return hasil


class DenganBerkasKosong(unittest.TestCase):
    """budget.json, kewajiban.json, perkiraan.json diarahkan ke folder sementara."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tambal = [(lm.pengaturan, "BUDGET_JSON"), (lm.kewajiban, "KEWAJIBAN_JSON"),
                       (lm.perkiraan, "PERKIRAAN_JSON")]
        self.asli = [getattr(m, k) for m, k in self.tambal]
        for m, k in self.tambal:
            setattr(m, k, self.tmp / k.lower())
        (self.tmp / "budget_json").write_text(json.dumps({"budget_bulanan": 1_000_000}))

    def tearDown(self):
        for (m, k), v in zip(self.tambal, self.asli):
            setattr(m, k, v)


class Pekan(DenganBerkasKosong):
    def test_minggu_masuk_senin_berikutnya_dan_minggu_sebelumnya_tidak(self):
        rows = tiap_hari(SENIN, MINGGU) + [
            tx("2026-10-25", "pengeluaran", 70_000, item="Minggu larut"),
            tx("2026-10-26", "pengeluaran", 999_000, item="Senin depan"),
            tx("2026-10-18", "pengeluaran", 888_000, item="Minggu lalu"),
        ]
        pesan = lm.susun(rows, SENIN, MINGGU, True)
        self.assertIn("Total: Rp 140.000 · 8 transaksi", pesan)
        self.assertIn("Minggu larut", pesan)
        self.assertNotIn("Senin depan", pesan)
        self.assertIn("Pekan: Senin 19 Okt – Minggu 25 Okt 2026", pesan)

    def test_pekan_lalu_sebagai_pembanding(self):
        rows = tiap_hari(SENIN, MINGGU) + [tx("2026-10-14", "pengeluaran", 35_000)]
        self.assertIn("vs pekan lalu: +Rp 35.000 (+100%)", lm.susun(rows, SENIN, MINGGU, True))


class Saldo(DenganBerkasKosong):
    def test_saldo_akhir_pekan(self):
        rows = [tx("2026-03-26", "pemasukan", 20_500_000, "opening_balance"),
                tx("2026-10-20", "pemasukan", 5_000_000, "salary"),
                tx("2026-10-21", "transfer", 3_000_000, "other"),
                tx("2026-10-26", "pengeluaran", 1_000_000)] + tiap_hari(SENIN, MINGGU)
        pesan = lm.susun(rows, SENIN, MINGGU, True)
        self.assertIn("🏦 Saldo Bersama akhir Pekan: Rp 25.430.000", pesan)  # tanpa transfer & Senin depan

    def test_pemasukan_pekan_tanpa_saldo_awal(self):
        rows = [tx("2026-10-20", "pemasukan", 20_500_000, "opening_balance"),
                tx("2026-10-21", "pemasukan", 400_000, "salary")] + tiap_hari(SENIN, MINGGU)
        self.assertIn("💰 Pemasukan pekan ini: Rp 400.000", lm.susun(rows, SENIN, MINGGU, True))

    def test_pekan_berjalan_saldo_per_hari_itu(self):
        rows = tiap_hari(SENIN, date(2026, 10, 21)) + [tx("2026-10-22", "pengeluaran", 5_000)]
        pesan = lm.susun(rows, SENIN, date(2026, 10, 21), False)
        self.assertIn("🏦 Saldo Bersama per 21 Okt: Rp -30.000", pesan)  # 22 Okt belum ikut


class HariKosong(DenganBerkasKosong):
    def test_satu_hari_kosong_biasa_saja(self):
        rows = [r for r in tiap_hari(SENIN, MINGGU) if r["tanggal"] != "2026-10-21"]
        self.assertNotIn("Tidak ada catatan", lm.susun(rows, SENIN, MINGGU, True))

    def test_dua_hari_berturut_diperingatkan(self):
        rows = [r for r in tiap_hari(SENIN, MINGGU)
                if r["tanggal"] not in ("2026-10-21", "2026-10-22")]
        self.assertIn("⚠️ Tidak ada catatan pada Rab 21, Kam 22 Okt", lm.susun(rows, SENIN, MINGGU, True))

    def test_pemasukan_saja_tetap_hari_kosong(self):
        rows = [r for r in tiap_hari(SENIN, MINGGU)
                if r["tanggal"] not in ("2026-10-24", "2026-10-25")]
        rows.append(tx("2026-10-24", "pemasukan", 100_000, "salary"))
        self.assertIn("Sab 24, Min 25 Okt", lm.susun(rows, SENIN, MINGGU, True))


class TakTerhitung(DenganBerkasKosong):
    def test_baris_tanpa_tanggal_diperingatkan_dan_tidak_mengubah_angka(self):
        rows = tiap_hari(SENIN, MINGGU)
        kotor = rows + [tx("", "pengeluaran", 500_000), tx("2026-10-20", "pemasukkan", 9)]
        bersih, pesan = lm.susun(rows, SENIN, MINGGU, True), lm.susun(kotor, SENIN, MINGGU, True)
        self.assertIn("⚠️ 2 transaksi tidak terhitung", pesan)
        self.assertNotIn("tidak terhitung", bersih)
        self.assertEqual([b for b in pesan.splitlines() if "tidak terhitung" not in b and b],
                         [b for b in bersih.splitlines() if b])


class LintasBulan(DenganBerkasKosong):
    def test_budget_dua_bulan(self):
        mulai, akhir = date(2026, 9, 28), date(2026, 10, 4)
        rows = tiap_hari(date(2026, 9, 1), akhir)
        pesan = lm.susun(rows, mulai, akhir, True)
        self.assertIn("📅 Budget Sep (tutup): Rp 300.000 dari Rp 1.000.000 (30%)", pesan)
        self.assertIn("📅 Budget Okt: Rp 40.000 dari Rp 1.000.000 (4%)", pesan)
        self.assertIn("Pekan: Senin 28 Sep – Minggu 4 Okt 2026", pesan)


if __name__ == "__main__":
    unittest.main()
