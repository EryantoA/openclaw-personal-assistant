# Balasan struk memuat Tanggal dan Pembeli, nilainya dari keluaran catat.py

Kerangka `✅ Sudah dicatat!` kini selalu menampilkan lima hal dari sebuah struk: nomor struk,
tanggal, jam, barang, dan **Pembeli** (pengirim pesan). Nilai nomor, tanggal, jam, dan pencatat
disalin dari baris `OK tersimpan` `catat.py`, yang diperluas membawa `tanggal` dan `pencatat`.

## Kenapa

Pada 16 Okt 2026 pemilik meminta agar format pembacaan struk (nomor seri, tanggal, jam, apa
yang dibeli, siapa yang membeli) tidak terlupakan tiap sesi direset. Kerangka lama hanya memuat
nomor dan jam. Bentuk yang hanya hidup di percakapan akan ditiru-tiru lalu menyimpang
([0011](0011-penjaga-kesehatan-tidak-boleh-butuh-model.md),
[0014](0014-bukti-transfer-dikonfirmasi-dulu-kontrak-di-agents-md.md)), jadi kontraknya ditulis
di `AGENTS.md` (selalu masuk prompt), dicerminkan di skill, dan dijaga `tests/test_kontrak_prompt.py`.

## Kenapa nilainya dari skrip

Model tidak boleh mengarang angka atau nama; tanggal dan pencatat yang dicetak skrip adalah yang
benar-benar tertulis di buku kas. Skema `bills.csv` tidak berubah.

## Batas

Keputusan "struk langsung dicatat" di sini **digantikan oleh [0016](0016-pratinjau-sebelum-simpan-untuk-semua-pencatatan.md)**: kini semua pencatatan lewat Pratinjau; kerangka balasan akhir tetap berlaku. Tes hanya
membuktikan teks kontrak dan keluaran skrip, bukan kepatuhan model.
