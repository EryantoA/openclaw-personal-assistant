> **Sebagian digantikan oleh [0016](0016-pratinjau-sebelum-simpan-untuk-semua-pencatatan.md):**
> konfirmasi dulu kini berlaku untuk semua pencatatan, bukan hanya Bukti Transfer.

# Bukti Transfer dikonfirmasi dulu, kontraknya hidup di AGENTS.md

Foto bukti transfer lewat dua langkah: bot membalas ringkasan bacaan + pertanyaan
(kategori, akun), baru memanggil `catat.py` setelah dijawab. Struk belanja dan teks bebas
tetap langsung dicatat (aturan lama di `AGENTS.md`).

## Kenapa

Pada 5 Okt 2026 bot membaca bukti transfer Rp 2.006.500, bertanya dengan bentuk improvisasi,
lalu mencatat Rp 2.000.000 dengan "Akun: <nama orang>", resi karangan berawalan sendiri, dan
klaim "61 entri tercatat" yang tidak pernah dihitung. Bentuk tanya dan balasan juga berbeda
setelah sesi direset. Akarnya sama dengan [0011](0011-penjaga-kesehatan-tidak-boleh-butuh-model.md)
dan commit `5ed904a`: perilaku yang hanya hidup di percakapan dan tidak di berkas yang selalu
dibaca bot akan ditiru-tiru lalu menyimpang.

OCR gambar bisa salah baca, dan tulisan ke buku kas tidak mudah ditarik
([0005](0005-bill-tracker-sebagai-sistem-resmi.md)), jadi untuk gambar mutasi satu putaran
konfirmasi sepadan. Akun wajib ditanyakan sesudah cutover ([0010](0010-akun-dan-transfer-lewat-cutover.md)).

## Kenapa bukan di skrip

`catat.py` tidak melihat gambar dan tidak punya keadaan "belum disimpan". Menambah status draft
ke CSV mengubah skema data demi perilaku percakapan. Pagar data (duplikat, kategori, transfer
wajib dua akun) tetap di skrip; kontrak percakapan ada di `AGENTS.md` dan dijaga tes dokumen
`tests/test_kontrak_prompt.py`. Tes itu hanya membuktikan teksnya ada, bukan kepatuhan model.
