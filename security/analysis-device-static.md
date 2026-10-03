# Static findings — device side (BK7252 RT-Thread RTOS)

No Linux rootfs exists on this device (RTOS monolith); analysis based on verified artifacts:
`docs/uart.log` (serial boot log, git history @a0ccf58), live boot capture `evidence/pcaps/cam170-boot-mqtt-http.pcap`, app protocol classes (`orig-app/com.naxclow.v720_source_from_JADX.zip` in git history), and live traffic against the sinkhole relay.

## Device / service inventory

| Item | Value | Source |
|---|---|---|
| SoC | Beken BK7252 (Wi-Fi+BLE SoC, ARM926/ARMv5 class) | upstream repo datasheet (`docs/BK7252 Data Sheet.pdf` @HEAD), uart banner |
| RTOS | RT-Thread 3.1.0 (+ FAL 0.4.0, OTA pkg 0.2.4) | `uart.log` banner |
| Flash layout | bootloader @0x0, app @ `os_addr 0x10000` | uart.log |
| Sensor/ISP | GalaxyCore gc0312, 640×480 JPEG, ~12 fps, G.711 8 kHz | MQTT Info `camType`, relay stream stats, snapshot evidence |
| Network services (LAN) | none listening — outbound only (TCP P2P, MQTT, HTTP) | 65 535-port scan (prior recon), live pcap |
| Radio services | SoftAP `Nax_<mac>` (factory, **no password**), STA + WPS/EasyJoin | uart.log `wpa_hostapd_no_password_connected`, `_wifi_softap: ssid:Nax_22000022A2AA key:` (empty) |
| Console | RT-Thread **FINSH/msh shell on UART**, prompt `msh />`, no auth | uart.log (`msh />` throughout) |

## Credentials / key material observed

| Secret | Value/format | Where | Verified |
|---|---|---|---|
| MQTT password | 10-hex, rotates per boot (`"52bc7e859a"`) | MQTT CONNECT cleartext | verified (pcap) |
| MQTT will token | static `"NAXCLOW"` | will payload | verified |
| Session `pwd` | 8-hex, from confcheck, echoed back in code-100 reg | HTTP + TCP | verified (relay+real cloud both serve it) |
| App-owner binding | userId `481174c5658c37874529550232128447e` (`isBind:1`) | real-cloud getDevInfo | verified (probe2 pcap) |
| RBL header key-string | ASCII `00010203040506070809` (vendor default field) | every acquired .rbl @0x40 | verified |
| WPS/EasyJoin PSK | `key:34974033A` printed to serial during join | uart.log | verified (older fw, candidate on current) |
| Device UID | `080c0e054577` = `080c0e` vendor prefix + 5 hex, sequential-family | all channels | verified (cam199 = `080c0e053F2F`) |

## Binary mitigations

RTOS flat image: no kernel, no ASLR/PIE, no stack canaries/RELRO applicable; firmware images AES-encrypted at rest on the OTA server but **delivered over cleartext HTTP** with only CRC verify — uart.log shows verify failure only triggers "recovery factory firmware", i.e. an attacker who can MITM dl2.naxclow.com (DNS is plain HTTP-reachable) supplies an image whose CRC passes; whether the AES/签名 check gates this on 2025 builds is unknown (no matching build acquired) — **candidate**, not verified.

## AV pipeline (goal context)

- Capture: gc0312 0.3 MP → MJPEG 640×480 via BK7252 ISP/JPEG encoder; nightly motion-gated frame replay in relay.
- Transport: UDP data channel w/ selective ARQ (pkgID window, code-605 retransmit), TCP control :6123.
- Ceiling: VGA sensor; realistic upgrades = JPEG quality tables / fps / ISP exposure tuning in newer builds, not resolution.
