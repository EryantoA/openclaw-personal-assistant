# Rekonsiliasi per Akun lewat chat; selisih ditutup terbuka sebagai Selisih Rekonsiliasi

> **Memperluas** [0010](0010-akun-dan-transfer-lewat-cutover.md) (Saldo Akun sejak cutover) dan
> mengikuti pola [0008](0008-saldo-awal-20-5-juta-dan-koreksi-rekonsiliasi.md) (selisih yang tak
> terjelaskan ditutup terbuka, bukan diserap). Pemicu dari
> [0012](0012-laporan-bulanan-dihitung-skrip-dikirim-tanggal-6.md) (Laporan Bulanan),
> [0014](0014-bukti-transfer-dikonfirmasi-dulu-kontrak-di-agents-md.md) (gambar dikonfirmasi dulu),
> dan [0016](0016-pratinjau-sebelum-simpan-untuk-semua-pencatatan.md) (Pratinjau).

Fitur Akun aktif sejak cutover 9 Nov 2026, tapi tidak ada yang memeriksa apakah Saldo Akun di Buku
Kas sama dengan uang yang sungguh ada di rekening, dompet, atau aplikasi. Transaksi yang lupa
dicatat, transfer yang tercatat di akun yang salah, atau baris tanpa akun membuat Saldo Akun
melenceng diam-diam — pada hari aktifnya saja sudah ada selisih Rp −472.097 dari 13 baris tanpa
akun. Pembukuan profesional menutup celah ini dengan **rekonsiliasi**: mencocokkan buku dengan
sumber luar secara rutin, lalu menjelaskan atau mencatat selisihnya.

## Keputusan

**Rekonsiliasi kapan saja, per Akun, lewat chat** — "saldo Mandiri Ryan 5.230.000" atau foto layar
saldo. Bukan ritual akhir bulan untuk semua Akun sekaligus: melapor saat sedang membuka aplikasi
bank jauh lebih mungkin benar-benar dilakukan, dan Akun tunai yang jarang dihitung tidak menahan
yang lain.

- **Saldo Nyata berlaku per saat pesan dikirim.** Saldo Akun dihitung dari Transaksi Akun itu
  bertanggal hari ini atau sebelumnya; untuk hari ini, hanya yang jamnya sudah lewat. Baris hari
  ini tanpa jam ikut dihitung **dan disebut di balasan**, karena itulah sumber selisih palsu yang
  paling mungkin. Tanggal bisa disebut ("per 30 Nov") untuk rekening koran atau mutasi; Saldo Akun
  lalu dihitung sampai akhir hari itu.
- **Foto layar saldo diterima dengan konfirmasi** (pola ADR-0014): bot menyebut nominal dan Akun
  yang terbaca, perbandingan baru dijalankan setelah "ya". Akun ditebak dari bank dan nomor
  rekening yang terlihat; bila ragu, ditanyakan. Gambar saldo **bukan** Bukti Transfer dan tidak
  pernah menjadi Transaksi; bila tidak jelas yang mana, bot bertanya.
- **Selisih dilaporkan, lalu ditawarkan dua jalan:** catat Transaksi yang terlupa lewat pencatatan
  biasa, atau tutup selisihnya sebagai satu Transaksi **Selisih Rekonsiliasi** pada Akun itu
  (Pengeluaran bila Saldo Nyata lebih kecil, Pemasukan bila lebih besar), lewat Pratinjau. Selisih
  juga boleh dibiarkan terbuka. Bot menyebut kandidat penyebab yang bisa dihitung: baris tanpa
  akun dan Transaksi Akun itu sejak Rekonsiliasi terakhir. Tidak pernah ditutup otomatis.
- **Selisih Rekonsiliasi** berkategori slug baru `reconciliation` (label "Selisih Rekonsiliasi").
  Uangnya sungguh sudah berpindah, hanya tidak diketahui untuk apa, jadi ia:

  | Hitungan | Ikut |
  |---|---|
  | Saldo Akun, Saldo Bersama | ya — itulah tujuannya |
  | Arus Kas Bulanan | ya — tanpa itu bulan tampak lebih baik dari kenyataan |
  | Per Kategori (Cermin) | ya, sebagai kategori sendiri |
  | Budget | tidak — bukan keputusan belanja; tampil terpisah seperti "Di luar budget" |
  | Jumlah Transaksi (ADR-0023) | tidak — seperti Saldo Awal dan Transfer |

- **Setiap Rekonsiliasi dicatat** di `data/rekonsiliasi.csv`, append-only dan di luar git
  (ADR-0004): tanggal-jam, Akun, Saldo Nyata, Saldo Akun saat itu, selisih, dan cara ditutup
  (`cocok` / `selisih_ditutup` + No Resi Selisih Rekonsiliasi-nya / `dibiarkan`; Transaksi terlupa
  yang dicatat lalu dicek ulang berakhir `cocok`). Bukan
  Transaksi dan tidak ikut hitungan apa pun. Tanpa catatan ini, Rekonsiliasi yang cocok tidak
  meninggalkan jejak, dan pengingat tak bisa membedakan "sudah dicek" dari "belum dicek".
- **Transaksi lama tidak dikunci, tapi tidak pernah berubah diam-diam.** Menambah, mengubah, atau
  menghapus Transaksi bertanggal sebelum Rekonsiliasi terakhir sebuah Akun tetap boleh; Pratinjau
  (dan laporan sinkron untuk suntingan dari Sheets) memperingatkan dengan besar geserannya:
  "⚠️ Mengubah Mandiri Ryan sebelum rekonsiliasi 1 Des (cocok) — saldo per 1 Des bergeser
  Rp −30.000." Polanya sama dengan Koreksi untuk bulan yang sudah dilaporkan (ADR-0012).
- **Pengingat = satu baris di Laporan Bulanan tanggal 6**, dihitung skrip (ADR-0011): Akun yang tak
  punya Rekonsiliasi bertanggal bulan lalu, dan selisih yang masih terbuka. Tidak ada pesan baru.
- **Cermin:** tab Saldo per Akun (ADR-0026) mendapat **Terakhir Dicek** dan **Selisih Terbuka** per
  Akun untuk bulan berjalan.

## Akibat

- Slug `reconciliation` masuk `kategori_custom` dan `label_kategori` di `data/budget.json`; bot tidak
  boleh memakainya untuk pencatatan biasa — hanya lewat alur Rekonsiliasi.
- `budget.py` dan laporan harus mengecualikan `reconciliation` dari Budget dan dari Jumlah Transaksi,
  dengan satu aturan yang sama di `buku_kas`, bukan per laporan.
- Rekonsiliasi pertama hanya bermakna setelah baris tanpa akun sejak cutover diberi Akun; kalau
  tidak, pengecekan pertama langsung menampilkan selisih yang bukan dari rekening.
- `data/rekonsiliasi.csv` berisi nominal saldo keluarga — data pribadi, masuk `.gitignore`.

## Ditolak

- **Ritual akhir bulan untuk semua Akun sekaligus:** tujuh pertanyaan beruntun mudah ditunda, dan
  satu Akun tunai yang belum dihitung menahan semuanya.
- **Kolom Saldo Nyata di Sheets:** Tab Laporan hanya-baca (ADR-0026), dan sinkron 15 menit membuat
  selisih tidak bisa dijawab saat itu juga.
- **Hanya melapor tanpa bisa menutup selisih:** Saldo Akun selamanya berbeda dari rekening, dan
  setiap Rekonsiliasi berikutnya ikut memikul selisih lama.
- **Menutup selisih otomatis:** menyembunyikan uang yang mungkin Transaksi terlupa.
- **Mengunci Transaksi sebelum Rekonsiliasi (tutup buku):** butuh jalur buka kunci dan menyulitkan
  koreksi salah ketik yang wajar; peringatan sudah membuat perubahan terlihat.
- **Menghitung Selisih Rekonsiliasi ke Budget:** satu selisih besar karena transfer salah catat akan
  membuat Budget "lewat" padahal tidak ada belanja.
- **Neraca / Kekayaan Bersih (ditunda, bukan ditolak):** keluarga belum punya utang, piutang, atau
  aset bukan uang yang ingin dipantau, jadi Aset = jumlah Saldo Akun = Saldo Bersama dan Kewajiban
  kosong — neraca akan selalu sama dengan Saldo Bersama. Dibuka lagi bila salah satunya muncul
  (mis. cicilan, emas); "utang" butuh konsep baru, karena Kewajiban hanya tagihan pascabayar.
