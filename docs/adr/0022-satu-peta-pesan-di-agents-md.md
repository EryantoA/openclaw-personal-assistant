# Satu peta "pesan → jawaban" di AGENTS.md

Sebelum Okt 2026 bot memilih jawaban dari tiga tempat: bagian-bagian `AGENTS.md`, daftar trigger
bebas di `SKILL.md` (±15 jenis perintah, tiap satu dengan tulisan "Trigger: …" sendiri), dan
tabel laporan di tengah `AGENTS.md`. Sebuah pesan seperti "laporan bulan ini" bisa cocok dengan
beberapa bagian sekaligus, dan model kecil memilih salah satunya tanpa pola.

## Keputusan

`AGENTS.md` (selalu di prompt) membuka dengan tabel **Peta pesan → jawaban**: tiap jenis pesan
punya tepat satu baris. Kolom jawaban berisi salah satu dari tiga hal:

1. **Perintah skrip** — jalankan dan salin keluarannya utuh (laporan, sisa budget, saldo akun,
   cek resi, cek duplikat, cek tagihan).
2. **Nama bagian alur** — Mencatat transaksi, Mencari transaksi, Mengubah dan menghapus.
3. **Berkas rujukan** — fitur jarang pakai, lewat tabel *Fitur lain* di `SKILL.md` (ADR-0021).

Baris terakhir adalah jaring pengaman: pesan di luar semua baris, atau yang tidak jelas,
ditanyakan maksudnya dalam satu kalimat. Bot tidak menjalankan skrip tebakan.

Peta adalah satu-satunya tempat perintah skrip untuk menjawab pesan didefinisikan. `SKILL.md`
menunjuk ke peta dan hanya memuat yang tidak ada di sana (definisi, batasan); ia tidak lagi
memiliki daftar trigger sendiri untuk Cari, Cek Resi, Cek Duplikat, maupun Hapus/Ubah.

## Penjagaan

`tests/test_kontrak_prompt.py` (kelas `PetaPesan`): peta ada sebelum Data & Script dan alur;
setiap perintah ada di dalamnya; tabel laporan lama tidak hidup berdampingan; `SKILL.md` tidak
memuat perintah `resi.py --check` / `--find-dup` yang bisa dijalankan.

## Batas

Tes hanya membuktikan teksnya ada dan tunggal, bukan bahwa model memilih baris yang benar
(ADR-0014). Itu baru terlihat di pemakaian nyata: kalau bot masih salah memilih, perbaiki kata di
kolom kiri, jangan tambah baris yang tumpang tindih.
