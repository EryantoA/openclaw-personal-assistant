# Family Bill Tracker

Catatan keuangan satu keluarga, diisi lewat pesan WhatsApp/Telegram dan diimpor dari
aplikasi keuangan yang dipakai sebelumnya.

## Language

### Transaksi

**Transaksi**:
Satu pembayaran atau penerimaan uang nyata, ditandai satu No Resi. Satu struk belanja berisi
banyak barang tetap satu Transaksi; tiap barangnya satu Item, yaitu satu baris di Buku Kas.
Hitungan "N transaksi" di laporan selalu menghitung No Resi unik, bukan baris. Transfer dan Saldo
Awal tidak dihitung (ADR-0023).
_Avoid_: entri, record, baris (untuk seluruh Transaksi)

**Buku Kas**:
Seluruh Transaksi yang tercatat — `data/bills.csv`, satu baris per Item. Sumber tunggal Saldo
Bersama dan Arus Kas Bulanan; aturan membaca dan menghitungnya (termasuk jumlah Transaksi dan
total per Kategori) hidup di `scripts/buku_kas.py`. Kewajiban dan Perkiraan tidak
ada di dalamnya.
_Avoid_: ledger, database, sheet

**Pemasukan**:
Uang yang masuk ke kas keluarga.
_Avoid_: income, pendapatan

**Pengeluaran**:
Uang yang keluar dari kas keluarga.
_Avoid_: expense, outcome, belanja

**Arah**:
Ke mana uang sebuah Transaksi bergerak: Pemasukan, Pengeluaran, atau Transfer antar akun sendiri
(bukan keduanya). Selalu disebut di Pratinjau dan balasan konfirmasi, supaya uang masuk tidak
terbaca seperti belanja (ADR-0019).
_Avoid_: income/outcome, jenis, tipe

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
jadi tidak pernah ikut menghitung Saldo Bersama maupun Arus Kas Bulanan. Gunanya dua: menyiapkan diri
untuk uang yang akan keluar, dan menyadari kalau yang seharusnya masuk ternyata tidak masuk.
_Avoid_: rencana, budget, langganan, recurring

### Uang

**Saldo Bersama**:
Seluruh uang keluarga di semua Akun — Dompet, Rekening, maupun Simpanan, milik kami berdua —
digabung jadi satu angka. Selalu kumulatif, dibawa terus dari bulan ke bulan. **Bukan** uang tunai
yang bisa dipegang. Memindahkan uang antar Akun (menabung, setor ke rekening) tidak dicatat sebagai
Transaksi dan karenanya tidak mengubah Saldo Bersama. Saldo Bersama = jumlah semua Saldo Akun.
Di kode dan ADR lama disebut `saldo` / "Saldo".
_Avoid_: sisa, selisih, balance, uang tunai, saldo bulanan

**Arus Kas Bulanan**:
Pemasukan dikurangi pengeluaran dalam satu bulan, berdiri sendiri tanpa membawa bulan lalu; bulan
berikutnya mulai dari nol lagi. Di kode dan ADR lama disebut `arus_kas_bulan` / "Arus Kas Bulan".
_Avoid_: saldo bulanan, saldo bulan ini, net

**Akun**:
Satu tempat uang disimpan. Tiga jenis dalam keluarga kami: **Dompet**, **Rekening** (bank), dan
**Simpanan**, masing-masing milik saya dan istri, jadi enam Akun (mis. Dompet Saya, Rekening
Istri). Nama Akun diisi di `data/akun.json`; sebelum fitur diaktifkan di sana masih nama bawaan
`Kas`, `Bank Utama`, `Tabungan`. `Kas` sebagai Akun artinya uang tunai, bukan Buku Kas.
Berbeda dari cara bayar (GoPay, Livin' by Mandiri), yang tempatnya di Catatan.
_Avoid_: tempat, kantong

**Saldo Akun**:
Uang di satu Akun, dihitung sejak tanggal cutover (ADR-0010). Sebelum cutover hanya Saldo Bersama
yang bermakna. Fiturnya belum aktif sampai `saldo_awal` tiap Akun diisi.
_Avoid_: saldo dompet (tanpa menyebut pemilik)

**Saldo Awal**:
Kas yang sudah dimiliki sebelum transaksi pertama tercatat. Bukan pemasukan — tidak ada
uang yang berpindah saat itu.
_Avoid_: modal awal, opening balance, saldo pembuka

**Budget**:
Batas pengeluaran yang ditetapkan untuk satu bulan. Hanya membatasi pengeluaran; pemasukan
tidak dihitung terhadapnya.

**Pengaturan**:
Isi `data/budget.json`: Budget, kategori yang sah, aturan Duplikat Lapis 2, toleransi Perkiraan,
dan kapan Kewajiban diingatkan. Budget hanya salah satu isinya, jadi berkasnya tidak disebut
"budget". Dibaca lewat `scripts/pengaturan.py`; kategori dan aturan Duplikat masih lewat
`resi.BUDGET_JSON` (ADR-0020).
_Avoid_: config, budget (untuk seluruh berkas)

### Penanda

**Kategori**:
Pengelompokan transaksi. Selalu slug Inggris huruf kecil, tidak pernah Bahasa Indonesia.
_Avoid_: jenis, tipe belanja

**Item**:
Satu baris di Buku Kas; satu Transaksi punya satu Item atau lebih. Apa yang dibeli, ditulis apa adanya. Kalau ada tokonya, namanya ikut di belakang setelah
tanda pisah — `Susu UHT + Yakult - Budiman Swalayan`. Toko tidak punya kolom sendiri: ia
bagian dari Item. Bank dan e-wallet bukan toko — itu cara bayar, tempatnya di Catatan.
_Avoid_: tempat, merchant, vendor, deskripsi

**Pratinjau**:
Tampilan apa yang akan disimpan ke CSV, dikirim bot sebelum pencatatan dan menunggu jawaban.
Bukan Transaksi: belum ada baris yang tertulis, jadi tidak mengubah Saldo Bersama (ADR-0016). Berlaku
juga sebelum mengubah atau menghapus Transaksi yang sudah tercatat, dengan tampilan sebelum →
sesudah (ADR-0018).
_Avoid_: draf, konfirmasi, preview

**Jejak Perubahan**:
Catatan append-only (`data/riwayat-ubah.csv`) tentang setiap Transaksi yang diubah atau dihapus:
kapan, siapa, isi sebelum dan sesudah. Bukan Transaksi dan tidak ikut hitungan apa pun; tidak
bisa diubah atau dihapus lewat chat (ADR-0018).
_Avoid_: log, audit, riwayat edit

**Pembeli**:
Orang yang berbelanja, sama dengan `pencatat` di data: nama pengirim pesan. Tampil di balasan
konfirmasi (ADR-0015), tetapi hanya untuk Pengeluaran; pada Pemasukan dan Transfer nama yang
sama tampil sebagai Pencatat, karena tidak ada yang dibeli (ADR-0019). Satu orang bisa punya banyak alias (nama panggilan, peran
seperti "istri", beda huruf besar-kecil); semuanya dibakukan ke satu nama baku (ADR-0017).
Bukan penerima transfer.
_Avoid_: buyer, pembayar

**No Resi**:
Penanda unik satu transaksi, sekaligus dasar deteksi duplikat.
_Avoid_: nomor struk, id, referensi

**Bukti Transfer**:
Gambar mutasi bank atau e-wallet yang menjadi sumber satu Transaksi. Seperti semua
pencatatan ia lewat Pratinjau (ADR-0016), dengan baris Referensi dan Arah tambahan dan
pertanyaan akun yang wajib (ADR-0014). Nomor referensi di dalamnya menjadi No Resi `STRUK-<nomor>`.
_Avoid_: struk transfer, slip

**Duplikat**:
Satu transaksi yang sama tercatat lebih dari sekali. Dua transaksi berbeda yang kebetulan
sama isinya bukan duplikat. Dicek di tiga lapis, semuanya di `scripts/duplikat.py` dan dengan
satu arti "sama" untuk satu nilai: **Lapis 1** No Resi sama persis (tidak bisa dilewati);
**Lapis 2** field `match_fields` di `budget.json` sama (bisa dilewati hanya setelah pengguna
menegaskan itu transaksi baru); **Audit** baris tersimpan yang sama di semua kolom selain No Resi
(laporan saja, tidak ada yang dihapus).
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
disebutkan. Saldo Bersama di dalamnya adalah Saldo Bersama per akhir Pekan, bukan per saat dikirim.
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
sesudahnya yang Saldo Bersama akhirnya ikut bergeser karena Saldo Bersama kumulatif.
_Avoid_: revisi, ralat, penyesuaian

### Waktu

**Pekan**:
Senin 00:00 sampai Minggu 23:59 WIB. Satuan waktu Laporan Mingguan dan pembandingnya
("pekan lalu"). Sebuah Pekan baru dilaporkan setelah ia tutup — jadi Transaksi yang dicatat
Minggu larut malam tetap masuk Pekan-nya. Kata "minggu" hanya dipakai untuk nama hari.
_Avoid_: minggu (untuk arti 7 hari), 7 hari terakhir, seminggu
