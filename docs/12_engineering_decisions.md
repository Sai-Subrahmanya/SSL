# 12 - Engineering Decision Log

## 1. Document purpose

This document is the **engineering decision log** for Smart Street Light V1.

It records decisions that have already been established, so that future work
has a stable baseline and so that any later change is visible as a change
rather than as a silent drift.

Only decisions established in the project direction are recorded here. No
additional engineering decisions have been invented.

---

## 2. Record structure

Each decision contains:

| Field | Meaning |
| --- | --- |
| Decision ID | Permanent identifier (`D-NNN`). |
| Date | Date the decision was established. |
| Decision | What was decided. |
| Reason | Why it was decided. |
| Alternatives | What was not chosen. |
| Consequences | What follows from the decision. |
| Status | Current standing of the decision. |

---

## 3. Status definitions

| Status | Meaning |
| --- | --- |
| `Established` | Decided and in force for V1. |
| `Proposed` | Recorded for review; not yet in force. |
| `Superseded` | Replaced by a later decision (record retained). |

---

## 4. Decision log

### D-001 - Product boundary

| Field | Value |
| --- | --- |
| Decision ID | D-001 |
| Date | 2026-09-25 |
| Decision | Smart Street Light V1 is a smart street-light **monitoring and control system** interfacing with an external, existing street-light/luminaire. It is not initially a complete luminaire. |
| Reason | Keeps the V1 scope achievable and reviewable; the luminaire remains a separate product concern. |
| Alternatives | Delivering a complete luminaire in V1. |
| Consequences | Lamp, driver, optics and enclosure are out of product scope; hardware validation of those items is out of scope. |
| Status | `Established` |

---

### D-002 - Mandatory engineering sequence

| Field | Value |
| --- | --- |
| Decision ID | D-002 |
| Date | 2026-09-25 |
| Decision | Development follows `REQUIREMENT -> ARCHITECTURE -> DESIGN -> IMPLEMENTATION -> TEST -> AUDIT -> VALIDATION`. Code-first development with retrofitted requirements is prohibited. |
| Reason | Traceability and reviewability; prevents undocumented behaviour. |
| Alternatives | Code-first prototyping with requirements derived afterwards. |
| Consequences | Every implementation element must be traceable to a `PR-*` requirement; traceability must be maintained continuously. |
| Status | `Established` |

---

### D-003 - Layered system architecture

| Field | Value |
| --- | --- |
| Decision ID | D-003 |
| Date | 2026-09-25 |
| Decision | The system is layered as Master Control Center -> Group Controller -> RS-485 bus -> Lamp Nodes. |
| Reason | Separates supervision, group coordination and field execution; supports scalability. |
| Alternatives | Flat architecture with direct MCC-to-node communication; fully distributed mesh. |
| Consequences | Aggregation and buffering responsibilities sit at the Group Controller; the MCC is a logical layer. |
| Status | `Established` |

---

### D-004 - Single RS-485 master

| Field | Value |
| --- | --- |
| Decision ID | D-004 |
| Date | 2026-09-25 |
| Decision | The Group Controller is the sole RS-485 master; lamp nodes are addressed nodes that transmit only in response to a request. |
| Reason | Deterministic, collision-free multi-drop communication. |
| Alternatives | Multi-master bus; token passing; wireless mesh. |
| Consequences | No arbitration logic is required; node-initiated reporting must be polled. |
| Status | `Established` |

---

### D-005 - One lamp node per physical lamp

| Field | Value |
| --- | --- |
| Decision ID | D-005 |
| Date | 2026-09-25 |
| Decision | One lamp node is associated with exactly one physical lamp. |
| Reason | Per-lamp identity, measurement and fault attribution are required. |
| Alternatives | Shared node for multiple lamps. |
| Consequences | Node count equals lamp count; per-lamp cost and per-lamp diagnostics. |
| Status | `Established` |

---

### D-006 - Initial group size of approximately 16 lamps

| Field | Value |
| --- | --- |
| Decision ID | D-006 |
| Date | 2026-09-25 |
| Decision | The initial target is approximately 16 lamp nodes per group, and the architecture must remain scalable. |
| Reason | Stated project target; balances bus loading against wiring practicality. |
| Alternatives | Smaller groups with more Group Controllers; much larger groups. |
| Consequences | Polling cycle time and bus loading budgets are set against this target; scalability is a requirement, not an option. |
| Status | `Established` |

---

### D-007 - Operating mode set and priority ordering

| Field | Value |
| --- | --- |
| Decision ID | D-007 |
| Date | 2026-09-25 |
| Decision | The operating modes are `AUTO_SENSOR`, `AUTO_SCHEDULE_SENSOR`, `FIXED_SCHEDULE`, `FORCE_ON`, `FORCE_OFF`, `RETURN_TO_AUTO`, resolved with priority: safety/hardware protection > authorized manual override > normal automatic mode > sensor/schedule logic. |
| Reason | Defines predictable behaviour when several control intents conflict. |
| Alternatives | Mode set without explicit priority resolution. |
| Consequences | Mode resolution logic must be deterministic and testable; documented as a behavioural requirement, not yet implemented. |
| Status | `Established` |

---

### D-008 - No automatic shutdown for non-protective conditions

| Field | Value |
| --- | --- |
| Decision ID | D-008 |
| Date | 2026-09-25 |
| Decision | The system shall not automatically switch a lamp OFF merely because power is unusually high, a fault is detected, or an alert is unacknowledged. Normal behaviour is to continue operation, monitor, log, notify and escalate. |
| Reason | Switching off public lighting on unconfirmed conditions creates safety hazards and destroys evidence. |
| Alternatives | Automatic shutdown on any detected fault. |
| Consequences | No automatic protective shutdown is specified for V1, because no protection condition has been defined. |
| Status | `Established` |

---

### D-009 - Multi-evidence expected-versus-actual diagnosis

| Field | Value |
| --- | --- |
| Decision ID | D-009 |
| Date | 2026-09-25 |
| Decision | Lamp health shall be diagnosed by combining command state, relay feedback, supply voltage, current, power, light level, sensor validity, communication state and controller state. Current alone shall not be used to classify lamp health. |
| Reason | A single measurement cannot distinguish lamp, supply, sensor and measurement faults. |
| Alternatives | Current-threshold-only diagnosis. |
| Consequences | Diagnostic rules are evidence-based and explicitly advisory rather than physical proof. |
| Status | `Established` |

---

### D-010 - Fault type vocabulary

| Field | Value |
| --- | --- |
| Decision ID | D-010 |
| Date | 2026-09-25 |
| Decision | Faults are classified as `LAMP_LOAD`, `UNDER_CURRENT`, `OVER_CURRENT`, `SUPPLY_VOLTAGE`, `LIGHT_SENSOR`, `COMMUNICATION`, `CONTROLLER`, `ENVIRONMENTAL`, `TAMPER`, `UNKNOWN`, `INSPECTION_REQUIRED`. |
| Reason | A controlled vocabulary is required for consistent reporting and repair workflow. |
| Alternatives | Free-text fault descriptions; a smaller category set. |
| Consequences | `UNKNOWN` and `INSPECTION_REQUIRED` exist so the system never invents an unsupported root cause. New types require a decision record. |
| Status | `Established` |

---

### D-011 - Fault lifecycle state machine

| Field | Value |
| --- | --- |
| Decision ID | D-011 |
| Date | 2026-09-25 |
| Decision | Faults follow `NORMAL -> SUSPECTED -> CONFIRMED -> NOTIFIED -> ACKNOWLEDGED -> UNDER_REPAIR -> VERIFYING -> CLOSED`. Failed verification returns the fault to an active fault state. Illegal transitions are rejected and recorded. |
| Reason | Makes fault handling auditable and prevents "resolved by silence". |
| Alternatives | Simple binary fault flag; free-form fault status. |
| Consequences | A full state machine with transition validation must be implemented and tested. |
| Status | `Established` |

---

### D-012 - Fault latching with configurable confirmation

| Field | Value |
| --- | --- |
| Decision ID | D-012 |
| Date | 2026-09-25 |
| Decision | Fault confirmation uses a configurable observation count within a configurable time window, with hysteresis where appropriate, so that threshold oscillation does not generate independent alerts on every crossing. |
| Reason | Prevents alert storms from oscillating measurements. |
| Alternatives | Instant confirmation on first threshold crossing. |
| Consequences | Parameters are configuration, never hardcoded; confirmation behaviour must be tested with an oscillation scenario. |
| Status | `Established` |

---

### D-013 - Acknowledgement, reminder and escalation

| Field | Value |
| --- | --- |
| Decision ID | D-013 |
| Date | 2026-09-25 |
| Decision | Fault notifications may require acknowledgement, with configurable reminder interval, escalation timeout and escalation destination. Failure to acknowledge shall not switch the lamp OFF. |
| Reason | Guarantees fault visibility without creating a safety hazard. |
| Alternatives | Auto-closing unacknowledged faults; automatic shutdown on missed acknowledgement. |
| Consequences | Notification and escalation state must be tracked on the fault record. |
| Status | `Established` |

---

### D-014 - Offline operation and store-and-forward

| Field | Value |
| --- | --- |
| Decision ID | D-014 |
| Date | 2026-09-25 |
| Decision | Local operation continues without Internet, without the Master Control Center and without the Group Controller. Records are stored locally and delivered after recovery following `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM`, with no silent loss of records. |
| Reason | Street lighting is a safety-relevant public service that must not depend on connectivity. |
| Alternatives | Cloud-dependent operation; dropping records during outages. |
| Consequences | Local persistent storage, buffering and upload confirmation are mandatory. |
| Status | `Established` |

---

### D-015 - Data model defined at information level

| Field | Value |
| --- | --- |
| Decision ID | D-015 |
| Date | 2026-09-25 |
| Decision | The data model defines Measurement, Fault, Event, Command, Configuration and record-envelope information content. Serialization and physical layout are deferred. |
| Reason | Information content is stable across implementation choices; encodings are not. |
| Alternatives | Defining a wire format and storage layout at this stage. |
| Consequences | Phase 8 and Phase 9 may choose encodings without invalidating this baseline. |
| Status | `Established` |

---

### D-016 - Identity hierarchy

| Field | Value |
| --- | --- |
| Decision ID | D-016 |
| Date | 2026-09-25 |
| Decision | Identity follows `Product ID -> Site ID -> Group ID -> Lamp ID -> MCU Unique ID`, and must be deterministic and persistent. |
| Reason | Aggregation and audit require stable, unambiguous identity. |
| Alternatives | Bus address as the only identity. |
| Consequences | The bus address is group-scoped and is not a substitute for `lamp_id`. |
| Status | `Established` |

---

### D-017 - Command success requires verified actual state

| Field | Value |
| --- | --- |
| Decision ID | D-017 |
| Date | 2026-09-25 |
| Decision | A command is not successful merely because it was received. The lifecycle is `COMMAND_SENT -> RECEIVED -> EXECUTED -> ACKNOWLEDGED -> ACTUAL_STATE_VERIFIED`. |
| Reason | Receipt, execution, acknowledgement and verified state are distinct facts. |
| Alternatives | Treating receipt as success. |
| Consequences | Command status tracking and actual-state verification are required. |
| Status | `Established` |

---

### D-018 - RS-485 frame and initial message types

| Field | Value |
| --- | --- |
| Decision ID | D-018 |
| Date | 2026-09-25 |
| Decision | Frames carry start-of-frame, protocol version, source address, destination address, message type, payload length, payload, sequence number and CRC. The initial message type set is defined in the communication architecture document. The protocol is not implemented yet. |
| Reason | Establishes the protocol baseline before implementation. |
| Alternatives | Adopting an existing off-the-shelf protocol at this stage. |
| Consequences | Phase 9 implements framing, sequencing and CRC against this baseline. |
| Status | `Established` |

---

### D-019 - Communication state machine

| Field | Value |
| --- | --- |
| Decision ID | D-019 |
| Date | 2026-09-25 |
| Decision | Communication health follows `COMM_HEALTHY -> RETRY -> DEGRADED -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY`. |
| Reason | Makes degradation visible and testable instead of a binary online/offline flag. |
| Alternatives | Binary connected/disconnected status. |
| Consequences | Communication faults enter the normal fault lifecycle as `COMMUNICATION` faults. |
| Status | `Established` |

---

### D-020 - Storage split and retention defaults

| Field | Value |
| --- | --- |
| Decision ID | D-020 |
| Date | 2026-09-25 |
| Decision | MCU internal Flash holds firmware, configuration and calibration; external SPI NOR holds measurements, events, faults and buffered records. Records carry sequence number, timestamp, payload, CRC and commit marker. Automatic deletion is disabled by default and storage-full must be visible. |
| Reason | Record storage and configuration storage have different integrity and wear profiles; evidence loss by default is unacceptable. |
| Alternatives | Single unified storage area; automatic oldest-record deletion by default. |
| Consequences | Storage-full behaviour remains an open assumption (A-09) requiring an explicit decision. |
| Status | `Established` |

---

### D-021 - RTC-backed local time with validity indication

| Field | Value |
| --- | --- |
| Decision ID | D-021 |
| Date | 2026-09-25 |
| Decision | Each lamp node keeps local time from an RTC, timestamps records locally when unsynchronized, indicates time uncertainty, and re-synchronizes after communication recovery. |
| Reason | Offline records must be timestamped, and their uncertainty must be visible. |
| Alternatives | Discarding records that cannot be timestamped from network time. |
| Consequences | Record ordering relies on sequence numbers when time is uncertain. |
| Status | `Established` |

---

### D-022 - Configuration model with audit and validation

| Field | Value |
| --- | --- |
| Decision ID | D-022 |
| Date | 2026-09-25 |
| Decision | Configuration covers operating mode, thresholds, hysteresis, schedules, measurement and reporting intervals, fault confirmation count and window, communication retry count and timeout, acknowledgement reminder interval, escalation timeout and device identity. Changes are validated, persisted, versioned and auditable. |
| Reason | Separates requirement from tunable parameter and makes the control path auditable. |
| Alternatives | Compile-time configuration constants. |
| Consequences | No operational threshold may be hardcoded. |
| Status | `Established` |

---

### D-023 - Hardware components are candidates only

| Field | Value |
| --- | --- |
| Decision ID | D-023 |
| Date | 2026-09-25 |
| Decision | All referenced hardware components are engineering candidates, not production-frozen selections, and no software shall depend directly on them at this stage. |
| Reason | Manufacturing decisions are not frozen; partner review may change selections. |
| Alternatives | Freezing a bill of materials before digital validation. |
| Consequences | Hardware interfaces are modelled abstractly in the digital prototype. |
| Status | `Established` |

---

### D-024 - Digital prototype scope and claim discipline

| Field | Value |
| --- | --- |
| Decision ID | D-024 |
| Date | 2026-09-25 |
| Decision | The digital prototype validates logic, state machines, data flow and communication behaviour. It does not validate physical properties, and no certification claim is made. |
| Reason | Prevents digital validation from being mistaken for physical validation. |
| Alternatives | Presenting simulation results as physical validation evidence. |
| Consequences | Claim discipline rules are defined and apply to all derived material. |
| Status | `Established` |

---

### D-025 - International engineering scope

| Field | Value |
| --- | --- |
| Decision ID | D-025 |
| Date | 2026-09-25 |
| Decision | India and China are important initial target markets, international adaptability is desired, the controller input target is 90-305 VAC, the nominal V1 switched lamp output is 230 VAC, and the scope is single-phase line-to-neutral. |
| Reason | Focuses early engineering on the most relevant markets and supply conditions. |
| Alternatives | Multi-region or three-phase scope in V1. |
| Consequences | These are engineering design targets, not compliance statements. |
| Status | `Established` |

---

### D-026 - Partner review workflow

| Field | Value |
| --- | --- |
| Decision ID | D-026 |
| Date | 2026-09-25 |
| Decision | The workflow is digital engineering -> internal validation -> engineering package -> Minewing engineering review -> physical prototype -> physical validation -> iteration. |
| Reason | The project is not designed as though all manufacturing decisions are already frozen. |
| Alternatives | Treating manufacturing decisions as frozen before partner review. |
| Consequences | Requirements and architecture must remain adaptable to partner feedback. |
| Status | `Established` |

---

### D-027 - Documentation-first repository foundation

| Field | Value |
| --- | --- |
| Decision ID | D-027 |
| Date | 2026-09-25 |
| Decision | Phase 0 establishes repository structure, documentation, requirements, architectural baseline, assumptions, traceability structure and development rules, and deliberately introduces no simulation source code. |
| Reason | Establishes a controlled baseline before implementation begins. |
| Alternatives | Starting implementation immediately. |
| Consequences | Implementation begins in Phase 1 or later, only after review of this baseline. |
| Status | `Established` |

---

### D-028 - Requirement identifier scheme

| Field | Value |
| --- | --- |
| Decision ID | D-028 |
| Date | 2026-09-25 |
| Decision | Requirements use `PR-<CATEGORY>-<NNN>` with the categories `PR-LIGHT`, `PR-CONTROL`, `PR-MEASURE`, `PR-DIAG`, `PR-FAULT`, `PR-COMM`, `PR-STORAGE`, `PR-TIME`, `PR-CONFIG`, `PR-IDENTITY`, `PR-SECURITY`, `PR-SCALABILITY`, `PR-OFFLINE`. Identifiers are permanent and never reused. |
| Reason | Stable identifiers are required for traceability across the project lifetime. |
| Alternatives | Numbering without category prefixes. |
| Consequences | Withdrawn requirements are retained and marked, not deleted. |
| Status | `Established` |

---

### D-029 - Measurements are engineering monitoring values

| Field | Value |
| --- | --- |
| Decision ID | D-029 |
| Date | 2026-09-25 |
| Decision | Voltage, current, power, energy and light-level values are engineering monitoring values and shall not be described as billing-grade metering. |
| Reason | Metering claims imply calibration, traceability and legal metrology obligations outside the V1 boundary. |
| Alternatives | Presenting the measurement set as billing-grade metering. |
| Consequences | No accuracy class is claimed anywhere in the documentation. |
| Status | `Established` |

---

### D-030 - Master Control Center is a logical layer without a GUI in early phases

| Field | Value |
| --- | --- |
| Decision ID | D-030 |
| Date | 2026-09-25 |
| Decision | The Master Control Center is defined as a logical operator/control and data layer. No graphical user interface is built in the early phases. |
| Reason | Interface work would precede validated behaviour. |
| Alternatives | Building an operator dashboard first. |
| Consequences | The Master Control Center data layer is deferred to Phase 15. |
| Status | `Established` |

---

## 5. Summary

| Metric | Value |
| --- | --- |
| Total decisions recorded | 30 |
| `Established` | 30 |
| `Proposed` | 0 |
| `Superseded` | 0 |

No decisions beyond those established in the project direction have been
invented in this log.

---

## 6. Related documents

- [00_project_overview.md](00_project_overview.md)
- [01_system_architecture.md](01_system_architecture.md)
- [02_product_requirements.md](02_product_requirements.md)
- [11_assumptions.md](11_assumptions.md)
- [requirements_traceability.md](requirements_traceability.md)
