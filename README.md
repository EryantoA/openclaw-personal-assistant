# 📱 Family Bill Tracker — WhatsApp + Telegram

Pencatatan pengeluaran keluarga via WhatsApp dan Telegram menggunakan **OpenClaw AI Gateway**.

**Stack AI (3 provider, hemat & cepat):**
- 🟢 **Groq** (primary) — gratis, super cepat, model `llama-3.3-70b-versatile`
- 🟡 **DeepSeek** (fallback 1) — $2 top up tahan berbulan-bulan, model `deepseek-chat`
- 🔵 **Claude / Anthropic** (fallback 2) — model `claude-sonnet-4-6` via Anthropic API

OpenClaw otomatis fallback ke provider berikutnya jika primary error atau kena rate limit.

---

## 🚀 Langkah Setup

### Step 1 — Install Node.js 24+

Download dari [nodejs.org](https://nodejs.org) → pilih versi **LTS terbaru** (24+).

Cek versi:
```bash
node -v   # harus v24.x.x ke atas
```

---

### Step 2 — Dapatkan Groq API Key (GRATIS — PRIMARY)

1. Buka [console.groq.com](https://console.groq.com)
2. Daftar / login dengan Google
3. Klik **API Keys** → **Create API Key**
4. Copy key-nya (mulai dari `gsk_...`)

> 💡 Groq gratis dengan limit 30 req/menit dan 500k token/hari — lebih dari cukup untuk keluarga.

---

### Step 3 — Dapatkan DeepSeek API Key (FALLBACK 1)

1. Buka [platform.deepseek.com](https://platform.deepseek.com)
2. Daftar → **Top Up** minimal $2 (≈ Rp32.000)
3. Buka **API Keys** → buat key baru
4. Copy key-nya (mulai dari `sk-...`)

> 💡 $2 cukup untuk ~16 tahun pencatatan 10 transaksi/hari

---

### Step 4 — Dapatkan Anthropic API Key (FALLBACK 2)

1. Buka [console.anthropic.com](https://console.anthropic.com)
2. Login / daftar
3. Klik **API Keys** → **Create Key**
4. Copy key-nya (mulai dari `sk-ant-...`)

> 💡 Claude digunakan sebagai last resort fallback. Hanya aktif jika Groq & DeepSeek error.

---

### Step 5 — Buat Telegram Bot

1. Buka Telegram → cari **@BotFather**
2. Ketik `/newbot`
3. Ikuti instruksi → masukkan nama dan username bot
4. Copy **token** yang diberikan (format: `1234567890:ABCdef...`)

---

### Step 6 — Isi Konfigurasi

Salin `openclaw.json.example` menjadi `openclaw.json`, lalu isi dengan key/token asli kamu:

```bash
cp openclaw.json.example openclaw.json
```

> ⚠️ `openclaw.json` berisi API key & token asli — file ini **tidak ikut ter-commit** (lihat `.gitignore`).
> Jangan pernah push file ini ke repo publik.

Edit file `openclaw.json`:

```json
{
  "env": {
    "GROQ_API_KEY": "gsk_...",
    "DEEPSEEK_API_KEY": "sk-...",
    "ANTHROPIC_API_KEY": "sk-ant-..."
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "groq/llama-3.3-70b-versatile",
        "fallbacks": [
          "deepseek/deepseek-chat",
          "anthropic/claude-sonnet-4-6"
        ]
      }
    }
  },
  "channels": {
    "telegram": {
      "token": "TOKEN_BOT_TELEGRAM_KAMU"
    },
    "whatsapp": {
      "allowFrom": [
        "+628XXXXXXXXXX"
      ]
    }
  }
}
```

**Ganti:**
- `GROQ_API_KEY` → key dari Step 2
- `DEEPSEEK_API_KEY` → key dari Step 3
- `ANTHROPIC_API_KEY` → key dari Step 4
- `token` → token bot dari Step 5
- `+628XXXXXXXXXX` → nomor HP WhatsApp kamu (format internasional)

---

### Step 7 — Jalankan Setup (Reinstall)

```bash
# Di folder project ini:
bash setup.sh
```

Script ini akan:
- ✅ Uninstall openclaw versi lama
- ✅ Install openclaw versi terbaru
- ✅ Cek semua API key (Groq, DeepSeek, Anthropic)
- ✅ Siapkan folder & data
- ✅ Tampilkan model yang aktif

---

### Step 8 — Jalankan Gateway

```bash
openclaw start
```

Pertama kali, akan muncul **QR Code** di terminal untuk pairing WhatsApp.
Buka WhatsApp di HP → **Perangkat Tertaut** → **Tautkan Perangkat** → scan QR.

---

## 🤖 Konfigurasi Model AI

| Urutan | Provider | Model | Biaya |
|--------|----------|-------|-------|
| 🟢 Primary | Groq | `llama-3.3-70b-versatile` | **GRATIS** |
| 🟡 Fallback 1 | DeepSeek | `deepseek-chat` | ~Rp170/bulan |
| 🔵 Fallback 2 | Anthropic | `claude-sonnet-4-6` | Pay-as-you-go |

Untuk mengganti model, edit bagian ini di `openclaw.json`:
```json
"model": {
  "primary": "groq/llama-3.3-70b-versatile",
  "fallbacks": [
    "deepseek/deepseek-chat",
    "anthropic/claude-sonnet-4-6"
  ]
}
```

Model lain yang bisa dipakai:
- Groq: `groq/llama-3.1-8b-instant` (lebih cepat/hemat)
- DeepSeek: `deepseek/deepseek-r1` (reasoning, lebih pintar)
- Claude: `anthropic/claude-haiku-4-5-20251001` (lebih murah)

---

## 💬 Cara Pakai

### Catat Pengeluaran (Teks)

Kirim pesan biasa ke WhatsApp/Telegram:

```
beli beras 50rb
makan siang 25000
bayar listrik 150.000
alfamart 87500 - sabun, pasta gigi, minyak goreng
```

Bot akan membalas konfirmasi otomatis:
```
✅ Berhasil dicatat!
📦 Item: Beras
📂 Kategori: Makanan
💰 Jumlah: Rp 50.000
📅 Tanggal: 20 Mei 2026
```

### Catat dari Foto Struk 📸

Kirim foto struk belanja → bot otomatis menganalisis dan mencatat semua item.

### Lihat Laporan

```
laporan hari ini
laporan minggu ini
laporan bulan ini
cari listrik
history makanan
hapus terakhir
```

---

## 📊 Laporan Otomatis

Setiap **Minggu pukul 20:00**, bot otomatis mengirim laporan mingguan ke semua channel (WhatsApp + Telegram).

Contoh laporan:
```
📊 LAPORAN KEUANGAN MINGGUAN
Periode: 13 - 19 Mei 2026

🍚 Makanan:      Rp 450.000 (38%)
🧹 Kebersihan:   Rp  95.000  (8%)
⚡ Tagihan:      Rp 320.000 (27%)
🚗 Transportasi: Rp  85.000  (7%)
💊 Kesehatan:    Rp  45.000  (4%)
📦 Lainnya:      Rp 185.000 (16%)

💰 TOTAL: Rp 1.180.000
📝 23 transaksi
```

---

## 📁 Struktur Project

```
openclaw-personal-assistant/
├── openclaw.json              ← Konfigurasi utama (model, API keys, channels)
├── setup.sh                   ← Script reinstall & setup otomatis
├── README.md                  ← Panduan ini
├── skills/
│   └── bill-tracker/
│       └── SKILL.md           ← Instruksi perilaku AI agent
└── data/
    ├── bills.csv              ← Database pengeluaran
    ├── budget.json            ← Konfigurasi budget
    └── backups/               ← Backup otomatis
```

---

## 🔧 Troubleshooting

### QR WhatsApp tidak muncul
```bash
openclaw start --qr
```

### Ganti nomor HP WhatsApp
Edit `openclaw.json` → `channels.whatsapp.allowFrom` → isi nomor baru.

### Tambah anggota keluarga di Telegram
Edit `openclaw.json` → `channels.telegram.allowFrom` → tambah username Telegram (opsional, default semua bisa).

### Groq limit / error
OpenClaw otomatis fallback ke DeepSeek, lalu ke Claude. Tidak perlu setting manual.

### Ganti model AI
Edit `openclaw.json` → `agents.defaults.model.primary` atau `.fallbacks`.

### Reinstall ulang openclaw
```bash
bash setup.sh
```

### Cek log
```bash
openclaw start --debug
```

---

## 💰 Estimasi Biaya

| Provider | Biaya | Catatan |
|----------|-------|---------|
| Groq | **GRATIS** | Rate limit: 30 req/menit, 500k token/hari |
| DeepSeek | ~Rp 170/bulan | 10 transaksi/hari, $2 top up ≈ 16 tahun |
| Anthropic | Pay-as-you-go | ~$0.003/1k token (claude-sonnet) |

---

## 📝 Format Data CSV

File `data/bills.csv` menyimpan semua transaksi (pemasukan & pengeluaran):

```csv
tanggal,tipe,kategori,item,jumlah,catatan,channel,pengirim,jatuh_tempo,waktu,no_resi
2026-05-20,pengeluaran,Makanan,Beras 5kg,75000,,telegram,Ayah,,14:05,TRX-20260520-4821
2026-05-20,pengeluaran,Tagihan,Listrik PLN,150000,token listrik,whatsapp,Ibu,2026-06-01,09:30,STRUK-3f9ab12c
2026-05-25,pemasukan,Gaji,Gaji bulanan,5000000,,whatsapp,Ayah,,08:00,TRX-20260525-0117
```

- Kolom `tipe`: `pemasukan` atau `pengeluaran`. Budget hanya menghitung `pengeluaran`.
- Kolom `waktu`: jam transaksi (`HH:MM`). Dari jam tercetak di struk bila ada, kalau tidak = jam input.
- Kolom `no_resi`: identitas unik tiap transaksi. Struk pakai nomor tercetak (`STRUK-...`), chat auto-generate
  (`TRX-YYYYMMDD-XXXX`). Dipakai untuk menandai transaksi sudah masuk & mencegah duplikat.
- Bisa dibuka langsung di Excel / Google Sheets untuk analisis lebih lanjut.

### 🧾 No Resi & Deteksi Duplikat

Setiap transaksi diberi **no resi**. Kalau kamu **kirim ulang struk yang sama** (atau input transaksi
kembar), bot otomatis mendeteksinya dan **menolak mencatat ulang** — jadi tidak ada data dobel.

Aturan duplikat bisa diatur di `data/budget.json` → blok `duplicate_check`:

```json
"duplicate_check": {
  "aktif": true,
  "match_fields": ["tanggal", "waktu", "jumlah"],
  "aksi": "tolak"
}
```

- `match_fields`: kolom yang harus **sama semua** baru dianggap duplikat. Pilihan:
  `tanggal`, `waktu`, `jumlah` (= total harga), `item`, `kategori`, `catatan`, `pengirim`.
- `aksi`: `tolak` (tidak dicatat) atau `warning` (diberi peringatan, tetap dicatat bila dikonfirmasi).

Cek manual apakah sebuah resi sudah tercatat:
```bash
python3 scripts/resi.py --check "STRUK-3f9ab12c"
```

**Data lama** (transaksi yang sudah tercatat sebelum fitur ini) diberi no resi sekali jalan dengan:
```bash
python3 scripts/resi.py --backfill
```

Cek data dobel di seluruh catatan kapan saja (isi identik, semua kolom sama kecuali `no_resi`):
```bash
python3 scripts/resi.py --find-dup
```

### 📊 Backup & Export Excel per bulan

Backup harian (atau `bash scripts/backup.sh` manual) menghasilkan file di `data/backups/`:
- `bills_YYYYMMDD.csv` — salinan mentah seluruh transaksi, **termasuk kolom `no_resi` & `waktu`**.
- `bills_export_YYYYMMDD_HHMMSS.xlsx` — Excel **dipisah per bulan**: satu sheet `Ringkasan` + satu sheet
  per bulan (`2026-05`, `2026-06`, ...), lengkap Total Pemasukan/Pengeluaran/Saldo. Kolom **`no_resi`**
  ditampilkan paling kiri tiap sheet.

> 🆕 **Tiap export = file baru.** Nama file Excel memakai stempel waktu sampai detik, jadi setiap kali kamu
> minta export, file baru dibuat tanpa menimpa yang lama.

Buat manual kapan saja (menghasilkan file baru tiap dijalankan):
```bash
python3 scripts/export-excel.py
```

**Laporan duplikat (otomatis, tanpa menghapus data):** saat export, semua baris tetap ditulis apa adanya,
tapi bila ada baris kembar (isi identik kecuali `no_resi`), file Excel mendapat sheet **"Duplikat"** dan
output mencetak ringkasan (mis. `⚠️ 2 baris duplikat dalam 1 grup`). Ini memudahkan cek "sudah diinput atau
belum" tanpa risiko kehilangan data.

**Retensi otomatis (30 hari):** tiap kali export Excel baru berhasil dibuat, file `bills_export_*.xlsx`
yang lebih tua dari 30 hari di `data/backups/` otomatis dihapus — berlaku baik lewat `backup.sh` maupun
lewat `python3 scripts/export-excel.py` langsung. Backup CSV harian (`bills_*.csv`) punya retensi 30 hari
terpisah di `backup.sh`.
