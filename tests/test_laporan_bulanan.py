"""Tes scripts/laporan-bulanan.py — aturan hitung dan aturan simpan (ADR-0012).

    python3 -m unittest tests/test_laporan_bulanan.py
"""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("laporan", AKAR / "scripts" / "laporan-bulanan.py")
lb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lb)

KOLOM = ["tanggal", "tipe", "kategori", "item", "jumlah", "catatan", "channel",
         "pencatat", "akun", "akun_tujuan", "waktu", "no_resi"]


def baris(tanggal, tipe, kategori, jumlah):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah)}


DASAR = [
    baris("2026-03-26", "pemasukan", "opening_balance", 20_500_000),
    baris("2026-07-05", "pengeluaran", "food", 100_000),
    baris("2026-07-28", "pemasukan", "salary", 5_000_000),
    baris("2026-08-03", "pengeluaran", "food", 300_000),
    baris("2026-08-10", "pengeluaran", "transport", 200_000),
    baris("2026-08-12", "transfer", "other", 1_000_000),
    baris("2026-08-27", "pemasukan", "salary", 5_000_000),
    baris("", "pengeluaran", "food", 999_999),  # tanpa tanggal: tidak ikut apa pun
]


class AturanHitung(unittest.TestCase):
    def test_opening_balance_ikut_saldo_tapi_bukan_pemasukan(self):
        arus = lb.arus_per_bulan(DASAR)
        self.assertEqual(arus["2026-03"]["pemasukan"], 0)
        self.assertEqual(lb.saldo_akhir(arus, "2026-03"), 20_500_000)

    def test_transfer_dilewati(self):
        arus = lb.arus_per_bulan(DASAR)
        self.assertEqual(arus["2026-08"]["pengeluaran"], 500_000)
        self.assertEqual(lb.jumlah_transaksi(DASAR, "2026-08"), 3)

    def test_saldo_kumulatif(self):
        arus = lb.arus_per_bulan(DASAR)
        self.assertEqual(lb.saldo_akhir(arus, "2026-07"), 20_500_000 - 100_000 + 5_000_000)
        self.assertEqual(lb.saldo_akhir(arus, "2026-08"), 25_400_000 + 5_000_000 - 500_000)

    def test_tanpa_tipe_dianggap_pengeluaran(self):
        arus = lb.arus_per_bulan([{"tanggal": "2026-08-01", "kategori": "food", "jumlah": "50"}])
        self.assertEqual(arus["2026-08"]["pengeluaran"], 50)

    def test_bulan_sebelum_melewati_tahun(self):
        self.assertEqual(lb.bulan_sebelum("2027-01"), "2026-12")


class AturanKoreksi(unittest.TestCase):
    def test_koreksi_hanya_di_bulan_asal(self):
        simpanan = lb.simpanan_baru({"bulan": {}}, "2026-07", lb.arus_per_bulan(DASAR))
        simpanan = lb.simpanan_baru(simpanan, "2026-08", lb.arus_per_bulan(DASAR))
        # Pencocokan bank menemukan pengeluaran Juli yang terlewat.
        kini = DASAR + [baris("2026-07-20", "pengeluaran", "other", 350_000)]
        koreksi = lb.cari_koreksi(lb.arus_per_bulan(kini), simpanan, "2026-09")
        self.assertEqual([k["bulan"] for k in koreksi], ["2026-07"])  # bukan Agustus juga
        self.assertEqual(koreksi[0]["pengeluaran"], 350_000)

    def test_koreksi_disebut_sekali(self):
        simpanan = lb.simpanan_baru({"bulan": {}}, "2026-07", lb.arus_per_bulan(DASAR))
        kini = lb.arus_per_bulan(DASAR + [baris("2026-07-20", "pengeluaran", "other", 350_000)])
        simpanan = lb.simpanan_baru(simpanan, "2026-08", kini)
        self.assertEqual(lb.cari_koreksi(kini, simpanan, "2026-09"), [])

    def test_bulan_yang_sedang_dilaporkan_bukan_koreksi(self):
        simpanan = lb.simpanan_baru({"bulan": {}}, "2026-08", lb.arus_per_bulan(DASAR))
        kini = lb.arus_per_bulan(DASAR + [baris("2026-08-30", "pengeluaran", "food", 1)])
        self.assertEqual(lb.cari_koreksi(kini, simpanan, "2026-08"), [])

    def test_koreksi_tampil_di_pesan(self):
        simpanan = lb.simpanan_baru({"bulan": {}}, "2026-07", lb.arus_per_bulan(DASAR))
        kini = DASAR + [baris("2026-07-20", "pengeluaran", "other", 350_000)]
        pesan = lb.susun("2026-08", kini, {}, simpanan, [])
        self.assertIn("Koreksi Juli 2026: pengeluaran naik Rp 350.000", pesan)

    def test_judul_bulan_berjalan(self):
        from datetime import date
        pesan = lb.susun("2026-08", DASAR, {}, {"bulan": {}}, [], date(2026, 8, 21))
        self.assertIn("(berjalan, per 21 Agu)", pesan.splitlines()[0])
        self.assertNotIn("berjalan", lb.susun("2026-08", DASAR, {}, {"bulan": {}}, []).splitlines()[0])


class AturanSimpan(unittest.TestCase):
    """Angka disimpan HANYA kalau terkirim; mode tampil tidak pernah menulis."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.asli = {k: getattr(lb, k) for k in
                     ("BILLS", "BUDGET", "SIMPANAN", "tujuan_baku", "kirim", "perkiraan_absen")}
        lb.BILLS, lb.BUDGET = self.tmp / "bills.csv", self.tmp / "budget.json"
        lb.SIMPANAN = self.tmp / "laporan.json"
        lb.tujuan_baku = lambda: [("whatsapp", "+0")]
        lb.perkiraan_absen = lambda bulan, today=None: []
        with open(lb.BILLS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=KOLOM)
            w.writeheader()
            w.writerows(DASAR)

    def tearDown(self):
        for k, v in self.asli.items():
            setattr(lb, k, v)

    def test_tampil_saja_tidak_menulis(self):
        self.assertEqual(lb.main(["--bulan", "2026-08"]), 0)
        self.assertFalse(lb.SIMPANAN.exists())

    def test_kirim_gagal_keluar_1_dan_tidak_menyimpan(self):
        lb.kirim = lambda pesan, kanal, ke: (False, "No active WhatsApp Web listener")
        self.assertEqual(lb.main(["--bulan", "2026-08", "--kirim"]), 1)
        self.assertFalse(lb.SIMPANAN.exists())

    def test_kirim_berhasil_menyimpan(self):
        lb.kirim = lambda pesan, kanal, ke: (True, "")
        self.assertEqual(lb.main(["--bulan", "2026-08", "--kirim"]), 0)
        disimpan = json.loads(lb.SIMPANAN.read_text())["bulan"]["2026-08"]
        self.assertEqual(disimpan["pengeluaran"], 500_000)
        self.assertEqual(disimpan["saldo_akhir"], 29_900_000)

    def test_bulan_berjalan_ditandai_dan_tidak_bisa_dikirim(self):
        lb.kirim = lambda pesan, kanal, ke: (True, "")
        self.assertEqual(lb.main(["--bulan", "2026-08", "--hari-ini", "2026-08-21", "--kirim"]), 2)
        self.assertFalse(lb.SIMPANAN.exists())

    def test_bulan_berjalan_meneruskan_hari_ini_ke_perkiraan(self):
        dipanggil = []
        lb.perkiraan_absen = lambda bulan, today=None: dipanggil.append(today) or []
        lb.main(["--bulan", "2026-08", "--hari-ini", "2026-08-21"])
        lb.main(["--bulan", "2026-08", "--hari-ini", "2026-09-06"])
        self.assertEqual([str(d) for d in dipanggil], ["2026-08-21", "None"])

    def test_tanpa_tujuan_keluar_2(self):
        lb.tujuan_baku = lambda: []
        self.assertEqual(lb.main(["--bulan", "2026-08", "--kirim"]), 2)
        self.assertFalse(lb.SIMPANAN.exists())


if __name__ == "__main__":
    unittest.main()
