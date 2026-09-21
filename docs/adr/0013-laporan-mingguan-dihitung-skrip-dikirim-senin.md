# Laporan Mingguan dihitung skrip, untuk Pekan yang sudah tutup, dikirim Senin 07:00

**Laporan Mingguan** (lihat `CONTEXT.md`) disusun seluruhnya oleh `scripts/laporan-mingguan.py`
sebagai **command payload** di cron Gateway, bukan oleh giliran agent. Ia melaporkan satu
**Pekan** (Senin 00:00 – Minggu 23:59 WIB) yang sudah tutup, dikirim **Senin 07:00**, lewat
`openclaw message send`. Keputusan ini sejalan dengan [0012](0012-laporan-bulanan-dihitung-skrip-dikirim-tanggal-6.md)
untuk Laporan Bulanan dan [0011](0011-penjaga-kesehatan-tidak-boleh-butuh-model.md) untuk
penjaga kesehatan.

## Kenapa skrip, bukan model

Tiga kegagalan dalam satu hari (21 Sep 2026) menunjukkan bahwa laporan versi agent tidak bisa
dipercaya, dan penyebabnya berbeda-beda:

- **Tidak jalan:** OAuth mati 20 Sep, dan laporan pekan itu tidak pernah dibuat.
- **Tidak terkirim:** setelah auth pulih, laporan dibuat (`ok`) tetapi tidak dikirim
  (`not-delivered`), karena model tidak memanggil tool `message` ([0009](0009-cron-hidup-di-gateway-bukan-di-openclaw-json.md), insiden ketiga).
- **Tidak konsisten:** periode "minggu ini" ditafsirkan berbeda di tiap run (1–6, 7–13,
  15–21 Sep). Di run 21 Sep model bahkan menulis "data sampai 29 Agustus" sebelum menyajikan
  angka September. Tidak ada cara memeriksa angka yang dihasilkan.

Laporan ini dipakai untuk mengambil keputusan soal uang, jadi angkanya harus bisa diulang.
Tips, narasi, dan "semangat menabung!" dikorbankan untuk itu. Pertanyaan bebas tetap bisa
diajukan ke bot.

## Kenapa Senin pagi, bukan Minggu malam

Laporan Minggu 20:00 untuk Pekan Senin–Minggu melewatkan Transaksi yang dicatat Minggu malam
setelah jam kirim. Laporan pekan berikutnya juga tidak memuatnya, sehingga Transaksi itu
**tidak pernah muncul di laporan mana pun**. Kalau dikirim Senin pagi, Pekan-nya sudah tutup
dan angka "pekan lalu" di laporan berikutnya dihitung dari batas waktu yang sama.

Pekan Minggu–Sabtu (tetap dikirim Minggu malam) ditolak karena tidak sejajar dengan cara
keluarga menghitung pekan.

## Keputusan isi yang mengejutkan tanpa konteks

- **"Pekan lalu" dihitung ulang, tanpa Koreksi.** Pembanding dihitung dari catatan saat ini dan
  diberi satu baris keterangan. Angkanya bisa berbeda dari pesan Senin sebelumnya kalau ada
  transaksi yang telat dicatat. Menyimpan angka dan menyebut Koreksi adalah tugas Laporan
  Bulanan (0012). Kalau Laporan Mingguan juga melakukannya, ada dua tempat yang mengurus hal
  yang sama. `bills.csv` juga tidak mencatat *kapan* baris dicatat, jadi tanpa simpanan tidak
  ada cara mengenali transaksi yang telat.
- **Saldo per akhir Pekan**, bukan per saat kirim. Dengan begitu Saldo pekan lalu + Pemasukan −
  Pengeluaran Pekan = Saldo yang dilaporkan, meskipun ada Transaksi Senin subuh.
- **Pekan yang melewati pergantian bulan menampilkan Budget dan Perkiraan kedua bulan**, dan
  bulan lama ditandai "(tutup)". Kalau hanya bulan baru yang tampil, angka final bulan lama
  baru muncul di Laporan Bulanan tanggal 6.
- **Peringatan Hari Kosong hanya untuk ≥2 hari berturut-turut dalam satu Pekan.** Data
  September 2026 punya 8 hari tanpa Pengeluaran. Empat di antaranya berdiri sendiri (4, 6, 7,
  13 Sep; dua di antaranya hari Minggu), dan empat lagi berderet (15–18 Sep, masa OAuth mati).
  Kalau peringatan muncul untuk setiap hari kosong, hampir tiap laporan akan memuatnya, dan
  peringatan yang muncul tiap pekan akan diabaikan (alasan peredaman di 0011). Dengan ambang
  ini, dari data Agustus–September hanya Pekan 14–20 Sep yang memicu peringatan, dan memang
  hanya Pekan itu yang kurang tercatat.

## Consequences

- **Permintaan lewat chat** ("laporan minggu ini") menjalankan skrip yang sama. Untuk Pekan
  yang belum tutup, judulnya diberi tanda "Pekan berjalan". Model meneruskan output apa adanya
  dan tidak memformat ulang, supaya tidak ada dua versi angka untuk satu Pekan.
- **Pengiriman dicoba sampai 3 kali dengan jeda 60 detik**, memakai `kirim()` yang sama dengan
  Laporan Bulanan. Dari 39 run penjaga kesehatan (6–21 Sep 2026) yang mencoba mengirim, 9 gagal
  secara acak (`No active WhatsApp Web listener`, `Connection Closed`), padahal
  `channels status` menyebut WhatsApp tersambung. Risikonya pesan ganda, dan itu lebih murah
  daripada laporan yang tidak sampai. Timeout cron harus ≥420 detik.
- **Skrip keluar dengan status gagal kalau ketiga percobaan gagal**, supaya cron tercatat `error`
  dan penjaga kesehatan menangkapnya pukul 08:00 di pagi yang sama.
- **Cron `laporan_mingguan` diubah di tempat** (`cron edit`, ID tetap), bukan dihapus lalu
  dibuat ulang, supaya riwayat run dan pemantauan penjaga kesehatan tidak terputus.
- **Aturan Perkiraan dipakai bersama** lewat `perkiraan_absen()` di `check-bills.py`, sama
  dengan Laporan Bulanan. Laporan Mingguan tidak punya aturan pencocokan sendiri.
- **Blind spot yang diakui:** skrip tidak bisa membedakan hari tanpa belanja dari hari yang
  tidak tercatat. Satu Hari Kosong yang sebenarnya karena lupa mencatat tidak memicu apa-apa.

## Diperluas ke `cek_budget_malam` (21 Sep 2026)

Cron peringatan malam (Senin–Sabtu 20:00) diubah dengan cara yang sama: command payload
`check-bills.py --mode all --kirim`, tanpa model, dan hanya mengirim kalau ada temuan. Selama
masih berupa giliran agent, 12 dari 53 run (sekitar 23%) gagal sebelum sempat mengecek (OAuth
mati, kuota habis, timeout). Menjalankan ulang skrip untuk malam-malam itu menunjukkan bahwa
peringatan "BUDGET HABIS" 26 Agu 2026 tidak pernah terkirim. Pada malam yang berjalan normal,
agent memang meneruskan peringatan dengan benar, jadi yang dibuang hanya ketergantungan pada
model, bukan logika pengecekannya.

Keputusan "ada isi atau tidak" diambil dari hasil tiap bagian (`temuan_all()` kosong atau
tidak), bukan dari teks "✅ Semua lancar". Dengan begitu, mengubah kalimat ramah itu tidak
bisa membuat cron diam-diam mengirim setiap malam.
