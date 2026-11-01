# Kategori custom: tambah, hapus, daftar

Daftar sah ada di `data/budget.json` → `kategori_custom`; kategori selalu slug Inggris huruf kecil.

## Tambah Kategori
Trigger: `tambah kategori [nama]`, `buat kategori [nama]`, `kategori baru [nama]`
Contoh: `tambah kategori investment`, `buat kategori home_repair`

Langkah:
1. Baca `data/budget.json`
2. Ubah nama dari pengguna ke slug Inggris huruf kecil `snake_case` (`Investasi` → `investment`);
   kategori tidak pernah Bahasa Indonesia atau berhuruf kapital. Sebut slug yang dipakai.
3. Cek apakah slug sudah ada
4. Jika belum ada, tambahkan ke `kategori_custom` array
5. Simpan kembali

Response (sukses):
```
✅ Kategori berhasil ditambahkan!

🏷️ Kategori baru: investment
📋 Total kategori: <jumlah isi kategori_custom>

Sekarang kamu bisa mencatat: "nabung saham 500rb" → otomatis masuk investment
```

Response (sudah ada):
```
⚠️ Kategori "investment" sudah ada!
```

## Hapus Kategori
Trigger: `hapus kategori [nama]`, `delete kategori [nama]`
Contoh: `hapus kategori investment`

Langkah:
1. Baca `data/budget.json`
2. Hapus slug-nya dari `kategori_custom` array (nama dari pengguna diubah ke slug seperti di atas)
3. Simpan kembali
4. Konfirmasi — ingatkan bahwa transaksi lama tetap tersimpan dengan kategori lama

Response:
```
🗑️ Kategori "investment" berhasil dihapus.

ℹ️ Transaksi yang sudah dicatat dengan kategori ini tidak berubah.
```

## Lihat Semua Kategori
Trigger: `daftar kategori`, `kategori apa saja`, `list kategori`

Response:
```
📋 Daftar Kategori (<jumlah isi kategori_custom>)

  <semua slug dari kategori_custom, dipisah " · ", apa adanya>

💡 Tambah: tambah kategori [nama]
💡 Hapus: hapus kategori [nama]
```
