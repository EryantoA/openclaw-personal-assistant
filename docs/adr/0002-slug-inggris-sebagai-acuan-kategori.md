# Slug Inggris sebagai acuan tunggal kategori

`skills/bill-tracker/SKILL.md` mendokumentasikan 9 kategori Bahasa Indonesia (`Makanan`,
`Minuman`, `Tagihan`, …), sementara 226 baris di `data/bills.csv` sudah memakai 22 slug
Inggris huruf kecil (`food`, `groceries`, `utilities`, …). Kami menetapkan **slug Inggris
sebagai satu-satunya acuan** dan menulis ulang dokumentasinya agar cocok dengan data, bukan
sebaliknya.

Daftar lengkapnya hidup di `data/budget.json` → `kategori_custom`. Tabel di `SKILL.md` hanya
menjelaskan arti tiap slug.

## Considered Options

Alternatifnya adalah mengonversi data turun ke 9 kategori Bahasa Indonesia yang terlanjur
didokumentasikan. Ditolak karena tidak bisa dibalik: `groceries`, `food`, `beauty`, dan
`personal_care` semuanya akan melebur, dan detail yang sudah terkumpul dari 4 bulan riwayat
hilang permanen. Menyesuaikan dokumentasi tidak menghilangkan apa pun.

## Consequences

Kategori adalah nilai data, bukan teks yang dibaca pengguna — jadi ia tetap Inggris walaupun
seluruh percakapan bot memakai Bahasa Indonesia. `budget.json` harus dibaca di awal tiap sesi;
menambah kategori berarti menambah slug ke sana, bukan mengarang nilai baru saat mencatat.
Kalau ada baris berkategori Bahasa Indonesia muncul di kemudian hari, itu tanda ada yang
menulis tanpa membaca `budget.json`, dan laporan per kategori akan terpecah dua.
