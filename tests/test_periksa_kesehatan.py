"""Tes sinyal Sheets dan Akun di scripts/periksa-kesehatan.py — dihitung dari berkas status, tanpa model (ADR-0011).

    python3 -m unittest tests/test_periksa_kesehatan.py
"""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

AKAR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("kesehatan", AKAR / "scripts" / "periksa-kesehatan.py")
pk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pk)

SEKARANG = datetime(2026, 11, 1, 18, 0, 0)


def iso(menit_lalu):
    return (SEKARANG - timedelta(minutes=menit_lalu)).isoformat(timespec="seconds")


class SinyalSheets(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = Path(self._tmp.name)
        self.config, self.status = d / "sheets.json", d / "sheets-status.json"
        for nama, nilai in (("CONFIG_SHEETS", self.config), ("STATUS_SHEETS", self.status)):
            p = mock.patch.object(pk, nama, nilai)
            p.start()
            self.addCleanup(p.stop)
        self.config.write_text("{}")

    def tulis_status(self, **isi):
        dasar = {"waktu": iso(5), "hasil": "sukses", "pesan": "", "waktu_sukses": iso(5)}
        self.status.write_text(json.dumps({**dasar, **isi}))

    def periksa(self):
        return pk.periksa_sheets(sekarang=SEKARANG)

    def test_sinkron_yang_belum_dikonfigurasi_bukan_masalah(self):
        self.config.unlink()

        self.assertEqual(self.periksa(), [])

    def test_sinkron_yang_baru_sukses_sehat(self):
        self.tulis_status()

        self.assertEqual(self.periksa(), [])

    def test_gagal_sesaat_sementara_sukses_terakhir_masih_baru_tidak_mengusik(self):
        self.tulis_status(hasil="gagal", pesan="ConnectionError: putus", waktu=iso(2), waktu_sukses=iso(17))

        self.assertEqual(self.periksa(), [])

    def test_sukses_terakhir_lewat_ambang_diperingatkan_dengan_sebab_percobaan_terakhir(self):
        self.tulis_status(hasil="gagal", pesan="HTTP 403: ditolak", waktu=iso(3),
                          waktu_sukses=iso(60 * pk.SHEETS_MANDEK_JAM + 30))

        (tingkat, judul, rinci), = self.periksa()

        self.assertEqual(tingkat, "PERINGATAN")
        self.assertIn("Sheets", judul)
        self.assertIn("HTTP 403", rinci)
        self.assertIn("gagal", rinci)

    def test_ditolak_yang_butuh_manusia_menyebut_pesannya(self):
        self.tulis_status(hasil="ditolak", pesan="Header worksheet 'Buku Kas' berubah",
                          waktu_sukses=iso(60 * pk.SHEETS_MANDEK_JAM + 1))

        (_, _, rinci), = self.periksa()

        self.assertIn("Header worksheet", rinci)

    def test_belum_pernah_sukses_sama_sekali_diperingatkan(self):
        self.tulis_status(hasil="gagal", pesan="google-auth belum terpasang", waktu_sukses=None)

        (_, _, rinci), = self.periksa()

        self.assertIn("google-auth", rinci)
        self.assertIn("belum pernah", rinci)

    def test_dikonfigurasi_tetapi_tidak_pernah_jalan_diperingatkan(self):
        (tingkat, judul, rinci), = self.periksa()

        self.assertEqual(tingkat, "PERINGATAN")
        self.assertIn("belum pernah", rinci)

    def test_berkas_status_rusak_diperingatkan_bukan_dianggap_sehat(self):
        self.status.write_text("{")

        (tingkat, _, rinci), = self.periksa()

        self.assertEqual(tingkat, "PERINGATAN")
        self.assertIn("tidak terbaca", rinci)

    def test_sinyal_tidak_memanggil_model_atau_proses_luar(self):
        self.tulis_status()
        with mock.patch.object(pk, "jalankan", side_effect=AssertionError("tidak boleh memanggil proses")):
            self.assertEqual(self.periksa(), [])

    def test_status_yang_bentuknya_salah_diperingatkan_bukan_menjatuhkan_penjaga(self):
        for isi in ("[]", "null", "123", '{"waktu_sukses": 123}', '{"waktu_sukses": ["x"]}',
                    '{"waktu_sukses": "2026-11-01T17:00:00+07:00"}', '{"waktu_sukses": "bukan tanggal"}'):
            with self.subTest(isi=isi):
                self.status.write_text(isi)

                hasil = self.periksa()  # tidak boleh melempar

                self.assertEqual(len(hasil), 1)
                self.assertEqual(hasil[0][0], "PERINGATAN")

    def test_waktu_sukses_di_masa_depan_diperingatkan_jam_sistem_dicurigai(self):
        self.tulis_status(waktu_sukses=iso(-120))

        (tingkat, _, rinci), = self.periksa()

        self.assertEqual(tingkat, "PERINGATAN")
        self.assertIn("masa depan", rinci)

    def test_sukses_basi_tanpa_percobaan_baru_menjelaskan_kemungkinan_sebabnya(self):
        self.tulis_status(hasil="sukses", waktu=iso(60 * 5), waktu_sukses=iso(60 * 5))

        (_, _, rinci), = self.periksa()

        self.assertNotIn("percobaan terakhir sukses", rinci)
        self.assertIn("tidak ada sinkron baru", rinci)
        self.assertIn("Mac", rinci)  # baru bangun dari tidur: sinkron menyusul


BILLS_HEADER = "tanggal,tipe,kategori,jumlah,akun\n"


class SinyalAkun(unittest.TestCase):
    """Konsistensi Akun (ADR-0028): Saldo Bersama sebelum cutover bisa bergeser diam-diam saat
    transaksi lama dihapus/diubah (10 Nov 2026). Penjaga memakai akun.periksa()."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = Path(self._tmp.name)
        self.bills, self.akun = d / "bills.csv", d / "akun.json"
        for nama, nilai in (("BILLS", self.bills), ("AKUN", self.akun)):
            p = mock.patch.object(pk, nama, nilai)
            p.start()
            self.addCleanup(p.stop)
        self.bills.write_text(
            BILLS_HEADER
            + "2026-10-01,pemasukan,opening_balance,1000000,\n"
            + "2026-10-20,pengeluaran,food,300000,\n"
            + "2026-11-09,pengeluaran,food,50000,Tunai Ayah\n",  # sesudah cutover: tak dihitung
            encoding="utf-8")

    def tulis_akun(self, global_=700000, awal=(400000, 300000)):
        self.akun.write_text(json.dumps({
            "cutover": "2026-11-09",
            "saldo_global_saat_cutover": global_,
            "akun": [{"id": f"a{i}", "nama": f"Akun {i}", "saldo_awal": s} for i, s in enumerate(awal)],
        }), encoding="utf-8")

    def test_konsisten_diam(self):
        self.tulis_akun()

        self.assertEqual(pk.periksa_akun(), [])

    def test_akun_json_tidak_ada_diam(self):
        self.assertEqual(pk.periksa_akun(), [])

    def test_fitur_akun_belum_aktif_diam(self):
        self.tulis_akun(awal=(400000, None))

        self.assertEqual(pk.periksa_akun(), [])

    def test_transaksi_lama_dihapus_diperingatkan_dengan_selisih_dan_perintah_cek(self):
        self.tulis_akun()
        self.bills.write_text(BILLS_HEADER + "2026-10-01,pemasukan,opening_balance,1000000,\n",
                              encoding="utf-8")  # pengeluaran 300.000 sebelum cutover hilang

        (tingkat, judul, rinci), = pk.periksa_akun()

        self.assertEqual(tingkat, "PERINGATAN")
        self.assertIn("Akun", judul)
        self.assertIn("300.000", rinci)
        self.assertIn("python3 scripts/akun.py --cek", rinci)

    def test_jumlah_saldo_awal_tidak_sama_diperingatkan(self):
        self.tulis_akun(awal=(400000, 250000))

        (tingkat, _, rinci), = pk.periksa_akun()

        self.assertEqual(tingkat, "PERINGATAN")
        self.assertIn("50.000", rinci)

    def test_data_rusak_diperingatkan_bukan_menjatuhkan_penjaga(self):
        kasus = {
            "akun.json bukan JSON": lambda: self.akun.write_text("{"),
            "akun.json bukan objek": lambda: self.akun.write_text("[]"),
            "akun tanpa daftar": lambda: self.akun.write_text('{"cutover": "2026-11-09"}'),
            "cutover bukan tanggal": lambda: self.akun.write_text(json.dumps(
                {"cutover": "kemarin", "saldo_global_saat_cutover": 1, "akun": [{"nama": "A", "saldo_awal": 1}]})),
            "bills.csv tanpa kolom wajib": lambda: (self.tulis_akun(), self.bills.write_text("x,y\n1,2\n")),
        }
        for nama, rusak in kasus.items():
            with self.subTest(nama):
                rusak()

                hasil = pk.periksa_akun()  # tidak boleh melempar

                self.assertEqual(len(hasil), 1)
                self.assertEqual(hasil[0][0], "PERINGATAN")
                self.assertIn("akun.py --cek", hasil[0][2])

    def test_akun_py_yang_gagal_diimpor_diperingatkan_bukan_menjatuhkan_penjaga(self):
        self.tulis_akun()
        with mock.patch.dict("sys.modules", {"akun": None}):  # import akun -> ImportError

            (tingkat, judul, _), = pk.periksa_akun()

        self.assertEqual(tingkat, "PERINGATAN")
        self.assertIn("tidak bisa jalan", judul)

    def test_sinyal_tidak_memanggil_model_atau_proses_luar(self):
        self.tulis_akun()
        with mock.patch.object(pk, "jalankan", side_effect=AssertionError("tidak boleh memanggil proses")):
            self.assertEqual(pk.periksa_akun(), [])


if __name__ == "__main__":
    unittest.main()
