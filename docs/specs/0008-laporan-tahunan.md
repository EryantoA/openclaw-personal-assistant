# Spec: Laporan Tahunan (bahan SPT & zakat)

Status: dikerjakan; keputusannya di [ADR-0033](../adr/0033-laporan-tahunan-bahan-spt-dan-zakat.md),
aturan bersumber di [riset](../research/spt-tahunan-dan-zakat-penghasilan.md).

## Problem Statement

Menjelang SPT Tahunan, pemilik harus mengumpulkan angka dari banyak tempat: pemasukan setahun,
saldo tiap rekening per 31 Desember, pembelian besar, dan zakat. Buku Kas punya sebagian, tapi
tidak pernah merangkumnya per tahun, dan sebagian angka SPT (bruto, PPh terpotong) memang tidak
bisa diambil dari kas.

## Solution

`scripts/laporan-tahunan.py` menyusun satu pesan dari Buku Kas, `akun.json`, `rekonsiliasi.csv`,
dan Pengaturan, tanpa model. Bisa diminta lewat chat; cron 2 Februari mengirim laporan tahun lalu.

```
python3 scripts/laporan-tahunan.py                  # tahun lalu, tampilkan saja
python3 scripts/laporan-tahunan.py --tahun 2026     # tahun tertentu (tahun ini = berjalan)
python3 scripts/laporan-tahunan.py --kirim          # cron 2 Feb: kirim tahun lalu
```

## User Stories

1. Sebagai pemilik, saya ingin tahu rentang tahun yang tidak tercatat, supaya tidak menganggap
   pemasukan setahun lengkap.
2. Sebagai pemilik, saya ingin Pemasukan setahun per Kategori, tanpa Saldo Awal dan Transfer.
3. Sebagai pemilik, saya ingin daftar semua Pemasukan selain gaji, supaya saya bisa memilah mana
   honor (cari bukti potong), hadiah keluarga, dan uang arisan.
4. Sebagai pemilik, saya ingin Saldo tiap Akun dan Saldo Bersama per 31 Desember beserta kapan
   terakhir dicocokkan, sebagai bahan daftar kas dan setara kas.
5. Sebagai pemilik, saya ingin melihat Pengeluaran Besar dan pembelian perhiasan setahun, supaya
   harta baru tidak terlupa.
6. Sebagai pemilik, saya ingin nisab dan 2,5% dari gaji tercatat sebagai batas bawah zakat,
   dengan pengingat bahwa angka sebenarnya dari gaji bruto per orang.
7. Sebagai pemilik, saya ingin zakat yang saya bayar terpisah dari infak.
8. Sebagai pemilik, saya ingin daftar dokumen dan tenggatnya.
9. Sebagai pemilik, saya ingin laporan tahun lalu datang sendiri tanggal 2 Februari.

## Implementation Decisions

- **Rentang:** 1 Jan–31 Des `--tahun`. Tahun berjalan: sampai hari ini, judul diberi
  "(berjalan, per <tgl>)", dan `--kirim` ditolak (kode 2). Tahun yang belum dimulai ditolak.
- **Cakupan:** tanggal paling awal di Buku Kas (semua baris bertanggal sah) dibanding 1 Januari.
  Tanpa baris di tahun itu: "Tidak ada transaksi tercatat".
- **Pemasukan per Kategori:** `buku_kas.ringkas` diberi `pemasukan_per_kategori` (aturan yang sama
  dengan `per_kategori` Pengeluaran). Label Kategori dipakai bila ada.
- **Daftar Pemasukan selain `salary`:** per baris (Item), urut tanggal; Saldo Awal dan Selisih
  Rekonsiliasi tidak ikut.
- **Harta:** `rekonsiliasi.saldo_akun` per akhir rentang bila fitur Akun aktif dan cutover tidak
  sesudah akhir rentang; selain itu satu kalimat alasan. Rekonsiliasi terakhir = catatan dengan
  `titik` tidak sesudah akhir rentang. Saldo Bersama = `buku_kas.saldo`.
- **Kandidat harta:** Transaksi Pengeluaran (per No Resi) yang total Item-nya ≥
  `pengeluaran_besar_mulai`, atau yang punya Item `jewelry`. `buku_kas.transaksi_pengeluaran`
  mengelompokkan per No Resi, dipakai juga oleh `pengeluaran_besar`.
- **Zakat:** `nisab_zakat_tahunan` di `budget.json` (objek tahun → rupiah). Kadar 2,5% tetap di
  skrip. Gaji = Pemasukan `salary`. Zakat dibayar = Pengeluaran `zakat`; infak = Pengeluaran
  `donation`.
- **Pengiriman:** `pengirim.kirim_ke_semua` ke `pengirim.tujuan_baku()` atau `--ke`; keluar 1 bila
  ada tujuan gagal. Tidak ada berkas simpanan.
- **Bot:** satu baris Peta pesan di `AGENTS.md`; tanya-jawab lanjutan di
  `skills/bill-tracker/references/laporan-tahunan.md`.

## Testing Decisions

`tests/test_laporan_tahunan.py` dengan berkas sementara: cakupan (mulai sesudah 1 Jan, tahun
kosong), Saldo Awal/Transfer tidak jadi Pemasukan, daftar selain gaji, Saldo Akun per 31 Des
mengabaikan transaksi tahun berikutnya, Akun belum aktif, kandidat harta per No Resi, zakat
(nisab ada/tidak, di atas/di bawah, `zakat` vs `donation`), tahun berjalan menolak `--kirim`,
pengiriman gagal → kode 1. `test_buku_kas` untuk `pemasukan_per_kategori` dan
`transaksi_pengeluaran`. `test_kontrak_prompt` untuk baris Peta pesan dan batas karakter.

## Out of Scope

- Menghitung PPh, PTKP, kurang/lebih bayar.
- Memisah pemasukan per orang.
- Merapikan Kategori pemasukan lama (`bonus` berisi arisan/hadiah) — terpisah, lewat `buku.py`.
- Mendaftarkan cron di gateway (langkah pemilik, ADR-0009).
- Daftar utang dari data.
