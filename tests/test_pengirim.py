"""Tes scripts/pengirim.py — kirim ke semua tujuan (dipakai tiga pesan otomatis).

    python3 -m unittest tests/test_pengirim.py
"""
import contextlib
import io
import sys
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


if __name__ == "__main__":
    unittest.main()
