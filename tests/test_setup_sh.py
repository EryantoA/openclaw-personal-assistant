"""Tes setup.sh tanpa menjalankan seluruh skrip (ia meng-install ulang openclaw lewat npm).

Tiap bagian diambil per penanda `# ── N.` lalu dijalankan sendiri di folder sementara.

    python3 -m unittest tests/test_setup_sh.py

Latar belakang (1 Nov 2026): langkah 4 menambahkan kolom `jatuh_tempo` ke bills.csv yang sudah ada
(menambah koma di setiap baris) dan membuat bills.csv baru dengan header 8 kolom lama; keduanya
merusak Buku Kas 12 kolom (ADR-0003). Langkah 6 masih memeriksa kunci API Groq/DeepSeek/Anthropic
padahal bot memakai login Claude.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
SKRIP = (AKAR / "setup.sh").read_text(encoding="utf-8")
WARNA = "CYAN=''; GREEN=''; YELLOW=''; RED=''; RESET=''\nset -e\n"
HEADER = "tanggal,tipe,kategori,item,jumlah,catatan,channel,pencatat,akun,akun_tujuan,waktu,no_resi"


def bagian(n):
    """Teks dari penanda `# ── n.` sampai penanda berikutnya."""
    m = re.search(rf"^# ── {n}\. .*?(?=^# ── {n + 1}\. )", SKRIP, flags=re.S | re.M)
    assert m, f"bagian {n} tidak ditemukan"
    return m.group(0)


def jalankan(teks, cwd, path_tambahan=None):
    env = dict(os.environ)
    if path_tambahan:
        env["PATH"] = f"{path_tambahan}:{env['PATH']}"
    return subprocess.run(["bash", "-c", WARNA + teks], cwd=cwd, env=env, capture_output=True, text=True)


class Sintaks(unittest.TestCase):
    def test_bash_menerima_skrip(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(AKAR / "setup.sh")]).returncode, 0)

    def test_tidak_ada_sisa_setup_lama(self):
        for lama in ("GROQ", "DEEPSEEK", "ANTHROPIC_API_KEY", "console.groq.com", "jatuh_tempo",
                     "Groq →", "pengirim,jatuh"):
            self.assertNotIn(lama, SKRIP)


class Langkah4Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "data").mkdir()
        shutil.copy(AKAR / "data" / "bills.csv.example", self.tmp / "data" / "bills.csv.example")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bills_csv_yang_sudah_ada_tidak_disentuh(self):
        isi = f"{HEADER}\n2026-10-31,pengeluaran,food,Nasi,25000,,whatsapp,Eryanto,,,12:00,TRX-1\n"
        (self.tmp / "data" / "bills.csv").write_text(isi, encoding="utf-8")
        hasil = jalankan(bagian(4), self.tmp)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        self.assertEqual((self.tmp / "data" / "bills.csv").read_text(encoding="utf-8"), isi)

    def test_bills_csv_baru_memakai_header_dua_belas_kolom(self):
        hasil = jalankan(bagian(4), self.tmp)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        self.assertEqual((self.tmp / "data" / "bills.csv").read_text(encoding="utf-8").strip(), HEADER)

    def test_budget_json_baru_memuat_ambang_pengeluaran_besar(self):
        jalankan(bagian(4), self.tmp)
        import json
        isi = json.loads((self.tmp / "data" / "budget.json").read_text(encoding="utf-8"))
        self.assertEqual(isi["pengeluaran_besar_mulai"], 1_000_000)


@unittest.skipUnless(shutil.which("node"), "node tidak terpasang")
class Langkah6Login(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "openclaw.json").write_text(
            '{"channels":{"telegram":{"token":"123:abc"},"whatsapp":{"allowFrom":["+6281234567890"]}}}',
            encoding="utf-8")
        self.bin = self.tmp / "bin"
        self.bin.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def claude_palsu(self, keluaran, kode=0):
        f = self.bin / "claude"
        f.write_text(f"#!/bin/bash\necho '{keluaran}'\nexit {kode}\n", encoding="utf-8")
        f.chmod(0o755)

    def test_login_claude_terdeteksi(self):
        self.claude_palsu('{"loggedIn": true, "authMethod": "claude.ai"}')
        hasil = jalankan(bagian(6), self.tmp, str(self.bin))
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        self.assertIn("✓ Login Claude", hasil.stdout)

    def test_belum_login_diberi_petunjuk_dan_tidak_menghentikan_setup(self):
        self.claude_palsu('{"loggedIn": false}')
        hasil = jalankan(bagian(6), self.tmp, str(self.bin))
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        self.assertIn("belum login", hasil.stdout)
        self.assertIn("claude auth status", hasil.stdout)

    def test_claude_tidak_terpasang_diberi_petunjuk(self):
        # PATH hanya berisi folder kosong kita + direktori sistem tanpa `claude`
        env_kosong = subprocess.run(["bash", "-c", WARNA + bagian(6)], cwd=self.tmp, capture_output=True, text=True,
                                    env={"PATH": f"{self.bin}:/usr/bin:/bin"})
        self.assertEqual(env_kosong.returncode, 0, env_kosong.stderr)
        self.assertIn("belum login", env_kosong.stdout)

    def test_token_telegram_dan_nomor_whatsapp_tetap_diperiksa(self):
        self.claude_palsu('{"loggedIn": true}')
        hasil = jalankan(bagian(6), self.tmp, str(self.bin))
        self.assertIn("Telegram Bot Token sudah diisi", hasil.stdout)
        self.assertIn("Nomor WhatsApp sudah diisi", hasil.stdout)

    def test_tidak_lagi_mencari_kunci_api(self):
        self.claude_palsu('{"loggedIn": true}')
        hasil = jalankan(bagian(6), self.tmp, str(self.bin))
        for lama in ("Groq", "DeepSeek", "Anthropic API Key"):
            self.assertNotIn(lama, hasil.stdout)


class Langkah7dan8Teks(unittest.TestCase):
    def test_urutan_model_diambil_dari_konfigurasi_bukan_ditulis_keras(self):
        self.assertNotIn("Urutan:", bagian(7))

    def test_jadwal_sesuai_cron_sebenarnya(self):
        akhir = SKRIP[SKRIP.index("# ── 8. "):]
        self.assertIn("Senin pukul", akhir)             # laporan mingguan: Senin 07:00 (ADR-0013)
        self.assertIn("07:00", akhir)
        self.assertNotIn("Minggu pukul 20:00", akhir)   # jadwal lama yang salah
        self.assertNotIn("Reminder tagihan", akhir)     # tak ada cron reminder terpisah
        self.assertIn("tanggal 6", akhir)               # laporan bulanan (ADR-0012)


class ReadmeSelaras(unittest.TestCase):
    def test_readme_tidak_lagi_minta_langkah_api_key_diabaikan(self):
        readme = (AKAR / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("masih menampilkan", readme)
        self.assertIn("Cek login Claude", readme)
        self.assertIn("bills.csv", readme[readme.index("Jalankan Setup"):readme.index("Jalankan Gateway")])


if __name__ == "__main__":
    unittest.main()
