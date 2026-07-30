# Data transaksi tidak masuk git

`data/bills.csv` dikeluarkan dari pelacakan git (`git rm --cached`) dan dimasukkan ke
`.gitignore` bersama `data/*.bak`. Yang dilacak hanya `data/bills.csv.example` berisi baris
header — pola yang sama dengan `openclaw.json` / `openclaw.json.example` yang sudah dipakai
repo ini untuk kredensial.

`.gitignore` sebetulnya sudah menyatakan sikapnya sejak awal: `data/backups/*` dikecualikan
dengan alasan "data pribadi keluarga". Tapi file induknya sendiri dilacak, sementara repo
punya remote publik-mungkin di GitHub. Isinya gaji kedua orang, pembayaran BPJS, dan pembelian
cincin nikah Rp 12,88 juta. Beruntung yang terlanjur ter-commit baru baris header — nol
transaksi pernah keluar dari mesin.

## Considered Options

"Cukup pastikan repo-nya privat" ditolak: status privat sebuah repo bisa berubah kapan saja —
tidak sengaja dipublikkan, dipindahkan ke organisasi, atau di-fork — sementara riwayat git
bersifat permanen dan sulit dibersihkan setelah ter-push. Menjaga data tidak pernah masuk
riwayat jauh lebih murah daripada menghapusnya setelah masuk.

## Consequences

Data transaksi tidak punya riwayat versi maupun salinan luar-mesin lewat git. Perlindungannya
bergantung pada `data/backups/` (harian lewat `scripts/backup.sh`) dan `data/*.bak`, keduanya
lokal. Kalau disk hilang, datanya hilang — cadangan luar-mesin perlu diatur terpisah, bukan
lewat git.

`data/budget.json` tetap dilacak: isinya nama kategori dan ambang persen, bukan nominal
transaksi.
