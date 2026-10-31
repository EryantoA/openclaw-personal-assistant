"""Tes silang: data yang sama harus menghasilkan jumlah Transaksi dan total uang yang sama di semua
laporan (ADR-0023). Menjaga agar angka "N transaksi" tidak lagi berbeda antar laporan.

    python3 -m unittest tests/test_laporan_silang.py
"""
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))


def muat(nama, berkas):
    spec = importlib.util.spec_from_file_location(nama, AKAR / "scripts" / berkas)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


harian = muat("silang_harian", "laporan-harian.py")
mingguan = muat("silang_mingguan", "laporan-mingguan.py")
bulanan = muat("silang_bulanan", "laporan-bulanan.py")
rekap = muat("silang_rekap", "rekap-bulanan.py")
pembeli = muat("silang_pembeli", "laporan-pembeli.py")

HARI = date(2026, 10, 14)  # Rabu; sehari, satu Pekan (12–18 Okt), satu bulan


def baris(tipe, jumlah, resi, pencatat, kategori="food"):
    return {"tanggal": HARI.isoformat(), "tipe": tipe, "kategori": kategori, "item": "x",
            "jumlah": str(jumlah), "no_resi": resi, "pencatat": pencatat}


# 3 Transaksi pengeluaran dari 6 baris: S1 (3 Item), S2 (2 Item), S3 (1 Item), Rp 600.000 seluruhnya.
ROWS = [
    baris("pengeluaran", 100_000, "STRUK-S1", "Eryanto"),
    baris("pengeluaran", 100_000, "STRUK-S1", "Eryanto", "groceries"),
    baris("pengeluaran", 100_000, "STRUK-S1", "Eryanto"),
    baris("pengeluaran", 100_000, "STRUK-S2", "Elsi"),
    baris("pengeluaran", 100_000, "STRUK-S2", "Elsi", "groceries"),
    baris("pengeluaran", 100_000, "TRX-S3", "Eryanto"),
    baris("pemasukan", 5_000_000, "TRX-P1", "Eryanto", "salary"),      # bukan Pengeluaran
    baris("transfer", 2_000_000, "TRX-T1", "Eryanto", "transfer"),     # tidak dihitung apa pun
]
TRANSAKSI, TOTAL = 3, "Rp 600.000"


class LaporanSilang(unittest.TestCase):
    def setUp(self):
        # budget/kewajiban/perkiraan ke folder sementara supaya data asli tidak ikut terbaca
        self.tmp = Path(tempfile.mkdtemp())
        self.tambal = [(mingguan.pengaturan, "BUDGET_JSON"), (mingguan.kewajiban, "KEWAJIBAN_JSON"),
                       (mingguan.perkiraan, "PERKIRAAN_JSON")]
        self.asli = [getattr(m, k) for m, k in self.tambal]
        for m, k in self.tambal:
            setattr(m, k, self.tmp / k.lower())
        (self.tmp / "budget_json").write_text(json.dumps({"budget_bulanan": 1_000_000}))

    def tearDown(self):
        for (m, k), v in zip(self.tambal, self.asli):
            setattr(m, k, v)

    def test_harian(self):
        teks = harian.susun(ROWS, HARI)
        self.assertIn(f"Total: {TOTAL}", teks)
        self.assertIn(f"{TRANSAKSI} transaksi tercatat", teks)

    def test_mingguan(self):
        teks = mingguan.susun(ROWS, date(2026, 10, 12), date(2026, 10, 18), True)
        self.assertIn(f"Total: {TOTAL} · {TRANSAKSI} transaksi", teks)

    def test_bulanan(self):
        teks = bulanan.susun("2026-10", ROWS, {}, {"bulan": {}}, [])
        self.assertIn(f"Pengeluaran: {TOTAL}  ({TRANSAKSI} transaksi)", teks)

    def test_rekap_menghitung_pemasukan_ditambah_pengeluaran_di_samping_arus_kas(self):
        teks = rekap.susun(ROWS, date(2026, 11, 15))
        self.assertIn(f"Pengeluaran: {TOTAL}", teks)
        self.assertIn(f"({TRANSAKSI + 1} transaksi)", teks)  # + 1 Transaksi Pemasukan

    def test_pembeli_jumlahnya_per_orang_tapi_aturannya_sama(self):
        teks = pembeli.susun(ROWS, date(2026, 10, 12), date(2026, 10, 18), "x", peta={})
        self.assertIn(f"Total: {TOTAL}", teks)
        per_orang = [int(n) for n in re.findall(r"(\d+) transaksi", teks)]
        self.assertEqual(sum(per_orang), TRANSAKSI)  # S1+S3 milik Eryanto (2), S2 milik Elsi (1)

    def test_semua_laporan_sepakat_jumlah_transaksi_pengeluaran(self):
        angka = {
            "harian": int(re.search(r"(\d+) transaksi tercatat", harian.susun(ROWS, HARI)).group(1)),
            "mingguan": int(re.search(r"· (\d+) transaksi", mingguan.susun(
                ROWS, date(2026, 10, 12), date(2026, 10, 18), True)).group(1)),
            "bulanan": int(re.search(r"Pengeluaran: .*\((\d+) transaksi\)", bulanan.susun(
                "2026-10", ROWS, {}, {"bulan": {}}, [])).group(1)),
        }
        self.assertEqual(set(angka.values()), {TRANSAKSI}, angka)


if __name__ == "__main__":
    unittest.main()
