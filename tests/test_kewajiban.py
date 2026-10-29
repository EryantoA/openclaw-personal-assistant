"""Tes scripts/kewajiban.py — Kewajiban lunas lewat tautan ke fakta (ADR-0006).

    python3 -m unittest tests/test_kewajiban.py
"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import kewajiban  # noqa: E402

ROWS = [{"no_resi": "STRUK-1"}, {"no_resi": "STRUK-1"}, {"no_resi": ""}, {"no_resi": " TRX-2 "}]
LUNAS = {"id": "K1", "nama": "PLN", "nominal": 300_000, "jatuh_tempo": "2026-10-20", "lunas_resi": "STRUK-1"}
HILANG = {"id": "K2", "nama": "WiFi", "nominal": 350_000, "jatuh_tempo": "2026-10-30",
          "lunas_resi": "STRUK-tidak-ada"}
BELUM = {"id": "K3", "nama": "Air", "nominal": 90_000, "jatuh_tempo": "2026-11-02", "lunas_resi": None}
DAFTAR = [LUNAS, HILANG, BELUM]


class BelumLunas(unittest.TestCase):
    def test_lunas_hanya_bila_barisnya_ada(self):
        hasil = kewajiban.belum_lunas(DAFTAR, ROWS)
        self.assertEqual([(e["id"], tautan) for e, tautan in hasil], [("K2", "STRUK-tidak-ada"), ("K3", None)])

    def test_no_resi_dibandingkan_tanpa_spasi_tepi(self):
        self.assertEqual(kewajiban.belum_lunas([dict(BELUM, lunas_resi="TRX-2")], ROWS), [])

    def test_tanpa_daftar_kosong(self):
        self.assertEqual(kewajiban.belum_lunas([], ROWS), [])


class Diingatkan(unittest.TestCase):
    ATUR = {"kewajiban_ingat_h_minus": 2}

    def test_hanya_h_minus_dan_hari_h(self):
        def pada(hari):
            return [(e["id"], sisa) for e, sisa, _ in kewajiban.diingatkan(DAFTAR, ROWS, hari, self.ATUR)]
        self.assertEqual(pada(date(2026, 10, 28)), [("K2", 2)])
        self.assertEqual(pada(date(2026, 10, 30)), [("K2", 0)])
        self.assertEqual(pada(date(2026, 10, 31)), [("K3", 2)])
        self.assertEqual(pada(date(2026, 10, 29)), [])
        self.assertEqual(pada(date(2026, 10, 20)), [])  # K1 hari H, tapi sudah lunas

    def test_tautan_hilang_ikut_disebut(self):
        self.assertEqual(kewajiban.diingatkan(DAFTAR, ROWS, date(2026, 10, 28), self.ATUR)[0][2],
                         "STRUK-tidak-ada")

    def test_h_minus_bawaan_2(self):
        self.assertEqual(len(kewajiban.diingatkan(DAFTAR, ROWS, date(2026, 10, 28), {})), 1)

    def test_tanpa_jatuh_tempo_tidak_diingatkan(self):
        tanpa = dict(BELUM, jatuh_tempo="")
        self.assertEqual(kewajiban.diingatkan([tanpa], ROWS, date(2026, 10, 31), self.ATUR), [])


class Nilai(unittest.TestCase):
    def test_jatuh_tempo(self):
        self.assertEqual(kewajiban.jatuh_tempo(BELUM), date(2026, 11, 2))
        self.assertIsNone(kewajiban.jatuh_tempo({"jatuh_tempo": "2-11-2026"}))
        self.assertIsNone(kewajiban.jatuh_tempo({}))

    def test_nominal(self):
        self.assertEqual(kewajiban.nominal(BELUM), 90_000)
        self.assertEqual(kewajiban.nominal({}), 0)
        self.assertIsNone(kewajiban.nominal({"nominal": "abc"}))

    def test_nama(self):
        self.assertEqual(kewajiban.nama(BELUM), "Air")
        self.assertEqual(kewajiban.nama({"id": "K9", "nama": ""}), "K9")
        self.assertEqual(kewajiban.nama({}), "(tanpa nama)")


class Tertaut(unittest.TestCase):
    def test_kewajiban_yang_menunjuk_transaksi(self):
        self.assertEqual([e["id"] for e in kewajiban.tertaut(DAFTAR, "STRUK-1")], ["K1"])
        self.assertEqual(kewajiban.tertaut(DAFTAR, "STRUK-9"), [])
        self.assertEqual(kewajiban.tertaut([dict(BELUM, lunas_resi="")], ""), [])


class Muat(unittest.TestCase):
    def test_tidak_ada_atau_rusak_kosong(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "kewajiban.json"
            self.assertEqual(kewajiban.muat(p), [])
            p.write_text("{rusak", encoding="utf-8")
            self.assertEqual(kewajiban.muat(p), [])
            p.write_text(json.dumps({"kewajiban": {"bukan": "daftar"}}), encoding="utf-8")
            self.assertEqual(kewajiban.muat(p), [])
            p.write_text(json.dumps({"kewajiban": DAFTAR}), encoding="utf-8")
            self.assertEqual(len(kewajiban.muat(p)), 3)


if __name__ == "__main__":
    unittest.main()
