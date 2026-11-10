# Peringatan Budget sekali per ambang, per bulan

> **Mengubah** perilaku peringatan [0024](0024-budget-adalah-batas-belanja-rutin.md) dan
> [0029](0029-batas-kategori-untuk-kategori-pilihan.md), dan prinsip `check-bills.py` "tidak pernah
> menulis" (ADR-0006) untuk satu berkas keadaan.

Setelah setiap pencatatan, bot menjalankan cek budget; selama Budget total atau sebuah Batas Kategori
di atas `alert_persen`, peringatan yang sama muncul di **setiap** balasan sampai akhir bulan, dan cron
malam mengirimnya lagi tiap malam. Peringatan yang selalu ada berhenti dibaca — pelajaran yang sama
yang melahirkan ADR-0024.

## Keputusan

- **Sekali per ambang, per bulan, per hal yang dibatasi.** Budget total dan tiap Batas Kategori
  masing-masing punya dua ambang: `alert_persen` (mendekati) dan 100% (lewat). Peringatan muncul
  saat pertama kali ambang itu dicapai di bulan tersebut; ambang yang lebih tinggi tetap muncul.
- **Ingatannya `data/peringatan-budget.json`**: bulan → {`total` | slug: ambang tertinggi yang sudah
  diperingatkan}. Hanya beberapa bulan terakhir disimpan; tidak ada isi Transaksi; di luar git.
  Ini satu-satunya berkas yang ditulis `check-bills.py`.
- **Satu ingatan untuk dua jalur:** yang sudah disebut setelah mencatat tidak diulang cek malam, dan
  sebaliknya.
- **Dicatat hanya bila sampai:** setelah mencatat, langsung (bot menyalin keluarannya ke balasan saat
  itu juga); cron malam, hanya bila pengiriman berhasil — gagal kirim berarti diulang malam
  berikutnya, bukan hilang.
- **Tidak berubah:** "sisa budget", Laporan Bulanan, dan tab Budget di Cermin selalu menampilkan
  status lengkap; yang berkurang hanya pengulangan peringatan.

## Ditolak

- **Sekali per hari:** tetap cerewet selama di atas ambang, sebulan bisa 20 kali.
- **Sekali per ambang + pengingat mingguan:** menambah pesan ke Laporan Mingguan, yang sengaja tidak
  memuat Batas Kategori (ADR-0029).
- **Tetap tanpa ingatan:** masalah awalnya.
