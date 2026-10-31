"""Skrip yang dipakai cron harus terkompilasi di Python bawaan macOS (3.9), bukan hanya di Python
yang menjalankan tes ini. Contoh yang pernah lolos tes tapi gagal di cron: tanda kutip sama di
dalam f-string (`f"{x["k"]}"`), sah hanya di Python 3.12+.

    python3 -m unittest tests/test_sintaks_cron.py
"""
import subprocess
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
PYTHON_CRON = Path("/usr/bin/python3")


class SintaksCron(unittest.TestCase):
    @unittest.skipUnless(PYTHON_CRON.exists(), "tidak ada /usr/bin/python3")
    def test_semua_skrip_terkompilasi_di_python_cron(self):
        versi = subprocess.run([str(PYTHON_CRON), "-c", "import sys;print(sys.version_info[:2] < (3, 12))"],
                               capture_output=True, text=True).stdout.strip()
        if versi != "True":
            self.skipTest("Python sistem sudah 3.12+, tidak bisa meniru cron")
        for skrip in sorted((AKAR / "scripts").glob("*.py")):
            hasil = subprocess.run([str(PYTHON_CRON), "-c",
                                    "import sys;compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')",
                                    str(skrip)], capture_output=True, text=True)
            self.assertEqual(hasil.returncode, 0, f"{skrip.name}: {hasil.stderr.strip()[-200:]}")


if __name__ == "__main__":
    unittest.main()
