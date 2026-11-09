# Nama Akun baku ditegakkan skrip; cutover = hari pemilik mengecek saldo

Melanjutkan [0010](0010-akun-dan-transfer-lewat-cutover.md). Keputusan dari sesi tanya-jawab
dengan pemilik data, 9 Nov 2026.

Saat ditinjau, fitur Akun belum aktif dan datanya bertentangan dengan dirinya sendiri:
`akun.json` masih berisi akun bawaan (`Kas`, `Bank Utama`, `Tabungan`) yang tidak pernah dipakai,
glosarium menyebut enam Akun Dompet/Rekening/Simpanan, dan kolom `akun` di `bills.csv` berisi teks
bebas — satu akun tertulis dua cara, satu nama orang luar tercatat sebagai Akun tujuan. Penyebab
dasarnya: bot hanya *diminta* memakai nama dari `akun.json`, dan selama fitur belum aktif
`akun.py` tidak menampilkan daftar nama sama sekali, jadi bot mengarang.

## Keputusan

- **Cutover = hari pemilik membuka dompet, m-banking, dan e-wallet lalu mencatat isinya**, bukan
  tanggal di masa lalu. Cutover lama (1 Sep 2026) ditinggalkan: kolom `akun` baru mulai diisi
  awal November, sehingga ratusan baris sejak 1 Sep harus diberi Akun secara mundur — persis
  tebakan yang dilarang ADR-0010.
- **Saldo awal adalah angka yang dilihat, bukan sisa hitungan.** Akun yang saldonya belum bisa
  dicek diisi `null`, dan fitur tetap belum aktif. Selisih terhadap Saldo Bersama dibahas terbuka
  (koreksi rekonsiliasi seperti ADR-0008), tidak pernah diserap ke satu Akun.
- **E-wallet adalah jenis Akun**, di samping tunai dan rekening bank. Isi ulang = Transfer ke Akun
  e-wallet; belanja memakai saldonya = Pengeluaran dari Akun itu. Cara bayar (QRIS, aplikasi bank)
  tetap di Catatan.
- **Rekening orang di luar rumah tangga bukan Akun.** Uang ke sana adalah Pengeluaran.
- **Nama baku `<Tempat> <Panggilan>`**, satu panggilan per orang, "Tunai" untuk uang tunai.
- **`validasi.cek_baris` menolak `akun`/`akun_tujuan` yang tidak ada di `akun.json`** — berlaku
  untuk `catat.py`, `buku.py`, dan baris dari Sheets. Id atau beda huruf besar-kecil dibakukan
  ke nama; nama lain ditolak dengan daftar pilihan, sehingga bot harus bertanya. Kolom kosong
  tetap boleh. Tanpa `akun.json` (instalasi baru) tidak ada pengecekan.
- Nilai lama dibakukan lewat `buku.py` (Jejak Perubahan), tidak dikosongkan: baris sebelum
  cutover yang sudah menyebut Akun dengan jelas tetap informatif walau tidak masuk Saldo Akun.

## Ditolak

- **Hanya memperketat AGENTS.md.** Aturan "jangan menebak akun" sudah ada di prompt dan tetap
  dilanggar pada hari yang sama. Penolakan di skrip adalah penegak utamanya, seperti kategori.
- **Memetakan sinonim otomatis** (mis. "dompet" → "Tunai"). Kecocokan yang diterima hanya nama
  dan id; sinonim lain bisa menunjuk Akun yang berbeda dan harus ditanyakan.
- **Mewajibkan `akun` terisi sejak cutover** dan menambah `akun` ke `duplicate_check.match_fields`:
  ditunda sampai fitur benar-benar aktif (semua `saldo_awal` terisi dan `akun.py --cek` lolos),
  sesuai langkah aktivasi di `references/akun-transfer.md`.

Nomor ADR ini 0028 karena 0027 (Rekonsiliasi per Akun) digabung lebih dulu; keduanya saling
melengkapi: 0028 menetapkan saldo awal dan nama Akun, 0027 memeriksa Saldo Akun sesudahnya.
