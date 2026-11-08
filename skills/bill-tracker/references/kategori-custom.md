# Kategori custom: tambah, hapus, daftar

Daftar sah ada di `data/budget.json` → `kategori_custom`; kategori selalu slug Inggris huruf kecil.
Tiap slug punya **Label Kategori** Bahasa Indonesia di `label_kategori` (slug → label) — hanya nama
tampil di Google Sheets, data tetap slug (ADR-0026). Label wajib unik.

## Tambah Kategori
Trigger: `tambah kategori [nama]`, `buat kategori [nama]`, `kategori baru [nama]`
Contoh: `tambah kategori investment`, `buat kategori home_repair`

Langkah:
1. Baca `data/budget.json`
2. Ubah nama dari pengguna ke slug Inggris huruf kecil `snake_case` (`Investasi` → `investment`);
   kategori tidak pernah Bahasa Indonesia atau berhuruf kapital. Sebut slug yang dipakai.
3. Cek apakah slug sudah ada
4. Usulkan Label Kategori Bahasa Indonesia (kata pengguna bila ia menulis Bahasa Indonesia,
   mis. `Investasi`). Label tidak boleh sama (abaikan huruf besar-kecil) dengan label lain di
   `label_kategori` — kalau sama, usulkan yang lain dan sebut bentroknya.
5. Kirim Pratinjau dan tunggu jawaban (ADR-0016); pengguna boleh mengganti labelnya di sini:
   ```
   🏷️ Kategori baru
   Slug: investment
   Label di Sheets: Investasi

   Simpan? (ya / ganti label: <label>)
   ```
6. Setelah "ya": tambahkan slug ke `kategori_custom` dan `"<slug>": "<label>"` ke `label_kategori`,
   lalu simpan kembali. Label yang diganti pengguna dicek unik lagi sebelum disimpan.

Response (sukses):
```
✅ Kategori berhasil ditambahkan!

🏷️ Kategori baru: investment (Investasi)
📋 Total kategori: <jumlah isi kategori_custom>

Sekarang kamu bisa mencatat: "nabung saham 500rb" → otomatis masuk investment
```

Response (sudah ada):
```
⚠️ Kategori "investment" sudah ada!
```

Response (label kembar):
```
⚠️ Label "Investasi" sudah dipakai kategori savings. Pakai label lain?
```

## Hapus Kategori
Trigger: `hapus kategori [nama]`, `delete kategori [nama]`
Contoh: `hapus kategori investment`

Langkah:
1. Baca `data/budget.json`
2. Hapus slug-nya dari `kategori_custom` array (nama dari pengguna diubah ke slug seperti di atas).
   Entri `label_kategori`-nya dibiarkan, supaya transaksi lama tetap tampil berlabel di Sheets.
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
