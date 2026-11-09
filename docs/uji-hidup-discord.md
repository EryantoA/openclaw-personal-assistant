# Lembar daftar periksa uji hidup (#36, #38, #39, #41, #42, #43)

Disusun dari isi issue, README, dan ADR-0023 per 9 Nov 2026. Jalankan berurutan; urutannya mengikuti
ketergantungan antar issue. Centang dengan bukti singkat, **tanpa data pribadi** (jangan salin ID, token,
nominal, atau nama toko). Penyimpangan menjadi issue baru, bukan ditambal diam-diam (#43).

Catatan kejujuran: perintah di bawah saya cocokkan dengan `--help` skrip di repo. Perintah `openclaw`
dan isi config Hermes **tidak bisa saya jalankan dari sesi cloud**, jadi bagian itu mengikuti README/ADR
dan belum saya coba.

---

## 0. Prasyarat (sekali)

- [ ] `PR #60` (catatan Hermes) sudah tergabung dan checkout utama di Mac sudah `git pull`
      (agen membaca `AGENTS.md` dan skrip dari checkout utama).
- [ ] `openclaw channels status` menyebut Discord tersambung.
- [ ] Kanal keuangan privat: hanya kamu, istri, dan bot yang punya izin *View Channel*. Periksa juga peran
      *Administrator* di server (peran itu tetap melihat semua kanal; isi Buku Kas memuat gaji).

## 1. #36 Bot OpenClaw di Discord (sebagian sudah teruji 2 Nov)

Sudah teruji: bot diam tanpa @mention; catat → Pratinjau → ya → tersimpan (`channel` `discord`);
duplikat terdeteksi. Yang belum:

- [ ] Wajib @mention di **thread**, termasuk jawaban "ya" atas Pratinjau.
- [ ] `@bot cari …` menemukan baris yang tadi dicatat
      (`python3 scripts/buku.py cari --terakhir --batas 1` di Mac sebagai pembanding).
- [ ] Foto struk lewat Discord dicatat dengan Pratinjau, sama seperti di WhatsApp.
- [ ] Pengguna lain (akun uji bila ada) diabaikan; kanal lain diabaikan.
- [ ] Pembeli istri tercatat atas namanya, bukan namamu (alias lewat `data/pembeli.json`).
- [ ] Pesan tanpa @mention tidak ikut jadi konteks Pratinjau berikutnya (`historyLimit: 0`).
- [ ] WhatsApp, Telegram, dan bot helpdesk berperilaku seperti sebelumnya.

## 2. #39 Laporan ke banyak tujuan

Sebelum mengisi `data/tujuan.json`, pastikan batas waktu tiga cron laporan sudah 600 detik
(`openclaw cron edit … --timeout-seconds 600`, README bagian laporan otomatis).

- [ ] Laporan Mingguan tiba di **WhatsApp dan Telegram**:
      `python3 scripts/laporan-mingguan.py --kirim` (tanpa efek simpan; aman diulang).
- [ ] Cek budget tiba bila ada isi, dan diam bila tidak ada: `python3 scripts/check-bills.py --mode all --kirim` (sama dengan cron `cek_budget_malam`).
- [ ] Laporan Bulanan: `python3 scripts/laporan-bulanan.py --kirim` **menyimpan angka yang dilaporkan**
      (dasar Koreksi bulan berikutnya). Jalankan hanya untuk bulan yang memang akan dilaporkan.
      Saya tidak yakin apakah `--ke KANAL:TUJUAN` melewati penyimpanan; jangan mengandalkannya, baca
      `scripts/laporan-bulanan.py` dulu.

## 3. #41 Laporan sampai ke Discord

- [ ] `data/tujuan.json` berisi `discord` (bentuk di `data/tujuan.json.example`; berkas ini di luar git).
- [ ] Mingguan, Bulanan (mode kirim), dan cek budget (saat ada isi) tiba di kanal Discord.
- [ ] Matikan **satu Kanal bergantian** (WhatsApp, lalu Telegram, lalu Discord): dua lainnya tetap menerima
      dan skrip keluar dengan kode 1. Cek kode keluar: `echo $?` tepat setelah perintah `--kirim`.
- [ ] Semua Kanal mati: angka Laporan Bulanan tidak tersimpan, kode keluar 1.

## 4. #38 dan #42 Relay Hermes

Pasang dulu sesuai README ("Pasang Hermes sebagai Relay teks"). Sintaks config Hermes **belum teruji**.

- [ ] (#38 butir 3) `discord.channel_prompts` benar-benar berlaku di Discord sungguhan; thread jatuh ke kanal induk.
- [ ] Teks di kanal keuangan lewat Hermes menghasilkan Pratinjau dari agen `keuangan`.
- [ ] `@Hermes ya` menyimpan; baris berisi `discord-via-hermes` dan Pencatat benar (kamu **dan** istri).
- [ ] Pratinjau dua langkah berlanjut di percakapan yang sama (`contextId` stabil per orang).
- [ ] "ya" dari pengirim lain **tidak** menyimpan (agen menanyakan siapa).
- [ ] Kepala Relay tidak lengkap atau `Relay-Kanal` bukan `discord`: tidak ada yang ditulis, dan jawaban
      persis `⚠️ Kepala Relay tidak lengkap, tidak ada yang dicatat.`
- [ ] Foto di kanal keuangan dijawab kalimat baku dan tidak dibaca.
- [ ] Di kanal lain Hermes tidak menjawab angka keuangan dan mengarahkan ke kanal keuangan.
- [ ] Satu @mention tidak memicu bot lain; satu "ya" tidak dijawab dua bot
      (`DISCORD_THREAD_REQUIRE_MENTION=true` disetel).
- [ ] Agen `keuangan` menolak perintah di luar skrip bill-tracker.
- [ ] Hermes tidak dapat memanggil agen `main` (peer `hermes` terikat ke `keuangan` sebelum tokennya dipakai).
- [ ] Hermes tidak menulis `bills.csv` dan tidak menyimpan data keuangan ke `MEMORY.md`/`USER.md`.
- [ ] `curl -s http://127.0.0.1:18789/.well-known/agent-card.json` hanya menyebut `keuangan`;
      tugas A2A tanpa token ditolak.
- [ ] Model agen `keuangan` adalah Sonnet (Haiku terbukti tidak memanggil alat, 2 Nov).

## 5. #43 Penutup

- [ ] Setiap butir di atas dicentang dengan bukti singkat tanpa data pribadi.
- [ ] README, `AGENTS.md`, `CONTEXT.md`, ADR-0023 mutakhir; ubah "Status" spek 0004 sesuai kenyataan.
- [ ] Kirim hasilnya ke saya: saya perbarui README/ADR dan komentar di tiap issue, lalu kamu menutup issue
      yang acceptance-nya lengkap.
