# Family Bill Tracker

Catatan keuangan satu keluarga, diisi lewat pesan WhatsApp/Telegram dan diimpor dari
aplikasi keuangan yang dipakai sebelumnya.

## Language

### Transaksi

**Transaksi**:
Satu pembayaran atau penerimaan uang nyata, ditandai satu No Resi. Satu struk belanja berisi
banyak barang tetap satu Transaksi; tiap barangnya satu Item, yaitu satu baris di Buku Kas.
Hitungan "N transaksi" di laporan selalu menghitung No Resi unik, bukan baris. Transfer, Saldo
Awal, dan Selisih Rekonsiliasi tidak dihitung (ADR-0023, ADR-0027).
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
Di Cermin tampil per Item di kolom "Saldo Bersama" (ADR-0026).
Di kode dan ADR lama disebut `saldo` / "Saldo".
_Avoid_: sisa, selisih, balance, uang tunai, saldo bulanan, saldo berjalan

**Arus Kas Bulanan**:
Pemasukan dikurangi pengeluaran dalam satu bulan, berdiri sendiri tanpa membawa bulan lalu; bulan
berikutnya mulai dari nol lagi. Di kode dan ADR lama disebut `arus_kas_bulan` / "Arus Kas Bulan".
_Avoid_: saldo bulanan, saldo bulan ini, net

**Akun**:
Satu tempat uang disimpan milik satu orang di rumah tangga: uang tunai, rekening bank (termasuk
rekening tabungan), atau saldo e-wallet. Nama bakunya `<Tempat> <Panggilan>` — mis. `Tunai Ayah`,
`GoPay Ibu` — dan daftarnya hanya di `data/akun.json`; nama lain ditolak skrip, tidak ditebak
(ADR-0028). Rekening orang di luar rumah tangga bukan Akun: uang ke sana Pengeluaran, bukan
Transfer. Isi ulang e-wallet adalah Transfer ke Akun e-wallet; belanja memakai saldonya adalah
Pengeluaran dari Akun itu. Berbeda dari cara bayar (QRIS, Livin' by Mandiri), yang tempatnya di
Catatan.
_Avoid_: tempat, kantong, dompet (untuk uang tunai — pakai Tunai), Kas (sebagai nama Akun)

**Saldo Akun**:
Uang di satu Akun menurut Buku Kas, dihitung sejak tanggal cutover (ADR-0010) — hari pemilik
mengecek isi tiap Akun sendiri (ADR-0028). Sebelum cutover hanya Saldo Bersama yang bermakna.
Fiturnya belum aktif sampai `saldo_awal` tiap Akun diisi dengan angka yang dilihat, bukan sisa
hitungan.
_Avoid_: saldo dompet (tanpa menyebut pemilik)

**Saldo Nyata**:
Uang yang sungguh ada di satu Akun pada satu saat, seperti terlihat di rekening, dompet, atau
aplikasi — dilaporkan pengguna, bukan dihitung. Pembanding Saldo Akun dalam Rekonsiliasi.
_Avoid_: saldo bank, saldo asli, saldo riil

**Rekonsiliasi**:
Satu pengecekan Saldo Akun terhadap Saldo Nyata satu Akun, per saat Saldo Nyata dilaporkan (atau
per tanggal yang disebut). Hasilnya cocok, atau selisih yang dijelaskan dengan Transaksi terlupa,
ditutup dengan Selisih Rekonsiliasi, atau dibiarkan terbuka. Dicatat di `data/rekonsiliasi.csv`;
bukan Transaksi dan tidak ikut hitungan apa pun (ADR-0027).
_Avoid_: cek saldo, pencocokan (untuk satu Akun), audit

**Selisih Rekonsiliasi**:
Transaksi yang menutup selisih tak terjelaskan antara Saldo Akun dan Saldo Nyata, berkategori
`reconciliation`, dibuat hanya dari Rekonsiliasi. Ikut Saldo Akun, Saldo Bersama, dan Arus Kas
Bulanan; tidak ikut Budget maupun hitungan Transaksi (ADR-0027). Berbeda dari Koreksi, yang hanya
menyebut perubahan angka bulan yang sudah dilaporkan tanpa mencatat apa pun.
_Avoid_: penyesuaian, adjustment, koreksi saldo

**Saldo Awal**:
Kas yang sudah dimiliki sebelum transaksi pertama tercatat. Bukan pemasukan — tidak ada
uang yang berpindah saat itu.
_Avoid_: modal awal, opening balance, saldo pembuka

**Budget**:
Batas belanja **rutin** yang kami tetapkan sendiri untuk satu bulan. Bukan uang yang dimiliki dan
tidak mengikuti pemasukan (yang naik-turun); kecukupan uang dijawab Arus Kas Bulanan. Hanya
Pengeluaran rutin yang dihitung terhadapnya: Pengeluaran Besar dan Selisih Rekonsiliasi tidak ikut
(ADR-0024, ADR-0027).
_Avoid_: sisa uang, saldo budget

**Batas Kategori**:
Batas belanja rutin satu Kategori untuk satu bulan, hanya untuk kategori yang dipilih, di bawah
Budget yang tetap batas utama. Kategori tanpa Batas Kategori tetap dihitung ke Budget. Pengeluaran
Besar dan Selisih Rekonsiliasi tidak ikut (ADR-0029).
_Avoid_: budget kategori, amplop, anggaran per kategori

**Pengeluaran Besar**:
Satu Transaksi Pengeluaran yang jumlah seluruh Item-nya mencapai ambang (`pengeluaran_besar_mulai`
di Pengaturan, Rp 1.000.000). Tidak dihitung ke Budget, tapi selalu tampil terpisah sebagai
"Di luar budget" supaya tidak hilang dari pandangan. Tetap Pengeluaran biasa untuk Arus Kas Bulanan
dan Saldo Bersama.
_Avoid_: pengeluaran besar-besaran, one-off

**Pengaturan**:
Isi `data/budget.json`: Budget, ambang Pengeluaran Besar, kategori yang sah, aturan Duplikat Lapis 2,
toleransi Perkiraan, dan kapan Kewajiban diingatkan. Budget hanya salah satu isinya, jadi berkasnya tidak disebut
"budget". Dibaca lewat `scripts/pengaturan.py`; kategori dan aturan Duplikat masih lewat
`resi.BUDGET_JSON` (ADR-0020).
_Avoid_: config, budget (untuk seluruh berkas)

### Penanda

**Kategori**:
Pengelompokan transaksi. Selalu slug Inggris huruf kecil, tidak pernah Bahasa Indonesia.
_Avoid_: jenis, tipe belanja

**Label Kategori**:
Nama tampil Bahasa Indonesia sebuah Kategori (`personal_care` → Perawatan Diri), disimpan di
`budget.json` → `label_kategori`. Hanya tampilan — data tetap slug (ADR-0002). Unik: satu label
menunjuk tepat satu slug, supaya yang diketik di Cermin bisa dipetakan balik (ADR-0026).
_Avoid_: nama kategori, kategori Indonesia

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
Sebutan Pencatat di balasan Pengeluaran (ADR-0015) — bukan fakta yang tersimpan sendiri. Data
hanya menyimpan Pencatat; bila seseorang mencatat belanja orang lain, Pembeli yang tampil keliru.
Hanya untuk Pengeluaran; pada Pemasukan dan Transfer nama yang
sama tampil sebagai Pencatat, karena tidak ada yang dibeli (ADR-0019). Satu orang bisa punya banyak alias (nama panggilan, peran
seperti "istri", beda huruf besar-kecil); semuanya dibakukan ke satu nama baku (ADR-0017).
Bukan penerima transfer.
_Avoid_: buyer, pembayar

**No Resi**:
Penanda unik satu transaksi, sekaligus dasar deteksi duplikat.
_Avoid_: nomor struk, id, referensi, no. bukti

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
Dari mana sebuah baris berasal — Kanal tempat pesannya masuk (ditandai bila lewat Relay), atau
impor dari aplikasi lain. Di data tersimpan di kolom `channel`.
_Avoid_: channel, sumber

**Kanal**:
Layanan pesan tempat seseorang berbicara dengan asisten keuangan: WhatsApp, Telegram, atau
Discord. Semua Kanal membaca dan menulis Buku Kas yang sama; tidak ada Kanal yang punya catatan
sendiri.
_Avoid_: channel, platform

**Relay**:
Jalur masuk tidak langsung: pesan keuangan diketik ke asisten lain, yang meneruskannya apa adanya
ke asisten keuangan. Hanya teks — foto struk dan Bukti Transfer harus dikirim langsung. Pencatat
pada Relay adalah klaim asisten peneruskan, bukan identitas yang terautentikasi, jadi Asal-nya
ditandai agar baris yang lewat Relay bisa disaring dan diperiksa. Pesan Relay diawali **kepala**
dua baris (pengirim dan Kanal asal) yang dibuat asisten peneruskan; tanpa kepala yang lengkap,
asisten keuangan tidak menulis.
_Avoid_: forward, proxy, jembatan

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

### Sinkron Google Sheets

**Cermin**:
Salinan Buku Kas di Google Sheets, disinkronkan dua arah (ADR-0021). Bukan Buku Kas dan bukan
cadangan: bila keduanya berselisih, Buku Kas menang, dan menghapus Transaksi tetap hanya lewat bot.
_Avoid_: sheet utama, database Sheets

**Tab Laporan**:
Worksheet Cermin yang hanya-baca dan dihitung skrip: Ringkasan Bulanan, Per Kategori `<tahun>`,
Budget `<tahun>`, Saldo per Akun (ADR-0026). Ditimpa tiap sinkron; suntingan di sana diabaikan.
Kebalikannya worksheet "Buku Kas", satu-satunya tab Cermin yang bisa disunting.
_Avoid_: dashboard, pivot


**Snapshot Sinkron**:
Isi Cermin yang terakhir disepakati dengan Buku Kas (`data/sheets-snapshot.json`, tidak masuk git).
Dasar diff tiga arah: dibandingkan dengan Cermin sekarang dan Buku Kas sekarang untuk tahu siapa yang
mengubah apa. Bukan Transaksi dan tidak ikut hitungan apa pun.
_Avoid_: cache, backup Sheets

**Status Sinkron**:
Hasil sinkron terakhir (`data/sheets-status.json`, tidak masuk git): sukses/tertunda/ditolak/gagal, kapan, dan kapan
terakhir sukses. Dibaca penjaga kesehatan untuk memperingatkan sinkron yang mandek; hanya hitungan dan pesan galat,
tidak pernah isi Transaksi.
_Avoid_: log sinkron

### Waktu

**Pekan**:
Senin 00:00 sampai Minggu 23:59 WIB. Satuan waktu Laporan Mingguan dan pembandingnya
("pekan lalu"). Sebuah Pekan baru dilaporkan setelah ia tutup — jadi Transaksi yang dicatat
Minggu larut malam tetap masuk Pekan-nya. Kata "minggu" hanya dipakai untuk nama hari.
_Avoid_: minggu (untuk arti 7 hari), 7 hari terakhir, seminggu
