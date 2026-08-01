# Saldo Awal Rp 20.500.000, dan koreksi rekonsiliasi ADR 0005

Mengoreksi [0005](0005-bill-tracker-sebagai-sistem-resmi.md); menutup pertanyaan terbuka di
[0001](0001-saldo-adalah-kas-kumulatif.md).

ADR 0005 menyatakan dua hal yang keduanya salah: saldo keluarga **+Rp 17.307.887**, dan **saldo
awalnya nol**. Menghitung ulang dari `bills.csv` yang hidup menghasilkan −Rp 1.606.268 — selisih
hampir Rp 19 juta. Penelusuran ke `keuangan.json` menemukan sebabnya, dan menemukan kekeliruan
yang lebih mendasar.

## Selisihnya bukan data hilang

34 transaksi `keuangan.json` tidak punya baris `IMP-` di `bills.csv`, tapi **32 di antaranya
sudah ada dengan `no_resi` berbeda** — dicatat ganda oleh app lama dan bot baru, lalu
dide-duplikasi dengan benar saat rebuild. Setelah dikurangi satu baris saja, rekonsiliasinya
tutup sampai ke sen:

```
−7.230.386,33  (keuangan.json tanpa id 254)
+5.624.118,00  (39 baris non-keuangan)
─────────────
−1.606.268,33  = saldo bills.csv
```

Baris yang dimaksud: **id 254 — 20 Jul 2026, Rp 22.456.955, "Gaji + Bonus"**. Ia dicatat sebagai
angka borongan, lalu dirinci jadi id 255 (Rp 9.037.000) dan id 258 (Rp 280.000) tanpa yang
borongan dihapus. Rebuild membuangnya, dan itu benar.

Yang tidak benar: ADR 0005 justru **menghitungnya** — kalimat *"gaji 20–21 Juli senilai
Rp 38.047.224"* adalah `22.456.955 + 9.037.000 + 280.000 + 6.273.269`. Satu commit memperlakukan
baris yang sama dengan dua cara: dibuang dari data, dipakai di alasan. Angka +Rp 17.307.887 lahir
dari saldo `Kas` app lama yang memuat borongan itu, sementara `bills.csv` tidak.

## Saldo awal tidak pernah bisa nol

Kekeliruan yang lebih besar terlihat setelahnya. Dengan saldo awal nol, saldo kumulatif menyentuh
**−Rp 14.361.172** di akhir Juni. Kas tidak bisa minus 14 juta. Ini berlaku dengan maupun tanpa
id 254 — id itu ada di Juli, sementara titik terendahnya di Juni.

ADR 0005 menolak kesimpulan "tabungan awal minimal Rp 20,5 juta" sebagai artefak backup 9 Juli
yang belum lengkap. Penolakan itu benar untuk *cara* angka itu diperoleh, tapi salah untuk
angkanya. Pemilik data mengonfirmasi: **Rp 20.500.000**. Dicatat sebagai satu baris
`no_resi = SALDO-AWAL`, kategori `opening_balance`, bertanggal 26 Mar 2026 — sehari sebelum
transaksi pertama — sesuai pola yang sudah ditetapkan ADR 0001.

Hasilnya saldo tidak pernah minus lagi: terendah Rp 6.138.828 di Juni, berakhir
**Rp 18.893.732**.

## Considered Options

**Memasukkan kembali id 254 sebagai gaji ditolak** — pemilik data memastikan itu angka borongan
yang lalu dirinci. Konsekuensinya diterima: rinciannya hanya berjumlah Rp 15.590.269, jadi ada
Rp 6.866.686 dalam angka borongan itu yang tidak pernah bisa dijelaskan. Menambahkannya kembali
akan menghitung uang yang sama dua kali — kesalahan yang lebih mahal daripada membiarkan satu
angka lama tak terjelaskan.

Rp 6.866.686 itu diperiksa lewat mutasi bank sebelum ditutup, bukan langsung diasumsikan
borongan. Tiga rekening diperiksa tuntas untuk Juli 2026 — Mandiri (…4637, Eryanto), BCA
(…5154, Eryanto), dan BSI (…3291, Elsi) — dan **tidak satu pun punya transaksi di tanggal
20 maupun 21 Juli sama sekali**, apalagi kredit yang mendekati Rp 22.456.955, 9.037.000, atau
6.273.269. Pemeriksaan ini sekaligus mengonfirmasi sumber `PRK-001` (Gaji Elsi): kredit 28 Jul
Rp 3.402.360,64 dari "BSI KCP Pekanbaru UIR — By Dosen UIR Juli 26" di rekening Elsi, cocok
dalam toleransi 1% dengan nominal yang di-seed. Karena tiga rekening yang tersedia sudah habis
dan semuanya nihil, Rp 6.866.686 ditutup sebagai **tak terjelaskan secara permanen** —
kemungkinan besar tunai, rekening lain yang tidak tersedia untuk diperiksa, atau angka yang
dicatat manual tanpa transaksi bank yang menyertainya.

**Menyimpan saldo awal sebagai konfigurasi di `budget.json` ditolak lagi**, dengan alasan yang
sama seperti ADR 0001: baris biasa membuat rantai kumulatif jalan sendiri tanpa kode tambahan.
Ada alasan baru yang menguatkan: `budget.json` dilacak git, dan Rp 20,5 juta adalah nominal —
menaruhnya di sana melanggar [0004](0004-data-transaksi-tidak-masuk-git.md).

## Consequences

Pertanyaan yang ADR 0001 gantung — apakah `export-excel.py` mengecualikan saldo awal dari Total
Pemasukan — sekarang **dijawab ya**. Kategori `opening_balance` dikeluarkan dari `Total
Pemasukan` dan `Arus Kas Bulan`, tapi ikut menyeed rantai `Saldo`, dan tampil sebagai kolom
sendiri `Saldo Awal Tercatat` di sheet Ringkasan. Tanpa itu, laporan akan mengklaim ada Rp 20,5
juta uang masuk yang tidak pernah ada — persis kesalahan yang ADR 0001 larang.

`check-bills.py` tidak terpengaruh: budget hanya menghitung `pengeluaran`.

Siapa pun yang menghitung laporan manual (termasuk bot saat menjawab di chat) harus ingat
pengecualian ini. Itu ditulis di `skills/bill-tracker/SKILL.md`, tapi tetap satu aturan yang
harus diingat manusia — risiko yang diterima karena alternatifnya, menaruh saldo awal di luar
`bills.csv`, menambah kode di semua pembaca.

Pelajaran yang lebih umum: **saldo kas yang minus adalah bug, bukan temuan.** Empat bulan
laporan berjalan dengan saldo minus dan tak ada yang menandainya, karena tidak ada satu pun
pemeriksaan yang bertanya "mungkinkah angka ini nyata?". Kalau saldo kumulatif menyentuh negatif
lagi, itu tanda ada data yang hilang — bukan tanda keluarga ini kehabisan uang.
