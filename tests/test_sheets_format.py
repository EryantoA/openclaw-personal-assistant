"""Tes scripts/sheets_format.py — tampilan worksheet "Buku Kas" (ADR-0026) dan baca baliknya.

    python3 -m unittest tests/test_sheets_format.py
"""
import sys
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import sheets_format as sf  # noqa: E402

LABEL = {"food": "Makan & Minum", "salary": "Gaji", "opening_balance": "Saldo Awal"}
SERIAL_5_SEP_2026 = 46270


def tx(tanggal, tipe, jumlah, kategori="food", item="x", no_resi="", waktu="", akun="", akun_tujuan=""):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "item": item, "jumlah": str(jumlah),
            "catatan": "", "channel": "whatsapp", "pencatat": "Eryanto", "akun": akun,
            "akun_tujuan": akun_tujuan, "waktu": waktu, "no_resi": no_resi}


def kol(baris, nama):
    return baris[sf.KOLOM_TAMPIL.index(nama)]


class Tampil(unittest.TestCase):
    def test_header_mengikuti_adr_0026(self):
        self.assertEqual(sf.KOLOM_TAMPIL, [
            "Tanggal", "Waktu", "No Resi", "Item", "Kategori", "Akun", "Akun Tujuan", "Pemasukan",
            "Pengeluaran", "Transfer", "Saldo Bersama", "Catatan", "Pencatat", "Asal"])

    def test_jumlah_masuk_ke_tepat_satu_kolom_sesuai_arah(self):
        rows = [tx("2026-09-01", "pemasukan", 5_000_000, "salary", no_resi="A"),
                tx("2026-09-02", "pengeluaran", 25_000, no_resi="B"),
                tx("2026-09-03", "transfer", 100_000, "other", no_resi="C", akun="Kas", akun_tujuan="Bank")]
        grid = sf.grid_tampil(rows, LABEL)
        uang = [[kol(b, k) for k in ("Pemasukan", "Pengeluaran", "Transfer")] for b in grid[1:]]
        self.assertEqual(uang, [[5_000_000, "", ""], ["", 25_000, ""], ["", "", 100_000]])

    def test_tipe_kosong_data_lama_tampil_sebagai_pengeluaran(self):
        grid = sf.grid_tampil([tx("2026-09-01", "", 9_000)], LABEL)
        self.assertEqual(kol(grid[1], "Pengeluaran"), 9_000)

    def test_kategori_tampil_sebagai_label_atau_slug_bila_tanpa_label(self):
        grid = sf.grid_tampil([tx("2026-09-01", "pengeluaran", 1, "food"),
                               tx("2026-09-01", "pengeluaran", 1, "pet")], LABEL)
        self.assertEqual([kol(b, "Kategori") for b in grid[1:]], ["Makan & Minum", "pet"])

    def test_tanggal_sah_dikirim_sebagai_serial_yang_tak_sah_apa_adanya(self):
        grid = sf.grid_tampil([tx("2026-09-05", "pengeluaran", 1), tx("kemarin", "pengeluaran", 1)], LABEL)
        self.assertEqual([kol(b, "Tanggal") for b in grid[1:]], [SERIAL_5_SEP_2026, "kemarin"])

    def test_urut_kronologis_terlama_di_atas_item_satu_struk_tetap_berurutan(self):
        rows = [tx("2026-09-02", "pengeluaran", 1, item="B", no_resi="S2"),
                tx("2026-09-01", "pengeluaran", 1, item="A2", no_resi="S1", waktu="10:00"),
                tx("2026-09-01", "pengeluaran", 1, item="A1", no_resi="S1", waktu="10:00"),
                tx("2026-09-01", "pengeluaran", 1, item="Z", no_resi="S0", waktu="08:00"),
                tx("rusak", "pengeluaran", 1, item="R")]
        self.assertEqual([kol(b, "Item") for b in sf.grid_tampil(rows, LABEL)[1:]],
                         ["Z", "A2", "A1", "B", "R"])

    def test_saldo_bersama_per_item_mulai_saldo_awal_transfer_tidak_menggeser(self):
        rows = [tx("2026-03-26", "pemasukan", 1_000_000, "opening_balance", no_resi="SALDO-AWAL"),
                tx("2026-09-01", "pengeluaran", 20_000, item="Susu", no_resi="S1"),
                tx("2026-09-01", "pengeluaran", 5_000, item="Roti", no_resi="S1"),
                tx("2026-09-02", "transfer", 300_000, "other", no_resi="T1"),
                tx("2026-09-03", "pemasukan", 100_000, "salary", no_resi="G1"),
                tx("rusak", "pengeluaran", 7, no_resi="X")]
        self.assertEqual([kol(b, "Saldo Bersama") for b in sf.grid_tampil(rows, LABEL)[1:]],
                         [1_000_000, 980_000, 975_000, 975_000, 1_075_000, ""])


class Baca(unittest.TestCase):
    def baca(self, baris):
        return sf.baca_baris(baris, sf.label_balik(LABEL))

    def test_baca_balik_tampilan_sama_dengan_bentuk_ternormal(self):
        rows = [tx("2026-09-05", "pemasukan", 5_000_000, "salary", no_resi="A", waktu="09:05"),
                tx("2026-09-05", "", 9_000, "pet", no_resi="B"),
                tx("2026-09-06", "transfer", 1, "other", no_resi="C", akun="Kas", akun_tujuan="Bank")]
        tampil = sf.grid_tampil(rows, LABEL)
        norm = sf.grid_norm(rows)
        self.assertEqual(norm[0], sf.KOLOM)
        self.assertEqual([self.baca(b) for b in tampil[1:]], [(n, None) for n in norm[1:]])

    def test_label_dan_slug_yang_diketik_keduanya_menjadi_slug(self):
        for ketik in ("Makan & Minum", "makan & minum", "food"):
            n, alasan = self.baca(["2026-09-01", "", "", "x", ketik, "", "", "", 1, ""])
            self.assertIsNone(alasan)
            self.assertEqual(n[sf.KOLOM.index("kategori")], "food")

    def test_kolom_uang_menentukan_tipe(self):
        n, _ = self.baca(["2026-09-01", "", "", "x", "Gaji", "", "", 5_000_000])
        self.assertEqual((n[sf.KOLOM.index("tipe")], n[sf.KOLOM.index("jumlah")]), ("pemasukan", "5000000"))

    def test_kosong_atau_lebih_dari_satu_kolom_uang_ditolak(self):
        for uang in (["", "", ""], [1, 2, ""], [1, "", 3]):
            n, alasan = self.baca(["2026-09-01", "", "R", "x", "food", "", ""] + uang)
            self.assertIsNone(n)
            self.assertIn("tepat satu dari Pemasukan, Pengeluaran, Transfer", alasan)

    def test_kolom_saldo_bersama_diabaikan(self):
        a, _ = self.baca(["2026-09-01", "", "R", "x", "food", "", "", "", 1, "", 999])
        b, _ = self.baca(["2026-09-01", "", "R", "x", "food", "", "", "", 1, "", "diketik"])
        self.assertEqual(a, b)

    def test_tanggal_serial_iso_dan_hari_bulan_tahun_diterima(self):
        for ketik in (SERIAL_5_SEP_2026, float(SERIAL_5_SEP_2026), "2026-09-05", "5/9/2026", "05/09/2026"):
            n, alasan = self.baca([ketik, "", "", "x", "food", "", "", "", 1])
            self.assertIsNone(alasan, ketik)
            self.assertEqual(n[0], "2026-09-05")

    def test_tanggal_tak_terbaca_ditolak(self):
        n, alasan = self.baca(["31/2/2026", "", "", "x", "food", "", "", "", 1])
        self.assertIsNone(n)
        self.assertIn("tanggal", alasan)

    def test_jumlah_teks_diteruskan_untuk_divalidasi_jalan_tulis(self):
        n, _ = self.baca(["2026-09-01", "", "", "x", "food", "", "", "", "Rp 1.500"])
        self.assertEqual(n[sf.KOLOM.index("jumlah")], "Rp 1.500")

    def test_baris_kosong_kecuali_saldo_dianggap_kosong(self):
        self.assertTrue(sf.kosong(["", "", "", "", "", "", "", "", "", "", 123]))
        self.assertFalse(sf.kosong(["", "", "", "x"]))


class LabelKategori(unittest.TestCase):
    def test_label_kembar_tidak_dipakai_dan_dilaporkan(self):
        label, kembar = sf.label_sah({"food": "Makan", "groceries": "Makan", "salary": "Gaji"})
        self.assertEqual(label, {"salary": "Gaji"})
        self.assertEqual(kembar, ["Makan"])

    def test_label_bukan_objek_diabaikan(self):
        self.assertEqual(sf.label_sah(["food"]), ({}, []))


if __name__ == "__main__":
    unittest.main()
