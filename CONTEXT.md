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

**Tempat**:
Toko, kedai, atau penyedia jasa tempat transaksi terjadi. Bank dan e-wallet bukan tempat —
itu cara bayar.
_Avoid_: merchant, toko, vendor

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
