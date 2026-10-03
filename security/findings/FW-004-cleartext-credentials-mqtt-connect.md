## FW-004: Device credentials + telemetry broadcast in cleartext (MQTT CONNECT, HTTP query params)

**Severity:** Medium
**CVSS v3.1 Score:** 4.3 (Medium)
**CVSS Vector:** CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N
**Category:** CWE-522: Insufficiently Protected Credentials / CWE-319
**Affected Component:** MQTT CONNECT + publish payloads; HTTP query strings
**Location:** firmware network task
**Discovery Method:** Dynamic Analysis (pcap)

### Description

Boot capture shows MQTT CONNECT carrying username=UID and password=`"52bc7e859a"` (10-hex, rotates per boot), plus Info publishes exposing owner-bound identifiers, Wi-Fi SSID (`Miau`) and firmware version; every HTTP request exposes `devicesCode/random/token` in the URI to every hop. Anyone passive-sniffing the segment (or any mirror/log, cf. nginx access logs) harvests live credentials and telemetry metadata.

**Verified:** `evidence/pcaps/cam170-boot-mqtt-http.pcap` (CONNECT t+243.18 s), `evidence/mqtt-info-boot.json`.

### Impact

1. Credential harvesting enables the FW-002/003 attacks from any broker-connected vantage.
2. Privacy leak: SSID, firmware version, owner userId, alert heartbeats.

### Proof of Concept

```bash
sudo tcpdump -i br0 -A 'host 10.0.0.170 and (port 1883 or port 80)' -c 200
```

### Remediation

MQTT over TLS with cert validation; move identifiers out of URIs; minimize telemetry metadata.

### References

- CWE-522, CWE-319

- **Discovered:** 2026-10-02/03
- **Reported:** n/a (internal assessment)
- **Status:** Open
**Analyst:** Andy (0x3d) — OpenFox assessment
