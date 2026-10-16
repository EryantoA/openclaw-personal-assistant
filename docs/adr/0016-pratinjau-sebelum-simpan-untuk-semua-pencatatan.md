# Semua pencatatan lewat Pratinjau dulu; uji coba skrip mengisi nilainya

Setiap pencatatan (struk, teks, pemasukan, transfer, Bukti Transfer) melalui dua langkah: bot
menjalankan `catat.py --uji`, menampilkan **Pratinjau** "Akan disimpan (belum dicatat)", lalu
menyimpan hanya setelah pengguna membalas *ya*. Menggantikan sebagian
[0014](0014-bukti-transfer-dikonfirmasi-dulu-kontrak-di-agents-md.md): Bukti Transfer bukan lagi
pengecualian, melainkan varian dari alur umum.

## Kenapa

OCR bisa salah baca dan tulisan ke buku kas tidak mudah ditarik
([0005](0005-bill-tracker-sebagai-sistem-resmi.md)). Aturan lama "langsung catat bila jelas"
membuat salah baca baru ketahuan setelah tersimpan, lalu harus dihapus dan dicatat ulang.
Pemilik meminta (16 Okt 2026) agar bot bertanya dulu apa yang akan disimpan ke CSV.
Harganya satu balasan tambahan per pencatatan; disengaja.

## Keputusan

- **Nilai pratinjau dari skrip:** `--uji` memberi no resi, jam, tanggal, pencatat yang asli dan
  menolak duplikat/kategori salah sebelum bertanya. Penyimpanan memakai no resi dan jam yang sama.
- **Draf hanya di percakapan.** Tidak ada status draf di CSV (alasan sama dengan 0014).
  Transaksi baru sebelum jawaban membuang draf lama dengan pemberitahuan.
- **Selisih total** struk vs jumlah item ditanyakan; diskon/PPN/layanan jadi item sendiri hanya
  setelah disetujui. Skema CSV tidak berubah.
- Kontrak ada di `AGENTS.md`, dijaga `tests/test_kontrak_prompt.py`; tes hanya membuktikan teks
  ada, bukan kepatuhan model.
