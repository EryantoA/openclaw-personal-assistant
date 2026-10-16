# Alias Pembeli dibakukan oleh skrip lewat data/pembeli.json

Satu orang sering ditulis dengan banyak nama di `pencatat` (huruf besar-kecil, nama panggilan,
peran seperti "suami"/"istri"). `catat.py` membakukan nama itu ke satu nama baku saat menulis, dan
`laporan-pembeli.py` membakukan juga baris lama saat menghitung, jadi laporan per Pembeli tidak
memecah satu orang menjadi beberapa.

## Keputusan

- Pemetaan ada di `data/pembeli.json` (`{"Nama baku": ["alias", ...]}`), pencocokan tidak peka
  huruf besar-kecil. Nama tak dikenal dibiarkan apa adanya; tanpa berkas, tidak ada perubahan.
- Berkas **tidak masuk git** (nama anggota keluarga = data pribadi, ADR-0004); yang dilacak hanya
  `data/pembeli.json.example` dengan nama karangan.
- Pembakuan di skrip, bukan di prompt: model tidak boleh menebak siapa itu "Teikoku".
- Baris lama di `bills.csv` tidak ditulis ulang; laporan membakukan saat membaca.
