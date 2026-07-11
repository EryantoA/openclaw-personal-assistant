#!/bin/bash

# ============================================================
# Backup Script — Family Bill Tracker
# Jalankan otomatis via cron atau manual: bash scripts/backup.sh
# ============================================================

set -e

# Paths (relatif ke folder project)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data"
BACKUP_DIR="$DATA_DIR/backups"
SOURCE_FILE="$DATA_DIR/bills.csv"

# Tanggal untuk nama file
DATE=$(date +%Y%m%d)
DATETIME=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/bills_$DATE.csv"
LOG_FILE="$BACKUP_DIR/backup.log"

# Buat folder backup jika belum ada
mkdir -p "$BACKUP_DIR"

# Cek apakah source file ada
if [ ! -f "$SOURCE_FILE" ]; then
  echo "⚠️  File $SOURCE_FILE tidak ditemukan, skip backup."
  exit 0
fi

# Hitung jumlah baris data (minus header)
TOTAL_ROWS=$(tail -n +2 "$SOURCE_FILE" | grep -c "." 2>/dev/null || echo "0")

# Copy file
cp "$SOURCE_FILE" "$BACKUP_FILE"

# Log
echo "[$DATETIME] Backup berhasil: bills_$DATE.csv ($TOTAL_ROWS transaksi)" >> "$LOG_FILE"

# Output untuk OpenClaw
echo "✅ Backup selesai!"
echo "📁 File: data/backups/bills_$DATE.csv"
echo "📊 Total transaksi: $TOTAL_ROWS"

# ── Export ke Excel per bulan ────────────────────────────────
echo ""
EXPORT_STATUS=0
EXPORT_OUTPUT=$(python3 "$SCRIPT_DIR/export-excel.py" 2>&1) || EXPORT_STATUS=$?
echo "$EXPORT_OUTPUT"

if [ "$EXPORT_STATUS" -eq 0 ]; then
  # Ambil nama file SEBENARNYA dari output python (bisa beda 1 detik dari $DATETIME
  # karena stempel waktunya dibuat sendiri oleh export-excel.py saat file ditulis).
  XLSX_NAME=$(echo "$EXPORT_OUTPUT" | grep "📁 File:" | sed 's#.*/##')
  echo "[$DATETIME] Export Excel berhasil: ${XLSX_NAME:-<nama tidak terdeteksi>} (file baru tiap export)" >> "$LOG_FILE"
else
  echo "⚠️  Export Excel gagal (lihat pesan di atas)."
  echo "[$DATETIME] Export Excel GAGAL" >> "$LOG_FILE"
fi
echo ""

# ── Cleanup CSV: hapus backup lebih dari 30 hari ──────────────
# (Cleanup file .xlsx sudah ditangani otomatis di dalam export-excel.py
# sendiri — lihat cleanup_old_exports() — supaya retensinya berlaku juga
# saat export dipanggil langsung, bukan cuma lewat backup.sh ini.)
DELETED=0
while IFS= read -r -d '' OLD_FILE; do
  rm "$OLD_FILE"
  DELETED=$((DELETED + 1))
done < <(find "$BACKUP_DIR" -name "bills_*.csv" -mtime +30 -print0 2>/dev/null)

if [ "$DELETED" -gt 0 ]; then
  echo "🗑️  $DELETED backup CSV lama dihapus (>30 hari)"
fi

# Tampilkan jumlah backup tersimpan
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "bills_*.csv" 2>/dev/null | wc -l | tr -d ' ')
TOTAL_XLSX=$(find "$BACKUP_DIR" -name "bills_export_*.xlsx" 2>/dev/null | wc -l | tr -d ' ')
echo "💾 Total backup tersimpan: $TOTAL_BACKUPS CSV + $TOTAL_XLSX Excel"
