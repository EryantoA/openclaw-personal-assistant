# Balasan pencatatan selalu menyebut Arah uang, dihitung skrip

Pratinjau dan balasan `✅ Sudah dicatat!` kini memuat baris `Arah:` di bawah baris nomor/tanggal/jam:
`📤 Pengeluaran`, `📥 Pemasukan`, atau `🔁 Transfer (<akun> → <akun_tujuan>)`. Baris nama berlabel
`Pembeli` hanya untuk Pengeluaran, dan `Pencatat` untuk Pemasukan dan Transfer. Keduanya dicetak
`catat.py` (field `arah` dan `nama_label` pada baris `OK lolos cek` / `OK tersimpan`), lalu disalin
model.

## Kenapa

Pada 22 Okt 2026 sebuah Bonus Rp 170.000 dibalas dengan kerangka yang persis sama dengan belanja,
lengkap dengan `Pembeli: Eryanto`. Pemilik tidak bisa membedakan uang masuk dari uang keluar.
ADR-0015 memang mewajibkan satu kerangka untuk semua tipe. Template lama `✅ Pemasukan dicatat!` di
skill yang masih bertentangan dengan kerangka itu dihapus.

## Pilihan yang ditolak

- **Pembuka beda per arah** (`✅ Pemasukan dicatat!`): paling mencolok, tetapi memecah pembuka baku
  yang dijaga ADR-0015 dan tes kontrak. Aturan "hanya bilang dicatat setelah `OK tersimpan`" juga
  bergantung pada pembuka itu.
- **Tanda +/− di Total**: mudah terlewat, dan transfer tidak punya tanda yang jujur.
- **Label `Penerima`** untuk pemasukan: nilainya `pencatat` (pengirim pesan), yang belum tentu orang
  yang menerima uangnya.

## Batas

Melengkapi [0015](0015-balasan-struk-memuat-tanggal-dan-pembeli.md): `Pembeli` tidak lagi selalu
tampil. Skema `bills.csv` tidak berubah. Tes hanya membuktikan teks kontrak dan keluaran skrip,
bukan kepatuhan model.
