"""Tes scripts/buku.py — cari, ubah, hapus data yang sudah ada di CSV.

    python3 -m unittest tests/test_buku.py

Satu seam: jalankan(...) / cari(...) terhadap CSV sementara (pola tests/test_catat.py).
"""
import csv
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import buku as bk  # noqa: E402

resi = bk.resi

HEADER = ",".join(resi.COLUMNS)
# tanggal,tipe,kategori,item,jumlah,catatan,channel,pencatat,akun,akun_tujuan,waktu,no_resi
BARIS = [
    "2026-10-10,pengeluaran,food,Nasi goreng - Warung Ani,25000,,whatsapp,Eryanto,,,12:00,STRUK-A",
    '2026-10-12,pengeluaran,groceries,"Susu UHT, 2 x 12.500",25000,via GoPay,whatsapp,Elsi,,,14:30,STRUK-B',
    "2026-10-12,pengeluaran,food,Roti,8000,,whatsapp,Elsi,,,14:30,STRUK-B",
    "2026-09-27,pemasukan,salary,Gaji,5000000,,whatsapp,Eryanto,,,08:00,STRUK-GAJI",
    "2026-10-13,transfer,transfer,Tarik tunai,500000,,whatsapp,Eryanto,Bank Utama,Kas,09:00,STRUK-T",
    "2026-07-01,pemasukan,opening_balance,Saldo awal,1000,,import,Eryanto,,,00:00,SALDO-AWAL",
]
SEKARANG = datetime(2026, 10, 16, 10, 0, 0)


class Dasar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.csv = self.d / "bills.csv"
        self.tulis("\n".join([HEADER, *BARIS]) + "\n")
        (self.d / "budget.json").write_text(json.dumps({
            "kategori_custom": ["food", "groceries", "transport", "salary", "opening_balance"],
            "duplicate_check": {"aktif": True, "match_fields": ["tanggal", "waktu", "jumlah"],
                                "aksi": "tolak"},
        }), encoding="utf-8")
        (self.d / "pembeli.json").write_text(json.dumps({"Eryanto": ["ryan"], "Elsi": ["istri"]}),
                                             encoding="utf-8")
        self.asli = (resi.BILLS_CSV, resi.BUDGET_JSON, resi.PEMBELI_JSON)
        resi.BILLS_CSV, resi.BUDGET_JSON, resi.PEMBELI_JSON = (
            self.csv, self.d / "budget.json", self.d / "pembeli.json")
        self.skema = bk.skema_bills()

    def tearDown(self):
        resi.BILLS_CSV, resi.BUDGET_JSON, resi.PEMBELI_JSON = self.asli
        self.tmp.cleanup()

    def tulis(self, teks):
        self.csv.write_bytes(teks.encode("utf-8"))

    def mentah(self):
        return self.csv.read_bytes()

    def baris(self):
        with open(self.csv, newline="", encoding="utf-8") as f:
            return list(csv.reader(f))

    def jejak(self):
        j = self.d / "riwayat-ubah.csv"
        if not j.exists():
            return []
        with open(j, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def cadangan(self):
        return sorted((self.d / "backups").glob("bills_sebelum-*")) if (self.d / "backups").exists() else []

    def jalan(self, aksi, req, uji=False):
        return bk.jalankan(self.skema, aksi, {"oleh": "ryan", **req}, uji=uji, sekarang=SEKARANG)

    def sidik(self, aksi, req):
        kode, pesan = self.jalan(aksi, req, uji=True)
        self.assertEqual(kode, 0, pesan)
        return re.search(r"sidik (\w+)", pesan).group(1)

    def terapkan(self, aksi, req):
        return self.jalan(aksi, {**req, "sidik": self.sidik(aksi, req)})


class Cari(Dasar):
    def cari(self, **f):
        return bk.cari(self.skema, **f)

    def test_per_struk_dengan_nomor_item_dan_total(self):
        kode, pesan = self.cari(resi_="STRUK-B")
        self.assertEqual(kode, 0)
        self.assertIn("🔍 Hasil pencarian: STRUK-B (1 transaksi)", pesan)
        self.assertIn("Struk: STRUK-B | Tanggal: 2026-10-12 | Jam: 14:30", pesan)
        self.assertIn("Pembeli: Elsi", pesan)
        self.assertIn("- [1] Susu UHT, 2 x 12.500: Rp 25.000", pesan)
        self.assertIn("- [2] Roti: Rp 8.000", pesan)
        self.assertIn("- Total: Rp 33.000", pesan)

    def test_filter_dan_kombinasinya(self):
        self.assertIn("STRUK-A", self.cari(kata="nasi")[1])
        self.assertNotIn("STRUK-B", self.cari(kata="nasi")[1])
        self.assertIn("(1 transaksi)", self.cari(pembeli="istri")[1])      # alias istri -> Elsi
        self.assertIn("STRUK-B", self.cari(pembeli="istri")[1])
        self.assertIn("(3 transaksi)", self.cari(dari="2026-10-01", sampai="2026-10-31")[1])
        self.assertIn("(1 transaksi)", self.cari(kategori="groceries")[1])
        self.assertIn("STRUK-T", self.cari(tipe="transfer")[1])
        self.assertIn("(1 transaksi)", self.cari(kata="roti", tanggal="2026-10-12", kategori="food")[1])

    def test_batas_dan_penanda_terpotong(self):
        kode, pesan = self.cari(dari="2000-01-01", batas=2)
        self.assertIn("(5 transaksi) — tampil 2 terbaru", pesan)
        self.assertEqual(pesan.count("Struk:"), 2)

    def test_terbaru_dulu_dan_terakhir_dicatat(self):
        urut = [m for m in re.findall(r"Struk: (\S+)", self.cari(batas=10)[1])]
        self.assertEqual(urut[0], "STRUK-T")                      # tanggal terbaru
        urut = re.findall(r"Struk: (\S+)", self.cari(terakhir=True, batas=10)[1])
        self.assertEqual(urut[0], "SALDO-AWAL")                   # paling bawah di berkas
        self.assertIn("STRUK-GAJI", self.cari(pembeli="ryan", batas=1, terakhir=True)[1] +
                      self.cari(pembeli="ryan", terakhir=True)[1])

    def test_tanpa_hasil_dijawab_jelas(self):
        kode, pesan = self.cari(kata="tidak-ada")
        self.assertEqual(kode, 0)
        self.assertIn("tidak ditemukan", pesan)

    def test_read_only(self):
        sebelum = self.mentah()
        self.cari(kata="nasi")
        self.assertEqual(self.mentah(), sebelum)
        self.assertEqual(self.cadangan(), [])
        self.assertEqual(self.jejak(), [])


class Hapus(Dasar):
    def test_uji_tidak_menulis_dan_memberi_pratinjau(self):
        sebelum = self.mentah()
        kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-B"}, uji=True)
        self.assertEqual(kode, 0, pesan)
        self.assertIn("OK lolos cek (tidak ditulis)", pesan)
        self.assertIn("Hapus Transaksi STRUK-B", pesan)
        self.assertIn("- [2] Roti: Rp 8.000", pesan)
        self.assertIn("Total dihapus: Rp 33.000", pesan)
        self.assertEqual(self.mentah(), sebelum)
        self.assertEqual(self.cadangan(), [])
        self.assertEqual(self.jejak(), [])

    def test_hapus_transaksi_utuh_baris_lain_utuh_byte_demi_byte(self):
        sebelum = self.mentah().decode()
        kode, pesan = self.terapkan("hapus", {"no_resi": "STRUK-B"})
        self.assertEqual(kode, 0, pesan)
        self.assertTrue(pesan.startswith("OK terhapus"))
        harapan = "".join(l for l in sebelum.splitlines(keepends=True) if "STRUK-B" not in l)
        self.assertEqual(self.mentah().decode(), harapan)

    def test_cadangan_dan_jejak_per_mutasi(self):
        sebelum = self.mentah()
        self.terapkan("hapus", {"no_resi": "STRUK-A"})
        cad = self.cadangan()
        self.assertEqual(len(cad), 1)
        self.assertEqual(cad[0].read_bytes(), sebelum)
        j = self.jejak()
        self.assertEqual(len(j), 1)
        self.assertEqual((j[0]["aksi"], j[0]["no_resi"], j[0]["oleh"]), ("hapus", "STRUK-A", "Eryanto"))
        self.assertEqual(json.loads(j[0]["sebelum"])[0]["item"], "Nasi goreng - Warung Ani")
        self.assertEqual(json.loads(j[0]["sesudah"]), [])

    def test_penolakan_dan_uji_tidak_menambah_jejak(self):
        self.jalan("hapus", {"no_resi": "TIDAK-ADA"})
        self.jalan("hapus", {"no_resi": "STRUK-A", "sidik": "salah"})
        self.jalan("hapus", {"no_resi": "STRUK-A"}, uji=True)
        self.assertEqual(self.jejak(), [])
        self.assertEqual(self.cadangan(), [])

    def test_sidik_wajib_dan_sidik_basi_ditolak(self):
        kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-A"})
        self.assertEqual(kode, 2)
        self.assertIn("sidik", pesan)
        sidik = self.sidik("hapus", {"no_resi": "STRUK-A"})
        # data berubah di antara Pratinjau dan jawaban ya
        self.tulis(self.mentah().decode().replace(",25000,,whatsapp,Eryanto,,,12:00",
                                                  ",26000,,whatsapp,Eryanto,,,12:00"))
        kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-A", "sidik": sidik})
        self.assertEqual(kode, 2)
        self.assertIn("sidik tidak cocok", pesan)
        self.assertIn("STRUK-A", self.mentah().decode())

    def test_sidik_terikat_pada_permintaan(self):
        sidik = self.sidik("hapus", {"no_resi": "STRUK-B", "item_ke": 1})
        kode, _ = self.jalan("hapus", {"no_resi": "STRUK-B", "sidik": sidik})  # seluruh Transaksi
        self.assertEqual(kode, 2)

    def test_hapus_satu_item(self):
        kode, pesan = self.terapkan("hapus", {"no_resi": "STRUK-B", "item_ke": 2})
        self.assertEqual(kode, 0, pesan)
        teks = self.mentah().decode()
        self.assertNotIn("Roti", teks)
        self.assertIn("Susu UHT", teks)
        self.assertEqual(len(self.baris()), len(BARIS))  # header + 5

    def test_item_terakhir_sama_dengan_hapus_transaksi(self):
        self.terapkan("hapus", {"no_resi": "STRUK-A", "item_ke": 1})
        self.assertNotIn("STRUK-A", self.mentah().decode())
        self.assertEqual(self.jejak()[0]["item_ke"], "")

    def test_nomor_item_salah_ditolak(self):
        for ke in (0, 3, "x"):
            kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-B", "item_ke": ke}, uji=True)
            self.assertEqual(kode, 2, ke)

    def test_opening_balance_tidak_bisa_dihapus(self):
        kode, pesan = self.jalan("hapus", {"no_resi": "SALDO-AWAL"}, uji=True)
        self.assertEqual(kode, 2)
        self.assertIn("opening_balance", pesan)

    def test_resi_kosong_atau_oleh_kosong_ditolak(self):
        self.assertEqual(bk.jalankan(self.skema, "hapus", {"oleh": "x"}, uji=True)[0], 2)
        self.assertEqual(bk.jalankan(self.skema, "hapus", {"no_resi": "STRUK-A"}, uji=True)[0], 2)
        self.assertEqual(bk.jalankan(self.skema, "hapus", {"no_resi": "A", "oleh": "x", "x": 1},
                                     uji=True)[0], 2)

    def test_mempertahankan_crlf_dan_baris_terakhir_tanpa_akhir_baris(self):
        self.tulis("\r\n".join([HEADER, *BARIS]))  # CRLF, tanpa EOL di baris terakhir
        self.terapkan("hapus", {"no_resi": "STRUK-A"})
        b = self.mentah()
        self.assertEqual(b.count(b"\r\n"), b.count(b"\n"))
        self.assertFalse(b.endswith(b"\n"))
        self.terapkan("hapus", {"no_resi": "STRUK-T"})
        self.assertNotIn(b"STRUK-T", self.mentah())

    def test_berkas_kerja_sementara_tidak_tertinggal(self):
        self.terapkan("hapus", {"no_resi": "STRUK-A"})
        self.assertEqual([p.name for p in self.d.glob("*.proses")], [])

    def test_baris_rusak_tidak_disentuh(self):
        self.tulis(self.mentah().decode() + "2026-10-14,pengeluaran,food,Rusak,1,,whatsapp,E,,,10:00,STRUK-R,EXTRA\n")
        kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-R"}, uji=True)
        self.assertEqual(kode, 2)
        self.assertIn("rusak", pesan)

    def test_dua_mutasi_berurutan_tidak_saling_menimpa(self):
        self.terapkan("hapus", {"no_resi": "STRUK-A"})
        self.terapkan("hapus", {"no_resi": "STRUK-T"})
        teks = self.mentah().decode()
        self.assertNotIn("STRUK-A", teks)
        self.assertNotIn("STRUK-T", teks)
        self.assertEqual(len(self.jejak()), 2)


class Ubah(Dasar):
    def test_ubah_item_tunggal(self):
        kode, pesan = self.terapkan("ubah", {"no_resi": "STRUK-B", "item_ke": 1,
                                             "set": {"jumlah": "Rp 30.000", "kategori": "food"}})
        self.assertEqual(kode, 0, pesan)
        self.assertTrue(pesan.startswith("OK terubah"))
        rows = self.baris()
        self.assertEqual(rows[2][2:5], ["food", "Susu UHT, 2 x 12.500", "30000"])
        self.assertEqual(rows[3][3:5], ["Roti", "8000"])        # item lain tak berubah
        self.assertEqual(len(rows), len(BARIS) + 1)

    def test_pratinjau_sebelum_sesudah(self):
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-B", "item_ke": 1, "set": {"jumlah": 30000}},
                                 uji=True)
        self.assertEqual(kode, 0, pesan)
        self.assertIn("- [1] jumlah: Rp 25.000 → Rp 30.000", pesan)
        self.assertIn("Total Transaksi: Rp 33.000 → Rp 38.000", pesan)

    def test_kolom_tingkat_transaksi_berlaku_ke_semua_item(self):
        kode, pesan = self.terapkan("ubah", {"no_resi": "STRUK-B", "set": {"tanggal": "2026-10-13", "waktu": "15:00"}})
        self.assertEqual(kode, 0, pesan)
        rows = self.baris()
        self.assertEqual({r[0] for r in rows[2:4]}, {"2026-10-13"})
        self.assertEqual({r[10] for r in rows[2:4]}, {"15:00"})

    def test_pencatat_alias_dibakukan(self):
        self.terapkan("ubah", {"no_resi": "STRUK-A", "set": {"pencatat": "istri"}})
        self.assertEqual(self.baris()[1][7], "Elsi")

    def test_kolom_item_butuh_item_ke_bila_banyak_item(self):
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-B", "set": {"kategori": "food"}}, uji=True)
        self.assertEqual(kode, 2)
        self.assertIn("item_ke", pesan)
        kode, _ = self.jalan("ubah", {"no_resi": "STRUK-B", "item_ke": "semua", "set": {"kategori": "food"}},
                             uji=True)
        self.assertEqual(kode, 0)
        kode, _ = self.jalan("ubah", {"no_resi": "STRUK-A", "set": {"kategori": "groceries"}}, uji=True)
        self.assertEqual(kode, 0)  # satu item: tak perlu item_ke

    def test_kolom_transaksi_dengan_item_ke_ditolak(self):
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-B", "item_ke": 1, "set": {"tanggal": "2026-10-13"}},
                                 uji=True)
        self.assertEqual(kode, 2)
        self.assertIn("seluruh Transaksi", pesan)

    def test_kolom_terkunci_dan_tak_dikenal_ditolak(self):
        for kolom in ("no_resi", "channel", "warna"):
            kode, _ = self.jalan("ubah", {"no_resi": "STRUK-A", "set": {kolom: "x"}}, uji=True)
            self.assertEqual(kode, 2, kolom)

    def test_hasil_tidak_valid_ditolak_tanpa_menulis(self):
        sebelum = self.mentah()
        buruk = [{"kategori": "Makanan"}, {"kategori": "opening_balance"}, {"jumlah": 0},
                 {"jumlah": "abc"}, {"tanggal": "12-10-2026"}, {"waktu": "9.30"}, {"item": " "},
                 {"tipe": "keluar"}, {"akun_tujuan": "Kas"}, {"tipe": "transfer"}]
        for st in buruk:
            kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-A", "set": st}, uji=True)
            self.assertEqual(kode, 2, (st, pesan))
        self.assertEqual(self.mentah(), sebelum)

    def test_transfer_tetap_konsisten(self):
        kode, _ = self.jalan("ubah", {"no_resi": "STRUK-T", "set": {"akun_tujuan": ""}}, uji=True)
        self.assertEqual(kode, 2)
        kode, _ = self.jalan("ubah", {"no_resi": "STRUK-T", "set": {"akun_tujuan": "Tabungan"}}, uji=True)
        self.assertEqual(kode, 0)
        kode, _ = self.jalan("ubah", {"no_resi": "STRUK-T", "set": {"kategori": "food"}}, uji=True)
        self.assertEqual(kode, 2)

    def test_hasil_duplikat_ditolak_dengan_kode_1(self):
        # STRUK-A (2026-10-10 12:00 25000) dijadikan 14:30 -> sama dengan baris pertama STRUK-B? jumlah 25000
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-A", "set": {"tanggal": "2026-10-12", "waktu": "14:30"}},
                                 uji=True)
        self.assertEqual(kode, 1, pesan)
        self.assertIn("DUPLICATE", pesan)

    def test_duplikat_lama_tidak_menghalangi_ubah_kolom_lain(self):
        self.tulis(self.mentah().decode() + "2026-10-10,pengeluaran,food,Dobel,25000,,whatsapp,Eryanto,,,12:00,STRUK-D\n")
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-D", "set": {"item": "Dobel lama"}}, uji=True)
        self.assertEqual(kode, 0, pesan)

    def test_tanpa_perubahan_ditolak(self):
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-A", "set": {"jumlah": 25000}}, uji=True)
        self.assertEqual(kode, 2)
        self.assertIn("tidak ada yang berubah", pesan)

    def test_opening_balance_tidak_bisa_diubah(self):
        kode, _ = self.jalan("ubah", {"no_resi": "SALDO-AWAL", "set": {"jumlah": 1}}, uji=True)
        self.assertEqual(kode, 2)

    def test_sidik_berubah_bila_set_berbeda(self):
        a = self.sidik("ubah", {"no_resi": "STRUK-A", "set": {"jumlah": 26000}})
        b = self.sidik("ubah", {"no_resi": "STRUK-A", "set": {"jumlah": 27000}})
        self.assertNotEqual(a, b)
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-A", "set": {"jumlah": 27000}, "sidik": a})
        self.assertEqual(kode, 2)

    def test_cadangan_jejak_dan_baris_lain_utuh(self):
        sebelum = self.mentah().decode()
        self.terapkan("ubah", {"no_resi": "STRUK-A", "set": {"jumlah": 26000}})
        sesudah = self.mentah().decode()
        beda = [(a, b) for a, b in zip(sebelum.splitlines(), sesudah.splitlines()) if a != b]
        self.assertEqual(len(beda), 1)
        self.assertEqual(len(self.cadangan()), 1)
        self.assertEqual(self.cadangan()[0].read_text(), sebelum)
        j = self.jejak()[0]
        self.assertEqual((j["aksi"], j["no_resi"]), ("ubah", "STRUK-A"))
        self.assertEqual(json.loads(j["sebelum"])[0]["jumlah"], "25000")
        self.assertEqual(json.loads(j["sesudah"])[0]["jumlah"], "26000")

    def test_hasil_ubah_tetap_dua_belas_kolom(self):
        self.terapkan("ubah", {"no_resi": "STRUK-B", "item_ke": 2, "set": {"catatan": "tunai, kasir 2"}})
        self.assertTrue(all(len(r) == 12 for r in self.baris()))
        self.assertEqual(self.baris()[3][5], "tunai, kasir 2")


class Peringatan(Dasar):
    def test_kewajiban_tertaut_diperingatkan_saat_hapus(self):
        (self.d / "kewajiban.json").write_text(json.dumps({"kewajiban": [
            {"id": "KWJ-001", "nama": "WiFi", "lunas_resi": "STRUK-A"}]}), encoding="utf-8")
        kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-A"}, uji=True)
        self.assertEqual(kode, 0)
        self.assertIn("Kewajiban WiFi (KWJ-001)", pesan)
        self.assertIn("belum lunas", pesan)
        kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-B"}, uji=True)
        self.assertNotIn("Kewajiban", pesan)

    def test_bulan_dilaporkan_diperingatkan_bila_arus_berubah(self):
        (self.d / "laporan-bulanan.json").write_text(json.dumps({"bulan": {"2026-10": {}}}), encoding="utf-8")
        kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-A"}, uji=True)
        self.assertIn("Bulan 2026-10 sudah dilaporkan", pesan)
        self.assertIn("Koreksi", pesan)
        # kategori tidak mengubah arus -> tanpa peringatan
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-A", "set": {"kategori": "groceries"}}, uji=True)
        self.assertNotIn("Koreksi", pesan)
        # pindah bulan: bulan lama dan baru sama-sama disebut
        (self.d / "laporan-bulanan.json").write_text(json.dumps({"bulan": {"2026-10": {}, "2026-11": {}}}),
                                                     encoding="utf-8")
        kode, pesan = self.jalan("ubah", {"no_resi": "STRUK-A", "set": {"tanggal": "2026-11-02"}}, uji=True)
        self.assertIn("Bulan 2026-10", pesan)
        self.assertIn("Bulan 2026-11", pesan)

    def test_transfer_tidak_memicu_koreksi(self):
        (self.d / "laporan-bulanan.json").write_text(json.dumps({"bulan": {"2026-10": {}}}), encoding="utf-8")
        kode, pesan = self.jalan("hapus", {"no_resi": "STRUK-T"}, uji=True)
        self.assertNotIn("Koreksi", pesan)

    def test_peringatan_tidak_mengubah_berkas_lain(self):
        kw = self.d / "kewajiban.json"
        kw.write_text(json.dumps({"kewajiban": [{"id": "K", "lunas_resi": "STRUK-A"}]}), encoding="utf-8")
        isi = kw.read_text()
        self.terapkan("hapus", {"no_resi": "STRUK-A"})
        self.assertEqual(kw.read_text(), isi)


class Skema(Dasar):
    """CSV lain cukup mendaftarkan Skema untuk mendapat cari, ubah, hapus."""

    def setUp(self):
        super().setUp()
        self.mainan = self.d / "mainan.csv"
        self.mainan.write_text("id,nama,warna\nA1,bola,merah\nA2,balon,biru\n", encoding="utf-8")

        def cek(b, awalan=""):
            if not str(b.get("nama") or "").strip():
                raise bk.Tolak(f"{awalan}nama kosong")
            return {"id": b["id"], "nama": str(b["nama"]).strip(), "warna": str(b.get("warna") or "")}

        self.sk = bk.Skema(
            nama="mainan", path=lambda: self.mainan, kolom=["id", "nama", "warna"], kunci="id",
            terkunci=frozenset({"id"}), tingkat_transaksi=frozenset({"warna"}), cek_baris=cek,
            cek_duplikat=lambda baru, lain: None, terlindung=lambda d: None,
            format_cari=bk._format_cari_umum, peringatan=lambda p, l, b: [], kolom_kata=("nama",))

    def jalan_sk(self, aksi, req, uji=False):
        return bk.jalankan(self.sk, aksi, {"oleh": "E", **req}, uji=uji, sekarang=SEKARANG)

    def test_cari_ubah_hapus_tanpa_kode_baru(self):
        self.assertIn("A2", bk.cari(self.sk, kata="balon")[1])
        req = {"id": "A1", "set": {"nama": "bola besar", "warna": "hijau"}}
        kode, pesan = self.jalan_sk("ubah", req, uji=True)
        self.assertEqual(kode, 0, pesan)
        sidik = re.search(r"sidik (\w+)", pesan).group(1)
        self.assertEqual(self.jalan_sk("ubah", {**req, "sidik": sidik})[0], 0)
        self.assertIn("A1,bola besar,hijau", self.mainan.read_text())
        self.assertEqual(self.jalan_sk("ubah", {"id": "A1", "set": {"id": "Z"}}, uji=True)[0], 2)  # terkunci
        kode, pesan = self.jalan_sk("hapus", {"id": "A2"}, uji=True)
        sidik = re.search(r"sidik (\w+)", pesan).group(1)
        self.assertEqual(self.jalan_sk("hapus", {"id": "A2", "sidik": sidik})[0], 0)
        self.assertEqual(self.mainan.read_text(), "id,nama,warna\nA1,bola besar,hijau\n")
        self.assertEqual(len(list((self.d / "backups").glob("mainan_sebelum-*"))), 2)

    def test_append_only_menolak_ubah_dan_hapus(self):
        jejak = bk.skema_jejak()
        (self.d / "riwayat-ubah.csv").write_text(",".join(bk.JEJAK_KOLOM) + "\nx,hapus,A,,E,[],[]\n",
                                                 encoding="utf-8")
        for aksi in ("ubah", "hapus"):
            kode, pesan = bk.jalankan(jejak, aksi, {"no_resi": "A", "oleh": "E", "set": {"aksi": "x"}}, uji=True)
            self.assertEqual(kode, 2)
            self.assertIn("append-only", pesan)
        self.assertEqual(bk.cari(jejak, kata="hapus")[0], 0)


if __name__ == "__main__":
    unittest.main()
