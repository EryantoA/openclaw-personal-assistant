# Riset: menggabungkan OpenClaw dan Hermes agar WhatsApp, Telegram, dan Discord "berkesinambungan data"

Tanggal riset: 31 Okt 2026. Dikerjakan read-only: tidak ada config diubah, proses direstart, atau pesan dikirim.
Rahasia (token, API key, nomor telepon, ID chat) sengaja tidak dicantumkan; hanya nama kunci.

Penanda: **[V]** terverifikasi dari kode/config/dokumen terpasang di mesin ini, **[D]** dugaan/inferensi, **[T]** tidak ditemukan.

## Kesimpulan

**Sebagian bisa, dan tidak perlu "menggabungkan" kedua agen.** Kata "berkesinambungan" ternyata mencakup tiga hal yang dukungannya berbeda:
(1) satu percakapan lintas kanal dan satu identitas pengguna: OpenClaw sudah punya mekanismenya (`session.identityLinks`, sesi utama lintas kanal) dan sudah memegang WhatsApp + Telegram, jadi ini cukup perubahan config di OpenClaw, bukan integrasi dua agen [V];
(2) memori/fakta bersama: Hermes hanya punya memori per-profil (`MEMORY.md`/`USER.md`, bukan per-kanal) dan pencarian sesi lintas kanal; tidak ada jembatan memori resmi ke OpenClaw selain penyedia memori eksternal bersama (Honcho) atau berkas bersama [V];
(3) satu kotak masuk untuk semua kanal: tidak ada jalur sinkronisasi hidup antar keduanya, hanya migrasi sekali jalan, MCP, A2A, dan kirim-pesan lewat CLI [V].
Rekomendasi: **jangan memindahkan atau menyatukan WhatsApp dan keuangan ke Hermes**; pertahankan pembagian domain yang sudah ada (OpenClaw = keuangan + WA, Hermes = Discord/riset/catatan), aktifkan kesinambungan identitas di OpenClaw, dan sambungkan keduanya hanya lewat antarmuka sempit dan satu arah. Keputusan pengguna yang menentukan: apa yang dimaksud "berkesinambungan data" (lihat bagian *Belum terjawab*).

## 1. Apa persisnya keduanya di mesin ini

| | OpenClaw | Hermes |
|---|---|---|
| Versi | 2026.10.9 (8b18b55) [V: `openclaw --version`] | Hermes Agent v0.22.2 (2026.9.24), ada pembaruan tersedia [V: `hermes --version`] |
| Pasang | `/opt/homebrew/lib/node_modules/openclaw` (Node, global npm); state `~/.openclaw` [V] | `~/.hermes/hermes-agent` (git, Python 3.14); state `~/.hermes`; binari `~/.local/bin/hermes` [V] |
| Proses | launchd `ai.openclaw.gateway`, gateway lokal `bind: loopback`, port 18789, auth token [V: `launchctl list`, `openclaw.json` kunci `gateway`] | launchd `ai.hermes.gateway` (`hermes gateway run --external-supervisor`), satu proses melayani tiga profil (`multiplex_profiles: true`; `served_profiles` = default, istri, peneliti) [V: `~/Library/LaunchAgents/ai.hermes.gateway.plist`, `~/.hermes/gateway_state.json`, `config.yaml`] |
| Kanal aktif | **WhatsApp** (linked device, `health:healthy`) dan **Telegram** (polling, terhubung) [V: `openclaw channels status`]. Discord: "not installed, not configured" [V: `openclaw channels list --all`] | **Telegram** dan **Discord** terhubung [V: `gateway_state.json`]. WhatsApp mati: `WHATSAPP_ENABLED=false` di `~/.hermes/.env` [V] |
| Telegram | Satu bot (token A) | Satu bot (token B). **Token berbeda**: ID bot pada token OpenClaw dan Hermes tidak sama [V: dibandingkan tanpa menampilkan nilai]. Artinya di Telegram pengguna sebenarnya berhadapan dengan **dua bot terpisah** |
| Model/auth | `anthropic/claude-haiku-4-5` (fallback `claude-opus-4-7`) lewat runtime `claude-cli`, yaitu langganan Claude (OAuth), bukan API key [V: `openclaw.json` `agents.defaults`; memori `openclaw-pa-auth-and-config`] | `provider: nous`, `model.default: upstage/solar-mini4:free` (model gratis) [V: `~/.hermes/config.yaml`]. `.env` juga memuat kunci `ANTHROPIC_API_KEY` dan `ANTHROPIC_TOKEN` (status aktif tidak diperiksa) [V nama kunci] |
| Agen/profil | `main` (bill-tracker; WA pribadi + satu grup finansial + semua Telegram) dan `helpdesk` (bot FH UIR; menyedot sisa WA) [V: `bindings`] | `default`, `istri` (profil pribadi istri; dirutekan lewat `gateway.profile_routes` untuk satu guild+pengguna Discord dan satu chat Telegram), `peneliti` [V] |
| Eksekusi alat | Agen `main` jalan di folder repo ini dengan `bypassPermissions` (memori `openclaw-pa-auth-and-config`); `helpdesk` di sandbox Docker [V] | Terminal backend Docker; hanya `/Users/apple/hermes-workspace`, `hermes-rumah`, dan `~/.hermes/alat` (read-only) yang dipasang. Repo ini dan `data/bills.csv` **tidak** dipasang [V: `terminal.docker_volumes`] |
| Cron | Cron gateway (laporan keuangan, penjaga kesehatan, backup) [V: memori + ADR-0009/0012/0013] | `cron/jobs.json`: 9 job `no_agent` berskrip (ringkasan pagi, laporan repo malam, digest riset, backup workspace) yang mengirim ke Discord (`#dev`, `#riset-*`) dan Telegram [V] |

Hubungan historis: pada 18 Okt 2026 sudah dijalankan `hermes claw migrate` sekali (8 item termigrasi, 4 diarsipkan, 2 konflik: `SOUL.md` dan model tidak ditimpa; `MEMORY.md` OpenClaw tidak ditemukan) [V: `~/.hermes/migration/openclaw/20261018T192019/summary.md`]. Skill `bill-tracker` tercantum di `skills.disabled` Hermes [V]; `SOUL.md` Hermes melarang menulis/mengubah/menghapus data keuangan dan menyimpan data keuangan ke memori [V: `~/.hermes/SOUL.md`].

Peringatan: `MIGRATION_NOTES.md` dari migrasi itu menyarankan `hermes claw cleanup`, yang **mengganti nama `~/.openclaw` menjadi `.pre-migration`**. Itu akan mematikan gateway OpenClaw yang sedang dipakai; jangan dijalankan selama OpenClaw aktif [V: isi berkas + `hermes claw --help`].

## 2. Model memori dan sesi

### OpenClaw
- Sesi disimpan di state SQLite gateway; transkrip bot `claude-cli` ada di `~/.claude/projects/...` (memori `bot-skill-loading-and-transcripts`) [V].
- **Bawaan OpenClaw: satu percakapan bergulir lintas semua kanal.** Semua DM dari Telegram/WhatsApp/dst jatuh ke "main session" `agent:<id>:main` [V: `docs/concepts/main-session.md`, `docs/concepts/session.md` bagian DM isolation].
- **Config pengguna menimpanya:** `session.dmScope = "per-channel-peer"` dan `resetByType.direct = idle 360 menit` [V: `openclaw config get session`]. Jadi saat ini WA dan Telegram **sengaja** terpisah per kanal+pengirim.
- Identitas lintas kanal: `session.identityLinks` memetakan identitas kanonik ke ID per kanal (`{ alice: ["telegram:123", "discord:987"] }`) agar DM-nya jatuh ke satu sesi [V: `docs/gateway/config-agents/sessions.md`, `docs/concepts/session.md:83-95`, skema `openclaw config schema` -> `session.identityLinks`]. Belum di-set di mesin ini [V: tidak ada di `session`]. Ada juga tautan identitas pengirim-kanal ke profil Gateway (`docs/concepts/user-model.md:212`) [V, tidak ditelusuri lebih jauh].
- Grup terpisah per grup (`groupScope: per-group` bawaan) [V: `session.md`].
- Memori jangka panjang: `MEMORY.md`, `USER.md`, `memory/*.md` di workspace (folder repo ini punya `memory/2026-*.md`, `USER.md`, `SOUL.md`, `IDENTITY.md`) [V]. **Indeks pencarian memori saat ini rusak**: `openclaw memory status` -> 0/11 berkas terindeks, pencarian vektor "paused", metadata indeks hilang, provider embedding `openai` diminta [V]. Jadi memori OpenClaw praktis hanya terbaca bila dimuat langsung ke prompt, bukan dicari.
- Plugin memori eksternal: Honcho (`@honcho-ai/openclaw-honcho`) menawarkan memori lintas sesi dan lintas kanal serta model pengguna [V: `docs/concepts/memory-honcho.md`]. Belum terpasang [V: `plugins.entries` hanya whatsapp, anthropic, google, groq].

### Hermes
- Sesi di `~/.hermes/state.db` (SQLite + FTS5), satu basis data **per profil** [V: `docs/user-guide/sessions.md`, struktur `profiles/*/state.db`].
- Kunci sesi gateway per kanal: `agent:main:telegram:dm:<chat_id>`, `agent:main:discord:dm:<chat_id>`, `...:group:<chat_id>:<user_id>`, WhatsApp `...:whatsapp:dm:<canonical_identifier>` [V: `sessions.md:~936`, kunci nyata di `~/.hermes/sessions/sessions.json`]. **Tidak ada konsep identitas pengguna lintas platform di inti**: pencarian `identity_links`/setara di `gateway/`, `agent/`, `hermes_cli/` dan dokumen pengguna tidak menemukan apa pun [T]. Percakapan Telegram dan Discord pengguna yang sama adalah dua sesi terpisah.
- Memori bawaan: `~/.hermes/memories/MEMORY.md` (2.200 karakter) dan `USER.md` (1.375 karakter), disuntik beku ke prompt tiap awal sesi, **dibagi semua platform dalam satu profil** (tidak per-kanal), dibatasi per profil [V: `docs/user-guide/features/memory.md`; `config.yaml` `memory.*`].
- `session_search` mencari lintas semua sesi tanpa saringan platform (hanya sumber `kanban`/`subagent`/`tool` disembunyikan) [V: `tools/session_search_tool.py:21-23,371`]. Inilah "kesinambungan" Hermes lintas kanal: bukan satu sesi, tetapi ingatan yang bisa dicari ulang.
- `/handoff <platform>` memindahkan sesi CLI hidup ke kanal pesan [V: `sessions.md:225`]; tidak memindahkan antar kanal pesan.
- Penyedia memori eksternal: saat ini "none — built-in only"; terpasang plugin `byterover` dan `retaindb`; Honcho tersedia dan punya pemetaan identitas gateway (`userPeerAliases`, `pinUserPeer`) yang mengumpulkan ID Telegram/Discord ke satu "peer" [V: `hermes memory status`; `docs/user-guide/features/memory-providers.md` "Gateway identity mapping"].
- Sesi gateway tidak kedaluwarsa otomatis; reset hanya `/new` [V: `sessions.md` "Session continuity"].

Ringkasnya: **tidak satu pun dari dua sistem menyimpan memori "per kanal"** untuk fakta jangka panjang, tetapi **sesi percakapan** memang per-kanal di Hermes, dan di OpenClaw per-kanal hanya karena pilihan config.

## 3. Jalur integrasi resmi

| Jalur | Arah | Status | Catatan |
|---|---|---|---|
| `hermes claw migrate` / `openclaw migrate hermes` | sekali jalan, dua arah | [V] ada kedua sisi (`docs/guides/migrate-from-openclaw.md`, `docs/install/migrating-hermes.md`) | Bukan sinkronisasi. Sisi OpenClaw: `sessions/`, `state.db`, `cron/`, `kanban/`, `platforms/` hanya diarsipkan, tidak dimuat; `MEMORY.md`/`USER.md` ditambahkan ke milik OpenClaw. OpenClaw menolak impor jika sudah ada state lokal kecuali `--overwrite` |
| `openclaw mcp serve` | OpenClaw -> klien MCP mana pun | [V] (`docs/cli/mcp/serve.md`) | Server stdio: `conversations_list`, `conversation_get`, `messages_read`, `events_poll/wait`, `messages_send`, persetujuan; menampilkan **semua percakapan berrute** dari semua kanal. Antrean live hanya selama klien terhubung |
| `hermes mcp serve` | Hermes -> klien MCP | [V] (`mcp_serve.py:1-8`) | Menyediakan permukaan setara (daftar percakapan, baca riwayat, kirim pesan, poll event, persetujuan) |
| Hermes sebagai klien MCP | Hermes memakai server lain | [V] (`hermes mcp add`; `mcp_servers.*.tools.include/exclude`) | Saat ini "No MCP servers configured" |
| OpenClaw sebagai klien MCP | `openclaw mcp add/set`, `tools` untuk saringan | [V] | |
| A2A (Agent2Agent 1.0) | dua arah | [V] kedua sisi (`docs/channels/a2a.md` OpenClaw, contoh peer bernama `hermes`; `docs/user-guide/messaging/a2a.md` Hermes) | Satu agen memanggil agen lain sebagai tugas teks dengan token bearer per peer. Belum diaktifkan di mesin ini |
| `hermes send --to platform:chat` / `openclaw message send` | dorong pesan keluar | [V] | Cara termurah agar cron satu sistem mengirim ke kanal yang dipegang sistem lain, tanpa berbagi sesi |
| ACP (`openclaw acp`, `hermes acp`) | editor/host <-> agen | [V] | Untuk IDE; bukan jembatan kanal. Tidak relevan |
| Plugin memori bersama (Honcho) | keduanya -> satu layanan | [V] tersedia untuk keduanya | Butuh layanan Honcho (API terkelola atau self-host) |
| Berbagi folder workspace/vault | berkas | [D] | Hermes sudah memasang `~/hermes-workspace` (berisi `vault`) di kontainernya; OpenClaw bisa membacanya bila folder itu ditambahkan ke aksesnya. Tidak diuji |
| Impor langsung state OpenClaw oleh Hermes secara live | n/a | [T] | Tidak ada fitur sinkron hidup di dokumen kedua proyek |

Dokumen OpenClaw sendiri membandingkan keduanya dan tidak menyebut jembatan bersama (`docs/start/why-openclaw/openclaw-and-hermes-agent.md`) [V]; perbandingan itu ditulis pihak OpenClaw, jadi bacalah sebagai sudut pandang satu pihak.

## 4. Batasan teknis per kanal

- **Telegram, satu token = satu pemolling.** OpenClaw: "only one active poller can use a bot token at a time"; konflik `getUpdates` 409 berarti ada proses lain memakai token yang sama [V: `docs/channels/telegram/messaging.md:23`]. Hermes menjaga ini dengan kunci per-token lintas profil/home (`acquire_scoped_lock`, "one Telegram token across homes") [V: `gateway/status.py:1565-1568`]. Dokumen Bot API Telegram juga menyatakan `getUpdates` tak berfungsi bila webhook aktif [V: core.telegram.org/bots/api]; larangan dua pemolling tidak dinyatakan di halaman itu, jadi bagian "satu pemolling" bersumber dari dokumentasi kedua proyek, bukan Telegram. Saat ini aman karena token berbeda.
- **Discord, satu token.** Hermes memegang kunci token Discord (komentar `gateway/status.py:577-578` menyebut "Discord bot-token lock") [V]. Aturan dari sisi Discord (apakah dua koneksi gateway dengan satu token diizinkan) tidak diverifikasi dari sumber Discord [T]; secara praktik dua proses akan sama-sama membalas. Jika OpenClaw diberi Discord, pakai **bot/token baru**, jangan token Hermes.
- **WhatsApp (Baileys, linked device).** Kedua proyek memakai Baileys; sesi tertaut disimpan sebagai kredensial lokal per proses. OpenClaw: "The gateway owns the linked session(s)" (`docs/channels/whatsapp.md`); Hermes: `hermes whatsapp` memindai QR sendiri, dan satu sesi dipegang satu proses bridge, dengan penolakan `whatsapp_bridge_foreign_session` bila bridge profil lain memakai port/sesi yang sama (`docs/user-guide/messaging/whatsapp.md`) [V]. **Menyalin kredensial** dari satu proses ke yang lain tidak boleh dilakukan [D, karena protokol Web memutus sesi yang bentrok; tidak ada sumber primer WhatsApp yang berhasil diambil: halaman FAQ resmi tidak termuat]. Memasang Hermes sebagai linked device **kedua** pada nomor bot yang sama memungkinkan kedua agen menerima semua pesan, yang berarti balasan ganda kecuali dirutekan [D].
- WhatsApp rapuh di sini: sesi OpenClaw logout tiap 2-3 minggu dan kirim dari cron gagal acak (memori `openclaw-pa-auth-and-config`) [V]. Hermes mengakui risiko larangan akun untuk bridge tak resmi dan menawarkan WhatsApp Business Cloud API sebagai jalur resmi (`whatsapp-cloud.md`) [V]. Hermes juga menyarankan nomor khusus bot.
- Satu gateway OpenClaw per direktori state (`docs/gateway/gateway-lock.md`); Hermes: "One agent per Hermes home" (jangan dua proses menulis `~/.hermes` yang sama; `memory.md` blok caution) [V].
- Hermes tidak menyediakan balasan lintas profil: grup yang tidak ter-rute jatuh ke profil `default` [D, dari `profile_routes`].

## 5. Opsi arsitektur

### (a) Satu gateway memegang ketiga kanal; yang lain jadi backend
- **OpenClaw sebagai gateway tunggal.** WhatsApp dan Telegram sudah ada; Discord adalah plugin bawaan (`docs/channels/discord.md`) tetapi belum terpasang. Dengan `identityLinks` + `dmScope` yang tepat, DM pengguna dari ketiganya menjadi satu sesi [V]. Hermes tinggal jadi pemanggil (A2A/MCP) atau dimatikan. Untung: satu tempat, kesinambungan nyata, bill-tracker tetap utuh, WhatsApp tidak perlu dipasangkan ulang. Rugi: Hermes kehilangan peran Discord (kanban, cron `#dev`, profil istri, `peneliti`) kecuali tetap dijalankan untuk itu; memigrasi seluruhnya ke OpenClaw berarti membangun ulang ketiganya. Model: OpenClaw memakai langganan Claude yang sudah ada.
- **Hermes sebagai gateway tunggal.** Hermes sudah memegang Telegram + Discord dan punya multi-profil dan kanban; WhatsApp harus dipasangkan ulang (mode bot atau Cloud API) [V]. Untung: kesinambungan Discord/Telegram/profil istri tetap. Rugi: bill-tracker harus dipindah (skill dinonaktifkan, Docker tanpa repo, model gratis, tidak ada ADR/skrip yang dirancang untuk Hermes); bot helpdesk FH UIR (sudah dipakai mahasiswa) ikut pindah; Hermes tidak punya identity-link inti sehingga "satu percakapan lintas kanal" tidak tercapai, hanya ingatan bersama. Risiko terbesar.

### (b) Tiap agen pegang kanal berbeda, satu store memori bersama
- Dua proses tidak boleh berbagi `~/.hermes` (didokumentasikan) [V], jadi store bersama harus eksternal: Honcho (kedua sisi punya plugin) atau berkas Markdown di folder bersama [V/D].
- Untung: fakta dan preferensi mengalir ke kedua arah. Rugi: Honcho mengirim isi percakapan ke layanan (terkelola atau perlu di-host sendiri), bertentangan dengan aturan `SOUL.md` Hermes (tak ada data keuangan di memori) dan ADR-0004 (data keluarga tak keluar mesin). Hanya layak bila dikecualikan dari percakapan keuangan, dan itu sulit dipaksakan karena penyaringan terjadi pada model, bukan pada jalur data [D]. Indeks memori OpenClaw sedang rusak (bagian 2), jadi memori OpenClaw perlu diperbaiki dulu.

### (c) Terpisah, tersinkron lewat MCP/A2A/berkas
- Hermes mendaftarkan `openclaw mcp serve` sebagai server MCP, atau sebaliknya, atau keduanya saling A2A. Pengguna tetap punya dua bot Telegram, tetapi satu agen bisa menanyakan hal ke yang lain atau mengirim lewat kanal yang lain.
- Untung: tak ada pemindahan kanal; reversibel; punya saringan alat (`tools.include/exclude`). Rugi: tidak ada percakapan tunggal; `openclaw mcp serve` menampilkan **semua** percakapan OpenClaw, termasuk grup finansial, kecuali disaring; Hermes dijalankan oleh model yang lebih lemah dan memiliki `terminal`/`code_execution`.
- Varian paling aman: **dorongan satu arah** tanpa memberi akses baca: skrip Hermes memanggil `openclaw message send`, atau skrip OpenClaw memanggil `hermes send`, hanya dengan teks yang sudah dihitung skrip (cocok dengan pola ADR-0012/0013 dan 0011).

### (d) Hal lain
- **Dua kanal, satu bot Telegram:** karena kini ada dua bot Telegram, cukup pilih satu bot sebagai "rumah" pengguna (rekomendasi: OpenClaw, untuk keuangan) dan jadikan bot lain khusus notifikasi/istri, atau hentikan salah satu.
- **Migrasi sekali jalan** `openclaw migrate hermes` / `hermes claw migrate --overwrite`: berguna hanya untuk menyalin `SOUL.md`/`MEMORY.md`/`USER.md`, bukan kesinambungan [V].
- **Profil/agen OpenClaw baru** (mis. `main` untuk keuangan, agen kedua untuk non-keuangan) bila ingin satu gateway tetapi menjaga konteks keuangan terpisah: `agents.entries` + `bindings` per peer [V: `docs/concepts/multi-agent.md` ada; tidak dibaca rinci].

## Rekomendasi

1. **Tentukan makna dulu** (lihat bagian berikutnya).
2. Jika yang dimau adalah "satu percakapan dengan asisten, di WhatsApp maupun Telegram": ubah di OpenClaw saja. Tambah `session.identityLinks` untuk satu identitas pemilik (nomor WA + ID Telegram), pakai `dmScope: per-peer` (bukan `main`: `main` menggabungkan DM **semua** pengirim yang diizinkan; ada dua nomor di `allowFrom`), dan putuskan batas reset (kini 360 menit idle). Coba dengan `openclaw agent --session-key ...` dulu, bukan lewat WhatsApp. Ini perubahan config; ia memerlukan keputusan dan tidak dilakukan dalam riset ini.
3. **Pertahankan Discord di Hermes.** Menambah Discord ke OpenClaw berarti bot baru dan memindahkan kanban/cron/profil; keuntungannya kecil bagi data keuangan.
4. **Hubungkan kedua agen hanya dengan dorongan satu arah dan skrip** (varian (c)), bukan dengan membuka `openclaw mcp serve` ke Hermes. Bila MCP/A2A tetap diinginkan, wajib `tools.include` yang membatasi ke satu-dua alat dan jangan `messages_read` dari grup finansial.
5. **Jangan** memindahkan WhatsApp ke Hermes, memasang Honcho untuk percakapan campuran, atau menjalankan `hermes claw cleanup`.
6. Perbaiki lebih dulu indeks memori OpenClaw bila memori bersama dianggap penting (`openclaw memory status`: vektor "paused", 0/11 berkas terindeks).

## Risiko

- **Kebocoran data keuangan (ADR-0004/0005).** Setiap jalur yang meneruskan teks percakapan ke agen lain memindahkan isi `bills.csv` ke konteks model lain: MCP `messages_read`, A2A, Honcho, atau `session_search` Hermes bila percakapan finansial masuk ke `state.db`-nya. Hermes dibatasi aturan `SOUL.md`, tetapi itu instruksi ke model, bukan penghalang teknis [V]. Pemisah teknis yang ada: repo/`bills.csv` tidak dipasang di Docker Hermes [V], dan skill `bill-tracker` dinonaktifkan di Hermes [V]. Alat `file` Hermes mungkin tidak lewat Docker; tidak diperiksa apakah ia bisa membaca di luar mount [D/belum terjawab].
- **Bocor ke grup/orang salah.** Dengan `dmScope: main`, DM semua pengirim di `allowFrom` bercampur [V: peringatan di `session.md`]. Pemetaan `identityLinks` yang salah (mis. mengaitkan nomor istri ke identitas pemilik) menyatukan percakapan privat. Profil `istri` Hermes sengaja terpisah (memori, sesi, SOUL sendiri) [V]; jangan diselaraskan dengan profil pemilik. Dokumentasi Hermes: pengguna yang diizinkan dalam satu adapter dipercaya setara dan bisa memakai alat konfigurasinya [V: ringkasan di `why-openclaw/openclaw-and-hermes-agent.md`, sumber Hermes `SECURITY.md`].
- **Balasan ganda.** Dua pemolling Telegram dengan token sama menghasilkan 409; satu nomor WA tertaut ke dua bridge menghasilkan pesan masuk ke keduanya [D]. Dua bot Telegram yang berbeda sudah menimbulkan kebingungan "bot mana yang dijawab".
- **Dua agen merebut sesi/state.** Dua proses pada `~/.hermes` yang sama (didokumentasikan sebagai terlarang), dua gateway pada `~/.openclaw` yang sama (`gateway-lock.md`), atau `hermes claw cleanup` yang mengganti nama state OpenClaw yang hidup [V].
- **Operasional.** Gateway OpenClaw berjalan dengan `bypassPermissions` dan alat penuh; menambah pemanggil luar (MCP/A2A) memperluas siapa yang bisa memicu aksi itu. Kegagalan WA yang berulang (logout 2-3 mingguan) tidak berubah dengan integrasi apa pun.

## Belum terjawab / perlu keputusan pengguna

1. **Makna "berkesinambungan data":** (i) satu percakapan lintas kanal, (ii) fakta/preferensi bersama, (iii) data keuangan terjangkau dari semua kanal, atau (iv) satu bot per kanal saja? Jawabannya memilih opsi di atas.
2. **Boleh tidak data keuangan terlihat dari Discord/Telegram-bot-Hermes?** ADR-0005 menjadikan bill-tracker satu-satunya sistem; belum ada keputusan tentang akses lintas agen.
3. **Istri:** apakah profil `istri` Hermes dan akses WhatsApp/Telegram OpenClaw-nya harus ikut tersinambung? Tidak diperiksa siapa dua nomor di `allowFrom`/`groupAllowFrom` OpenClaw, atau siapa pemilik dua chat Telegram pada cron Hermes (dugaan: pemilik dan istri).
4. **Bot Telegram mana yang dipertahankan sebagai rumah**, dan apakah bot lain dipensiunkan.
5. **Model:** Hermes memakai model gratis `solar-mini4:free`; OpenClaw memakai Claude. Apakah kualitas jawaban harus disamakan? Status kunci `ANTHROPIC_API_KEY` Hermes tidak diperiksa (memori mencatat API key lama mati).
6. **Honcho:** diizinkan atau tidak, dan di-host sendiri atau terkelola. Tidak ditelusuri harganya/versinya.
7. **Tidak diuji (hanya dibaca):** apakah `identityLinks` + `per-peer` bekerja bersama `resetByType`/`claude-cli` seperti yang didokumentasikan; apakah `profile_routes` Hermes bisa merutekan per grup WhatsApp; perilaku dua linked device pada satu nomor WA; aturan Discord untuk dua koneksi per token; kebijakan WhatsApp tentang bridge tak resmi.
8. Pembaruan: Hermes melaporkan ada versi lebih baru, dan OpenClaw berganti skema config cepat (memori mencatat skema lama vs baru). Fitur di atas bersumber dari versi terpasang (OpenClaw 2026.10.9, Hermes 0.22.2); periksa ulang setelah update.

## Sumber

Lokal (dibaca 31 Okt 2026):
- `~/.openclaw/openclaw.json` (kunci: `channels`, `bindings`, `session`, `agents`, `plugins`, `gateway`; nilai rahasia tidak dibaca ke laporan); keluaran `openclaw --version`, `channels status`, `channels list --all`, `agents list`, `memory status`, `config schema`, `config get ...`, `mcp --help`, `memory --help`
- `/opt/homebrew/lib/node_modules/openclaw/docs/`: `concepts/session.md`, `concepts/main-session.md`, `concepts/multi-user.md`, `concepts/user-model.md`, `concepts/memory-honcho.md`, `gateway/config-agents/sessions.md`, `gateway/gateway-lock.md`, `channels/telegram/messaging.md`, `channels/whatsapp.md`, `channels/discord.md`, `channels/a2a.md`, `cli/mcp.md`, `cli/mcp/serve.md`, `cli/migrate.md`, `install/migrating-hermes.md`, `start/why-openclaw/openclaw-and-hermes-agent.md`, `security/formal-verification.md`
- `~/.hermes/config.yaml` (kunci: `model`, `terminal`, `gateway.profile_routes`, `memory`, `platform_toolsets`, `skills.disabled`), `~/.hermes/gateway_state.json`, `~/.hermes/.env` (hanya nama kunci dan `WHATSAPP_ENABLED`), `~/.hermes/SOUL.md`, `~/.hermes/cron/jobs.json`, `~/.hermes/sessions/sessions.json` (bentuk kunci), `~/.hermes/state.db` (hitungan per sumber), `~/Library/LaunchAgents/ai.hermes.gateway.plist`, `~/.hermes/migration/openclaw/20261018T192019/{summary.md,MIGRATION_NOTES.md}`; keluaran `hermes --version`, `memory status`, `mcp list`, `mcp --help`, `claw --help`, `gateway status`
- `~/.hermes/hermes-agent/` (install git): `mcp_serve.py:1-8`, `tools/session_search_tool.py:21-32,371`, `gateway/status.py:1565-1568` dan `:577-578`; `website/docs/user-guide/`: `sessions.md`, `features/memory.md`, `features/memory-providers.md`, `features/honcho.md`, `features/acp.md`, `messaging/whatsapp.md`, `messaging/whatsapp-cloud.md`, `messaging/a2a.md`, `multi-profile-gateways.md`; `website/docs/guides/migrate-from-openclaw.md`
- Repo ini: `CONTEXT.md`, `AGENTS.md`, `docs/adr/0004`, `0005`, `0022`, `docs/specs/`; memori `openclaw-pa-auth-and-config.md`, `bot-skill-loading-and-transcripts.md`

Eksternal:
- Telegram Bot API, `getUpdates`/"Getting updates": https://core.telegram.org/bots/api (hanya bagian webhook yang terbaca; halaman 580 ribu karakter, sisanya tidak dibaca)
- Halaman bantuan resmi WhatsApp tentang perangkat tertaut (https://faq.whatsapp.com/378279804439436) tidak termuat isinya; klaim terkait ditandai dugaan.
