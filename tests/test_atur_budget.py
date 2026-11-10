"""Tes scripts/atur-budget.py — satu-satunya jalan bot mengubah Budget, alert, dan Batas Kategori
(ADR-0029). Semua berkas di folder sementara.

    python3 -m unittest tests/test_atur_budget.py
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import resi  # noqa: E402

spec = importlib.util.spec_from_file_location("atur_budget", AKAR / "scripts" / "atur-budget.py")
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)

AWAL = {"budget_bulanan": 8_000_000, "alert_persen": 80,
        "kategori_custom": ["food", "groceries", "health", "transfer", "opening_balance", "reconciliation"],
        "label_kategori": {"food": "Makan & Minum", "groceries": "Belanja Dapur", "health": "Kesehatan"},
        "keterangan": {"budget_bulanan": "x"}, "pengeluaran_besar_mulai": 1_000_000}


class Dasar(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "budget.json"
        self.path.write_text(json.dumps(AWAL, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        asli = resi.BUDGET_JSON
        resi.BUDGET_JSON = self.path
        self.addCleanup(lambda: setattr(resi, "BUDGET_JSON", asli))

    def jalan(self, *argv):
        keluar = io.StringIO()
        with contextlib.redirect_stdout(keluar):
            kode = ab.main(list(argv))
        return kode, keluar.getvalue()

    def isi(self):
        return json.loads(self.path.read_text(encoding="utf-8"))


class Nominal(unittest.TestCase):
    def test_bentuk_yang_diketik_orang(self):
        for teks, nilai in [("2100000", 2_100_000), ("2.100.000", 2_100_000), ("Rp 2.100.000", 2_100_000),
                            ("2,1 jt", 2_100_000), ("2.1jt", 2_100_000), ("3 juta", 3_000_000),
                            ("600rb", 600_000), ("250 ribu", 250_000), ("1,25jt", 1_250_000)]:
            self.assertEqual(ab.nominal(teks), nilai, teks)

    def test_bukan_angka_ditolak(self):
        for teks in ("banyak", "", "-5000", "2,1"):
            with self.assertRaises(ab.Ditolak, msg=teks):
                ab.nominal(teks)


class BatasKategori(Dasar):
    def test_label_atau_slug_menjadi_slug_dan_urutan_kunci_dipertahankan(self):
        self.assertEqual(self.jalan("kategori", "Makan & Minum", "2,1 jt")[0], 0)
        kode, out = self.jalan("kategori", "groceries", "1.200.000")
        self.assertEqual(kode, 0, out)
        self.assertIn("Belanja Dapur (groceries): Rp 1.200.000/bulan", out)
        isi = self.isi()
        self.assertEqual(isi["budget_kategori"], {"food": 2_100_000, "groceries": 1_200_000})
        self.assertEqual(list(isi)[:4], ["budget_bulanan", "alert_persen", "kategori_custom", "label_kategori"])
        self.assertEqual(isi["keterangan"], {"budget_bulanan": "x"})

    def test_hapus(self):
        self.jalan("kategori", "food", "2100000")
        kode, out = self.jalan("kategori", "makan & minum", "--hapus")
        self.assertEqual(kode, 0, out)
        self.assertEqual(self.isi()["budget_kategori"], {})

    def test_kategori_tak_dikenal_ditolak_dengan_daftar_tanpa_mengubah_berkas(self):
        sebelum = self.path.read_bytes()
        kode, out = self.jalan("kategori", "Jajan", "100000")
        self.assertEqual(kode, 2)
        self.assertIn("Makan & Minum", out)
        self.assertEqual(self.path.read_bytes(), sebelum)

    def test_kategori_khusus_ditolak(self):
        for slug in ("opening_balance", "reconciliation", "transfer"):
            self.assertEqual(self.jalan("kategori", slug, "100000")[0], 2, slug)


class TotalDanAlert(Dasar):
    def test_total(self):
        kode, out = self.jalan("total", "9 juta")
        self.assertEqual((kode, self.isi()["budget_bulanan"]), (0, 9_000_000))
        self.assertIn("Rp 9.000.000", out)

    def test_alert_harus_1_sampai_100(self):
        self.assertEqual(self.jalan("alert", "75%")[0], 0)
        self.assertEqual(self.isi()["alert_persen"], 75)
        self.assertEqual(self.jalan("alert", "0")[0], 2)
        self.assertEqual(self.jalan("alert", "150")[0], 2)


if __name__ == "__main__":
    unittest.main()
