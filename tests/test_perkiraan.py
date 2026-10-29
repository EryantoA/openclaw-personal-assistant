"""Tes scripts/perkiraan.py dan scripts/pengaturan.py — Perkiraan yang tidak muncul (ADR-0006).

    python3 -m unittest tests/test_perkiraan.py
"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pengaturan  # noqa: E402
import perkiraan  # noqa: E402

PENGATURAN = {"perkiraan_toleransi_hari": 3, "perkiraan_toleransi_persen": 10}
GAJI = {"id": "PRK-1", "nama": "Gaji", "arah": "masuk", "kategori": "salary",
        "nominal": 5_000_000, "tanggal_biasanya": 26}
LANGGANAN = {"id": "PRK-2", "nama": "Langganan", "arah": "keluar", "kategori": "subscription",
             "nominal": 366_588, "tanggal_biasanya": 26, "toleransi_persen": 1}


def tx(tanggal, tipe, kategori, jumlah):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah)}


def absen(daftar, rows, tahun=2026, bulan=10, today=None, atur=PENGATURAN):
    return [e["id"] for e in perkiraan.absen(daftar, rows, tahun, bulan, today, atur)]


class Absen(unittest.TestCase):
    def test_ketemu_dalam_toleransi(self):
        rows = [tx("2026-10-27", "pemasukan", "salary", 4_600_000)]  # selisih 8%
        self.assertEqual(absen([GAJI], rows), [])

    def test_di_luar_toleransi_absen(self):
        rows = [tx("2026-10-27", "pemasukan", "salary", 4_400_000)]  # selisih 12%
        self.assertEqual(absen([GAJI], rows), ["PRK-1"])

    def test_toleransi_per_entri(self):
        self.assertEqual(absen([LANGGANAN], [tx("2026-10-26", "pengeluaran", "subscription", 366_751)]), [])
        # 3,6% lolos toleransi umum 10%, tapi entri ini memperketat ke 1%
        self.assertEqual(absen([LANGGANAN], [tx("2026-10-26", "pengeluaran", "subscription", 380_000)]),
                         ["PRK-2"])

    def test_arah_dan_kategori_harus_cocok(self):
        self.assertEqual(absen([GAJI], [tx("2026-10-27", "pengeluaran", "salary", 5_000_000)]), ["PRK-1"])
        self.assertEqual(absen([GAJI], [tx("2026-10-27", "pemasukan", "bonus", 5_000_000)]), ["PRK-1"])

    def test_bulan_lain_tidak_dihitung(self):
        self.assertEqual(absen([GAJI], [tx("2026-09-26", "pemasukan", "salary", 5_000_000)]), ["PRK-1"])

    def test_bulan_berjalan_menunggu_toleransi_hari(self):
        self.assertEqual(absen([GAJI], [], today=date(2026, 10, 29)), [])        # 3 hari: belum
        self.assertEqual(absen([GAJI], [], today=date(2026, 10, 30)), ["PRK-1"])  # 4 hari: ditanya

    def test_bulan_tutup_semua_diperiksa(self):
        self.assertEqual(absen([GAJI, LANGGANAN], []), ["PRK-1", "PRK-2"])

    def test_tanggal_31_di_bulan_pendek(self):
        akhir = dict(GAJI, tanggal_biasanya=31)
        self.assertEqual(absen([akhir], [], bulan=2, today=date(2026, 2, 28)), [])
        self.assertEqual(absen([akhir], [], bulan=2, today=date(2026, 3, 4)), ["PRK-1"])

    def test_entri_rusak_dilewati(self):
        rusak = [dict(GAJI, id="A", tanggal_biasanya=0), dict(GAJI, id="B", nominal=0),
                 dict(GAJI, id="C", nominal="abc"), dict(GAJI, id="D", tanggal_biasanya=32)]
        self.assertEqual(absen(rusak, []), [])

    def test_toleransi_bawaan_bila_pengaturan_kosong(self):
        rows = [tx("2026-10-27", "pemasukan", "salary", 4_600_000)]
        self.assertEqual(absen([GAJI], rows, atur={}), [])
        self.assertEqual(absen([GAJI], [], today=date(2026, 10, 29), atur={}), [])


class Muat(unittest.TestCase):
    def test_hanya_yang_aktif(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "perkiraan.json"
            p.write_text(json.dumps({"perkiraan": [GAJI, dict(LANGGANAN, aktif=False)]}), encoding="utf-8")
            self.assertEqual([e["id"] for e in perkiraan.muat(p)], ["PRK-1"])

    def test_tidak_ada_atau_rusak_kosong(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "perkiraan.json"
            self.assertEqual(perkiraan.muat(p), [])
            p.write_text("{rusak", encoding="utf-8")
            self.assertEqual(perkiraan.muat(p), [])


class Pengaturan(unittest.TestCase):
    def test_bawaan_digabung_isi_berkas(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "budget.json"
            self.assertEqual(pengaturan.muat(p), pengaturan.BAWAAN)
            p.write_text(json.dumps({"budget_bulanan": 7_000_000, "perkiraan_toleransi_hari": 5}),
                         encoding="utf-8")
            atur = pengaturan.muat(p)
            self.assertEqual((atur["budget_bulanan"], atur["alert_persen"], atur["perkiraan_toleransi_hari"]),
                             (7_000_000, 80, 5))
            p.write_text("{rusak", encoding="utf-8")
            self.assertEqual(pengaturan.muat(p), pengaturan.BAWAAN)

    def test_bawaan_tidak_ikut_berubah(self):
        pengaturan.muat(Path("/tidak/ada.json"))["budget_bulanan"] = 1
        self.assertEqual(pengaturan.BAWAAN["budget_bulanan"], 0)


if __name__ == "__main__":
    unittest.main()
