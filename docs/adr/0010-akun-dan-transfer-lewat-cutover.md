# Akun dan transfer masuk lewat cutover, bukan diisi mundur

`bills.csv` mendapat kolom `akun` dan `akun_tujuan`, dan `tipe` mendapat nilai ketiga:
`transfer`. Saldo per akun dihitung dari saldo awal per akun pada satu tanggal **cutover**
(`data/akun.json`), bukan dengan menelusuri 357 baris yang sudah ada.

Fitur ini dibawa dari `openclaw-finansial-keluarga` yang dipensiunkan (lihat
`~/Developments/_arsip/README.md`). Di sana ada tiga akun terkonfigurasi — Kas, Bank Utama,
Tabungan — yang tidak punya padanan di bill-tracker.

Masalahnya, [0001](0001-saldo-adalah-kas-kumulatif.md) menetapkan Saldo sebagai satu kas
kumulatif dengan satu titik mulai. Memecahnya jadi tiga kantong secara surut mustahil: 357
baris antara 26 Mar dan 20 Agu 2026 tidak menyebut akun sama sekali, dan tidak ada cara
menyimpulkannya dari `catatan` maupun `channel`. Menebaknya akan menghasilkan tiga angka
yang terlihat masuk akal dan tidak satu pun benar — untuk buku kas, itu kegagalan yang
lebih buruk daripada tidak punya fiturnya.

Karena itu batasnya dibuat tegas dan diumumkan, bukan disamarkan: **sebelum cutover hanya
Saldo global yang bermakna; sejak cutover saldo per akun berlaku.** Baris lama dibiarkan
berkolom `akun` kosong. Kolom kosong yang jujur lebih berguna daripada kolom terisi yang
mengarang.

Aturan yang menjaga keduanya tetap tersambung: jumlah seluruh `saldo_awal` harus sama
dengan Saldo global pada tanggal cutover. `scripts/akun.py` menegakkannya dan melaporkan
selisih secara terbuka — tidak pernah menyerapnya diam-diam ke salah satu akun.

`transfer` ikut lahir di sini karena tanpanya fitur akun rusak pada pemakaian pertama:
memindahkan uang Bank Utama → Kas bukan pemasukan dan bukan pengeluaran, tapi model lama
hanya punya dua nilai itu. `export-excel.py` sebelumnya menghitung apa pun yang bukan
`pemasukan` sebagai pengeluaran, sehingga satu transfer Rp 500.000 akan menggelembungkan
pengeluaran bulan itu **dan** menurunkan Saldo — padahal uangnya tidak ke mana-mana.

## Considered Options

**Menyimpan saldo awal akun sebagai baris transaksi**, meniru cara Saldo Awal di
[0001](0001-saldo-adalah-kas-kumulatif.md), ditolak. Baris Saldo Awal berhasil karena ia
satu-satunya dan menjadi titik mulai rantai. Tiga baris saldo awal akun pada tanggal
cutover akan terhitung **dua kali**: sekali lewat 357 baris yang sudah membentuk saldo
sampai hari itu, sekali lagi lewat baris barunya. Menghindarinya menuntut tipe baris
pengecualian — lebih rumit daripada satu file konfigurasi.

**Mengisi `akun` secara mundur dengan tebakan** ditolak, alasannya di atas.

**Memakai `catatan` untuk menandai akun** ditolak. Pola itulah yang membunuh kolom `tempat`
di [0007](0007-kolom-tempat-dibuang.md), tapi arahnya berlawanan: di sana informasinya
memang sudah hidup di `item`, sedangkan di sini `catatan` hanya memuat cara bayar
(`Livin' by Mandiri`, `GoPay`) yang **bukan** akun. Cara bayar dan akun sumber dana sering
berbeda, dan mencampurnya akan membuat saldo salah tanpa ada yang menyadari.

**Menambahkan `akun` ke `duplicate_check.match_fields` sekarang juga** ditolak — ditunda
sampai cutover. Sebelum cutover kolomnya kosong di semua baris, dan `resi.py --check-dup`
menolak setiap pencatatan yang field wajibnya belum terisi, sehingga pencatatan harian
akan mati seketika. Instruksinya disimpan di `data/budget.json`.

## Consequences

Fitur ini **belum aktif**. `data/akun.json` sengaja dikirim dengan `saldo_awal: null`, dan
`scripts/akun.py` menolak menghitung apa pun sampai ketiganya diisi — angka saldo per akun
hanya boleh datang dari pemilik data, bukan dari tebakan.

Laporan harus menyebutkan batas cutover-nya setiap kali menampilkan saldo per akun, kalau
tidak pembaca akan mengira angka itu berlaku untuk seluruh riwayat.

Transaksi sejak cutover yang lupa menyebut `akun` tidak masuk hitungan akun mana pun.
`scripts/akun.py` melaporkannya sebagai peringatan tersendiri, bukan membebankannya ke
salah satu akun.
