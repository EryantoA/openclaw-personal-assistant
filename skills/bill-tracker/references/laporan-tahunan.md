# Laporan Tahunan: bahan SPT & zakat (ADR-0033)

Semua angka dari `scripts/laporan-tahunan.py`; jangan menghitung sendiri dan jangan membaca
`data/bills.csv`. Salin keluarannya **utuh**.

| Pengguna menyebut | Jalankan |
|---|---|
| laporan tahunan, bahan SPT, tahun lalu | `python3 scripts/laporan-tahunan.py` |
| tahun ini (belum tutup) atau tahun tertentu | `python3 scripts/laporan-tahunan.py --tahun YYYY` |
| "berapa zakat saya?", "sudah wajib zakat?", nisab | perintah yang sama untuk tahun yang ditanyakan |

## Pertanyaan lanjutan

- **Bukan nasihat pajak atau fikih.** Laporan ini bahan, bukan angka SPT. Jangan menyebut PPh
  terutang, kurang/lebih bayar, PTKP, atau "wajib/tidak wajib zakat". Kalau ditanya, jawab bahwa
  angkanya dari bukti potong kantor (BPA1) atau dari konsultan/KPP, dan keputusan di tangan pemilik.
- **Gaji di Buku Kas neto.** Angka 2,5% di laporan selalu batas bawah; jangan menyajikannya sebagai
  zakat yang harus dibayar.
- **Memilah pemasukan** ("julajula itu bukan penghasilan"): Kategori lama tidak diubah dari sini.
  Kalau pengguna ingin membetulkan Kategorinya, itu permintaan ubah biasa: bagian **Mengubah dan
  menghapus** di `AGENTS.md` (Pratinjau dulu).
- **Membayar zakat** dicatat sebagai Pengeluaran berkategori `zakat` (ke BAZNAS/LAZ resmi; minta
  bukti setornya disimpan). Infak, sedekah, dan sumbangan masjid tetap `donation`. Zakat yang
  dipotong lewat gaji tidak dicatat: uangnya tidak pernah masuk kas.
- **Nisab tahun yang belum diisi:** jangan menebak dari tahun lain. Sampaikan bahwa
  `nisab_zakat_tahunan` di `data/budget.json` perlu diisi dari SK BAZNAS tahun itu oleh pemilik.
- `--kirim` hanya untuk cron 2 Februari; bot tidak menjalankannya.
