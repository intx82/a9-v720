## FW-008: Unauthenticated root shell (RT-Thread FINSH) on UART console

**Severity:** Medium (physical access)
**CVSS v3.1 Score:** 6.8 (Medium)
**CVSS Vector:** CVSS:3.1/AV:P/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
**Category:** CWE-1392: Use of Default Credentials / CWE-077
**Affected Component:** RT-Thread FINSH `msh />` prompt on debug UART
**Location:** PCB test-pad UART (upstream STLink/pad photos in community thread); `docs/uart.log`
**Discovery Method:** Static Analysis (serial capture)

### Description

The bootloader/RT-Thread log shows a live interactive `msh />` shell with full RT-Thread command set and no login. Physical access (3 screws + 3 pads) yields flash read (`flash` commands), memory, and the entire secret inventory — bypassing every remote mitigation and enabling raw-flash extraction of the AES-encrypted app partitions plus the keys that decrypt them in the field.

### Impact

Full secret extraction (keys/OTA key material), firmware implant injection, then permanent network compromise via FW-005 mechanics.

### Remediation

Fuse/disable debug console on production units; require signed auth for msh.

### References

- CWE-1392; RT-Thread FINSH documentation

- **Discovered:** 2026-10-02/03
- **Reported:** n/a (internal assessment)
- **Status:** Open
**Analyst:** Andy (0x3d) — OpenFox assessment
