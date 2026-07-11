#!/bin/bash

# ============================================================
# Setup Script — Family Bill Tracker (OpenClaw)
# ============================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║   Family Bill Tracker — OpenClaw Setup   ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── 1. Check Node.js ─────────────────────────────────────────
echo -e "${CYAN}[1/8] Mengecek Node.js...${RESET}"
if ! command -v node &> /dev/null; then
  echo -e "${RED}✗ Node.js tidak ditemukan!${RESET}"
  echo "  Install Node.js 24+ dari: https://nodejs.org"
  exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 24 ]; then
  echo -e "${RED}✗ Node.js versi $NODE_VERSION ditemukan, butuh v24+${RESET}"
  echo "  Update Node.js dari: https://nodejs.org"
  exit 1
fi
echo -e "${GREEN}✓ Node.js $(node -v) OK${RESET}"

# ── 2. Reinstall OpenClaw ────────────────────────────────────
echo ""
echo -e "${CYAN}[2/8] Reinstall OpenClaw (versi terbaru)...${RESET}"
if command -v openclaw &> /dev/null; then
  echo -e "${YELLOW}  Menghapus versi lama...${RESET}"
  npm uninstall -g openclaw 2>/dev/null || true
fi
npm install -g openclaw
echo -e "${GREEN}✓ OpenClaw $(openclaw --version 2>/dev/null || echo 'terinstall') OK${RESET}"

# ── 3. Check Python 3 ────────────────────────────────────────
echo ""
echo -e "${CYAN}[3/8] Mengecek Python 3...${RESET}"
if command -v python3 &> /dev/null; then
  PYTHON_VER=$(python3 --version 2>&1)
  echo -e "${GREEN}✓ $PYTHON_VER OK${RESET}"
else
  echo -e "${YELLOW}⚠ Python 3 tidak ditemukan${RESET}"
  echo "  Script check-bills.py membutuhkan Python 3."
  echo "  Install dari: https://www.python.org atau via brew: brew install python3"
fi

# ── 4. Buat folder struktur ──────────────────────────────────
echo ""
echo -e "${CYAN}[4/8] Membuat struktur folder...${RESET}"

mkdir -p data
mkdir -p data/backups
mkdir -p scripts

if [ ! -f data/bills.csv ]; then
  echo "tanggal,kategori,item,jumlah,catatan,channel,pengirim,jatuh_tempo" > data/bills.csv
  echo -e "${GREEN}✓ data/bills.csv dibuat${RESET}"
else
  # Cek apakah header perlu update (tambah kolom jatuh_tempo)
  HEADER=$(head -1 data/bills.csv)
  if [[ "$HEADER" != *"jatuh_tempo"* ]]; then
    TMPFILE=$(mktemp)
    echo "${HEADER},jatuh_tempo" > "$TMPFILE"
    tail -n +2 data/bills.csv | awk '{print $0","}' >> "$TMPFILE"
    mv "$TMPFILE" data/bills.csv
    echo -e "${GREEN}✓ data/bills.csv diupdate (tambah kolom jatuh_tempo)${RESET}"
  else
    echo -e "${GREEN}✓ data/bills.csv sudah ada${RESET}"
  fi
fi

if [ ! -f data/budget.json ]; then
  cat > data/budget.json << 'EOF'
{
  "budget_bulanan": 0,
  "alert_persen": 80,
  "kategori_custom": []
}
EOF
  echo -e "${GREEN}✓ data/budget.json dibuat${RESET}"
else
  echo -e "${GREEN}✓ data/budget.json sudah ada${RESET}"
fi

# Set permission untuk scripts
if [ -f scripts/backup.sh ]; then
  chmod +x scripts/backup.sh
  echo -e "${GREEN}✓ scripts/backup.sh siap dijalankan${RESET}"
fi

if [ -f scripts/check-bills.py ]; then
  chmod +x scripts/check-bills.py
  echo -e "${GREEN}✓ scripts/check-bills.py siap dijalankan${RESET}"
fi

# ── 5. Test scripts ──────────────────────────────────────────
echo ""
echo -e "${CYAN}[5/8] Test scripts...${RESET}"
if command -v python3 &> /dev/null && [ -f scripts/check-bills.py ]; then
  TEST_OUTPUT=$(python3 scripts/check-bills.py --mode all 2>&1)
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ check-bills.py berjalan OK${RESET}"
  else
    echo -e "${YELLOW}⚠ check-bills.py ada error: $TEST_OUTPUT${RESET}"
  fi
fi

# ── 6. Cek konfigurasi API Keys ──────────────────────────────
echo ""
echo -e "${CYAN}[6/8] Mengecek konfigurasi API Keys...${RESET}"

GROQ_KEY=$(node -e "const c=require('./openclaw.json'); console.log(c.env?.GROQ_API_KEY||'')" 2>/dev/null || echo "")
DEEPSEEK_KEY=$(node -e "const c=require('./openclaw.json'); console.log(c.env?.DEEPSEEK_API_KEY||'')" 2>/dev/null || echo "")
ANTHROPIC_KEY=$(node -e "const c=require('./openclaw.json'); console.log(c.env?.ANTHROPIC_API_KEY||'')" 2>/dev/null || echo "")
TG_TOKEN=$(node -e "const c=require('./openclaw.json'); console.log(c.channels?.telegram?.token||'')" 2>/dev/null || echo "")
WA_NUMBER=$(node -e "const c=require('./openclaw.json'); console.log((c.channels?.whatsapp?.allowFrom||[])[0]||'')" 2>/dev/null || echo "")

# Groq
if [[ "$GROQ_KEY" == gsk_* ]]; then
  echo -e "${GREEN}✓ [PRIMARY] Groq API Key sudah diisi${RESET}"
else
  echo -e "${RED}✗ [PRIMARY] Groq API Key belum diisi!${RESET}"
  echo "  → Daftar GRATIS di: https://console.groq.com"
  echo "  → Isi di openclaw.json → env.GROQ_API_KEY"
fi

# DeepSeek
if [[ "$DEEPSEEK_KEY" == sk-* ]]; then
  echo -e "${GREEN}✓ [FALLBACK 1] DeepSeek API Key sudah diisi${RESET}"
else
  echo -e "${YELLOW}⚠ [FALLBACK 1] DeepSeek API Key belum diisi (opsional)${RESET}"
  echo "  → Top up \$2 di: https://platform.deepseek.com"
  echo "  → Isi di openclaw.json → env.DEEPSEEK_API_KEY"
fi

# Anthropic / Claude
if [[ "$ANTHROPIC_KEY" == sk-ant-* ]]; then
  echo -e "${GREEN}✓ [FALLBACK 2] Anthropic API Key sudah diisi${RESET}"
else
  echo -e "${YELLOW}⚠ [FALLBACK 2] Anthropic API Key belum diisi (opsional)${RESET}"
  echo "  → Dapatkan di: https://console.anthropic.com → API Keys"
  echo "  → Isi di openclaw.json → env.ANTHROPIC_API_KEY"
fi

# Telegram
if [[ "$TG_TOKEN" =~ ^[0-9]+:.+ ]]; then
  echo -e "${GREEN}✓ Telegram Bot Token sudah diisi${RESET}"
else
  echo -e "${YELLOW}⚠ Telegram Bot Token belum diisi${RESET}"
  echo "  → Buat bot di: https://t.me/BotFather → /newbot"
  echo "  → Isi di openclaw.json → channels.telegram.token"
fi

# WhatsApp
if [[ "$WA_NUMBER" == +628* ]] && [[ "$WA_NUMBER" != "+628XXXXXXXXXX" ]]; then
  echo -e "${GREEN}✓ Nomor WhatsApp sudah diisi: $WA_NUMBER${RESET}"
else
  echo -e "${YELLOW}⚠ Nomor WhatsApp belum diisi${RESET}"
  echo "  → Isi di openclaw.json → channels.whatsapp.allowFrom"
  echo "  → Format: \"+6281234567890\" (dengan +62)"
fi

# ── 7. Tampilkan model yang digunakan ────────────────────────
echo ""
echo -e "${CYAN}[7/8] Konfigurasi Model AI...${RESET}"
PRIMARY=$(node -e "const c=require('./openclaw.json'); console.log(c.agents?.defaults?.model?.primary||'')" 2>/dev/null || echo "")
FALLBACK=$(node -e "const c=require('./openclaw.json'); const f=c.agents?.defaults?.model?.fallbacks||[]; console.log(f.join(' → '))" 2>/dev/null || echo "")
echo -e "  🟢 Primary  : ${GREEN}${PRIMARY}${RESET}"
echo -e "  🔄 Fallback : ${YELLOW}${FALLBACK}${RESET}"
echo ""
echo -e "  Urutan: Groq → DeepSeek → Claude (Anthropic)"
echo -e "  ${CYAN}OpenClaw otomatis beralih ke fallback jika primary error/limit.${RESET}"

# ── 8. Selesai ───────────────────────────────────────────────
echo ""
echo -e "${CYAN}[8/8] Setup selesai!${RESET}"
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}║          Cara Menjalankan Gateway        ║${RESET}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${YELLOW}openclaw start${RESET}          — Jalankan gateway"
echo -e "  ${YELLOW}openclaw start --qr${RESET}     — Tampilkan QR WhatsApp di terminal"
echo ""
echo -e "  Setelah gateway jalan:"
echo -e "  • Scan QR WhatsApp dengan HP kamu"
echo -e "  • Buka Telegram dan chat bot kamu"
echo -e "  • Coba kirim: ${CYAN}beli beras 50rb${RESET}"
echo ""
echo -e "  ${CYAN}Fitur:${RESET}"
echo -e "  • ${YELLOW}set budget 3 juta${RESET}         — Set budget bulanan"
echo -e "  • ${YELLOW}sisa budget${RESET}               — Cek sisa budget"
echo -e "  • ${YELLOW}tambah kategori Investasi${RESET}   — Buat kategori custom"
echo -e "  • ${YELLOW}jatuh tempo${RESET}               — Lihat tagihan mendatang"
echo -e "  • ${YELLOW}backup sekarang${RESET}           — Backup manual data"
echo ""
echo -e "  Jadwal otomatis:"
echo -e "  • Backup data setiap hari pukul ${YELLOW}02:00${RESET}"
echo -e "  • Reminder tagihan jatuh tempo ${YELLOW}09:00${RESET} (jika ada)"
echo -e "  • Cek budget malam pukul ${YELLOW}20:00${RESET} (Senin-Sabtu)"
echo -e "  • Laporan mingguan setiap ${YELLOW}Minggu pukul 20:00${RESET}"
echo ""
