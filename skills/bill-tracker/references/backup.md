# Backup dan export Excel

Backup otomatis harian dan perintah manual.

Backup otomatis tiap hari pukul 02:00 (`scripts/backup.sh`) ke `data/backups/`:
`bills_YYYYMMDD.csv` (salinan mentah) dan `bills_export_YYYYMMDD_HHMMSS.xlsx` (Excel: sheet
`Ringkasan` + satu sheet per bulan, plus sheet `Duplikat` bila ada baris kembar — hanya
dilaporkan, tidak ada yang dihapus). Tiap export membuat file baru; yang lebih tua dari 30 hari
dihapus otomatis.

## Cek Status Backup
Trigger: `backup`, `cek backup`, `status backup`

List isi `data/backups/` (Bash) dan laporkan **apa adanya**: jumlah CSV dan Excel yang benar-benar
ada dan file terbarunya (dari stempel di nama file). Jangan mengarang jumlah atau jam.

## Backup Manual / Export Excel
Trigger: `backup sekarang`, `backup manual`, `export excel`, `backup excel`

Jalankan `bash scripts/backup.sh` (CSV **dan** Excel). Hanya Excel: `python3 scripts/export-excel.py`.
Sebut nama file dari keluaran skrip, bukan dari ingatan.
