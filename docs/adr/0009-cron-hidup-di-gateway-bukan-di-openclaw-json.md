# Cron hidup di state gateway, bukan di `openclaw.json`; dan `delivered: true` bukan bukti sampai

Dua commit sebelumnya (3ee80c7, dea1886) memperbaiki pesan tiga cron di `openclaw.json` —
`reminder_jatuh_tempo` dihapus, `cek_budget_malam` diganti `--mode all`, `laporan_mingguan`
diperbarui. Keduanya diterima sebagai perbaikan tuntas. Ternyata tidak: gateway yang sedang
berjalan tidak pernah membaca ulang file itu untuk cron yang sudah terdaftar. `openclaw.json`
cuma dipakai sekali, saat pendaftaran pertama; setelah itu cron hidup sebagai state tersendiri
di gateway, diubah lewat `openclaw cron edit`/`rm`, bukan lewat edit file.

Ini baru ketahuan saat merestart gateway (atas permintaan pengguna, tanpa kaitan dengan
pekerjaan cron) dan menjalankan `openclaw cron list`: `reminder_jatuh_tempo` **masih hidup**,
jalan tiap 09:00, memanggil `--mode jatuh_tempo --days 7` — mode yang sudah dihapus sejak
[0003](0003-buku-kas-bukan-perencana-tagihan.md). Cron itu gagal tiap pagi, dan kegagalan itulah
yang menghasilkan pesan heartbeat yang memicu seluruh percakapan hari ini — bot mengarang jawaban
dari kegagalan mode yang tak ada, bukan dari analisis data yang jujur.

Diperbaiki langsung di gateway: `reminder_jatuh_tempo` dihapus, `cek_budget_malam` dan
`laporan_mingguan` di-`cron edit --message` dengan isi yang sama seperti yang sudah ditulis di
`openclaw.json`. File repo sekarang cuma dokumentasi nilai yang seharusnya berlaku untuk cron
baru — bukan kontrol atas cron yang sudah ada.

## Insiden kedua: restart yang sama menyembunyikan kegagalan kirim

Cron `cek_budget_malam` yang baru diperbaiki jalan pukul 20:00 WIB — 7 menit setelah restart
gateway. Riwayatnya (`openclaw cron runs`) mencatat `deliveredStatus: "delivered"`,
`delivered: true`, tapi `summary: "NO_REPLY"` — beda dari malam-malam sebelumnya yang selalu
punya ringkasan isi pesan. Pengguna mengonfirmasi: **tidak ada pesan yang masuk ke WhatsApp
malam itu**, padahal gateway yakin sudah terkirim.

Dua faktor bertumpuk: koneksi WhatsApp (mirip sesi WhatsApp Web) kemungkinan belum tersambung
penuh 7 menit setelah restart, dan `openclaw doctor` melaporkan plugin WhatsApp ketinggalan versi
(`2026.5.18` vs gateway `2026.7.1-2`). Diperbaiki dengan `openclaw plugins update whatsapp`,
restart ulang, jeda 15 detik, verifikasi `channels status` menunjukkan `connected` — baru setelah
itu kirim pesan tes eksplisit ke nomor sendiri via `openclaw message send`, dan pengguna
mengonfirmasi pesan itu sampai.

## Considered Options

**Mempercayai `deliveredStatus: delivered` di riwayat cron ditolak** sebagai bukti tunggal.
Status itu mencatat bahwa panggilan API terkirim ke lapisan pengiriman, bukan bahwa pesannya
sungguh sampai ke telepon. Setelah restart gateway atau update plugin channel, satu-satunya cara
memastikan adalah mengirim pesan tes eksplisit dan menunggu konfirmasi manusia — bukan membaca
status di dashboard/CLI begitu saja.

**Terus mengedit `openclaw.json` untuk mengubah perilaku cron yang sudah berjalan ditolak.**
Itulah yang dilakukan dua commit sebelumnya dan gagal diam-diam. Perubahan pada cron yang sudah
terdaftar harus lewat `openclaw cron edit <id> --message ...` atau `openclaw cron rm <id>`
langsung ke gateway yang hidup. Mengedit file tetap berguna — sebagai dokumentasi nilai yang
seharusnya berlaku, dan sebagai sumber saat cron didaftarkan ulang dari nol — tapi bukan
mekanisme kontrol.

## Consequences

Setiap kali `openclaw.json` diedit untuk mengubah pesan atau jadwal cron yang **sudah ada**,
langkah itu harus diikuti `openclaw cron list` + `openclaw cron get <id>` untuk memverifikasi
gateway benar-benar memakai isi yang baru, dan `openclaw cron edit` untuk menerapkannya kalau
belum. Melewatkan langkah ini adalah persis yang terjadi di commit 3ee80c7/dea1886: perubahan
yang terlihat benar di git, tidak berlaku sama sekali di produksi, selama berhari-hari tanpa
ada yang tahu.

Setiap restart gateway atau update plugin channel harus diikuti verifikasi kirim nyata — pesan
tes eksplisit ke nomor sendiri, dikonfirmasi manusia — sebelum mempercayai cron berikutnya akan
terkirim. Peringatan drift versi plugin di `openclaw doctor` tetap menunjukkan versi lama
sesaat setelah update+restart meski `package.json` di disk sudah benar; penyebabnya belum
ditelusuri tuntas (kemungkinan cache metadata terpisah dari kode yang dimuat) dan dibiarkan
terbuka karena tes pengiriman nyata sudah membuktikan perilakunya benar terlepas dari angka
yang tertampil.

Pelajaran yang lebih umum, senada dengan [0008](0008-saldo-awal-20-5-juta-dan-koreksi-rekonsiliasi.md):
**status "berhasil" dari sistem bukan bukti — cuma klaim.** Baik saldo yang tak pernah minus
maupun pesan yang tercatat terkirim, keduanya perlu dicocokkan ke kenyataan (mutasi bank, HP
yang benar-benar berbunyi) sebelum dipercaya.
