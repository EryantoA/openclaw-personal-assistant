# Spec: Batas Kategori

Status: dikerjakan; keputusannya di [ADR-0029](../adr/0029-batas-kategori-untuk-kategori-pilihan.md).

## Problem Statement

Budget total menjawab "belanja rutin bulan ini masih wajar?", tapi tidak "kategori mana yang harus
direm". Keluarga ingin batas untuk beberapa kategori yang rutin dan bisa dikendalikan.

## Solution

`budget_kategori` di `data/budget.json` (slug → nominal), dihitung `budget.pemakaian` dari belanja
rutin per Kategori, ditampilkan di peringatan setelah mencatat (kategori Transaksi itu saja), cek
malam, "sisa budget", Laporan Bulanan, dan tab Budget `<tahun>` di Cermin. Diubah lewat
`scripts/atur-budget.py`, yang juga menggantikan suntingan tangan bot untuk `budget_bulanan` dan
`alert_persen`.

## User Stories

1. Sebagai pemilik, saya ingin memberi batas pada Makan & Minum, Belanja Dapur, Belanja Lain, dan
   Hiburan, supaya saya tahu kategori mana yang harus direm.
2. Sebagai pemilik, saya ingin peringatan setelah mencatat hanya menyebut kategori transaksi itu bila
   sudah ≥ 80% atau lewat, supaya pesan tidak membanjir.
3. Sebagai pemilik, saya ingin "sisa budget" menampilkan semua Batas Kategori.
4. Sebagai pemilik, saya ingin cek malam menyebut Batas Kategori yang ≥ 80%.
5. Sebagai pemilik, saya ingin Laporan Bulanan memuat satu baris per Batas Kategori.
6. Sebagai anggota keluarga, saya ingin tab Budget di Sheets menunjukkan persen tiap Batas Kategori
   per bulan.
7. Sebagai pemilik, saya ingin Pengeluaran Besar dan Selisih Rekonsiliasi tidak menghabiskan Batas
   Kategori.
8. Sebagai pemilik, saya ingin mengubah, menambah, atau menghapus Batas Kategori lewat chat dengan
   label atau slug, dan kategori yang tidak dikenal ditolak dengan daftar pilihan.
9. Sebagai pemilik, saya ingin `set budget` dan `set alert` ditulis skrip, bukan diedit bot dengan
   tangan, supaya `budget.json` tidak pernah rusak.

## Implementation Decisions

- `budget.pemakaian(...)["kategori"]`: daftar `{slug, label, rutin, batas, persen}` berurutan sesuai
  `budget_kategori`; `rutin` = Pengeluaran rutin Kategori itu (sudah tanpa Pengeluaran Besar dan
  Selisih Rekonsiliasi).
- `budget.pesan(..., kategori=None)`: `selalu` → semua; tidak `selalu` dan `kategori` diberikan →
  hanya kategori itu bila ≥ `alert_persen`; tidak `selalu` tanpa `kategori` (cron) → semua yang ≥
  `alert_persen`. Pesan total dan pesan kategori berdiri sendiri: total di bawah ambang tidak
  membungkam kategori yang lewat.
- Tab Budget `<tahun>`: kolom kosong lalu satu kolom per Batas Kategori di kanan tabel total,
  header `<label> · Rp <batas>`, isinya persen (format persen per kolom).
- `check-bills.py --mode budget --kategori <slug|label>` (boleh diulang, satu per kategori item).
- `atur-budget.py total <nominal>`, `alert <persen>`, `kategori <label|slug> <nominal>`,
  `kategori <label|slug> --hapus`; tulis atomik di bawah kunci berkas, pertahankan urutan kunci.

## Testing Decisions

Tes lewat `budget.pemakaian`/`pesan`/`baris_laporan`, `check-bills.main`, `atur-budget.main`,
`sheets_laporan.grid_budget`, dengan berkas sementara.

## Out of Scope

Mempertajam kategorisasi "Lain-lain"; peringatan sekali-saja per ambang.
