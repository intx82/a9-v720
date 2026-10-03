# Firmware acquisition & extraction status

## Acquired builds (see `evidence/firmware/hashes.txt`)

| File | Size | Build date | Source URL |
|---|---|---|---|
| `7252_A9_IPC_2102011649.rbl` | 618,688 | 2021-02-01 | `http://120.77.233.10/BK7252_P2P_IPC_FW/A9_RELEASE_FW/` |
| `7252_A9_IPC_2103181543.rbl` | 610,400 | 2021-03-18 | same (A9_RELEASE_FW + A9_DEBUG_FW — byte-identical) |
| `7252_TG_IPC_2202281530.rbl` | 665,600 | 2022-02-28 | `…/TG_SA9_RELEASE_FW/` |

All other folders on the OTA server (see `evidence/ota-index-BK7252_P2P_IPC_FW.html`):
`CY_DEBUG_FW`, `CY_RELEASE_FW`, `HB66_*` (cafago/HB66 clones), `K9_*`, `MINIONS_*`, `TG_SA9_DEBUG_FW`. Newest artifact anywhere on the host: 2022-02-28. **cam170 runs 202503081631 — its build is not on the public OTA host; `ota_url`/`updateUrl` for the device are `null` server-side** (`evidence/ota-confcheck-real-cloud.json`).

## RBL container format

```
00: "RBL\0" magic            40: 16-byte ASCII key-string "00010203040506070809" (default vendor key)
04: ver 02 01                4C: 4-byte CRC/hash, then high-entropy AES payload (8.000 bits/byte)
08: build timestamp (unix LE) to 80+ : image-name ASCII + padding
```
`unblob` not present on host; `binwalk -B` and `binwalk -e --matryoshka` find **zero signatures** — the entire app payload is AES-encrypted. **Unresolved region: 100 % (encrypted).** Extraction therefore yields no bootloader/kernel/squashfs — this is a BK7252 **RTOS** (RT-Thread 3.1.0, no Linux rootfs at all; confirmed by `docs/uart.log` boot banner in git history).

## What the device firmware actually is (verified from uart.log + live boot capture)

- RT-Thread 3.1.0, build banner e.g. `Dec 1 2022`; RT-Thread OTA pkg v0.2.4; FAL v0.4.0 flash abstraction.
- Boot: bootloader @0, app @ `os_addr 0x10000`; OTA verify failure path prints `App verify failed! Need to recovery factory firmware.`
- Wi-Fi: Beken `wlan`/`rwd` stack — **AP mode with no password factory default** (`wpa_hostapd_no_password_connected`, `--------wlan ap [no password] connected`).
- Video: gc0312 0.3 MP sensor → JPEG @ **640×480**, ~12 fps, ~7.6 KB/frame (~91 KB/s) over the P2P data channel; audio G.711 A-law 8 kHz mono. Snapshot: `evidence/screenshots/cam170-snapshot.jpg`.

## AV-quality levers (for the better-firmware goal)

- Sensor `gc0312` (VGA-class) is the hard ceiling for cam170 — any firmware can only optimise ISP tuning/JPEG quality tables, not resolution.
- The RBL app image is AES-encrypted with a vendor key not present in any acquired artifact — encoder/ISP parameter extraction requires either the matching (2025) build **plus** the key, or a raw SPI-flash dump from the device (hardware path, see upgrade notes).
