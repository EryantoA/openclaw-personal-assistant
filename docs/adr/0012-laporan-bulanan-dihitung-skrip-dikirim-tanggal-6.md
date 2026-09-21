# Laporan Bulanan dihitung skrip, dikirim tanggal 6, dan mengingat angkanya sendiri

**Laporan Bulanan** (lihat `CONTEXT.md`) melaporkan bulan yang **sudah tutup**, dikirim
**tanggal 6 pukul 09:00 WIB**, dan disusun seluruhnya oleh skrip sebagai **command payload**
di cron Gateway — bukan oleh giliran agent. Angka yang dilaporkan disimpan, dan Laporan
Bulanan berikutnya menyebutkan **Koreksi** untuk bulan mana pun yang angkanya berubah sejak
dilaporkan.

## Kenapa tanggal 6, bukan tanggal 1

Pencatatan di buku kas tidak seketika. Membandingkan backup harian berturut-turut
(22 Agu–13 Sep 2026, di luar impor besar 23 Agu) menunjukkan dua pola:

- Pencatatan lewat WhatsApp: hampir semua 0–1 hari, paling telat **5 hari**.
- Pencocokan mutasi bank: baris yang ditemukan belakangan telat **10–25 hari**.

Laporan tanggal 1 hampir pasti kehilangan transaksi akhir bulan. Tanggal 6 menampung pola
pertama. Pola kedua tidak bisa ditampung jadwal mana pun yang masih pantas disebut
"bulanan" — itulah gunanya Koreksi.

## Kenapa skrip, bukan model

Koreksi hanya bermakna kalau angka yang dilaporkan dan angka hitung ulang dihasilkan dengan
cara yang persis sama. Model yang menjumlahkan ratusan baris bisa meleset beberapa ribu
rupiah antar run, dan selisih itu akan tampil sebagai "koreksi" padahal datanya tidak
berubah. Aturan akuntansi yang harus diterapkan — `opening_balance` masuk Saldo tapi tidak
masuk Pemasukan, `transfer` dilewati, Saldo kumulatif — semuanya pernah salah di riwayat
project ini; di skrip, aturan itu bisa diuji.

Alasan kedua sama dengan [0011](0011-penjaga-kesehatan-tidak-boleh-butuh-model.md): OAuth
model mati 15–17 dan 20 Sep 2026, dan `laporan_mingguan` ikut gagal. Laporan yang terbit
sebulan sekali tidak boleh ikut hilang karena hal yang sama. Pengirimannya lewat
`openclaw message send`, jalur yang sama dengan penjaga kesehatan — bukan lewat tool
`message` yang harus diingat model untuk dipanggil ([0009](0009-cron-hidup-di-gateway-bukan-di-openclaw-json.md)).

## Considered Options

**Tanggal 1 dengan label "angka sementara"** ditolak. Laporan bulanan dibaca sebagai angka
final; angka yang berubah setelah dikirim, tanpa penjelasan, merusak kepercayaan pada
Saldo — pelajaran [0008](0008-saldo-awal-20-5-juta-dan-koreksi-rekonsiliasi.md).

**Giliran agent** (seperti `laporan_mingguan`) dan **campuran** (skrip menghitung, agent
menarasikan dan mengirim) ditolak. Keduanya mati bersama model, dan yang pertama tidak
menjamin angka yang sama dua kali. Pengamatan bebas ("kopi naik 40%") dikorbankan; itu
tetap bisa didapat dengan bertanya ke bot.

**Mengabaikan perubahan setelah laporan terkirim** ditolak: Saldo akhir di laporan berikutnya
tidak akan nyambung dengan laporan sebelumnya, tanpa penjelasan. **Mengirim ulang laporan
setiap kali bulan lama berubah** ditolak karena terlalu berisik untuk koreksi kecil.

## Consequences

- **Angka disimpan hanya setelah pengiriman berhasil.** Kalau disimpan dulu lalu pengiriman
  gagal, Koreksi bulan depan dihitung terhadap angka yang tidak pernah diterima siapa pun.
  Skrip juga **harus keluar dengan status gagal** kalau pengiriman gagal, supaya cron tercatat
  `error` dan penjaga kesehatan menangkapnya pukul 14:00 di hari yang sama. Jam 09:00 dipilih
  untuk itu, dan supaya tidak bertabrakan dengan cron pukul 20:00.
- **Pengiriman dicoba sampai 3 kali, berjeda 60 detik** (batas waktu cron 420 detik). Uji
  kirim pertama 21 Sep 2026 gagal dua kali berturut-turut — `Connection Closed`, lalu
  `No active WhatsApp Web listener` — padahal `channels status` menyebut WhatsApp tersambung.
  Riwayat penjaga kesehatan 5–21 Sep menunjukkan pola yang sama: sekitar 9 dari 60 run gagal
  kirim secara acak. Pesan yang terbit sebulan sekali tidak boleh bergantung pada menit yang
  kebetulan buruk; pesan ganda sesekali lebih murah daripada laporan yang tidak sampai.
  Percobaan ketiga hari itu terkirim lewat cron gateway, dan pengguna mengonfirmasi laporan
  Agustus benar-benar masuk di WhatsApp — bukti sampai yang diminta
  [0009](0009-cron-hidup-di-gateway-bukan-di-openclaw-json.md), bukan sekadar status `ok`.
- **Koreksi melekat pada bulan asal perubahan**, bukan pada setiap bulan sesudahnya yang Saldo
  akhirnya ikut bergeser. Setelah disebutkan sekali, angka simpanan bulan itu diperbarui.
- **Permintaan lewat chat** (`laporan bulan lalu`) menjalankan skrip yang sama dalam mode
  tampilkan-saja: angkanya identik dengan versi tanggal 6, dan tidak menyimpan apa pun.
  Kalau menyimpan, ia akan menghabiskan Koreksi sebelum laporan tanggal 6 sempat
  menyebutnya.
- **Nama "Laporan Bulanan" hanya untuk bulan yang sudah tutup.** Fitur on-demand untuk bulan
  berjalan di `SKILL.md` berganti nama supaya satu nama tidak menunjuk dua hal.
- **Blind spot yang diakui:** transaksi yang ditemukan lebih dari lima hari setelah bulan tutup
  tidak pernah muncul di laporan aslinya; ia hanya muncul sebagai Koreksi sebulan kemudian.
  Simpanan dimulai dari **Agustus 2026**: laporan Agustus terkirim lewat cron pada 21 Sep 2026
  (uji kirim, lalu satu run manual), dan pengguna memutuskan angkanya dibiarkan tersimpan —
  laporan itu memang sudah diterima, jadi perubahan Agustus sesudahnya layak disebut sebagai
  Koreksi di laporan 6 Okt. Bulan-bulan sebelum Agustus tidak diisi mundur.
- Laporan hanya dikirim ke nomor pemilik (`channels.whatsapp.allowFrom[0]`). Menambah
  penerima adalah keputusan keluarga soal siapa melihat angka apa, bukan soal teknis.
