## FW-002: Unauthenticated MQTT control channel (device commands from any LAN client)

**Severity:** Medium
**CVSS v3.1 Score:** 6.3 (Medium)
**CVSS Vector:** CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L
**Category:** CWE-306: Missing Authentication for Critical Function
**Affected Component:** MQTT client (subscribes `Naxclow/P2P/Users/Device/sub/<UID>`, QoS1)
**Location:** firmware MQTT task + broker configuration (anonymous access enabled)
**Discovery Method:** Dynamic Analysis

### Description

The device executes JSON device-commands published to its sub-topic with no message signature and no broker authentication visible to LAN clients. On our broker (nanomq, anonymous) any LAN process controls the camera. The camera's own broker credentials (rotating 10-hex password, username = UID) travel in cleartext, so even auth-enabled brokers leak them to anyone on the segment (FW-004).

**Verified:** `mosquitto_pub` reboot executed — broker log flips `080c0e054577 offline!/online!` within 1 s (`/var/log/nanomq.log` 2026-10-02 20:47:32 UTC); command 299 executed; control command 218 also delivered anonymously (no auth challenge); the documented MQTT command table (fake_server.md: 201-221 + 299: Wi-Fi set/scan, SD format, IR/LED, reboot) is served by the same unauthenticated sink.

### Impact

1. Reboot/DoS at will (299), Wi-Fi credential theft via forced reconfig/scan (204/211), SD format (207), IR/LED toggling.
2. Silent stream opening (privacy breach) via the normal watching handshake.

**Technical Impact:** C:L / I:L / A:L

### Proof of Concept

```bash
python3 evidence/exploits/poc01_mqtt_control.py 10.0.0.2 080c0e054577 --reboot
# run output: poc01.out ; broker evidence: nanomq.log offline->online
```

### Remediation

- Sign/mAC device-command payloads (per-device key), or tunnel MQTT with TLS + client certs.
- Broker: disable anonymous access; per-ACL publish to `sub/<UID>` only for the bound app account.

### Verification

Anonymous publish rejected (ACL log); unsigned command ignored by device.

### References

- CWE-306; OWASP IoT "Insecure Communication"/"Badly Protected Credentials"

- **Discovered:** 2026-10-02/03
- **Reported:** n/a (internal assessment)
- **Status:** Open
**Analyst:** Andy (0x3d) — OpenFox assessment
