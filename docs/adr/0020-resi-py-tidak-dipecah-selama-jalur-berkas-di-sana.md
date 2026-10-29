# resi.py tidak dipecah selama jalur berkas data tinggal di sana

Review arsitektur 28–29 Okt 2026 mengusulkan memecah `scripts/resi.py`, yang memuat No Resi,
alias Pembeli, normalisasi nilai (`norm_*`), konfigurasi Duplikat, label balasan bot, dan jalur
berkas (`BILLS_CSV`, `BUDGET_JSON`, `PEMBELI_JSON`). Usulan itu **tidak dikerjakan**.

## Kenapa

Yang mengikat module lain ke `resi.py` adalah **jalur berkasnya**, bukan fungsi-fungsinya.
`duplikat.py` butuh `resi.BUDGET_JSON`, alias Pembeli butuh `resi.PEMBELI_JSON`, dan ketiga jalur
itu adalah titik tambal (monkeypatch) di `test_catat.py`, `test_buku.py`, dan `test_duplikat.py`.
Memindahkan fungsi sambil membiarkan jalurnya di `resi.py` tidak memutus ketergantungan apa pun —
module baru tetap harus meng-import `resi`. Yang tersisa hanya memindah kode tanpa menyatukan
kompleksitas (gagal uji penghapusan).

Sisa gesekannya kecil: `resi.do_find_dup` meng-import `duplikat` di dalam fungsi, karena
`duplikat` meng-import `resi`. Itu impor lokal di satu perintah CLI dan tidak berbahaya.

## Kapan dibuka lagi

Hanya bersama keputusan memindahkan jalur berkas ke module pemilik berkasnya (`bills.csv` →
`buku_kas`, `pembeli.json` → module Pembeli, `budget.json` → yang perlu diputuskan, karena dipakai
bersama validasi, Duplikat, dan `check-bills.py`), dengan fixture tes yang ikut ditulis ulang.
Usulan memecah `resi.py` tanpa itu jangan diajukan ulang.

Catatan yang sudah diketahui (29 Okt 2026): `bills.csv` punya tujuh konstanta jalur (`buku_kas`,
`resi`, `akun`, `laporan-bulanan`, `check-bills`, `export-excel`, `periksa-kesehatan` — yang
terakhir sengaja, ADR-0011) dan `budget.json` tiga (`resi`, dipakai juga `validasi` dan `duplikat`;
`check-bills`; `laporan-bulanan`). Itu pekerjaan yang sama dengan di atas, bukan perbaikan
terpisah.
