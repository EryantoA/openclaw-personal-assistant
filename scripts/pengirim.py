"""Pengirim pesan WhatsApp untuk cron tanpa model.

Dipakai tiga pesan otomatis: laporan-bulanan.py (ADR-0012), laporan-mingguan.py (ADR-0013),
dan check-bills.py --kirim (cron cek_budget_malam). Hidup di file sendiri supaya ketiganya
tidak saling bergantung — kalau satu skrip laporan rusak, pesan yang lain tetap terkirim.

Pengiriman lewat `openclaw message send`, channel plugin Gateway yang tidak menyentuh model.
periksa-kesehatan.py sengaja TIDAK memakai modul ini: penjaga harus berdiri sendiri (ADR-0011).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"


def tujuan_baku():
    """Nomor pemilik dari config — tidak ditulis keras di repo (ADR-0011)."""
    try:
        d = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
        return [("whatsapp", d["channels"]["whatsapp"]["allowFrom"][0])]
    except Exception:  # noqa: BLE001
        return []


def kirim_sekali(pesan, kanal, ke):
    argv = ["openclaw", "message", "send", "--channel", kanal, "--target", ke, "-m", pesan]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        return p.returncode == 0, (p.stderr or p.stdout).strip()[:200]
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def kirim(pesan, kanal, ke, coba=3, jeda=60):
    """Coba ulang: koneksi WhatsApp sesekali putus sesaat.

    Riwayat penjaga kesehatan 5–21 Sep 2026: 9 dari 39 run yang mencoba mengirim gagal secara
    acak ("Connection Closed", "No active WhatsApp Web listener"), sementara run sebelum dan
    sesudahnya terkirim. Risikonya pesan ganda kalau "gagal" ternyata sampai — lebih murah
    daripada pesan yang tidak sampai. Cron pemakainya butuh batas waktu ≥ 420 detik.
    """
    ket = ""
    for i in range(coba):
        if i:
            time.sleep(jeda)
        ok, ket = kirim_sekali(pesan, kanal, ke)
        if ok:
            return True, ket
        print(f"(percobaan {i + 1}/{coba} gagal: {ket[:120]})", file=sys.stderr)
    return False, ket
