# Budget: set budget dan alert

Sisa budget dan cek otomatis setelah catat dijawab skrip — lihat *Peta pesan* di `AGENTS.md`.

Budget = batas belanja **rutin** yang kami tetapkan sendiri, bukan uang yang dimiliki dan tidak mengikuti
pemasukan. Transaksi sebesar `pengeluaran_besar_mulai` atau lebih (Pengeluaran Besar) tidak dihitung ke
Budget dan tampil terpisah sebagai "Di luar budget" (ADR-0024). Jangan menyebut "sisa uang" untuk Budget.

Angka budget dan ambang alert selalu dibaca dari `data/budget.json`, jangan dari ingatan atau
contoh di bawah (cuma ilustrasi format).

**Semua perubahan lewat `scripts/atur-budget.py`** (ADR-0029). Jangan mengedit `data/budget.json`
dengan Edit/Write. Salin keluarannya: `OK …` = tersimpan; `ERROR …` = tidak ada yang berubah,
sampaikan apa adanya (untuk kategori yang tidak dikenal, keluarannya memuat daftar pilihan).

## Set Budget Bulanan
Trigger: `set budget [nominal]`, `atur budget [nominal]`
Contoh: `set budget 3 juta`, `set budget 2500000`, `atur budget 1.5jt`

```bash
python3 scripts/atur-budget.py total "3 juta"
```

## Set Alert Threshold
Trigger: `set alert [persen]%`, `alert budget [persen]`
Contoh: `set alert 75%`, `alert budget 90`

```bash
python3 scripts/atur-budget.py alert 75
```
Ambang ini berlaku untuk Budget total dan untuk setiap Batas Kategori.

## Batas Kategori
Batas belanja rutin untuk kategori pilihan, di bawah Budget total (ADR-0029). Kategori tanpa batas
tetap dihitung ke Budget. Pengeluaran Besar dan Selisih Rekonsiliasi tidak ikut.

Trigger: `budget makan 2,1jt`, `set budget kategori belanja dapur 1.2jt`, `batas hiburan 250rb`,
`hapus budget kategori hiburan`

```bash
python3 scripts/atur-budget.py kategori "Makan & Minum" 2,1jt     # label atau slug
python3 scripts/atur-budget.py kategori entertainment --hapus
```
Nama kategori dari pengguna boleh label (`Makan & Minum`) atau slug (`food`). Bila tidak jelas
kategori mana ("budget jajan"), tanyakan dengan menyebut pilihan yang ada; jangan menebak.

Status semua Batas Kategori ada di "sisa budget" (`check-bills.py --mode status`).
