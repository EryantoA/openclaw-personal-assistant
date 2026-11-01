"""Tes sinyal Sheets di scripts/periksa-kesehatan.py — dihitung dari berkas status, tanpa model (ADR-0011).

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


if __name__ == "__main__":
    unittest.main()
