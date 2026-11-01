# SKILL.md hanya memuat yang dipakai tiap pencatatan; fitur jarang pindah ke references/

`skills/bill-tracker/SKILL.md` tumbuh jadi 897 baris, dibaca penuh oleh model kecil
(`groq/llama-3.3-70b-versatile`) tiap skill dipakai, di samping `AGENTS.md` yang selalu ada di
prompt. Isinya bertabrakan sendiri dan dengan `AGENTS.md` (kategori berkapital, "konfirmasi jika
ragu" padahal Pratinjau wajib, templat konfirmasi transfer dengan saldo karangan). Penataan ulang
Okt 2026 memangkasnya dua tahap: buang salinan dan aturan bentrok (897 → 652), lalu memecah fitur
jarang pakai ke `skills/bill-tracker/references/` (652 → ±360).

## Aturan pembagian

- **`AGENTS.md`** (selalu di prompt): alur Pratinjau → simpan, kerangka balasan, tabel perintah
  laporan. Satu-satunya tempat kerangka balasan didefinisikan.
- **`SKILL.md`** (dibaca tiap skill dipakai): apa pun yang berlaku di tengah pencatatan biasa —
  kategori, `catat.py`, No Resi, duplikat, arti kolom, konfirmasi, pencarian, aturan penting.
- **`references/*.md`** (dibaca hanya saat diminta): fitur yang jarang dan berdiri sendiri —
  budget, Kewajiban & Perkiraan, Akun & Transfer, kategori custom, backup, rekap per bulan.
  `SKILL.md` memuat tabel "pengguna menyebut → baca berkas ini" dengan `{baseDir}`.

## Yang tidak boleh dipindah ke references

Aturan yang bisa kena di tengah pencatatan biasa, karena bot tidak akan punya alasan membuka
berkasnya. Contohnya menautkan pembayaran tagihan ke `kewajiban.json` (`lunas_resi`), transfer
bukan belanja, dan jangan tebak akun. Tiga hal itu tetap di inti sebagai Aturan Penting, dengan
rujukan ke berkasnya untuk rinciannya. `tests/test_kontrak_prompt.py` (kelas `SkillInti`)
menjaganya dan menolak inti yang kembali di atas 420 baris.

## Risiko yang diterima

Model kecil bisa tidak membuka berkas rujukan dan menjawab dari tebakan. Diterima karena fitur di
references jarang dipakai dan hasilnya tidak mengubah Buku Kas lewat jalur tulis yang tak
berpratinjau (semua penulisan tetap lewat `catat.py` / `buku.py`). Kalau terbukti sering terjadi
di pemakaian nyata, kembalikan bagian itu ke inti — bukan menambah instruksi "wajib baca".

## Yang sempat tertinggal

`references/laporan-per-bulan.md` semula menyuruh model menghitung rekap dari `bills.csv`, bertolak
belakang dengan "JANGAN hitung sendiri". Sudah diganti `scripts/rekap-bulanan.py` (baris di Peta
pesan, ADR-0022) dan berkasnya dihapus.
