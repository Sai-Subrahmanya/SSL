# 12 - Engineering Decision Log

## 1. Document purpose

This document is the **engineering decision log** for Smart Street Light V1.

It records decisions that have already been established, so that future work
has a stable baseline and so that any later change is visible as a change
rather than as a silent drift.

Most entries are `Established` and in force. Where the engineering audit found
that a decision must be taken before the physical design can be frozen, a
`Proposed` entry records the direction for review; a `Proposed` entry is **not**
in force and describes nothing that is implemented. No decision has been
invented, and no open question has been recorded as decided.

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
| Decision | The persistent operating modes are the configured automatic modes `AUTO_SENSOR`, `AUTO_SCHEDULE_SENSOR` and `FIXED_SCHEDULE`. `FORCE_ON` and `FORCE_OFF` are **not** persistent operating modes: they are temporary manual override states held in `active_override`, alongside `NONE`. The effective operating mode is derived from the two. Priority for resolving the effective state: safety/hardware protection > authorized manual override > configured automatic mode > sensor/schedule logic. `RETURN_TO_AUTO` is an operator command that clears the active override; it is not a persistent mode and not an override state. |
| Reason | Defines predictable behaviour when several control intents conflict. |
| Alternatives | Mode set without explicit priority resolution. |
| Consequences | Mode resolution logic must be deterministic and testable. Implemented in `src/sslv1/control.py` and covered by `tests/test_control.py` and `tests/test_scenarios.py`. |
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
| Decision | Lamp health shall be diagnosed by combining command state, switching feedback, supply voltage, current, power, light level, sensor validity, communication state and controller state, where available. Current alone shall not be used to classify lamp health. "Switching feedback" is an abstraction; the physical mechanism is a hardware-design decision. |
| Reason | A single measurement cannot distinguish lamp, supply, sensor and measurement faults. |
| Alternatives | Current-threshold-only diagnosis. |
| Consequences | Diagnostic rules are evidence-based and explicitly advisory rather than physical proof. The diagnostic layer must not assume a relay auxiliary contact. |
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
| Decision | Faults follow `NORMAL -> SUSPECTED -> CONFIRMED -> ACKNOWLEDGED -> UNDER_REPAIR -> VERIFYING -> CLOSED`. Failed verification returns the fault to `UNDER_REPAIR` (an active fault state), never to `NORMAL` or `CLOSED`, and never silently. Illegal transitions are rejected and recorded. Notification and escalation progress is tracked in a separate notification state machine. |
| Reason | Makes fault handling auditable and prevents "resolved by silence". Returning to `UNDER_REPAIR` keeps the repair workflow open and re-arms the verification step, so the same fault cannot be closed twice without a fresh verification. Returning to `CONFIRMED` was rejected because it would discard the repair context and force the operator to re-acknowledge before continuing. |
| Alternatives | Simple binary fault flag; free-form fault status; returning failed verification to `CONFIRMED`. |
| Consequences | A full state machine with transition validation must be implemented and tested, plus an independent notification state machine. |
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
| Decision | Frames carry start-of-frame, protocol version, source address, destination address, message type, payload length, payload, sequence number and CRC. The initial message type set is defined in the communication architecture document. A digital implementation now exists; physical protocol details remain deferred. |
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
| Consequences | The Master Control Center data layer is deferred to Phase 15. Phase 15 implemented it as an in-memory logical model (`src/sslv1/mcc.py`) without a GUI. |
| Status | `Established` |

---

---

### D-031 - Configured mode, active override and effective state are modelled separately

| Field | Value |
| --- | --- |
| Decision ID | D-031 |
| Date | 2026-09-25 |
| Decision | The system models the configured automatic mode, the active override and the effective operating state as three separate values. The effective operating state is derived deterministically from the other two. |
| Reason | Conflating configuration with temporary override corrupts the audit trail and the operator mental model. |
| Alternatives | A single "current mode" value that is overwritten by overrides. |
| Consequences | `RETURN_TO_AUTO` is modelled as a command that clears the override, not as a persistent mode. Requires `PR-CONTROL-007`. |
| Status | `Established` |

---

### D-032 - "Switching feedback" replaces "relay feedback"

| Field | Value |
| --- | --- |
| Decision ID | D-032 |
| Date | 2026-09-25 |
| Decision | The domain model and diagnostics use the abstract term `switching_feedback` for the observed state of the switching path. No specific physical realisation is assumed. |
| Reason | Candidate physical mechanisms include isolated switched-output voltage sensing, a relay auxiliary contact, or another sensing mechanism. Tying the model to one of them would couple software to an undecided hardware choice. |
| Alternatives | Retaining the term "relay feedback" and assuming an auxiliary contact. |
| Consequences | The diagnostic engine consumes an abstract switching-state input. Assumption A-18 records that *some* feedback mechanism must exist. |
| Status | `Established` |

---

### D-033 - Notification state is independent of the fault lifecycle

| Field | Value |
| --- | --- |
| Decision ID | D-033 |
| Date | 2026-09-25 |
| Decision | Notification and escalation progress is tracked in an independent notification state machine (`NOT_REQUIRED`, `PENDING`, `SENT`, `ACK_PENDING`, `REMINDER_DUE`, `ESCALATED`, `DELIVERY_FAILED`). `NOTIFIED` and `ESCALATED` are not fault lifecycle states. |
| Reason | A fault can stay `CONFIRMED` for a long period while notification state changes repeatedly; modelling notification inside the fault lifecycle forces premature lifecycle changes or loss of notification history. |
| Alternatives | Adding `NOTIFIED` and `ESCALATED` as fault lifecycle states. |
| Consequences | Two state machines must be implemented and tested independently. Requires `PR-FAULT-013`. |
| Status | `Established` |

---

### D-034 - Fault category, diagnostic classification and root cause are distinct

| Field | Value |
| --- | --- |
| Decision ID | D-034 |
| Date | 2026-09-25 |
| Decision | Faults carry both a fault category (reporting bucket) and a diagnostic classification (evidence-based interpretation). Neither is a confirmed physical root cause. |
| Reason | `LAMP_LOAD` and `UNDER_CURRENT` describe overlapping symptoms; treating them as independent root causes produces contradictory fault records. |
| Alternatives | Treating each fault category as a distinct root cause. |
| Consequences | The diagnostic engine emits category + classification + evidence + confidence. Requires `PR-FAULT-014`. |
| Status | `Established` |

---

### D-035 - Record lifecycle and retention model

| Field | Value |
| --- | --- |
| Decision ID | D-035 |
| Date | 2026-09-25 |
| Decision | Records follow `CREATED -> STORED -> PENDING_UPLOAD -> UPLOADED -> CONFIRMED -> RETAINED`. Upload confirmation permits removal from the pending upload queue only; it never deletes the retained historical record. Deletion requires explicit authorization, produces a deletion audit event and is never silent. A hard minimum retention applies. |
| Reason | Conflating "uploaded" with "deletable" silently destroys the evidence the system exists to preserve. |
| Alternatives | Deleting records on upload confirmation. |
| Consequences | No numeric retention period is committed; the value remains an open assumption (A-29). Requires `PR-STORAGE-009`. |
| Status | `Established` |

---

### D-036 - Preliminary operator roles

| Field | Value |
| --- | --- |
| Decision ID | D-036 |
| Date | 2026-09-25 |
| Decision | Preliminary roles are `VIEWER`, `OPERATOR`, `ENGINEER`, `ADMIN` and `OWNER`, distinguished conceptually rather than by a detailed permission matrix. |
| Reason | Authorization decisions need a role abstraction now; a full permission matrix would be speculative before the security design. |
| Alternatives | Defining a full permission matrix immediately. |
| Consequences | Detailed permission mapping is deferred to the security design phase (assumption A-27). Requires `PR-SECURITY-006`. |
| Status | `Established` |

---

### D-037 - Group Controller local storage is an abstract capability

| Field | Value |
| --- | --- |
| Decision ID | D-037 |
| Date | 2026-09-25 |
| Decision | The Group Controller's local storage/buffer is modelled as an abstract capability; no physical memory device is selected. |
| Reason | Selecting a device now would prematurely constrain the hardware architecture phase. |
| Alternatives | Committing to a specific external memory part for the Group Controller. |
| Consequences | The abstraction is implemented and tested without a physical medium (assumption A-28). Requires `PR-SCALABILITY-005`. |
| Status | `Established` |

---

### D-038 - RESET_ENERGY is a CONTROL_COMMAND subtype

| Field | Value |
| --- | --- |
| Decision ID | D-038 |
| Date | 2026-09-25 |
| Decision | Resetting accumulated energy is carried as a subtype inside the `CONTROL_COMMAND` message type; no new RS-485 message type is introduced. |
| Reason | Adding a message type per action inflates the protocol and increases the validation surface for no functional gain. |
| Alternatives | Introducing a dedicated `RESET_ENERGY` message type. |
| Consequences | The message type set remains as originally defined. Requires `PR-COMM-010`. |
| Status | `Established` |

---

### D-039 - Physical RTC performance is outside digital validation

| Field | Value |
| --- | --- |
| Decision ID | D-039 |
| Date | 2026-09-25 |
| Decision | The digital prototype validates logical time semantics only. Physical RTC backup duration, leakage, temperature effects, oscillator accuracy and power-interruption behaviour are excluded from digital claims. |
| Reason | These are physical properties of the RTC and its backup circuit that require physical measurement. |
| Alternatives | Implying that simulated timekeeping validates the physical RTC. |
| Consequences | Assumption A-26 records the open physical question. Requires `PR-TIME-005`. |
| Status | `Established` |

---

### D-040 - Phase 1 domain model implemented in Python

| Field | Value |
| --- | --- |
| Decision ID | D-040 |
| Date | 2026-09-25 |
| Decision | The Phase 1 core domain model is implemented in Python under `src/sslv1/`, with tests under `tests/`, using only the standard library for runtime code and pytest as the test runner. |
| Reason | Zero cost, freely available tooling; the domain layer must remain hardware-independent and unit-testable. |
| Alternatives | Implementing the domain model directly against STM32 firmware tooling. |
| Consequences | The domain layer can later be reused behind a hardware abstraction layer without rewriting core logic. No runtime dependency on any hardware library. |
| Status | `Established` |

---

### D-041 - Master Control Center is a consumer of existing components

| Field | Value |
| --- | --- |
| Decision ID | D-041 |
| Date | 2026-10-04 |
| Decision | The Phase 15 Master Control Center is an in-memory aggregation and orchestration layer over the existing LampNode, GroupController, AuthorizationService, CommandService and record store. It holds no lamp control, fault lifecycle, event log, storage or permission rules of its own; it reads the existing state and routes operator commands through the existing authorized command path with the original actor identity. |
| Reason | A second implementation would create two sources of truth for status, faults, audits and authorization, which contradicts D-030 (logical layer) and the single-lifecycle requirements. |
| Alternatives | Giving the MCC its own control model, fault engine, event log and permission table. |
| Consequences | Status, faults, events and commands are only ever read from or written to the existing components; aggregation is deterministic and derived. The MCC keeps no persistence (see 03_data_model.md) and no GUI (D-030). Production multi-group deployment, persistence and scale validation remain outside the digital prototype. |
| Status | `Established` |

---

### D-042 - Group Controller restart re-initializes transient state only

| Field | Value |
| --- | --- |
| Decision ID | D-042 |
| Date | 2026-10-04 |
| Decision | A Group Controller restart keeps identity, configuration, registrations, the per-link replay window and the retained record store (including the pending upload queue). It clears state a restarted device cannot have: queued inbound frames, pending requests and their deadlines, volatile per-node views (last measurement, last status, last acknowledgement payloads, awaiting-response flags) and the evidence of a verified time synchronization. In-flight command transactions end `FAILED`. The restart is audited as `NODE_RESTARTED`/`WARNING` carrying `nodes`, `cleared_requests` and `failed_commands`. |
| Reason | A restarted device has no requests in flight, so presenting a command as `ACKNOWLEDGED` and still awaiting evidence would be a false claim about a dead transaction. Conversely, discarding the retained store or the replay window would lose evidence and weaken replay detection - a restart must not make the system *less* safe. |
| Alternatives | Reset everything (loses buffered evidence and breaks store-and-forward). Keep everything (presents pre-restart volatile data as current, and leaves dead transactions pending forever). |
| Consequences | Restart behavior is deterministic and asserted by tests (`test_controller_restart_drops_transient_state_and_keeps_persistence`); the MCC shows `UNKNOWN` for healthy-comm lamps until a fresh poll, and `DEGRADED`/`UNAVAILABLE` where the link itself is unhealthy. This is digital object re-initialization: no flash retention, brown-out or MCU power-loss behavior is claimed (`docs/09`). |
| Status | `Established` (implemented in Phase 16, recorded by the Phase 17 audit) |

---

### D-043 - MCC upstream record intake semantics

| Field | Value |
| --- | --- |
| Decision ID | D-043 |
| Date | 2026-10-04 |
| Decision | The Master Control Center accepts an uploaded record only when it is valid, attributable to that group's controller, and consistent with the scope the record itself declares (`site_id`, `group_id`, and any `lamp_id` must match the delivering group). A record that was already received is answered `True` - the far end has it - but counted as a duplicate and stored once. A record it cannot attribute is refused (`False`) and stays pending at the sender. Received records are kept in arrival order, unchanged, and the MCC keeps no second record format. |
| Reason | The sender's confirmation semantics are "the far end has it", so a re-sent record after a lost confirmation must not be reported as a failure; but a second copy must not corrupt or duplicate history either. And because group identities are unique only inside a site, a mis-delivered record must be refused rather than filed under the wrong site, group or lamp. |
| Alternatives | Store every delivery (duplicates corrupt history). Refuse duplicates as failures (a lost confirmation would strand a delivered record). Trust the payload's own identity without the delivering link (cross-site contamination). |
| Consequences | The intake is an append log in arrival order plus a duplicate counter; the MCC still owns no storage engine, no lifecycle and no second source of truth (`D-041`), and record identity is `(site, group, record type, sequence number)`. |
| Status | `Established` (implemented in Phase 16, recorded by the Phase 17 audit) |

---

### D-044 - Fault-set reporting contract for the physical prototype

| Field | Value |
| --- | --- |
| Decision ID | D-044 |
| Date | 2026-10-04 |
| Decision | The reporting contract between the Group Controller and the operator layer shall, for the physical prototype, carry the lamp's active fault **set** (bounded) - every active fault identity with its lifecycle state and per-fault open/close transitions - instead of a single active-fault snapshot. |
| Reason | The data model allows a lamp to hold concurrent faults (`docs/03`), but the current `FAULT_REPORT` pull carries one snapshot (`docs/05` section 5). The consequence is demonstrable: with two confirmed faults on one lamp only one is propagated, and a fault closed while another is being reported is never recorded as cleared at the operator layer (`PR-FAULT-007` is PARTIAL; pinned by `tests/test_integration.py::test_concurrent_confirmed_faults_are_bounded_by_the_single_fault_report_pull`). A monitoring system that withholds a second fault on the same lamp, or keeps listing a closed fault as active, is not an acceptable physical baseline. |
| Alternatives | Keep the single snapshot and accept the limitation in V1 (cheapest, but loses concurrent-fault visibility and can leave a stale active fault listed). Report only the highest-severity fault plus an "additional faults exist" count (bounded payload, but identities stay hidden). Report the full bounded active set with per-fault transitions (chosen direction). |
| Consequences | The report payload and its acknowledgement grow with the active-fault count and therefore need a bound and an encoding; the Group Controller and the operator layer must apply per-fault open/close transitions instead of a single snapshot. The digital model keeps its current snapshot behaviour until that revision exists, so `PR-FAULT-007` remains `PARTIAL` and this entry remains `Proposed`; no code changed with this entry. |
| Status | `Proposed` (direction for the physical-prototype wire contract; not implemented, not in force) |

---

## 5. Summary

| Metric | Value |
| --- | --- |
| Total decisions recorded | 44 |
| `Established` | 43 |
| `Proposed` | 1 |
| `Superseded` | 0 |

No decisions beyond those established in the project direction have been
invented in this log. Decisions D-031 to D-039 were introduced by review
finding REVIEW-000 and are recorded in the review record; D-040 and D-041 were
added by the Phase 14 and Phase 15 implementations respectively; D-042 and
D-043 record the Phase 16 restart and record-intake decisions, which the
Phase 17 audit found implemented but not yet in this log. D-044 was added by
the Phase 18 engineering audit as a `Proposed` direction for the
physical-prototype fault-reporting contract; it is deliberately not implemented
in the digital model.

---

## 6. Related documents

- [00_project_overview.md](00_project_overview.md)
- [01_system_architecture.md](01_system_architecture.md)
- [02_product_requirements.md](02_product_requirements.md)
- [10_hardware_reference.md](10_hardware_reference.md)
- [11_assumptions.md](11_assumptions.md)
- [15_engineering_audit.md](15_engineering_audit.md)
- [requirements_traceability.md](requirements_traceability.md)

## Implementation reconciliation (2026-09-26)

The earlier decisions remain the product-direction baseline; no open hardware,
storage-full, numeric-retention or production-security decision is closed here.
The corrective implementation follows D-017 (distinct command stages), D-031
(single configured mode plus override), D-033 (independent notification), D-035
(retention versus confirmation), D-036 (preliminary roles), D-037 (abstract GC
buffer), D-038 (RESET_ENERGY subtype) and D-039 (logical-only time).

Protocol revision 2, its strict binary metadata, symmetric numeric hysteresis
margin and version-zero startup convention are explicit **digital implementation
conventions** documented in 05/07, not new claims of approved hardware design,
production authentication, site thresholds or numeric retention. They require
engineering review before any firmware/wire compatibility baseline is frozen.
