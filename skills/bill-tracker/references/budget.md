# Budget: set budget dan alert

Sisa budget dan cek otomatis setelah catat dijawab skrip — lihat *Peta pesan* di `AGENTS.md`.

Budget = batas belanja **rutin** yang kami tetapkan sendiri, bukan uang yang dimiliki dan tidak mengikuti
pemasukan. Transaksi sebesar `pengeluaran_besar_mulai` atau lebih (Pengeluaran Besar) tidak dihitung ke
Budget dan tampil terpisah sebagai "Di luar budget" (ADR-0024). Jangan menyebut "sisa uang" untuk Budget.

Angka budget dan ambang alert selalu dibaca dari `data/budget.json`, jangan dari ingatan atau
contoh di bawah (cuma ilustrasi format).

## Set Budget Bulanan
Trigger: `set budget [nominal]`, `atur budget [nominal]`
Contoh: `set budget 3 juta`, `set budget 2500000`, `atur budget 1.5jt`

Langkah:
1. Baca `data/budget.json`
2. Update field `budget_bulanan` dengan nominal yang diparse
3. Simpan kembali ke `data/budget.json`
4. Konfirmasi ke pengguna

Response:
```
💰 Budget bulanan berhasil diset!

📊 Budget: Rp 3.000.000/bulan
🔔 Alert akan dikirim saat pengeluaran mencapai 80%
```

## Set Alert Threshold
Trigger: `set alert [persen]%`, `alert budget [persen]`
Contoh: `set alert 75%`, `alert budget 90`

Update field `alert_persen` di `data/budget.json`.
