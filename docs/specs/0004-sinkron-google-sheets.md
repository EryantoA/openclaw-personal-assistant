# Spec: Sinkron dua arah Buku Kas ↔ Google Sheets

Status: siap dikerjakan. Turunan dari [ADR-0004](../adr/0004-data-transaksi-tidak-masuk-git.md),
[ADR-0005](../adr/0005-bill-tracker-sebagai-sistem-resmi.md),
[ADR-0011](../adr/0011-penjaga-kesehatan-tidak-boleh-butuh-model.md),
[ADR-0018](../adr/0018-ubah-hapus-lewat-skrip-copy-lalu-ganti.md), dan spec
[0002](0002-crud-data-csv.md).

## Problem Statement

Seluruh Buku Kas hidup di satu berkas CSV di satu Mac. Akibatnya:

- Anggota keluarga selain pemilik tidak bisa melihat Transaksi, Saldo, atau Arus Kas Bulan kapan
  saja; mereka hanya tahu lewat balasan bot dan laporan.
- Membaca, menyaring, dan mengoreksi banyak baris sekaligus (mis. mencocokkan mutasi bank) hanya
  nyaman di tabel, bukan lewat chat satu Transaksi per satu Pratinjau.
- ADR-0004 sudah mencatat konsekuensinya: kalau disk hilang, datanya hilang, dan "cadangan
  luar-mesin perlu diatur terpisah". Sampai sekarang belum ada.

Pemilik ingin data itu juga ada di Google Sheets, dan bisa diubah dari kedua sisi — chat/CSV dan
Sheets — tanpa salah satunya menjadi usang atau saling menimpa.

## Solution

`bills.csv` tetap satu-satunya **Buku Kas**. Google Sheets adalah tampilan tabel yang
**disinkronkan dua arah secara berkala** (bukan real-time — tidak ada server, aplikasi berjalan di
Mac lokal):

- **Keluar (CSV → Sheets):** setiap Transaksi muncul di worksheet "Buku Kas"; worksheet
  "Ringkasan" menampilkan Arus Kas Bulan dan Saldo per bulan, dihitung skrip yang sama dengan
  laporan (bukan rumus Sheets), jadi satu arti Saldo.
- **Masuk (Sheets → CSV):** perubahan yang dibuat di worksheet "Buku Kas" (baris baru, sel yang
  diubah) dikenali dengan membandingkan Sheet dengan **snapshot sinkron terakhir**, lalu
  dijalankan lewat jalan tulis resmi yang sama dengan bot — validasi, cek Duplikat, cadangan,
  tulis atomik, dan Jejak Perubahan. Perubahan yang ditolak dikembalikan ke nilai CSV di Sheet dan
  dilaporkan beserta alasannya.
- **Konflik:** bila baris yang sama berubah di kedua sisi sejak sinkron terakhir, **CSV menang**.
- **Hapus hanya lewat bot.** Baris yang hilang dari Sheet dipulihkan pada sinkron berikutnya dan
  dilaporkan; penghapusan Transaksi tetap lewat Pratinjau (ADR-0018). Satu klik "hapus baris" yang
  tidak sengaja di Sheet tidak boleh menghilangkan data keuangan.

Sinkron dipicu cron berkala dan satu perintah manual. Pencatatan lewat chat tidak pernah menunggu
atau bergantung pada Google.

## User Stories

1. Sebagai pemilik, saya ingin seluruh Transaksi tampil di Google Sheets, supaya saya bisa melihat
   dan menyaringnya sebagai tabel tanpa membuka terminal.
2. Sebagai istri pemilik, saya ingin melihat Transaksi dan Saldo di Google Sheets dari HP, supaya
   saya tidak perlu menunggu laporan atau bertanya ke bot.
3. Sebagai pemilik, saya ingin Transaksi yang dicatat lewat WhatsApp muncul di Sheets dalam
   hitungan menit, supaya tabel itu tidak terasa basi.
4. Sebagai pemilik, saya ingin mengubah kategori, jumlah, atau item sebuah Transaksi langsung di
   Sheets, supaya mencocokkan mutasi bank dengan banyak baris tidak harus satu per satu lewat chat.
5. Sebagai pemilik, saya ingin menambah baris baru di Sheets, supaya Transaksi yang lupa dicatat
   bisa dimasukkan dalam sekali isi.
6. Sebagai pemilik, saya ingin baris baru dari Sheets mendapat No Resi otomatis dan lolos cek
   yang sama dengan pencatatan chat, supaya data dari Sheets tidak lebih longgar daripada data dari
   bot.
7. Sebagai pemilik, saya ingin baris baru yang kembar dengan Transaksi yang sudah ada ditolak
   dengan alasan yang jelas, supaya sinkron tidak diam-diam menggandakan uang.
8. Sebagai pemilik, saya ingin kategori yang tidak dikenal, jumlah bukan angka, atau tanggal
   tidak sah ditolak dan dikembalikan ke nilai sebelumnya, supaya CSV tidak pernah rusak oleh
   salah ketik di Sheets.
9. Sebagai pemilik, saya ingin sel yang ditolak diberi tahu alasannya di laporan sinkron, supaya
   saya tahu apa yang harus dibetulkan.
10. Sebagai pemilik, saya ingin kolom No Resi dan Channel tidak bisa diubah dari Sheets, supaya
    kunci Transaksi dan Asal tetap benar (sama dengan aturan ADR-0018).
11. Sebagai pemilik, saya ingin baris saldo awal (`opening_balance`) dan baris rusak tidak bisa
    diubah dari Sheets, supaya Saldo tidak bergeser tanpa sengaja.
12. Sebagai pemilik, saya ingin baris yang terhapus dari Sheets dipulihkan dan dilaporkan, bukan
    ikut menghapus Transaksi di CSV, supaya salah hapus baris tidak menghilangkan data.
13. Sebagai pemilik, saya ingin penghapusan Transaksi tetap lewat Pratinjau di bot, supaya ada
    konfirmasi dan Jejak Perubahan.
14. Sebagai pemilik, saya ingin bila baris yang sama berubah di CSV dan di Sheets, nilai CSV yang
    dipakai dan edit Sheets dilaporkan sebagai ditolak, supaya tidak ada tebak-tebakan siapa
    benar.
15. Sebagai pemilik, saya ingin setiap perubahan yang masuk dari Sheets tercatat di Jejak
    Perubahan dengan penanda asal Sheets, supaya saya bisa menelusuri siapa/apa yang mengubah.
16. Sebagai pemilik, saya ingin perubahan dari Sheets yang menggeser bulan yang sudah dilaporkan
    tampil sebagai Koreksi di Laporan Bulanan berikutnya, supaya angka lama tidak berubah diam-diam
    (ADR-0012).
17. Sebagai pemilik, saya ingin worksheet "Ringkasan" menampilkan Arus Kas Bulan dan Saldo per
    bulan, supaya keluarga melihat angka yang sama dengan laporan bot.
18. Sebagai pemilik, saya ingin edit di worksheet "Ringkasan" diabaikan dan ditimpa pada sinkron
    berikutnya, supaya hanya ada satu sumber hitungan Saldo.
19. Sebagai pemilik, saya ingin sinkron berjalan sendiri tiap beberapa menit lewat cron, supaya
    saya tidak perlu mengingat menjalankannya.
20. Sebagai pemilik, saya ingin bisa menjalankan sinkron manual dengan satu perintah, supaya saya
    bisa memaksa tabel segar sebelum melihatnya.
21. Sebagai pemilik, saya ingin mode uji (`--uji`) yang menampilkan apa yang akan didorong,
    diterima, dan ditolak tanpa menulis apa pun, supaya saya bisa memeriksa sebelum sinkron
    pertama.
22. Sebagai pemilik, saya ingin sinkron pertama memuat seluruh Buku Kas ke Sheet kosong, supaya
    awalnya tidak perlu salin manual.
23. Sebagai pemilik, saya ingin sinkron menolak jalan bila Sheet sudah berisi data tetapi belum ada
    snapshot, dan meminta inisialisasi eksplisit, supaya sinkron tidak menebak mana yang benar.
24. Sebagai pemilik, saya ingin pencatatan lewat WhatsApp tetap jalan walau internet atau Google
    mati, supaya bot keuangan tidak bergantung pada layanan luar.
25. Sebagai pemilik, saya ingin sinkron yang gagal di tengah jalan tidak meninggalkan CSV atau
    snapshot setengah berubah, supaya sinkron berikutnya bisa melanjutkan dengan aman.
26. Sebagai pemilik, saya ingin sinkron kedua tanpa perubahan apa pun tidak mengubah apa-apa
    (idempoten), supaya cron berkala tidak membuat riwayat atau cadangan sampah.
27. Sebagai pemilik, saya ingin penjaga kesehatan memperingatkan bila sinkron mandek terlalu
    lama, tanpa butuh model, supaya kegagalan diam-diam seperti export Excel dulu tidak terulang
    (ADR-0011).
28. Sebagai pemilik, saya ingin kunci akses Google berada di luar git dan spreadsheet hanya
    dibagikan ke orang yang saya pilih, supaya data keuangan tidak bocor lewat repo (ADR-0004).
29. Sebagai pemilik, saya ingin sinkron tidak berebut dengan `catat.py` atau `buku.py` yang sedang
    menulis, supaya baris tidak rusak oleh dua penulis sekaligus.
30. Sebagai pemilik, saya ingin satu Transaksi dengan banyak Item (struk multi-barang) tampil
    sebagai beberapa baris dengan No Resi yang sama dan tetap bisa diubah per Item, supaya
    struk besar tidak jadi satu sel raksasa.
31. Sebagai pemilik, saya ingin alias Pencatat yang diketik di Sheets (mis. "istri") dibakukan
    ke nama baku seperti di bot, supaya laporan per Pembeli tidak pecah.
32. Sebagai pemilik, saya ingin cadangan CSV harian tetap berjalan seperti sekarang, supaya Sheets
    bukan satu-satunya salinan sekaligus bukan pengganti cadangan.
33. Sebagai pengembang, saya ingin seluruh aturan sinkron bisa diuji dengan klien Sheets palsu,
    supaya tidak ada tes yang memanggil Google sungguhan.

## Implementation Decisions

**CSV tetap sumber tunggal.** Tidak ada perubahan pada ADR-0005: `catat.py` tetap satu-satunya
jalan menambah, `buku.py` satu-satunya jalan mengubah/menghapus. Sinkron adalah *klien* kedua dari
jalan tulis itu, bukan jalan tulis baru. Aturan validasi tetap di satu tempat (`validasi.py`) dan
aturan Duplikat di satu tempat (`duplikat.py`).

**Satu module baru `sheets_sync`.** Antarmuka tinggi satu pintu: satu fungsi sinkron menerima
lokasi Buku Kas, sebuah klien Sheets (disuntikkan), lokasi snapshot, dan mode (`uji` /
`inisialisasi`), lalu mengembalikan **laporan** berisi: jumlah baris didorong, diterima, ditolak
(beserta alasan per sel/baris), dan dipulihkan. Pembangunan tabel dari baris (CSV → grid
Sheet) dan penguraian grid Sheet → perubahan murni, tanpa I/O. Klien Google yang sungguhan adalah
adaptor tipis di tepi yang memenuhi antarmuka klien yang sama dengan klien palsu di tes. Tidak ada
logika bisnis di adaptor.

**Skrip masukan.** Satu skrip CLI tipis (`--uji`, `--inisialisasi`), mengikuti pola skrip lain di
repo (Pekan, Perkiraan, Kewajiban, dan Pengaturan sudah dipisah dari CLI-nya). Cron Python di Mac
adalah 3.9 bawaan macOS: module harus punya `from __future__ import annotations`, dan dependensi
Google harus terpasang untuk interpreter yang dipakai cron (pelajaran export Excel yang mati diam
29 Jul–21 Sep 2026).

**Identitas baris.** Kunci baris = No Resi + nomor Item, sama dengan yang dipakai `buku.py`. Baris
baru di Sheets ditandai: No Resi kosong. Skrip membuatkan No Resi `TRX-…` lewat jalur yang sama
dengan `catat.py`, mengisi Channel `sheets`, lalu menulis No Resi itu balik ke Sheet. Baris baru
yang sudah membawa No Resi diperlakukan sebagai Lapis 1 Duplikat bila sudah ada, atau ditambahkan
bila belum.

**Layout Sheet.** Worksheet "Buku Kas": 12 kolom persis `bills.csv` (urutan dan nama sama), jumlah
sebagai angka. Worksheet "Ringkasan": satu baris per bulan (Pemasukan, Pengeluaran, Arus Kas
Bulan, Saldo Awal Tercatat, Saldo Akhir), dihitung `buku_kas`, ditimpa tiap sinkron. Baris
`opening_balance` ikut tampil. Kolom terkunci (`no_resi`, `channel`) dan worksheet "Ringkasan"
diberi perlindungan di Sheets sebagai peringatan; penegak sebenarnya adalah penolakan di sisi
skrip, bukan perlindungan Google (yang bisa dilepas pemilik).

**Snapshot.** Setelah setiap sinkron sukses, skrip menyimpan isi Sheet dan CSV yang disepakati
sebagai snapshot lokal (tidak masuk git — ADR-0004). Sinkron berikutnya melakukan diff tiga arah:
snapshot (dasar) vs CSV sekarang vs Sheet sekarang. Hanya satu sisi berubah → sisi itu diterapkan
ke yang lain. Kedua sisi berubah di sel/baris yang sama → CSV menang, edit Sheet ditolak dan
dilaporkan. Snapshot ditulis setelah semua penulisan lain berhasil, sehingga kegagalan di tengah
jalan membuat sinkron berikutnya mengulang bagian yang belum selesai, bukan melewatinya.

**Perubahan masuk ditulis lewat jalan resmi.** Baris baru → logika `catat.py`; sel yang diubah →
logika `buku.py ubah` (kolom terkunci tidak bisa, cek Duplikat bila kolom pembanding berubah,
cadangan sebelum tulis, rename atomik, Jejak Perubahan). Ditambahkan penanda `sheets` pada kolom
"siapa" di Jejak Perubahan karena Sheets tidak memberi tahu siapa pengubahnya. Pratinjau percakapan
tidak dipakai: pengeditan langsung di Sheet adalah konfirmasi, dan laporan sinkron adalah
pengganti Pratinjau.

**Hapus tidak masuk dari Sheets.** Baris yang ada di snapshot tetapi hilang di Sheet dipulihkan
dari CSV dan dimasukkan ke laporan. Hapus tetap hanya lewat `buku.py hapus` dengan Pratinjau.

**Pengunci.** Sinkron memakai berkas `*.lock` yang sama dengan `catat.py` dan `buku.py` (ADR-0018)
selama membaca CSV, menerapkan perubahan masuk, dan menulis snapshot. Panggilan jaringan ke Google
dilakukan di luar bagian terkunci sejauh mungkin supaya pencatatan chat tidak menunggu Google.

**Mode.** `--uji` mengeluarkan laporan yang sama tanpa menulis apa pun ke CSV, Sheet, maupun
snapshot. `--inisialisasi` dipakai sekali: bila Sheet kosong, memuat seluruh Buku Kas; bila Sheet
sudah berisi data dan tidak ada snapshot, sinkron biasa menolak dan meminta mode ini secara
eksplisit, yang menimpa Sheet dari CSV (CSV menang).

**Pemicu.** Cron berkala (interval beberapa menit; cron hidup di gateway, ADR-0009, jadi
didaftarkan lewat `openclaw cron`, bukan hanya di `openclaw.json`) dan perintah manual. Tidak ada
pemanggilan sinkron dari dalam `catat.py` atau `buku.py`. Lonjakan sinkron berurutan tidak boleh
menumpuk: sinkron yang masih jalan membuat pemanggilan berikutnya keluar tanpa kerja.

**Penjaga kesehatan.** `periksa-kesehatan` mendapat satu sinyal: waktu sinkron sukses terakhir
lebih tua dari ambang. Ia dihitung skrip tanpa model (ADR-0011). Hasil terakhir sinkron
(sukses/gagal, waktu, jumlah ditolak) ditulis ke berkas status kecil di `data/`, tidak masuk git.

**Autentikasi.** Akun layanan Google (service account); berkas kuncinya di luar git (pola sama
dengan `openclaw.json`), dan spreadsheet dibagikan privat ke email akun layanan serta ke anggota
keluarga yang dipilih pemilik. Tidak ada kredensial di prompt bot, README contoh, atau log.

**ADR baru.** Keputusan ini memutar ADR-0004: data keuangan keluarga kini juga tinggal di Google.
Itu harus ditulis sebagai ADR sendiri (cermin dua arah, CSV menang, hapus hanya lewat bot,
konsekuensi privasi) — ADR-0004 tidak diubah, tetapi konsekuensinya "cadangan luar-mesin" kini
terjawab sebagian, dengan catatan bahwa Sheets bukan cadangan karena edit/hapus juga tersinkron.

**Tidak memakai konektor Sheets di sesi Claude Code.** Konektor itu hanya untuk sesi interaktif;
cron butuh skrip mandiri dengan kredensial sendiri.

## Testing Decisions

**Tes yang baik di sini** hanya memeriksa perilaku yang terlihat dari luar module `sheets_sync`:
isi Sheet palsu, isi CSV, isi Jejak Perubahan, dan laporan yang dikembalikan, setelah satu atau
beberapa kali memanggil fungsi sinkron. Tidak menguji fungsi pembangun tabel secara terpisah dan
tidak ada tes yang memanggil API Google.

**Satu seam.** Antarmuka fungsi sinkron di `sheets_sync` dengan klien Sheets palsu berbasis memori
(menyimpan grid per worksheet; bisa disuntik kegagalan di langkah tertentu). Di atas seam ini
diuji:

- Sinkron pertama ke Sheet kosong → semua Transaksi dan Ringkasan muncul; angka Saldo sama dengan
  `buku_kas`.
- Sinkron kedua tanpa perubahan → tidak ada tulisan sama sekali (idempoten), tidak ada cadangan
  baru.
- Transaksi baru di CSV → muncul di Sheet; ubahan di CSV → sel berubah di Sheet.
- Sel diubah di Sheet (valid) → CSV berubah, Jejak Perubahan bertanda `sheets`, cadangan dibuat.
- Sel diubah ke nilai tidak sah (kategori asing, jumlah huruf, tanggal ngawur) → ditolak, Sheet
  dikembalikan, CSV tak berubah, alasan ada di laporan.
- Sel kolom terkunci (`no_resi`, `channel`) diubah → ditolak dan dikembalikan.
- Baris `opening_balance` diubah → ditolak.
- Baris baru di Sheet tanpa No Resi → CSV dapat Transaksi baru ber-`TRX-` dan Channel `sheets`;
  No Resi ditulis balik ke Sheet.
- Baris baru yang kembar dengan baris ada → ditolak (Lapis 1 dan Lapis 2).
- Alias Pencatat di baris baru → dibakukan.
- Baris dihapus dari Sheet → dipulihkan, CSV utuh, laporan menyebutnya.
- Baris yang sama diubah di CSV dan Sheet → nilai CSV menang; edit Sheet ditolak.
- Edit di worksheet Ringkasan → ditimpa.
- Sheet berisi data tanpa snapshot → menolak; dengan mode inisialisasi → CSV menang.
- Mode `uji` → laporan lengkap, tidak ada tulisan ke CSV, Sheet, atau snapshot.
- Klien palsu gagal di tengah jalan → CSV konsisten, snapshot tak berubah, sinkron berikutnya
  menyelesaikan dengan benar.
- Bulan yang sudah dilaporkan berubah lewat Sheet → muncul sebagai Koreksi pada Laporan Bulanan
  berikutnya (memakai pembaca yang sudah ada).

**Prior art.** `tests/test_catat.py` dan `tests/test_buku.py` (pemanggilan langsung dengan jalur
data diarahkan ke direktori sementara, pencocokan keluaran), `tests/test_buku_kas.py` (pembaca
Buku Kas lewat antarmuka), `tests/test_duplikat.py` (aturan sama-nya Duplikat).

## Out of Scope

- Sinkron *real-time* (push tiap sel diedit). Itu butuh server publik atau Apps Script yang
  memanggil balik ke Mac lewat ngrok; interval cron sudah cukup untuk catatan keluarga.
- Menjadikan Sheets sumber utama dan membuang CSV (membongkar ADR-0004/0005/0018).
- Menghapus Transaksi dari Sheets.
- Rumus Sheets untuk Saldo/Arus Kas Bulan; semua hitungan tetap dari `buku_kas`.
- Berkas selain Buku Kas: `riwayat-ubah.csv` (Jejak Perubahan), `kewajiban.json`,
  `perkiraan.json`, `budget.json`, `akun.json`, `pembeli.json`.
- Hak edit per anggota keluarga atau atribusi "siapa mengubah sel apa" di Sheets.
- Notifikasi WhatsApp atas hasil sinkron; cukup laporan dan sinyal penjaga kesehatan.
- Mengubah `export-excel.py` atau `backup.sh`; keduanya tetap berjalan seperti sekarang.
- Impor otomatis dari Google Forms.

## Further Notes

- Pertimbangan terbesar: "dua arah bersamaan" tidak bisa dijamin mutlak. Bila Sheet diedit persis
  saat sinkron sedang menulis, Sheets API tidak punya penguncian optimistis per sel; jendela itu
  kecil (detik) dan perubahan yang terlewat tertangkap pada sinkron berikutnya lewat diff terhadap
  snapshot. Karena itu aturan konfliknya sengaja tegas: CSV menang.
- Alasan hapus-tidak-masuk-dari-Sheets: menghapus baris di Sheets satu gerakan, tanpa konfirmasi,
  sementara ADR-0018 memagari penghapusan dengan Pratinjau dan cadangan. Bila kelak pemilik
  merasa terlalu ketat, bentuk lunaknya adalah kolom "hapus?" yang harus diisi eksplisit — bukan
  hapus baris.
- Privasi: data berisi gaji, BPJS, dan pembelian pribadi akan berada di Google. Spreadsheet harus
  privat dan dibagikan eksplisit; jangan pernah "siapa saja dengan tautan". Ini bagian dari ADR
  baru yang harus ditulis bersamaan dengan implementasi.
- Pemulihan bencana: Sheets bukan cadangan (kesalahan tersinkron dua arah). Cadangan CSV harian
  di `backup.sh` tetap satu-satunya cadangan yang dapat dipercaya; riwayat versi Google Sheets
  hanya jaring pengaman tambahan.
- Sinkron pertama sebaiknya dijalankan dengan `--uji` dulu, lalu `--inisialisasi`.
