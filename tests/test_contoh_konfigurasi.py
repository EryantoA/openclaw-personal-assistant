"""openclaw.json.example harus tetap JSON sah dan memuat pengaturan yang kita butuhkan (ADR-0025).

    python3 -m unittest tests/test_contoh_konfigurasi.py
"""
import json
import re
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
CONTOH = json.loads((AKAR / "openclaw.json.example").read_text(encoding="utf-8"))


class ResetSesiGrup(unittest.TestCase):
    def test_sesi_grup_reset_setelah_dua_jam_tak_aktif(self):
        # Sesi grup yang panjang membuat bot meniru balasan lamanya dan mengabaikan AGENTS.md.
        # Skema OpenClaw menolak kunci komentar di blok session, jadi alasannya ada di ADR-0025.
        grup = CONTOH["session"]["resetByType"]["group"]
        self.assertEqual(grup, {"mode": "idle", "idleMinutes": 120})

    def test_alasan_tercatat_di_adr(self):
        adr = list((AKAR / "docs" / "adr").glob("0025-*.md"))
        self.assertEqual(len(adr), 1)
        self.assertIn("idleMinutes", adr[0].read_text(encoding="utf-8"))


APPROVALS = json.loads((AKAR / "exec-approvals.keuangan.json.example").read_text(encoding="utf-8"))
KEUANGAN = CONTOH["agents"]["entries"]["keuangan"]


class AgenKeuanganRelay(unittest.TestCase):
    """Agen `keuangan` menerima Relay Hermes (ADR-0023, hasil spike #38)."""

    def test_workspace_sama_dengan_agen_utama_dan_alat_dibatasi(self):
        self.assertTrue(KEUANGAN["workspace"].endswith("openclaw-personal-assistant"))
        self.assertEqual(KEUANGAN["tools"]["allow"], ["exec"])
        self.assertEqual(KEUANGAN["tools"]["exec"], {"mode": "allowlist"})
        # read membaca di luar workspace (spike #38), jadi wajib ditolak bersama alat tulis dan web.
        for alat in ("read", "write", "edit", "apply_patch", "browser", "web_search", "web_fetch",
                     "message", "cron", "nodes", "canvas"):
            self.assertIn(alat, KEUANGAN["tools"]["deny"])

    def test_model_sonnet_karena_haiku_tidak_memanggil_alat(self):
        # Uji hidup 2 Nov 2026: Haiku menulis perintah lalu minta /approve tanpa memanggil alat.
        self.assertEqual(KEUANGAN["model"], "anthropic/claude-sonnet-5")

    def test_peer_hermes_dengan_token_dari_lingkungan_bukan_literal(self):
        a2a = CONTOH["channels"]["a2a"]
        self.assertEqual(a2a["peers"]["hermes"]["token"], "${A2A_HERMES_TOKEN}")
        self.assertEqual(a2a["exposeAgents"], ["keuangan"])  # Agent Card publik tidak membuka `main`

    def test_peer_hermes_terikat_ke_keuangan_bukan_main(self):
        # Peer tanpa binding dijawab `main` dengan exec penuh (spike #38).
        cocok = [b for b in CONTOH["bindings"]
                 if b["match"]["channel"] == "a2a" and b["match"]["peer"]["id"] == "hermes"]
        self.assertEqual([b["agentId"] for b in cocok], ["keuangan"])

    def test_tidak_ada_token_sungguhan_di_contoh(self):
        teks = (AKAR / "openclaw.json.example").read_text(encoding="utf-8")
        self.assertNotRegex(teks, r'"token"\s*:\s*"[0-9a-f]{32,}"')


class AllowlistKeuangan(unittest.TestCase):
    ATURAN = APPROVALS["agents"]["keuangan"]["allowlist"]

    def cocok(self, argumen: str) -> bool:
        return any(a["pattern"] == "python3" and re.search(a["argPattern"], argumen)
                   for a in self.ATURAN)

    def test_skrip_bill_tracker_lolos(self):
        for arg in ("scripts/catat.py --uji --json '{}'", "scripts/buku.py cari --batas 1",
                    "scripts/laporan-harian.py", "scripts/laporan-bulanan.py --bulan 2026-10",
                    "scripts/check-bills.py --mode status", "scripts/akun.py",
                    "scripts/resi.py --check STRUK-1", "scripts/rekap-bulanan.py"):
            self.assertTrue(self.cocok(arg), arg)

    def test_eksekusi_bebas_dan_skrip_lain_ditolak(self):
        # Tanpa jangkar, nama skrip yang diselipkan di komentar ikut lolos (terbukti di spike #38).
        for arg in ('-c "print(1)  # scripts/catat.py"', "-c 'import os' scripts/buku.py",
                    "scripts/backup.sh", "scripts/export-excel.py", "scripts/../x.py",
                    "/tmp/scripts/catat.py", "scripts/catatan.py",
                    "scripts/laporan-mingguan.py --kirim", "scripts/check-bills.py --mode all --kirim",
                    "scripts/resi.py --backfill", "scripts/resi.py --gen", "scripts/catat.py --paksa --json {}"):
            self.assertFalse(self.cocok(arg), arg)

    def test_semua_argpattern_berjangkar(self):
        for a in self.ATURAN:
            self.assertTrue(a["argPattern"].startswith("^"), a)


if __name__ == "__main__":
    unittest.main()
