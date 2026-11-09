# Spec: Rekonsiliasi per Akun

Status: dikerjakan; keputusannya di [ADR-0027](../adr/0027-rekonsiliasi-per-akun-dan-selisih-rekonsiliasi.md).

## Problem Statement

Sejak fitur Akun aktif (cutover 9 Nov 2026), tidak ada yang memeriksa apakah Saldo Akun di Buku Kas
sama dengan Saldo Nyata di rekening, dompet, atau aplikasi. Transaksi terlupa, transfer salah akun,
dan baris tanpa akun membuat Saldo Akun melenceng diam-diam.

## Solution

Satu skrip, `scripts/rekonsiliasi.py`, yang dipanggil bot:

- `cek --akun A --saldo N [--per YYYY-MM-DD]` — hanya membaca: Saldo Akun per titik, selisih,
  kandidat penyebab (baris tanpa akun sejak titik Rekonsiliasi terakhir/cutover; baris hari ini
  tanpa jam). Tidak menulis apa pun.
- `simpan --akun A --saldo N [--per …] --cara cocok|dibiarkan` — menulis satu baris ke
  `data/rekonsiliasi.csv` (cocok hanya bila selisih Rp 0). "Transaksi dicatat" dari ADR-0027 = catat
  Transaksi yang terlupa lewat `catat.py`, lalu `cek` + `simpan --cara cocok` lagi.
- `tutup --akun A --saldo N [--per …] [--uji]` — membuat Transaksi Selisih Rekonsiliasi lewat
  `catat.catat` (`--uji` = Pratinjau), lalu menulis baris `selisih_ditutup` berisi No Resi-nya.

Aturan hitung `reconciliation` hidup di `buku_kas` (Jumlah Transaksi) dan `budget` (Budget).
Peringatan transaksi sebelum Rekonsiliasi terakhir lewat `buku.py` (ubah/hapus, termasuk dari
Sheets) dan `catat.py` (tambah). Laporan Bulanan mendapat satu baris pengingat; tab Saldo per Akun
mendapat bagian Rekonsiliasi.

## User Stories

1. Sebagai pemilik, saya ingin mengetik "saldo Mandiri Ryan 5.230.000" dan langsung tahu cocok atau
   selisih berapa, supaya saya bisa mengecek akun kapan saja.
2. Sebagai pemilik, saya ingin mengirim foto layar saldo dan bot mengonfirmasi angka yang terbaca
   sebelum membandingkan, supaya salah baca tidak jadi selisih palsu.
3. Sebagai pemilik, saya ingin bisa menyebut tanggal ("per 30 Nov"), supaya rekening koran akhir
   bulan bisa dicocokkan.
4. Sebagai pemilik, saya ingin diberi tahu transaksi hari ini tanpa jam yang ikut dihitung, supaya
   saya tahu sumber selisih palsu.
5. Sebagai pemilik, saya ingin melihat baris tanpa akun sejak pengecekan terakhir sebagai kandidat
   penyebab selisih.
6. Sebagai pemilik, saya ingin menutup selisih tak terjelaskan sebagai Selisih Rekonsiliasi lewat
   Pratinjau, supaya Saldo Akun sama dengan rekening tanpa uang yang hilang diam-diam.
7. Sebagai pemilik, saya ingin Selisih Rekonsiliasi ikut Saldo dan Arus Kas Bulanan tapi tidak ikut
   Budget dan jumlah transaksi.
8. Sebagai pemilik, saya ingin setiap pengecekan tercatat (termasuk yang cocok), supaya ada riwayat.
9. Sebagai pemilik, saya ingin diperingatkan saat mengubah, menghapus, atau menambah transaksi
   bertanggal sebelum rekonsiliasi terakhir sebuah akun, beserta besar geserannya.
10. Sebagai pemilik, saya ingin Laporan Bulanan menyebut akun yang belum dicek bulan lalu dan
    selisih yang masih terbuka.
11. Sebagai anggota keluarga, saya ingin tab Saldo per Akun menunjukkan kapan tiap akun terakhir
    dicek dan selisih yang masih terbuka.
12. Sebagai pemilik, saya ingin kategori `reconciliation` ditolak di pencatatan biasa, supaya hanya
    alur Rekonsiliasi yang membuatnya.

## Implementation Decisions

- Titik = datetime. Tanpa `--per`: sekarang; dengan `--per D`: D 23:59:59. Baris ikut bila
  (tanggal, waktu) ≤ titik; waktu kosong dianggap 00:00 (ikut) dan, bila tanggalnya hari titik,
  disebut di keluaran.
- Saldo Akun per titik = `saldo_awal` + efek baris sejak cutover, dengan aturan dan alias yang sama
  dengan `akun.saldo_per_akun` (Transfer: keluar dari akun, masuk ke akun_tujuan).
- `data/rekonsiliasi.csv`: `waktu_cek, titik, akun, saldo_nyata, saldo_akun, selisih, cara, no_resi`.
  Append-only, di luar git.
- Selisih Terbuka sebuah Akun = selisih baris terakhirnya bila `cara = dibiarkan`, selain itu 0.
- `catat.catat` menolak kategori `reconciliation` kecuali dipanggil dengan `rekonsiliasi=True`.
- Transaksi Selisih Rekonsiliasi: tipe = pengeluaran bila Saldo Nyata < Saldo Akun, pemasukan bila
  lebih besar; tanggal/waktu = titik; akun = Akun itu; item "Selisih rekonsiliasi <akun>";
  channel dari bot; pencatat dari pengirim.
- Peringatan geser: untuk tiap Akun dengan Rekonsiliasi, bandingkan Saldo Akun per titik terakhir
  sebelum dan sesudah perubahan; tidak nol → satu baris ⚠️.

## Testing Decisions

Tes lewat fungsi publik `rekonsiliasi`, `catat.catat`, `buku.jalankan`, `budget.pemakaian`,
`buku_kas.ringkas`, `laporan-bulanan.susun`, `sheets_laporan.grid_saldo_akun`, dengan berkas
sementara. Tidak ada data sungguhan di tes.

## Out of Scope

Neraca / Kekayaan Bersih (ditunda, ADR-0027), penguncian tutup buku, membaca mutasi bank otomatis.
