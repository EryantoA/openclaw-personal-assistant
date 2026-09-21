# Penjaga kesehatan tidak boleh butuh model, dan blind spot-nya diakui

`scripts/periksa-kesehatan.py` memeriksa status cron, masa berlaku OAuth, dan kesegaran
`bills.csv`, lalu mengabari lewat `openclaw message send`. Ia berjalan sebagai **command
payload** di cron Gateway — bukan sebagai giliran agent.

Pemicunya kejadian nyata. Pada 21 Agustus 2026 OAuth `claude-cli` berhenti bisa disegarkan.
Karena seluruh model memakai `agentRuntime: claude-cli`, **setiap giliran agent gagal** —
termasuk pencatatan bill-tracker lewat WhatsApp. `cek_budget_malam` berstatus `error`
selama dua hari dan **tidak mengabari siapa pun**: cron yang gagal hanya mencatat error
pada dirinya sendiri. Ini kelas kegagalan yang sama dengan yang
[0009](0009-cron-hidup-di-gateway-bukan-di-openclaw-json.md) tulis untuk dihindari, muncul
lagi di tempat yang berbeda.

Dari situ syarat utamanya jelas: **penjaga tidak boleh bergantung pada hal yang ia jaga.**
Kalau ia butuh model untuk menyusun laporannya, ia akan mati bersama model — persis pada
saat ia paling dibutuhkan. Karena itu ia hanya membaca status dan menyusun kalimat dari
template, dan mengirim lewat channel plugin Gateway yang tidak menyentuh model sama sekali.

Ia juga meredam ulangan: peringatan dengan isi sama tidak diulang sebelum 12 jam. Penjaga
yang mengirim pesan identik tiap jam akan diabaikan dalam seminggu, dan penjaga yang
diabaikan sama saja dengan tidak ada.

## Considered Options

**Menjadikannya giliran agent** ditolak, walau lebih luwes: agent bisa merangkum keadaan,
menautkan sebab-akibat, bahkan menyarankan perbaikan. Semua itu hilang persis ketika model
mati — yaitu satu-satunya keadaan yang paling perlu dilaporkan.

**Menyandarkan diri pada notifikasi kegagalan bawaan cron** ditolak setelah diperiksa:
`lastFailureNotificationDeliveryStatus` untuk pekerjaan yang gagal itu berbunyi `unknown`,
dan kenyataannya tidak ada pesan yang sampai selama dua hari.

**Memeriksa tiap jam** ditolak demi 3x sehari (08:00, 14:00, 21:00 Asia/Jakarta). Jam 21:00
dipilih supaya kegagalan `cek_budget_malam` yang berjadwal 20:00 tertangkap di malam yang
sama, bukan besok paginya.

## Consequences

**Blind spot yang harus diakui:** penjaga ini berjalan DI DALAM Gateway. Kalau Gateway
sendiri mati total, ia ikut mati dan tidak ada yang mengabari. Ini batas mendasar dari
penjaga yang tinggal serumah dengan yang dijaganya, dan tidak ditutup-tutupi. Sinyal
cadangan untuk kasus itu adalah `backup_harian`: kalau berkas backup harian berhenti
bertambah, Gateway-nya yang bermasalah. Kalau suatu saat itu dirasa kurang, penjaga
sungguhan harus hidup di luar OpenClaw — launchd tersendiri.

Nomor tujuan **tidak ditulis keras** di skrip; ia dibaca dari
`channels.whatsapp.allowFrom[0]` di `openclaw.json`, dan bisa ditimpa lewat `--ke`. Repo ini
di-publish, dan nomor telepon tidak perlu ikut.

Ambang pemeriksaan sengaja longgar (cron mandek 3 jam, buku kas diam 3 hari) supaya
peringatan pertama yang muncul benar-benar berarti. Ambang yang terlalu ketat menghasilkan
peringatan palsu, dan peringatan palsu mematikan kepercayaan lebih cepat daripada tidak ada
peringatan sama sekali.

**Koreksi 22 Agustus 2026 — OAuth tidak punya peringatan dini lagi.** Ambang "OAuth 5 hari"
yang semula ditulis di sini justru melanggar alasan di atas. Token akses OAuth hanya hidup
hitungan jam lalu disegarkan sendiri, jadi token yang paling sehat pun selalu "tersisa 0,1
hari" — peringatan kuning menyala pada setiap pemeriksaan, tiga kali sehari, selamanya.
Ambang dalam satuan hari tidak pernah bisa benar untuk umur yang diukur dalam jam. Sekarang
satu-satunya sinyal OAuth adalah **sudah lewat masa berlaku**, yang artinya penyegaran
otomatis berhenti jalan — persis keadaan 21 Agustus.

Sumber bacaannya juga diperbaiki. Semula angka masa berlaku dibaca langsung dari sqlite
`auth_profile_store`, dan simpanan itu bisa **basi**: 22 Agustus simpanannya masih mencatat
kedaluwarsa 01 Agustus padahal token di keychain sudah disegarkan, dan baru ikut berubah
setelah ada yang membaca lewat CLI. Penjaga sekarang memanggil `openclaw models auth list`,
yang memaksa pembacaan ulang dari keychain; sqlite tinggal cadangan kalau perintah itu
gagal. Perintah ini tidak menyentuh model, jadi syarat utama ADR ini tetap terjaga.

**Koreksi 21 September 2026: kiriman yang gagal dianggap terkirim, dan penjaga mengadukan
dirinya sendiri.** Dua cacat ini saling menutupi:

- `catat()` dijalankan walaupun pengiriman gagal. Akibatnya peredam menahan peringatan yang
  tidak pernah diterima siapa pun selama 12 jam. Dari 39 run (6–21 Sep) yang mencoba mengirim,
  9 gagal secara acak (`No active WhatsApp Web listener`), padahal channel berstatus
  "connected". Sekarang peringatan hanya dicatat setelah terkirim, dan pengiriman dicoba
  sampai 3 kali dengan jeda 60 detik. Retry-nya ditulis ulang di skrip ini, tidak dipinjam dari
  `laporan-bulanan.py`, supaya penjaga tetap bergantung pada sesedikit mungkin kode lain.
- Penjaga melaporkan run-nya sendiri yang gagal. Laporan itu tidak bisa ditindak ("tanpa
  keterangan"), dan satu-satunya efeknya adalah mengubah sidik sehingga cacat pertama tidak
  terlihat. Pesan 21 Sep 21:00 isinya hanya itu, padahal semuanya sudah sehat. Sekarang job
  `penjaga_kesehatan` dilewati, karena run yang sedang berjalan sudah bukti bahwa ia hidup.

Timeout yang terjadi tiga kali (18, 20, 21 Sep, 10–17 menit) **bukan** cacat skrip. Menurut
`pmset -g log`, Mac yang berjalan dengan baterai terbangun sebentar (DarkWake, sekitar 14
detik), cron jalan, lalu Mac tidur lagi di tengah run. Selama Mac tidur, semua cron dan
balasan bot berhenti. Ini soal pengaturan daya, bukan soal kode.
