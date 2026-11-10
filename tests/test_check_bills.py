"""Tes check-bills.py — status budget sesuai permintaan, dan cek budget yang tetap diam.

    python3 -m unittest tests/test_check_bills.py
"""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

AKAR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_bills", AKAR / "scripts" / "check-bills.py")
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

HARI = date(2026, 10, 31)


def b(tanggal, tipe, jumlah, kategori="food"):
    return {"tanggal": tanggal, "tipe": tipe, "kategori": kategori, "jumlah": str(jumlah)}


ROWS = [
    b("2026-10-05", "pengeluaran", 850_000),
    b("2026-10-20", "pengeluaran", 350_000),
    b("2026-10-21", "pemasukan", 9_000_000, "salary"),        # bukan pengeluaran
    b("2026-10-22", "transfer", 2_000_000, "transfer"),       # bukan pengeluaran
    b("2026-09-30", "pengeluaran", 999_999),                  # bulan lain
]


def jalankan(fungsi, budget, rows=ROWS):
    atur = {"budget_bulanan": budget, "alert_persen": 80, "pengeluaran_besar_mulai": 1_000_000}
    with mock.patch.object(cb.pengaturan, "muat", return_value=atur), \
            mock.patch.object(cb, "load_bills", return_value=rows):
        return fungsi(HARI)


class StatusBudget(unittest.TestCase):
    """check-bills hanya meneruskan ke budget.pesan; aturan hitung dan bunyinya diuji di test_budget.py."""

    def test_selalu_menjawab_walau_di_bawah_ambang_tapi_cek_malam_tetap_diam(self):
        teks = jalankan(cb.status_budget, 7_000_000)
        self.assertIn("💰 Status Budget — Oktober 2026", teks)
        self.assertIn("Rp 1.200.000 (17%)", teks)
        self.assertEqual(jalankan(cb.check_budget, 7_000_000), "")

    def test_budget_belum_diset(self):
        self.assertIn("Budget belum diset", jalankan(cb.status_budget, 0))


class CekBudget(unittest.TestCase):
    def test_peringatan_di_atas_ambang(self):
        teks = jalankan(cb.check_budget, 1_300_000)  # 1.200.000 = 92%
        self.assertIn("Mendekati batas Budget", teks)
        self.assertIn("92%", teks)

    def test_diam_bila_budget_belum_diset(self):
        self.assertEqual(jalankan(cb.check_budget, 0), "")

    def test_bulan_transaksi_diteruskan(self):
        atur = {"budget_bulanan": 1_000_000, "alert_persen": 80, "pengeluaran_besar_mulai": 1_000_000}
        rows = [b("2026-09-10", "pengeluaran", 900_000), b("2026-10-10", "pengeluaran", 100_000)]
        with mock.patch.object(cb.pengaturan, "muat", return_value=atur), \
                mock.patch.object(cb, "load_bills", return_value=rows):
            self.assertEqual(cb.check_budget(HARI, bulan="2026-10"), "")           # Oktober 10%: diam
            self.assertEqual(cb.check_budget(HARI), "")                           # bulan ini (Okt) sama
            self.assertEqual(cb.check_budget(date(2026, 10, 15), bulan="2026-09"), "")  # 90% tapi sudah tutup


class BatasKategoriSetelahMencatat(unittest.TestCase):
    """ADR-0029: bot meneruskan kategori Transaksi yang baru dicatat lewat --kategori."""

    ATUR = {"budget_bulanan": 8_000_000, "alert_persen": 80, "pengeluaran_besar_mulai": 1_000_000,
            "budget_kategori": {"food": 100_000}, "label_kategori": {"food": "Makan & Minum"}}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = mock.patch.object(cb, "INGATAN", Path(tmp.name) / "peringatan-budget.json")
        p.start()
        self.addCleanup(p.stop)

    def jalan(self, *argv):
        rows = [b("2026-10-10", "pengeluaran", 90_000)]  # kategori food: 90%
        keluar = io.StringIO()
        with mock.patch.object(cb.pengaturan, "muat", return_value=self.ATUR), \
                mock.patch.object(cb, "load_bills", return_value=rows), \
                mock.patch("sys.argv", ["check-bills.py", "--mode", "budget", "--tanggal", "2026-10-31", *argv]), \
                contextlib.redirect_stdout(keluar):
            kode = cb.main()
        return kode, keluar.getvalue()

    def test_kategori_transaksi_yang_sampai_ambang_disebut(self):
        kode, teks = self.jalan("--bulan", "2026-10", "--kategori", "food")
        self.assertEqual(kode, 0)
        self.assertIn("⚠️ Makan & Minum", teks)

    def test_kategori_lain_diam(self):
        kode, teks = self.jalan("--bulan", "2026-10", "--kategori", "groceries")
        self.assertEqual(teks.strip(), "✅ Semua lancar!")

    def test_sekali_saja_lalu_diam_sampai_ambang_berikutnya(self):
        # ADR-0031
        self.assertIn("⚠️ Makan & Minum", self.jalan("--bulan", "2026-10", "--kategori", "food")[1])
        self.assertEqual(self.jalan("--bulan", "2026-10", "--kategori", "food")[1].strip(), "✅ Semua lancar!")
        self.assertEqual(json.loads(cb.INGATAN.read_text())["2026-10"], {"food": 80})

    def test_kategori_hanya_untuk_mode_budget(self):
        with mock.patch("sys.argv", ["check-bills.py", "--mode", "all", "--kategori", "food"]), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cb.main()


class CekMalamSekaliSaja(unittest.TestCase):
    """ADR-0031: cron mencatat 'sudah diperingatkan' hanya bila pesannya terkirim."""

    ATUR = {"budget_bulanan": 1_000_000, "alert_persen": 80, "pengeluaran_besar_mulai": 1_000_000}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ingatan = Path(tmp.name) / "peringatan-budget.json"
        for obj, nama, nilai in [(cb, "INGATAN", self.ingatan),
                                 (cb.pengaturan, "muat", lambda *a: self.ATUR),
                                 (cb, "load_bills", lambda: [b("2026-10-10", "pengeluaran", 900_000)]),
                                 (cb, "check_kewajiban", lambda today=None: ""),
                                 (cb, "check_perkiraan", lambda today=None: "")]:
            p = mock.patch.object(obj, nama, nilai)
            p.start()
            self.addCleanup(p.stop)

    def malam(self, berhasil):
        terkirim = []
        with mock.patch.object(cb, "kirim_kalau_ada", lambda isi: terkirim.append(isi) or (0 if berhasil else 1)), \
                mock.patch("sys.argv", ["check-bills.py", "--mode", "all", "--kirim", "--tanggal", "2026-10-20"]), \
                contextlib.redirect_stdout(io.StringIO()):
            kode = cb.main()
        return kode, terkirim

    def test_gagal_kirim_tidak_dicatat_jadi_diulang_malam_berikutnya(self):
        self.assertEqual(self.malam(False)[0], 1)
        self.assertFalse(self.ingatan.exists())
        kode, terkirim = self.malam(True)
        self.assertIn("Mendekati batas Budget", terkirim[0])
        self.assertEqual(json.loads(self.ingatan.read_text())["2026-10"], {"total": 80})
        self.assertEqual(self.malam(True)[1], [""])  # sudah diperingatkan: tidak ada yang dikirim


class KirimKalauAda(unittest.TestCase):
    def test_tanpa_isi_tidak_mengirim_ke_tujuan_mana_pun(self):
        with mock.patch("subprocess.run", side_effect=AssertionError("tidak boleh mengirim")):
            self.assertEqual(cb.kirim_kalau_ada(""), 0)

    @staticmethod
    def pengirim(tujuan, hasil_ok):
        """Pengirim palsu: hasil_ok = {kanal: bool}; mencatat siapa saja yang dikirimi."""
        dikirimi = []

        def kirim_ke_semua(pesan, daftar):
            dikirimi.extend(k for k, _ in daftar)
            return [(k, ke, hasil_ok[k], "") for k, ke in daftar]

        return SimpleNamespace(tujuan_baku=lambda: tujuan, kirim_ke_semua=kirim_ke_semua), dikirimi

    def test_semua_tujuan_menerima_keluar_0(self):
        p, dikirimi = self.pengirim([("whatsapp", "A"), ("telegram", "B")], {"whatsapp": True, "telegram": True})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cb.kirim_kalau_ada("Budget 92%", p), 0)
        self.assertEqual(dikirimi, ["whatsapp", "telegram"])

    def test_satu_tujuan_gagal_keluar_1_dan_yang_lain_tetap_dikirimi(self):
        p, dikirimi = self.pengirim([("whatsapp", "A"), ("telegram", "B"), ("discord", "C")],
                                    {"whatsapp": False, "telegram": True, "discord": True})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cb.kirim_kalau_ada("Budget 92%", p), 1)
        self.assertEqual(dikirimi, ["whatsapp", "telegram", "discord"])

    def test_tanpa_tujuan_keluar_1(self):
        p, dikirimi = self.pengirim([], {})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cb.kirim_kalau_ada("Budget 92%", p), 1)
        self.assertEqual(dikirimi, [])


if __name__ == "__main__":
    unittest.main()
