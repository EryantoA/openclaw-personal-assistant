# Kolom `tempat` dibuang; nama toko hidup di dalam `item`

Kolom `tempat` dihapus dari `data/bills.csv`, `scripts/resi.py`, `scripts/export-excel.py`, dan
dari daftar pilihan `duplicate_check.match_fields`. Istilah **Tempat** dicabut dari `CONTEXT.md`
dan digantikan **Item**.

Alasannya sama persis dengan yang membunuh `jatuh_tempo` di [0003](0003-buku-kas-bukan-perencana-tagihan.md):
terisi **0 dari 288 baris**. Bedanya, `tempat` punya definisi yang paling rinci di seluruh
`CONTEXT.md` — lengkap dengan aturan bahwa bank dan e-wallet bukan tempat — dan tetap tak pernah
dipakai sekali pun selama empat bulan.

Yang membuat kasus ini berbeda dari `jatuh_tempo`: informasinya **tidak hilang**. Nama toko
selalu dicatat, hanya saja di dalam `item`, di belakang tanda pisah — `Susu UHT + Yakult -
Budiman Swalayan`, `Matcha Cream Sea Salt - Sanama Plus Marpoyan`. Pola itu muncul di 82 baris.
Kolomnya kosong bukan karena tokonya tidak penting, melainkan karena orang menulisnya di tempat
yang lebih alami: satu kalimat, sekali tulis, tanpa memilah mana barang mana toko.

Karena itu `CONTEXT.md` tidak sekadar kehilangan satu istilah. **Item** menggantikannya, dan
definisinya menyebut secara eksplisit bahwa nama toko adalah bagian darinya. Kebiasaan yang
sudah berjalan dinaikkan statusnya jadi konvensi, bukan dibiarkan jadi kebetulan.

## Considered Options

**Menyuruh bot mengisi `tempat` ditolak.** Nama tokonya sudah ada di `item`, jadi mengisi kolom
terpisah berarti menyimpan hal yang sama dua kali — dan dua salinan yang bisa berbeda lebih
buruk daripada satu yang utuh. Empat bulan bukti juga menunjukkan arah kebiasaannya tidak ke
sana.

**Memecah `item` jadi barang + toko secara otomatis ditolak.** Bisa saja memisah di tanda ` - `,
tapi hanya 82 dari 288 baris berpola itu, dan tanda pisah juga muncul di dalam nama barang.
Memecah data yang sudah tercatat rapi demi mengisi kolom yang tak ada yang minta adalah
pekerjaan yang risikonya lebih besar daripada manfaatnya.

## Consequences

Analisis per toko jadi tidak bisa dilakukan lewat satu kolom — harus mencocokkan teks di `item`.
Itu diterima: tak pernah ada yang memintanya selama empat bulan, dan datanya tetap ada kalau
kelak dibutuhkan.

Backup lama (`data/backups/bills_*.csv`, `data/*.bak`) masih berskema 11 kolom. Keduanya hanya
dibaca manusia, bukan oleh script — `export-excel.py` dan `resi.py` selalu membaca `bills.csv`
yang hidup. Cadangan tepat sebelum perubahan disimpan sebagai `data/bills.csv.pre-drop-tempat.bak`.

Pelajaran yang lebih umum, dan ini kedua kalinya: **kolom yang kosong selama berbulan-bulan
adalah data soal domainnya, bukan soal kedisiplinan penggunanya.** Sebelum membuangnya, cek dulu
apakah informasinya benar-benar tidak dibutuhkan (`jatuh_tempo`) atau cuma ditulis di kolom lain
(`tempat`) — jawabannya menentukan apakah istilahnya dihapus atau dipindahkan.
