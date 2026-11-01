# Sesi grup WhatsApp direset setelah 2 jam tak aktif

Bot berjalan di grup "Finance Bot" dengan model Claude Haiku 4.5 lewat claude-cli. Sesi grup
tidak punya aturan reset, jadi satu sesi menyambung berhari-hari. Pada 31 Okt 2026 bot di sesi
panjang itu dua kali mengabaikan `AGENTS.md`: menjawab "sisa budget" dari ingatan tanpa
menjalankan skrip, merangkum dengan kalimat sendiri, dan membungkus judul dengan `**…**`. Setelah
`/new`, pesan yang sama langsung dijalankan lewat skrip dan disalin utuh. Model kecil lebih
menurut pada contoh balasannya sendiri di percakapan daripada pada instruksi tertulis, dan
menambah kalimat ke prompt tidak membantu (serta memakan jatah 20.000 karakter per berkas;
`AGENTS.md` sudah ±18.300).

## Keputusan

`session.resetByType.group = { mode: "idle", idleMinutes: 120 }`: sesi grup baru dimulai pada
pesan pertama setelah jeda lebih dari 2 jam. Aturan `direct` (idle 6 jam) tidak berubah. Dipasang
di gateway dengan `openclaw config patch` (tanpa restart) dan dicontohkan di
`openclaw.json.example`. Alasannya ada di sini, bukan di berkasnya: skema OpenClaw menolak kunci
`_keterangan` di blok `session`.

## Akibat

- Pratinjau yang menunggu jawaban *ya* lebih dari 2 jam hilang; bot mulai dari awal.
- Dalam satu percakapan yang rapat (jeda < 2 jam) sesi tetap menumpuk, jadi `/new` masih berguna
  bila bot mulai menyimpang.
- Bila 120 menit terasa terlalu singkat atau terlalu lama, ubah `idleMinutes`; jangan menambah
  instruksi "jalankan ulang" ke prompt sebagai gantinya.
