# Cermin Sheets berformat buku kas, ditambah tab laporan hanya-baca

> **Mengubah sebagian** [0021](0021-sheets-cermin-dua-arah-csv-tetap-sumber.md): header worksheet
> "Buku Kas", worksheet "Ringkasan", dan perlindungan Google. Selebihnya 0021 tetap berlaku.
> Spec: [0005](../specs/0005-format-cermin-sheets.md).

Cermin yang ada menyalin 12 kolom `bills.csv` apa adanya: slug Inggris, tanggal teks ISO, satu
kolom `jumlah` yang artinya bergantung pada kolom `tipe`, dan satu worksheet "Ringkasan". Untuk
keluarga yang membukanya di HP, tabel itu terbaca seperti berkas data, bukan buku kas, dan tidak
menjawab "uangnya ke mana" per kategori. Pemilik ingin susunannya mengikuti pencatatan keuangan
yang lazim.

## Keputusan

**Buku Kas tidak berubah.** `bills.csv`, slug Inggris (ADR-0002), jalan tulis bot, dan sinkron
dua arah tetap. Yang berubah hanya cara Cermin menyajikan dan membaca balik.

**Worksheet "Buku Kas" (bisa disunting)**, 14 kolom berurutan:
Tanggal · Waktu · No Resi · Item · Kategori · Akun · Akun Tujuan · Pemasukan · Pengeluaran ·
Transfer · Saldo Bersama · Catatan · Pencatat · Asal.

- **Pemasukan / Pengeluaran / Transfer menggantikan `tipe` + `jumlah`.** Tiap baris mengisi tepat satu;
  tipe dibaca dari kolom yang terisi. Nol atau lebih dari satu → ditolak dan dilaporkan. Isian
  tidak bisa lagi saling bertentangan (tipe `pemasukan` dengan angka di sisi keluar). Header-nya
  persis tiga nilai Arah, kata yang sama dengan Pratinjau dan balasan bot (ADR-0019).
- **Kolom Saldo Bersama** berisi Saldo Bersama setelah tiap Item, dihitung skrip, urut tanggal → waktu → No Resi, mulai dari
  `opening_balance`, transfer tidak menggeser (ADR-0001, ADR-0010). Hanya-baca, ditimpa.
- **Kategori tampil sebagai Label Kategori** Bahasa Indonesia dengan dropdown. Peta slug → label
  di `budget.json` (`label_kategori`); label wajib unik agar bisa dipetakan balik ke tepat satu
  slug. Slug yang diketik tetap diterima; slug tanpa label tampil sebagai slug, sinkron tidak gagal.
- **Tanggal adalah nilai tanggal Sheets**, tampil `5 Sep 2026`; locale spreadsheet `in_ID` agar
  ketikan `5/9/2026` dibaca hari/bulan. Dibaca balik sebagai nomor seri lalu diubah ke ISO untuk
  CSV. Waktu tetap teks `HH:MM`. Uang berformat `Rp #,##0`.
- **Urutan kronologis, terlama di atas**, seperti buku kas cetak; baris yang diketik di bawah tetap
  di bawah dan kolom Saldo Bersama terbaca dari atas.
- **Header memakai kata yang sama dengan bot dan glosarium**, bukan istilah akuntansi cetak: "No Resi"
  (bukan "No. Bukti"; bot menulis `No Resi:` di setiap balasan), "Item" (bukan "Keterangan", yang
  hampir bersinonim dengan Catatan dan mengundang salah isi yang tidak bisa ditangkap sinkron), dan
  tiga nilai Arah untuk kolom uang, serta "Asal" untuk kolom `channel`. Satu-satunya nama tampil yang berbeda dari data adalah Label
  Kategori, karena slug-nya Inggris.
- Baris 1 dan kolom Tanggal–Item dibekukan; Waktu dan Asal dalam grup kolom tertutup.

**Worksheet laporan (hanya-baca, dihitung skrip, ditimpa tiap sinkron)**, urutan tab:
Ringkasan Bulanan → Per Kategori `<tahun>` → Budget `<tahun>` → Saldo per Akun → Buku Kas.

- **Ringkasan Bulanan** menggantikan "Ringkasan": Bulan · Jumlah Transaksi · Pemasukan ·
  Pengeluaran · Arus Kas Bulanan · Saldo Awal · Saldo Bersama Akhir Bulan — header memakai istilah
  glosarium, bukan nama lama ("Arus Kas Bulan", "Saldo Akhir"). Jumlah Transaksi menghitung No Resi
  unik tanpa Transfer dan Saldo Awal (ADR-0023); Ringkasan lama menghitung baris, jadi struk
  12 barang terbaca 12 transaksi.
- **Per Kategori `<tahun>`**: kolom Jan–Des + Total Tahun, Pemasukan lalu Pengeluaran per label,
  baris total dan Arus Kas Bulanan. Saldo Awal dan transfer tidak ikut. Bulan pertama pencatatan
  ditandai parsial. Satu tab per tahun, dibuat otomatis saat Transaksi pertama tahun itu ada.
- **Budget `<tahun>`**: Pengeluaran rutin vs Budget, persen, Di luar budget, status — angka dari
  `scripts/budget.py`, sama dengan peringatan bot. Semua bulan dibandingkan dengan **batas yang
  berlaku sekarang**, dengan keterangan di atas tabel (lihat Ditolak).
- **Saldo per Akun** hanya berisi pemberitahuan "belum aktif" selama `akun.json` belum lengkap;
  terisi sendiri sesudahnya. Angka per akun tidak pernah ditebak (ADR-0010). Kolom Akun di
  "Buku Kas" tetap teks bebas sampai itu selesai.

**Bagian hanya-baca ditandai dua kali:** latar abu-abu + catatan header, dan perlindungan Google
`warningOnly` (No Resi, Saldo Bersama, Asal, semua tab laporan). Ini peringatan sebelum menyunting,
bukan larangan; penolakan di skrip tetap penegak utamanya. Menutup satu batas yang diketahui di
ADR-0021.

**Label kategori baru diusulkan bot** di Pratinjau tambah kategori ("Slug `investment`, label
Investasi"), bisa dikoreksi di sana (ADR-0016). Label kembar ditolak.

**Peralihan lewat perintah sekali jalan** `sinkron-sheets.py --migrasi-format` (ada `--uji`),
dijalankan manual oleh pemilik: sinkron format lama dulu agar suntingan tertunda masuk CSV, tulis
format baru, hapus "Ringkasan" lama, pasang perlindungan, simpan snapshot baru paling akhir.
Sebelum migrasi, cron menolak dengan pesan yang menyebut perintah itu. Tautan dan izin berbagi
spreadsheet tidak berubah; filter tampilan dan catatan sel buatan keluarga di tab lama hilang dan
disebut di laporan migrasi.

## Akibat

- Snapshot Sinkron berganti format; format lama hanya dikenali oleh `--migrasi-format`.
- Diff tiga arah membandingkan nilai yang sudah dinormalkan (tipe+jumlah, slug, tanggal ISO),
  bukan sel mentah, supaya mengganti tampilan label atau format tidak terbaca sebagai suntingan.
- Mengubah label di `budget.json` mengubah tampilan seluruh kolom Kategori pada sinkron berikutnya;
  tidak ada data yang berubah.
- Locale spreadsheet menjadi bagian dari kontrak: skrip memeriksa dan memasangnya (`id_ID`).
- Snapshot menyimpan peta label yang terakhir ditulis; label lama tetap dikenali saat membaca balik,
  jadi baris yang belum sempat ditulis ulang tidak terbaca sebagai suntingan.
- **Batas yang diketahui:** tata letak (format, abu-abu, perlindungan, dropdown) dipasang ulang hanya
  saat tab itu ditulis, bukan diperiksa tiap sinkron — perlindungan yang dihapus pengguna kembali pada
  perubahan berikutnya di tab itu. Grup kolom dilipat hanya saat pertama dibuat. Kode locale `id_ID`
  belum diuji terhadap Google sungguhan sebelum migrasi pertama.

## Ditolak

- **Pembukuan berpasangan (debit/kredit, daftar akun ala akuntan):** terlalu berat untuk buku kas
  keluarga dan membongkar ADR-0005/0021 beserta seluruh jalan tulis bot.
- **Hanya merapikan tab laporan, "Buku Kas" tetap 12 kolom mentah:** tab yang paling sering dibuka
  dan disunting tetap terbaca seperti berkas data.
- **Riwayat batas Budget di `budget.json`:** akurat untuk bulan lama, tetapi menambah model data
  untuk `budget.py`, peringatan, dan laporan. Tab Budget menampilkan pola belanja terhadap satu
  acuan, bukan audit peringatan lama. Bila batas berganti lagi dan riwayat terasa perlu, itu
  keputusan terpisah.
- **Inisialisasi ulang manual / spreadsheet baru untuk peralihan:** yang pertama bisa membuang
  suntingan Sheet yang belum tersinkron; yang kedua mengganti tautan dan izin yang sudah dibagikan.
- **Terbaru di atas:** kolom Saldo Bersama terbaca terbalik dan baris yang baru diketik "pindah" ke atas
  setelah sinkron.
