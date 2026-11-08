# Spec: Cermin Sheets berformat buku kas + tab laporan

Status: siap dikerjakan; keputusannya di [ADR-0026](../adr/0026-cermin-sheets-berformat-buku-kas-dan-tab-laporan.md).
Memperluas spec [0004](0004-sinkron-google-sheets.md) dan [ADR-0021](../adr/0021-sheets-cermin-dua-arah-csv-tetap-sumber.md).

## Problem Statement

Cermin Google Sheets menyalin 12 kolom `bills.csv` mentah: slug Inggris, tanggal teks ISO, satu
kolom `jumlah` yang artinya bergantung pada `tipe`, dan satu worksheet "Ringkasan". Keluarga yang
membukanya di HP melihat berkas data, bukan buku kas. Tidak ada tampilan per kategori, budget,
atau Saldo Bersama per baris, dan bagian yang tidak boleh disunting baru ketahuan setelah suntingannya
ditimpa.

## Solution

Buku Kas (`bills.csv`) dan jalan tulisnya tidak berubah. Cermin disajikan ulang:

- Worksheet **"Buku Kas"** dengan 14 kolom gaya buku kas (Pemasukan / Pengeluaran / Transfer / Saldo Bersama),
  Label Kategori Indonesia dengan dropdown, tanggal sungguhan, format Rupiah, kronologis.
- Empat **Tab Laporan** hanya-baca: Ringkasan Bulanan, Per Kategori `<tahun>`, Budget `<tahun>`,
  Saldo per Akun.
- Bagian hanya-baca berlatar abu-abu dan dilindungi `warningOnly`.
- Peralihan lewat `sinkron-sheets.py --migrasi-format`.

## User Stories

1. Sebagai anggota keluarga, saya ingin melihat uang masuk dan keluar di kolom terpisah, supaya
   arah uang terbaca sekilas tanpa membaca kolom tipe.
2. Sebagai anggota keluarga, saya ingin kolom Saldo Bersama di tiap baris, supaya saya tahu
   saldo setelah tiap transaksi seperti di buku kas cetak.
3. Sebagai pemilik, saya ingin menambah atau mengubah transaksi dengan mengisi tepat satu dari
   Pemasukan/Pengeluaran/Transfer, dan baris yang mengisi nol atau lebih dari satu ditolak dengan alasan
   jelas, supaya tipe tidak bisa salah.
4. Sebagai anggota keluarga, saya ingin kategori tampil dalam Bahasa Indonesia dan dipilih dari
   dropdown, supaya tidak perlu hafal slug dan tidak salah ketik.
5. Sebagai pemilik, saya ingin slug yang saya ketik langsung tetap diterima, supaya kebiasaan
   lama tidak ditolak.
6. Sebagai pemilik, saya ingin slug tanpa label tampil sebagai slug tanpa membuat sinkron gagal,
   supaya kategori baru tidak menghentikan Cermin.
7. Sebagai anggota keluarga, saya ingin tanggal tampil `5 Sep 2026` dengan pemilih kalender dan
   filter tanggal, supaya mencari transaksi per rentang mudah.
8. Sebagai pemilik, saya ingin tanggal yang diketik `5/9/2026` dibaca 5 September, dan tanggal
   yang tak terbaca ditolak dan dilaporkan.
9. Sebagai anggota keluarga, saya ingin angka uang tampil `Rp 1.250.000`.
10. Sebagai pemilik, saya ingin baris diurutkan terlama di atas, supaya kolom Saldo Bersama terbaca
    dari atas dan baris yang saya ketik di bawah tetap di bawah.
11. Sebagai anggota keluarga di HP, saya ingin header dan kolom Tanggal–Item dibekukan dan
    Waktu/Asal terlipat, supaya tabel tetap terbaca saat digeser.
12. Sebagai anggota keluarga, saya ingin tab Ringkasan Bulanan dengan bulan Indonesia dan header
    Bulan · Jumlah Transaksi · Pemasukan · Pengeluaran · Arus Kas Bulanan · Saldo Awal · Saldo
    Bersama Akhir Bulan, supaya istilahnya sama dengan laporan bot.
12a. Sebagai pemilik, saya ingin Jumlah Transaksi di Ringkasan Bulanan sama dengan laporan bot (No
    Resi unik, tanpa Transfer dan Saldo Awal), bukan jumlah baris.
13. Sebagai pemilik, saya ingin tab Per Kategori per tahun (Jan–Des + Total Tahun, Pemasukan dan
    Pengeluaran per label, Arus Kas Bulanan), supaya saya tahu uangnya ke mana.
14. Sebagai pemilik, saya ingin bulan pertama pencatatan (Mar 2026) ditandai parsial.
15. Sebagai pemilik, saya ingin tab Budget per tahun dengan angka yang sama dengan peringatan
    bot, dibandingkan dengan batas yang berlaku sekarang dan diberi keterangan.
16. Sebagai pemilik, saya ingin tab Saldo per Akun menyatakan "belum aktif" selama `akun.json`
    belum lengkap, bukan menampilkan angka karangan.
17. Sebagai pemilik, saya ingin tab tahun baru dibuat otomatis dan langsung dilindungi.
18. Sebagai anggota keluarga, saya ingin diperingatkan Google sebelum menyunting bagian
    hanya-baca, supaya saya tidak kaget suntingan saya ditimpa.
19. Sebagai pemilik, saya ingin bot mengusulkan Label Kategori saat menambah kategori, dan
    menolak label kembar.
20. Sebagai pemilik, saya ingin satu perintah migrasi yang menyerap suntingan tertunda dulu, lalu
    menulis format baru, dengan mode `--uji`.
21. Sebagai pemilik, saya ingin cron menolak dengan pesan jelas sebelum migrasi dijalankan,
    bukan gagal tanpa petunjuk.
22. Sebagai pemilik, saya ingin mengganti label di `budget.json` hanya mengubah tampilan, tidak
    terbaca sebagai suntingan dan tidak mengubah CSV.

## Implementation Decisions

- **Pemetaan dua arah di satu modul murni** (`scripts/sheets_sync.py` atau modul format baru):
  `baris_csv → baris_sheet` dan `baris_sheet → nilai_csv | alasan_tolak`. Diff tiga arah tetap di
  atas nilai yang sudah dinormalkan (tipe, jumlah, slug, tanggal ISO), sehingga perubahan
  label/format tidak terbaca sebagai suntingan.
- **Snapshot** menyimpan grid ternormalisasi format baru plus penanda versi format. Snapshot tanpa
  penanda = format lama → hanya `--migrasi-format` yang menerimanya.
- **Kolom Saldo Bersama** dihitung dari fungsi saldo yang sama dengan laporan (`buku_kas`), tidak
  dihitung ulang dengan aturan sendiri.
- **Jumlah Transaksi** memakai hitungan yang sama dengan laporan (ADR-0023), menggantikan hitungan
  baris di `grid_ringkasan`.
- **Tab Laporan** dirakit dari fungsi yang sudah ada (`buku_kas`, `budget.pemakaian`); tidak ada
  definisi angka baru.
- **`budget.json` → `label_kategori`** (objek slug → label). Validasi keunikan di jalur simpan
  kategori; sinkron menerima peta yang tidak lengkap.
- **Klien Sheets** (`sheets_google.py`) bertambah: menulis nilai tanggal (nomor seri), membaca
  `UNFORMATTED_VALUE`, number format `Rp #,##0` dan tanggal `d mmm yyyy`, data validation dropdown,
  frozen rows/cols, column group, latar abu-abu + catatan header, protected range `warningOnly`,
  locale `in_ID`, membuat/menghapus worksheet. Klien palsu di tes mencatat permintaan format
  tanpa memanggil Google.
- **Protected range dan format** dipasang saat migrasi dan saat tab baru dibuat; sinkron biasa
  memeriksa dan memasang ulang bila hilang.
- **Bot:** `skills/bill-tracker/references/kategori-custom.md` mendapat langkah label di
  Pratinjau dan aturan label unik.

## Testing Decisions

- Tes perilaku lewat antarmuka publik `sinkron()` dengan klien Sheets palsu, seperti tes yang ada.
- Kasus wajib: tepat satu kolom uang (0, 1, 2, 3 terisi); label → slug, slug langsung, label tak
  dikenal, slug tanpa label; tanggal seri, teks `5/9/2026`, teks tak terbaca; kolom Saldo Bersama
  dengan multi-Item, transfer, dan `opening_balance`; suntingan di kolom Saldo Bersama/tab laporan
  diabaikan; ganti label tidak menghasilkan suntingan; idempoten; migrasi dari snapshot lama
  (suntingan tertunda masuk dulu), `--uji` tidak menulis, cron menolak sebelum migrasi; tab tahun
  baru dibuat; Jumlah Transaksi struk multi-Item = 1 dan tanpa Transfer/Saldo Awal; Saldo per Akun "belum aktif" saat `akun.json` tak lengkap.
- Tes yang ada untuk sinkron dan klien Google diperbarui ke format baru, bukan dihapus.

## Out of Scope

- Mengaktifkan fitur akun (membakukan nama akun, mengisi saldo awal) — tugas terpisah.
- Riwayat batas Budget.
- Label Kategori di balasan bot dan laporan WhatsApp/Telegram/Discord.
- Pembukuan berpasangan.
