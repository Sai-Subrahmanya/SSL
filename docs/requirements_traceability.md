# Requirements Traceability

## 1. Document purpose

This document maps every requirement to its architecture element, its
future implementation module, its future test, and its verification status.

It is the mechanism that enforces the project principle:

```text
REQUIREMENT -> ARCHITECTURE -> DESIGN -> IMPLEMENTATION -> TEST -> AUDIT -> VALIDATION
```

## 2. Column definitions

| Column | Meaning |
| --- | --- |
| Requirement ID | Identifier from [02_product_requirements.md](02_product_requirements.md). |
| Requirement | Short title of the requirement. |
| Architecture element | Element of [01_system_architecture.md](01_system_architecture.md) that carries it. |
| Future implementation module | Conceptual module expected to implement it, with the phase that creates it. |
| Future test | Test reference. `TBD` because no test exists yet. |
| Verification status | Current standing. |

Module names above are **conceptual**, not file names. No file name is
invented for code that does not yet exist. Test identifiers are assigned
when the corresponding phase begins.

## 3. Traceability matrix

### 3.1 Lighting control behaviour

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-LIGHT-001` | Automatic sensor-based control (AUTO_SENSOR) | Lighting control (Lamp Node) | Lighting control module - Phase 3 | TBD (Phase 3) | Not started - implementation pending |
| `PR-LIGHT-002` | Schedule-with-sensor control (AUTO_SCHEDULE_SENSOR) | Lighting control (Lamp Node) | Lighting control + schedule handling - Phase 3 | TBD (Phase 3) | Not started - implementation pending |
| `PR-LIGHT-003` | Fixed-schedule control (FIXED_SCHEDULE) | Lighting control (Lamp Node) | Schedule handling - Phase 3 | TBD (Phase 3) | Not started - implementation pending |
| `PR-LIGHT-004` | Authorized operator override (FORCE_ON / FORCE_OFF) | Command handling / override | Override handling - Phase 3 | TBD (Phase 3) | Not started - implementation pending |
| `PR-LIGHT-005` | Return to automatic mode (RETURN_TO_AUTO) | Command handling / override | Override handling - Phase 3 | TBD (Phase 3) | Not started - implementation pending |

### 3.2 Command handling, mode priority, restart behaviour

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-CONTROL-001` | Mode priority ordering | Mode priority resolution | Mode / priority resolver - Phase 3 | TBD (Phase 3) | Not started - implementation pending |
| `PR-CONTROL-002` | Command lifecycle and success definition | Command lifecycle | Command handling - Phase 2 / Phase 10 | TBD (Phase 10) | Not started - implementation pending |
| `PR-CONTROL-003` | Duplicate command handling | Command lifecycle / duplicate detection | Command handling + protocol sequencing - Phase 9 / Phase 10 | TBD (Phase 9) | Not started - implementation pending |
| `PR-CONTROL-004` | Command authorization status | Command authorization | Command authorization - Phase 10 / Phase 16 | TBD (Phase 16) | Not started - implementation pending |
| `PR-CONTROL-005` | Safe state restoration after restart | Lamp Node lifecycle / watchdog | Lamp Node lifecycle - Phase 2 | TBD (Phase 2) | Not started - implementation pending |
| `PR-CONTROL-006` | No automatic shutdown for non-protective conditions | Protective behaviour policy | Fault / lighting control policy - Phase 6 | TBD (Phase 6) | Not started - implementation pending |

### 3.3 Measurement handling

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-MEASURE-001` | Per-lamp measurement set | Measurement handling | Measurement module - Phase 4 | TBD (Phase 4) | Not started - implementation pending |
| `PR-MEASURE-002` | Configurable measurement and reporting intervals | Measurement handling | Measurement scheduling - Phase 4 | TBD (Phase 4) | Not started - implementation pending |
| `PR-MEASURE-003` | Energy accumulation | Energy accumulation | Energy accumulator - Phase 4 | TBD (Phase 4) | Not started - implementation pending |
| `PR-MEASURE-004` | Sensor validity reporting | Sensor health monitoring | Sensor health handling - Phase 4 | TBD (Phase 4) | Not started - implementation pending |
| `PR-MEASURE-005` | Monitoring values, not billing-grade metering | Documentation constraint (no accuracy claim) | Not applicable - documentation constraint | Inspection (Phase 0 / Phase 18) | Not started - implementation pending |

### 3.4 Expected-versus-actual diagnostics

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-DIAG-001` | Multi-evidence diagnosis | Diagnostics (Lamp Node) | Diagnostics module - Phase 5 | TBD (Phase 5) | Not started - implementation pending |
| `PR-DIAG-002` | Normal-operation diagnostic rule | Diagnostics (Lamp Node) | Diagnostic rule set - Phase 5 | TBD (Phase 5) | Not started - implementation pending |
| `PR-DIAG-003` | Open-load / lamp-fault diagnostic rule | Diagnostics (Lamp Node) | Diagnostic rule set - Phase 5 | TBD (Phase 5) | Not started - implementation pending |
| `PR-DIAG-004` | Unexpected-current diagnostic rule | Diagnostics (Lamp Node) | Diagnostic rule set - Phase 5 | TBD (Phase 5) | Not started - implementation pending |
| `PR-DIAG-005` | Supply-voltage diagnostic rule | Diagnostics (Lamp Node) | Diagnostic rule set - Phase 5 | TBD (Phase 5) | Not started - implementation pending |
| `PR-DIAG-006` | Sensor-fault diagnostic rule | Diagnostics (Lamp Node) | Diagnostic rule set - Phase 5 | TBD (Phase 5) | Not started - implementation pending |
| `PR-DIAG-007` | Diagnostic classification levels and evidential status | Diagnostics (Lamp Node) | Diagnostic classification levels - Phase 5 | TBD (Phase 5) | Not started - implementation pending |

### 3.5 Fault model and fault lifecycle

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-FAULT-001` | Fault type categories | Fault model | Fault model - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-002` | Fault severity classification | Fault model / severity | Fault severity handling - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-003` | Fault lifecycle state machine | Fault lifecycle | Fault lifecycle state machine - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-004` | Rejection of illegal fault transitions | Fault lifecycle | Fault transition validation - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-005` | Configurable fault confirmation | Fault confirmation | Confirmation policy - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-006` | Fault latching and hysteresis | Fault latching | Latching and hysteresis - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-007` | Fault notification | Fault notification | Notification handling - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-008` | Acknowledgement, reminder and escalation | Fault acknowledgement / escalation | Acknowledgement and escalation - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-009` | Unacknowledged alerts must not switch the lamp OFF | Protective behaviour policy | Fault / lighting control policy - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-010` | Repair workflow | Repair workflow | Repair workflow - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-011` | Verification workflow and failed verification | Verification workflow | Verification workflow - Phase 6 | TBD (Phase 6) | Not started - implementation pending |
| `PR-FAULT-012` | Fault closure and failure containment | Fault closure / failure containment | Closure handling + group containment - Phase 6 / Phase 13 | TBD (Phase 6 / Phase 13) | Not started - implementation pending |

### 3.6 Communication architecture and behaviour

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-COMM-001` | RS-485 master/slave discipline | RS-485 bus discipline | RS-485 master / node stack - Phase 9 | TBD (Phase 9) | Not started - implementation pending |
| `PR-COMM-002` | Node addressing and group size | Node addressing | Address handling - Phase 9 | TBD (Phase 9) | Not started - implementation pending |
| `PR-COMM-003` | Frame format | Frame format | Frame codec - Phase 9 | TBD (Phase 9) | Not started - implementation pending |
| `PR-COMM-004` | Initial message type set | Message types | Message dispatcher - Phase 9 | TBD (Phase 9) | Not started - implementation pending |
| `PR-COMM-005` | Sequence numbering, duplicate and replay handling | Sequence handling | Sequence / duplicate handling - Phase 9 | TBD (Phase 9) | Not started - implementation pending |
| `PR-COMM-006` | CRC integrity verification | Frame integrity | CRC checking - Phase 9 | TBD (Phase 9) | Not started - implementation pending |
| `PR-COMM-007` | Polling, timeout and retry policy | Group Controller polling | Polling, timeout and retry - Phase 10 | TBD (Phase 10) | Not started - implementation pending |
| `PR-COMM-008` | Communication state machine | Communication state machine | Communication state machine - Phase 11 | TBD (Phase 11) | Not started - implementation pending |
| `PR-COMM-009` | Communication failure must not stop local operation | Offline operation / recovery | Offline operation and recovery - Phase 11 | TBD (Phase 11) | Not started - implementation pending |

### 3.7 Storage, logging and retention

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-STORAGE-001` | Local persistent record storage | Local storage | Storage layer - Phase 8 | TBD (Phase 8) | Not started - implementation pending |
| `PR-STORAGE-002` | Record structure | Record envelope | Record codec - Phase 8 | TBD (Phase 8) | Not started - implementation pending |
| `PR-STORAGE-003` | Power-loss safety | Commit / power-loss semantics | Commit and recovery logic - Phase 8 | TBD (Phase 8) | Not started - implementation pending |
| `PR-STORAGE-004` | Corruption detection and handling | Corruption handling | Integrity checking - Phase 8 | TBD (Phase 8) | Not started - implementation pending |
| `PR-STORAGE-005` | Retention: automatic deletion off by default | Retention policy | Retention policy - Phase 8 | TBD (Phase 8) | Not started - implementation pending |
| `PR-STORAGE-006` | Storage-full visibility | Storage-full condition | Storage-full handling - Phase 8 | TBD (Phase 8) | Not started - implementation pending |
| `PR-STORAGE-007` | Separation of configuration/calibration storage | Configuration storage separation | Configuration storage - Phase 8 / Phase 12 | TBD (Phase 12) | Not started - implementation pending |
| `PR-STORAGE-008` | Store-and-forward buffering with upload confirmation | Store-and-forward | Store-and-forward queue - Phase 8 | TBD (Phase 8) | Not started - implementation pending |

### 3.8 Timekeeping and synchronization

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-TIME-001` | RTC-backed local timekeeping | Local time source (RTC) | Time source - Phase 2 | TBD (Phase 2) | Not started - implementation pending |
| `PR-TIME-002` | Offline timestamps with validity indication | Record timestamping | Timestamp validity handling - Phase 7 | TBD (Phase 7) | Not started - implementation pending |
| `PR-TIME-003` | Time synchronization | Time synchronization | Time synchronization - Phase 10 | TBD (Phase 10) | Not started - implementation pending |
| `PR-TIME-004` | Time-uncertainty handling and recovery | Time-uncertainty handling | Time validity tracking - Phase 11 | TBD (Phase 11) | Not started - implementation pending |

### 3.9 Configuration handling

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-CONFIG-001` | Configuration parameter set | Configuration model | Configuration model - Phase 12 | TBD (Phase 12) | Not started - implementation pending |
| `PR-CONFIG-002` | Configuration read and write over the bus | Configuration distribution | Configuration distribution - Phase 12 | TBD (Phase 12) | Not started - implementation pending |
| `PR-CONFIG-003` | Configuration validation | Configuration validation | Configuration validation - Phase 12 | TBD (Phase 12) | Not started - implementation pending |
| `PR-CONFIG-004` | Configuration change auditability | Configuration audit | Audit trail - Phase 12 | TBD (Phase 12) | Not started - implementation pending |
| `PR-CONFIG-005` | Configuration persistence and versioning | Configuration persistence | Configuration persistence and versioning - Phase 12 | TBD (Phase 12) | Not started - implementation pending |
| `PR-CONFIG-006` | No hardcoded operational thresholds | Cross-cutting (no hardcoded thresholds) | Configuration + fault policy - Phase 6 / Phase 12 | Inspection (Phase 6 / Phase 12) | Not started - implementation pending |

### 3.10 Device identity

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-IDENTITY-001` | Identity hierarchy | Identity model | Identity model - Phase 1 | TBD (Phase 1) | Not started - implementation pending |
| `PR-IDENTITY-002` | Deterministic and persistent identity | Identity persistence | Identity assignment - Phase 2 | TBD (Phase 2) | Not started - implementation pending |
| `PR-IDENTITY-003` | Bus address uniqueness | Bus addressing | Address management - Phase 9 | TBD (Phase 9) | Not started - implementation pending |
| `PR-IDENTITY-004` | Identity query | Identity query | Identity query - Phase 9 | TBD (Phase 9) | Not started - implementation pending |

### 3.11 Authorization, authentication, audit, tamper

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-SECURITY-001` | Operator authorization for overrides | Command authorization | Authorization handling - Phase 10 / Phase 16 | TBD (Phase 16) | Not started - implementation pending |
| `PR-SECURITY-002` | Command authentication status | Command authentication | Authentication status handling - Phase 10 / Phase 16 | TBD (Phase 16) | Not started - implementation pending |
| `PR-SECURITY-003` | Audit trail | Audit history | Audit trail - Phase 15 | TBD (Phase 15) | Not started - implementation pending |
| `PR-SECURITY-004` | Tamper detection | Tamper detection | Tamper detection - Phase 14 | TBD (Phase 14) | Not started - implementation pending |
| `PR-SECURITY-005` | Security validation boundary | Documentation constraint (claim discipline) | Not applicable - documentation constraint | Inspection (Phase 0 / Phase 18) | Not started - implementation pending |

### 3.12 Scale and failure containment

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-SCALABILITY-001` | Lamps per group | Group sizing | Group simulation - Phase 13 | TBD (Phase 13) | Not started - implementation pending |
| `PR-SCALABILITY-002` | Groups per site | Multi-group aggregation | Master Control Center aggregation - Phase 15 | TBD (Phase 13) | Not started - implementation pending |
| `PR-SCALABILITY-003` | Failure containment | Failure containment | Failure containment - Phase 13 | TBD (Phase 13) | Not started - implementation pending |
| `PR-SCALABILITY-004` | Architectural headroom | Architectural headroom | Cross-cutting - Phase 13 | Inspection (Phase 13) | Not started - implementation pending |

### 3.13 Offline operation and store-and-forward

| Requirement ID | Requirement | Architecture element | Future implementation module | Future test | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-OFFLINE-001` | Local operation without Internet | Offline operation | Offline operation - Phase 11 | TBD (Phase 11) | Not started - implementation pending |
| `PR-OFFLINE-002` | Local operation without the Master Control Center | Offline operation | Offline operation - Phase 11 | TBD (Phase 11) | Not started - implementation pending |
| `PR-OFFLINE-003` | Local operation without the Group Controller | Offline operation | Offline operation - Phase 11 | TBD (Phase 11) | Not started - implementation pending |
| `PR-OFFLINE-004` | Offline record buffering | Record buffering | Store-and-forward queue - Phase 8 | TBD (Phase 8) | Not started - implementation pending |
| `PR-OFFLINE-005` | Post-recovery synchronization without silent loss | Recovery and synchronization | Recovery and synchronization - Phase 11 | TBD (Phase 11) | Not started - implementation pending |

## 4. Summary

| Metric | Value |
| --- | --- |
| Requirements traced | 80 |
| Requirements with architecture element | 80 |
| Requirements with future implementation module | 80 |
| Requirements with a completed test | 0 |
| Requirements verified | 0 |

## 5. Verification status definitions

| Status | Meaning |
| --- | --- |
| Not started - implementation pending | Requirement documented; nothing implemented. |
| Implemented - test pending | Implementation exists; test evidence not yet recorded. |
| Verified - digital | Demonstrated in the digital prototype with recorded evidence. |
| Verified - inspection | Demonstrated by documentation or design review. |
| Verified - physical | Demonstrated on physical hardware (**not achievable in the digital prototype**). |

## 6. Coverage checks

| Check | Result |
| --- | --- |
| Every requirement has an architecture element | Pass |
| Every requirement has a future implementation module | Pass |
| Every requirement has a future test reference | Pass |
| No requirement ID is duplicated | Pass |
| No invented file names for non-existent code | Pass |
| No requirement claims physical validation | Pass |

## 7. Related documents

- [02_product_requirements.md](02_product_requirements.md)
- [01_system_architecture.md](01_system_architecture.md)
- [08_testing_strategy.md](08_testing_strategy.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
