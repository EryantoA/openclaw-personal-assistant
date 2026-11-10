# Tema warna Cermin Sheets: Indigo, Olive, Hijau, Bordeaux

> **Mengubah sebagian** [0026](0026-cermin-sheets-berformat-buku-kas-dan-tab-laporan.md): warna
> tanda hanya-baca (abu-abu → Olive pucat). Perlindungan `warningOnly` dan selebihnya 0026 tetap.
> Spec: [0005](../specs/0005-format-cermin-sheets.md).

Cermin hanya punya header tebal dan latar abu-abu untuk bagian hanya-baca. Di HP, arah uang, angka
minus, dan status Budget terbaca sama polosnya dengan teks biasa. Pemilik memilih palet empat warna:
Bordeaux Red `#A21232`, Deep Indigo `#1A1831`, Forest Green `#20615B`, Antique Olive `#DECE9C`.

## Keputusan

Setiap warna punya satu arti, dan arti itu sama di semua tab:

| Elemen | Tampilan |
|---|---|
| Baris header, semua tab | Latar Indigo, teks tebal Olive (kontras ±11:1) |
| Kolom Pemasukan (Buku Kas) | Teks Hijau |
| Kolom Pengeluaran (Buku Kas) | Teks Bordeaux |
| Kolom Transfer | Teks bawaan (tidak menggeser Saldo Bersama, ADR-0010) |
| Bagian hanya-baca | Latar Olive pucat `#F5F0DC`, menggantikan abu-abu `#EDEDED` |
| Angka < 0 di tab laporan dan kolom Saldo Bersama | Teks Bordeaux; angka positif tetap bawaan |
| Status Budget | Aman: teks Hijau · Mendekati: teks Bordeaux · Lewat: teks putih tebal di latar Bordeaux |

- **Warna teks, bukan latar,** untuk arah uang: latar merah/hijau di ratusan baris melelahkan di HP
  dan bertabrakan dengan tanda hanya-baca.
- **Hijau hanya berarti uang masuk / Aman**, Bordeaux hanya berarti uang keluar / minus / peringatan.
  Angka positif di laporan tidak dihijaukan agar Hijau tidak kehilangan arti.
- **"Lewat" satu-satunya sel berlatar Bordeaux**, sama dengan 🚨 Lewat di bot (ADR-0031); Mendekati
  lebih ringan, setara ⚠️.
- **Angka minus dan Status diwarnai skrip per sel tiap sinkron**, bukan lewat aturan pewarnaan
  bersyarat Sheets: nilainya memang dihitung skrip, aturan bersyarat akan menumpuk tiap sinkron dan
  tak bisa dibedakan dari aturan buatan pengguna, dan pola angka Sheets tidak menerima warna hex.
  Warna teks lama di bagian hanya-baca dibersihkan dulu setiap tulis, jadi tanda yang sudah tidak
  berlaku hilang sendiri.
- **Header dipasang sesudah latar hanya-baca**, agar sel header di kolom hanya-baca tetap Indigo.
- Tanda hanya-baca tetap dua: warna latar + perlindungan `warningOnly`; hanya warnanya yang berganti.

## Ditolak

- **Header Bordeaux:** merah di setiap tab terbaca sebagai peringatan, dan Bordeaux tak lagi bebas
  untuk uang keluar.
- **Tetap abu-abu untuk hanya-baca:** tak perlu ADR, tetapi abu netral terlihat asing di samping palet.
- **Kuning untuk Mendekati:** lebih seperti lampu lalu lintas, tetapi keluar dari palet.
- **Semua angka positif hijau:** laporan terlalu ramai.
