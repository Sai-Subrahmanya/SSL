# 02 - Product Requirements

## 1. Document purpose

This document defines the **structured engineering requirements** for Smart
Street Light V1.

It is the authoritative source of `PR-*` requirement identifiers. Every
future design element, implementation module and test must be traceable to
one or more requirements defined here, as recorded in
[requirements_traceability.md](requirements_traceability.md).

---

## 2. Conventions

### 2.1 Requirement identifier scheme

```text
PR-<CATEGORY>-<NNN>
```

| Category prefix | Subject area |
| --- | --- |
| `PR-LIGHT` | Lighting control behaviour |
| `PR-CONTROL` | Command handling, mode priority, restart behaviour |
| `PR-MEASURE` | Measurement handling |
| `PR-DIAG` | Expected-versus-actual diagnostics |
| `PR-FAULT` | Fault model and fault lifecycle |
| `PR-COMM` | Communication architecture and behaviour |
| `PR-STORAGE` | Storage, logging and retention |
| `PR-TIME` | Timekeeping and synchronization |
| `PR-CONFIG` | Configuration handling |
| `PR-IDENTITY` | Device identity |
| `PR-SECURITY` | Authorization, authentication, audit, tamper |
| `PR-SCALABILITY` | Scale and failure containment |
| `PR-OFFLINE` | Offline operation and store-and-forward |

Category prefixes above are fixed. Identifiers are permanent and are never
reused, including when requirements are withdrawn.

Identifiers are permanent. A withdrawn requirement is marked
`Withdrawn` and is never reused.

### 2.2 Priority definitions

| Priority | Meaning |
| --- | --- |
| MUST | Required for V1. Absence is a defect. |
| SHOULD | Required unless a documented, reviewed reason exists. |
| MAY | Optional / desirable capability. |

### 2.3 Status definitions

| Status | Meaning |
| --- | --- |
| Proposed | Written, awaiting review approval. |
| Approved | Accepted as the baseline requirement. |
| Implemented | Satisfied by implementation (recorded in traceability). |
| Verified | Satisfied and demonstrated by test evidence. |
| Withdrawn | No longer applicable; retained for traceability. |

The per-requirement `Status` line in section 4 uses the following compound
values, which are resolved against
[requirements_traceability.md](requirements_traceability.md):

| Status value | Meaning |
| --- | --- |
| `VERIFIED (digital prototype)` | Implemented in `src/sslv1/` and demonstrated by a deterministic test in `tests/`. **Digital prototype only** - no physical property is validated. |
| `IMPLEMENTED (digital prototype)` | Implemented in `src/sslv1/`; no named test yet. |
| `Proposed - not implemented` | No implementation exists yet. Reserved for physical-only requirements and work belonging to a later phase. |

`VERIFIED (digital prototype)` never means physical verification. Requirements
whose verification method is `Physical test` are never marked
`VERIFIED (digital prototype)`.

### 2.4 Verification method definitions

| Verification method | Meaning |
| --- | --- |
| Digital prototype test | Demonstrated in the digital prototype / simulation. |
| Integration test | Demonstrated across multiple simulated elements. |
| Inspection | Demonstrated by documentation or design review. |
| Physical test | Requires physical hardware - **not** achievable in the digital prototype. |

---

## 3. Requirement counts

| Category | Count |
| --- | --- |
| PR-LIGHT | 5 |
| PR-CONTROL | 7 |
| PR-MEASURE | 5 |
| PR-DIAG | 7 |
| PR-FAULT | 14 |
| PR-COMM | 10 |
| PR-STORAGE | 9 |
| PR-TIME | 5 |
| PR-CONFIG | 6 |
| PR-IDENTITY | 4 |
| PR-SECURITY | 6 |
| PR-SCALABILITY | 5 |
| PR-OFFLINE | 5 |
| **Total** | **88** |

---

## 4. Requirements

### 4.1 PR-LIGHT - Lighting control behaviour

#### PR-LIGHT-001 - Automatic sensor-based control (AUTO_SENSOR)

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 3)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
When the operating mode is `AUTO_SENSOR`, the lamp shall be switched ON when
the measured light level falls below the configured ON threshold, and
switched OFF when the measured light level rises above the configured OFF
threshold, subject to the configured hysteresis.

**Rationale.**
Light-level-based automatic operation is the core value of a smart street
light and is the default operating behaviour of the product.

**Requirement / design boundary.**
The *existence* of configurable ON/OFF thresholds and hysteresis is a
requirement. The *numeric values* of those thresholds are configuration, not
requirements, and must not be hardcoded as requirements.

---

#### PR-LIGHT-002 - Schedule-with-sensor control (AUTO_SCHEDULE_SENSOR)

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 3)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall support an operating mode (`AUTO_SCHEDULE_SENSOR`) in which
a configurable time window is combined with sensor-based control, such that
sensor-based control is active inside the window and the configured
out-of-window behaviour applies outside the window.

**Rationale.**
Municipal lighting is frequently constrained to fixed operating windows;
combining a window with sensing allows energy savings without losing control
over when the lamp is permitted to operate.

**Requirement / design boundary.**
The existence of the mode is a requirement. The default out-of-window
behaviour is an **assumption** (see
[11_assumptions.md](11_assumptions.md), assumption regarding out-of-window
behaviour) and must not be treated as a requirement until decided.

---

#### PR-LIGHT-003 - Fixed-schedule control (FIXED_SCHEDULE)

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 3)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall support an operating mode (`FIXED_SCHEDULE`) in which the
lamp is switched ON and OFF strictly according to configured times,
independent of the measured light level.

**Rationale.**
Fixed scheduling is required for installations where light sensing is
unreliable, disabled, or where regulation mandates fixed operating times.

---

#### PR-LIGHT-004 - Authorized operator override (FORCE_ON / FORCE_OFF)

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 3); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
An authorized operator shall be able to force a lamp ON (`FORCE_ON`) or OFF
(`FORCE_OFF`). A forced state shall remain in effect until it is explicitly
changed by a further authorized command or by `RETURN_TO_AUTO`.

**Rationale.**
Operational exceptions (events, maintenance, emergencies) require direct
operator control that overrides automatic logic.

**Requirement / design boundary.**
The capability and its persistence are requirements. The *authorization
mechanism* is covered by `PR-SECURITY-001` and `PR-SECURITY-002`.

---

#### PR-LIGHT-005 - Return to automatic mode (RETURN_TO_AUTO operator command)

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 3)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall provide a `RETURN_TO_AUTO` operator command that clears the
active forced override and returns control to the configured automatic mode.

**Rationale.**
Overrides must be explicitly and safely reversible so that temporary
intervention does not permanently disable automatic operation.

**Requirement / design boundary.**
`RETURN_TO_AUTO` is **not** a persistent operating mode. It is an operator
command/action. The persistent operating modes are `AUTO_SENSOR`,
`AUTO_SCHEDULE_SENSOR` and `FIXED_SCHEDULE`; `FORCE_ON` and `FORCE_OFF` are
temporary override states, not persistent modes (`PR-CONTROL-007`). The
system shall not model a persistent `RETURN_TO_AUTO` mode.

---

#### PR-CONTROL-007 - Separation of configured mode, active override and effective state

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 3)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall model three values separately: the **configured automatic
mode**, the **active override**, and the **effective operating state**. The
effective operating state shall be derived deterministically from the
configured mode and the active override.

**Rationale.**
Conflating configuration with temporary override makes it impossible to
distinguish "the operator changed the mode" from "the operator forced the
lamp", which corrupts the audit trail and the operator mental model.

**Requirement / design boundary.**
The three-value model is a requirement. The derivation rules are the control
model design (see `src/sslv1/control.py`).

Example:

```text
configured_mode = AUTO_SENSOR, active_override = NONE
    -> effective_mode = AUTO_SENSOR

configured_mode = AUTO_SENSOR, active_override = FORCE_ON
    -> effective_mode = FORCE_ON

RETURN_TO_AUTO: active_override = NONE
    -> effective_mode = configured_mode
```

---

### 4.2 PR-CONTROL - Command handling, mode priority, restart behaviour

#### PR-CONTROL-001 - Mode priority ordering

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 3)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall resolve conflicting control intents using the following
priority order, highest first:

```text
1. Safety / hardware protection
2. Authorized manual override
3. Normal automatic mode
4. Sensor / schedule logic
```

**Rationale.**
Deterministic priority resolution is required so that behaviour is
predictable and testable when several control sources are active.

---

#### PR-CONTROL-002 - Command lifecycle and success definition

- **Priority:** MUST
- **Verification method:** Integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
A command shall not be considered successful merely because it was received.
The command lifecycle shall be:

```text
COMMAND_SENT -> RECEIVED -> EXECUTED -> ACKNOWLEDGED -> ACTUAL_STATE_VERIFIED
```

and each stage shall be independently observable.

**Rationale.**
Receipt, execution, acknowledgement and verified actual state are distinct
engineering facts. Conflating them hides switching and measurement faults.

---

#### PR-CONTROL-003 - Duplicate command handling

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
A command carrying a command identity that has already been executed shall
not be executed a second time. The system shall report the duplicate
condition rather than silently re-executing.

**Rationale.**
Retries and repeated transmission are normal on a shared bus; without
duplicate suppression, a retried command can toggle a lamp twice.

---

#### PR-CONTROL-004 - Command authorization status

- **Priority:** MUST
- **Verification method:** Inspection (Phase 12); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Each command shall carry and report an authorization status, and commands
that are not authorized shall be rejected and recorded rather than executed.

**Rationale.**
Control of a public asset must be attributable and restricted to authorized
actors.

---

#### PR-CONTROL-005 - Safe state restoration after restart

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 2); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
After a watchdog reset or restart, a lamp node shall restore a defined
commanded state (the last known commanded state, or a configured
restart-default state), report the restart as an event, and resume normal
operation.

**Rationale.**
Uncontrolled post-reset behaviour can leave lamps in an unknown state and
makes field faults undiagnosable.

---

#### PR-CONTROL-006 - No automatic shutdown for non-protective conditions

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6); system validation (Phase 17)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall not automatically switch a lamp OFF merely because power is
unusually high, because a fault has been detected, or because an alert has
not been acknowledged. The system shall instead continue operation, monitor,
log, notify and escalate.

**Rationale.**
Switching off a public light in response to an unconfirmed condition creates
a safety hazard and destroys diagnostic evidence. Protective shutdown is a
separate, explicitly defined function.

**Requirement / design boundary.**
Automatic protective shutdown is reserved for genuine protection conditions
that will be explicitly defined later. **No protection condition is defined
in V1**, therefore no automatic shutdown behaviour is required by this
document.

---

### 4.3 PR-MEASURE - Measurement handling

#### PR-MEASURE-001 - Per-lamp measurement set

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 4)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Each lamp shall conceptually provide, as a minimum: voltage, current, power,
energy, light level, commanded state, switching feedback, actual state,
sensor status, communication status, controller status and operating mode.

**Rationale.**
A single measurement cannot describe lamp health; the full evidence set is
required for expected-versus-actual diagnosis.

**Requirement / design boundary.**
"Switching feedback" is an abstraction for the observed state of the
switching path. The system shall not assume a specific physical realisation
such as a relay auxiliary contact. The physical implementation is a
hardware-design decision (`PR-DIAG-001`, assumption A-18).

---

#### PR-MEASURE-002 - Configurable measurement and reporting intervals

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 4); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Measurement sampling interval and reporting interval shall be independently
configurable, and the currently effective values shall be reportable.

**Rationale.**
Sampling rate determines diagnostic responsiveness; reporting rate
determines bus and storage load. They must not be coupled.

---

#### PR-MEASURE-003 - Energy accumulation

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 4)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall accumulate energy per lamp monotonically over time, shall
survive restart, and shall reset only on an explicit authorized command.

**Rationale.**
Energy accumulation supports operational analysis of the installation.

**Requirement / design boundary.**
Energy accumulation is an **engineering monitoring value**. It is not
billing-grade metering and must not be presented as such.

---

#### PR-MEASURE-004 - Sensor validity reporting

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 4)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Every measurement shall be accompanied by a sensor validity/health status
indicating whether the underlying sensor input is currently trustworthy.

**Rationale.**
An invalid sensor must be distinguishable from a valid measurement that
indicates a fault, otherwise diagnostics will produce false lamp-failure
conclusions.

---

#### PR-MEASURE-005 - Monitoring values, not billing-grade metering

- **Priority:** MUST
- **Verification method:** Inspection (Phase 0 and Phase 18)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
All measurement values produced by the system shall be described and used as
engineering monitoring values. The system shall not be described as
providing billing-grade metering, and no accuracy class shall be claimed.

**Rationale.**
Claiming metering accuracy implies calibration, traceability and legal
metrology obligations that are outside the V1 boundary.

---

### 4.4 PR-DIAG - Expected-versus-actual diagnostics

#### PR-DIAG-001 - Multi-evidence diagnosis

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 5)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Lamp health shall not be classified using current alone. Diagnostic
evaluation shall combine, as applicable: command state, switching feedback,
supply voltage, current, power, light level, sensor validity, communication
state and controller state, where available.

**Rationale.**
Current alone cannot distinguish an open lamp, a partially failed driver, a
supply problem or a measurement error.

**Requirement / design boundary.**
"Switching feedback" is an abstraction. The diagnostic system shall not
depend on the assumption that the selected switching element provides an
auxiliary contact; the physical mechanism (isolated switched-output voltage
sensing, auxiliary contact, or another mechanism) remains a hardware-design
decision.

---

#### PR-DIAG-002 - Normal-operation diagnostic rule

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 5)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The combination `ON command + switching feedback ON + voltage present +
normal current + normal light level` shall be classified as normal
operation.

**Rationale.**
Defines the reference healthy signature against which deviations are
evaluated.

---

#### PR-DIAG-003 - Open-load / lamp-fault diagnostic rule

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 5)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The combination `ON command + switching feedback ON + voltage present +
near-zero current` shall be classified as a suspected open-load condition
(diagnostic classification `POSSIBLE_OPEN_LOAD`), not as a confirmed lamp
failure.

**Rationale.**
This is the most common field failure mode and must be detectable without
asserting physical proof.

---

#### PR-DIAG-004 - Unexpected-current diagnostic rule

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 5)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The combination `OFF command + switching feedback OFF + significant current`
shall be classified as a suspected unexpected-current condition
(`UNEXPECTED_CURRENT`), indicating a switching-path issue or an external
condition.

**Rationale.**
Current flowing while the lamp is commanded off indicates a switching,
wiring or external-supply problem that must be surfaced, not ignored.

---

#### PR-DIAG-005 - Supply-voltage diagnostic rule

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 5)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The combination `ON command + voltage absent` shall be classified as a
suspected supply/voltage issue.

**Rationale.**
Distinguishes an upstream supply problem from a lamp or node problem.

---

#### PR-DIAG-006 - Sensor-fault diagnostic rule

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 5)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
An abnormal light-level reading combined with an invalid sensor status shall
be classified as a sensor problem and shall not be classified as a confirmed
lamp failure.

**Rationale.**
Prevents invalid sensor data from generating false lamp-failure alerts.

---

#### PR-DIAG-007 - Diagnostic classification levels and evidential status

- **Priority:** MUST
- **Verification method:** Inspection (Phase 5); digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall maintain three distinct classification levels:
**measurement abnormality**, **suspected fault** and **confirmed fault**,
and shall treat diagnostic rules as advisory evidence rather than physical
proof.

**Rationale.**
Separating observation from conclusion is essential to avoid false alerts
and to keep the diagnostic model honest about what it can and cannot prove.

---

### 4.5 PR-FAULT - Fault model and fault lifecycle

#### PR-FAULT-001 - Fault type categories

- **Priority:** MUST
- **Verification method:** Inspection (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Faults shall be classified into the following categories:
`LAMP_LOAD`, `UNDER_CURRENT`, `OVER_CURRENT`, `SUPPLY_VOLTAGE`,
`LIGHT_SENSOR`, `COMMUNICATION`, `CONTROLLER`, `ENVIRONMENTAL`, `TAMPER`,
`UNKNOWN`, `INSPECTION_REQUIRED`.

**Rationale.**
A controlled vocabulary is required for consistent reporting, aggregation
and repair workflow.

**Requirement / design boundary.**
Fault categories are reporting buckets, not root causes. `LAMP_LOAD` and
`UNDER_CURRENT` in particular shall not be treated as independent root
causes; each fault carries both a fault category and a diagnostic
classification (`PR-FAULT-014`).

---

#### PR-FAULT-002 - Fault severity classification

- **Priority:** SHOULD
- **Verification method:** Inspection (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Each fault shall carry a severity classification that drives notification
and escalation behaviour.

**Rationale.**
Notification policy must be able to distinguish urgent from informational
conditions without hardcoding fault types into the notification logic.

**Requirement / design boundary.**
The existence of severity is a requirement. The severity scale and its
values are configuration/design and are not fixed by this document.

---

#### PR-FAULT-003 - Fault lifecycle state machine

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Faults shall follow the lifecycle:

```text
NORMAL -> SUSPECTED -> CONFIRMED -> ACKNOWLEDGED
       -> UNDER_REPAIR -> VERIFYING -> CLOSED
```

**Rationale.**
A single, explicit lifecycle makes fault handling auditable and prevents
ambiguous "resolved by silence" behaviour.

**Requirement / design boundary.**
`NOTIFIED` is **not** a fault lifecycle state. Notification and escalation
progress is tracked independently (`PR-FAULT-013`), so a fault may remain
`CONFIRMED` while its notification state moves `PENDING -> SENT ->
ACK_PENDING -> ESCALATED`.

---

#### PR-FAULT-004 - Rejection of illegal fault transitions

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Transitions that are not permitted by the fault lifecycle shall be rejected
and recorded as events rather than applied.

**Rationale.**
Illegal transitions corrupt the audit trail and can hide unresolved field
faults.

---

#### PR-FAULT-005 - Configurable fault confirmation

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
A fault shall be confirmed only when the supporting evidence persists for a
configurable observation count within a configurable time window.

**Rationale.**
Prevents transient conditions from generating confirmed faults and
unnecessary field dispatches.

---

#### PR-FAULT-006 - Fault latching and hysteresis

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall latch faults and apply hysteresis where appropriate, so
that oscillation around a threshold does not generate independent alerts on
every threshold crossing.

**Rationale.**
A measurement oscillating around a threshold (for example 39, 41, 39, 41)
must produce one latched fault condition, not a stream of new alerts.

---

#### PR-FAULT-007 - Fault notification

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
A confirmed fault shall be notified to the operator layer, and the
notification status shall be tracked on the fault record.

**Rationale.**
Faults that are detected but never surfaced provide no operational value.

---

#### PR-FAULT-008 - Acknowledgement, reminder and escalation

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Fault notifications shall support acknowledgement, with configurable
reminder interval, configurable escalation timeout and configurable
escalation destination.

**Rationale.**
Unacknowledged faults must not silently age out; escalation guarantees
visibility.

**Requirement / design boundary.**
Notification state is tracked separately from the fault lifecycle
(`PR-FAULT-013`). Notification failure or escalation does not alter the
fault lifecycle state.

---

#### PR-FAULT-009 - Unacknowledged alerts must not switch the lamp OFF

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6); system validation (Phase 17)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Failure to acknowledge a fault notification shall not, by itself, cause the
lamp to be switched OFF.

**Rationale.**
Turning public lighting off because an operator did not press
"acknowledge" is unacceptable and creates a safety hazard.

---

#### PR-FAULT-010 - Repair workflow

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall support an `UNDER_REPAIR` state that records that repair
activity is in progress for a confirmed fault.

**Rationale.**
Distinguishes "known and being worked on" from "known and ignored".

---

#### PR-FAULT-011 - Verification workflow and failed verification

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall support a `VERIFYING` state in which a repaired fault is
checked against the original evidence. Failed verification shall return the
fault to an active fault state rather than closing it.

**Rationale.**
Closure without verification allows recurring faults to disappear from the
system.

---

#### PR-FAULT-012 - Fault closure and failure containment

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall support fault closure with a recorded closure timestamp and
actor, and the presence of a fault on one lamp node shall not affect the
operation, measurement, reporting or fault handling of any other lamp node
or of the group.

**Rationale.**
Closure must be auditable, and a single faulty node must never cascade into
a group-level outage.

---

### 4.6 PR-COMM - Communication architecture and behaviour

#### PR-COMM-001 - RS-485 master/slave discipline

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The RS-485 bus shall be controlled by a single master (the Group
Controller). Lamp nodes shall transmit only in response to a request
addressed to them.

**Rationale.**
A single-master bus provides deterministic collision-free communication,
which is a prerequisite for reliable multi-drop behaviour.

---

#### PR-COMM-002 - Node addressing and group size

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Each lamp node shall have a unique address within its group, and the design
shall support an initial target of approximately 16 nodes per group.

**Rationale.**
Addressing is required for directed polling; the group size target drives
polling cycle time and bus loading.

---

#### PR-COMM-003 - Frame format

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Communication frames shall contain, as a minimum: start-of-frame, protocol
version, source address, destination address, message type, payload length,
payload, sequence number and CRC.

**Rationale.**
A self-describing, integrity-protected frame is required to detect
corruption, misdelivery and version mismatch.

---

#### PR-COMM-004 - Initial message type set

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The protocol shall support at least the following message types:
`STATUS_REQUEST`, `STATUS_RESPONSE`, `MEASUREMENT_REQUEST`,
`MEASUREMENT_RESPONSE`, `CONTROL_COMMAND`, `CONTROL_ACK`, `FAULT_REPORT`,
`EVENT_REPORT`, `CONFIG_READ`, `CONFIG_WRITE`, `CONFIG_ACK`, `TIME_SYNC`,
`TIME_ACK`, `IDENTIFY`, `IDENTIFY_ACK`, `HEARTBEAT`, `HEARTBEAT_ACK`.

**Rationale.**
Defines the minimum interaction set needed for polling, control, fault and
event reporting, configuration, time synchronization and identity.

---

#### PR-COMM-005 - Sequence numbering, duplicate and replay handling

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Frames shall carry a sequence number, and the receiver shall detect and
report duplicate or out-of-window sequence numbers rather than processing
them as new information.

**Rationale.**
Retry behaviour on a noisy bus makes duplicate delivery normal; duplicates
must be detectable without ambiguity.

---

#### PR-COMM-006 - CRC integrity verification

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Every frame shall be integrity-checked using its CRC, and frames failing the
check shall be discarded, counted and reported rather than acted upon.

**Rationale.**
Acting on a corrupted frame can issue a wrong lamp command.

---

#### PR-COMM-007 - Polling, timeout and retry policy

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 10); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The Group Controller shall poll nodes, shall detect non-response within a
configured timeout, shall retry within a configured retry count, and shall
track command acknowledgement status per command.

**Rationale.**
Distinguishes "slow" from "failed" and prevents indefinite waiting on an
unresponsive node.

---

#### PR-COMM-008 - Communication state machine

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 11)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Communication health shall be modelled by the state machine:

```text
COMM_HEALTHY -> RETRY -> DEGRADED -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY
```

**Rationale.**
Explicit communication states make degradation visible and testable instead
of collapsing everything into a binary "online/offline" flag.

---

#### PR-COMM-009 - Communication failure must not stop local operation

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 11); system validation (Phase 17)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Loss of communication with the Group Controller, the Master Control Center
or the Internet shall not stop local lighting operation. On recovery, the
system shall re-synchronize buffered records and re-establish time
synchronization.

**Rationale.**
Street lighting is a safety-relevant public service; it must not depend on
connectivity.

---

### 4.7 PR-STORAGE - Storage, logging and retention

#### PR-STORAGE-001 - Local persistent record storage

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall store measurements, events, faults and buffered records
locally and persistently, independent of upstream connectivity.

**Rationale.**
Local records are the only evidence available when communication is lost and
are required for the store-and-forward workflow.

---

#### PR-STORAGE-002 - Record structure

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Each stored record shall carry a sequence number, a timestamp, a payload, a
CRC and a commit marker.

**Rationale.**
These fields are the minimum required to order, validate and safely recover
records.

---

#### PR-STORAGE-003 - Power-loss safety

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
A record shall be considered valid only when its commit marker indicates
completion, and storage shall be recoverable to a consistent state after a
power loss occurring at any point.

**Rationale.**
Street-light nodes lose power routinely; partial records must never be
mistaken for valid data.

---

#### PR-STORAGE-004 - Corruption detection and handling

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Records that fail integrity checking shall be detected, reported and
excluded from upload; they shall never be silently accepted or silently
deleted.

**Rationale.**
Silent corruption handling either loses evidence or propagates bad data
upstream.

---

#### PR-STORAGE-005 - Retention: automatic deletion off by default

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Automatic deletion of stored records shall be disabled by default; any
deletion policy shall be explicitly configured and auditable.

**Rationale.**
Evidence loss by default is unacceptable in a system intended to support
maintenance and audit.

**Requirement / design boundary.**
The retention model shall distinguish: the pending upload queue, the
confirmed historical record, retention, and authorized deletion. Deletion
requires explicit authorization, produces a deletion audit event, and is
never silent. A numeric retention period is **not** specified by this
document (`PR-STORAGE-009`, assumption A-29).

---

#### PR-STORAGE-006 - Storage-full visibility

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
A storage-full condition shall be explicitly visible (reported as a
condition and as an event), and the behaviour on storage-full shall be
defined and explicit rather than implicit.

**Rationale.**
A full store that behaves unpredictably silently destroys the diagnostic
value of the system.

---

#### PR-STORAGE-007 - Separation of configuration/calibration storage

- **Priority:** SHOULD
- **Verification method:** Inspection (Phase 8); digital prototype test (Phase 12)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Firmware, configuration and calibration data shall be stored separately from
measurement, event and fault records.

**Rationale.**
Record storage is append-heavy and wear-sensitive; configuration storage has
different integrity and update requirements.

---

#### PR-STORAGE-008 - Store-and-forward buffering with upload confirmation

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Records that cannot be uploaded shall be buffered, and buffered records shall
leave the pending upload queue only after upload confirmation is received,
following the sequence `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD ->
CONFIRM`.

**Rationale.**
Prevents both data loss and duplicate upload of the same record.

**Requirement / design boundary.**
Leaving the pending upload queue is **not** deletion of the retained
historical record (`PR-STORAGE-009`).

---

### 4.8 PR-TIME - Timekeeping and synchronization

#### PR-TIME-001 - RTC-backed local timekeeping

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 2)
- **Status:** IMPLEMENTED (digital prototype)

**Requirement.**
Each lamp node shall maintain local time using a real-time clock that
continues to run while the node is otherwise unpowered or offline.

**Rationale.**
Local timestamps are required for offline records, schedules and fault
correlation.

**Requirement / design boundary.**
The digital prototype models logical RTC/time semantics only. Physical RTC
backup duration, leakage, temperature effects, oscillator accuracy and
power-interruption behaviour require physical validation and are **not**
established by the digital prototype (`PR-TIME-005`).

---

#### PR-TIME-002 - Offline timestamps with validity indication

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 7)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Records created while time synchronization is unavailable shall be
timestamped locally and shall carry an indication of time validity or
uncertainty.

**Rationale.**
An offline timestamp is better than no timestamp, but its uncertainty must
be visible to the consumer of the record.

---

#### PR-TIME-003 - Time synchronization

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 10)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The Group Controller shall distribute time to lamp nodes, and
synchronization shall be acknowledged (`TIME_SYNC` / `TIME_ACK`).

**Rationale.**
Consistent time across a group is required to correlate measurements,
events and faults.

---

#### PR-TIME-004 - Time-uncertainty handling and recovery

- **Priority:** SHOULD
- **Verification method:** Digital prototype test (Phase 11)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall track how long a node has been unsynchronized, shall
re-establish synchronization after communication recovery, and shall
preserve record ordering using sequence numbers when time is uncertain.

**Rationale.**
Clock drift during long offline periods must not silently corrupt the event
history.

### 4.9 PR-CONFIG - Configuration handling

#### PR-CONFIG-001 - Configuration parameter set

- **Priority:** MUST
- **Verification method:** Inspection (Phase 12)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall support configuration of, as a minimum: operating mode,
light thresholds, hysteresis, schedules, measurement interval, reporting
interval, fault confirmation count, fault confirmation window,
communication retry count, communication timeout, acknowledgement
requirement, acknowledgement reminder interval, escalation timeout,
escalation destination, notification retry count, measurement thresholds,
energy-reset authorization rule and device identity.

**Rationale.**
Defines the boundary between requirement and tunable parameter; without
these parameters, behaviour cannot be adapted per site.

**Requirement / design boundary.**
Every operational threshold shall come from configuration; none shall be
hardcoded in business logic (`PR-CONFIG-006`).

---

#### PR-CONFIG-002 - Configuration read and write over the bus

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 12)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Configuration shall be readable and writable over the RS-485 bus, and each
write shall be acknowledged (`CONFIG_WRITE` / `CONFIG_ACK`).

**Rationale.**
Remote configuration is required for scalable operation across many nodes.

---

#### PR-CONFIG-003 - Configuration validation

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 12)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Configuration values shall be validated on receipt, and invalid values shall
be rejected with a reported reason while the previous valid configuration
remains in effect.

**Rationale.**
Prevents a bad configuration push from disabling a group of lamps.

---

#### PR-CONFIG-004 - Configuration change auditability

- **Priority:** MUST
- **Verification method:** Inspection (Phase 12); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Every configuration change shall be recorded as an auditable event
including actor, timestamp, parameter, previous value and new value.

**Rationale.**
Configuration is a control path; unlogged changes make field faults
untraceable.

---

#### PR-CONFIG-005 - Configuration persistence and versioning

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 12)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Configuration shall persist across restart and shall carry a version
identifier that is reportable.

**Rationale.**
Version identification is required to reason about node behaviour during
diagnosis and firmware updates.

---

#### PR-CONFIG-006 - No hardcoded operational thresholds

- **Priority:** MUST
- **Verification method:** Inspection (Phase 6); digital prototype test (Phase 12)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Operational thresholds, fault confirmation count, fault confirmation window
and hysteresis shall not be hardcoded; they shall be configurable
parameters.

**Rationale.**
Hardcoded thresholds make the system unadaptable and make requirements
undocumented.

---

### 4.10 PR-IDENTITY - Device identity

#### PR-IDENTITY-001 - Identity hierarchy

- **Priority:** MUST
- **Verification method:** Inspection (Phase 1)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Identity shall follow the hierarchy:

```text
Product ID -> Site ID -> Group ID -> Lamp ID -> MCU Unique ID
```

**Rationale.**
A stable hierarchy is required to aggregate and report per site, per group
and per lamp without ambiguity.

---

#### PR-IDENTITY-002 - Deterministic and persistent identity

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 2)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Identity shall be deterministic and persistent: the same physical lamp node
shall report the same identity across restarts, and identity shall not
depend on volatile state.

**Rationale.**
Non-deterministic identity breaks event history, fault records and audit
trails.

---

#### PR-IDENTITY-003 - Bus address uniqueness

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Each lamp node shall have a unique bus address within its group, and address
conflicts shall be detectable and reportable.

**Rationale.**
Duplicate addresses corrupt the bus and produce misleading diagnostics.

---

#### PR-IDENTITY-004 - Identity query

- **Priority:** SHOULD
- **Verification method:** Digital prototype test (Phase 9)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall support an identity query (`IDENTIFY` / `IDENTIFY_ACK`)
that returns the node's identity.

**Rationale.**
Supports commissioning and verification that the intended node is at the
intended address.

---

### 4.11 PR-SECURITY - Authorization, authentication, audit, tamper

#### PR-SECURITY-001 - Operator authorization for overrides

- **Priority:** MUST
- **Verification method:** Integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Operator override commands (`FORCE_ON`, `FORCE_OFF`, `RETURN_TO_AUTO`) shall
be accepted only from an authorized operator.

**Rationale.**
Direct control of public lighting must be restricted to accountable actors.

---

#### PR-SECURITY-002 - Command authentication status

- **Priority:** MUST
- **Verification method:** Integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Each command shall carry an authentication status, and unauthenticated
commands shall be rejected and recorded.

**Rationale.**
Authentication status must be explicit so that rejected commands are
visible in the audit trail rather than silently dropped.

---

#### PR-SECURITY-003 - Audit trail

- **Priority:** MUST
- **Verification method:** Inspection (Phase 15); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall maintain an audit history of commands, configuration
changes, acknowledgements, repairs, verifications and closures, including
actor and timestamp.

**Rationale.**
Auditability is required for operational accountability and for later
engineering review.

---

#### PR-SECURITY-004 - Tamper detection

- **Priority:** SHOULD
- **Verification method:** Digital prototype test (Phase 14)
- **Status:** Proposed - not implemented

**Requirement.**
The system shall support a `TAMPER` fault category and shall report tamper
indications through the normal fault lifecycle.

**Rationale.**
Tamper indications must be surfaced through the same auditable path as other
faults.

---

#### PR-SECURITY-005 - Security validation boundary

- **Priority:** MUST
- **Verification method:** Inspection (Phase 0 and Phase 18)
- **Status:** Proposed - not implemented

**Requirement.**
The digital prototype shall not be used to claim validation of security,
cryptography, key management or RF security. Any such claim requires
separate engineering validation.

**Rationale.**
Simulated security is not security; conflating them would create a false
assurance claim.

---

### 4.12 PR-SCALABILITY - Scale and failure containment

#### PR-SCALABILITY-001 - Lamps per group

- **Priority:** MUST
- **Verification method:** Integration test (Phase 13)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall support an initial target of approximately 16 lamp nodes per
group, and shall scale to a larger node count without architectural change.

**Rationale.**
Group size is a primary cost and performance driver of the architecture.

---

#### PR-SCALABILITY-002 - Groups per site

- **Priority:** SHOULD
- **Verification method:** Integration test (Phase 13)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The architecture shall support multiple groups per site, aggregated at the
Master Control Center layer.

**Rationale.**
Real deployments span more lamps than a single group can serve.

---

#### PR-SCALABILITY-003 - Failure containment

- **Priority:** MUST
- **Verification method:** Integration test (Phase 13)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Failure or misbehaviour of a single lamp node shall not degrade or stop the
operation of other lamp nodes or of the group as a whole.

**Rationale.**
A shared bus creates a cascade risk that must be explicitly contained.

---

#### PR-SCALABILITY-004 - Architectural headroom

- **Priority:** SHOULD
- **Verification method:** Inspection (Phase 13)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Adding lamp nodes or groups shall not require redesign of the lamp node,
Group Controller or Master Control Center data model.

**Rationale.**
Scalability achieved by redesign is not scalability.

---

### 4.13 PR-OFFLINE - Offline operation and store-and-forward

#### PR-OFFLINE-001 - Local operation without Internet

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 11); system validation (Phase 17)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall continue full local operation when the Internet is
unavailable.

**Rationale.**
Connectivity loss is routine; lighting service must not depend on it.

---

#### PR-OFFLINE-002 - Local operation without the Master Control Center

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 11); system validation (Phase 17)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall continue full local operation when the Master Control
Center is unavailable.

**Rationale.**
The Master Control Center is a supervisory layer, not a control dependency.

---

#### PR-OFFLINE-003 - Local operation without the Group Controller

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 11); system validation (Phase 17)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
A lamp node shall continue to operate its lamp according to its configured
mode when the Group Controller is unavailable.

**Rationale.**
The lamp node is the only element guaranteed to be present at the lamp.

---

#### PR-OFFLINE-004 - Offline record buffering

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Records generated while upstream communication is unavailable shall be
buffered locally until they can be delivered.

**Rationale.**
Buffering is the mechanism that makes offline operation non-destructive.

---

#### PR-OFFLINE-005 - Post-recovery synchronization without silent loss

- **Priority:** MUST
- **Verification method:** Integration test (Phase 16); system validation (Phase 17)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
After communication recovery, buffered records shall be delivered following
`STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM`, and no record shall
be silently lost.

**Rationale.**
Silent record loss would invalidate the event history and the fault audit
trail.

---

---

#### PR-FAULT-013 - Notification state independent of fault lifecycle

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Notification and escalation progress shall be tracked in a notification
state that is independent of the fault lifecycle. The notification state
shall support at least: `NOT_REQUIRED`, `PENDING`, `SENT`, `ACK_PENDING`,
`REMINDER_DUE`, `ESCALATED`, `DELIVERY_FAILED`.

**Rationale.**
A fault may remain `CONFIRMED` for a long time while its notification state
changes repeatedly. Modelling notification as a fault lifecycle state forces
either premature fault-state changes or loss of notification history.

**Requirement / design boundary.**
`ESCALATED` is a notification state, never a fault lifecycle state. Changes
in notification state do not alter the fault lifecycle state.

---

#### PR-FAULT-014 - Fault category, diagnostic classification and root cause

- **Priority:** MUST
- **Verification method:** Inspection (Phase 5); digital prototype test (Phase 6)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall distinguish three concepts: the **fault category** (the
controlled-vocabulary bucket the fault is reported under), the **diagnostic
classification** (the evidence-based interpretation of the measurements), and
the **confirmed physical root cause** (established only by physical
inspection or repair). The system shall never assert a confirmed physical
root cause from a single abnormal measurement.

**Rationale.**
`LAMP_LOAD` and `UNDER_CURRENT` describe overlapping symptoms. Treating them
as independent root causes produces contradictory fault records and
misleading maintenance instructions.

Example:

```text
fault_category = UNDER_CURRENT
diagnostic_classification = POSSIBLE_OPEN_LOAD
```

---

#### PR-SECURITY-006 - Preliminary operator roles

- **Priority:** SHOULD
- **Verification method:** Digital prototype test (Phase 10); integration test (Phase 16)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The system shall define the preliminary roles `VIEWER`, `OPERATOR`,
`ENGINEER`, `ADMIN` and `OWNER`, distinguishing at least: read-only
monitoring, normal operational control and acknowledgement,
engineering/diagnostic and configuration actions, administrative actions,
and owner-level authority.

**Rationale.**
Authorization decisions require a role abstraction before the detailed
permission matrix is designed.

**Requirement / design boundary.**
The detailed permission matrix is a later security/design task and is not
specified by this document (assumption A-27).

---

#### PR-STORAGE-009 - Record lifecycle and retention policy

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 8)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Records shall follow the lifecycle
`CREATED -> STORED -> PENDING_UPLOAD -> UPLOADED -> CONFIRMED -> RETAINED`.
Upload confirmation shall not cause deletion of the retained historical
record; it shall only permit removal from the pending upload queue.
Retention shall be configurable with a hard minimum retention, and deletion
shall require explicit authorization, produce a deletion audit event, and
never be silent.

**Rationale.**
Conflating "uploaded" with "deletable" silently destroys the evidence that
the system exists to preserve.

**Requirement / design boundary.**
No numeric retention period or minimum retention value is specified by this
document (assumption A-29).

---

#### PR-SCALABILITY-005 - Group Controller local storage abstraction

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 10)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
The Group Controller shall provide an abstract local storage/buffer capable
of holding node data, communication events, configuration transactions,
synchronization state and data that could not be forwarded during an
upstream communication failure.

**Rationale.**
The Group Controller must survive upstream outages without losing the
aggregated history of its group.

**Requirement / design boundary.**
The physical memory device is deliberately **not** selected. The requirement
is on the abstract capability only (assumption A-28).

---

#### PR-COMM-010 - Command subtypes carried inside CONTROL_COMMAND

- **Priority:** MUST
- **Verification method:** Digital prototype test (Phase 9)
- **Status:** VERIFIED (digital prototype)

**Requirement.**
Command actions such as resetting accumulated energy shall be carried as
subtypes inside the `CONTROL_COMMAND` message type and shall not require new
RS-485 message types.

**Rationale.**
Adding a message type per action inflates the protocol and increases the
validation surface for no functional gain.

**Requirement / design boundary.**
`RESET_ENERGY` is a `CONTROL_COMMAND` subtype, not a message type and not a
separate protocol frame.

---

#### PR-TIME-005 - Physical RTC performance is not digitally validated

- **Priority:** MUST
- **Verification method:** Inspection (Phase 0 and Phase 18)
- **Status:** Proposed - not implemented

**Requirement.**
The digital prototype shall not be used to claim validation of physical RTC
performance, including backup retention duration, leakage, temperature
effects, oscillator accuracy and power-interruption behaviour.

**Rationale.**
These are physical properties of the RTC and its backup circuit that can only
be established by physical measurement.

**Requirement / design boundary.**
The digital prototype validates logical time semantics only (local clock,
timestamp generation, offline timestamps, synchronization state, validity and
restart behaviour).

## 5. Requirement versus design choice

The following items are **explicitly not requirements** in this document and
must not be treated as such:

| Item | Classification |
| --- | --- |
| Numeric light thresholds and hysteresis values | Configuration / design choice |
| Baud rate selection (9.6 vs 19.2 kbps) | Design choice, pending decision |
| Node count per group beyond "approximately 16" | Design target / assumption |
| Specific hardware components (MCU, metering IC, RTC, flash) | Engineering candidates |
| Specific fault severity values | Design choice |
| Default out-of-window behaviour of `AUTO_SCHEDULE_SENSOR` | Assumption |
| Restart-default lamp state | Assumption / configuration |
| Record layout and field widths | Design (Phase 8) |
| Cryptographic algorithms and key management | Out of scope for V1 documentation |

Requirements state **what** the system must do. Design choices state **how**
it will be done. Mixing the two is prohibited by the project engineering
principle.

---

## 6. Requirements that cannot be verified digitally

The following requirements are verified by **inspection** or by physical
test and are not claimed as validated by the digital prototype:

| Requirement | Reason |
| --- | --- |
| `PR-MEASURE-005` | Documentation-level constraint on claims |
| `PR-SECURITY-005` | Documentation-level constraint on claims |
| `PR-CONTROL-005` | Physical restart behaviour is modelled, not measured |
| `PR-STORAGE-003` | Power-loss safety is modelled, not physically tested |
| `PR-TIME-001` | RTC behaviour is modelled, not physically tested |

Modelled behaviour is **digital validation only**.

---

## 7. Review status

| Item | Status |
| --- | --- |
| Requirements drafted | Yes (88 requirements) |
| Independent review | REVIEW-000 recorded as *approved with required corrective actions* - see [review/README.md](review/README.md) |
| Traceability established | Yes - [requirements_traceability.md](requirements_traceability.md) |
| Implementation | Phase 1 domain model implemented and tested |

Requirement status values in this document remain `Proposed - not
implemented` at the individual requirement level; implementation and
verification state is recorded in the traceability matrix rather than
duplicated here.

---

## 8. Related documents

- [00_project_overview.md](00_project_overview.md)
- [01_system_architecture.md](01_system_architecture.md)
- [03_data_model.md](03_data_model.md)
- [04_fault_management.md](04_fault_management.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [07_configuration.md](07_configuration.md)
- [08_testing_strategy.md](08_testing_strategy.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
- [requirements_traceability.md](requirements_traceability.md)
