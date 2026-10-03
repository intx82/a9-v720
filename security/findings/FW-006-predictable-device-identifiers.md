## FW-006: Sequential device identifiers enable batch enumeration

**Severity:** Medium
**CVSS v3.1 Score:** 4.3 (Medium)
**CVSS Vector:** CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L
**Category:** CWE-340: Generation of Predictable Numbers or Identifiers
**Affected Component:** bootstrap `registerDevices` (`data = 0800c00%05d` counter) / UID structure
**Location:** cloud bootstrap API + device provisioning
**Discovery Method:** Static Analysis (upstream captures) + Dynamic PoC

### Description

UIDs are `080c0e05` + 4 hex, allocated near-sequentially per batch: the two LAN cameras differ by 0x648. A linear scan over the 16-bit suffix enumerates a whole batch; combined with FW-001/002 each hit is controllable. The scan itself is harmless (relay device-list demo), but establishes the targeting primitive for cloud-side abuse.

**Verified:** PoC resolves both live cameras from a range sweep (poc04.out).

### Proof of Concept

```bash
python3 evidence/exploits/poc04_uid_enum.py 080c0e05 3F00 0x700
```

### Remediation

Random 128-bit device IDs (public identifier ≠ addressing key); rate-limit enumeration server-side.

### References

- CWE-340

- **Discovered:** 2026-10-02/03
- **Reported:** n/a (internal assessment)
- **Status:** Open
**Analyst:** Andy (0x3d) — OpenFox assessment
