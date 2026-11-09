# 📱 Family Bill Tracker — WhatsApp + Telegram

Pencatatan pengeluaran keluarga via WhatsApp dan Telegram menggunakan **OpenClaw AI Gateway**.

**Stack AI:** Claude, lewat login Claude di Mac (`claude-cli`) — tanpa kunci API.
- 🟢 **Primary:** `anthropic/claude-haiku-4-5`
- 🔵 **Fallback:** `anthropic/claude-opus-4-7`

OpenClaw otomatis beralih ke fallback jika primary error. Cek yang aktif dengan
`openclaw models status`.

---

## 🚀 Langkah Setup

### Step 1 — Install Node.js 24+

Download dari [nodejs.org](https://nodejs.org) → pilih versi **LTS terbaru** (24+).

Cek versi:
```bash
node -v   # harus v24.x.x ke atas
```

---

### Step 2 — Login Claude

Bot memakai akun Claude yang login di Mac ini, bukan kunci API. Di Terminal:

```bash
claude            # ikuti petunjuk login
claude auth status   # harus "loggedIn": true
```

Kalau sesi login habis, bot berhenti membalas (lihat *Bot tidak membalas sama sekali* di bawah).

---

### Step 3 — Buat Telegram Bot

1. Buka Telegram → cari **@BotFather**
2. Ketik `/newbot`
3. Ikuti instruksi → masukkan nama dan username bot
4. Copy **token** yang diberikan (format: `1234567890:ABCdef...`)

---

### Step 4 — Isi Konfigurasi

Salin `openclaw.json.example` menjadi `openclaw.json`, lalu isi dengan token/nomor asli kamu:

```bash
cp openclaw.json.example openclaw.json
```

> ⚠️ `openclaw.json` berisi token bot asli — file ini **tidak ikut ter-commit** (lihat `.gitignore`).
> Jangan pernah push file ini ke repo publik.

Edit file `openclaw.json`:

```json
{
  "env": {},
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-haiku-4-5",
        "fallbacks": ["anthropic/claude-opus-4-7"]
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
- `token` → token bot dari Step 3
- `+628XXXXXXXXXX` → nomor HP WhatsApp kamu (format internasional)

---

### Step 5 — Jalankan Setup (Reinstall)

```bash
# Di folder project ini:
bash setup.sh
```

Script ini akan:
- ✅ Uninstall openclaw versi lama
- ✅ Install openclaw versi terbaru
- ✅ Cek login Claude, token Telegram, dan nomor WhatsApp
- ✅ Membuat `data/bills.csv` (12 kolom) hanya bila belum ada; Buku Kas yang sudah ada tidak diubah
- ✅ Siapkan folder & data
- ✅ Tampilkan model yang aktif

---

### Step 6 — Jalankan Gateway

```bash
openclaw start
```

Pertama kali, akan muncul **QR Code** di terminal untuk pairing WhatsApp.
Buka WhatsApp di HP → **Perangkat Tertaut** → **Tautkan Perangkat** → scan QR.

---

## 🤖 Konfigurasi Model AI

| Urutan | Model |
|--------|-------|
| 🟢 Primary | `anthropic/claude-haiku-4-5` |
| 🔵 Fallback | `anthropic/claude-opus-4-7` |

Untuk mengganti model, edit bagian ini di `openclaw.json` (atau `openclaw config set`):
```json
"model": {
  "primary": "anthropic/claude-haiku-4-5",
  "fallbacks": ["anthropic/claude-opus-4-7"]
}
```

Daftar model yang diizinkan dan yang aktif: `openclaw models status`.

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
✅ Sudah dicatat!

Struk: TRX-20260520-4821 | Jam: 14:05

Detail:
- Beras: Rp 50.000
- Total: Rp 50.000
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

## 🩺 Penjaga Kesehatan

Berjalan **08:00, 14:00, dan 21:00 WIB**, dan mengabari lewat WhatsApp hanya kalau ada
yang salah:

- cron gagal atau mandek (lewat jadwal > 3 jam)
- OAuth sudah lewat masa berlaku — tandanya penyegaran otomatis berhenti jalan. Tidak ada
  peringatan dini di sini: token akses cuma hidup hitungan jam lalu disegarkan sendiri,
  jadi ambang "hampir habis" dalam satuan hari akan menyala pada setiap pemeriksaan sehat
- `bills.csv` tidak bertambah ≥ 3 hari — gejala jalur WhatsApp mati, bukan sekadar sepi

Peringatan yang isinya sama tidak diulang sebelum 12 jam, supaya tidak jadi gangguan yang
lama-lama diabaikan.

```bash
python3 scripts/periksa-kesehatan.py             # periksa & cetak saja (aman)
python3 scripts/periksa-kesehatan.py --kirim     # kirim kalau ada masalah
python3 scripts/periksa-kesehatan.py --uji-kirim # buktikan jalur kirim hidup (dry-run)
```

**Kenapa ia tidak memakai model.** Pada 21 Agustus 2026 OAuth `claude-cli` berhenti bisa
disegarkan; seluruh giliran agent gagal — termasuk pencatatan lewat WhatsApp — dan
`cek_budget_malam` berstatus `error` **dua hari tanpa mengabari siapa pun**. Penjaga yang
butuh model akan ikut mati persis saat paling dibutuhkan, jadi ia hanya membaca status dan
mengirim lewat channel plugin Gateway. Rinciannya di
[ADR-0011](docs/adr/0011-penjaga-kesehatan-tidak-boleh-butuh-model.md).

**Batasnya:** penjaga ini hidup di dalam Gateway. Kalau Gateway mati total, ia ikut mati.
Sinyal cadangan untuk kasus itu adalah `backup_harian` — kalau berkas backup berhenti
bertambah, Gateway-nya yang bermasalah.

---

## 📁 Struktur Project

```
openclaw-personal-assistant/
├── openclaw.json              ← Konfigurasi utama (model, channels)
├── setup.sh                   ← Script reinstall & setup otomatis
├── README.md                  ← Panduan ini
├── skills/
│   └── bill-tracker/
│       └── SKILL.md           ← Instruksi perilaku AI agent
└── data/
    ├── bills.csv              ← Database pengeluaran
    ├── budget.json            ← Konfigurasi budget & ambang pengingat
    ├── kewajiban.json         ← Tagihan pascabayar yang belum dibayar
    ├── perkiraan.json         ← Transaksi berulang yang diharapkan
    └── backups/               ← Backup otomatis
```

> 🔒 `kewajiban.json` dan `perkiraan.json` memuat nominal (gaji, premi, langganan), jadi sama-sama
> **tidak dilacak git** seperti `bills.csv` — yang ada di repo cuma pasangan `.example`-nya.
> Lihat `docs/adr/0004` dan `docs/adr/0006`.

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

### Terima laporan otomatis di Telegram atau Discord
Laporan Mingguan, Laporan Bulanan, dan cek budget malam selalu ke WhatsApp. Untuk menambah
Telegram atau Discord, salin `data/tujuan.json.example` ke `data/tujuan.json` (di luar git) dan
isi ID-nya; Kanal yang tidak diisi dilewati. Telegram dan Discord tidak diulang kalau gagal
(WhatsApp 3 kali). Ketiga cron laporan berbatas waktu 600 detik, bukan 420 (ADR-0023); jangan diturunkan lagi.

Uji hidup tujuan Discord (#41), lulus (dilaporkan pemilik, 9 Nov 2026): Laporan Mingguan, Laporan Bulanan
(mode kirim), dan cek budget (saat ada isi) tiba di kanal Discord; dengan satu Kanal dimatikan bergantian
(WhatsApp, Telegram, Discord), dua lainnya tetap menerima dan skrip keluar dengan kode 1.

### Pasang bot Discord OpenClaw (jalur langsung)
Pemilik dan istri mencatat, bertanya, mengubah, dan menghapus dari satu kanal keuangan privat di
Discord (ADR-0023, jalur A). Ini bot **baru** dengan token baru, terpisah dari bot Hermes. Foto
struk juga bisa dikirim di sini. Langkah (1–4 kamu kerjakan sendiri di Discord):

1. [Developer Portal](https://discord.com/developers/applications) → *New Application* → *Bot* →
   *Reset Token* (simpan, jangan kirim di chat). Aktifkan **Message Content Intent**.
2. *OAuth2 → URL Generator*: scope `bot`; izin *View Channels*, *Send Messages*, *Send Messages in
   Threads*, *Read Message History*, *Attach Files*. Buka URL-nya untuk mengundang bot ke server.
3. Buat satu kanal teks **privat** (mis. `#keuangan`): matikan *View Channel* untuk `@everyone`,
   izinkan hanya pemilik, istri, dan bot. Peran yang punya izin *Administrator* tetap melihat semua
   kanal: pastikan tidak ada anggota lain di server dengan peran itu, karena isi Buku Kas memuat gaji.
4. Aktifkan *Developer Mode* (Pengaturan → Lanjutan), lalu *Salin ID* untuk server, kanal, pemilik,
   dan istri. Token masuk `.env` tanpa tampil di layar:
   `read -rs T && echo "DISCORD_BOT_TOKEN=$T" >> ~/.openclaw/.env; unset T`.
5. Tambahkan `channels.discord` dan binding `discord` → `main` dari `openclaw.json.example` ke
   config hidup, dengan ID asli (tanpa kunci `_keterangan`), lewat `openclaw config patch
   --dry-run` lalu tanpa `--dry-run`. `bindings` diganti utuh: gabungkan dengan yang sudah ada.
6. `openclaw gateway restart`, lalu `openclaw channels status` harus menyebut Discord tersambung.
   Contoh config memasang `historyLimit: 0`; jangan dihapus. Bawaannya (20) membuat pesan tanpa
   @mention ikut jadi konteks dan tergabung ke Pratinjau berikutnya (temuan uji hidup 2 Nov 2026).
7. Uji terima, lulus (dilaporkan pemilik: sebagian 2 Nov 2026, sisanya dan seluruh lembar 9 Nov 2026,
   `docs/uji-hidup-discord.md`): tanpa @mention bot diam; wajib @mention di thread dan untuk jawaban
   "ya"; kanal lain dan orang lain diabaikan; catat → Pratinjau → `@bot ya` → tersimpan dengan
   `channel` `discord`; duplikat terdeteksi; `@bot cari …` menemukan baris tadi; foto struk dicatat
   dengan Pratinjau; Pembeli istri tercatat atas namanya; kanal hanya terlihat pemilik dan istri.

Hanya `AGENTS.md` yang dibaca agen untuk kontraknya, jadi percakapan di Discord sama dengan di
WhatsApp. WhatsApp, Telegram, dan bot helpdesk tidak berubah.

### Pasang agen `keuangan` untuk Relay Hermes
Agen kedua yang menerima pesan keuangan dari Hermes lewat A2A (ADR-0023). Workspace dan
`AGENTS.md`-nya sama dengan agen utama, tetapi alatnya hanya skrip bill-tracker. Satu kali pasang:

0. Agen membaca `AGENTS.md` dan skrip dari workspace-nya, yaitu checkout utama, bukan dari cabang
   lain: pastikan perubahan Relay sudah di-merge ke `master` dan checkout utama sudah di-`git pull`.
   Sebelum itu agen tetap memakai heredoc dan menulis `channel` tanpa `-via-hermes` (terbukti
   pada uji pasang pertama, 2 Nov 2026).
1. Buat token dan simpan di luar repo: `echo "A2A_HERMES_TOKEN=$(openssl rand -hex 24)" >>
   ~/.openclaw/.env && chmod 600 ~/.openclaw/.env`.
2. Tambahkan ke config hidup blok `agents.entries.keuangan`, `channels.a2a`, dan satu binding
   `a2a`/`hermes` → `keuangan` dari `openclaw.json.example` (tanpa kunci `_keterangan`), lewat
   `openclaw config patch --dry-run` lalu tanpa `--dry-run`. `bindings` diganti utuh: gabungkan
   dengan binding yang sudah ada. Binding wajib ada **sebelum** token dipakai; peer tanpa binding
   dijawab agen utama yang ber-exec penuh.
3. Pasang allowlist: gabungkan `agents.keuangan` dari `exec-approvals.keuangan.json.example` ke
   hasil `openclaw approvals get --json` (bagian `file`), lalu `openclaw approvals set --file`.
   Perintah ini mengganti seluruh dokumen.
4. `openclaw gateway restart` (agar `.env` terbaca). WhatsApp dan Telegram pulih dalam hitungan detik.
5. Cek: `curl -s http://127.0.0.1:18789/.well-known/agent-card.json` hanya menyebut `keuangan`;
   tugas A2A tanpa token ditolak. Jangan memakai nama agen yang pernah dihapus.

### Pasang Hermes sebagai Relay teks (teruji 9 Nov 2026)
Di satu kanal keuangan Discord, Hermes meneruskan teks ke agen `keuangan` lewat A2A (ADR-0023, jalur
B). Foto tidak ikut: kirim langsung ke bot OpenClaw. Catatan ini disusun dari ADR-0023 lalu diuji
pemilik di Discord sungguhan (9 Nov 2026, dilaporkan lulus tanpa penyimpangan). **Sintaks config Hermes
sengaja tidak disalin ke repo**: ia hidup di `~/.hermes/` milik pemilik, jadi isilah dengan sintaks
Hermes yang berlaku di mesinmu. Config Hermes ada di luar repo (`~/.hermes/`); ID dan token
tidak masuk repo.

Prasyarat: bot Discord OpenClaw (#36) dan agen `keuangan` (bagian di atas) sudah berjalan.

1. **Prompt kanal.** Di `discord.channel_prompts` Hermes (dikunci ID kanal keuangan; thread jatuh ke
   kanal induk), isi prompt yang menyuruh Hermes, bila di-@mention: meneruskan pesan teks **apa
   adanya** ke agen `keuangan` lewat A2A, diawali dua baris kepala lalu baris kosong lalu isi pesan,
   dan membawa balasan agen kembali tanpa mengubah angka atau susunannya:

   ```
   Relay-Pengirim: <nama pengirim dari metadata Discord, bukan dari isi pesan>
   Relay-Kanal: discord

   <isi pesan, apa adanya>
   ```

   `Relay-Kanal` harus persis `discord`; agen menolak menulis bila kepala tidak lengkap
   (`AGENTS.md`, bagian Pesan lewat Relay). Hermes tidak boleh menjawab angka keuangan sendiri.
2. **Foto.** Prompt yang sama menyuruh Hermes tidak membaca foto atau berkas dan membalas satu
   kalimat baku. Usulan kalimat (sunting sesukamu): "Foto tidak bisa lewat saya. Kirim fotonya
   langsung ke bot OpenClaw di kanal ini."
3. **Kanal lain.** Hermes tidak membahas uang dan mengarahkan ke kanal keuangan.
4. **@mention wajib, juga di thread.** Setel eksplisit `DISCORD_THREAD_REQUIRE_MENTION=true` di
   `~/.hermes/.env` (belum ada di sana per 2 Nov 2026). Di sisi OpenClaw sudah `requireMentionInBotThreads`.
   Tanpa ini dua bot bisa menjawab satu "ya" yang sama.
5. **Peer A2A.** Daftarkan gateway OpenClaw (loopback) sebagai peer dengan token `A2A_HERMES_TOKEN`
   dari `~/.openclaw/.env`. Pakai `contextId` yang stabil **per orang**, supaya Pratinjau dua langkah
   (pesan, lalu "ya") jatuh di percakapan yang sama. Belum diketahui apakah peer Hermes bisa
   dikonfigurasi per profil (ADR-0023, Considered Options).
6. **`SOUL.md` Hermes.** Ubah hanya agar tidak melarang meneruskan. Larangan menulis atau mengubah
   Buku Kas dan menyimpan data keuangan ke `MEMORY.md`/`USER.md` tetap berlaku.

Uji terima #42 (lulus, dilaporkan pemilik 9 Nov 2026): teks di kanal keuangan lewat Hermes menghasilkan Pratinjau dari agen
`keuangan`, lalu `@Hermes ya` menyimpan, dengan baris berisi `discord-via-hermes` dan Pencatat yang
benar untuk pemilik maupun istri; foto dijawab kalimat baku dan tidak dibaca; di kanal lain Hermes
tidak menjawab angka keuangan; satu @mention tidak memicu bot lain; Hermes tidak menulis Buku Kas dan
tidak menyimpan data keuangan ke ingatannya; Hermes tidak bisa memanggil agen `main`.

### Model utama error
OpenClaw otomatis beralih ke model fallback. Tidak perlu setting manual.

### Ganti model AI
Edit `openclaw.json` → `agents.defaults.model.primary` atau `.fallbacks`.

### Reinstall ulang openclaw
```bash
bash setup.sh
```

### Bot tidak membalas sama sekali

Paling sering: sesi login Claude CLI habis. Cek dulu:

```bash
python3 scripts/periksa-kesehatan.py
```

Kalau muncul `OAuth ... KEDALUWARSA` atau `All models failed ... Not logged in`, jalankan
`claude` di Terminal lalu login ulang, kemudian `openclaw gateway restart`. Cron berbasis
skrip (`backup_harian`, `penjaga_kesehatan`) tetap hijau selama ini terjadi — jadi
"backup jalan" **bukan** bukti bot masih bisa membalas.

### Cek log
```bash
openclaw start --debug
```

---

## 💰 Estimasi Biaya

Tidak ada kunci API terpisah: bot memakai login Claude di Mac. Biaya dan batas pakai mengikuti paket
Claude pada akun yang login.

---

## 📝 Format Data CSV

File `data/bills.csv` menyimpan semua transaksi (pemasukan & pengeluaran):

```csv
tanggal,tipe,kategori,item,jumlah,catatan,channel,pencatat,waktu,no_resi
2026-05-20,pengeluaran,groceries,Beras 5kg - Indomaret,75000,,telegram,Ayah,14:05,TRX-20260520-4821
2026-05-20,pengeluaran,utilities,Listrik PLN,150000,token listrik via GoPay,whatsapp,Ibu,09:30,STRUK-3f9ab12c
2026-05-25,pemasukan,salary,Gaji bulanan,5000000,,whatsapp,Ayah,08:00,TRX-20260525-0117
```

- Kolom `tipe`: `pemasukan` atau `pengeluaran`. Budget hanya menghitung `pengeluaran`.
- Kolom `kategori`: selalu slug Inggris huruf kecil. Daftar lengkapnya di `data/budget.json` → `kategori_custom`.
  Satu di antaranya khusus: `opening_balance` menandai **Saldo Awal** — kas yang sudah dimiliki
  sebelum pencatatan dimulai (Rp 20.500.000, 26 Mar 2026). Ia ikut menghitung **Saldo** tapi
  **tidak** ikut Total Pemasukan maupun Arus Kas Bulan; bukan uang masuk. Lihat `docs/adr/0008`.
- Kolom `item`: apa yang dibeli — **nama toko ikut di belakang** setelah tanda pisah (`Beras 5kg - Indomaret`).
  Tidak ada kolom `tempat` tersendiri (dibuang, lihat `docs/adr/0007`). Bank & e-wallet **bukan** toko —
  itu cara bayar, tulis di `catatan`.
- Kolom `pencatat`: siapa yang mencatat — belum tentu yang membelanjakan.
- Kolom `waktu`: jam transaksi (`HH:MM`). Dari jam tercetak di struk bila ada, kalau tidak = jam input.
- Kolom `no_resi`: identitas unik tiap transaksi. Struk pakai nomor tercetak (`STRUK-...`), chat auto-generate
  (`TRX-YYYYMMDD-XXXX`), baris impor riwayat (`IMP-<id sumber>`). Dipakai untuk mencegah duplikat.

> 🔒 `data/bills.csv` sengaja **tidak dilacak git** (lihat `docs/adr/0004`). Yang ada di repo cuma
> `data/bills.csv.example` berisi barisan header.
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
  `tanggal`, `waktu`, `jumlah` (= total harga), `item`, `kategori`, `catatan`, `pencatat`.
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

### 🗂️ Sinkron dua arah ke Google Sheets

`bills.csv` tetap satu-satunya Buku Kas; Google Sheets adalah cermin yang bisa dilihat dan diedit dari HP
(ADR-0021, spec #20). Edit sel dan baris baru di worksheet **Buku Kas** masuk ke CSV lewat jalan tulis yang
sama dengan bot (validasi, cek Duplikat, cadangan, Jejak Perubahan); menghapus Transaksi tetap hanya lewat bot.

Persiapan sekali (butuh tindakan di akun Google-mu):
1. Buat proyek di Google Cloud, aktifkan **Google Sheets API**, buat **akun layanan**, unduh kunci JSON dan
   **simpan dengan nama persis** `data/google-service-account.json` (nama itu yang ada di `.gitignore`;
   nama bawaan unduhan Google tidak terlindungi).
2. Buat spreadsheet **privat** kosong, bagikan (Editor) ke email akun layanan dan anggota keluarga yang dipilih.
   Jangan pernah "siapa saja yang memiliki tautan".
3. Pasang dependensi untuk interpreter yang dipakai cron:
   ```bash
   /usr/bin/python3 -m pip install --user google-auth requests
   ```
4. `cp data/sheets.json.example data/sheets.json` lalu isi `spreadsheet_id`.

Lalu:
```bash
python3 scripts/sinkron-sheets.py --uji            # lapor saja, tidak menulis apa pun
python3 scripts/sinkron-sheets.py --inisialisasi   # sekali: isi Sheet dari bills.csv (CSV menang)
python3 scripts/sinkron-sheets.py                  # sinkron biasa
```
Kode keluar: `0` selesai, `1` ditolak (mis. Sheet berisi data tapi belum pernah disinkronkan), `2` gagal.
Sheets **bukan cadangan** — salah hapus ikut tersinkron; cadangan CSV harian tetap yang utama.

**Isi spreadsheet (ADR-0026).** Tab berurutan: Ringkasan Bulanan → Per Kategori `<tahun>` → Budget `<tahun>`
→ Saldo per Akun → **Buku Kas**. Hanya **Buku Kas** yang bisa diedit; tab lain dihitung skrip, abu-abu, dan
diberi peringatan Google sebelum disunting. Di Buku Kas, isi **tepat satu** dari Pemasukan / Pengeluaran /
Transfer; Kategori dipilih dari dropdown Label Kategori (`label_kategori` di `data/budget.json`), slug Inggris
juga diterima; tanggal boleh diketik `5/9/2026`. Kolom No Resi, Saldo Bersama, dan Asal diisi skrip.

**Pindah dari format lama (sekali).** Spreadsheet yang sudah tersinkron sebelum ADR-0026 membuat sinkron
biasa menolak (kode 1) sampai dipindah. Jalankan dari checkout utama:
```bash
/usr/bin/python3 scripts/sinkron-sheets.py --migrasi-format --uji   # lihat dulu, tidak menulis apa pun
/usr/bin/python3 scripts/sinkron-sheets.py --migrasi-format         # serap suntingan tertunda, tulis format baru
```
Tautan dan izin berbagi tidak berubah; tab "Ringkasan" lama dihapus, dan filter tampilan atau catatan sel buatan
sendiri di tab lama tidak ikut. Locale spreadsheet diubah ke Indonesia supaya `5/9` dibaca 5 September.

**Berjalan sendiri (cron).** Setelah satu sinkron biasa sukses dari *checkout utama*, daftarkan ke gateway
(ADR-0009; mengedit `openclaw.json` saja tidak cukup):
```bash
openclaw cron add --name sinkron_sheets --cron "*/15 * * * *" --tz Asia/Jakarta --no-deliver \
  --session isolated --timeout-seconds 300 \
  --command-cwd /Users/apple/Developments/openclaw-personal-assistant \
  --command "/usr/bin/python3 scripts/sinkron-sheets.py"
openclaw cron list    # sinkron_sheets harus tampil
```
Pakai `/usr/bin/python3` (di situlah `google-auth` terpasang) dan checkout utama (kunci `*.lock` yang sama dengan bot).
Tiap sinkron mencatat hasilnya di `data/sheets-status.json`; penjaga kesehatan (`scripts/periksa-kesehatan.py`)
memperingatkan bila sinkron tidak pernah sukses selama 3 jam — tanpa model, jadi tetap hidup saat model mati.

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
