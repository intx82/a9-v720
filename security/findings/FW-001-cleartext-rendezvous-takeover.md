## FW-001: Unauthenticated cleartext HTTP rendezvous lets any MitM redirect/control the device

**Severity:** High
**CVSS v3.1 Score:** 7.7 (High)
**CVSS Vector:** CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:L
**Category:** CWE-319: Cleartext Transmission of Sensitive Information (+ CWE-295 improper certificate validation — no TLS at all)
**Affected Component:** HTTP bootstrap/confcheck client (`v720.naxclow.com:80`)
**Location:** firmware cloud client; endpoints `/app/api/ApiServer/getA9ConfCheck`, `/app/api/ApiSysDevices/getDevInfo`, `/app/api/ApiSysDevicesBatch/registerDevices`
**Discovery Method:** Dynamic Analysis (protocol capture against sinkhole + one controlled un-sinkhole probe)

### Description

The device bootstraps over plain HTTP with no server authentication: `random` (6 chars) and `token` (10 hex) are nonces used only server→device, and the answer body — `host`, `tcpPort`, `pwd`, `updateUrl` — is executed verbatim. Anyone who controls DNS/BGP/routing for `*.naxclow.com` becomes the device's cloud: they can point it at an attacker P2P server, read the session `pwd`, open streams, and inject all code-301 device commands.

**Verified:** the CatCam sinkhole relay *is* such a server, running in production on this LAN for months: cam170 faithfully registered with `host=10.0.0.1`, streamed to it, and accepted injected commands (see FW-002/003 PoCs). The real cloud's answer (same fields, incl. OTA section) was captured during a 3-minute controlled un-sinkhole: `evidence/ota-confcheck-real-cloud.json`, `evidence/pcaps/cam170-boot-mqtt-http.pcap` (t+65 s).

### Impact

1. **Full device control** — attacker becomes the device's "cloud": stream open, reboot, Wi-Fi reconfig (code 204!), SD format (207).
2. **Persistent man-in-the-middle** of camera video/audio and all credentials (rotating MQTT password, session pwd, owner userId).
3. **Fleet attack** — one DNS compromise targets every device of the batch.

**Technical Impact:** Confidentiality High / Integrity High / Availability Low (reboot/DoS only while exploiting).

### Proof of Concept

Any HTTP server answering the confcheck path with a chosen `host`:
```bash
python3 evidence/exploits/poc03_http_takeover.py rogue 80   # + DNS redirect of v720.naxclow.com
```
Production proof: cam170 streams on our relay right now (`http://10.0.0.1:8247/dev/080c0e054577/live`).

### Remediation

- Ship TLS (server cert pinning) for all cloud endpoints; bind answers to the device's request nonce.
- Per-device bootstrap credentials instead of shared-batch `random/token` pattern.

### Verification

After fix: TLS-only endpoints reject plaintext POST; a rogue server lacking the pinned cert is ignored.

### References

- CWE-319, CWE-295; OWASP IoT "Insecure Network Services"

- **Discovered:** 2026-10-02/03
- **Reported:** n/a (internal assessment)
- **Status:** Open
**Analyst:** Andy (0x3d) — OpenFox assessment
