# Saldo adalah kas kumulatif, dan saldo awal dicatat sebagai baris transaksi

Laporan sempat memakai satu kata "Saldo" untuk pemasukan dikurangi pengeluaran dalam satu
bulan, padahal yang dimaksud pengguna adalah sisa kas yang dibawa terus antar bulan. Kami
memisahkan keduanya: **Arus Kas Bulan** berdiri sendiri per bulan, **Saldo** selalu kumulatif.
Konsekuensi langsung: saldo keseluruhan adalah saldo bulan terakhir, bukan penjumlahan kolom
saldo antar bulan.

Karena saldo kumulatif butuh titik mulai, **Saldo Awal** — kas yang sudah ada sebelum
transaksi pertama tercatat — disimpan sebagai satu baris biasa di `data/bills.csv`, bukan
sebagai field konfigurasi di `data/budget.json`.

## Considered Options

Menyimpannya sebagai konfigurasi di `budget.json` lebih benar secara model: saldo awal bukan
transaksi, tidak ada uang berpindah, dan menaruhnya di `bills.csv` memaksanya memakai
`tipe=pemasukan` sehingga kata "pemasukan" jadi berarti dua hal. Opsi itu ditolak karena
pendekatan baris justru membuat kode lebih sederhana — kolom kumulatif cukup menjumlah baris
berurutan tanggal, tanpa perlu membaca konfigurasi terpisah, dan baris saldo awal otomatis
menjadi titik mulai rantai tanpa perubahan kode apa pun.

## Consequences

`Total Pemasukan` di sheet Ringkasan akan memuat saldo awal begitu barisnya ditambahkan,
sehingga angka itu berhenti mencerminkan uang masuk sungguhan. Siapa pun yang ingin pemasukan
riil harus mengecualikan baris berkategori saldo awal. Keputusan apakah `export-excel.py`
melakukan pengecualian itu otomatis masih terbuka, menunggu nominal saldo awalnya diketahui.

Pendekatan lain yang sempat dipakai dan **dibatalkan**: menyisipkan baris `adjustment` per
bulan untuk menolkan saldo bulan-bulan yang minus. Cara itu mengarang Rp 21.054.246 pemasukan
yang tidak pernah ada dan merusak justru angka yang paling dipedulikan. Jangan diulang.
