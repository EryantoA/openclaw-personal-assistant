# Budget adalah batas belanja rutin, bukan uang yang dimiliki

Budget Rp 7.000.000 dibaca seperti "uang kami sebulan", padahal pemasukan keluarga naik-turun
(Mei–Okt 2026: Rp 7,3 jt sampai Rp 24,6 jt per bulan) dan angka itu diisi manual. Peringatan
Oktober ("BUDGET HABIS … Sisa Rp 754.771 (MINUS!)") terdengar seperti uang sudah minus, padahal
hanya batas yang terlewati. Batas 7 jt juga meleset: dikalibrasi dari belanja rutin Apr–Jul di
luar transaksi ≥ Rp 1 jt, tapi peringatan menghitung **semua** pengeluaran. Pengeluaran rutin
sendiri melewati 7 jt di Juli, Agustus, September, dan Oktober, jadi alarm hampir selalu menyala.

## Keputusan

- **Budget = batas belanja rutin yang kami tetapkan sendiri**; tidak mengikuti pemasukan.
  Kecukupan uang dijawab **Arus Kas Bulanan**. Satu alat, satu pertanyaan. (Batas yang mengikuti
  pemasukan ditolak: pemasukan datang tidak teratur, jadi batasnya nol atau kecil di awal bulan
  dan baru benar saat sudah terlambat.)
- **Pengeluaran Besar** = satu Transaksi (No Resi, ADR-0023) yang jumlah seluruh Item-nya
  >= `pengeluaran_besar_mulai` (Rp 1.000.000, di `data/budget.json`). Tidak dihitung ke Budget,
  tampil terpisah sebagai "Di luar budget". Per Transaksi, bukan per kategori: pada data Mei–Okt
  hanya 7 dari 521 Transaksi ≥ 1 jt, tersebar di lima kategori.
- **Batas Rp 8.000.000** (median pengeluaran rutin Mei–Okt Rp 8,3 jt), peringatan di 80%.
- **Bunyi pesan:** "Mendekati batas Budget" (80–99%) dan "Lewat batas Budget" (100%+), "Masih
  bisa" atau "Lewat Rp …" sebagai ganti "Sisa … MINUS", baris Di luar budget, baris Arus Kas
  Bulanan, dan nama bulan Indonesia.
- **Kalimat saran** disusun skrip dari aturan (sisa hari, maksimal per hari, kategori rutin
  terbesar), bukan model, karena pesan ini jalan dari cron (ADR-0011, ADR-0013).
- **Satu perhitungan** (`scripts/budget.py`) untuk pesan peringatan, "sisa budget", Laporan
  Mingguan, dan Laporan Bulanan.

## Akibat

Persen Budget di semua tempat turun dibanding sebelumnya bila ada Pengeluaran Besar. Laporan
Bulanan dan Mingguan menampilkan baris "Di luar budget" (Mingguan hanya bila ada). Angka total
Pengeluaran di laporan tidak berubah: Pengeluaran Besar tetap Pengeluaran untuk Arus Kas
Bulanan dan Saldo Bersama.

## Belum diputuskan

Membuat pesan Budget memperhitungkan Perkiraan pemasukan yang belum masuk (mis. gaji tgl 26)
ditunda; pesan hanya menyebut Arus Kas Bulanan apa adanya.
