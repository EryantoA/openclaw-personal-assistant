# Laporan Tahunan: bahan persiapan SPT dan zakat, bukan angka SPT

Keputusan dari sesi tanya-jawab dengan pemilik data, 10 Nov 2026. Aturan pajak dan zakat yang
dipakai bersumber di [riset SPT & zakat](../research/spt-tahunan-dan-zakat-penghasilan.md)
(diakses 10 Nov 2026). Mengikuti pola [0012](0012-laporan-bulanan-dihitung-skrip-dikirim-tanggal-6.md):
dihitung skrip tanpa model.

Tahun 2026 tinggal tujuh minggu, dan SPT Tahunan jatuh tempo 31 Maret. Buku Kas punya semua
Pemasukan dan saldo yang tercatat, tetapi **tidak tahu angka yang sebenarnya diminta SPT**. Gaji
yang masuk rekening adalah gaji neto, sesudah dipotong PPh 21, iuran pensiun, dan BPJS. Penghasilan
bruto, PPh terpotong, dan pengurang hanya ada di bukti potong kantor (BPA1, dulu 1721-A1).
Laporan yang mengaku menghitung pajak dari arus kas pasti salah dengan cara yang meyakinkan.

## Keputusan

- **Laporan Tahunan menyajikan angka Buku Kas dan aturan bersumber; skrip tidak menghitung PPh**,
  tidak menyebut kurang/lebih bayar, dan tidak memutuskan zakat wajib atau tidak. Judulnya
  menyatakan "bahan persiapan SPT & zakat — bukan angka SPT".
- **Cakupan data dinyatakan terang.** Bila catatan pertama tahun itu sesudah 1 Januari, laporan
  menyebut rentang yang tidak tercatat. Untuk 2026: Buku Kas mulai 26 Mar 2026, jadi
  1 Jan–25 Mar tidak tercatat.
- **Pemasukan setahun per Kategori**, satu angka keluarga. Saldo Awal dan Transfer tidak ikut
  (ADR-0008, ADR-0010). **Tidak dipisah per orang**: Buku Kas hanya menyimpan Pencatat, bukan
  penerima, dan Akun baru terisi sejak 9 Nov 2026. Pemisahan per orang untuk SPT datang dari
  bukti potong masing-masing.
- **Semua Item Pemasukan selain `salary` didaftar** (tanggal, jumlah, Item, Kategori, Pencatat)
  untuk dipilah pemilik. Kategori tidak dipercaya untuk keperluan pajak: menang arisan tercatat
  `bonus`, hadiah keluarga di `bonus`/`other`/`gift`, honor panitia di `bonus`. Skrip tidak
  menebak dari kata kunci.
- **Harta:** Saldo per Akun dan Saldo Bersama per 31 Des (bahan "kas dan setara kas", nilai
  nominal), dengan tanggal Rekonsiliasi terakhir tiap Akun. Lalu Pengeluaran Besar dan `jewelry`
  setahun sebagai "kandidat harta baru — cek" (harta dicatat dengan harga perolehan). Utang
  hanya pengingat.
- **Zakat penghasilan:** nisab tahunan dibaca dari Pengaturan (`nisab_zakat_tahunan`, per tahun;
  2026: Rp 91.681.728, Keputusan Ketua BAZNAS 15/2026), kadar 2,5% (PMA 52/2014 jo. 31/2019).
  Total Pemasukan `salary` keluarga dibandingkan dengan nisab, dan 2,5% darinya disebut **batas
  bawah**. BAZNAS menghitung dari gaji bruto; nisab berlaku per orang. Zakat yang dibayar
  dijumlahkan dari Kategori baru **`zakat`**. Infak (`donation`) disebut terpisah dan tidak
  dihitung sebagai zakat, karena hanya zakat ke BAZ/LAZ resmi yang bisa jadi pengurang (PMK
  114/2025).
- **Daftar dokumen:** BPA1 tiap kantor (paling lambat 31 Jan), bukti potong honor (BP21), bukti
  setor zakat, rekening koran 31 Des, data cicilan; tenggat SPT 31 Mar.
- **Dikirim:** bisa diminta lewat chat kapan saja (tahun berjalan diberi tanda "berjalan, per …",
  daftar dokumennya tetap), dan cron tanpa model **2 Februari 09:00 WIB** untuk tahun lalu,
  ke tujuan yang sama dengan Laporan Bulanan. 2 Februari dipilih karena BPA1 sudah harus ada dan
  masih dua bulan sebelum tenggat.
- **Tidak menyimpan angka dan tidak punya Koreksi.** Laporan ini terbit setahun sekali sebagai
  bahan kerja, bukan angka yang dirujuk laporan berikutnya.

## Ditolak

- **Estimasi PPh dari arus kas.** Gaji kas neto; PTKP, status suami-istri, dan PPh terpotong
  tidak ada di data. Angka yang hampir benar lebih berbahaya daripada tidak ada angka.
- **Pisah per Pencatat atau per Akun.** Pencatat bukan penerima (uang dari mertua dicatat
  suami); per Akun hanya bermakna sejak 9 Nov 2026.
- **Mencocokkan gaji ke Perkiraan `Gaji Elsi` / `Gaji Teikoku` untuk nisab per orang.**
  Pencocokan Perkiraan longgar (kategori + nominal ± toleransi); THR, gaji yang dirinci, dan gaji
  sebelum Perkiraan dibuat bisa salah tempat.
- **Merapikan Kategori lama lebih dulu.** Mengubah data sungguhan per baris; bisa dikerjakan
  terpisah lewat `buku.py` dengan izin pemilik. Laporan tetap benar dengan data apa adanya karena
  pemilahan diserahkan ke pemilik.
- **Zakat sebagai Kewajiban atau Perkiraan bulanan.** Mengubah data dan cek malam, di luar
  laporan tahunan.
- **Cron 6 Januari** (bersama Laporan Bulanan Desember): bukti potong biasanya belum ada.

## Consequences

- Kategori `zakat` (Label "Zakat", Kelompok Sosial & Keluarga) ditambahkan; Label `donation`
  berubah dari "Donasi & Zakat" menjadi "Donasi & Infak" supaya label tetap unik (ADR-0026).
  Sinkron Sheets mengenali label lama, jadi pergantian ini tidak terbaca sebagai suntingan.
  Zakat lewat potongan gaji tidak lewat kas dan tidak tercatat; itu memang sudah ada di BPA1.
- Nisab berubah tiap tahun. Tahun tanpa `nisab_zakat_tahunan` ditampilkan "nisab belum diisi",
  bukan ditebak dari tahun lain. Mengisinya butuh SK BAZNAS tahun itu.
- Pemasukan 2026 tidak lengkap (Jan–Mar tidak tercatat) dan laporan mengatakannya; angka
  zakat 2026 karenanya juga di bawah sebenarnya.
- Cron hidup di gateway (ADR-0009). Contohnya ada di `openclaw.json.example`; mendaftarkannya
  ke gateway adalah langkah pemilik.
- **Bukan nasihat pajak atau fikih.** Aturan yang "belum pasti" di riset (formulir tahun pajak
  2026, nisab gabungan suami-istri, perlakuan arisan) tidak dijadikan aturan di skrip.
