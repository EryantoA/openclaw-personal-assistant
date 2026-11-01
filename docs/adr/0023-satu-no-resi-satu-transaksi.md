# Satu No Resi = satu Transaksi, satu baris = satu Item

`CONTEXT.md` mendefinisikan Transaksi sebagai satu baris, tapi `catat.py` menulis satu baris per
barang dalam satu struk, dan alur cari/ubah/hapus (ADR-0018) sudah memperlakukan **Transaksi =
No Resi** dan **Item = baris**. Laporan terbelah: harian dan per Pembeli menghitung No Resi unik,
mingguan, bulanan, dan rekap menghitung baris. Pada data Okt 2026 selisihnya ±11% (612 baris
pengeluaran, 543 No Resi unik; 28 struk multi-Item, maksimal 15 Item).

## Keputusan

- **Transaksi** = satu No Resi; **Item** = satu baris. Definisi di `CONTEXT.md` yang dibetulkan,
  bukan alur ubah/hapus.
- Hitungan "N transaksi" mengikuti angka di sebelahnya: di samping total Pengeluaran, Transaksi
  Pengeluaran; di samping Arus Kas Bulanan, Pemasukan ditambah Pengeluaran. **Transfer dan Saldo
  Awal tidak pernah dihitung** (ADR-0010, ADR-0008).
- Satu Transaksi yang barisnya jatuh di dua periode dihitung di keduanya: yang dihitung adalah No
  Resi unik di antara baris yang jatuh di periode itu. Baris tanpa No Resi (belum ada di data)
  dihitung satu Transaksi per baris.
- Aturan hitung (jumlah Transaksi dan total per Kategori) tinggal di `buku_kas.ringkas()`,
  satu tempat, bersama aturan Saldo Bersama dan Arus Kas Bulanan.
- Istilah keluarga masuk glosarium dan label balasan bot (Saldo Bersama, Arus Kas Bulanan);
  nama fungsi di kode (`saldo`, `arus_kas_bulan`) tidak diganti.

## Akibat

Angka "N transaksi" di Laporan Mingguan, Laporan Bulanan, dan rekap turun dibanding sebelumnya
(No Resi lebih sedikit daripada baris), dan di samping Pengeluaran tak lagi ikut menghitung
Pemasukan. Laporan yang sudah terkirim tidak berubah; `laporan-bulanan.json` tidak menyimpan
jumlah Transaksi, jadi tidak ada angka tersimpan yang perlu dimigrasi.

`laporan-pembeli.py` tidak memakai `ringkas()` karena butuh alias Pembeli dari `resi.py`
(ADR-0020); ia sudah memakai aturan yang sama dan dijaga tes silang.
