# Lembar daftar periksa uji hidup (#36, #38, #39, #41, #42, #43)

Disusun dari isi issue, README, dan ADR-0023 per 9 Nov 2026. Jalankan berurutan; urutannya mengikuti
ketergantungan antar issue. Centang dengan bukti singkat, **tanpa data pribadi** (jangan salin ID, token,
nominal, atau nama toko). Penyimpangan menjadi issue baru, bukan ditambal diam-diam (#43).

Catatan kejujuran: perintah di bawah saya cocokkan dengan `--help` skrip di repo. Perintah `openclaw`
dan isi config Hermes **tidak bisa saya jalankan dari sesi cloud**, jadi bagian itu mengikuti README/ADR
dan belum saya coba.

**Status 9 Nov 2026:** pemilik melaporkan semua butir lulus tanpa penyimpangan. Bukti per butir tidak
dilampirkan di berkas ini (sesuai aturan tanpa data pribadi); centang di bawah mencatat laporan itu,
bukan hasil yang saya amati sendiri.

---

## 0. Prasyarat (sekali)

- [x] `PR #60` (catatan Hermes) sudah tergabung dan checkout utama di Mac sudah `git pull`
      (agen membaca `AGENTS.md` dan skrip dari checkout utama).
- [x] `openclaw channels status` menyebut Discord tersambung.
- [x] Kanal keuangan privat: hanya kamu, istri, dan bot yang punya izin *View Channel*. Periksa juga peran
      *Administrator* di server (peran itu tetap melihat semua kanal; isi Buku Kas memuat gaji).

## 1. #36 Bot OpenClaw di Discord (sebagian sudah teruji 2 Nov)

Sudah teruji: bot diam tanpa @mention; catat → Pratinjau → ya → tersimpan (`channel` `discord`);
duplikat terdeteksi. Yang belum:

- [x] Wajib @mention di **thread**, termasuk jawaban "ya" atas Pratinjau.
- [x] `@bot cari …` menemukan baris yang tadi dicatat
      (`python3 scripts/buku.py cari --terakhir --batas 1` di Mac sebagai pembanding).
- [x] Foto struk lewat Discord dicatat dengan Pratinjau, sama seperti di WhatsApp.
- [x] Pengguna lain (akun uji bila ada) diabaikan; kanal lain diabaikan.
- [x] Pembeli istri tercatat atas namanya, bukan namamu (alias lewat `data/pembeli.json`).
- [x] Pesan tanpa @mention tidak ikut jadi konteks Pratinjau berikutnya (`historyLimit: 0`).
- [x] WhatsApp, Telegram, dan bot helpdesk berperilaku seperti sebelumnya.

## 2. #39 Laporan ke banyak tujuan

Sebelum mengisi `data/tujuan.json`, pastikan batas waktu tiga cron laporan sudah 600 detik
(`openclaw cron edit … --timeout-seconds 600`, README bagian laporan otomatis).

- [x] Laporan Mingguan tiba di **WhatsApp dan Telegram**:
      `python3 scripts/laporan-mingguan.py --kirim` (tanpa efek simpan; aman diulang).
- [x] Cek budget tiba bila ada isi, dan diam bila tidak ada: `python3 scripts/check-bills.py --mode all --kirim` (sama dengan cron `cek_budget_malam`).
- [x] Laporan Bulanan: `python3 scripts/laporan-bulanan.py --kirim` **menyimpan angka yang dilaporkan**
      (dasar Koreksi bulan berikutnya). Jalankan hanya untuk bulan yang memang akan dilaporkan.
      Saya tidak yakin apakah `--ke KANAL:TUJUAN` melewati penyimpanan; jangan mengandalkannya, baca
      `scripts/laporan-bulanan.py` dulu.

## 3. #41 Laporan sampai ke Discord

- [x] `data/tujuan.json` berisi `discord` (bentuk di `data/tujuan.json.example`; berkas ini di luar git).
- [x] Mingguan, Bulanan (mode kirim), dan cek budget (saat ada isi) tiba di kanal Discord.
- [x] Matikan **satu Kanal bergantian** (WhatsApp, lalu Telegram, lalu Discord): dua lainnya tetap menerima
      dan skrip keluar dengan kode 1. Cek kode keluar: `echo $?` tepat setelah perintah `--kirim`.
- [x] Semua Kanal mati: angka Laporan Bulanan tidak tersimpan, kode keluar 1.

## 4. #38 dan #42 Relay Hermes

Pasang dulu sesuai README ("Pasang Hermes sebagai Relay teks"). Sintaks config Hermes **belum teruji**.

- [x] (#38 butir 3) `discord.channel_prompts` benar-benar berlaku di Discord sungguhan; thread jatuh ke kanal induk.
- [x] Teks di kanal keuangan lewat Hermes menghasilkan Pratinjau dari agen `keuangan`.
- [x] `@Hermes ya` menyimpan; baris berisi `discord-via-hermes` dan Pencatat benar (kamu **dan** istri).
- [x] Pratinjau dua langkah berlanjut di percakapan yang sama (`contextId` stabil per orang).
- [x] "ya" dari pengirim lain **tidak** menyimpan (agen menanyakan siapa).
- [x] Kepala Relay tidak lengkap atau `Relay-Kanal` bukan `discord`: tidak ada yang ditulis, dan jawaban
      persis `⚠️ Kepala Relay tidak lengkap, tidak ada yang dicatat.`
- [x] Foto di kanal keuangan dijawab kalimat baku dan tidak dibaca.
- [x] Di kanal lain Hermes tidak menjawab angka keuangan dan mengarahkan ke kanal keuangan.
- [x] Satu @mention tidak memicu bot lain; satu "ya" tidak dijawab dua bot
      (`DISCORD_THREAD_REQUIRE_MENTION=true` disetel).
- [x] Agen `keuangan` menolak perintah di luar skrip bill-tracker.
- [x] Hermes tidak dapat memanggil agen `main` (peer `hermes` terikat ke `keuangan` sebelum tokennya dipakai).
- [x] Hermes tidak menulis `bills.csv` dan tidak menyimpan data keuangan ke `MEMORY.md`/`USER.md`.
- [x] `curl -s http://127.0.0.1:18789/.well-known/agent-card.json` hanya menyebut `keuangan`;
      tugas A2A tanpa token ditolak.
- [x] Model agen `keuangan` adalah Sonnet (Haiku terbukti tidak memanggil alat, 2 Nov).

## 5. #43 Penutup

- [x] Setiap butir di atas dicentang dengan bukti singkat tanpa data pribadi.
- [x] README, `AGENTS.md`, `CONTEXT.md`, ADR-0023 mutakhir; ubah "Status" spek 0004 sesuai kenyataan.
- [x] Kirim hasilnya ke saya: saya perbarui README/ADR dan komentar di tiap issue, lalu kamu menutup issue
      yang acceptance-nya lengkap.
