# Keuangan terjangkau dari semua Kanal; Hermes hanya Relay teks ke agen terbatas

> **Memperluas** [0005](0005-bill-tracker-sebagai-sistem-resmi.md) (bill-tracker satu-satunya
> sistem) dan [0016](0016-pratinjau-sebelum-simpan-untuk-semua-pencatatan.md)/
> [0018](0018-ubah-hapus-lewat-skrip-copy-lalu-ganti.md) (Pratinjau untuk semua perubahan).
> Riset dasarnya: `docs/research/openclaw-hermes-integrasi.md` (31 Okt 2026).

Pemilik ingin data keuangan bisa dijangkau dari WhatsApp, Telegram, dan Discord, oleh pemilik
dan istri, termasuk mencatat, mengubah, dan menghapus. Hermes (model gratis, tanpa kontrak
Pratinjau, repo dan `bills.csv` tidak dipasang di Docker-nya, `SOUL.md` melarangnya menyentuh
data keuangan) sudah memegang Discord dan satu bot Telegram, sedangkan OpenClaw memegang
WhatsApp dan bot Telegram yang lain. Kedua agen **tidak digabung**: keuangan tetap hanya hidup
di OpenClaw, dan semua Kanal membaca serta menulis `bills.csv` yang sama lewat skrip yang sama.

## Keputusan

- **Jalur A, langsung.** OpenClaw memegang WhatsApp, Telegram, dan Discord (bot Discord baru,
  token baru; satu kanal privat bersama dengan Hermes). Semua kemampuan ada di sini, termasuk
  foto struk dan Bukti Transfer. Agen `main` melayani.
- **Jalur B, Relay Hermes, hanya Discord dan hanya teks.** Di kanal keuangan Discord, prompt
  kanal menyuruh Hermes meneruskan pesan apa adanya ke OpenClaw lewat A2A. Lokasi, bukan
  penilaian model, yang menentukan sebuah pesan itu urusan uang. Di tempat lain Hermes tidak
  membahas uang. Telegram tidak ikut jalur B. Foto tidak diteruskan (A2A OpenClaw hanya
  menerima teks dan JSON); Hermes menjawab "kirim fotonya ke bot OpenClaw".
- **Agen `keuangan` terpisah** menerima Relay: workspace dan `AGENTS.md` yang sama dengan `main`
  tetapi alatnya dibatasi ke skrip bill-tracker dan pembacaan berkas. Tugas A2A mewarisi alat
  agen tujuannya, dan `main` jalan dengan `bypassPermissions`; model gratis tidak boleh
  berada di depan izin sepenuh itu.
- **Pencatat pada Relay hanya klaim.** Satu peer `hermes`; nama pengirim ikut di teks, jadi
  identitasnya diklaim model Hermes. Tidak ada pagar tambahan di skrip: Pratinjau menampilkan
  nama Pembeli dan menunggu jawaban (ADR-0015/0016). Baris Relay ditandai di kolom `channel`
  (`discord-via-hermes`), diisi agen `keuangan` dari teks Relay, bukan oleh Hermes, supaya baris
  yang identitasnya lebih lemah bisa disaring dan diperiksa.
- **Di Discord tiap pesan wajib @mention bot yang dituju**, termasuk "ya" atas Pratinjau.
  Hermes memakai `DISCORD_THREAD_REQUIRE_MENTION=true`, OpenClaw `requireMentionInBotThreads:
  true`. Tanpa itu dua bot bisa menjawab satu "ya" yang sama.
- **Laporan otomatis** (Mingguan, Bulanan, cek budget malam) dikirim ke WhatsApp, Telegram, dan
  Discord; tiap tujuan dicoba terpisah supaya kegagalan satu kanal tidak menggagalkan yang
  lain. Penjaga kesehatan (ADR-0011) tidak berubah.
- **Percakapan tidak disatukan lintas Kanal** (`session.identityLinks` tidak dipakai): data
  keuangan sudah bersama lewat CSV, dan Pratinjau dikonfirmasi di Kanal tempat ia dimulai.

## Considered Options

- **Hermes menjalankan skrip sendiri** (repo dipasang, skill `bill-tracker` diaktifkan lagi):
  ditolak. Kontrak Pratinjau harus disalin ke agen yang modelnya lebih lemah, dan itu satu-satunya
  pagar percakapan; pagar data (sidik, validasi, cadangan) ada di skrip, tapi kepatuhan
  Pratinjau hanya dijaga prompt.
- **Relay oleh penilaian model Hermes** (toolset `a2a` aktif di semua profil, model memutuskan
  mana yang urusan uang): ditolak. Model gratis bisa lupa meneruskan atau menjawab angka
  sendiri; lokasi lebih mudah dipatuhi dan kegagalannya terlihat.
- **Foto diteruskan lewat folder bersama atau dibaca Hermes:** ditolak. Folder lintas agen belum
  teruji, dan membaca angka struk adalah pencatatan yang paling rawan salah baca.
- **Satu peer A2A per orang** (identitas dari token): lebih kuat, tidak dipilih. Pemilik menerima
  risiko identitas-klaim dengan Pratinjau sebagai pengaman, dan belum terverifikasi bahwa
  konfigurasi peer A2A Hermes bisa berbeda per profil.
- **Menggabungkan atau memindahkan agen**, memasang Honcho, menyatukan sesi dengan
  `identityLinks`: tidak dilakukan; lihat riset untuk alasannya.

## Consequences

Data keuangan kini bisa tampak di Discord dan di sesi Hermes (`session_search`, `state.db`).
Itu disengaja oleh pemilik. `SOUL.md` Hermes tetap berlaku: Hermes tidak menulis `bills.csv` dan
tidak menyimpan data keuangan ke `MEMORY.md`; ia hanya meneruskan.

Pencatat pada baris `*-via-hermes` bisa salah (mis. transaksi istri tercatat atas pemilik) kalau
Pratinjau tidak diperhatikan. Penyaringan lewat kolom `channel` adalah satu-satunya jejaknya.

Pelaksanaan pengiriman laporan (#39, 1 Nov 2026): config OpenClaw hanya menyimpan nomor
WhatsApp, tidak ada ID tujuan Telegram atau Discord, jadi ID itu dibaca dari `data/tujuan.json`
(di luar git, ADR-0004; bentuknya di `data/tujuan.json.example`). Memakai
`channels.telegram.allowFrom` ditolak karena kunci itu juga menentukan siapa boleh mengirim DM
ke bot yang sedang hidup. Waktu terburuk satu pengiriman: WhatsApp ±300 detik (3 percobaan,
batas 60 detik, 2 jeda 60 detik), sedangkan ketiga cron laporan berbatas 420 detik. Bila semua
tujuan diulang 3 kali, dua tujuan saja (2 x 300) sudah terpotong; karena itu hanya WhatsApp yang
diulang dan Telegram serta Discord sekali coba (±60 detik terburuk masing-masing). Total
terburuk tiga tujuan jadi ±420 detik: tepat di batas, tanpa margin untuk waktu mulai proses dan
penyusunan laporan. Maka batas cron `laporan_mingguan`, `laporan_bulanan`, dan
`cek_budget_malam` dinaikkan ke 600 detik di cron hidup pada 1 Nov 2026 (`openclaw cron edit
--timeout-seconds 600`; `penjaga_kesehatan` tetap 420). Ini harus mendahului pengisian
`data/tujuan.json`.

Peringatan penjaga kesehatan (`periksa-kesehatan.py`, ADR-0011) tetap hanya ke WhatsApp: ia
sengaja punya `tujuan_baku` sendiri supaya berdiri sendiri, jadi tidak ikut Telegram atau Discord.

Perlu diverifikasi saat membangun, karena baru dugaan di riset: pembatasan alat per agen di
OpenClaw dan berbagi `AGENTS.md` antara dua agen (bila gagal, Relay jatuh ke `main` sebagai risiko
yang diterima dan dicatat ulang di sini); `channel_prompts` Hermes untuk Discord; izin kanal
Discord hanya untuk pemilik dan istri (isi `bills.csv` memuat gaji). Urutan pembangunan: Jalur A
dulu (bot Discord OpenClaw, tujuan laporan tambahan), lalu Jalur B.
