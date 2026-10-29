"""Tes scripts/duplikat.py — tiga lapis Duplikat lewat interface module saja.

    python3 -m unittest tests/test_duplikat.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import duplikat  # noqa: E402
import resi  # noqa: E402


def b(no_resi, tanggal="2026-10-20", waktu="10:00", jumlah=25000, item="Es Teh", tipe="pengeluaran",
      pencatat="Eryanto", **lain):
    d = {"tanggal": tanggal, "waktu": waktu, "tipe": tipe, "kategori": "food", "item": item,
         "jumlah": str(jumlah), "catatan": "", "channel": "whatsapp", "pencatat": pencatat,
         "akun": "", "akun_tujuan": "", "no_resi": no_resi}
    d.update(lain)
    return d


ADA = [b("A1"), b("B1", tanggal="2026-10-21", waktu="12:30", jumlah=40000, item="Nasi")]


class DenganKonfigurasi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.budget = Path(self.tmp.name) / "budget.json"
        self.asli = resi.BUDGET_JSON
        resi.BUDGET_JSON = self.budget
        self.atur({"aktif": True, "match_fields": ["tanggal", "waktu", "jumlah"], "aksi": "tolak"})

    def tearDown(self):
        resi.BUDGET_JSON = self.asli
        self.tmp.cleanup()

    def atur(self, duplicate_check):
        self.budget.write_text(json.dumps({"duplicate_check": duplicate_check}), encoding="utf-8")


class Lapis1(DenganKonfigurasi):
    def test_no_resi_sama_ditolak(self):
        pesan = duplikat.cek([b("A1", tanggal="2026-01-01", jumlah=1)], ADA)
        self.assertIn("DUPLICATE no_resi A1 sudah ada", pesan)
        self.assertIn("Lapis 1", pesan)

    def test_paksa_tidak_melewati_lapis_1(self):
        self.assertIn("DUPLICATE no_resi A1", duplikat.cek([b("A1", jumlah=1)], ADA, paksa=True))

    def test_bisa_dimatikan_untuk_pengubahan(self):
        # buku.py mengubah baris yang no_resi-nya memang sudah ada; hanya Lapis 2 yang relevan
        self.assertIsNone(duplikat.cek([b("A1", jumlah=1)], ADA, lapis_1=False))

    def test_hanya_baris_pertama_menentukan_no_resi(self):
        # satu struk berbanyak item berbagi no_resi; baris pertama mewakili
        self.assertIsNone(duplikat.cek([b("C1", jumlah=1), b("C1", jumlah=2)], ADA))


class Lapis2(DenganKonfigurasi):
    def test_cocok_pada_match_fields_ditolak(self):
        pesan = duplikat.cek([b("C1")], ADA)
        self.assertIn("DUPLICATE [A1]", pesan)
        self.assertIn("cocok pada: tanggal, waktu, jumlah", pesan)
        self.assertIn("aksi=tolak", pesan)

    def test_saran_paksa_ikut_pesan_kecuali_dimatikan(self):
        self.assertIn("--paksa", duplikat.cek([b("C1")], ADA))
        self.assertNotIn("--paksa", duplikat.cek([b("C1")], ADA, saran_paksa=False))

    def test_paksa_melewati_lapis_2(self):
        self.assertIsNone(duplikat.cek([b("C1")], ADA, paksa=True))

    def test_nonaktif(self):
        self.atur({"aktif": False})
        self.assertIsNone(duplikat.cek([b("C1")], ADA))

    def test_beda_satu_field_lolos(self):
        self.assertIsNone(duplikat.cek([b("C1", waktu="10:01")], ADA))

    def test_satu_arti_sama_untuk_jumlah(self):
        self.assertIn("DUPLICATE", duplikat.cek([b("C1", jumlah="Rp 25.000")], ADA))

    def test_satu_arti_sama_untuk_teks(self):
        self.atur({"aktif": True, "match_fields": ["tanggal", "item"], "aksi": "tolak"})
        self.assertIn("DUPLICATE", duplikat.cek([b("C1", item="es teh!", jumlah=1)], ADA))


class Audit(DenganKonfigurasi):
    def test_baris_kembar_di_semua_kolom_selain_no_resi(self):
        grup = duplikat.kelompok(ADA + [b("A2")])
        self.assertEqual([[r["no_resi"] for r in g] for g in grup], [["A1", "A2"]])

    def test_item_berbeda_dalam_satu_struk_bukan_kembar(self):
        self.assertEqual(duplikat.kelompok([b("S1", item="Nasi"), b("S1", item="Teh")]), [])

    def test_satu_arti_sama_juga_di_audit(self):
        grup = duplikat.kelompok([b("A1"), b("A2", item="es teh!", jumlah="Rp 25.000")])
        self.assertEqual(len(grup), 1)

    def test_pencatat_berbeda_bukan_kembar(self):
        self.assertEqual(duplikat.kelompok([b("A1"), b("A2", pencatat="Elsi")]), [])

    def test_urutan_grup_mengikuti_kemunculan_pertama(self):
        rows = [b("X1", jumlah=1), b("Y1", jumlah=2), b("Y2", jumlah=2), b("X2", jumlah=1)]
        self.assertEqual([g[0]["no_resi"] for g in duplikat.kelompok(rows)], ["X1", "Y1"])

    def test_tanpa_duplikat_kosong(self):
        self.assertEqual(duplikat.kelompok(ADA), [])


if __name__ == "__main__":
    unittest.main()
