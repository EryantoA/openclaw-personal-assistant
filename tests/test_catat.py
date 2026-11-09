"""Tes scripts/catat.py — jalan tulis tunggal ke bills.csv.

    python3 -m unittest tests/test_catat.py
"""
import contextlib
import csv
import importlib.util
import io
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
        self.pembeli = d / "pembeli.json"
        self.pembeli.write_text(json.dumps({"Eryanto": ["ryan", "Teikoku"], "Elsi": ["istri"]}),
                                encoding="utf-8")
        self.asli_pembeli = resi.PEMBELI_JSON
        resi.PEMBELI_JSON = self.pembeli
        self.addCleanup(setattr, resi, "AKUN_JSON", resi.AKUN_JSON)
        self.akun = d / "akun.json"  # belum dibuat = nama Akun tak dicek
        resi.AKUN_JSON = self.akun

    def tearDown(self):
        resi.BILLS_CSV, resi.BUDGET_JSON = self.asli
        resi.PEMBELI_JSON = self.asli_pembeli
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

    def test_keluaran_ok_membawa_resi_waktu_tanggal_dan_pencatat(self):
        kode, pesan = ct.catat(tx(no_resi="STRUK-000123", waktu="09:15"), sekarang=JAM)
        self.assertEqual(kode, 0, pesan)
        baris_ok = pesan.splitlines()[0]
        self.assertEqual(
            baris_ok,
            "OK tersimpan 1 baris | no_resi STRUK-000123 | label Struk | waktu 09:15 | "
            "tanggal 2026-09-21 | pencatat Eryanto | nama_label Pembeli | arah 📤 Pengeluaran")

    def test_keluaran_uji_membawa_field_yang_sama_untuk_pratinjau(self):
        kode, pesan = ct.catat(tx(waktu="09:15"), uji=True, sekarang=JAM)
        self.assertEqual(kode, 0, pesan)
        self.assertRegex(pesan, r"^OK lolos cek \(tidak ditulis\): no_resi TRX-20260921-\d{4} "
                                r"\| label No Resi \| waktu 09:15 \| tanggal 2026-09-21 \| pencatat Eryanto "
                                r"\| nama_label Pembeli \| arah 📤 Pengeluaran$")
        self.assertEqual(len(self.baris()), 2)  # tidak menulis

    def test_keluaran_membawa_label_no_resi_untuk_resi_bebas(self):
        kode, pesan = ct.catat(tx(no_resi="IMP-262"), sekarang=JAM)
        self.assertEqual(kode, 0, pesan)
        self.assertIn("no_resi IMP-262 | label No Resi", pesan.splitlines()[0])

    def test_keluaran_membawa_arah_dan_nama_label_per_tipe(self):
        masuk = tx(tipe="pemasukan", items=[{"kategori": "food", "item": "Bonus", "jumlah": 170000}])
        pindah = tx(tipe="transfer", akun="Bank Utama", akun_tujuan="Kas",
                    items=[{"kategori": "transfer", "item": "Tarik tunai", "jumlah": 500000}])
        for t, akhir in ((masuk, "| nama_label Pencatat | arah 📥 Pemasukan"),
                         (pindah, "| nama_label Pencatat | arah 🔁 Transfer (Bank Utama → Kas)")):
            for uji in (True, False):
                kode, pesan = ct.catat(t, uji=uji, sekarang=JAM)
                self.assertEqual(kode, 0, pesan)
                self.assertTrue(pesan.splitlines()[0].endswith(akhir), pesan)

    def test_pencatat_alias_disimpan_dengan_nama_baku(self):
        for i, (alias, baku) in enumerate((("ryan", "Eryanto"), ("TEIKOKU", "Eryanto"),
                                            ("Istri", "Elsi"), ("Elsi", "Elsi"))):
            kode, pesan = ct.catat(tx(pencatat=alias, no_resi=f"STRUK-{alias}",
                                      items=[{"kategori": "food", "item": "x", "jumlah": 1000 + i}]), sekarang=JAM)
            self.assertEqual(kode, 0, pesan)
            self.assertEqual(self.baris()[-1][7], baku)
            self.assertIn(f"pencatat {baku}", pesan.splitlines()[0])

    def test_pencatat_tak_dikenal_atau_tanpa_berkas_dibiarkan(self):
        ct.catat(tx(pencatat="Tamu", no_resi="STRUK-1"), sekarang=JAM)
        self.assertEqual(self.baris()[-1][7], "Tamu")
        self.pembeli.unlink()
        ct.catat(tx(pencatat="ryan", no_resi="STRUK-2",
                    items=[{"kategori": "food", "item": "x", "jumlah": 2000}]), sekarang=JAM)
        self.assertEqual(self.baris()[-1][7], "ryan")

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

    def tulis_akun(self):
        self.akun.write_text(json.dumps({"cutover": "2026-11-09", "akun": [
            {"id": "tunai_a", "nama": "Tunai A", "saldo_awal": None},
            {"id": "bank_b", "nama": "Bank B", "saldo_awal": None}]}), encoding="utf-8")

    def test_akun_dibakukan_dari_id_atau_beda_huruf(self):
        self.tulis_akun()
        for i, (akun, tujuan) in enumerate((("tunai_a", "BANK  b"), ("tunai a", "bank_b"))):
            t = tx(tipe="transfer", akun=akun, akun_tujuan=tujuan, no_resi=f"STRUK-{i}",
                   items=[{"kategori": "transfer", "item": "Setor", "jumlah": 1000 + i}])
            kode, pesan = ct.catat(t, sekarang=JAM)
            self.assertEqual(kode, 0, pesan)
            self.assertEqual(self.baris()[-1][8:10], ["Tunai A", "Bank B"])

    def test_akun_tak_terdaftar_ditolak_dengan_pilihan(self):
        self.tulis_akun()
        for t in (tx(akun="Dompet A"),
                  tx(tipe="transfer", akun="Tunai A", akun_tujuan="Rekening Orang Lain",
                     items=[{"kategori": "transfer", "item": "x", "jumlah": 1}])):
            kode, pesan = ct.catat(t, sekarang=JAM)
            self.assertEqual(kode, 2, pesan)
            self.assertIn("tidak ada di data/akun.json", pesan)
            self.assertIn("Bank B, Tunai A", pesan)
        self.assertEqual(len(self.baris()), 2)

    def test_akun_kosong_tetap_boleh(self):
        self.tulis_akun()
        self.assertEqual(ct.catat(tx(), sekarang=JAM)[0], 0)

    def test_mengikuti_akhir_baris_crlf_file(self):
        self.csv.write_bytes(f"{HEADER}\r\n{LAMA}\r\n".encode())
        self.assertEqual(ct.catat(tx(), sekarang=JAM)[0], 0)
        b = self.csv.read_bytes()
        self.assertEqual(b.count(b"\r\n"), b.count(b"\n"))
        self.assertEqual(b.count(b"\r\n"), 3)

    def test_kunci_inggris_ditolak_dengan_petunjuk(self):
        kode, pesan = ct.catat({"amount": 10000, "category": "Food", "date": "2026-09-21"}, sekarang=JAM)
        self.assertEqual(kode, 2)
        self.assertIn("kunci tidak dikenal", pesan)
        self.assertIn("tanggal", pesan)
        self.assertEqual(len(self.baris()), 2)

    def test_uji_tidak_menulis(self):
        kode, pesan = ct.catat(tx(), uji=True, sekarang=JAM)
        self.assertEqual(kode, 0)
        self.assertIn("tidak ditulis", pesan)
        self.assertEqual(len(self.baris()), 2)


class Arah(unittest.TestCase):
    def test_arah_dan_nama_label(self):
        self.assertEqual(resi.arah_tampil({"tipe": "pengeluaran"}), "📤 Pengeluaran")
        self.assertEqual(resi.arah_tampil({"tipe": "pemasukan"}), "📥 Pemasukan")
        self.assertEqual(resi.arah_tampil({"tipe": "transfer", "akun": "BCA", "akun_tujuan": "Tabungan"}),
                         "🔁 Transfer (BCA → Tabungan)")
        self.assertEqual(resi.label_nama({"tipe": "pengeluaran"}), "Pembeli")
        for tipe in ("pemasukan", "transfer"):
            self.assertEqual(resi.label_nama({"tipe": tipe}), "Pencatat")


class LabelResi(unittest.TestCase):
    def test_struk_untuk_awalan_struk(self):
        for no_resi in ("STRUK-000123", "STRUK-a1b2c3d4"):
            self.assertEqual(resi.label_resi(no_resi), "Struk")

    def test_no_resi_untuk_awalan_lain(self):
        for no_resi in ("TRX-20260921-0001", "IMP-262", "SALDO-AWAL", "MOMOYO-14SEP"):
            self.assertEqual(resi.label_resi(no_resi), "No Resi")

    def test_kosong_tidak_error(self):
        for no_resi in ("", None):
            self.assertEqual(resi.label_resi(no_resi), "No Resi")


class PilihanKategoriDiGalat(unittest.TestCase):
    """Agen Relay tidak boleh membaca budget.json; galatnya yang menyebut pilihan (ADR-0023)."""
    setUp, tearDown = Catat.setUp, Catat.tearDown

    def test_kategori_salah_menyebut_pilihan_yang_sah(self):
        kode, pesan = ct.catat(tx(items=[{"kategori": "makanan", "item": "x", "jumlah": 1000}]), uji=True)
        self.assertEqual(kode, 2)
        self.assertIn("'makanan'", pesan)
        self.assertIn("pilihan: food, transport", pesan)  # opening_balance tidak ditawarkan


class MasukanLewatArgumen(unittest.TestCase):
    """`--json` menggantikan stdin: agen berallowlist tidak boleh memakai pengalihan (ADR-0023)."""
    setUp, tearDown, baris = Catat.setUp, Catat.tearDown, Catat.baris

    def cli(self, argv, stdin=""):
        keluar, asli_stdin = io.StringIO(), sys.stdin
        sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(keluar):
                kode = ct.main(argv)
        finally:
            sys.stdin = asli_stdin
        return kode, keluar.getvalue()

    def test_json_argumen_menyimpan_sama_seperti_stdin(self):
        kode, out = self.cli(["--json", json.dumps(tx())])
        self.assertEqual(kode, 0, out)
        self.assertTrue(out.startswith("OK tersimpan"), out)
        self.assertEqual(len(self.baris()), 3)

    def test_json_argumen_dengan_uji_tidak_menulis(self):
        kode, out = self.cli(["--uji", "--json", json.dumps(tx())])
        self.assertEqual(kode, 0, out)
        self.assertTrue(out.startswith("OK lolos cek"), out)
        self.assertEqual(len(self.baris()), 2)

    def test_json_argumen_menang_atas_stdin(self):
        kode, out = self.cli(["--json", json.dumps(tx())], stdin="bukan json")
        self.assertEqual(kode, 0, out)

    def test_tanpa_json_stdin_tetap_dipakai(self):
        kode, out = self.cli([], stdin=json.dumps(tx()))
        self.assertEqual(kode, 0, out)
        self.assertEqual(len(self.baris()), 3)

    def test_json_argumen_rusak_ditolak_tanpa_menulis(self):
        kode, out = self.cli(["--json", "{rusak"])
        self.assertEqual(kode, 2)
        self.assertIn("ERROR JSON tidak valid", out)
        self.assertEqual(len(self.baris()), 2)

    def test_apostrof_ditulis_u0027_di_dalam_kutip_tunggal(self):
        # Di shell, apostrof memutus kutip tunggal; \u0027 adalah JSON sah untuk karakter itu.
        mentah = '{"tanggal": "2026-09-21", "tipe": "pengeluaran", "channel": "whatsapp", ' \
                 '"pencatat": "Eryanto", "items": [{"kategori": "food", "item": "Mie Ani\\u0027s", ' \
                 '"jumlah": 12000}]}'
        self.assertNotIn("'", mentah)
        kode, out = self.cli(["--json", mentah])
        self.assertEqual(kode, 0, out)
        self.assertEqual(self.baris()[-1][3], "Mie Ani's")


if __name__ == "__main__":
    unittest.main()
