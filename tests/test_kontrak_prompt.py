"""Tes kontrak prompt: AGENTS.md selalu masuk prompt bot, jadi aturannya harus ada di sana.

    python3 -m unittest tests/test_kontrak_prompt.py

Hanya membuktikan teks kontrak ada dan tidak bertentangan, bukan bahwa model patuh (ADR-0014).
"""
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
AGENTS = (AKAR / "AGENTS.md").read_text(encoding="utf-8")
SKILL = (AKAR / "skills" / "bill-tracker" / "SKILL.md").read_text(encoding="utf-8")

KERANGKA_AKHIR = "✅ Sudah dicatat!"
KERANGKA_PRATINJAU = "🧾 Akan disimpan (belum dicatat)"
KERANGKA_CARI = "🔍 Hasil pencarian"


class KontrakPratinjau(unittest.TestCase):
    def test_pratinjau_didefinisikan_sekali_di_agents_dan_tidak_di_skill(self):
        self.assertEqual(AGENTS.count(KERANGKA_PRATINJAU), 1)
        self.assertNotIn(KERANGKA_PRATINJAU, SKILL)
        self.assertIn("hanya di `AGENTS.md`", SKILL)

    def test_semua_pencatatan_lewat_uji_lalu_pratinjau(self):
        self.assertIn("catat.py --uji", AGENTS)
        self.assertIn("*ya*", AGENTS)
        self.assertIn("*batal*", AGENTS)
        self.assertIn("buang draf lama", AGENTS)  # draf lama dibuang bila ada transaksi baru
        self.assertIn("scripts/resi.py --fingerprint", AGENTS)  # struk tanpa nomor tetap terdeteksi dobel

    def test_tidak_ada_lagi_aturan_langsung_catat(self):
        self.assertNotIn("jangan tanya konfirmasi dulu", AGENTS)
        self.assertNotIn("kecuali Bukti Transfer", AGENTS)
        self.assertNotIn("PENGECUALIAN", AGENTS)

    def test_kerangka_akhir_sama_di_skill_dan_agents(self):
        for teks in (AGENTS, SKILL):
            self.assertIn(KERANGKA_AKHIR + "\n\nStruk: ", teks)

    def test_pratinjau_dan_akhir_memuat_lima_hal_struk(self):
        for teks in (AGENTS, SKILL):
            self.assertIn("| Tanggal: ", teks)
            self.assertIn("| Jam: ", teks)
            self.assertIn("Pembeli: ", teks)
            self.assertIn("ADR-0015", teks)
        self.assertEqual(AGENTS.count("Pembeli: <pencatat dari keluaran>"), 2)  # pratinjau + balasan akhir


class KontrakBacaStruk(unittest.TestCase):
    def test_selisih_total_dan_biaya_tambahan(self):
        for kata in ("Selisih", "Diskon", "PPN", "Layanan", "total tercetak"):
            self.assertIn(kata, AGENTS)

    def test_qty_harga_satuan_dan_cara_bayar(self):
        self.assertIn("harga satuan", AGENTS)
        self.assertIn("cara bayar", AGENTS)


class KontrakBuktiTransfer(unittest.TestCase):
    def test_bukti_transfer_adalah_varian_pratinjau(self):
        self.assertIn("Varian Bukti Transfer", AGENTS)
        self.assertNotIn("🧾 Bukti transfer terbaca", AGENTS)
        self.assertIn("Referensi: ", AGENTS)
        self.assertIn("Arah: ", AGENTS)

    def test_larangan_tertulis(self):
        self.assertIn("nama orang bukan akun", AGENTS)
        self.assertIn("MENANG-", AGENTS)  # contoh awalan karangan yang dilarang
        self.assertIn("N entri tercatat", AGENTS)
        self.assertIn("STRUK-<nomor referensi>", AGENTS)


class KontrakBacaData(unittest.TestCase):
    def test_laporan_per_pembeli_terdaftar(self):
        for teks in (AGENTS, SKILL):
            self.assertIn("laporan-pembeli.py", teks)

    def test_kerangka_cari_didefinisikan_sekali_dan_sama_di_skill(self):
        self.assertEqual(AGENTS.count(KERANGKA_CARI), 1)
        self.assertNotIn(KERANGKA_CARI, SKILL)
        self.assertIn("hanya di `AGENTS.md`", SKILL)
        self.assertIn("Pembeli: <pencatat>", AGENTS)


class Dokumen(unittest.TestCase):
    def test_adr_dan_glosarium(self):
        self.assertTrue(list((AKAR / "docs" / "adr").glob("0016-*.md")))
        self.assertIn("**Pratinjau**", (AKAR / "CONTEXT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
