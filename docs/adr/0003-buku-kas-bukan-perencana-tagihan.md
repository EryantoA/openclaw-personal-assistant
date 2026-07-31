# Ini buku kas, bukan perencana tagihan

> **Dibatalkan sebagian oleh [0006](0006-kewajiban-dan-perkiraan.md)** (31 Jul 2026). Syarat
> pembatalan yang ditulis di bawah — munculnya tagihan pascabayar — sudah terpenuhi, dan
> konsepnya dibangun ulang di luar `bills.csv` sebagai Kewajiban & Perkiraan. Yang tetap
> berlaku dari ADR ini: kolom `jatuh_tempo` di `bills.csv` tidak dihidupkan, dan tidak ada
> cron harian khusus tagihan.

Kolom `jatuh_tempo`, mode `--mode jatuh_tempo` di `scripts/check-bills.py`, cron harian
`reminder_jatuh_tempo`, dan istilah "Jatuh Tempo" di `CONTEXT.md` semuanya dibuang. Alasannya
empiris: setelah empat bulan pemakaian nyata, `jatuh_tempo` terisi di **0 dari 226 baris**.

Sebabnya terlihat jelas di data. Seluruh tagihan keluarga ini prabayar — pulsa, paket data
MyTelkomsel, gas Elpiji, top-up GoPay — dibeli di tempat, bukan datang lebih dulu lalu dibayar
belakangan. BPJS pun dicatat setelah dibayar. Konsep "kewajiban yang belum dibayar" tidak
pernah muncul.

## Consequences

Kalau kelak ada tagihan pascabayar (listrik PLN, internet bulanan, cicilan), fiturnya harus
dibangun ulang dari nol. Itu diterima: menyimpan fitur mati membuat `CONTEXT.md` berbohong
soal apa yang sebenarnya penting di domain ini, dan cron yang tiap hari berjalan tanpa pernah
menghasilkan apa pun hanya melatih orang mengabaikan notifikasi.

`scripts/check-bills.py` jadi hanya punya satu fungsi — cek budget. Argumen `--mode` disisakan
(`budget` dan `all`) supaya prompt cron yang sudah ada tidak perlu diubah.
