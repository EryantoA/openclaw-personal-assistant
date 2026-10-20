# Spec: Label "Struk" hanya untuk No Resi yang benar-benar dari struk

Status: siap dikerjakan. Turunan dari [ADR-0015](../adr/0015-balasan-struk-memuat-tanggal-dan-pembeli.md)
dan spec [0002](0002-crud-data-csv.md).

## Problem Statement

Tiga kerangka balasan bot — Pratinjau (`🧾 Akan disimpan`), konfirmasi akhir (`✅ Sudah dicatat!`),
dan Hasil pencarian (`🔍 Hasil pencarian`) — selalu menulis baris pertamanya `Struk: <no_resi> | ...`,
apa pun asal No Resi itu. Tapi hanya sebagian No Resi benar-benar berasal dari foto struk
(awalan `STRUK-`, baik nomor tercetak maupun sidik jari struk tanpa nomor): chat biasa dapat
`TRX-YYYYMMDD-XXXX` dari `catat.py`, baris impor massal dapat `IMP-<id>`, dan baris lama berresi
bebas (`SS-20SEP-SOCK`, dst., dibiarkan apa adanya per aturan skill) juga bukan struk.

Contoh nyata yang sudah tertulis sebagai contoh resmi di `AGENTS.md` sendiri: pencatatan hadiah
uang tunai lewat chat (bukan struk sama sekali) dibalas `Struk: TRX-20261015-0032 | ...`. Label
ini menyesatkan — pengguna bisa mengira ada struk yang terbaca padahal transaksinya hanya chat,
dan istilah "Struk" di sini juga bertentangan dengan definisi **No Resi** sendiri di `CONTEXT.md`
(_Avoid_: nomor struk) yang sudah menyediakan nama generik untuk field ini.

## Solution

`Struk:` hanya dipakai sebagai label baris pertama bila No Resi transaksi benar-benar berasal
dari bukti (awalan `STRUK-` — struk difoto dengan atau tanpa nomor tercetak, maupun Bukti
Transfer). Untuk semua No Resi lain (`TRX-`, `IMP-`, `SALDO-AWAL`, dan resi bebas peninggalan)
label baris pertama berganti jadi `No Resi:` — istilah yang sudah ada di glosarium `CONTEXT.md`,
tanpa field baru di `bills.csv` dan tanpa istilah baru.

Label ini **dihitung oleh skrip, bukan dibaca sendiri oleh model dari awalan No Resi**, mengikuti
pola ADR-0015 (nilai yang tampil di balasan berasal dari keluaran skrip, bukan dihitung/dikarang
model). `scripts/resi.py` mendapat satu fungsi label, dipakai `catat.py` (baris `OK tersimpan`/
`OK lolos cek`) dan `scripts/buku.py` (`_format_cari_bills`, satu-satunya tempat kata "Struk"
sudah di-hardcode di kode, bukan di teks prompt) supaya ketiga kerangka balasan konsisten
otomatis tanpa logika kondisi di `AGENTS.md`/`SKILL.md`.

## User Stories

1. Sebagai anggota keluarga, saya ingin balasan Pratinjau transaksi chat biasa (tanpa struk)
   berlabel `No Resi:`, bukan `Struk:`, supaya saya tidak mengira bot membaca struk yang tidak
   ada.
2. Sebagai anggota keluarga, saya ingin balasan `✅ Sudah dicatat!` untuk transaksi chat biasa
   juga berlabel `No Resi:`, konsisten dengan Pratinjaunya.
3. Sebagai anggota keluarga, saya ingin balasan untuk foto struk (dengan atau tanpa nomor
   tercetak) tetap berlabel `Struk:` seperti sekarang, supaya tidak ada regresi pada kasus yang
   sudah benar.
4. Sebagai anggota keluarga, saya ingin balasan untuk Bukti Transfer tetap berlabel `Struk:`
   (No Resi-nya tetap `STRUK-<referensi>`), supaya baris `Referensi:`/`Arah:` yang sudah ada
   tidak berubah maknanya.
5. Sebagai anggota keluarga, saya ingin hasil `cari ...` menampilkan `No Resi:` untuk setiap
   Transaksi yang bukan struk (termasuk baris impor dan baris `SALDO-AWAL`), dan `Struk:` untuk
   yang memang struk, dalam satu hasil pencarian yang sama bila keduanya tercampur.
6. Sebagai anggota keluarga, saya ingin label ini konsisten di tiga tempat (Pratinjau, konfirmasi
   akhir, hasil pencarian) tanpa saya perlu mengecek sendiri mana yang benar.
7. Sebagai pemilik, saya ingin label dihitung oleh skrip dari No Resi yang sudah ada, bukan
   ditebak model dari pesan, supaya tidak ada risiko model salah menilai sumbernya seperti yang
   coba dihindari ADR-0015.
8. Sebagai pemilik, saya ingin aturan ini tidak menambah kolom baru di `bills.csv` atau field
   baru di masukan `catat.py`, supaya skema data tidak berubah untuk perubahan tampilan semata.
9. Sebagai pemilik, saya ingin baris lama berresi bebas (`SS-20SEP-SOCK`, `MOMOYO-14SEP`,
   `TRX-20260908-CATFOOD`, dibiarkan apa adanya per aturan skill) ikut dapat label `No Resi:`
   saat dicari, bukan dianggap kasus khusus baru.
10. Sebagai pemilik, saya ingin kontrak teks baru ini tertulis di `AGENTS.md`/`SKILL.md` dengan
    kedua contoh (struk dan bukan struk) persis seperti sekarang ditulis untuk kasus struk,
    supaya tidak menyimpang antar-sesi (ADR-0014).
11. Sebagai pengembang, saya ingin fungsi penentu label bisa diuji langsung dengan memanggilnya
    atas berbagai nilai No Resi, tanpa perlu menjalankan seluruh `catat.py`/`buku.py`.

## Implementation Decisions

**Aturan label.** Satu fungsi baru di `scripts/resi.py`, menerima satu nilai No Resi dan
mengembalikan `"Struk"` bila nilainya berawalan `STRUK-`, selain itu `"No Resi"`. Tidak ada
aturan tambahan berbasis `channel`/Asal atau kolom lain — awalan No Resi yang sudah ada di
`resi.py` (`STRUK-`, `TRX-`, `IMP-`, `SALDO-AWAL`, bebas) sudah cukup sebagai sinyal, sesuai
konvensi yang didokumentasikan di docstring `resi.py` saat ini.

**`catat.py`.** Baris keluaran `OK tersimpan ...` dan `OK lolos cek (tidak ditulis): ...`
mendapat satu segmen baru berisi label itu (mis. `label Struk` / `label No Resi`), ditambahkan
di tempat yang sama dengan segmen `no_resi` yang sudah ada. Isi dan urutan segmen lain tidak
berubah.

**`buku.py` — `_format_cari_bills`.** Kata `"Struk"` yang sekarang ditulis langsung di kode
diganti memanggil fungsi label baru berdasarkan `no_resi` baris itu, per kelompok Transaksi di
hasil pencarian. `_format_cari_umum` (dipakai skema `riwayat`/Jejak Perubahan) tidak disentuh —
Jejak Perubahan tidak memakai kerangka `Struk:`.

**`AGENTS.md` dan `skills/bill-tracker/SKILL.md`.** Kerangka Pratinjau dan `✅ Sudah dicatat!`
memakai `<label dari keluaran>: <no_resi dari keluaran>` sebagai pengganti teks tetap `Struk:`,
dengan instruksi memakai label persis dari keluaran skrip (sama dengan aturan nilai lain:
"jangan mengarang"). Ditambahkan **dua** contoh lengkap berdampingan — satu untuk struk/Bukti
Transfer (label `Struk:`, seperti contoh yang sudah ada sekarang) dan satu untuk chat biasa
(label `No Resi:`) — menggantikan contoh chat biasa yang sekarang salah berlabel `Struk:`.
Kerangka Hasil pencarian di `AGENTS.md` (hanya didefinisikan di sana, bukan di skill — pola yang
sudah ada) mendapat penjelasan yang sama: label ikut baris tiap Transaksi, bisa berbeda antar
baris dalam satu hasil pencarian.

**Bukti Transfer tidak berubah perilakunya.** Karena No Resi-nya tetap `STRUK-<referensi>`
(AGENTS.md, aturan yang sudah ada), label yang dihasilkan tetap `Struk:` — ini bukan pengecualian
baru, hanya konsekuensi dari aturan awalan yang sama.

## Testing Decisions

**Tes yang baik di sini** memeriksa string label pada keluaran yang terlihat dari luar: baris
`OK tersimpan`/`OK lolos cek` dari `catat.py`, dan teks hasil pencarian dari `buku.py cari` —
sama persis dengan pola pengujian yang sudah dipakai kedua skrip ini sekarang. Tidak menguji
pemetaan awalan secara terpisah dari perilaku ini kecuali lewat fungsi label itu sendiri
(unit test langsung, karena fungsinya murni dan tanpa I/O).

**`tests/test_catat.py`.** Perbarui dua assertion yang sudah mengunci teks penuh baris `OK
tersimpan`/`OK lolos cek` (`test_keluaran_ok_membawa_resi_waktu_tanggal_dan_pencatat`,
`test_keluaran_uji_membawa_field_yang_sama_untuk_pratinjau`) agar menyertakan segmen label baru:
No Resi `STRUK-000123` → `label Struk`; No Resi `TRX-...` (default chat) → `label No Resi`.
Tambahkan kasus baru untuk No Resi `IMP-...` dan resi bebas (mis. `MOMOYO-14SEP`) → `label No
Resi`, memakai pola pemanggilan `ct.catat(...)` yang sama dengan tes lain di berkas ini.

**`tests/test_buku.py`.** Perbarui assertion yang mengunci `Struk:` untuk baris yang bukan
struk: `test_terbaru_dulu_dan_terakhir_dicatat` (baris `SALDO-AWAL`, baris 119–125) harus
berharap `No Resi: SALDO-AWAL`, bukan `Struk: SALDO-AWAL`, dan hitungan `"Struk:"` di tes itu
disesuaikan (ganti sebagian ke hitungan `"No Resi:"` atau hitung gabungan). Tambahkan kasus baru:
hasil pencarian yang mencampur satu Transaksi berawalan `STRUK-` dan satu berawalan `TRX-` harus
menampilkan `Struk:` untuk yang pertama dan `No Resi:` untuk yang kedua dalam satu balasan yang
sama (user story 5).

**Fungsi label di `resi.py`.** Tes unit langsung: `STRUK-000123` → `"Struk"`, `STRUK-a1b2c3d4` →
`"Struk"`, `TRX-20260921-0001` → `"No Resi"`, `IMP-262` → `"No Resi"`, `SALDO-AWAL` → `"No
Resi"`, resi bebas (`MOMOYO-14SEP`) → `"No Resi"`, nilai kosong/`None` → `"No Resi"` (tidak error).

**Tes kontrak dokumen.** Perluas `tests/test_kontrak_prompt.py`: assertion
`test_kerangka_akhir_sama_di_skill_dan_agents` yang sekarang mengunci
`KERANGKA_AKHIR + "\n\nStruk: "` persis di `AGENTS.md`/`SKILL.md` harus diperlonggar — contoh
struk tetap wajib ada persis seperti itu (tidak boleh hilang), **ditambah** assertion baru yang
membuktikan contoh chat biasa di kedua berkas memakai `No Resi:` bukan `Struk:`, dan bahwa kata
"jangan mengarang" (atau kalimat senada) tetap melekat pada instruksi label ini. Tes ini — sama
seperti tes kontrak lain di berkas ini — hanya membuktikan teksnya ada, bukan kepatuhan model.

**Prior art.** `tests/test_catat.py` (pola pemanggilan `ct.catat()` langsung, path data
diarahkan ke direktori sementara), `tests/test_buku.py` kelas `Cari` (pemanggilan `bk.cari()`
langsung dan pencocokan string pada hasilnya), `tests/test_kontrak_prompt.py` (pencocokan teks
kontrak di `AGENTS.md`/`SKILL.md`).

## Out of Scope

- Mengubah No Resi, awalan, atau cara `resi.py` membuatnya (`--gen`, `--fingerprint`, dll.) —
  spec ini hanya mengubah **label tampilan**, bukan nilai `no_resi`.
- Menambah label ketiga/keempat per sumber (mis. "Catatan" untuk chat, "Impor" untuk baris
  massal) — hanya dua label: `Struk` (awalan `STRUK-`) dan `No Resi` (selain itu). Lihat
  Further Notes bila ini perlu dipertimbangkan ulang nanti.
- Mengubah kerangka Ubah/Hapus Transaksi (`✏️ Akan diubah`, `🗑️ Akan dihapus`) — keduanya tidak
  pernah memakai kata "Struk" (memakai "Transaksi \<nomor\>"/"no_resi \<nomor\>" apa adanya),
  jadi tidak terdampak.
- Mengubah kerangka Hasil pencarian untuk skema `riwayat` (Jejak Perubahan) — tidak memakai
  kerangka `Struk:` sama sekali.
- Menata ulang baris lama berresi bebas atau migrasi data apa pun di `bills.csv`.
- Mengubah definisi **No Resi** atau istilah lain di `CONTEXT.md` — istilah itu sudah benar dan
  sudah dipakai sebagai nama label baru di sini.

## Further Notes

- Pertimbangan "label beda per sumber" (Catatan/Impor/dst.) ditolak untuk spec ini karena
  menambah istilah baru yang berpotensi tabrakan dengan kolom `catatan` yang sudah ada dan
  menggandakan kerangka balasan yang harus dijaga `test_kontrak_prompt.py`. Dua label (Struk vs
  No Resi) adalah titik tengah yang paling kecil ubahannya dan paling konsisten dengan glosarium
  yang sudah ada.
- Risiko utama bukan di skrip (fungsi labelnya murni dan mudah diuji), melainkan di teks
  `AGENTS.md`/`SKILL.md`: bila contoh kedua kasus (struk vs bukan struk) tidak ditulis
  berdampingan dengan jelas, model berisiko tetap memakai `Struk:` dari kebiasaan sesi
  sebelumnya. Mengikuti pola ADR-0014/0015, pagar sebenarnya adalah kata "label dari keluaran,
  jangan mengarang" plus contoh eksplisit, bukan penegakan di kode (kode hanya menyediakan nilai
  labelnya, tidak memaksa model memakainya).
