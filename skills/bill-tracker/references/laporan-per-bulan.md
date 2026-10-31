# Laporan per bulan (rekap semua bulan)

**Catatan:** bagian ini masih menyuruh model menghitung sendiri dari `bills.csv`, bertentangan dengan aturan *Laporan: JANGAN hitung sendiri* di `AGENTS.md`. Belum ada skripnya; sampai ada, angka per bulan bisa diambil dari `python3 scripts/laporan-bulanan.py --bulan YYYY-MM` satu per satu.

Trigger: `laporan per bulan`, `rekap per bulan`, `breakdown bulanan`, `laporan semua bulan`

Langkah:
1. Baca `data/bills.csv`
2. Kelompokkan transaksi per bulan berdasarkan kolom `tanggal` → kunci `YYYY-MM`
3. Untuk **tiap bulan** (urut kronologis), hitung total `pemasukan`, total `pengeluaran`, dan
   **Arus Kas Bulan** (= pemasukan − pengeluaran bulan itu saja). **Baris `tipe=transfer`
   dilewati seluruhnya** — uangnya hanya berpindah antar akun sendiri, tidak masuk dan tidak
   keluar dari kas keluarga
4. Hitung **Saldo** secara **kumulatif**: saldo bulan lalu + arus kas bulan ini. Saldo dibawa
   terus antar bulan — ia sisa kas, bukan selisih bulanan. Baris berkategori `opening_balance`
   (Rp 20.500.000, Mar 2026) **ikut** ke Saldo tapi **tidak** ke Total Pemasukan maupun Arus Kas
   Bulan — kalau ikut, laporan akan mengklaim ada Rp 20,5 juta uang masuk yang tidak pernah ada
5. Tampilkan **terpisah per bulan** — jangan digabung jadi satu total
6. Kalau fitur akun sudah aktif (`data/akun.json` terisi) dan pengguna memintanya, tambahkan saldo per akun dari `python3 scripts/akun.py` — **selalu disertai keterangan bahwa angka itu berlaku sejak tanggal cutover**, bukan untuk seluruh riwayat

Response format:
```
📅 REKAP PER BULAN

▸ Januari 2025
  📥 Pemasukan:   Rp 5.000.000
  📤 Pengeluaran: Rp 2.850.000
  💚 Arus Kas:    Rp 2.150.000  (12 transaksi)
  🏦 Saldo:       Rp 2.150.000

▸ Februari 2025
  📥 Pemasukan:   Rp 5.000.000
  📤 Pengeluaran: Rp 6.200.000
  🔴 Arus Kas:    -Rp 1.200.000  (18 transaksi)
  🏦 Saldo:       Rp 950.000

─────────────────────────
Saldo terakhir (akhir Februari 2025): Rp 950.000
```

> ⚠️ **Jangan tukar dua istilah ini.** `Arus Kas Bulan` berdiri sendiri per bulan; `Saldo`
> selalu kumulatif dan dibawa antar bulan. Menjumlahkan kolom `Saldo` antar bulan tidak
> bermakna — saldo keseluruhan = saldo bulan terakhir, bukan penjumlahan.

> 💡 Untuk versi Excel per-bulan (satu sheet tiap bulan), lihat bagian **Fitur Backup** → `export excel`.
