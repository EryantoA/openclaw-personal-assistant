# Google Sheets sebagai cermin dua arah; CSV tetap satu-satunya Buku Kas

> **Memperluas** [0016](0016-pratinjau-sebelum-simpan-untuk-semua-pencatatan.md) dan
> [0018](0018-ubah-hapus-lewat-skrip-copy-lalu-ganti.md), dan **menjawab sebagian** konsekuensi
> [0004](0004-data-transaksi-tidak-masuk-git.md) ("cadangan luar-mesin perlu diatur terpisah").
> Spec: issue #20.

Pemilik ingin Buku Kas juga ada di Google Sheets dan bisa diubah dari kedua sisi. Bot, laporan,
Duplikat, dan Saldo semuanya membaca `bills.csv`; memindahkan sumbernya ke Sheets berarti menulis
ulang semua itu di atas API yang tidak punya rename atomik, kunci, atau Jejak Perubahan, dan
membuat pencatatan lewat WhatsApp bergantung pada internet dan Google. Maka Sheets dibuat
**cermin yang disinkronkan dua arah**, bukan sumber.

## Keputusan

- **CSV tetap sumber tunggal** (ADR-0005). Perubahan dari Sheets masuk lewat jalan tulis yang
  sama dengan bot: `catat.catat` untuk baris baru, `buku.jalankan ubah` untuk sel yang diubah.
  Validasi, Duplikat Lapis 1 dan 2, cadangan, rename atomik, dan Jejak Perubahan (bertanda
  `sheets`) berlaku sama.
- **Diff tiga arah terhadap snapshot** (isi Sheet yang terakhir disepakati). Satu sisi berubah →
  diterapkan ke sisi lain. Kedua sisi berubah pada baris yang sama → **CSV menang**.
- **Menghapus Transaksi hanya lewat bot.** Baris yang hilang dari Sheet dipulihkan dan dilaporkan;
  satu klik "hapus baris" tidak boleh menghilangkan data keuangan.
- **Kolom terkunci** (`no_resi`, `channel`), baris `opening_balance`, dan worksheet "Ringkasan"
  tidak bisa diubah dari Sheets; penegaknya penolakan di skrip, bukan perlindungan Google.
- **Pratinjau digantikan laporan sinkron** untuk perubahan yang datang dari Sheets: mengetik atau
  mengedit sel langsung adalah konfirmasinya, dan laporan memuat apa yang diterima, ditolak
  (beserta alasan dan isi barisnya), dan dipulihkan. Pratinjau percakapan (ADR-0016/0018) tetap
  berlaku untuk bot.
- **Bukan real-time.** Tidak ada server; sinkron berkala lewat cron dan perintah manual.
  Pencatatan lewat chat tidak pernah menunggu Google.
- **Tahan gagal.** Jaringan tidak dilakukan sambil memegang kunci CSV; hanya satu sinkron sekaligus;
  snapshot ditulis paling akhir; baris baru dijurnalkan sebelum ditulis agar kegagalan menulis Sheet
  tidak menggandakan Transaksi; Sheet dibaca ulang sebelum ditulis agar edit pengguna tidak
  ditimpa diam-diam.

## Privasi dan konsekuensi

- **Data keuangan keluarga kini juga tinggal di Google** (gaji, BPJS, pembelian pribadi — alasan
  ADR-0004). Spreadsheet wajib **privat** dan dibagikan hanya ke email akun layanan dan anggota
  keluarga yang dipilih pemilik; jangan pernah "siapa saja yang memiliki tautan".
- **Kunci akun layanan di luar git** (`data/google-service-account.json`), begitu pula
  `data/sheets.json`, snapshot, dan jurnal — semuanya di `.gitignore`.
- **Sheets bukan cadangan.** Salah edit atau salah hapus ikut tersinkron. Cadangan CSV harian
  (`backup.sh`) tetap satu-satunya cadangan yang dapat dipercaya; riwayat versi Google hanya jaring
  pengaman tambahan.
- **Batas yang diketahui:** jurnal anti-ganda berbasis isi baris, jadi baris baru yang diedit
  di antara dua ronde setelah kegagalan bisa menjadi dua Transaksi; edit multi-Item yang butuh dua
  permintaan dan gagal separuh jalan hanya dilaporkan, tidak diselesaikan; Sheets API tidak punya
  penguncian per sel, jadi celah beberapa detik antara baca-ulang dan tulis tetap ada;
  perlindungan Google (`warningOnly`) untuk kolom terkunci dan "Ringkasan" belum dipasang —
  penolakan di skrip yang menegakkannya; format kolom TEXT hanya dipasang ulang saat ada tulis;
  cron dan penjaga kesehatan belum mendaftarkan sinkron ini (tiket #27); belum dijalankan terhadap
  Google sungguhan (butuh akun layanan dan spreadsheet pemilik).
- **Dependensi baru** (`google-auth`, `requests`) harus terpasang untuk interpreter yang dipakai
  cron (`/usr/bin/python3`, 3.9). Tanpa itu sinkron gagal dengan kode 2 dan pesan yang jelas —
  jangan mengulang pelajaran export Excel yang mati diam 29 Jul–21 Sep 2026.

## Ditolak

- **Sheets sebagai sumber, CSV dibuang:** menulis ulang semua skrip di atas API tanpa kunci atau
  rename atomik, dan bot menjadi bergantung pada Google (ADR-0004/0005/0018 dibongkar). Mac mati
  tetap berarti bot mati; yang menyelesaikannya mesin yang selalu hidup, bukan pindah
  penyimpanan.
- **Menghapus lewat Sheets:** terlalu mudah tak sengaja. Bila kelak terlalu ketat, bentuk
  lunaknya kolom "hapus?" yang diisi eksplisit, bukan hapus baris.
