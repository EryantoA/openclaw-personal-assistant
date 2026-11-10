# Kelompok Kategori, empat kategori baru, dan "Lain-lain" hanya sebagai sisa

> **Memperluas** [0002](0002-slug-inggris-sebagai-acuan-kategori.md) (slug sebagai data) dan
> [0026](0026-cermin-sheets-berformat-buku-kas-dan-tab-laporan.md) (Label Kategori, tab Per Kategori).

"Lain-lain" (`other`) adalah kategori terbesar kedua — rata-rata Rp 1,22 jt belanja rutin per bulan,
66 pengeluaran senilai Rp 29,5 jt sejak Maret. Penelusuran baris per baris menemukan dua sebab:

1. **Banyak yang sebenarnya punya kategori:** cincin nikah (Perhiasan), infaq (Donasi & Zakat),
   makanan kucing (Hewan Peliharaan), potong rambut (Perawatan Diri), biaya nikah dan undangan (Acara
   & Kondangan), kredit Anthropic (Langganan).
2. **Sisanya tidak punya rumah:** perjalanan bulan madu (hotel, money changer, tiket ±Rp 9,4 jt),
   uang untuk orang tua, biaya transfer bank, pembayaran utang.

Pemilik ingin susunan kategori seperti pencatatan keuangan profesional.

## Keputusan

- **Dua tingkat: Kelompok di atas Kategori**, hanya untuk tampilan dan ringkasan. Peta di
  `budget.json` → `kelompok_kategori` ({Kelompok: [slug]}); data tetap slug (ADR-0002). Kategori yang
  tidak tercantum masuk **Lainnya**.

  | Kelompok | Kategori |
  |---|---|
  | Kebutuhan Pokok | Belanja Dapur, Makan & Minum, Listrik Air & Internet, Pulsa & Telepon, Transportasi, Rumah Tangga, Kesehatan, Pendidikan |
  | Gaya Hidup | Belanja Lain, Pakaian, Kecantikan, Perawatan Diri, Hiburan, Langganan, Hewan Peliharaan, Perhiasan, Liburan & Perjalanan |
  | Sosial & Keluarga | Donasi & Zakat, Hadiah, Acara & Kondangan, Arisan, Bantuan Keluarga |
  | Kewajiban & Biaya | Asuransi, Biaya Bank, Cicilan & Utang |

- **Empat kategori baru:** `travel` (Liburan & Perjalanan), `family_support` (Bantuan Keluarga),
  `bank_fees` (Biaya Bank), `debt_payment` (Cicilan & Utang). "Cicilan & Utang" adalah Kategori
  pembayaran, **bukan** Kewajiban (tagihan pascabayar) dan bukan neraca (ditunda, ADR-0027).
- **Tampil di:** tab Per Kategori `<tahun>` (Pengeluaran dikelompokkan dengan baris Subtotal per
  Kelompok) dan satu baris Laporan Bulanan
  (`🧭 Kebutuhan Pokok 52% · Gaya Hidup 31% · …`, porsi dari seluruh Pengeluaran). **Tidak** di
  Pratinjau dan balasan bot, Budget, maupun Batas Kategori.
- **"Lain-lain" hanya sisa:** bot memakai `other` hanya bila tidak ada kategori yang cocok, dan bila
  ragu menanyakannya; contoh kategori baru masuk tabel kategori di SKILL.md.
- **Baris lama dipindah lewat `buku.py ubah`** setelah pemilik menyetujui daftarnya (Jejak Perubahan,
  cadangan). Total Pemasukan/Pengeluaran tiap bulan tidak berubah, jadi tidak ada Koreksi; yang
  bergeser hanya angka per Kategori. Baris yang tujuannya belum diketahui tetap `other` — tidak
  ditebak.

## Ditolak

- **Mengganti kategori dengan hierarki di data (mis. `kebutuhan/food`):** membongkar ADR-0002 dan
  semua yang membaca slug; peta tampilan cukup.
- **"Tabungan & Investasi" sebagai kategori pengeluaran:** memindah uang ke tabungan adalah Transfer
  antar Akun (ADR-0010); mencatatnya sebagai pengeluaran membuat Arus Kas Bulanan tampak buruk
  padahal uangnya masih ada.
- **Kelompok di Budget:** Batas Kategori (ADR-0029) sudah menjawab "di mana harus direm"; batas per
  Kelompok menambah angka tanpa keputusan baru.
