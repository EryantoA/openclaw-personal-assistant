# Ubah dan hapus data CSV lewat skrip: Pratinjau, salin dulu, ganti sekaligus

> **Diperluas oleh** [0021](0021-sheets-cermin-dua-arah-csv-tetap-sumber.md): untuk perubahan yang datang dari Google Sheets, laporan sinkron menggantikan ubah/hapus percakapan.

> **Memperluas** [0005](0005-bill-tracker-sebagai-sistem-resmi.md) dan
> [0016](0016-pratinjau-sebelum-simpan-untuk-semua-pencatatan.md): Pratinjau kini berlaku juga
> untuk mengubah dan menghapus transaksi yang sudah tercatat, bukan hanya mencatat.

Sampai 16 Okt 2026 hanya **menambah** transaksi yang punya jalan resmi (`catat.py`). Mengubah
atau menghapus berarti bot "membaca lalu menulis ulang file" — cara yang justru dilarang untuk
menambah karena model pernah merusak baris (13 kolom, resi karangan). "Hapus terakhir" menghapus
baris terakhir *berkas*, padahal satu struk bisa beberapa baris.

## Keputusan

- **`scripts/buku.py`** punya `cari`, `ubah`, `hapus`; menambah tetap `catat.py`. Aturan validasi
  satu baris hidup di satu tempat (`validasi.py`) dan dipakai keduanya, jadi baris yang diubah
  lolos cek yang sama dengan baris baru (kategori, jumlah, tanggal, jam, transfer, larangan
  `opening_balance`, cek Duplikat bila kolom pembandingnya berubah).
- **Pratinjau dua langkah.** `--uji` tidak menulis; ia mengeluarkan sebelum → sesudah dan
  `sidik` (hash permintaan + isi Transaksi). Eksekusi menolak tanpa `sidik` yang sama, jadi
  data yang sudah berubah sejak Pratinjau, atau permintaan yang berbeda, tidak diterapkan.
  Draf tetap hanya di percakapan (alasan sama dengan 0014/0016).
- **Salin dulu, ganti sekaligus.** Di bawah kunci berkas: cadangan ke `data/backups/`
  (`bills_sebelum-<aksi>_<cap>.csv`, ikut dipangkas retensi 30 hari `backup.sh`), proses di
  berkas kerja, verifikasi (header sama, baris lain persis sama), lalu `rename` atomik. Teks
  baris yang tidak disentuh dan akhir baris (CRLF/LF) dipertahankan apa adanya.
- **Kunci lewat `*.lock`**, bukan pada CSV: `rename` mengganti inode, dan penulis yang menunggu
  kunci pada inode lama akan menulis ke berkas yang sudah tak terpakai. `catat.py` ikut pindah.
- **Jejak Perubahan** `data/riwayat-ubah.csv` (append-only, tidak masuk git — 0004): waktu, aksi,
  No Resi, nomor Item, siapa, baris sebelum dan sesudah. Ia sengaja tanpa ubah/hapus lewat chat.
- **Sasaran tepat satu.** Satu panggilan menunjuk satu Transaksi (No Resi) atau satu Item
  (nomor urut); tidak ada hapus/ubah massal. `no_resi` dan `channel` tidak bisa diubah; baris
  `opening_balance` dan baris rusak tidak bisa disentuh.
- **Peringatan, tidak memblokir:** menghapus Transaksi yang dirujuk `lunas_resi` mengembalikan
  Kewajiban ke belum lunas; mengubah arus bulan yang sudah dilaporkan akan muncul sebagai
  Koreksi (ADR-0012).
- **Skema per CSV.** `buku.py` bekerja lewat deklarasi `Skema` (kolom, kunci, kolom terkunci,
  validator, penanda append-only). CSV baru cukup mendaftarkan satu `Skema`.

## Kenapa bukan di tempat lain

Tidak ada status draf di CSV dan bot tidak diberi izin tulis langsung: kontrak percakapan ada
di `AGENTS.md` dan dijaga `tests/test_kontrak_prompt.py` (hanya membuktikan teksnya ada, bukan
kepatuhan model). Pagar sebenarnya ada di skrip: sidik wajib, validasi, dan cadangan.

## Consequences

Memulihkan hapus yang keliru masih manual (salin dari `data/backups/` atau baca jejak); tidak
ada "undo" lewat chat. Berkas JSON (kewajiban, perkiraan, akun, pembeli, budget) bukan CSV dan
belum mendapat jalur yang sama.

`resi.py --backfill` masih menulis ulang `bills.csv` tanpa kunci `*.lock`; jangan dijalankan
bersamaan dengan `buku.py` atau `catat.py` (tugas sekali jalan, bukan cron).
Baris lama yang tidak lolos aturan sekarang (waktu kosong, kategori usang) tetap bisa diubah:
`ubah` hanya memvalidasi kolom yang sedang diubah, kolom lainnya dibiarkan apa adanya.
