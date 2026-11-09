"""Tes scripts/budget.py — Budget rutin, Pengeluaran Besar, pesan, dan saran (ADR-0024).

    python3 -m unittest tests/test_budget.py
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import budget  # noqa: E402

AKHIR = date(2026, 10, 31)
ATUR = {"budget_bulanan": 8_000_000, "alert_persen": 80, "pengeluaran_besar_mulai": 1_000_000}
_resi = iter(range(1, 10_000))


def pengeluaran(jumlah, kategori="food", tanggal="2026-10-05", resi=None):
    return {"tanggal": tanggal, "tipe": "pengeluaran", "kategori": kategori, "jumlah": str(jumlah),
            "no_resi": resi or f"TRX-{next(_resi)}"}


def rutin(total, kategori="food", tanggal="2026-10-05"):
    """Banyak Transaksi kecil (≤ Rp 500.000, jauh di bawah ambang) yang berjumlah `total`."""
    hasil, sisa = [], total
    while sisa > 0:
        hasil.append(pengeluaran(min(500_000, sisa), kategori, tanggal))
        sisa -= 500_000
    return hasil


def lain(tipe, jumlah, kategori, tanggal="2026-10-05"):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah),
            "no_resi": f"TRX-{next(_resi)}"}


class Pemakaian(unittest.TestCase):
    def hitung(self, rows, atur=ATUR, mulai=date(2026, 10, 1), akhir=AKHIR):
        return budget.pemakaian(rows, mulai, akhir, atur)

    def test_pengeluaran_besar_dipisah_dari_rutin(self):
        p = self.hitung(rutin(3_000_000) + [pengeluaran(4_000_000, "transport")])
        self.assertEqual((p["rutin"], p["besar"], p["transaksi_besar"]), (3_000_000, 4_000_000, 1))
        self.assertEqual(p["pengeluaran"], 7_000_000)
        self.assertAlmostEqual(p["persen"], 37.5)

    def test_per_kategori_rutin_tidak_memuat_yang_besar(self):
        p = self.hitung(rutin(2_000_000, "food") + [pengeluaran(4_000_000, "food")])
        self.assertEqual(p["per_kategori"], {"food": 2_000_000})

    def test_ambang_dibaca_dari_pengaturan_dan_bawaan_satu_juta(self):
        rows = [pengeluaran(1_500_000)]
        self.assertEqual(self.hitung(rows, {**ATUR, "pengeluaran_besar_mulai": 2_000_000})["besar"], 0)
        tanpa = {k: v for k, v in ATUR.items() if k != "pengeluaran_besar_mulai"}
        self.assertEqual(self.hitung(rows, tanpa)["besar"], 1_500_000)

    def test_batas_nol_persen_kosong(self):
        self.assertIsNone(self.hitung(rutin(1_000_000), {**ATUR, "budget_bulanan": 0})["persen"])

    def test_pemasukan_transfer_dan_bulan_lain_tidak_dihitung(self):
        p = self.hitung(rutin(1_000_000) + [lain("pemasukan", 9_000_000, "salary"),
                                              lain("transfer", 2_000_000, "transfer"),
                                              pengeluaran(999_999, tanggal="2026-09-30")])
        self.assertEqual((p["rutin"], p["besar"]), (1_000_000, 0))


class Pesan(unittest.TestCase):
    def teks(self, rows, atur=ATUR, hari=AKHIR, selalu=False):
        return budget.pesan(rows, hari, atur, selalu=selalu)

    # 97%: Rp 7.754.771 dari Rp 8.000.000, tanggal 31 Okt → sisa 1 hari
    MENDEKATI = rutin(7_754_771)

    def test_mendekati_batas_judul_angka_dan_saran_sisa_satu_hari(self):
        t = self.teks(self.MENDEKATI)
        self.assertIn("⚠️ Mendekati batas Budget — Oktober 2026", t)
        self.assertIn("Batas rutin:", t)
        self.assertIn("Rp 8.000.000", t)
        self.assertIn("Terpakai (rutin):", t)
        self.assertIn("Rp 7.754.771 (97%)", t)
        self.assertIn("Masih bisa:", t)
        self.assertIn("Rp 245.229", t)
        self.assertIn("💡 Saran: sisa 1 hari, jadi belanja rutin hari ini sebaiknya tidak lebih dari Rp 245.229.", t)

    def test_mendekati_batas_banyak_hari_memberi_rata_rata_per_hari(self):
        t = self.teks(rutin(7_000_000), hari=date(2026, 10, 20))  # 87,5%; sisa 12 hari
        self.assertIn("💡 Saran: sisa 12 hari, rata-rata sebaiknya tidak lebih dari Rp 83.333 per hari.", t)

    def test_lewat_batas_menyebut_lewatnya_dan_kategori_terbesar_rutin(self):
        rows = rutin(6_000_000, "food") + rutin(3_000_000, "groceries") + [pengeluaran(5_000_000, "transport")]
        t = self.teks(rows)  # rutin 9 jt dari 8 jt = 112%
        self.assertIn("🚨 Lewat batas Budget — Oktober 2026", t)
        self.assertIn("Lewat:", t)
        self.assertIn("Rp 1.000.000", t)
        self.assertIn("💡 Saran: sudah lewat Rp 1.000.000. Kategori terbesar bulan ini food "
                      "(Rp 6.000.000, 67%). Tunda belanja yang bisa ditunda ke bulan depan.", t)
        self.assertNotIn("transport", t)  # yang besar tidak jadi 'kategori terbesar' rutin

    def test_baris_di_luar_budget_selalu_tampil(self):
        self.assertIn("Di luar budget:", self.teks(self.MENDEKATI))
        self.assertIn("Rp 0 (0 transaksi ≥ Rp 1.000.000)", self.teks(self.MENDEKATI))
        t = self.teks(self.MENDEKATI + [pengeluaran(4_000_000, "transport")])
        self.assertIn("Rp 4.000.000 (1 transaksi ≥ Rp 1.000.000)", t)

    def test_arus_kas_bulanan_memuat_pemasukan_dan_seluruh_pengeluaran(self):
        t = self.teks(self.MENDEKATI + [lain("pemasukan", 7_322_000, "salary")] + [pengeluaran(1_000_000)])
        self.assertIn("Arus Kas Bulanan Oktober: -Rp 1.432.771", t)
        self.assertIn("masuk Rp 7.322.000, keluar Rp 8.754.771", t)

    def test_diam_di_bawah_ambang_alarm_kecuali_diminta(self):
        rows = rutin(1_000_000)
        self.assertEqual(self.teks(rows), "")
        t = self.teks(rows, hari=date(2026, 10, 12), selalu=True)
        self.assertIn("💰 Status Budget — Oktober 2026", t)
        self.assertIn("💡 Saran: masih aman. Sisa 20 hari, rata-rata sebaiknya tidak lebih dari "
                      "Rp 350.000 per hari.", t)
        self.assertIn("Dihitung scripts/check-bills.py, tanpa model", t)

    def test_budget_belum_diset(self):
        belum = {**ATUR, "budget_bulanan": 0}
        self.assertEqual(self.teks(rutin(1_000_000), belum), "")
        self.assertIn("Budget belum diset", self.teks(rutin(1_000_000), belum, selalu=True))

    def test_kata_yang_menyesatkan_tidak_dipakai_lagi(self):
        for rows in (self.MENDEKATI, rutin(9_000_000)):
            t = self.teks(rows, selalu=True)
            for kata in ("MINUS", "BUDGET HABIS", "October", "Sisa:"):
                self.assertNotIn(kata, t)


class BulanTransaksi(unittest.TestCase):
    """Cek setelah pencatatan memakai bulan transaksi, bukan bulan hari ini (pencatatan mundur)."""

    NOV = date(2026, 11, 1)  # hari ini; transaksi yang baru dicatat bertanggal Oktober

    def teks(self, rows, selalu=False, bulan="2026-10"):
        return budget.pesan(rows, self.NOV, ATUR, selalu=selalu, bulan=bulan)

    def test_oktober_lewat_batas_terdeteksi_walau_hari_ini_november(self):
        t = self.teks(rutin(8_389_942))  # 105%
        self.assertIn("🚨 Lewat batas Budget — Oktober 2026 (sudah tutup)", t)
        self.assertIn("Lewat:", t)
        self.assertIn("Rp 389.942", t)
        self.assertIn("💡 Saran: sudah lewat Rp 389.942.", t)
        self.assertNotIn("Tunda belanja", t)  # bulannya sudah lewat; tak ada yang bisa ditunda ke bulan depan
        self.assertNotIn("sisa", t.lower().replace("terbesar", ""))  # tak ada "sisa N hari" untuk bulan tutup

    def test_bulan_tutup_di_bawah_100_persen_diam(self):
        self.assertEqual(self.teks(rutin(7_900_000)), "")  # 98%: tak ada gunanya memperingatkan bulan yang sudah lewat

    def test_bulan_tutup_diminta_lewat_chat_dijawab_tanpa_saran_sisa_hari(self):
        t = self.teks(rutin(7_200_000), selalu=True)
        self.assertIn("💰 Status Budget — Oktober 2026 (sudah tutup)", t)
        self.assertIn("💡 Saran: bulan sudah tutup di 90% dari batas.", t)
        self.assertNotIn("Sisa", t)

    def test_bulan_berjalan_tidak_berubah(self):
        rows = rutin(7_754_771)
        sama = budget.pesan(rows, AKHIR, ATUR, selalu=False)
        self.assertEqual(sama, budget.pesan(rows, AKHIR, ATUR, selalu=False, bulan="2026-10"))
        self.assertNotIn("sudah tutup", sama)

    def test_bulan_lain_tidak_ikut_dihitung(self):
        rows = rutin(8_389_942, tanggal="2026-10-10") + rutin(7_000_000, tanggal="2026-11-01")
        self.assertIn("Rp 8.389.942", self.teks(rows))
        self.assertIn("Rp 7.000.000", budget.pesan(rows, self.NOV, ATUR, selalu=True))


class BarisLaporan(unittest.TestCase):
    def test_baris_budget_dan_di_luar_budget_untuk_laporan(self):
        rows = rutin(7_754_771) + [pengeluaran(4_000_000, "transport")]
        p = budget.pemakaian(rows, date(2026, 10, 1), AKHIR, ATUR)
        self.assertEqual(budget.baris_laporan(p), [
            "💰 Budget: Rp 7.754.771 dari Rp 8.000.000 (97%)",
            "📦 Di luar budget: Rp 4.000.000 (1 transaksi ≥ Rp 1.000.000)"])

    def test_budget_belum_diset(self):
        p = budget.pemakaian(rutin(1_000_000), date(2026, 10, 1), AKHIR, {**ATUR, "budget_bulanan": 0})
        self.assertEqual(budget.baris_laporan(p)[0], "💰 Budget: Rp 1.000.000 (budget belum diset)")


class SelisihRekonsiliasi(unittest.TestCase):
    """ADR-0027: Selisih Rekonsiliasi bukan keputusan belanja — tidak ke Budget, tampil terpisah."""

    def test_tidak_dihitung_ke_budget_maupun_pengeluaran_besar(self):
        rows = rutin(1_000_000) + [pengeluaran(1_500_000, "reconciliation")]
        p = budget.pemakaian(rows, date(2026, 10, 1), AKHIR, ATUR)
        self.assertEqual((p["rutin"], p["besar"], p["transaksi_besar"]), (1_000_000, 0, 0))
        self.assertEqual(p["rekonsiliasi"], 1_500_000)
        self.assertEqual(p["pengeluaran"], 2_500_000)  # tetap uang yang keluar
        self.assertNotIn("reconciliation", p["per_kategori"])

    def test_baris_laporan_menyebutnya_terpisah_bila_ada(self):
        p = budget.pemakaian(rutin(1_000_000) + [pengeluaran(250_000, "reconciliation")],
                             date(2026, 10, 1), AKHIR, ATUR)
        self.assertEqual(budget.baris_laporan(p)[-1],
                         "🔁 Selisih rekonsiliasi: Rp 250.000 (tidak dihitung ke budget)")
        p = budget.pemakaian(rutin(1_000_000), date(2026, 10, 1), AKHIR, ATUR)
        self.assertEqual(len(budget.baris_laporan(p)), 2)


if __name__ == "__main__":
    unittest.main()
