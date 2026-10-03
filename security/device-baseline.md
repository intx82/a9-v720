# cam170 — Device fingerprint baseline

Captured 2026-10-03 (CET), device in normal service on the LAN.

| Field | Value | Evidence |
|---|---|---|
| LAN address | 10.0.0.170 (DHCP, br0) | `ip neigh` |
| MAC | 22:c0:e0:12:ab:78 (locally-administered/ randomised OUI) | `ip neigh show 10.0.0.170` |
| UID / devicesCode | 080c0e054577 | relay log, MQTT, HTTP |
| Model class | Naxclow-branded A9/V720 "cat camera", batch `A9_X4_V12` | registerDevices batch param (upstream docs + relay) |
| Sensor | `gc0312` (GalaxyCore 0.3 MP) | MQTT Device/Info `camType` |
| Wi-Fi SSID | `Miau` | MQTT Device/Info `wifiName` |
| **Firmware version (live)** | **202503081631** (previously seen: 202411201737, same scheme = build timestamp) | MQTT `Naxclow/P2P/Users/Device/Info` at boot — `evidence/mqtt-info-boot.json` |
| Hardware SoC | Beken BK7252 (per upstream repo; datasheet in git history) | upstream a9-v720 readme/datasheet |
| LAN listeners | none — zero TCP/UDP ports open (full scan, prior session) | connect-only device |

## Outbound endpoints (all normally DNS-sinkholed to 10.0.0.2 = DyOne)

| Endpoint | Protocol | Real destination (public DNS) | Purpose |
|---|---|---|---|
| `v720.naxclow.com:80` | HTTP cleartext | `47.243.132.88` (one of 8 RR IPs: 47.243.x/8.21x.x/43.242.130.61) | bootstrap `registerDevices`, `confirm`, `getDevInfo`, `getA9ConfCheck`, `a9SendAlertV3` (~every 30 s), `a9bindingAppDevice` |
| `v720.p2p.naxclow.com:1883` | MQTT 3.1.1 cleartext | same RR set | control pipe + will/status/info |
| `dl2.naxclow.com` / `.com.cn` | HTTP | `43.241.19.58` | firmware download host (OTA) |
| `home.naxclow.com`, `logo.naxclow.com.cn` | HTTP | — | app-side, not observed from cam170 |
| TCP `:6123` (our relay) / `:29942` (real cloud) | proprietary framing | relay `10.0.0.1` / cloud `107.149.136.10` | P2P rendezvous + MJPEG/G.711 data channel |

## Boot handshake (observed, `evidence/pcaps/cam170-boot-mqtt-http.pcap`)

1. HTTP `POST /app/api/ApiSysDevices/getDevInfo?devicesCode=…&random=<6char>&token=<10hex>` → cloud returns `ota_url`/`ota_version` (null = no update) + owner `userInfo_userId`.
2. HTTP `POST /app/api/ApiServer/getA9ConfCheck?devicesCode=…&random=…&token=…` → `tcpPort`, P2P `host`, session `pwd`, `updateUrl`, `version` (both null for this device).
3. MQTT CONNECT: client-id/username = UID, **password = 10-hex cleartext** (`"52bc7e859a"` this boot), will = Status offline msg; subscribe `Naxclow/P2P/Users/Device/sub/<UID>` (QoS1); publish Status + Info (incl. `version`, `token`, Wi-Fi SSID).
4. TCP to P2P host: `{"code":100,"uid":…,"token":…,"domain":…}` registration; persistent connection, heartbeats, forwarded commands (`code 301`).

Real-cloud confcheck answer captured during a controlled 3-minute un-sinkhole probe: `evidence/ota-confcheck-real-cloud.json` (device is bound to an app account: `isBind:"1"`, owner userId `481174c5658c37874529550232128447e`).

## Notes

- All identifiers rotate per boot: `random` (6 alnum), `token` (10 hex), confcheck `pwd`, MQTT password — but the camera accepts server directives with no payload integrity, and MQTT broker auth is effectively absent on the LAN broker (any LAN client publishes to `…/sub/<UID>`; proven in PoCs, see `evidence/exploits/`).
- `reboot:1` (code 299) executed over **both** MQTT (nanomq log confirms offline→online 1 s later) and TCP code-301 forward (camera resets ≤45 s).
