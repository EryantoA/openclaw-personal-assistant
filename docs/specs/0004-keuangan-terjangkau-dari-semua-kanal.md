# Spec: Keuangan terjangkau dari semua Kanal

Status: dilaksanakan; uji terima manual lulus (dilaporkan pemilik, 9 Nov 2026). Turunan dari [ADR-0023](../adr/0023-keuangan-terjangkau-dari-semua-kanal-hermes-hanya-relay-teks.md),
dan memperluas [ADR-0005](../adr/0005-bill-tracker-sebagai-sistem-resmi.md),
[ADR-0012](../adr/0012-laporan-bulanan-dihitung-skrip-dikirim-tanggal-6.md),
[ADR-0013](../adr/0013-laporan-mingguan-dihitung-skrip-dikirim-senin.md),
[ADR-0016](../adr/0016-pratinjau-sebelum-simpan-untuk-semua-pencatatan.md),
[ADR-0018](../adr/0018-ubah-hapus-lewat-skrip-copy-lalu-ganti.md). Dasar faktanya ada di
`docs/research/openclaw-hermes-integrasi.md`. Istilah **Kanal**, **Relay**, dan **Asal** mengikuti
`CONTEXT.md`.

## Problem Statement

Keluarga ini memakai dua asisten di Mac yang sama dan mereka tidak berbagi apa-apa. OpenClaw
memegang WhatsApp dan satu bot Telegram, dan hanya di sana Buku Kas bisa ditanya atau diisi.
Hermes memegang Discord dan bot Telegram yang lain; di sana keuangan sengaja tertutup (tidak
punya kontrak Pratinjau, repo tidak terpasang, `SOUL.md` melarangnya menyentuh uang).

Akibatnya, kalau pemilik atau istri sedang di Discord atau di bot Telegram Hermes, mereka tidak
bisa menanyakan Saldo, mencatat belanja, atau mengubah Transaksi, dan harus pindah ke WhatsApp.
Laporan otomatis (Mingguan, Bulanan, cek budget) juga hanya sampai ke WhatsApp, kanal yang
paling rapuh: sesinya logout tiap 2–3 minggu dan kirim dari cron gagal acak. Saat WhatsApp mati,
laporan tidak sampai ke mana pun.

## Solution

Buku Kas yang sama bisa dijangkau dari WhatsApp, Telegram, dan Discord, oleh pemilik dan istri,
dengan semua jaminan yang sudah ada (Pratinjau, validasi skrip, kunci berkas, cadangan, Jejak
Perubahan).

- **Jalur langsung.** OpenClaw memegang ketiga Kanal, termasuk bot Discord baru. Di sini semuanya
  bisa: tanya, catat, ubah, hapus, foto struk, Bukti Transfer.
- **Jalur Relay.** Di satu kanal keuangan Discord, orang juga bisa mengajak bot Hermes. Hermes
  meneruskan teks apa adanya ke agen keuangan OpenClaw dan membawa jawabannya kembali. Hanya
  teks; foto harus dikirim ke bot OpenClaw.
- **Laporan** dikirim ke ketiga Kanal, dan kegagalan satu Kanal tidak menggagalkan yang lain.

Tidak ada penyatuan percakapan lintas Kanal. Yang bersama adalah Buku Kas, bukan sesi.

## User Stories

1. Sebagai pemilik, saya ingin bertanya "Saldo berapa?" di Discord, supaya saya tidak perlu
   pindah ke WhatsApp hanya untuk melihat angka.
2. Sebagai istri, saya ingin bertanya dan mencatat dari Telegram atau Discord, supaya saya tidak
   bergantung pada satu aplikasi.
3. Sebagai pemilik, saya ingin mencatat Pengeluaran dengan mengetik di Discord, supaya belanja
   yang baru saya ingat tercatat saat itu juga.
4. Sebagai pemilik, saya ingin tiap pencatatan dari Discord tetap melewati Pratinjau dan menunggu
   jawaban saya, supaya salah ketik tidak langsung masuk Buku Kas.
5. Sebagai pemilik, saya ingin mengubah dan menghapus Transaksi dari Discord dengan tampilan
   sebelum → sesudah, supaya perbaikan sama amannya dengan di WhatsApp.
6. Sebagai pemilik, saya ingin mengirim foto struk ke bot OpenClaw di Discord atau Telegram,
   supaya pencatatan lewat foto tidak hanya bisa di WhatsApp.
7. Sebagai pemilik, saya ingin mengirim Bukti Transfer lewat Kanal mana pun yang dipegang
   OpenClaw, supaya aturan akun dan Arah (ADR-0014) berlaku sama.
8. Sebagai pemilik, saya ingin bot Hermes menjawab "kirim fotonya ke bot OpenClaw" kalau saya
   mengirim foto di kanal keuangan, supaya saya tahu itu bukan error.
9. Sebagai pemilik, saya ingin Hermes meneruskan semua pesan di kanal keuangan Discord tanpa
   menilai isinya, supaya tidak ada pesan uang yang dijawab Hermes sendiri dengan angka karangan.
10. Sebagai pemilik, saya ingin Hermes tidak membahas uang di kanal lain dan menyuruh saya ke
    kanal keuangan, supaya angka tidak pernah muncul dari model yang lemah.
11. Sebagai pemilik, saya ingin tahu persis bot mana yang saya ajak bicara dengan menyebutnya
    (@mention), supaya dua bot di satu kanal tidak menjawab bersamaan.
12. Sebagai pemilik, saya ingin menjawab Pratinjau dengan `@bot ya`, supaya "ya" saya tidak
    ditangkap bot yang salah.
13. Sebagai pemilik, saya ingin Pratinjau yang dimulai di satu Kanal dikonfirmasi di Kanal yang
    sama, supaya tidak ada keadaan setengah jadi yang menggantung di Kanal lain.
14. Sebagai pemilik, saya ingin pesan yang lewat Relay dicatat dengan Asal `discord-via-hermes`,
    supaya saya bisa menyaring baris yang identitas Pencatat-nya hanya klaim.
15. Sebagai pemilik, saya ingin melihat nama Pembeli di Pratinjau Relay, supaya salah nama
    ketahuan sebelum tersimpan.
16. Sebagai istri, saya ingin Transaksi saya dari Discord tercatat atas nama saya, bukan atas
    nama pemilik.
17. Sebagai pemilik, saya ingin pesan Relay tanpa nama pengirim ditolak untuk menulis, supaya
    tidak ada baris dengan Pencatat kosong atau tertebak.
18. Sebagai pemilik, saya ingin pertanyaan baca saja (Saldo, laporan, cari Transaksi) tetap
    dijawab walau header Relay tidak lengkap, supaya kerusakan format tidak menutup akses baca.
19. Sebagai pemilik, saya ingin agen yang menerima Relay tidak bisa menjalankan perintah bebas
    atau membuka web, supaya model gratis tidak berada di depan izin penuh.
20. Sebagai pemilik, saya ingin agen utama saya tidak bisa dipanggil langsung oleh Hermes,
    supaya jangkauan Hermes sempit.
21. Sebagai pemilik, saya ingin percakapan Relay saya berlanjut antar pesan, supaya Pratinjau
    dua langkah bisa diselesaikan lewat Hermes.
22. Sebagai pemilik, saya ingin Laporan Mingguan sampai di WhatsApp, Telegram, dan Discord, supaya
    saya tetap menerimanya saat WhatsApp logout.
23. Sebagai pemilik, saya ingin Laporan Bulanan sampai ke ketiga Kanal, supaya Koreksi bulan
    berikutnya tidak hilang hanya karena satu Kanal gagal.
24. Sebagai pemilik, saya ingin pengecekan budget malam mengirim ke semua Kanal hanya saat ada
    yang perlu ditindak, seperti sekarang.
25. Sebagai pemilik, saya ingin kegagalan satu Kanal tidak menghentikan pengiriman ke Kanal
    lain, supaya satu gangguan tidak membisukan semuanya.
26. Sebagai pemilik, saya ingin angka Laporan Bulanan tersimpan selama minimal satu tujuan
    menerimanya, supaya satu Kanal yang mati tidak mengacaukan Koreksi.
27. Sebagai pemilik, saya ingin tetap tahu bila ada tujuan yang gagal (kode keluar bukan 0),
    supaya penjaga kesehatan dan saya bisa memperbaikinya.
28. Sebagai pemilik, saya ingin satu tujuan yang tidak punya konfigurasi dilewati dengan pesan
    jelas, supaya pengiriman ke Kanal lain tidak ikut mati.
29. Sebagai pemilik, saya ingin kanal keuangan Discord hanya bisa dilihat saya dan istri, supaya
    gaji dan saldo keluarga tidak terbuka ke anggota server lain.
30. Sebagai pemilik, saya ingin hanya saya dan istri yang bisa memerintah bot keuangan di
    Discord dan Telegram, supaya orang lain tidak bisa mencatat atau menghapus.
31. Sebagai pemilik, saya ingin bot Discord OpenClaw memakai token sendiri, supaya tidak
    bertabrakan dengan bot Hermes yang sudah ada.
32. Sebagai pemilik, saya ingin token dan ID Kanal tidak pernah masuk repo, supaya data pribadi
    keluarga tidak bocor (ADR-0004).
33. Sebagai pemilik, saya ingin Hermes tetap tidak menulis Buku Kas dan tidak menyimpan data
    keuangan ke ingatannya, supaya batas di `SOUL.md` tetap benar.
34. Sebagai pemilik, saya ingin WhatsApp dan Telegram OpenClaw berjalan seperti sebelumnya tanpa
    perubahan perilaku, supaya perluasan ini tidak merusak yang sudah dipakai.
35. Sebagai pemilik, saya ingin bot helpdesk FH UIR tidak terpengaruh, supaya mahasiswa yang
    memakainya tidak terganggu.
36. Sebagai pengembang, saya ingin ada daftar uji terima manual untuk bagian yang tidak bisa
    diuji otomatis, supaya pemasangan Discord, A2A, dan prompt kanal bisa diverifikasi tanpa
    menebak.
37. Sebagai pengembang, saya ingin kontrak Relay tertulis di `AGENTS.md` dan dijaga tes kontrak,
    supaya perubahan prompt yang melemahkannya langsung terlihat.
38. Sebagai pemilik, saya ingin ada catatan jelas kalau pembatasan alat per agen ternyata tidak
    mungkin, supaya risiko yang saya terima tercatat, bukan tersembunyi.

## Implementation Decisions

**Dua jalur, satu Buku Kas.** Semua pencatatan, ubah, dan hapus tetap lewat skrip yang ada.
Tidak ada skema CSV yang berubah, tidak ada skrip baru untuk menulis. Kolom `channel` tetap
string bebas; nilai baru yang muncul hanya `discord` (jalur langsung) dan `discord-via-hermes`
(Relay, yang hanya ada di Discord). `telegram` dan `whatsapp` sudah ada.

**Jalur langsung (A).**
- OpenClaw mendapat Kanal Discord dengan bot baru dan token baru, terpisah dari token Hermes.
  Token berada di config gateway, bukan di repo.
- Akses Discord dibatasi lewat daftar izin server dan kanal (allowlist), ke kanal keuangan
  bersama dan DM, hanya untuk pemilik dan istri.
- Bot Telegram OpenClaw yang sudah ada dipakai apa adanya; yang berubah hanya bahwa ia dipakai
  juga untuk keuangan dan menerima laporan.
- Agen `main` melayani semua pesan di jalur ini. Kontrak percakapan di `AGENTS.md` berlaku apa
  adanya, termasuk Pratinjau, `--uji`, sidik, dan balasan baku.
- Sesi tetap per Kanal dan per pengirim; penyatuan lintas Kanal tidak dipakai.

**Jalur Relay (B), hanya Discord, hanya teks.**
- Di kanal keuangan Discord, Hermes dikonfigurasi lewat prompt kanal untuk meneruskan setiap
  pesan yang menyebutnya, apa adanya, ke OpenClaw lewat A2A, dan mengembalikan balasan agen
  tanpa mengubahnya. Hermes tidak menilai isi; lokasi yang menentukan.
- Di semua tempat lain Hermes tidak membahas uang dan mengarahkan ke kanal keuangan.
- Hermes membungkus pesan dengan dua baris kepala: pengirim (nama dari metadata pesan Discord,
  bukan dari isi) dan Kanal asal. Isi pesan pengguna menyusul tanpa diubah.
- Setiap orang punya `contextId` A2A yang stabil, supaya Pratinjau dua langkah bisa diselesaikan
  di pesan berikutnya.
- Foto dan berkas tidak diteruskan. Hermes menjawab dengan satu kalimat baku yang menyuruh
  mengirim fotonya ke bot OpenClaw.
- Hermes tetap tidak menulis Buku Kas dan tidak menyimpan data keuangan ke ingatan permanen
  (`MEMORY.md`/`USER.md`); `SOUL.md` Hermes disesuaikan hanya agar tidak melarang meneruskan.
- Di Discord, bot Hermes dan OpenClaw sama-sama wajib di-@mention, juga di dalam thread. Itu
  menyingkirkan jawaban ganda atas satu "ya".

**Agen `keuangan` di OpenClaw.**
- Agen baru, dengan workspace dan kontrak (`AGENTS.md`) yang sama dengan `main`, tetapi alatnya
  dibatasi ke menjalankan skrip bill-tracker dan membaca berkas data. Tidak ada eksekusi bebas,
  web, atau akses di luar itu.
- Peer A2A `hermes` diikat ke agen ini; agen `main` tidak bisa dicapai dari Hermes.
- Satu peer, satu token yang kuat, token ada di lingkungan gateway, bukan di repo.
- Bila ternyata OpenClaw tidak bisa membatasi alat per agen atau berbagi `AGENTS.md` antar dua
  agen, Relay jatuh ke `main` dan hal itu dicatat sebagai risiko yang diterima di ADR-0023.

**Kontrak Relay di `AGENTS.md`.**
- Agen mengenali pesan Relay dari kepalanya. Pencatat = nama di kepala (tetap dibakukan skrip
  lewat alias, ADR-0017); `channel` = Kanal di kepala + `-via-hermes`.
- Kepala yang tidak lengkap atau tidak terbaca: tidak ada penulisan (catat, ubah, hapus). Agen
  meminta pesan dikirim ulang. Pertanyaan baca saja tetap dijawab.
- Kontrak Pratinjau tidak berubah dan tidak diduplikasi: Relay memakai kerangka yang sama.
- Foto di jalur Relay tidak terjadi (Hermes tidak meneruskan); kontrak tidak perlu cabang
  untuknya selain larangan menebak bila ada.

**Pengiriman laporan (perubahan kode).**
- Module pengirim mengembalikan banyak tujuan: nomor pemilik di WhatsApp ditambah tujuan Telegram
  dan Discord, semuanya dari config, tidak ditulis keras di repo (ADR-0011). Tujuan yang tidak
  terkonfigurasi dilewati dengan pesan yang jelas; tidak ada satu pun tujuan = kegagalan seperti
  sekarang.
- Tiap tujuan dicoba sendiri-sendiri; kegagalan satu tidak menghentikan yang lain.
- **Semantik baru "terkirim" untuk Laporan Bulanan:** angka disimpan bila **minimal satu**
  tujuan menerima, karena maksud aturan "disimpan hanya kalau terkirim" adalah laporan itu sudah
  sampai ke seseorang. Sebelumnya semua tujuan harus berhasil, yang tidak lagi masuk akal dengan
  tiga tujuan. Kode keluar tetap 1 bila ada tujuan yang gagal, supaya kegagalan itu terlihat.
- Laporan Mingguan dan cek budget malam: kode keluar 1 bila ada tujuan yang gagal, selebihnya
  tidak berubah. Penjaga kesehatan (ADR-0011) tidak berubah dan tetap berdiri sendiri.
- Batas waktu cron: percobaan ulang yang ada berlaku per tujuan, jadi waktu terburuk bertambah
  linear; batas waktu cron perlu dinaikkan atau percobaan ulang tujuan baru dikurangi.

**Config dan dokumentasi.**
- Contoh config baru (Discord, peer A2A, agen `keuangan`) masuk `openclaw.json.example` dengan
  nilai karangan. Config Hermes ada di luar repo; yang masuk repo adalah catatan pemasangan.
- ADR-0023 diperbarui bila verifikasi memutuskan hal berbeda dari dugaannya.

## Testing Decisions

**Tes yang baik di sini** hanya menyentuh perilaku luar: apa yang disimpan dan dikirim, kode
keluar, dan teks kontrak yang dibaca model. Tidak menguji cara internal memilih tujuan.

**Seam 1: `tujuan_baku` dan `kirim`** (sudah ada, ditimpa langsung di tes laporan). Kasus:
- banyak tujuan, semua berhasil: Laporan Bulanan menyimpan angka, kode keluar 0;
- banyak tujuan, sebagian gagal: angka tersimpan, kode keluar 1, tujuan yang berhasil tetap
  menerima;
- semua tujuan gagal: angka tidak tersimpan, kode keluar 1;
- tidak ada tujuan: perilaku seperti sekarang;
- Laporan Mingguan dan cek budget: kode keluar 1 bila ada yang gagal, 0 bila semua berhasil;
- cek budget tanpa isi tidak mengirim apa pun ke tujuan mana pun.

Prior art: `test_laporan_bulanan.py` (menimpa `kirim` dan `tujuan_baku`, memeriksa simpanan),
`test_laporan_mingguan.py`, `test_check_bills.py`.

**Seam 2: `test_kontrak_prompt.py`** (sudah ada). Kasus: kepala Relay didefinisikan sekali di
`AGENTS.md` dan tidak di skill; aturan "tanpa kepala lengkap = tidak menulis"; `channel` berakhiran
`-via-hermes` untuk Relay; larangan menebak untuk foto di jalur Relay; Pratinjau tetap hanya satu
definisi. Seperti tes yang ada, ini membuktikan teks kontrak, bukan kepatuhan model (ADR-0014).

**Daftar uji terima manual** (tanpa seam otomatis), dijalankan sebelum jalur dianggap selesai:
- bot Discord OpenClaw menjawab di kanal keuangan hanya bila di-@mention, dan tidak menjawab di
  kanal lain atau pada pengguna lain;
- siklus penuh di Discord: catat → Pratinjau → `@bot ya` → tersimpan → `cari`;
- satu pesan dengan @mention satu bot tidak menghasilkan jawaban dari bot lain;
- Relay: pesan teks lewat Hermes menghasilkan Pratinjau dari agen `keuangan`; "ya" lewat Hermes
  menyelesaikannya; barisnya berisi `discord-via-hermes` dan Pencatat yang benar;
- foto di kanal keuangan lewat Hermes ditolak dengan kalimat baku;
- Hermes tidak menjawab angka keuangan di kanal selain kanal keuangan;
- agen `keuangan` menolak perintah di luar skrip bill-tracker (batas alat benar-benar berlaku);
- Hermes tidak dapat memanggil agen `main`;
- laporan benar-benar tiba di ketiga Kanal, dan mematikan satu Kanal tidak menghalangi dua lain;
- izin kanal Discord: hanya pemilik dan istri yang melihatnya.

## Out of Scope

- Menyatukan percakapan lintas Kanal (`session.identityLinks` tidak diaktifkan).
- Memindahkan WhatsApp, keuangan, atau bill-tracker ke Hermes; mengaktifkan skill `bill-tracker`
  di Hermes; memasang repo ke Docker Hermes.
- Relay lewat Telegram, dan Relay foto atau berkas.
- Satu peer A2A per orang (identitas dari token); Honcho; memori bersama antar agen.
- Autentikasi kuat untuk Pencatat pada Relay; risiko identitas-klaim diterima (ADR-0023).
- Mengubah penjaga kesehatan atau tujuan peringatannya.
- Memperbaiki indeks memori OpenClaw yang rusak (0/11 berkas terindeks) dan menjalankan
  `hermes claw cleanup` (jangan dijalankan: mengganti nama `~/.openclaw` yang sedang dipakai).
- Mengubah perilaku bot helpdesk FH UIR.

## Further Notes

- **Urutan pembangunan:** jalur A dulu (bot Discord OpenClaw, tujuan laporan tambahan), lalu agen
  `keuangan` dan jalur B. Jalur B bergantung pada A2A yang belum aktif dan pada verifikasi
  pembatasan alat per agen.
- **Dugaan yang perlu diverifikasi sebelum dikerjakan:** pembatasan alat per agen dan berbagi
  `AGENTS.md` antar dua agen di OpenClaw; `channel_prompts` Hermes untuk Discord (terdokumentasi
  untuk Telegram, Slack, Mattermost); apakah kanal Discord benar-benar hanya terlihat dua orang;
  perilaku dua koneksi bot di satu server; perilaku `contextId` A2A lintas restart (tugas A2A
  OpenClaw hanya di memori dan hilang saat gateway restart, jadi Pratinjau yang menggantung
  hilang dan harus diulang).
- **Pratinjau yang menggantung** mengikuti aturan yang ada: draf hanya di percakapan, dibuang
  bila ada Transaksi baru atau konteksnya hilang.
- **Isi `bills.csv` memuat gaji.** Izin kanal Discord adalah syarat keamanan, bukan detail
  pemasangan; jangan dianggap selesai sebelum diperiksa di Discord.
- **Tidak diperiksa:** siapa dua nomor di `allowFrom` OpenClaw dan siapa pemilik dua chat
  Telegram pada cron Hermes (dugaan: pemilik dan istri).
- Hermes dan OpenClaw sering berganti skema config; riset ini bersumber dari OpenClaw 2026.10.9
  dan Hermes 0.22.2, jadi cek ulang setelah pembaruan.
