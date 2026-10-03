## FW-003: TCP P2P control channel accepts forwarded commands without device-side session check

**Severity:** Medium
**CVSS v3.1 Score:** 6.3 (Medium)
**CVSS Vector:** CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L
**Category:** CWE-306 + CWE-347 (Improper Verification of Cryptographic Signature — absent)
**Affected Component:** code-100 registration + code-301 forward-command handling on TCP :6123 (real cloud :29942)
**Location:** firmware P2P client (framing: `uint32 len | uint16 cmd | flags | fwd-id | pkgID`)
**Discovery Method:** Dynamic Analysis

### Description

Registration is `{"code":100,"uid":<UID>,"token":<pwd from cleartext confcheck>}` — knowledge most any "server" the device talks to possesses by design (FW-001). Forwarded device commands (code 301) are executed with no per-command auth. Our CatCam relay demonstrates day-and-night operation: `POST /dev/<uid>/cmd` on the relay injects arbitrary forward commands; the camera rebooted ≤7 s after a TCP-path 299 (relay log 2026-10-02 22:30:08→22:30:15).

**Verified:** reboot via relay injection; camera registered against a third-party-chosen `host` in probe2 (`pwd` echoed unmodified).

### Impact

1. Same control surface as FW-002 for anyone who can reach/pose as the P2P server.
2. Video/audio interception when the attacker controls the data channel.

### Proof of Concept

```bash
python3 evidence/exploits/poc02_relay_cmd.py --reboot   # output: poc02.out
```

### Remediation

- Device-side: verify a MAC over forwarded commands using a per-device secret not known to the routing server (end-to-end signed control plane).
- Bind sessions to the device's ephemeral key exchange, not a server-side password echo.

### Verification

Injection without valid MAC ignored; session hijack rejected after TLS/SPKI rollout.

### References

- CWE-306, CWE-347

- **Discovered:** 2026-10-02/03
- **Reported:** n/a (internal assessment)
- **Status:** Open
**Analyst:** Andy (0x3d) — OpenFox assessment
