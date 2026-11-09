# Akun dan Transfer

Saldo Akun, aktivasi cutover, dan mencatat transfer antar akun sendiri (ADR-0010).

**Akun** = tempat uangnya berada: uang tunai, rekening bank, atau saldo e-wallet, dengan nama
`<Tempat> <Panggilan>` (mis. `Tunai Ayah`, `GoPay Ibu`). Daftar resminya **hanya** di
`data/akun.json`; `catat.py` dan `buku.py` menolak nama lain dan menyebut pilihannya — teruskan
pilihan itu ke pengguna sebagai pertanyaan, jangan memilih sendiri (ADR-0027). Ini **berbeda dari
cara bayar** — QRIS atau `Livin' by Mandiri` ditulis di `catatan`. Isi ulang e-wallet = transfer
ke Akun e-wallet; belanja dari saldonya = pengeluaran dari Akun e-wallet. Rekening orang di luar
rumah tangga bukan Akun: uang ke sana adalah pengeluaran.

## ⚠️ Batas cutover — sebut ini setiap kali melaporkan saldo per akun

Saldo Akun **hanya berlaku sejak tanggal `cutover`** di `data/akun.json`. Transaksi
sebelum tanggal itu tidak menyebut akun sama sekali dan **tidak boleh ditebak** — sebelum
cutover, hanya **Saldo Bersama** yang bermakna (ADR-0010).

Jangan pernah menyajikan saldo per akun seolah berlaku untuk seluruh riwayat.

## Status sekarang

Jalankan `python3 scripts/akun.py` untuk melihat saldo per akun. Kalau `saldo_awal` di
`data/akun.json` masih `null`, **fiturnya belum aktif** dan skripnya akan bilang begitu.
Jangan mengarang angkanya — hanya pemilik data yang tahu berapa isi tiap akun.

## Mengaktifkan (sekali saja, saat cutover)

Kalau pengguna minta mengaktifkan akun, tuntun begini:

1. Cutover = hari pengguna mengecek isi tiap akun sendiri (ADR-0027). Tanyakan angka yang
   **dilihat** di dompet/aplikasi, sebelum ada transaksi hari itu. Akun yang belum bisa dicek
   tetap `null` — jangan diisi sisa hitungan.
2. Isi `saldo_awal` tiap akun dan `saldo_global_saat_cutover` di `data/akun.json`.
3. Jalankan `python3 scripts/akun.py --cek`. **Jumlah semua `saldo_awal` harus sama
   dengan Saldo Bersama pada tanggal cutover.** Kalau tidak sama, laporkan selisihnya
   apa adanya dan tanyakan mana yang keliru — **jangan pernah menyerap selisih itu**
   ke salah satu akun supaya angkanya "pas".
4. Tambahkan `"akun"` ke `duplicate_check.match_fields` di `data/budget.json`
   (keterangannya sudah ada di file itu). **Baru pada langkah ini**, tidak sebelumnya.
5. Sejak saat itu, setiap transaksi baru **wajib** menyebut akun. Kalau pengguna tidak
   menyebutkannya, tanyakan — jangan menebak.

## Mencatat transfer

Memindahkan uang antar akun sendiri bukan pemasukan dan bukan pengeluaran.

```
tarik tunai 500rb dari bank
pindah 2 juta ke tabungan
```

Catat lewat `catat.py` dengan `"tipe": "transfer"`, `"akun"` = asal, `"akun_tujuan"` = tujuan, dan
item berkategori `transfer` (di luar `kategori_custom`; `catat.py` menolak transfer tanpa dua akun).

```
2026-09-02,transfer,transfer,Tarik tunai untuk belanja,500000,,whatsapp,Ayah,Mandiri Ayah,Tunai Ayah,09:00,TRX-20260902-0001
```

Transfer **tidak pernah** menyentuh Total Pemasukan, Total Pengeluaran, Arus Kas Bulanan,
Saldo Bersama, maupun budget. Ia hanya menggeser saldo antar akun. Kalau setelah mencatat
transfer angka Saldo Bersama ikut berubah, itu **bug** — hentikan dan laporkan.

Konfirmasinya memakai kerangka bersama di `AGENTS.md`; baris `Arah:` menyebut kedua sisinya
(`🔁 Transfer (Mandiri Ayah → Tunai Ayah)`). Jangan menambah baris saldo: saldo akun hanya dari
`python3 scripts/akun.py`, tidak pernah dihitung atau dikarang di balasan.
