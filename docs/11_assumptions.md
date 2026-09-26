# 11 - Assumptions Register

## 1. Document purpose

This document records every **assumption** that the Smart Street Light V1
engineering baseline currently depends on.

An assumption is a statement that is treated as true for the purpose of
progress, but which is **not yet a decided requirement or design choice**.
Each assumption records what happens if it turns out to be wrong.

Assumptions are not requirements. They are tracked here so that they can be
converted into decisions (recorded in
[12_engineering_decisions.md](12_engineering_decisions.md)) or into
requirements when they are resolved.

---

## 2. Status definitions

| Status | Meaning |
| --- | --- |
| `Target` | A stated engineering target, not yet validated. |
| `Open` | Not decided; progress is made on a provisional basis. |
| `Accepted` | Provisionally accepted for V1; revisit if affected. |

---

## 3. Register

### A-01 - Approximately 16 lamps per group

| Field | Value |
| --- | --- |
| Assumption | Approximately 16 lamp nodes per group is the initial target. |
| Reason | Stated project target; drives bus loading and polling design. |
| Status | `Target` |
| Effect if changed | Polling cycle time, bus loading, storage sizing and Group Controller capacity must be re-evaluated. The architecture is required to scale, so no redesign is expected, but timing budgets change. |
| Related requirements | `PR-SCALABILITY-001`, `PR-COMM-002` |

---

### A-02 - Nominal V1 switched lamp output is 230 VAC

| Field | Value |
| --- | --- |
| Assumption | The V1 switched lamp output is nominally 230 VAC. |
| Reason | India and China are important initial target markets. |
| Status | `Target` |
| Effect if changed | Switching element selection, measurement front-end range, and safety scope all change; the measurement model range configuration changes. |
| Related requirements | `PR-MEASURE-001` |

---

### A-03 - Controller input target is 90-305 VAC

| Field | Value |
| --- | --- |
| Assumption | The controller input target range is 90-305 VAC. |
| Reason | Wide-range input supports international adaptability. |
| Status | `Target` |
| Effect if changed | Power supply design and measurement range assumptions change; no requirement change is expected. |
| Related requirements | `PR-MEASURE-001` |

---

### A-04 - V1 scope is single-phase line-to-neutral

| Field | Value |
| --- | --- |
| Assumption | V1 addresses single-phase, line-to-neutral installations only. |
| Reason | Reduces V1 complexity; three-phase is a later consideration. |
| Status | `Accepted` |
| Effect if changed | Measurement model, node hardware and fault categories (`SUPPLY_VOLTAGE`) would require extension; architecture remains valid. |
| Related requirements | `PR-MEASURE-001`, `PR-DIAG-005` |

---

### A-05 - RS-485 baud rate is 9.6 kbps or 19.2 kbps

| Field | Value |
| --- | --- |
| Assumption | A low baud rate of 9.6 kbps or 19.2 kbps will be used. |
| Reason | Favours noise immunity on long street-lighting runs. |
| Status | `Open` |
| Effect if changed | Polling cycle time, maximum practical node count, protocol timing tests and the achievable reporting interval all change. |
| Related requirements | `PR-COMM-002`, `PR-COMM-007` |

---

### A-06 - RS-485 is single-master with the Group Controller as sole master

| Field | Value |
| --- | --- |
| Assumption | The Group Controller is the only bus master; nodes transmit only when addressed. |
| Reason | Deterministic, collision-free communication. |
| Status | `Accepted` |
| Effect if changed | Collision handling, arbitration and additional protocol states would be required. |
| Related requirements | `PR-COMM-001` |

---

### A-07 - Out-of-window behaviour of `AUTO_SCHEDULE_SENSOR`

| Field | Value |
| --- | --- |
| Assumption | Outside the configured time window, the lamp is OFF by default. |
| Reason | Common municipal practice of restricting operation to defined windows. |
| Status | `Open` |
| Effect if changed | Lighting behaviour, energy results and Phase 3 test expectations change. Must be resolved before Phase 3 design is frozen. |
| Related requirements | `PR-LIGHT-002` |

---

### A-08 - Restart-default lamp state

| Field | Value |
| --- | --- |
| Assumption | After restart, a lamp node restores its last known commanded state. |
| Reason | Preserves operator intent across resets. |
| Status | `Open` |
| Effect if changed | Post-restart behaviour, safety review and `PR-CONTROL-005` test expectations change. |
| Related requirements | `PR-CONTROL-005` |

---

### A-09 - Storage-full behaviour

| Field | Value |
| --- | --- |
| Assumption | Storage-full behaviour has not been selected. Candidates: stop recording, overwrite oldest, raise condition only. |
| Reason | The choice has evidence-retention consequences that require an explicit decision. |
| Status | `Open` |
| Effect if changed | Record retention, completeness of the event history and diagnostic value change. Must be resolved before Phase 8 design is frozen. |
| Related requirements | `PR-STORAGE-006`, `PR-STORAGE-005` |

---

### A-10 - Target record retention duration is unspecified

| Field | Value |
| --- | --- |
| Assumption | No target retention duration has been specified for stored records. |
| Reason | Retention depends on site policy, storage capacity and upload cadence. |
| Status | `Open` |
| Effect if changed | Storage capacity sizing, upload cadence and the storage-full decision are all affected. |
| Related requirements | `PR-STORAGE-001`, `PR-STORAGE-006` |

---

### A-11 - Fault severity scale is not defined

| Field | Value |
| --- | --- |
| Assumption | A severity scale exists, but its values are not defined. |
| Reason | Severity drives notification and escalation; the scale is a design choice. |
| Status | `Open` |
| Effect if changed | Notification and escalation configuration and Phase 6 tests change. |
| Related requirements | `PR-FAULT-002`, `PR-FAULT-007`, `PR-FAULT-008` |

---

### A-12 - Fault clear policy is not defined

| Field | Value |
| --- | --- |
| Assumption | The conditions required to clear a latched fault (beyond hysteresis) are not defined. |
| Reason | Clear policy interacts with latching and confirmation and must be decided with them. |
| Status | `Open` |
| Effect if changed | Fault lifecycle behaviour and Phase 6 tests change; risk of either sticky or flapping faults. |
| Related requirements | `PR-FAULT-005`, `PR-FAULT-006` |

---

### A-13 - Time synchronization source and cadence

| Field | Value |
| --- | --- |
| Assumption | Time is distributed by the Group Controller, which itself obtains time from upstream; cadence is undefined. |
| Reason | Architecture requires group-consistent time; cadence affects drift handling. |
| Status | `Open` |
| Effect if changed | Time-uncertainty thresholds and `PR-TIME-004` behaviour change. |
| Related requirements | `PR-TIME-003`, `PR-TIME-004` |

---

### A-14 - Upstream link type for the Group Controller

| Field | Value |
| --- | --- |
| Assumption | The Group Controller reaches the Master Control Center over a wired or cellular upstream link; the selection is undecided. |
| Reason | Both Ethernet and cellular candidates exist. |
| Status | `Open` |
| Effect if changed | Connectivity modelling, availability assumptions and the store-and-forward test scenarios change. |
| Related requirements | `PR-OFFLINE-001`, `PR-OFFLINE-002` |

---

### A-15 - Cellular module regional variant is undecided

| Field | Value |
| --- | --- |
| Assumption | The Quectel EG915U-CN candidate is China-region; a regional variant will be needed for other markets. |
| Reason | Regional certification and band support differ. |
| Status | `Open` |
| Effect if changed | Hardware selection, certification path and international adaptability claims change. |
| Related requirements | (None directly - hardware candidate only) |

---

### A-16 - External SPI NOR candidate capacity is sufficient

| Field | Value |
| --- | --- |
| Assumption | The S25FL128L candidate (16 MB) is sufficient for the intended record volume and retention. |
| Reason | Capacity must be checked against intervals, record size and retention once those are designed. |
| Status | `Open` |
| Effect if changed | Storage component selection, record layout and retention policy change. |
| Related requirements | `PR-STORAGE-001`, `PR-STORAGE-006` |

---

### A-17 - Node addressing scheme

| Field | Value |
| --- | --- |
| Assumption | Lamp node bus addresses are assigned at commissioning and are unique within a group. |
| Reason | Unique addressing is required for polling; the assignment method is a commissioning decision. |
| Status | `Open` |
| Effect if changed | Commissioning workflow and identity-conflict detection behaviour change. |
| Related requirements | `PR-IDENTITY-003` |

---

### A-18 - A switching-feedback mechanism is available

| Field | Value |
| --- | --- |
| Assumption | Some mechanism exists that lets the lamp node observe the state of the switching path, separately from the command. The domain model uses the abstract term `switching_feedback` and does not assume which mechanism is used. |
| Reason | Expected-versus-actual diagnosis requires the switching path state to be observable separately from the command. The physical realisation (isolated switched-output voltage sensing, relay auxiliary contact, or another mechanism) is a hardware-design decision. |
| Status | `Open` |
| Effect if changed | If no feedback mechanism exists, `PR-DIAG-003` and `PR-DIAG-004` lose a primary evidence input and the diagnostic rules must be revised. This is the highest-impact assumption in the diagnostics area. |
| Related requirements | `PR-DIAG-001`, `PR-DIAG-003`, `PR-DIAG-004` |

---

### A-19 - Operator identity and authorization mechanism

| Field | Value |
| --- | --- |
| Assumption | Operators are identifiable and authorizable, but the mechanism is undefined. |
| Reason | Authorization is required for override commands; the mechanism is a later design/security decision. |
| Status | `Open` |
| Effect if changed | `PR-SECURITY-001` and `PR-SECURITY-002` implementation and tests change; the audit model gains or loses actor detail. |
| Related requirements | `PR-SECURITY-001`, `PR-SECURITY-002`, `PR-SECURITY-003` |

---

### A-20 - Site / group / lamp identifier assignment

| Field | Value |
| --- | --- |
| Assumption | Site, group and lamp identifiers are assigned by the deploying organization and are stable. |
| Reason | Identity hierarchy requires externally assigned identifiers. |
| Status | `Open` |
| Effect if changed | Identity model and Master Control Center aggregation change. |
| Related requirements | `PR-IDENTITY-001`, `PR-IDENTITY-002` |

---

### A-21 - Environmental fault category without a defined environmental sensor set

| Field | Value |
| --- | --- |
| Assumption | The `ENVIRONMENTAL` fault category exists in the vocabulary, but the environmental inputs that trigger it are not defined. |
| Reason | The category is required by the controlled vocabulary; the sensor set is a later design decision. |
| Status | `Open` |
| Effect if changed | Sensor set, measurement model and fault rules expand or contract. |
| Related requirements | `PR-FAULT-001` |

---

### A-22 - Measurement front-end adequacy for monitoring

| Field | Value |
| --- | --- |
| Assumption | The candidate measurement front end is adequate for engineering monitoring (not for billing-grade metering). |
| Reason | The product explicitly disclaims billing-grade metering. |
| Status | `Accepted` |
| Effect if changed | If metering-grade accuracy were ever required, calibration, traceability and legal metrology obligations would enter scope and the V1 boundary would change. |
| Related requirements | `PR-MEASURE-005` |

---

### A-23 - Digital prototype implementation language is Python

| Field | Value |
| --- | --- |
| Assumption | The digital prototype will be implemented in Python. |
| Reason | Project direction for the simulation work. |
| Status | `Accepted` |
| Effect if changed | Tooling, test framework and repository layout change; requirements are unaffected. |
| Related requirements | (None - implementation choice) |

---

### A-24 - No graphical UI is required for the Master Control Center in early phases

| Field | Value |
| --- | --- |
| Assumption | The Master Control Center is modelled as a logical/data layer without a graphical user interface in the early phases. |
| Reason | UI work would precede validated behaviour. |
| Status | `Accepted` |
| Effect if changed | Demonstration and review approach changes; the data layer requirement is unaffected. |
| Related requirements | `PR-SCALABILITY-002`, `PR-SECURITY-003` |

---

### A-25 - Hardware candidates are not frozen

| Field | Value |
| --- | --- |
| Assumption | All hardware components referenced in the documentation remain candidates. |
| Reason | Manufacturing decisions are not frozen; Minewing review may change selections. |
| Status | `Accepted` |
| Effect if changed | Any component change requires a new decision record and may affect assumptions A-02, A-03, A-15, A-16, A-18 and A-22. |
| Related requirements | (None - governance assumption) |

---

---

### A-26 - Physical RTC backup duration is not established

| Field | Value |
| --- | --- |
| Assumption | The physical RTC backup circuit (candidate RV-3028-C7 plus backup storage) will maintain time for the required duration. |
| Reason | The digital prototype models logical clock semantics only and cannot measure backup retention, leakage or temperature effects. |
| Status | `Open` |
| Effect if changed | Time-uncertainty handling and offline record ordering would need to be revisited; a hardware measurement campaign would be required. |
| Related requirements | `PR-TIME-001`, `PR-TIME-002`, `PR-TIME-004` |

---

### A-27 - Detailed role permission matrix is deferred

| Field | Value |
| --- | --- |
| Assumption | The preliminary roles (`VIEWER`, `OPERATOR`, `ENGINEER`, `ADMIN`, `OWNER`) are sufficient for V1; the detailed permission mapping is deferred to the security design phase. |
| Reason | Role concepts are needed now for authorization decisions; a full permission matrix would be speculative without the security design. |
| Status | `Accepted` |
| Effect if changed | Authorization checks would need to be extended; the domain model's role abstraction is unaffected. |
| Related requirements | `PR-SECURITY-006` |

---

### A-28 - Group Controller local storage medium is not selected

| Field | Value |
| --- | --- |
| Assumption | The Group Controller's local storage/buffer is modelled abstractly; the physical memory device is not selected. |
| Reason | Selecting a memory device now would prematurely constrain the hardware architecture phase. |
| Status | `Accepted` |
| Effect if changed | Storage capacity and buffering limits would need to be dimensioned; the abstract interface is unaffected. |
| Related requirements | `PR-SCALABILITY-005`, `PR-STORAGE-010` |

---

### A-29 - Numeric retention period is not decided

| Field | Value |
| --- | --- |
| Assumption | No numeric retention period (including the hard minimum retention) has been decided. |
| Reason | Retention depends on site policy, regulation and storage capacity, none of which are established. |
| Status | `Open` |
| Effect if changed | Storage sizing and the storage-full decision are affected; the retention abstraction is unaffected. |
| Related requirements | `PR-STORAGE-005`, `PR-STORAGE-009` |

## 4. Summary

| Status | Count | Identifiers |
| --- | --- | --- |
| `Target` | 3 | A-01, A-02, A-03 |
| `Open` | 18 | A-05, A-07, A-08, A-09, A-10, A-11, A-12, A-13, A-14, A-15, A-16, A-17, A-18, A-19, A-20, A-21, A-26, A-29 |
| `Accepted` | 8 | A-04, A-06, A-22, A-23, A-24, A-25, A-27, A-28 |
| **Total** | **29** | A-01 .. A-29 |

The `Open` assumptions are the ones that must be resolved before the phase
they block:

| Blocking phase | Open assumptions |
| --- | --- |
| Phase 3 (lighting control) | A-07, A-08 |
| Phase 6 (fault lifecycle) | A-11, A-12 |
| Phase 8 (storage) | A-09, A-10, A-16 |
| Phase 9 (RS-485) | A-05, A-17 |
| Phase 10 (group controller) | A-13, A-14 |
| Phase 12 (configuration) | A-19, A-20 |
| Physical validation phase | A-26 |
| Retention design (Phase 8 / Phase 12) | A-29 |

---

## 5. Revision history

| Date | Change |
| --- | --- |
| 2026-09-25 | Initial assumptions register created (25 assumptions). |
| 2026-09-25 | A-18 reworded to the `switching_feedback` abstraction; A-26 to A-29 added (29 assumptions). |

---

## 6. Related documents

- [00_project_overview.md](00_project_overview.md)
- [02_product_requirements.md](02_product_requirements.md)
- [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
- [10_hardware_reference.md](10_hardware_reference.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
- [requirements_traceability.md](requirements_traceability.md)

## Corrective audit disposition (2026-09-26)

A-09 and A-10 remain open: deterministic capacity failure is not a selected
storage-full policy or retention duration. A-18 remains an abstract diagnostic
input requiring a physical implementation decision. A-26 remains a hardware
validation item. A-27 remains an accepted deferral of the detailed production
permission matrix; correcting preliminary authorization bypasses does not
resolve that matrix. A-29 remains open; supplied retention floors are enforced
without selecting a default period. No assumption status changed in this pass.
