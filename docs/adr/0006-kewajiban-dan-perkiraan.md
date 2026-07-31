# Kewajiban dan Perkiraan: jatuh tempo kembali, tapi statusnya tidak pernah disimpan

Membatalkan sebagian [0003](0003-buku-kas-bukan-perencana-tagihan.md).

ADR 0003 membuang seluruh fitur jatuh tempo dan menulis syarat pembatalannya sendiri: *"Kalau
kelak ada tagihan pascabayar (listrik PLN, internet bulanan, cicilan), fiturnya harus dibangun
ulang dari nol."* Syarat itu terpenuhi — `WiFi 233.000` (16 Jul 2026) adalah internet bulanan —
dan pemilik data mengonfirmasi tiga kekhawatiran sekaligus: lupa bayar pascabayar, kaget uang
tersedot langganan auto-debit, dan pemasukan yang telat masuk.

Bukti terkuat justru di pemasukan: gaji Rp 3.402.000 masuk 28 Apr, **tidak ada di Mei**, lalu
27 Jun dan 28 Jul. Entah tidak masuk, entah tidak tercatat — tiga bulan berlalu dan sudah tak
bisa dipastikan lagi. Itu kerugian yang fitur ini dimaksudkan cegah.

Dua konsep dipisah, bukan disatukan:

- **Kewajiban** (`data/kewajiban.json`) — tagihan pascabayar yang sudah datang. Dibuat manual
  saat tagihannya tiba, karena itu momen yang alami: pemiliknya memang sedang memegangnya.
- **Perkiraan** (`data/perkiraan.json`) — transaksi berulang yang diharapkan. Dideklarasikan
  manual, tapi **tidak lahir kosong**: diisi dari riwayat 285 baris yang sudah ada.

Kolom `jatuh_tempo` di `bills.csv` **tetap tidak dihidupkan**. Jatuh tempo adalah atribut sebuah
Kewajiban, bukan atribut sebuah Transaksi — mencampurnya ke buku kas adalah kekeliruan yang
membuatnya mati pertama kali.

## Considered Options

**Satu konsep gabungan ("Jadwal") ditolak.** Ketiga masalah memang berbentuk sama — "sesuatu
yang diharapkan terjadi tanggal X" — tapi Kewajiban menuntut tindakan manusia dan Perkiraan
tidak. Menyatukannya membuat notifikasi kehilangan perbedaan antara "bayar sekarang" dan
"sekadar tahu". Filenya pun dipisah karena siklus hidupnya berlawanan: `kewajiban.json` sering
ditulis ulang bot, `perkiraan.json` dirawat manusia dan nyaris tak berubah — menyatukannya
mengundang bot menimpa deklarasi yang tak ia pahami.

**Mendeteksi pola berulang otomatis dari riwayat ditolak.** Nol perawatan, tapi berarti bot
menyimpulkan pola keuangan sendiri. [ADR 0005](0005-bill-tracker-sebagai-sistem-resmi.md)
mencatat mahalnya kesalahan semacam itu — kesimpulan "tabungan awal Rp 20,5 juta" yang ternyata
artefak data tak lengkap.

**Menandai lunas secara manual ditolak — ini inti keputusannya.** `jatuh_tempo` tidak mati
karena konsepnya salah; ia mati karena menuntut manusia mengisi sesuatu. Menandai lunas adalah
tindakan kedua per tagihan, dan tindakan kedua itulah yang paling mungkin terlupa. Karena itu
**tidak ada satu pun field status yang disimpan**: yang tersimpan cuma fakta — `lunas_resi`,
tautan ke `no_resi` baris `bills.csv`. Aktif, lunas, dan kedaluwarsa seluruhnya dihitung ulang
tiap kali dari tautan itu + tanggal hari ini. `scripts/check-bills.py` karenanya tetap
read-only; cron tidak pernah menulis apa pun.

**Cron harian baru ditolak.** ADR 0003 menghukum cron yang jalan tiap hari tanpa pernah
menghasilkan apa pun karena "melatih orang mengabaikan notifikasi". Pengecekan menumpang
`cek_budget_malam` yang sudah ada dan mewarisi sifatnya: diam total kalau tak ada yang perlu
ditindak.

## Consequences

Bot wajib menautkan `lunas_resi` saat mencatat pembayaran. Ia akan lupa sesekali — model
primernya `groq/llama-3.3-70b-versatile`. Kalau lupa, pengingat berbunyi di H-2 dan hari-H lalu
**berhenti sendiri 5 hari setelah jatuh tempo**, dengan status tidak diketahui: bukan lunas,
bukan nunggak. Ini pilihan sadar — sebuah tagihan yang lolos sesekali lebih murah daripada
antrean kewajiban zombie yang mengajari orang menggeser notifikasi tanpa membacanya. Tautan yang
menunjuk baris tak ada diperlakukan belum lunas, supaya salah tulis ketahuan, bukan mengendap.

Pencocokan Perkiraan tidak selalu bisa memisahkan dua hal yang mirip. Terbukti saat pengujian:
gaji Teikoku (Rp 3.450.000) dan gaji istri (Rp 3.402.000) berbagi kategori `salary` dan hanya
berbeda **1,4%**, sehingga toleransi ±10% membuat yang satu menutupi absennya yang lain — uji
terhadap Mei 2026 semula lolos begitu saja. Karena itu toleransi bisa diperketat per entri
(`toleransi_persen`), dan gaji istri disetel 1%. Konsekuensinya, kenaikan gaji sekecil apa pun
akan memicu pertanyaan sampai `perkiraan.json` diperbarui. Itu diterima: pertanyaan yang salah
jauh lebih murah daripada absen yang senyap.

Kedua file memuat nominal (gaji, premi, langganan), jadi ikut dikecualikan dari git seperti
`bills.csv` — lihat [0004](0004-data-transaksi-tidak-masuk-git.md). Keduanya karenanya tidak
punya riwayat versi; kalau `perkiraan.json` terhapus, deklarasinya harus disusun ulang dari
riwayat `bills.csv`.
