# Family Bill Tracker

Catatan keuangan satu keluarga, diisi lewat pesan WhatsApp/Telegram dan diimpor dari
aplikasi keuangan yang dipakai sebelumnya.

## Language

### Transaksi

**Transaksi**:
Satu pergerakan uang nyata, tercatat sebagai satu baris.
_Avoid_: entri, record

**Pemasukan**:
Uang yang masuk ke kas keluarga.
_Avoid_: income, pendapatan

**Pengeluaran**:
Uang yang keluar dari kas keluarga.
_Avoid_: expense, outcome, belanja

### Yang Belum Jadi Transaksi

**Kewajiban**:
Tagihan yang sudah datang tapi belum dibayar. Hanya ada untuk yang pascabayar — datang dulu,
dibayar belakangan. Pembelian prabayar (pulsa, paket data, gas, top-up e-wallet) tidak pernah
jadi Kewajiban: uangnya keluar di detik yang sama. Sebuah Kewajiban berakhir ketika ada
Transaksi yang membayarnya, bukan ketika seseorang menandainya selesai.
_Avoid_: utang, tanggungan, bill, tagihan terencana

**Perkiraan**:
Transaksi yang diharapkan berulang tiap bulan — gaji yang biasanya masuk akhir bulan,
langganan yang biasanya ditarik tanggal 26. Bukan Transaksi: belum ada uang yang berpindah,
jadi tidak pernah ikut menghitung Saldo maupun Arus Kas Bulan. Gunanya dua: menyiapkan diri
untuk uang yang akan keluar, dan menyadari kalau yang seharusnya masuk ternyata tidak masuk.
_Avoid_: rencana, budget, langganan, recurring

### Uang

**Saldo**:
Seluruh uang keluarga di semua tempat — tunai, rekening, maupun tabungan — digabung jadi satu
angka. Selalu kumulatif, dibawa terus dari bulan ke bulan. **Bukan** uang tunai yang bisa
dipegang. Pemindahan antar tempat (menabung, setor ke rekening) tidak dicatat sebagai
transaksi dan karenanya tidak mengubah Saldo.
_Avoid_: sisa, selisih, balance, uang tunai

**Arus Kas Bulan**:
Pemasukan dikurangi pengeluaran dalam satu bulan, berdiri sendiri tanpa membawa bulan lalu.
_Avoid_: saldo bulanan, saldo bulan ini, net

**Saldo Awal**:
Kas yang sudah dimiliki sebelum transaksi pertama tercatat. Bukan pemasukan — tidak ada
uang yang berpindah saat itu.
_Avoid_: modal awal, opening balance, saldo pembuka

**Budget**:
Batas pengeluaran yang ditetapkan untuk satu bulan. Hanya membatasi pengeluaran; pemasukan
tidak dihitung terhadapnya.

### Penanda

**Kategori**:
Pengelompokan transaksi. Selalu slug Inggris huruf kecil, tidak pernah Bahasa Indonesia.
_Avoid_: jenis, tipe belanja

**Item**:
Apa yang dibeli, ditulis apa adanya. Kalau ada tokonya, namanya ikut di belakang setelah
tanda pisah — `Susu UHT + Yakult - Budiman Swalayan`. Toko tidak punya kolom sendiri: ia
bagian dari Item. Bank dan e-wallet bukan toko — itu cara bayar, tempatnya di Catatan.
_Avoid_: tempat, merchant, vendor, deskripsi

**No Resi**:
Penanda unik satu transaksi, sekaligus dasar deteksi duplikat.
_Avoid_: nomor struk, id, referensi

**Duplikat**:
Satu transaksi yang sama tercatat lebih dari sekali. Dua transaksi berbeda yang kebetulan
sama isinya bukan duplikat.
_Avoid_: dobel, kembar

**Asal**:
Dari mana sebuah baris berasal — pesan yang masuk, atau impor dari aplikasi lain.
_Avoid_: channel, sumber

**Pencatat**:
Anggota keluarga yang mencatat transaksi. Belum tentu orang yang membelanjakan uangnya.
_Avoid_: pengirim, user

### Laporan

**Laporan Bulanan**:
Laporan untuk satu bulan yang sudah tutup, dikirim beberapa hari setelah bulan berganti supaya
transaksi yang telat dicatat ikut terhitung. Bukan laporan bulan berjalan — memantau bulan yang
sedang berjalan adalah tugas pengecekan budget dan laporan mingguan. Angka yang dilaporkan
disimpan, supaya perubahan sesudahnya bisa dikenali.
_Avoid_: rekap bulanan, laporan bulan ini, tutup buku

**Laporan Mingguan**:
Laporan untuk satu Pekan yang sudah tutup, dikirim Senin pagi. Angkanya dihitung dari catatan
saat laporan dibuat — termasuk angka "pekan lalu" sebagai pembanding, yang karenanya bisa
berbeda dari laporan yang dulu terkirim. Laporan Mingguan tidak punya Koreksi; itu tugas
Laporan Bulanan. Kalau Pekan-nya melewati pergantian bulan, Budget dan Perkiraan kedua bulan
disebutkan. Saldo di dalamnya adalah Saldo per akhir Pekan, bukan per saat dikirim.
_Avoid_: laporan minggu ini, weekly report, rekap mingguan

**Hari Kosong**:
Hari dalam sebuah Pekan tanpa satu pun Pengeluaran tercatat. Satu Hari Kosong biasa saja;
dua atau lebih berturut-turut dalam satu Pekan dianggap tanda ada yang tidak tercatat, dan
Laporan Mingguan memperingatkannya dengan menyebut hari-harinya.
_Avoid_: hari bolong, data hilang

**Koreksi**:
Selisih antara angka sebuah bulan yang sudah dilaporkan dan angka bulan itu bila dihitung ulang
sekarang — biasanya karena transaksi yang baru tercatat saat pencocokan mutasi bank. Koreksi
tidak mengubah laporan yang sudah terkirim; ia disebutkan di Laporan Bulanan berikutnya, untuk
bulan mana pun yang pernah dilaporkan, dan hanya sekali. Koreksi melekat pada bulan asal
perubahan — bulan yang Pemasukan atau Pengeluarannya berubah — bukan pada bulan-bulan
sesudahnya yang Saldo akhirnya ikut bergeser karena Saldo kumulatif.
_Avoid_: revisi, ralat, penyesuaian

### Waktu

**Pekan**:
Senin 00:00 sampai Minggu 23:59 WIB. Satuan waktu Laporan Mingguan dan pembandingnya
("pekan lalu"). Sebuah Pekan baru dilaporkan setelah ia tutup — jadi Transaksi yang dicatat
Minggu larut malam tetap masuk Pekan-nya. Kata "minggu" hanya dipakai untuk nama hari.
_Avoid_: minggu (untuk arti 7 hari), 7 hari terakhir, seminggu
