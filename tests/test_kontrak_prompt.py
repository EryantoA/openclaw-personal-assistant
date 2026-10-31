"""Tes kontrak prompt: AGENTS.md selalu masuk prompt bot, jadi aturannya harus ada di sana.

    python3 -m unittest tests/test_kontrak_prompt.py

Hanya membuktikan teks kontrak ada dan tidak bertentangan, bukan bahwa model patuh (ADR-0014).
"""
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
AGENTS = (AKAR / "AGENTS.md").read_text(encoding="utf-8")
SKILL = (AKAR / "skills" / "bill-tracker" / "SKILL.md").read_text(encoding="utf-8")
REFERENSI = {p.name: p.read_text(encoding="utf-8")
             for p in sorted((AKAR / "skills" / "bill-tracker" / "references").glob("*.md"))}
SKILL_DAN_REFERENSI = SKILL + "\n".join(REFERENSI.values())

KERANGKA_AKHIR = "✅ Sudah dicatat!"
KERANGKA_PRATINJAU = "🧾 Akan disimpan (belum dicatat)"
KERANGKA_CARI = "🔍 Hasil pencarian"
KALIMAT_DRAF_DIBUANG = "⚠️ Yang tadi tidak tersimpan."
KERANGKA_UBAH = "✏️ Akan diubah (belum berubah)"
KERANGKA_HAPUS = "🗑️ Akan dihapus (belum berubah)"


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
        self.assertIn(KALIMAT_DRAF_DIBUANG, AGENTS)  # kalimat pembuka baku, bukan parafrase
        self.assertIn("baris PERTAMA balasan", AGENTS)
        self.assertIn("scripts/resi.py --fingerprint", AGENTS)  # struk tanpa nomor tetap terdeteksi dobel

    def test_tidak_ada_lagi_aturan_langsung_catat(self):
        self.assertNotIn("jangan tanya konfirmasi dulu", AGENTS)
        self.assertNotIn("kecuali Bukti Transfer", AGENTS)
        self.assertNotIn("PENGECUALIAN", AGENTS)

    def test_kerangka_akhir_sama_di_skill_dan_agents(self):
        # AGENTS.md memakai placeholder label (Struk/No Resi dihitung skrip, lihat ADR-0015);
        # SKILL.md menunjukkan kedua label lewat dua contoh konkret berdampingan.
        self.assertIn(KERANGKA_AKHIR + "\n\n<label dari keluaran>: ", AGENTS)
        self.assertIn(KERANGKA_AKHIR + "\n\nStruk: ", SKILL)
        self.assertIn(KERANGKA_AKHIR + "\n\nNo Resi: ", SKILL)

    def test_label_struk_hanya_untuk_struk_dijelaskan(self):
        for teks in (AGENTS, SKILL):
            self.assertIn("No Resi", teks)
            self.assertIn("STRUK-", teks)
        self.assertIn("jangan dikarang", AGENTS)
        self.assertIn("jangan dikarang", SKILL)

    def test_pratinjau_dan_akhir_memuat_lima_hal_struk(self):
        for teks in (AGENTS, SKILL):
            self.assertIn("| Tanggal: ", teks)
            self.assertIn("| Jam: ", teks)
            self.assertIn("Pembeli: ", teks)
            self.assertIn("ADR-0015", teks)
        self.assertEqual(AGENTS.count("<nama_label dari keluaran>: <pencatat dari keluaran>"), 2)  # pratinjau + balasan akhir

    def test_arah_di_pratinjau_dan_akhir(self):
        # ADR-0019: arah uang selalu tampil, dihitung skrip
        baris = "| Jam: <waktu dari keluaran>\nArah: <arah dari keluaran>\n<nama_label dari keluaran>: "
        self.assertEqual(AGENTS.count(baris), 2)
        for teks in (AGENTS, SKILL):
            self.assertIn("ADR-0019", teks)
            for arah in ("📥 Pemasukan", "📤 Pengeluaran", "🔁 Transfer"):
                self.assertIn(arah, teks)
        self.assertIn("Arah: 📥 Pemasukan\nPencatat: ", SKILL)
        self.assertNotIn("Pemasukan dicatat!", SKILL)  # template lama yang bertentangan
        self.assertNotIn("memakai kerangka yang sama", AGENTS)


class KontrakPembeli(unittest.TestCase):
    def test_alias_dibakukan_skrip_bukan_model(self):
        self.assertIn("data/pembeli.json", AGENTS)
        self.assertTrue((AKAR / "data" / "pembeli.json.example").exists())


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
        self.assertNotIn("Arah: pemasukan | pengeluaran", AGENTS)  # dilebur ke baris Arah umum

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


class KontrakUbahHapus(unittest.TestCase):
    """Ubah/hapus transaksi yang sudah tercatat (ADR-0018): kontrak hanya di AGENTS.md."""

    def test_kerangka_pratinjau_didefinisikan_sekali_di_agents(self):
        for kerangka in (KERANGKA_UBAH, KERANGKA_HAPUS):
            self.assertEqual(AGENTS.count(kerangka), 1)
            self.assertNotIn(kerangka, SKILL)

    def test_dua_langkah_dengan_uji_dan_sidik(self):
        for teks in ("buku.py ubah --uji", "buku.py hapus --uji", "\"sidik\"", "*ya*", "*batal*"):
            self.assertIn(teks, AGENTS)
        self.assertIn("tanya yang mana", AGENTS)  # penunjuk ambigu tidak ditebak

    def test_klaim_hanya_setelah_keluaran_ok(self):
        self.assertIn("OK terubah", AGENTS)
        self.assertIn("OK terhapus", AGENTS)
        self.assertIn("tidak ada yang berubah", AGENTS)

    def test_tulis_langsung_ke_csv_dilarang(self):
        self.assertIn("Jangan pernah mengedit `data/bills.csv`", AGENTS)
        self.assertNotIn("tetap dikerjakan dengan membaca lalu menulis ulang file", SKILL)
        self.assertNotIn("Hapus baris terakhir di CSV", SKILL)
        self.assertIn("hanya di `AGENTS.md`", SKILL)

    def test_dokumen_dan_ignore(self):
        self.assertTrue(list((AKAR / "docs" / "adr").glob("0018-*.md")))
        self.assertIn("**Jejak Perubahan**", (AKAR / "CONTEXT.md").read_text(encoding="utf-8"))
        ignore = (AKAR / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("data/riwayat-ubah.csv", ignore)
        self.assertIn("data/*.lock", ignore)


class SkillTidakBertentangan(unittest.TestCase):
    """SKILL.md tidak boleh memuat aturan yang berlawanan dengan AGENTS.md / ADR."""

    def test_contoh_kategori_selalu_slug_sah(self):
        # ADR-0002: kategori slug Inggris huruf kecil. Contoh berkapital/Indonesia hanya
        # boleh muncul sebagai larangan ("Jangan pernah menulis kategori ... seperti").
        for salah in ("`Gaji`", "`Penjualan`", "`Lainnya`", "kategori Investasi", "`Donasi`"):
            self.assertNotIn(salah, SKILL_DAN_REFERENSI)

    def test_daftar_kategori_tidak_dicetak_ulang(self):
        # kategori_custom di budget.json satu-satunya acuan; daftar keras basi sendiri.
        self.assertNotIn("Daftar Kategori (23)", SKILL_DAN_REFERENSI)
        self.assertIn("<semua slug dari kategori_custom", REFERENSI["kategori-custom.md"])

    def test_pratinjau_tanpa_syarat_keraguan(self):
        # ADR-0016: semua pencatatan lewat Pratinjau, bukan hanya saat ragu.
        self.assertNotIn("jika ada keraguan", SKILL)
        self.assertIn("**Selalu Pratinjau** setiap pencatatan, tanpa kecuali", SKILL)


class SkillTidakMenyalinAgents(unittest.TestCase):
    """Bagian SKILL.md yang dipangkas karena menyalin AGENTS.md atau memancing angka karangan."""

    def test_contoh_balasan_berangka_tetap_tidak_ada(self):
        self.assertNotIn("7 CSV + 7 Excel", SKILL_DAN_REFERENSI)    # status backup dari isi folder
        self.assertNotIn("Laporan Mingguan Otomatis", SKILL_DAN_REFERENSI)  # skrip cron, bukan bot
        self.assertNotIn("PENGELUARAN PER KATEGORI", SKILL_DAN_REFERENSI)   # salinan keluaran skrip

    def test_pencatat_adalah_nama_pengirim(self):
        self.assertNotIn("nomor HP atau username", SKILL)
        self.assertIn("**Pencatat** = nama pengirim pesan", SKILL)

    def test_laporan_satu_blok_menunjuk_agents(self):
        self.assertEqual(SKILL.count("### 📊 Laporan"), 1)  # tidak lagi satu blok per jenis laporan
        self.assertIn("*Peta pesan* di `AGENTS.md`", SKILL)


class SkillInti(unittest.TestCase):
    """SKILL.md hanya memuat yang dipakai tiap pencatatan; fitur jarang ada di references/ (ADR-0021)."""

    def test_setiap_referensi_ditunjuk_tabel_dan_ada(self):
        self.assertTrue(REFERENSI, "folder references/ kosong")
        for nama in REFERENSI:
            self.assertIn("{baseDir}/references/" + nama, SKILL, f"{nama} tidak ditunjuk SKILL.md")
        for nama in __import__("re").findall(r"\{baseDir\}/references/([\w.-]+\.md)", SKILL):
            self.assertIn(nama, REFERENSI, f"SKILL.md menunjuk {nama} yang tidak ada")

    def test_aturan_yang_berlaku_tiap_pencatatan_tetap_di_inti(self):
        # Menautkan pembayaran tagihan terjadi di tengah pencatatan biasa; kalau hanya ada di
        # referensi, bot tak punya alasan membukanya.
        self.assertIn("Pembayaran tagihan ditautkan", SKILL)
        self.assertIn("lunas_resi", SKILL)
        self.assertIn("Transfer bukan belanja", SKILL)
        self.assertIn("Jangan tebak akun", SKILL)
        self.assertIn("kategori `transfer`", SKILL)

    def test_inti_tidak_menggembung_lagi(self):
        # Batas kasar, bukan target: melewatinya berarti ada fitur jarang yang masuk ke inti lagi.
        self.assertLess(len(SKILL.splitlines()), 420)

    def test_referensi_tidak_menyalin_alur_agents(self):
        for nama, teks in REFERENSI.items():
            self.assertNotIn(KERANGKA_PRATINJAU, teks, nama)
            self.assertNotIn(KERANGKA_AKHIR, teks, nama)


class PetaPesan(unittest.TestCase):
    """Satu pintu masuk: tiap jenis pesan punya tepat satu baris jawaban di AGENTS.md (ADR-0022)."""

    PETA = AGENTS[AGENTS.index("## Peta pesan"):AGENTS.index("## Data & Script")] \
        if "## Peta pesan" in AGENTS else ""

    def test_peta_ada_sebelum_data_dan_alur(self):
        self.assertIn("## Peta pesan", AGENTS)
        self.assertLess(AGENTS.index("## Peta pesan"), AGENTS.index("## Data & Script"))
        self.assertLess(AGENTS.index("## Peta pesan"), AGENTS.index("## Mencatat transaksi"))

    def test_setiap_jawaban_skrip_ada_di_peta_tepat_sekali(self):
        for perintah in ("scripts/laporan-mingguan.py --berjalan", "scripts/laporan-mingguan.py`",
                         "scripts/laporan-bulanan.py --bulan YYYY-MM", "scripts/laporan-pembeli.py",
                         "scripts/laporan-harian.py`", "scripts/check-bills.py --mode status",
                         "scripts/akun.py`", "scripts/rekap-bulanan.py`", "scripts/resi.py --check", "scripts/resi.py --find-dup",
                         "scripts/check-bills.py --mode all", "scripts/buku.py cari"):
            self.assertIn(perintah, self.PETA)
        # tabel laporan lama tidak boleh hidup berdampingan dengan peta (dua sumber, dua kebenaran)
        self.assertNotIn("| Permintaan | Jalankan |", AGENTS)
        self.assertEqual(AGENTS.count("python3 scripts/laporan-mingguan.py --berjalan"), 1)

    def test_alur_dan_fitur_jarang_ditunjuk_peta(self):
        for rujukan in ("Mencatat transaksi", "Mencari transaksi", "Mengubah dan menghapus",
                        "Fitur lain", "`ya`"):
            self.assertIn(rujukan, self.PETA)

    def test_salinan_tanpa_format_tambahan(self):
        # Pernah terjadi (31 Okt 2026): bot membungkus judul dengan **…**, yang di WhatsApp tampil
        # sebagai tanda bintang mentah. WhatsApp memakai satu bintang untuk tebal.
        self.assertIn("jangan menambah huruf tebal", self.PETA)
        self.assertIn("`**…**`", self.PETA)

    def test_pesan_tak_dikenal_ditanyakan_bukan_ditebak(self):
        self.assertIn("Tanyakan maksudnya", self.PETA)

    def test_skill_tidak_punya_peta_kedua(self):
        self.assertNotIn("python3 scripts/resi.py --find-dup", SKILL)   # perintahnya hanya di peta
        self.assertNotIn('python3 scripts/resi.py --check "<no_resi>"', SKILL)
        self.assertIn("*Peta pesan*", SKILL)
        self.assertNotIn("tabel *Laporan*", SKILL_DAN_REFERENSI)


class AngkaDariSkripBukanModel(unittest.TestCase):
    """Bot menyalin keluaran skrip; ia tidak menghitung angka dari CSV sendiri."""

    def test_agents_mengarahkan_setiap_permintaan_angka_ke_skrip(self):
        for perintah in ("scripts/laporan-harian.py", "scripts/check-bills.py --mode status",
                         "scripts/akun.py", "scripts/laporan-bulanan.py --bulan YYYY-MM",
                         "scripts/check-bills.py --mode budget"):
            self.assertIn(perintah, AGENTS)

    def test_skill_tidak_lagi_menyuruh_menghitung_dari_csv(self):
        self.assertNotIn("Hitung sisa dan persentase", SKILL)
        self.assertNotIn("Hitung persentase: `(total / budget_bulanan)", SKILL)
        self.assertNotIn("Saldo Bank Utama: Rp", SKILL)   # saldo karangan di konfirmasi transfer
        self.assertNotIn("✅ Transfer dicatat!", SKILL)   # kerangka konfirmasi hanya satu
        self.assertNotIn("food:          Rp 125.000", SKILL)  # contoh laporan harian buatan tangan

    def test_cek_budget_setelah_tersimpan_lewat_skrip(self):
        self.assertIn("Cek budget setelah tersimpan", AGENTS)
        self.assertIn("Jangan menghitung persentase budget sendiri", AGENTS)


class Dokumen(unittest.TestCase):
    def test_adr_dan_glosarium(self):
        self.assertTrue(list((AKAR / "docs" / "adr").glob("0016-*.md")))
        self.assertIn("**Pratinjau**", (AKAR / "CONTEXT.md").read_text(encoding="utf-8"))
        self.assertTrue(list((AKAR / "docs" / "adr").glob("0019-*.md")))
        self.assertIn("**Arah**", (AKAR / "CONTEXT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
