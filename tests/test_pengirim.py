"""Tes scripts/pengirim.py — kirim ke semua tujuan (dipakai tiga pesan otomatis).

    python3 -m unittest tests/test_pengirim.py
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "scripts"))
import pengirim  # noqa: E402


def senyap(fungsi, *a, **kw):
    """Jalankan fungsi dan buang keluaran cetaknya; kembalikan (hasil, teks cetak)."""
    keluaran = io.StringIO()
    with contextlib.redirect_stdout(keluaran):
        hasil = fungsi(*a, **kw)
    return hasil, keluaran.getvalue()


class KirimKeSemua(unittest.TestCase):
    def test_semua_berhasil_mengembalikan_hasil_per_tujuan(self):
        hasil, _ = senyap(pengirim.kirim_ke_semua, "halo",
                          [("whatsapp", "A"), ("telegram", "B")],
                          pakai=lambda pesan, kanal, ke: (True, ""))
        self.assertEqual(hasil, [("whatsapp", "A", True, ""), ("telegram", "B", True, "")])

    def test_mencetak_satu_baris_per_tujuan_seperti_sebelum_dipusatkan(self):
        # Format ini dulu dicetak sendiri oleh tiga skrip; cron membaca log-nya.
        sebagian = lambda pesan, kanal, ke: (kanal == "whatsapp", "" if kanal == "whatsapp" else "ditolak")
        _, teks = senyap(pengirim.kirim_ke_semua, "halo",
                         [("whatsapp", "A"), ("telegram", "B")], pakai=sebagian)
        self.assertEqual(teks, "\n✅ terkirim whatsapp -> A\n\n❌ GAGAL telegram -> B: ditolak\n")

    def test_tujuan_pertama_gagal_tidak_menghentikan_yang_kedua(self):
        dicoba = []

        def kirim(pesan, kanal, ke):
            dicoba.append(kanal)
            return kanal != "whatsapp", "logout"

        hasil, _ = senyap(pengirim.kirim_ke_semua, "halo",
                          [("whatsapp", "A"), ("telegram", "B")], pakai=kirim)
        self.assertEqual(dicoba, ["whatsapp", "telegram"])
        self.assertEqual([ok for _, _, ok, _ in hasil], [False, True])

    def test_tanpa_pengganti_memakai_kirim_modul_yang_dicari_saat_dipanggil(self):
        # Mingguan dan cek budget tidak mengoper pengirim; tes yang menimpa pengirim.kirim
        # (tiket laporan banyak tujuan) harus tetap berlaku.
        asli = pengirim.kirim
        pengirim.kirim = lambda pesan, kanal, ke: (True, "dari-kirim-modul")
        try:
            hasil, _ = senyap(pengirim.kirim_ke_semua, "halo", [("whatsapp", "A")])
        finally:
            pengirim.kirim = asli
        self.assertEqual(hasil, [("whatsapp", "A", True, "dari-kirim-modul")])

    def test_semua_gagal_dan_tanpa_tujuan(self):
        gagal = lambda pesan, kanal, ke: (False, "putus")
        hasil, _ = senyap(pengirim.kirim_ke_semua, "halo", [("whatsapp", "A")], pakai=gagal)
        self.assertEqual(hasil, [("whatsapp", "A", False, "putus")])
        kosong, teks = senyap(pengirim.kirim_ke_semua, "halo", [], pakai=gagal)
        self.assertEqual((kosong, teks), ([], ""))


class PercobaanUlang(unittest.TestCase):
    """WhatsApp gagal acak dan layak diulang; Telegram/Discord sekali coba (batas waktu cron)."""

    def setUp(self):
        self.asli = (pengirim.kirim_sekali, pengirim.time.sleep)
        self.dicoba, self.jeda = [], []
        pengirim.kirim_sekali = lambda pesan, kanal, ke: self.dicoba.append(kanal) or (False, "putus")
        pengirim.time.sleep = self.jeda.append

    def tearDown(self):
        pengirim.kirim_sekali, pengirim.time.sleep = self.asli

    def kirim(self, kanal):
        with contextlib.redirect_stderr(io.StringIO()):
            return pengirim.kirim("halo", kanal, "x")

    def test_whatsapp_dicoba_tiga_kali_dengan_jeda(self):
        self.assertEqual(self.kirim("whatsapp"), (False, "putus"))
        self.assertEqual(self.dicoba, ["whatsapp"] * 3)
        self.assertEqual(self.jeda, [60, 60])

    def test_telegram_dan_discord_sekali_coba_tanpa_jeda(self):
        for kanal in ("telegram", "discord"):
            self.dicoba.clear()
            self.assertEqual(self.kirim(kanal), (False, "putus"))
            self.assertEqual(self.dicoba, [kanal])
        self.assertEqual(self.jeda, [])


class TujuanBaku(unittest.TestCase):
    """Nomor WhatsApp dari config OpenClaw; Kanal lain dari data/tujuan.json (di luar git)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.asli = (pengirim.OPENCLAW_JSON, getattr(pengirim, "TUJUAN_JSON", None))
        pengirim.OPENCLAW_JSON = self.tmp / "openclaw.json"
        pengirim.TUJUAN_JSON = self.tmp / "tujuan.json"
        self.tulis_wa("+62000")

    def tearDown(self):
        pengirim.OPENCLAW_JSON, pengirim.TUJUAN_JSON = self.asli

    def tulis_wa(self, nomor):
        pengirim.OPENCLAW_JSON.write_text(
            json.dumps({"channels": {"whatsapp": {"allowFrom": [nomor, "+62999"]}}}), encoding="utf-8")

    def tulis_tujuan(self, isi):
        pengirim.TUJUAN_JSON.write_text(isi if isinstance(isi, str) else json.dumps(isi), encoding="utf-8")

    def ambil(self):
        galat = io.StringIO()
        with contextlib.redirect_stderr(galat):
            return pengirim.tujuan_baku(), galat.getvalue()

    def test_tanpa_berkas_tujuan_hanya_whatsapp_dan_kanal_kosong_disebut_dilewati(self):
        tujuan, galat = self.ambil()
        self.assertEqual(tujuan, [("whatsapp", "+62000")])
        self.assertIn("telegram belum dikonfigurasi", galat)
        self.assertIn("discord belum dikonfigurasi", galat)

    def test_kanal_lain_ditambahkan_berurutan_setelah_whatsapp_tanpa_peringatan(self):
        self.tulis_tujuan({"discord": "channel:3", "telegram": "2"})
        tujuan, galat = self.ambil()
        self.assertEqual(tujuan, [("whatsapp", "+62000"), ("telegram", "2"), ("discord", "channel:3")])
        self.assertEqual(galat, "")

    def test_whatsapp_tak_terbaca_tidak_menghilangkan_kanal_lain_tapi_diperingatkan(self):
        # Tanpa peringatan, Telegram yang sukses menutupi hilangnya WhatsApp.
        pengirim.OPENCLAW_JSON.write_text("bukan json", encoding="utf-8")
        self.tulis_tujuan({"telegram": "2"})
        tujuan, galat = self.ambil()
        self.assertEqual(tujuan, [("telegram", "2")])
        self.assertIn("whatsapp tidak terbaca", galat)

    def test_berkas_rusak_dilewati_dengan_peringatan_dan_whatsapp_tetap(self):
        self.tulis_tujuan("{ rusak")
        tujuan, galat = self.ambil()
        self.assertEqual(tujuan, [("whatsapp", "+62000")])
        self.assertIn("tujuan.json", galat)

    def test_isian_kosong_atau_bukan_teks_dilewati(self):
        self.tulis_tujuan({"telegram": "", "discord": 123})
        tujuan, galat = self.ambil()
        self.assertEqual(tujuan, [("whatsapp", "+62000")])
        self.assertIn("telegram", galat)
        self.assertIn("discord", galat)

    def test_kanal_tak_dikenal_diabaikan(self):
        self.tulis_tujuan({"signal": "x"})
        self.assertEqual(self.ambil()[0], [("whatsapp", "+62000")])


if __name__ == "__main__":
    unittest.main()
