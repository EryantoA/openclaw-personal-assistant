# Rekonsiliasi: mencocokkan Saldo Akun dengan saldo sungguhan

Pengguna melaporkan **Saldo Nyata** satu Akun (ADR-0027): `saldo Mandiri Ryan 5.230.000`,
`saldo BSI Elsi per 30 Nov 2.100.000`, atau **foto layar saldo** aplikasi bank/e-wallet. Ini
**bukan** pencatatan Transaksi. Semua angka dari `scripts/rekonsiliasi.py`; jangan menghitung sendiri.

Bedakan dari pertanyaan: "berapa saldo Mandiri?" (tanpa angka) = `python3 scripts/akun.py`.

## 1. Pastikan Akun dan angkanya

- Nama Akun harus salah satu dari `data/akun.json` (mis. `Tunai Ryan`, `Mandiri Ryan`). Kalau
  pengguna menyebut sebagian ("saldo Mandiri") dan ada lebih dari satu yang cocok, tanyakan.
- **Foto layar:** baca nominal dan, bila terlihat, bank + nomor rekening untuk menebak Akun. Lalu
  tanyakan dulu, jangan langsung dijalankan:
  ```
  Saldo terbaca Rp 5.230.000 untuk Mandiri Ryan, benar?
  ```
  Foto saldo **bukan** Bukti Transfer dan tidak pernah dicatat sebagai Transaksi. Kalau tidak jelas
  gambar itu saldo atau bukti transfer, tanyakan.
- Tanggal hanya bila pengguna menyebutnya ("per 30 Nov", rekening koran) → `--per YYYY-MM-DD`.
  Tanpa tanggal = saldo saat ini.

## 2. Cek

```bash
python3 scripts/rekonsiliasi.py cek --akun "Mandiri Ryan" --saldo 5230000 [--per 2026-11-30]
```
Salin keluarannya **utuh** sebagai balasan.

- `✅ Cocok` → langsung catat hasilnya, lalu balas keluaran cek + `Tercatat.`:
  ```bash
  python3 scripts/rekonsiliasi.py simpan --akun "Mandiri Ryan" --saldo 5230000 --cara cocok [--per …]
  ```
- `Selisih: …` → balas keluaran cek (sudah memuat kandidat penyebab dan tiga pilihan), lalu
  **tunggu jawaban**. Jangan memilih sendiri.

## 3. Pilihan pengguna bila selisih

1. **Catat transaksi yang terlupa** → ikuti **Mencatat transaksi** di `AGENTS.md` (Pratinjau → simpan,
   dengan `akun` diisi). Setelah semuanya tersimpan, jalankan `cek` lagi dengan saldo dan `--per` yang
   sama, lalu ikuti langkah 2.
2. **Tutup sebagai Selisih Rekonsiliasi** → Pratinjau dulu:
   ```bash
   python3 scripts/rekonsiliasi.py tutup --akun "Mandiri Ryan" --saldo 5230000 --channel <kanal> \
     --pencatat "<nama pengirim>" --uji [--per …]
   ```
   Salin keluarannya sebagai Pratinjau dan tanya `Simpan? (ya / batal)`. Setelah `ya`, jalankan
   perintah yang sama **tanpa** `--uji` dan salin keluarannya.
3. **Biarkan** →
   ```bash
   python3 scripts/rekonsiliasi.py simpan --akun "Mandiri Ryan" --saldo 5230000 --cara dibiarkan [--per …]
   ```

## Aturan

- Kategori `reconciliation` **hanya** lewat `rekonsiliasi.py tutup`. `catat.py` menolaknya.
- Baris `⚠️ Transaksi ini bertanggal sebelum rekonsiliasi …` dari `catat.py` atau `buku.py` wajib
  ikut disalin ke Pratinjau dan balasan — itu peringatan, bukan penolakan.
- `ERROR …` dari skrip = tidak ada yang dicatat; sampaikan apa adanya.
