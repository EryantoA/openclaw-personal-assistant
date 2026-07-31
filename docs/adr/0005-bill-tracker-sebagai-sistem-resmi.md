# bill-tracker sebagai satu-satunya sistem pencatatan

> **Dikoreksi oleh [0008](0008-saldo-awal-20-5-juta-dan-koreksi-rekonsiliasi.md)** (31 Jul 2026).
> Dua angka di bawah **salah**: saldo bukan +Rp 17.307.887 melainkan **+Rp 18.893.732**, dan
> saldo awalnya bukan nol melainkan **Rp 20.500.000**. Rekonsiliasi di bawah memakai saldo `Kas`
> app lama yang memuat baris borongan id 254 (Rp 22.456.955) — baris yang rebuild-nya sendiri
> buang. Keputusan pokok ADR ini (bill-tracker jadi satu-satunya sistem, `keuangan-keluarga`
> dimatikan) tetap berlaku.

Selama beberapa waktu ada **dua** bot keuangan aktif bersamaan lewat dua mekanisme berbeda:
`agents.defaults.skills` memuat `bill-tracker` (membaca `data/bills.csv`), sementara
`skills.entries."keuangan-keluarga".enabled` juga `true` (membaca
`~/.openclaw/skills/keuangan-keluarga/data/keuangan.json`). Bot menjawab pertanyaan laporan
dari `keuangan.json`, sehingga data yang diimpor ke `bills.csv` tampak "tidak terbaca".

`keuangan-keluarga` dimatikan. `bills.csv` dibangun ulang dari `keuangan.json` (251 transaksi,
27 Mar – 23 Jul 2026) digabung 22 baris asli bill-tracker → 272 baris. `keuangan.json` **tidak
dihapus** — ia jadi arsip sumber sekaligus alat rekonsiliasi.

## Consequences

**Saldo awal keluarga ini nol.** Catat baik-baik, karena sempat ada kesimpulan keliru bahwa
ada "tabungan awal minimal Rp 20,5 juta". Itu muncul karena analisis dijalankan atas backup
xlsx tanggal 9 Juli yang belum memuat gaji 20–21 Juli senilai Rp 38.047.224. Saldo yang tampak
minus Rp 16,6 juta seluruhnya artefak data yang belum lengkap. Angka yang benar: **+Rp 17.307.887**.

Pelajaran yang lebih umum: jangan menyimpulkan pola keuangan dari backup, selalu dari sumber
yang hidup. Backup selalu tertinggal, dan yang tertinggal justru bisa transaksi terbesarnya.

Rekonsiliasi terhadap sistem lama harus selalu cocok:
`15.160.568,67 (saldo Kas tersimpan) + 31.000 (bot lama meleset terhadap datanya sendiri)
+ 35.000 (duplikat id 213 dibuang) + 4.402.000 − 2.320.682 (delta bill-tracker) = 17.307.886,67`.

Fitur `recurring` sistem lama (`gaji-teikoku` Rp 3.450.000, `gaji-istri` Rp 3.402.000 bulanan)
tidak punya padanan di `bill-tracker` dan hilang saat berpindah.
