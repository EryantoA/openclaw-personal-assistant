# Spec: Bot bertanya dulu sebelum menyimpan ke CSV, dan membaca struk lebih lengkap

Status: siap dikerjakan (semua rekomendasi ronde tanya-jawab 16 Okt 2026 diterima pemilik).
Turunan dari [ADR-0014](../adr/0014-bukti-transfer-dikonfirmasi-dulu-kontrak-di-agents-md.md) dan
[ADR-0015](../adr/0015-balasan-struk-memuat-tanggal-dan-pembeli.md).

## Problem Statement

Hanya Bukti Transfer yang ditanyakan dulu. Struk foto dan teks bebas langsung masuk `bills.csv`,
padahal OCR bisa salah baca dan tulisan ke buku kas tidak mudah ditarik
([ADR-0005](../adr/0005-bill-tracker-sebagai-sistem-resmi.md)). Pengguna baru tahu ada salah
setelah tersimpan. Selain itu bot belum membaca diskon, PPN, biaya layanan, jumlah×harga satuan,
dan cara bayar dari struk, sehingga total di CSV bisa tidak sama dengan total di struk, dan
belum ada cara melihat pengeluaran per **Pembeli**.

## Solution

Semua pencatatan lewat dua langkah: bot menampilkan **Pratinjau** persis apa yang akan jadi baris
CSV (diisi dari uji coba skrip, bukan tebakan), pengguna menjawab ya / koreksi / batal, baru
bot menyimpan. Bot juga membaca lebih banyak dari struk dan menandai selisih total. Ditambah
laporan pengeluaran per Pembeli yang dihitung skrip.

## Alur (dengan project sekarang)

```
Pengguna kirim foto struk / teks / pemasukan / transfer / Bukti Transfer
        |
        v
Bot membaca: nomor struk, tanggal, jam, barang + harga (qty x satuan),
             diskon, PPN/layanan, cara bayar, total tercetak, Pembeli (= pengirim)
        |
        v
Bot menyusun JSON  --->  catat.py --uji   (tidak menulis; isi no_resi/jam,
        |                                  cek duplikat & kategori)
        |                     |
        |        DUPLICATE ---+--> bot: "sudah tercatat", berhenti
        |        ERROR     ---+--> bot perbaiki JSON, uji lagi
        v
Bot kirim PRATINJAU "Akan disimpan (belum dicatat)"
   - jumlah item vs total struk: selisih? -> peringatan + tanya cara mencatat
   - tanya hanya yang belum bisa dijawab (kategori, akun)
        |
        +--> "ya"            --> catat.py (tanpa --uji) --> hanya bila "OK tersimpan":
        |                        balas "Sudah dicatat!" (kerangka ADR-0015)
        +--> koreksi bebas   --> susun ulang --> uji --> pratinjau baru
        +--> "batal"         --> tidak ada yang disimpan
        +--> transaksi baru sebelum dijawab --> draf lama dibuang, bot bilang
                                                 "yang tadi tidak tersimpan"
```

Kerangka pratinjau (bentuknya tetap, dijaga tes):

```
🧾 Akan disimpan (belum dicatat)

Struk: <no_resi> | Tanggal: <tanggal> | Jam: <waktu>
Pembeli: <pencatat>

Detail:
- <item>: Rp 34.010
- Total: Rp 58.510

Kategori: <per item>   Akun: <dari data/akun.json>
Catatan: <cara bayar>

Balas *ya* untuk simpan, *batal*, atau tulis yang mau diubah.
```

## Pembanding: sebelum vs sesudah

| Hal | Sebelum | Sesudah |
|---|---|---|
| Struk foto | Langsung disimpan | Pratinjau dulu, simpan setelah "ya" |
| Teks bebas, pemasukan, transfer | Langsung disimpan | Pratinjau dulu |
| Bukti Transfer | Dua langkah (pengecualian) | Dua langkah, kini aturan umum |
| Aturan di `AGENTS.md` | "Langsung jalankan, jangan tanya" + satu pengecualian | Satu aturan: selalu pratinjau |
| Nilai di pratinjau | Tidak ada pratinjau (Bukti Transfer: bacaan model) | Dari `catat.py --uji` (no resi, jam asli; duplikat terdeteksi sebelum bertanya) |
| Duplikat | Ketahuan setelah mencoba menyimpan | Ketahuan sebelum bertanya |
| Total struk vs jumlah item | Tidak dibandingkan | Dibandingkan; selisih ditanyakan |
| Diskon / PPN / layanan | Tidak dibaca khusus | Dibaca; dicatat sebagai item sendiri bila disetujui |
| Qty × harga satuan, cara bayar | Hanya sesekali di nama item | Dibaca; cara bayar masuk catatan |
| Pembeli | Tidak tampil (sebelum ADR-0015) | Tampil, dari pengirim pesan |
| Koreksi salah baca | Hapus transaksi terakhir, catat ulang | Cukup balas koreksi sebelum tersimpan |
| Laporan per orang | Tidak ada | Pengeluaran per Pembeli per pekan/bulan, dihitung skrip |
| Pencarian transaksi | Tanpa kerangka tetap | Menampilkan Tanggal dan Pembeli |
| Skema `bills.csv` | 12 kolom | Tetap 12 kolom |
| Jumlah langkah pengguna | 1 pesan | 2 pesan (harga: satu balasan "ya" demi kebenaran) |

## User Stories

1. Sebagai pengguna, saya ingin melihat apa yang akan disimpan sebelum masuk CSV, supaya salah baca ketahuan lebih awal.
2. Sebagai pengguna, saya ingin pratinjau berlaku untuk struk, teks, pemasukan, dan transfer, supaya perilaku bot seragam.
3. Sebagai pengguna, saya ingin menjawab "ya" untuk menyimpan, supaya konfirmasi cepat.
4. Sebagai pengguna, saya ingin mengoreksi dengan kalimat bebas ("kategori jadi transport"), supaya tak perlu mengulang dari awal.
5. Sebagai pengguna, saya ingin pratinjau baru setelah koreksi, supaya saya melihat hasil akhirnya sebelum simpan.
6. Sebagai pengguna, saya ingin "batal" membuang draf tanpa jejak di CSV.
7. Sebagai pengguna, saya ingin draf lama dibuang bila saya mengirim transaksi baru, dan bot menyebut yang tadi tidak tersimpan, supaya tidak ada simpanan tak sengaja.
8. Sebagai pengguna, saya ingin no resi dan jam di pratinjau sudah nilai asli, supaya sama dengan yang tersimpan.
9. Sebagai pengguna, saya ingin tahu duplikat sebelum ditanya apa pun, supaya tidak membuang waktu.
10. Sebagai pengguna, saya ingin bot memperbaiki masukan yang ditolak skrip sendiri, supaya saya tak melihat pesan error.
11. Sebagai pengguna, saya ingin total item dibandingkan dengan total struk, supaya selisih tidak lolos diam-diam.
12. Sebagai pengguna, saya ingin diskon, PPN, dan biaya layanan muncul sebagai baris sendiri bila saya setuju, supaya total cocok dengan struk.
13. Sebagai pengguna, saya ingin qty × harga satuan terbaca, supaya detail item akurat.
14. Sebagai pengguna, saya ingin cara bayar masuk catatan, supaya bisa ditelusuri.
15. Sebagai pengguna, saya ingin Pembeli selalu tampil, supaya jelas siapa yang belanja.
16. Sebagai pengguna, saya ingin laporan pengeluaran per Pembeli untuk pekan/bulan, supaya bisa melihat kontribusi tiap anggota.
17. Sebagai pengguna, saya ingin angka laporan per Pembeli sama dengan laporan lain, supaya tidak ada dua versi angka.
18. Sebagai pengguna, saya ingin pencarian transaksi menampilkan Tanggal dan Pembeli, supaya hasilnya mudah dicek.
19. Sebagai pengguna, saya ingin bot tidak menyebut "sudah dicatat" sebelum skrip bilang `OK tersimpan`, supaya tak ada klaim palsu.
20. Sebagai pengguna, saya ingin bot hanya menanyakan yang belum bisa dibaca (kategori, akun), supaya pratinjau tak berisi pertanyaan berlebih.
21. Sebagai pengguna, saya ingin gambar buram diminta kirim ulang, bukan ditebak.
22. Sebagai pengguna, saya ingin angka berbeda dari yang saya sebut diberi tahu selisihnya, bukan diubah diam-diam.
23. Sebagai pengembang, saya ingin satu aturan di `AGENTS.md` (bukan pengecualian), supaya tidak ada dua jalur perilaku.
24. Sebagai pengembang, saya ingin tidak ada status draf di CSV, supaya skema data tetap bersih.
25. Sebagai pengembang, saya ingin tes kontrak yang gagal bila kerangka pratinjau di `AGENTS.md` dan skill berbeda.
26. Sebagai pengembang, saya ingin laporan per Pembeli berupa skrip dengan tes, mengikuti laporan mingguan/bulanan.
27. Sebagai pengembang, saya ingin ADR baru yang menggantikan pengecualian ADR-0014, supaya alasan perubahan tercatat.
28. Sebagai pengembang, saya ingin istilah **Pratinjau** masuk glosarium, supaya kosakata konsisten.

## Implementation Decisions

- **Satu aturan umum:** semua pencatatan lewat Pratinjau lalu simpan. Aturan "langsung jalankan"
  dan pengecualian Bukti Transfer di prompt utama dilebur menjadi satu alur. ADR baru
  menggantikan sebagian ADR-0014 (kerangka Bukti Transfer dipertahankan sebagai varian).
- **Pratinjau dari uji coba skrip:** bot memanggil skrip pencatat dalam mode uji (sudah ada) untuk
  mendapatkan no resi, jam, dan hasil cek duplikat/kategori; hanya pratinjau yang ditampilkan,
  tidak ada yang ditulis. Penyimpanan sesungguhnya setelah "ya".
- **Draf hanya hidup di percakapan.** Tidak ada status draf di CSV (alasan sama dengan ADR-0014).
  Transaksi baru sebelum jawaban membuang draf lama dengan pemberitahuan.
- **Pembandingan total:** bot menjumlahkan item dan membandingkan dengan total tercetak. Selisih
  dilaporkan di pratinjau; diskon/PPN/layanan menjadi item sendiri hanya setelah disetujui.
  Tanpa kolom CSV baru; cara bayar ke kolom catatan.
- **Pembeli** = pengirim pesan = `pencatat`. Istilah baru di glosarium: **Pratinjau**
  (apa yang akan disimpan, belum tertulis; bukan Transaksi). `Pembeli` sudah ada (ADR-0015).
- **Laporan per Pembeli:** skrip baru read-only, pola sama dengan laporan mingguan/bulanan
  (Pekan Senin–Minggu, bulan kalender), balasan bot menyalin keluaran utuh, tanpa `--kirim`.
  Hanya pengeluaran; Pemasukan dan transfer tidak dihitung. Baris lama tanpa pencatat
  dikelompokkan "Tanpa nama".
- **Pencarian transaksi** memakai kerangka tetap dengan Tanggal dan Pembeli.
- **Lokasi kontrak:** kerangka Pratinjau didefinisikan sekali di `AGENTS.md`; skill mencerminkan
  teks identik dan merujuk ke sana (pola ADR-0014/0015).
- **Skema CSV tidak berubah.**

## Testing Decisions

- Tes yang baik hanya memeriksa perilaku luar: teks kontrak yang dibaca bot dan keluaran skrip.
- **Seam 1, kontrak teks** (tes kontrak prompt yang ada): kerangka Pratinjau tepat satu kali di
  `AGENTS.md`, identik di skill; kalimat "langsung jalankan" tidak lagi ada sebagai aturan
  umum; larangan mengarang angka tetap; kerangka akhir `✅ Sudah dicatat!` tidak berubah.
- **Seam 2, laporan per Pembeli** (tes baru, pola tes laporan bulanan): jumlah per pencatat benar,
  hanya pengeluaran, batas pekan/bulan, baris tanpa pencatat, keluaran persis sama bila dijalankan
  dua kali.
- Skrip pencatat tidak berubah perilakunya (mode uji sudah ada dan sudah dites); cukup tes
  regresi yang ada.
- Tidak dapat dites otomatis: kepatuhan model. Uji manual di WhatsApp sesi baru: kirim struk
  (pratinjau muncul, "ya" menyimpan, "batal" tidak), struk dengan diskon (selisih ditanya),
  teks "beli beras 50rb" (pratinjau).

## Out of Scope

- Status draf atau tabel sementara di CSV.
- Grafik, ekspor baru, atau perubahan laporan mingguan/bulanan yang ada.
- Mengubah skema `bills.csv`.
- Menegakkan konfirmasi di level skrip (skrip tidak tahu percakapan); penegakan hanya lewat
  kontrak prompt dan tes teks.
- Pembatasan siapa boleh menjawab "ya" (hanya pengirim yang sama).

## Further Notes

- Dua seam saja: kontrak teks dan laporan per Pembeli. Seam skrip pencatat sudah ada.
- Tambahan satu pesan per transaksi adalah harga yang disengaja; bisa dilonggarkan nanti (mis.
  lewati pratinjau untuk teks sangat sederhana) hanya bila pemilik meminta.
- Penerbitan ke issue GitHub berlabel `ready-for-agent` belum dilakukan (tindakan keluar; repo
  belum punya konfigurasi tracker) — menunggu persetujuan pemilik.
