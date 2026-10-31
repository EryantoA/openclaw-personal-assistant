# Akun dan Transfer

Saldo per akun, aktivasi cutover, dan mencatat transfer antar akun sendiri (ADR-0010).

**Akun** = tempat uangnya berada: `Kas`, `Bank Utama`, `Tabungan`. Daftar resminya di
`data/akun.json`. Ini **berbeda dari cara bayar** — `Livin' by Mandiri`, `GoPay`, `Shopee
Pay` adalah cara bayar dan tetap ditulis di `catatan`. Orang bisa bayar pakai GoPay yang
saldonya ditarik dari Bank Utama: akunnya `Bank Utama`, cara bayarnya GoPay.

## ⚠️ Batas cutover — sebut ini setiap kali melaporkan saldo per akun

Saldo per akun **hanya berlaku sejak tanggal `cutover`** di `data/akun.json`. Transaksi
sebelum tanggal itu tidak menyebut akun sama sekali dan **tidak boleh ditebak** — sebelum
cutover, hanya **Saldo global** yang bermakna (ADR-0010).

Jangan pernah menyajikan saldo per akun seolah berlaku untuk seluruh riwayat.

## Status sekarang

Jalankan `python3 scripts/akun.py` untuk melihat saldo per akun. Kalau `saldo_awal` di
`data/akun.json` masih `null`, **fiturnya belum aktif** dan skripnya akan bilang begitu.
Jangan mengarang angkanya — hanya pemilik data yang tahu berapa isi tiap akun.

## Mengaktifkan (sekali saja, saat cutover)

Kalau pengguna minta mengaktifkan akun, tuntun begini:

1. Tanyakan saldo tiap akun **pada tanggal cutover**.
2. Isi `saldo_awal` tiap akun dan `saldo_global_saat_cutover` di `data/akun.json`.
3. Jalankan `python3 scripts/akun.py --cek`. **Jumlah semua `saldo_awal` harus sama
   dengan Saldo global pada tanggal cutover.** Kalau tidak sama, laporkan selisihnya
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
2026-09-02,transfer,transfer,Tarik tunai untuk belanja,500000,,whatsapp,Ayah,Bank Utama,Kas,09:00,TRX-20260902-0001
```

Transfer **tidak pernah** menyentuh Total Pemasukan, Total Pengeluaran, Arus Kas Bulan,
Saldo global, maupun budget. Ia hanya menggeser saldo antar akun. Kalau setelah mencatat
transfer angka Saldo global ikut berubah, itu **bug** — hentikan dan laporkan.

Konfirmasinya memakai kerangka bersama di `AGENTS.md`; baris `Arah:` menyebut kedua sisinya
(`🔁 Transfer (Bank Utama → Kas)`). Jangan menambah baris saldo: saldo akun hanya dari
`python3 scripts/akun.py`, tidak pernah dihitung atau dikarang di balasan.
