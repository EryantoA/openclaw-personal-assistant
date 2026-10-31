# Kewajiban dan Perkiraan

Tagihan pascabayar yang belum dibayar (`data/kewajiban.json`) dan transaksi berulang yang diharapkan (`data/perkiraan.json`). Definisi lengkap di `CONTEXT.md`.

## Kewajiban

**Kewajiban** = tagihan pascabayar yang **sudah datang tapi belum dibayar** — WiFi bulanan, PLN
pascabayar, cicilan. Disimpan di `data/kewajiban.json`.

> ⚠️ Pembelian **prabayar** bukan Kewajiban. Pulsa, paket data, gas Elpiji, top-up e-wallet —
> uangnya keluar di detik yang sama, jadi itu langsung Transaksi biasa di `bills.csv`.
> Kalau ragu: adakah jeda antara "tagihannya datang" dan "uangnya keluar"? Kalau tidak ada,
> bukan Kewajiban.

## Membuat Kewajiban
Trigger: pengguna menyebut tagihan yang datang & belum dibayar — `tagihan wifi 233rb jatuh tempo
tanggal 20`, `tagihan listrik datang 340.000 bayar sebelum 25`.

Langkah:
1. Baca `data/kewajiban.json`
2. Tambahkan entri: `id` (`KWJ-<urut>`), `nama`, `kategori` (slug dari `budget.json`), `nominal`,
   `jatuh_tempo` (`YYYY-MM-DD`), `dibuat` (hari ini), `lunas_resi: null`
3. Tulis ulang seluruh file (baca dulu, jangan append)

```
🧾 Tagihan dicatat (belum dibayar)

📄 WiFi — Rp 233.000
📅 Jatuh tempo: 20 Agu 2026
🔔 Saya ingatkan tgl 18 dan 20.
```

## Menautkan saat dibayar — WAJIB
Kalau pengguna mencatat pembayaran atas tagihan yang ada di `kewajiban.json`
(mis. `bayar wifi 233rb`):

1. Catat baris `bills.csv` **seperti biasa** lewat `scripts/catat.py`
2. **Lalu** buka `data/kewajiban.json`, isi `lunas_resi` entri itu dengan `no_resi` baris tadi

> ⚠️ **Tautkan, jangan menandai.** Tidak ada field status di file itu — jangan pernah menambah
> `"status": "lunas"` atau sejenisnya. Lunas dihitung ulang dari `lunas_resi`, dan tautan yang
> menunjuk baris tidak ada akan diperlakukan **belum** lunas.

Kalau lupa menautkan, pengingatnya berhenti sendiri 5 hari setelah jatuh tempo — tagihannya jadi
tidak diketahui, bukan lunas.

## Cek Tagihan
Trigger: `cek tagihan`, `tagihan apa saja`, `ada tagihan?`

```bash
python3 scripts/check-bills.py --mode all
```

## Perkiraan

**Perkiraan** = transaksi yang biasanya berulang tiap bulan — gaji akhir bulan, langganan yang
ditarik tanggal 26. Disimpan di `data/perkiraan.json`. **Bukan** Transaksi: belum ada uang
berpindah, jadi **tidak pernah** ikut menghitung Saldo, Arus Kas Bulan, maupun budget.

Gunanya dua: bersiap untuk uang yang akan keluar, dan menyadari kalau yang seharusnya masuk
ternyata tidak masuk.

> ⚠️ **Jangan sunting `data/perkiraan.json` tanpa diminta eksplisit.** File ini dirawat manusia
> dan jarang berubah. Kamu boleh membacanya kapan saja untuk menjawab pertanyaan; menambah atau
> mengubah entri hanya kalau pengguna memintanya dengan jelas (mis. `catat langganan Netflix
> 186rb tiap tanggal 5`).

Kalau menambah entri: `id` (`PRK-<urut>`), `nama`, `arah` (`masuk`/`keluar`), `kategori`,
`nominal`, `tanggal_biasanya` (1-31), `aktif: true`, `dasar` (bukti di data yang mendasarinya).

> 💡 Kalau kategori & nominalnya berdekatan dengan Perkiraan lain (mis. dua gaji di `salary`
> yang cuma beda 1%), tambahkan `toleransi_persen` yang lebih ketat pada keduanya — kalau tidak,
> yang satu akan menutupi absennya yang lain.
