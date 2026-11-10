# Batas Kategori untuk kategori pilihan, di bawah Budget total

> **Memperluas** [0024](0024-budget-adalah-batas-belanja-rutin.md) (Budget = batas belanja rutin,
> Pengeluaran Besar di luar). Mengikuti [0027](0027-rekonsiliasi-per-akun-dan-selisih-rekonsiliasi.md)
> (Selisih Rekonsiliasi di luar Budget) dan [0026](0026-cermin-sheets-berformat-buku-kas-dan-tab-laporan.md)
> (tab Budget `<tahun>`). Spec: [0007](../specs/0007-batas-kategori.md).

Budget total Rp 8 jt menjawab "belanja rutin bulan ini masih wajar?", tapi tidak "di mana harus
direm". Belanja rutin Mei–Okt 2026 naik-turun 5,7–13,3 jt; tiga kategori stabil (muncul 6/6 bulan)
— Makan & Minum, Belanja Dapur, Kesehatan — sedangkan banyak kategori kecil hanya muncul 1–2 bulan.
Pemilik ingin anggaran per kategori ala pencatatan profesional.

## Keputusan

- **Batas Kategori hanya untuk kategori pilihan**, di bawah Budget total yang tetap batas utama.
  Kategori tanpa batas tetap ikut Budget. Jumlah semua Batas Kategori tidak harus sama dengan Budget.
- **Empat kategori pertama**, belanja yang rutin dan bisa ditahan saat peringatan datang. Angkanya
  median belanja rutin Mei–Okt 2026 dibulatkan ke atas — cara yang sama dengan Budget di ADR-0024:

  | Kategori | Median | Batas |
  |---|---|---|
  | Makan & Minum (`food`) | Rp 2.054.000 | Rp 2.100.000 |
  | Belanja Dapur (`groceries`) | Rp 1.138.000 | Rp 1.200.000 |
  | Belanja Lain (`shopping`) | Rp 549.000 | Rp 600.000 |
  | Hiburan (`entertainment`) | Rp 203.000 | Rp 250.000 |

  Kesehatan sengaja tanpa batas: "Kesehatan lewat batas" tidak akan membuat orang menunda berobat,
  jadi hanya menambah rasa bersalah tanpa mengubah keputusan.
- **Hanya belanja rutin**, sama dengan Budget: Pengeluaran Besar dan Selisih Rekonsiliasi tidak ikut.
  Mediannya pun dihitung tanpa keduanya.
- **Peringatan setelah mencatat hanya untuk kategori Transaksi itu**, bila mencapai `alert_persen`
  atau lewat; tidak menyimpan keadaan "sudah diperingatkan" (`check-bills.py` tetap tidak pernah
  menulis). Cek malam menyebut semua Batas Kategori yang ≥ `alert_persen`; "sisa budget" menampilkan
  semuanya.
- **Tempat tampil:** "sisa budget", cek malam, Laporan Bulanan (satu baris per Batas Kategori), dan
  Cermin tab Budget `<tahun>` (kolom per Batas Kategori di kanan tabel total, sejajar baris bulan;
  isinya persen terhadap batas, header menyebut batasnya — tabel terpisah di bawah tidak bisa, karena
  format Sheets berlaku per kolom). **Tidak** di Laporan Mingguan: batas bulanan terhadap satu Pekan menyesatkan.
- **Disimpan di `budget.json` → `budget_kategori`** (slug → nominal) dan diubah lewat
  `scripts/atur-budget.py`, bersama `budget_bulanan` dan `alert_persen`. Bot tidak lagi mengedit
  `budget.json` dengan tangan; tanpa Pratinjau, karena ini Pengaturan yang mudah dibalik, bukan Transaksi.

## Akibat

- `budget.pemakaian` mengembalikan rincian Batas Kategori; semua tampilan memakai satu hitungan itu.
- Kategori yang dihapus dari `kategori_custom` tapi masih punya Batas Kategori tetap dihitung dari
  datanya; `atur-budget.py` hanya menerima kategori yang sah, dan menolak `opening_balance`,
  `reconciliation`, dan `transfer`.
- Bot meneruskan kategori Transaksi yang baru tersimpan ke `check-bills.py --mode budget --kategori`.

## Ditolak

- **Pecah habis Budget ke semua kategori (amplop):** 20-an angka, dan kategori yang jarang muncul akan
  selalu "aman" atau tiba-tiba "lewat" — alarm yang diabaikan, persis masalah yang ADR-0024 perbaiki.
- **Ganti Budget total dengan jumlah Batas Kategori:** total tidak lagi ditetapkan sendiri, dan kategori
  tanpa batas jadi tak terjaga.
- **Rata-rata sebagai batas:** satu bulan ekstrem (Makan Jul 3,87 jt, Belanja Lain Agu 2,53 jt) ikut
  menaikkan batas.
- **Pengeluaran Besar ikut Batas Kategori:** satu kulkas membuat Belanja Lain 580% dan berbunyi tiap
  transaksi sampai akhir bulan.
- **Peringatan sekali saja per ambang:** butuh `check-bills.py` menyimpan keadaan. Bila pola sekarang
  terasa cerewet, itu keputusan terpisah yang berlaku juga untuk Budget total.
- **Batas proporsional di Laporan Mingguan:** pekan dengan acara makan bersama selalu "lewat", pekan
  berikutnya "aman" — informasinya tidak stabil.

## Di luar lingkup

"Lain-lain" rata-rata Rp 1,22 jt per bulan, terbesar kedua: tanda kategorisasi bot kurang tajam.
Batas untuk "Lain-lain" tidak menjawab "uangnya ke mana", jadi itu tugas terpisah.
