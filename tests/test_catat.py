"""Tes scripts/catat.py — jalan tulis tunggal ke bills.csv.

    python3 -m unittest tests/test_catat.py
"""
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
spec = importlib.util.spec_from_file_location("catat", AKAR / "scripts" / "catat.py")
ct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct)
resi = ct.resi

HEADER = ",".join(resi.COLUMNS)
LAMA = "2026-09-14,pengeluaran,food,Momoyo,66000,,WhatsApp,Eryanto,,,,MOMOYO-14SEP"
JAM = datetime(2026, 9, 21, 22, 46)


def tx(**ubah):
    dasar = {"tanggal": "2026-09-21", "tipe": "pengeluaran", "channel": "whatsapp",
             "pencatat": "Eryanto", "items": [{"kategori": "food", "item": "Nasi goreng", "jumlah": 10000}]}
    dasar.update(ubah)
    return dasar


class Catat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.csv = d / "bills.csv"
        self.csv.write_text(f"{HEADER}\n{LAMA}\n", encoding="utf-8")
        budget = d / "budget.json"
        budget.write_text(json.dumps({
            "kategori_custom": ["food", "transport", "opening_balance"],
            "duplicate_check": {"aktif": True, "match_fields": ["tanggal", "waktu", "jumlah"], "aksi": "tolak"},
        }), encoding="utf-8")
        self.asli = (resi.BILLS_CSV, resi.BUDGET_JSON)
        resi.BILLS_CSV, resi.BUDGET_JSON = self.csv, budget

    def tearDown(self):
        resi.BILLS_CSV, resi.BUDGET_JSON = self.asli
        self.tmp.cleanup()

    def baris(self):
        with open(self.csv, newline="", encoding="utf-8") as f:
            return list(csv.reader(f))

    def test_baris_baru_selalu_12_kolom_dengan_waktu_dan_resi_trx(self):
        kode, pesan = ct.catat(tx(), sekarang=JAM)
        self.assertEqual(kode, 0, pesan)
        rows = self.baris()
        self.assertTrue(all(len(r) == 12 for r in rows))
        baru = dict(zip(resi.COLUMNS, rows[-1]))
        self.assertEqual(baru["waktu"], "22:46")
        self.assertRegex(baru["no_resi"], r"^TRX-20260921-\d{4}$")
        self.assertEqual(rows[1], next(csv.reader([LAMA])))  # baris lama tak tersentuh

    def test_struk_banyak_item_berbagi_satu_resi(self):
        kode, _ = ct.catat(tx(no_resi="STRUK-000123", items=[
            {"kategori": "food", "item": "Roti, isi keju", "jumlah": "Rp 12.000"},
            {"kategori": "transport", "item": "Parkir", "jumlah": 2000},
        ]), sekarang=JAM)
        self.assertEqual(kode, 0)
        rows = self.baris()[-2:]
        self.assertEqual({r[11] for r in rows}, {"STRUK-000123"})
        self.assertEqual(rows[0][3], "Roti, isi keju")
        self.assertEqual(rows[0][4], "12000")

    def test_resi_sama_ditolak_bahkan_dengan_paksa(self):
        kode, pesan = ct.catat(tx(no_resi="MOMOYO-14SEP"), paksa=True, sekarang=JAM)
        self.assertEqual(kode, 1)
        self.assertIn("DUPLICATE", pesan)
        self.assertEqual(len(self.baris()), 2)

    def test_lapis_2_menolak_kecuali_paksa(self):
        self.assertEqual(ct.catat(tx(waktu="10:00"), sekarang=JAM)[0], 0)
        kode, pesan = ct.catat(tx(waktu="10:00"), sekarang=JAM)
        self.assertEqual(kode, 1, pesan)
        self.assertEqual(ct.catat(tx(waktu="10:00"), paksa=True, sekarang=JAM)[0], 0)

    def test_masukan_buruk_tidak_ditulis(self):
        buruk = [
            tx(tipe="keluar"),
            tx(tanggal="21-09-2026"),
            tx(waktu="9.30"),
            tx(items=[{"kategori": "Makanan", "item": "x", "jumlah": 1}]),
            tx(items=[{"kategori": "opening_balance", "item": "x", "jumlah": 1}]),
            tx(items=[{"kategori": "food", "item": "x", "jumlah": 0}]),
            tx(akun_tujuan="Tabungan"),
            tx(pencatat=""),
        ]
        for t in buruk:
            self.assertEqual(ct.catat(t, sekarang=JAM)[0], 2, t)
        self.assertEqual(len(self.baris()), 2)

    def test_transfer_berkategori_transfer_dan_dua_akun(self):
        ok = tx(tipe="transfer", akun="Bank Utama", akun_tujuan="Kas",
                items=[{"kategori": "transfer", "item": "Tarik tunai", "jumlah": 500000}])
        self.assertEqual(ct.catat(ok, sekarang=JAM)[0], 0)
        tanpa_tujuan = dict(ok, akun_tujuan="")
        salah_kategori = dict(ok, items=[{"kategori": "food", "item": "x", "jumlah": 1}])
        transfer_bukan_transfer = tx(items=[{"kategori": "transfer", "item": "x", "jumlah": 1}])
        for t in (tanpa_tujuan, salah_kategori, transfer_bukan_transfer):
            self.assertEqual(ct.catat(t, sekarang=JAM)[0], 2, t)

    def test_mengikuti_akhir_baris_crlf_file(self):
        self.csv.write_bytes(f"{HEADER}\r\n{LAMA}\r\n".encode())
        self.assertEqual(ct.catat(tx(), sekarang=JAM)[0], 0)
        b = self.csv.read_bytes()
        self.assertEqual(b.count(b"\r\n"), b.count(b"\n"))
        self.assertEqual(b.count(b"\r\n"), 3)

    def test_uji_tidak_menulis(self):
        kode, pesan = ct.catat(tx(), uji=True, sekarang=JAM)
        self.assertEqual(kode, 0)
        self.assertIn("tidak ditulis", pesan)
        self.assertEqual(len(self.baris()), 2)


if __name__ == "__main__":
    unittest.main()
