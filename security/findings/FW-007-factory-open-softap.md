## FW-007: Factory SoftAP with no password (candidate on current firmware)

**Severity:** Medium
**CVSS v3.1 Score:** 5.0 (Medium)
**CVSS Vector:** CVSS:3.1/AV:A/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:L
**Category:** CWE-294 / CWE-1393 (Default credentials/authentication)
**Affected Component:** Wi-Fi SoftAP mode (`_wifi_softap`)
**Location:** firmware wlan task
**Discovery Method:** Static Analysis (serial boot log)

### Description

Boot log shows AP mode `ssid:Nax_22000022A2AA key:` (empty) and `wpa_hostapd_no_password_connected` — factory/provisioning mode exposes an **open AP** whose SSID embeds the MAC, with the full device stack (incl. FW-001..003 surfaces) behind it. Any nearby attacker joining it reaches the camera pre-authentication. Verified on the firmware image that produced `docs/uart.log` (2022 build); current build behaviour **candidate** (same code lineage, not re-observed — device today runs joined to `Miau`).

### Impact

Pre-provisioning takeover; provisioning-while-open attacks; MAC-tracked tracking.

### Remediation

WPS/PBC-less enrolment with per-device PIN; never default AP to open WPA2-required mode.

### References

- CWE-1393; upstream fake_server.md `--set-wifi` flow

- **Discovered:** 2026-10-02/03
- **Reported:** n/a (internal assessment)
- **Status:** Open
**Analyst:** Andy (0x3d) — OpenFox assessment
