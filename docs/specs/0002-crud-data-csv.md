# Spec: CRUD untuk setiap data yang disimpan di CSV

Status: siap dikerjakan. Turunan dari [ADR-0005](../adr/0005-bill-tracker-sebagai-sistem-resmi.md),
[ADR-0012](../adr/0012-laporan-bulanan-dihitung-skrip-dikirim-tanggal-6.md),
[ADR-0016](../adr/0016-pratinjau-sebelum-simpan-untuk-semua-pencatatan.md), dan spec
[0001](0001-konfirmasi-sebelum-simpan.md).

## Problem Statement

Dari semua data keluarga, hanya satu yang disimpan sebagai CSV: `bills.csv`, buku kas berisi
Transaksi. Dari empat operasi dasar, hanya **Create** yang punya jalan resmi (`catat.py`, lengkap
dengan Pratinjau, cek duplikat, dan validasi). Sisanya setengah jadi:

- **Read**: tidak ada cara mencari satu Transaksi. Pengguna harus menunggu laporan, atau bot
  membaca seluruh file lalu menebak.
- **Update** dan **Delete**: tidak ada skrip. Aturan di skill menyuruh bot "membaca lalu menulis
  ulang file", padahal Edit/Write ke CSV justru dilarang karena model pernah merusak baris
  (13 kolom, resi karangan). "Hapus terakhir" menghapus baris terakhir file, yang untuk struk
  multi-barang hanya satu dari beberapa barisnya.
- Salah baca OCR, salah kategori, atau salah angka yang baru ketahuan setelah tersimpan
  akhirnya dibereskan manual oleh pemilik di terminal, tanpa Pratinjau, tanpa cadangan, tanpa
  jejak siapa mengubah apa.

Selain itu setiap CSV baru yang kelak dibuat akan mengulang masalah yang sama, karena belum ada
pola yang bisa dipakai ulang.

## Solution

Setiap data di CSV punya empat operasi yang sama aman dengan Create hari ini: **cari** (Read),
**tambah** (Create, sudah ada), **ubah** (Update), **hapus** (Delete). Ubah dan hapus mengikuti
alur Pratinjau yang sama dengan pencatatan: bot menampilkan "sebelum → sesudah" (atau "akan
dihapus"), menunggu *ya* / koreksi / *batal*, baru menjalankan skrip. Skrip yang mengerjakan
semua yang mekanis: mencari Transaksi, memvalidasi dengan aturan yang sama dengan `catat.py`,
membuat cadangan, menulis atomik, dan mencatat jejak perubahan. Bot tidak pernah menyentuh CSV
langsung.

Mesin CRUD dibuat generik (satu deklarasi skema per CSV), dengan `bills.csv` sebagai pendaftar
pertama, sehingga CSV berikutnya cukup mendaftarkan skema dan otomatis ikut mendapat empat
operasi dan pagar keselamatannya.

## User Stories

1. Sebagai anggota keluarga, saya ingin mencari Transaksi lewat chat ("cari indomaret kemarin",
   "transaksi 12 Oktober"), supaya saya bisa memeriksa apa yang tercatat tanpa menunggu laporan.
2. Sebagai anggota keluarga, saya ingin pencarian bisa difilter berdasarkan tanggal atau rentang
   tanggal, supaya hasilnya tidak membludak.
3. Sebagai anggota keluarga, saya ingin pencarian bisa difilter berdasarkan Kategori, supaya saya
   bisa memeriksa satu jenis pengeluaran.
4. Sebagai anggota keluarga, saya ingin pencarian bisa difilter berdasarkan Pembeli/Pencatat,
   supaya saya bisa melihat catatan satu orang.
5. Sebagai anggota keluarga, saya ingin pencarian teks pada nama Item (termasuk nama toko), supaya
   saya bisa menemukan struk dari ingatan samar.
6. Sebagai anggota keluarga, saya ingin pencarian berdasarkan No Resi, supaya saya bisa menunjuk
   struk persis yang saya maksud.
7. Sebagai anggota keluarga, saya ingin hasil pencarian dikelompokkan per Transaksi (satu No
   Resi, banyak Item) dengan totalnya, supaya struk multi-barang terbaca sebagai satu kesatuan.
8. Sebagai anggota keluarga, saya ingin hasil pencarian dibatasi jumlahnya dan diberi tahu bila
   ada yang terpotong, supaya balasan WhatsApp tidak kepanjangan.
9. Sebagai anggota keluarga, saya ingin pencarian tanpa hasil dijawab jelas "tidak ditemukan",
   supaya saya tidak mengira bot error.
10. Sebagai anggota keluarga, saya ingin bisa mengubah kategori sebuah Transaksi atau satu Item
    di dalamnya, supaya salah kategori tidak merusak Budget.
11. Sebagai anggota keluarga, saya ingin bisa mengubah jumlah satu Item, supaya salah baca angka
    OCR bisa dibetulkan.
12. Sebagai anggota keluarga, saya ingin bisa mengubah tanggal dan jam Transaksi, supaya
    transaksi yang dicatat telat masuk ke Pekan dan bulan yang benar.
13. Sebagai anggota keluarga, saya ingin bisa mengubah nama Item dan Catatan, supaya typo dan
    cara bayar bisa dibetulkan.
14. Sebagai anggota keluarga, saya ingin bisa mengubah Pembeli, supaya laporan per Pembeli benar
    bila bot salah mengira siapa yang berbelanja.
15. Sebagai anggota keluarga, saya ingin bisa mengubah Akun sebuah Transaksi (dan akun asal/tujuan
    transfer), supaya Saldo per Akun benar.
16. Sebagai anggota keluarga, saya ingin sebelum apa pun berubah bot menampilkan Pratinjau
    "sebelum → sesudah" per kolom yang berubah, supaya saya yakin ini yang saya maksud.
17. Sebagai anggota keluarga, saya ingin menjawab *ya*, *batal*, atau koreksi bebas pada Pratinjau
    ubah, supaya alurnya sama dengan pencatatan yang sudah saya kenal.
18. Sebagai anggota keluarga, saya ingin bisa menghapus satu Transaksi utuh, supaya struk yang
    salah catat atau tercatat di dua tempat hilang dari buku kas.
19. Sebagai anggota keluarga, saya ingin bisa menghapus satu Item saja dari struk multi-barang,
    supaya barang yang salah masuk tidak memaksa saya mencatat ulang seluruh struk.
20. Sebagai anggota keluarga, saya ingin sebelum menghapus bot menampilkan persis baris yang akan
    hilang beserta total yang berkurang, supaya tidak ada yang terhapus tanpa saya lihat.
21. Sebagai anggota keluarga, saya ingin "hapus terakhir" menghapus Transaksi terakhir yang saya
    catat (bukan baris terakhir file), lewat Pratinjau yang sama, supaya struk multi-barang tidak
    terhapus separuh.
22. Sebagai anggota keluarga, saya ingin bila pencarian saya cocok dengan lebih dari satu
    Transaksi, bot meminta saya memilih salah satu dan tidak menebak, supaya yang berubah bukan
    Transaksi yang salah.
23. Sebagai anggota keluarga, saya ingin perubahan yang melanggar aturan data ditolak dengan
    alasan jelas (kategori tak dikenal, jumlah ≤ 0, tanggal salah format), supaya buku kas tetap
    konsisten.
24. Sebagai anggota keluarga, saya ingin perubahan yang membuat Transaksi persis sama dengan
    Transaksi lain ditolak sebagai Duplikat, supaya Saldo tidak terhitung dua kali.
25. Sebagai anggota keluarga, saya ingin bot hanya menjawab "sudah diubah" atau "sudah dihapus"
    bila skrip melaporkan berhasil, supaya saya tidak dibohongi seperti kasus bot yang mengaku
    mencatat padahal ditolak.
26. Sebagai anggota keluarga, saya ingin bila data sudah berubah antara Pratinjau dan jawaban
    *ya* (mis. ada ubahan lain), perubahan ditolak dan Pratinjau dibuat ulang, supaya saya tidak
    menimpa keadaan yang tidak saya lihat.
27. Sebagai anggota keluarga, saya ingin baris pembuka saldo (`opening_balance`) tidak bisa
    diubah atau dihapus lewat chat, supaya Saldo Awal tidak rusak ([ADR-0008](../adr/0008-saldo-awal-20-5-juta-dan-koreksi-rekonsiliasi.md)).
28. Sebagai anggota keluarga, saya ingin transfer antar akun tetap valid setelah diubah (akun
    asal dan tujuan wajib ada, kategori `transfer` tetap), supaya Saldo global tidak bergeser.
29. Sebagai anggota keluarga, saya ingin No Resi sebuah Transaksi tidak bisa diubah, supaya
    deteksi Duplikat dan tautan Kewajiban tidak putus.
30. Sebagai anggota keluarga, saya ingin diperingatkan bila Transaksi yang akan dihapus atau
    diubah adalah pembayaran sebuah Kewajiban, supaya saya tahu Kewajiban itu akan kembali
    berstatus belum lunas.
31. Sebagai anggota keluarga, saya ingin diperingatkan bila perubahan jatuh pada bulan yang sudah
    dilaporkan, supaya saya tahu angkanya akan muncul sebagai Koreksi di Laporan Bulanan berikut.
32. Sebagai pemilik, saya ingin setiap perubahan lewat skrip didahului cadangan otomatis file
    sebelum diubah, supaya salah hapus bisa dipulihkan.
33. Sebagai pemilik, saya ingin setiap ubah/hapus tercatat di jejak append-only (kapan, siapa,
    sebelum, sesudah), supaya saya bisa menelusuri apa yang terjadi pada angka saya.
34. Sebagai pemilik, saya ingin jejak perubahan tidak ikut masuk git, supaya data keuangan pribadi
    tidak bocor ([ADR-0004](../adr/0004-data-transaksi-tidak-masuk-git.md)).
35. Sebagai pemilik, saya ingin jejak perubahan itu sendiri tidak bisa diubah atau dihapus lewat
    chat, supaya ia tetap bisa dipercaya.
36. Sebagai pemilik, saya ingin penulisan file atomik dan terkunci, supaya pesan WhatsApp
    bersamaan atau proses yang mati di tengah tidak merusak `bills.csv`.
37. Sebagai pemilik, saya ingin format akhir baris (CRLF/LF) dan 12 kolom `bills.csv` dipertahankan
    setelah ubah/hapus, supaya skrip lain (laporan, ekspor, pemeriksa kesehatan) tidak rusak.
38. Sebagai pemilik, saya ingin urutan baris lain tidak berubah oleh ubah/hapus, supaya diff
    terhadap cadangan hanya memuat yang memang berubah.
39. Sebagai pemilik, saya ingin bot dilarang menulis CSV dengan Edit/Write bahkan untuk ubah dan
    hapus, supaya hanya ada satu jalan tulis yang tervalidasi.
40. Sebagai pemilik, saya ingin kontrak percakapan ubah/hapus tertulis di `AGENTS.md` dan dijaga
    tes dokumen, supaya perilakunya tidak menyimpang antar-sesi ([ADR-0014](../adr/0014-bukti-transfer-dikonfirmasi-dulu-kontrak-di-agents-md.md)).
41. Sebagai pemilik, saya ingin satu deklarasi skema (kolom, kunci, kolom yang tak boleh diubah,
    aturan validasi) cukup untuk memberi CSV baru keempat operasi, supaya CSV masa depan tidak
    mengulang pekerjaan ini.
42. Sebagai pemilik, saya ingin pesan error dari skrip memuat contoh masukan yang benar dan
    kalimat "tidak ada yang berubah", supaya model tidak mengarang keberhasilan.
43. Sebagai pengembang, saya ingin ubah dan hapus bisa diuji sepenuhnya lewat satu antarmuka
    skrip terhadap CSV sementara, supaya perilaku terlihat dari luar dan tes tidak rapuh terhadap
    refaktor.

## Implementation Decisions

**Cakupan data.** "Data di CSV" hari ini berarti `bills.csv`. Berkas JSON (kewajiban, perkiraan,
akun, pembeli, budget) bukan CSV dan tidak dimigrasi. Cadangan harian dan ekspor Excel adalah
turunan, bukan data sumber, jadi tidak diberi CRUD. Mesin CRUD dirancang generik supaya CSV baru
cukup mendaftarkan skema.

**Satu mesin CRUD, satu CLI.** Modul baru (skrip `buku`) dengan subperintah `cari`, `ubah`,
`hapus`; Create tetap `catat.py` (antarmukanya tidak berubah). Logika validasi kolom yang sama
(kategori sah, jumlah rupiah > 0, tanggal ISO, jam `HH:MM`, aturan transfer, larangan
`opening_balance`) dipakai bersama oleh `catat.py` dan mesin baru, tidak disalin. Skrip mengikuti
kebiasaan skrip yang ada: Python 3.9-kompatibel (`from __future__ import annotations`), JSON di
stdin, kode keluar 0/1/2, dan awalan keluaran `OK ...`, `DUPLICATE ...`, `ERROR ...`.

**Skema per CSV.** Satu deklarasi memuat: nama berkas, daftar kolom berurutan, kunci Transaksi,
kolom yang tidak boleh diubah, validator per kolom, dan pemeriksa duplikat. `bills.csv` mendaftar:
kunci = No Resi; tak boleh diubah = `no_resi` dan `channel` (Asal); kolom yang boleh diubah =
`tanggal`, `waktu`, `tipe`, `kategori`, `item`, `jumlah`, `catatan`, `pencatat`, `akun`,
`akun_tujuan`.

**Identitas baris.** Satu Transaksi = semua baris ber-No Resi sama. Menunjuk Transaksi lewat No
Resi; menunjuk satu Item lewat nomor urut Item di dalam Transaksi itu (urutan seperti di file,
dimulai dari 1, ditampilkan oleh `cari` dan Pratinjau). Item kembar tidak dibedakan selain lewat
nomor urut.

**Read (`cari`).** Filter yang bisa digabung: No Resi, tanggal atau rentang tanggal, Kategori,
Pencatat/Pembeli (alias dibakukan lewat tabel pembeli yang ada), kata dalam Item, tipe. Hasil
dikelompokkan per Transaksi dengan nomor urut Item dan total, terbaru dulu, dengan batas jumlah
Transaksi dan penanda "terpotong". Read-only, tidak mengunci tulis, tidak butuh Pratinjau.
`cari` juga mendukung "Transaksi terakhir oleh Pencatat X" untuk menggantikan "hapus terakhir".

**Update (`ubah`).** Masukan JSON: No Resi, nomor Item opsional (kosong = berlaku ke semua Item
untuk kolom tingkat-Transaksi seperti tanggal/waktu/pencatat/akun; kolom tingkat-Item seperti
kategori/item/jumlah wajib menyebut nomor Item atau diterapkan eksplisit ke semua), dan
himpunan perubahan kolom. Hasil akhir divalidasi penuh seolah Transaksi baru (aturan yang sama
dengan `catat.py`) dan dicek Duplikat terhadap baris lain (Lapis 2 yang sama; Lapis 1 tak
relevan karena No Resi tak berubah). Tipe/kategori `transfer` dan akun asal/tujuan harus tetap
konsisten.

**Delete (`hapus`).** Menghapus satu Transaksi utuh atau satu Item (nomor urut). Menghapus Item
terakhir sebuah Transaksi sama dengan menghapus Transaksi. Baris `opening_balance` ditolak.
Hapus tidak pernah massal: satu panggilan menunjuk tepat satu Transaksi atau satu Item; pencarian
yang cocok banyak Transaksi tidak pernah langsung berujung hapus.

**Pratinjau dua langkah, mengikuti ADR-0016.** Setiap `ubah`/`hapus` punya mode `--uji` yang
tidak menulis dan mengeluarkan: baris sebelum, baris sesudah (atau "akan dihapus"), selisih
total/Saldo, peringatan (lihat di bawah), dan satu **sidik keadaan** (hash isi Transaksi yang
dituju). Bot menampilkan kerangka Pratinjau baru ("✏️ Akan diubah (belum berubah)" /
"🗑️ Akan dihapus (belum berubah)") dan baru menjalankan tanpa `--uji` setelah *ya*, dengan
masukan yang sama ditambah sidik tadi. Bila isi Transaksi sudah berbeda dari sidik (ada ubahan
lain di antaranya), skrip menolak dengan `ERROR`, tidak menulis, dan bot membuat Pratinjau ulang.
Draf ubah/hapus hanya hidup di percakapan, tidak ada status draf di CSV (alasan sama dengan
ADR-0014/0016); transaksi atau perintah baru sebelum menjawab membuang draf lama dengan
kalimat pemberitahuan tetap.

**Peringatan di Pratinjau (tidak memblokir).**
(a) Transaksi dirujuk `lunas_resi` oleh sebuah Kewajiban: Kewajiban itu akan kembali "belum
lunas" bila Transaksi dihapus atau No Resi-nya berubah (No Resi tak bisa berubah, jadi hanya
hapus). (b) Bulan Transaksi (lama atau baru) sudah dilaporkan Laporan Bulanan: perubahan akan
muncul sebagai Koreksi, sesuai definisi Koreksi di CONTEXT.md. Skrip hanya membaca simpanan
laporan dan kewajiban, tidak mengubahnya.

**Keselamatan tulis.** Setiap mutasi berjalan di bawah kunci berkas yang sama dengan `catat.py`
(`flock`), menulis ke berkas sementara di folder yang sama lalu `rename` atomik, dan sebelumnya
menyalin file apa adanya ke `data/backups/` dengan nama bercap waktu. Format akhir baris dan
urutan baris lain dipertahankan; header ditulis dengan kolom kanonik. Cadangan ubah/hapus
dipangkas dengan kebijakan retensi yang sama dengan cadangan harian.

**Jejak perubahan.** Berkas CSV append-only baru (waktu, aksi ubah/hapus, No Resi, nomor Item,
sebelum, sesudah, pengirim pesan). Masuk `.gitignore` (data pribadi, ADR-0004), contoh header
ikut dilacak sebagai `.example`. Jejak ini sengaja **tanpa** CRUD: ia satu-satunya data yang
tidak bisa diubah lewat chat, dan skema CRUD menandainya sebagai append-only.

**Kontrak bot.** `AGENTS.md` mendapat bagian "Mengubah dan menghapus" (kerangka Pratinjau, urutan
`--uji` → *ya* → eksekusi, aturan klaim hanya setelah `OK terubah`/`OK terhapus`, pilih bila
pencarian ambigu, larangan Edit/Write). SKILL.md: bagian "Hapus Transaksi Terakhir" dan catatan
"tulis ulang file" diganti ke alur baru; pemicu baru untuk cari/ubah/hapus. ADR baru mencatat
keputusan ini dan menandai bagian terkait ADR-0005 dan 0016 sebagai diperluas.

**Kompatibilitas.** Skrip pembaca lain (laporan bulanan/mingguan/pembeli, pemeriksa budget,
ekspor Excel, pemeriksa kesehatan) tidak berubah; mereka sudah menghitung ulang dari CSV setiap
kali jalan. Mekanisme Koreksi Laporan Bulanan menangkap perubahan pada bulan yang sudah
dilaporkan tanpa perubahan di sana.

## Testing Decisions

**Tes yang baik di sini** menjalankan antarmuka skrip terhadap CSV sementara dan memeriksa apa
yang terlihat dari luar: isi berkas sesudahnya, kode keluar, awalan keluaran (`OK`, `DUPLICATE`,
`ERROR`), dan keberadaan cadangan serta jejak. Tidak menguji fungsi internal, urutan pemanggilan,
atau bentuk struktur data antara.

**Seam yang dipakai: satu.** Fungsi masukan-ke-hasil `(kode, pesan)` dari skrip CRUD baru, dipanggil
dengan jalur data yang diarahkan ke direktori sementara. Persis pola `tests/test_catat.py`
(mengganti path CSV/budget/pembeli lewat modul `resi`). Semua perilaku di bawah dicapai dari seam
ini; tidak ada seam kedua untuk mesin atau validator.

Perilaku yang dijaga di seam itu:
- Read: tiap filter dan kombinasinya, pengelompokan per Transaksi, batas/terpotong, tanpa hasil.
- Update: tiap kolom yang boleh diubah; kolom tak boleh diubah (`no_resi`, `channel`) ditolak;
  Item tunggal vs seluruh Transaksi; hasil divalidasi ulang (kategori, jumlah, tanggal, jam,
  transfer); Duplikat setelah ubah ditolak; `opening_balance` ditolak.
- Delete: Transaksi utuh, satu Item, Item terakhir = Transaksi utuh, `opening_balance` ditolak,
  penunjuk ambigu atau tidak ada ditolak tanpa menulis.
- Pratinjau: `--uji` tidak menulis apa pun (berkas identik byte demi byte); sidik basi ditolak.
- Keselamatan: cadangan dibuat sebelum mutasi; baris lain, urutan, dan akhir baris (CRLF vs LF)
  utuh; header 12 kolom; jejak bertambah satu baris per mutasi dan tidak bertambah pada `--uji`
  atau penolakan; dua mutasi berurutan tidak saling menimpa.
- Peringatan: Kewajiban tertaut dan bulan yang sudah dilaporkan muncul di keluaran `--uji`.
- Jejak append-only: tak ada jalur ubah/hapus untuknya.

**Tes kontrak dokumen.** Perluas `tests/test_kontrak_prompt.py` agar menjaga bahwa `AGENTS.md`
memuat kerangka Pratinjau ubah/hapus, aturan klaim hanya setelah `OK terubah`/`OK terhapus`, dan
larangan Edit/Write; serta bahwa SKILL.md tidak lagi menyuruh "tulis ulang file". Tes ini hanya
membuktikan teksnya ada, bukan kepatuhan model (batasan yang sama dengan ADR-0014).

**Prior art.** `tests/test_catat.py` (pola CSV sementara, path diganti, mengecek berkas dan
keluaran), `tests/test_kontrak_prompt.py` (kontrak teks), `tests/test_laporan_bulanan.py`
(perilaku Koreksi).

## Out of Scope

- Migrasi berkas JSON (kewajiban, perkiraan, akun, pembeli, budget) ke CSV, atau CRUD untuknya.
  Kategori sudah punya tambah/hapus lewat skill dan tidak diubah di sini.
- Hapus massal, ubah massal, atau "reset semua".
- Mengubah `channel` (Asal) atau `no_resi`.
- Membuat, mengubah, atau menghapus baris `opening_balance`, serta mengoreksi Saldo Awal
  (jalur rekonsiliasi pemilik, ADR-0008).
- Pemulihan otomatis dari cadangan ("undo") lewat chat; pemulihan tetap manual dari
  `data/backups/` dan jejak perubahan.
- Antarmuka web atau aplikasi untuk CRUD; semuanya lewat chat dan CLI.
- Perubahan format Laporan Bulanan/Mingguan atau mekanisme Koreksi.
- Hak akses berbeda antar anggota keluarga; semua pengirim yang sudah diizinkan gateway setara.

## Further Notes

- `data/bills.csv.example` hari ini berheader 10 kolom sedangkan `catat.py` menulis 12 kolom
  (tambah `akun`, `akun_tujuan`). Contoh perlu disamakan dengan kolom kanonik sebagai bagian
  pekerjaan ini, dan penulisan ulang file oleh mesin CRUD harus selalu memakai kolom kanonik.
- Istilah di CONTEXT.md perlu ditambah: **Jejak Perubahan** (catatan append-only ubah/hapus) dan
  penegasan bahwa **Pratinjau** juga berlaku untuk ubah/hapus. Hindari "edit", "record", "entri"
  (sudah di daftar _Avoid_ untuk Transaksi).
- Risiko utama bukan skrip melainkan model yang melewati skrip. Selama kontrak hanya hidup di
  teks `AGENTS.md`, kepatuhan tidak terjamin oleh tes; pagar sebenarnya adalah skrip menolak
  keadaan tak sah, sidik basi, dan larangan tulis langsung.
- Seam pengujian di atas sengaja satu. Bila saat pengerjaan tampak perlu seam kedua (mis. untuk
  skema CSV kedua), usulkan dulu sebelum menambahnya.
