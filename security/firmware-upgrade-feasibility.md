# Firmware-upgrade feasibility — cam170 (dedicated reversing unit)

Goal: better/faster firmware, better image quality, more reliable AV stream.

## Candidate builds

| Candidate | Source | Verdict |
|---|---|---|
| Newer vendor build than 202503081631 | real cloud (`ota_url`/`updateUrl` = null server-side), public OTA host (newest artifact 2022-02-28) | **none exists** — device already runs the newest Naxclow build ever published to the reachable update infrastructure |
| `7252_A9_IPC_2103181543.rbl` (2021) / `7252_TG_IPC_2202281530.rbl` (2022) | `http://120.77.233.10/BK7252_P2P_IPC_FW/` | **older, wrong-model risk (TG), AES-RBL** — would downgrade AV quality and reliability; different ISP tuning; possible partition mismatch = brick risk. Not recommended |
| OpenIPC | openipc.org platform list | **no BK7252 support** (HiSilicon/ARM/MIPS SoCs listed; Beken absent) |
| OpenBeken (OpenBK7231T) | supports BK7252N/U per flashing list | Tasmota/ESPHome-style IoT firmware — **no IP-camera video pipeline**; would lose the stream entirely. Not an AV upgrade |
| Vendor RTT SDK (bekencorp/bk7251_rtt_audio_sdk, bk7252 RTT projects) | Beken SDK | real possibility in principle (community did boot webserver demos) — weeks of porting to this PCB's pinout/sensor config, no guarantee for gc0312 driver; out of scope |
| Raw SPI-flash dump + patched build | UART `msh` / clip | needs hardware work (FW-008 path); enables key extraction + targeted ISP/JPEG table tweaks — the only credible "better" path on this exact unit |

## Flash paths (for whichever build)

| Path | Status on cam170 | Risk |
|---|---|---|
| OTA via sinkholed `updateUrl` | mechanism verified (FW-005); would need a matching .rbl + valid CRC/AES | low operational risk, but **bricks if image ≠ build lineage** (uart.log: verify-fail → recovery-factory path) |
| SD card (RT-Thread OTA on /sd) | no evidence of a .rbl auto-load convention in acquired images | unknown |
| UART bootloader / SPI clip | pads present (community photos); msh console confirmed on older build | highest control, moderate brick; makes recovery possible (read-back first) |

## Recommendation

1. **Stay on 202503081631 + sinkhole** — already the best available AV/reliability combo; the relay/go2rtc path delivers a stable 12 fps 640×480 MJPEG + G.711 stream that has been production-reliable since 2026-10-01.
2. If pushing further: SPI read-back of the flash (clip, before any experiment), then a UART-based experiment loop with a known-good dump staged for restore. Any flash on this device happens **only with explicit per-instance approval at execution time**.
3. Quality ceiling is the gc0312 VGA sensor; if image quality itself is the goal, hardware replacement with an OpenIPC-supported 5MP unit is the honest answer, not a firmware swap.
