# Requirements

## 1. Purpose

This document is the requirement set for Smart Street Light V1 and the status
of each requirement against the implementation in `src/sslv1/`. Requirements
describe **what the system must do**; the values chosen for thresholds,
schedules and intervals are configuration, not requirements, and are listed in
[architecture.md](architecture.md) section 9.

## 2. Conventions

| Term | Meaning |
| --- | --- |
| `MUST` | Mandatory for V1. |
| `SHOULD` | Expected for V1; a deviation needs a stated reason. |
| Requirement identifier | `PR-<CATEGORY>-<NNN>`. Identifiers are stable; the identifier scheme is used by the code and the tests. |

Implementation status:

| Status | Meaning |
| --- | --- |
| **Implemented** | The behaviour exists in the model and is covered by the cited tests. For requirements that mix modelled logic with a physical property, the status covers the modelled part only - see section 4. |
| **Partial** | Implemented for a documented subset; the remaining part is explicitly not implemented. Each case is described in section 3. |
| **Planned** | Not implemented. The requirement is a physical or security property that this repository cannot implement or verify. |

Current summary: **77 implemented, 8 partial, 3 planned** (88 requirements).

## 3. Requirement set

Each row cites the test modules that cover the requirement. All cited tests are
in `tests/` and pass; see [validation.md](validation.md) for how to run them.

### Lighting control

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-LIGHT-001` | **Automatic sensor-based control (AUTO_SENSOR).** When the operating mode is `AUTO_SENSOR`, the lamp shall be switched ON when the measured light level falls below the configured ON threshold, and switched OFF when the measured light level rises above the configured OFF threshold, subject to the configured hysteresis. | MUST | Implemented | `test_control.py`, `test_scenarios.py` |
| `PR-LIGHT-002` | **Schedule-with-sensor control (AUTO_SCHEDULE_SENSOR).** The system shall support an operating mode (`AUTO_SCHEDULE_SENSOR`) in which a configurable time window is combined with sensor-based control, such that sensor-based control is active inside the window and the configured out-of-window behaviour applies outside the window. | MUST | Implemented | `test_control.py`, `test_scenarios.py` |
| `PR-LIGHT-003` | **Fixed-schedule control (FIXED_SCHEDULE).** The system shall support an operating mode (`FIXED_SCHEDULE`) in which the lamp is switched ON and OFF strictly according to configured times, independent of the measured light level. | MUST | Implemented | `test_control.py`, `test_scenarios.py` |
| `PR-LIGHT-004` | **Authorized operator override (FORCE_ON / FORCE_OFF).** An authorized operator shall be able to force a lamp ON (`FORCE_ON`) or OFF (`FORCE_OFF`). A forced state shall remain in effect until it is explicitly changed by a further authorized command or by `RETURN_TO_AUTO`. | MUST | Implemented | `test_control.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-LIGHT-005` | **Return to automatic mode (RETURN_TO_AUTO operator command).** The system shall provide a `RETURN_TO_AUTO` operator command that clears the active forced override and returns control to the configured automatic mode. | MUST | Implemented | `test_control.py`, `test_scenarios.py` |

### Command handling and restart

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-CONTROL-007` | **Separation of configured mode, active override and effective state.** The system shall model three values separately: the **configured automatic mode**, the **active override**, and the **effective operating state**. The effective operating state shall be derived deterministically from the configured mode and the active override. | MUST | Implemented | `test_control.py`, `test_identity.py` |
| `PR-CONTROL-001` | **Mode priority ordering.** The system shall resolve conflicting control intents using the following priority order, highest first: `1. Safety / hardware protection 2. Authorized manual override 3. Normal automatic mode 4. Sensor / schedule logic` | MUST | Implemented | `test_control.py`, `test_scenarios.py` |
| `PR-CONTROL-002` | **Command lifecycle and success definition.** A command shall not be considered successful merely because it was received. The command lifecycle shall be: `COMMAND_CREATED -> RECEIVED -> EXECUTED -> ACKNOWLEDGED -> ACTUAL_STATE_VERIFIED` and each stage shall be independently observable. | MUST | Implemented | `test_command.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-CONTROL-003` | **Duplicate command handling.** A command carrying a command identity that has already been executed shall not be executed a second time. The system shall report the duplicate condition rather than silently re-executing. | MUST | Implemented | `test_command.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-CONTROL-004` | **Command authorization status.** Each command shall carry and report an authorization status, and commands that are not authorized shall be rejected and recorded rather than executed. | MUST | Implemented | `test_command.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-CONTROL-005` | **Safe state restoration after restart.** After a watchdog reset or restart, a lamp node shall restore a defined commanded state (the last known commanded state, or a configured restart-default state), report the restart as an event, and resume normal operation. | MUST | Implemented | `test_control.py`, `test_integration.py` |
| `PR-CONTROL-006` | **No automatic shutdown for non-protective conditions.** The system shall not automatically switch a lamp OFF merely because power is unusually high, because a fault has been detected, or because an alert has not been acknowledged. The system shall instead continue operation, monitor, log, notify and escalate. | MUST | Implemented | `test_control.py`, `test_scenarios.py`, `test_integration.py` |

### Measurement

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-MEASURE-001` | **Per-lamp measurement set.** Each lamp shall conceptually provide, as a minimum: voltage, current, power, energy, light level, commanded state, switching feedback, actual state, sensor status, communication status, controller status and operating mode. | MUST | Implemented | `test_measurement.py`, `test_scenarios.py` |
| `PR-MEASURE-002` | **Configurable measurement and reporting intervals.** Measurement sampling interval and reporting interval shall be independently configurable, and the currently effective values shall be reportable. | MUST | Implemented | `test_configuration.py`, `test_integration.py` |
| `PR-MEASURE-003` | **Energy accumulation.** The system shall accumulate energy per lamp monotonically over time, shall survive restart, and shall reset only on an explicit authorized command. | MUST | Implemented | `test_command.py`, `test_regressions.py`, `test_integration.py` |
| `PR-MEASURE-004` | **Sensor validity reporting.** Every measurement shall be accompanied by a sensor validity/health status indicating whether the underlying sensor input is currently trustworthy. | MUST | Implemented | `test_measurement.py` |
| `PR-MEASURE-005` | **Monitoring values, not billing-grade metering.** All measurement values produced by the system shall be described and used as engineering monitoring values. The system shall not be described as providing billing-grade metering, and no accuracy class shall be claimed. | MUST | Implemented | `test_scenarios.py` |

### Diagnostics

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-DIAG-001` | **Multi-evidence diagnosis.** Lamp health shall not be classified using current alone. Diagnostic evaluation shall combine, as applicable: command state, switching feedback, supply voltage, current, power, light level, sensor validity, communication state and controller state, where available. | MUST | Implemented | `test_diagnostics.py`, `test_scenarios.py` |
| `PR-DIAG-002` | **Normal-operation diagnostic rule.** The combination `ON command + switching feedback ON + voltage present + normal current + normal light level` shall be classified as normal operation. | MUST | Implemented | `test_diagnostics.py`, `test_scenarios.py` |
| `PR-DIAG-003` | **Open-load / lamp-fault diagnostic rule.** The combination `ON command + switching feedback ON + voltage present + near-zero current` shall be classified as a suspected open-load condition (diagnostic classification `POSSIBLE_OPEN_LOAD`), not as a confirmed lamp failure. | MUST | Implemented | `test_diagnostics.py`, `test_scenarios.py` |
| `PR-DIAG-004` | **Unexpected-current diagnostic rule.** The combination `OFF command + switching feedback OFF + significant current` shall be classified as a suspected unexpected-current condition (`UNEXPECTED_CURRENT`), indicating a switching-path issue or an external condition. | MUST | Implemented | `test_diagnostics.py`, `test_scenarios.py` |
| `PR-DIAG-005` | **Supply-voltage diagnostic rule.** The combination `ON command + voltage absent` shall be classified as a suspected supply/voltage issue. | MUST | Implemented | `test_diagnostics.py`, `test_scenarios.py` |
| `PR-DIAG-006` | **Sensor-fault diagnostic rule.** An abnormal light-level reading combined with an invalid sensor status shall be classified as a sensor problem and shall not be classified as a confirmed lamp failure. | MUST | Implemented | `test_diagnostics.py`, `test_scenarios.py` |
| `PR-DIAG-007` | **Diagnostic classification levels and evidential status.** The system shall maintain three distinct classification levels: | MUST | Implemented | `test_diagnostics.py`, `test_scenarios.py` |

### Fault model and lifecycle

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-FAULT-001` | **Fault type categories.** Faults shall be classified into the following categories: `LAMP_LOAD`, `UNDER_CURRENT`, `OVER_CURRENT`, `SUPPLY_VOLTAGE`, `LIGHT_SENSOR`, `COMMUNICATION`, `CONTROLLER`, `ENVIRONMENTAL`, `TAMPER`, `UNKNOWN`, `INSPECTION_REQUIRED`. | MUST | Implemented | `test_diagnostics.py` |
| `PR-FAULT-002` | **Fault severity classification.** Each fault shall carry a severity classification that drives notification and escalation behaviour. | SHOULD | Implemented | `test_scenarios.py` |
| `PR-FAULT-003` | **Fault lifecycle state machine.** Faults shall follow the lifecycle: `NORMAL -> SUSPECTED -> CONFIRMED -> ACKNOWLEDGED -> UNDER_REPAIR -> VERIFYING -> CLOSED` | MUST | Implemented | `test_fault.py`, `test_scenarios.py` |
| `PR-FAULT-004` | **Rejection of illegal fault transitions.** Transitions that are not permitted by the fault lifecycle shall be rejected and recorded as events rather than applied. | MUST | Implemented | `test_fault.py` |
| `PR-FAULT-005` | **Configurable fault confirmation.** A fault shall be confirmed only when the supporting evidence persists for a configurable observation count within a configurable time window. | MUST | Implemented | `test_fault.py`, `test_scenarios.py` |
| `PR-FAULT-006` | **Fault latching and hysteresis.** The system shall latch faults and apply hysteresis where appropriate, so that oscillation around a threshold does not generate independent alerts on every threshold crossing. | MUST | Implemented | `test_fault.py`, `test_scenarios.py` |
| `PR-FAULT-007` | **Fault notification.** A confirmed fault shall be notified to the operator layer, and the notification status shall be tracked on the fault record. | MUST | Partial | `test_fault.py`, `test_integration.py` |
| `PR-FAULT-008` | **Acknowledgement, reminder and escalation.** Fault notifications shall support acknowledgement, with configurable reminder interval, configurable escalation timeout and configurable escalation destination. | MUST | Implemented | `test_fault.py`, `test_integration.py` |
| `PR-FAULT-009` | **Unacknowledged alerts must not switch the lamp OFF.** Failure to acknowledge a fault notification shall not, by itself, cause the lamp to be switched OFF. | MUST | Implemented | `test_scenarios.py`, `test_integration.py` |
| `PR-FAULT-010` | **Repair workflow.** The system shall support an `UNDER_REPAIR` state that records that repair activity is in progress for a confirmed fault. | MUST | Implemented | `test_fault.py` |
| `PR-FAULT-011` | **Verification workflow and failed verification.** The system shall support a `VERIFYING` state in which a repaired fault is checked against the original evidence. Failed verification shall return the fault to an active fault state rather than closing it. | MUST | Partial | `test_fault.py`, `test_scenarios.py` |
| `PR-FAULT-012` | **Fault closure and failure containment.** The system shall support fault closure with a recorded closure timestamp and actor, and the presence of a fault on one lamp node shall not affect the operation, measurement, reporting or fault handling of any other lamp node or of the group. | MUST | Implemented | `test_fault.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-FAULT-013` | **Notification state independent of fault lifecycle.** Notification and escalation progress shall be tracked in a notification state that is independent of the fault lifecycle. The notification state shall support at least: `NOT_REQUIRED`, `PENDING`, `SENT`, `ACK_PENDING`, `REMINDER_DUE`, `ESCALATED`, `DELIVERY_FAILED`. | MUST | Implemented | `test_fault.py`, `test_scenarios.py` |
| `PR-FAULT-014` | **Fault category, diagnostic classification and root cause.** The system shall distinguish three concepts: the **fault category** (the controlled-vocabulary bucket the fault is reported under), the **diagnostic classification** (the evidence-based interpretation of the measurements), and the **confirmed physical root cause** (established only by physical inspection or repair). The system shall never assert a confirmed physical root cause from a single abnormal measurement. | MUST | Implemented | `test_diagnostics.py`, `test_scenarios.py` |

### Communication

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-COMM-001` | **RS-485 master/slave discipline.** The RS-485 bus shall be controlled by a single master (the Group Controller). Lamp nodes shall transmit only in response to a request addressed to them. | MUST | Implemented | `test_group_controller.py` |
| `PR-COMM-002` | **Node addressing and group size.** Each lamp node shall have a unique address within its group, and the design shall support an initial target of approximately 16 nodes per group. | MUST | Implemented | `test_group_controller.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-COMM-003` | **Frame format.** Communication frames shall contain, as a minimum: start-of-frame, protocol version, source address, destination address, message type, payload length, payload, sequence number and CRC. | MUST | Implemented | `test_comm.py` |
| `PR-COMM-004` | **Initial message type set.** The protocol shall support at least the following message types: `STATUS_REQUEST`, `STATUS_RESPONSE`, `MEASUREMENT_REQUEST`, `MEASUREMENT_RESPONSE`, `CONTROL_COMMAND`, `CONTROL_ACK`, `FAULT_REPORT`, `EVENT_REPORT`, `CONFIG_READ`, `CONFIG_WRITE`, `CONFIG_ACK`, `TIME_SYNC`, `TIME_ACK`, `IDENTIFY`, `IDENTIFY_ACK`, `HEARTBEAT`, `HEARTBEAT_ACK`. | MUST | Implemented | `test_comm.py` |
| `PR-COMM-005` | **Sequence numbering, duplicate and replay handling.** Frames shall carry a sequence number, and the receiver shall detect and report duplicate or out-of-window sequence numbers rather than processing them as new information. | MUST | Implemented | `test_group_controller.py` |
| `PR-COMM-006` | **CRC integrity verification.** Every frame shall be integrity-checked using its CRC, and frames failing the check shall be discarded, counted and reported rather than acted upon. | MUST | Implemented | `test_comm.py` |
| `PR-COMM-007` | **Polling, timeout and retry policy.** The Group Controller shall poll nodes, shall detect non-response within a configured timeout, shall retry within a configured retry count, and shall track command acknowledgement status per command. | MUST | Implemented | `test_group_controller.py`, `test_integration.py` |
| `PR-COMM-008` | **Communication state machine.** Communication health shall be modelled by the state machine: `COMM_HEALTHY -> RETRY -> DEGRADED -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY` | MUST | Partial | `test_comm.py`, `test_integration.py` |
| `PR-COMM-009` | **Communication failure must not stop local operation.** Loss of communication with the Group Controller, the Master Control Center or the Internet shall not stop local lighting operation. On recovery, the system shall re-synchronize buffered records and re-establish time synchronization. | MUST | Implemented | `test_group_controller.py`, `test_scenarios.py`, `test_integration.py` |
| `PR-COMM-010` | **Command subtypes carried inside CONTROL_COMMAND.** Command actions such as resetting accumulated energy shall be carried as subtypes inside the `CONTROL_COMMAND` message type and shall not require new RS-485 message types. | MUST | Implemented | `test_comm.py`, `test_command.py` |

### Storage, logging and retention

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-STORAGE-001` | **Local persistent record storage.** The system shall store measurements, events, faults and buffered records locally and persistently, independent of upstream connectivity. | MUST | Implemented | `test_group_controller.py`, `test_integration.py`, `test_scenarios.py`, `test_storage.py` |
| `PR-STORAGE-002` | **Record structure.** Each stored record shall carry a sequence number, a timestamp, a payload, a CRC and a commit marker. | MUST | Implemented | `test_storage.py` |
| `PR-STORAGE-003` | **Power-loss safety.** A record shall be considered valid only when its commit marker indicates completion, and storage shall be recoverable to a consistent state after a power loss occurring at any point. | MUST | Implemented | `test_scenarios.py`, `test_storage.py` |
| `PR-STORAGE-004` | **Corruption detection and handling.** Records that fail integrity checking shall be detected, reported and excluded from upload; they shall never be silently accepted or silently deleted. | MUST | Implemented | `test_storage.py` |
| `PR-STORAGE-005` | **Retention: automatic deletion off by default.** Automatic deletion of stored records shall be disabled by default; any deletion policy shall be explicitly configured and auditable. | MUST | Implemented | `test_storage.py` |
| `PR-STORAGE-006` | **Storage-full visibility.** A storage-full condition shall be explicitly visible (reported as a condition and as an event), and the behaviour on storage-full shall be defined and explicit rather than implicit. | MUST | Implemented | `test_scenarios.py`, `test_storage.py` |
| `PR-STORAGE-007` | **Separation of configuration/calibration storage.** Firmware, configuration and calibration data shall be stored separately from measurement, event and fault records. | SHOULD | Partial | `test_storage.py` |
| `PR-STORAGE-008` | **Store-and-forward buffering with upload confirmation.** Records that cannot be uploaded shall be buffered, and buffered records shall leave the pending upload queue only after upload confirmation is received, following the sequence `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM`. | MUST | Implemented | `test_group_controller.py`, `test_integration.py` |
| `PR-STORAGE-009` | **Record lifecycle and retention policy.** Records shall follow the lifecycle `CREATED -> STORED -> PENDING_UPLOAD -> UPLOADED -> CONFIRMED -> RETAINED`. Upload confirmation shall not cause deletion of the retained historical record; it shall only permit removal from the pending upload queue. Retention shall be configurable with a hard minimum retention, and deletion shall require explicit authorization, produce a deletion audit event, and never be silent. | MUST | Implemented | `test_scenarios.py`, `test_storage.py` |

### Timekeeping

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-TIME-001` | **RTC-backed local timekeeping.** Each lamp node shall maintain local time using a real-time clock that continues to run while the node is otherwise unpowered or offline. | MUST | Implemented | `test_group_controller.py`, `test_integration.py`, `test_time.py` |
| `PR-TIME-002` | **Offline timestamps with validity indication.** Records created while time synchronization is unavailable shall be timestamped locally and shall carry an indication of time validity or uncertainty. | MUST | Implemented | `test_group_controller.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-TIME-003` | **Time synchronization.** The Group Controller shall distribute time to lamp nodes, and synchronization shall be acknowledged (`TIME_SYNC` / `TIME_ACK`). | MUST | Implemented | `test_group_controller.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-TIME-004` | **Time-uncertainty handling and recovery.** The system shall track how long a node has been unsynchronized, shall re-establish synchronization after communication recovery, and shall preserve record ordering using sequence numbers when time is uncertain. | SHOULD | Implemented | `test_integration.py`, `test_time.py` |
| `PR-TIME-005` | **Physical RTC performance is not digitally validated.** The digital prototype shall not be used to claim validation of physical RTC performance, including backup retention duration, leakage, temperature effects, oscillator accuracy and power-interruption behaviour. | MUST | Planned | — |

### Configuration

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-CONFIG-001` | **Configuration parameter set.** The system shall support configuration of, as a minimum: operating mode, light thresholds, hysteresis, schedules, measurement interval, reporting interval, fault confirmation count, fault confirmation window, communication retry count, communication timeout, acknowledgement requirement, acknowledgement reminder interval, escalation timeout, escalation destination, notification retry count, measurement thresholds, energy-reset authorization rule and device identity. | MUST | Partial | `test_configuration.py`, `test_integration.py` |
| `PR-CONFIG-002` | **Configuration read and write over the bus.** Configuration shall be readable and writable over the RS-485 bus, and each write shall be acknowledged (`CONFIG_WRITE` / `CONFIG_ACK`). | MUST | Partial | `test_group_controller.py`, `test_integration.py` |
| `PR-CONFIG-003` | **Configuration validation.** Configuration values shall be validated on receipt, and invalid values shall be rejected with a reported reason while the previous valid configuration remains in effect. | MUST | Implemented | `test_configuration.py`, `test_scenarios.py` |
| `PR-CONFIG-004` | **Configuration change auditability.** Every configuration change shall be recorded as an auditable event including actor, timestamp, parameter, previous value and new value. | MUST | Implemented | `test_integration.py`, `test_scenarios.py` |
| `PR-CONFIG-005` | **Configuration persistence and versioning.** Configuration shall persist across restart and shall carry a version identifier that is reportable. | MUST | Implemented | `test_group_controller.py`, `test_integration.py` |
| `PR-CONFIG-006` | **No hardcoded operational thresholds.** Operational thresholds, fault confirmation count, fault confirmation window and hysteresis shall not be hardcoded; they shall be configurable parameters. | MUST | Implemented | `test_configuration.py`, `test_scenarios.py` |

### Identity

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-IDENTITY-001` | **Identity hierarchy.** Identity shall follow the hierarchy: `Product ID -> Site ID -> Group ID -> Lamp ID -> MCU Unique ID` | MUST | Implemented | `test_identity.py`, `test_integration.py`, `test_mcc.py` |
| `PR-IDENTITY-002` | **Deterministic and persistent identity.** Identity shall be deterministic and persistent: the same physical lamp node shall report the same identity across restarts, and identity shall not depend on volatile state. | MUST | Implemented | `test_identity.py` |
| `PR-IDENTITY-003` | **Bus address uniqueness.** Each lamp node shall have a unique bus address within its group, and address conflicts shall be detectable and reportable. | MUST | Implemented | `test_identity.py`, `test_integration.py`, `test_scenarios.py` |
| `PR-IDENTITY-004` | **Identity query.** The system shall support an identity query (`IDENTIFY` / `IDENTIFY_ACK`) that returns the node's identity. | SHOULD | Implemented | `test_comm.py`, `test_regressions.py` |

### Authorization, audit and security

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-SECURITY-001` | **Operator authorization for overrides.** Operator override commands (`FORCE_ON`, `FORCE_OFF`, `RETURN_TO_AUTO`) shall be accepted only from an authorized operator. | MUST | Implemented | `test_command.py`, `test_integration.py`, `test_mcc.py`, `test_scenarios.py` |
| `PR-SECURITY-002` | **Command authentication status.** Each command shall carry an authentication status, and unauthenticated commands shall be rejected and recorded. | MUST | Implemented | `test_command.py`, `test_integration.py` |
| `PR-SECURITY-003` | **Audit trail.** The system shall maintain an audit history of commands, configuration changes, acknowledgements, repairs, verifications and closures, including actor and timestamp. | MUST | Implemented | `test_integration.py`, `test_mcc.py`, `test_scenarios.py` |
| `PR-SECURITY-004` | **Tamper detection.** The system shall support a `TAMPER` fault category and shall report tamper indications through the normal fault lifecycle. | SHOULD | Planned | — |
| `PR-SECURITY-005` | **Security validation boundary.** The digital prototype shall not be used to claim validation of security, cryptography, key management or RF security. Any such claim requires separate engineering validation. | MUST | Planned | — |
| `PR-SECURITY-006` | **Preliminary operator roles.** The system shall define the preliminary roles `VIEWER`, `OPERATOR`, `ENGINEER`, `ADMIN` and `OWNER`, distinguishing at least: read-only monitoring, normal operational control and acknowledgement, engineering/diagnostic and configuration actions, administrative actions, and owner-level authority. | SHOULD | Implemented | `test_command.py`, `test_integration.py` |

### Scale and containment

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-SCALABILITY-001` | **Lamps per group.** The system shall support an initial target of approximately 16 lamp nodes per group, and shall scale to a larger node count without architectural change. | MUST | Implemented | `test_group_controller.py`, `test_scenarios.py` |
| `PR-SCALABILITY-002` | **Groups per site.** The architecture shall support multiple groups per site, aggregated at the Master Control Center layer. | SHOULD | Partial | `test_group_controller.py`, `test_integration.py`, `test_mcc.py` |
| `PR-SCALABILITY-003` | **Failure containment.** Failure or misbehaviour of a single lamp node shall not degrade or stop the operation of other lamp nodes or of the group as a whole. | MUST | Implemented | `test_group_controller.py`, `test_scenarios.py` |
| `PR-SCALABILITY-004` | **Architectural headroom.** Adding lamp nodes or groups shall not require redesign of the lamp node, Group Controller or Master Control Center data model. | SHOULD | Implemented | `test_group_controller.py` |
| `PR-SCALABILITY-005` | **Group Controller local storage abstraction.** The Group Controller shall provide an abstract local storage/buffer capable of holding node data, communication events, configuration transactions, synchronization state and data that could not be forwarded during an upstream communication failure. | MUST | Implemented | `test_group_controller.py` |

### Offline operation

| ID | Requirement | Priority | Status | Tests |
| --- | --- | --- | --- | --- |
| `PR-OFFLINE-001` | **Local operation without Internet.** The system shall continue full local operation when the Internet is unavailable. | MUST | Implemented | `test_group_controller.py`, `test_integration.py` |
| `PR-OFFLINE-002` | **Local operation without the Master Control Center.** The system shall continue full local operation when the Master Control Center is unavailable. | MUST | Implemented | `test_group_controller.py`, `test_mcc.py`, `test_integration.py` |
| `PR-OFFLINE-003` | **Local operation without the Group Controller.** A lamp node shall continue to operate its lamp according to its configured mode when the Group Controller is unavailable. | MUST | Implemented | `test_group_controller.py` |
| `PR-OFFLINE-004` | **Offline record buffering.** Records generated while upstream communication is unavailable shall be buffered locally until they can be delivered. | MUST | Implemented | `test_group_controller.py`, `test_integration.py` |
| `PR-OFFLINE-005` | **Post-recovery synchronization without silent loss.** After communication recovery, buffered records shall be delivered following `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM`, and no record shall be silently lost. | MUST | Partial | `test_group_controller.py`, `test_integration.py`, `test_validation.py` |

## 4. Modelled versus physical coverage

Four requirements state a behaviour that is only partly a software property.
For these, "Implemented" refers strictly to the modelled semantics:

| Requirement | What the implementation and tests establish | What remains a physical matter |
| --- | --- | --- |
| `PR-MEASURE-005` | The model carries no billing-grade field and makes no accuracy claim. | Any accuracy statement would require calibrated measurement on hardware. |
| `PR-CONTROL-005` | The modelled restart restores a defined commanded state, reports the restart and resumes operation. | Real watchdog, brown-out and relay fail-state behaviour. |
| `PR-STORAGE-003` | Commit-marker protocol, incomplete-record discard and recovery from a simulated power loss at every point. | Real flash programming, wear, write timing and power-fail windows. |
| `PR-TIME-001` | Logical local timekeeping, validity, ordering and restart semantics. | Physical RTC accuracy, drift and backup retention (`PR-TIME-005`). |

`PR-SECURITY-005` is a documentation boundary: it states that the model must
not be used as a security-validation claim, and it is satisfied by this
documentation set and by the module docstrings.

## 5. Partially implemented requirements

| Requirement | Implemented | Not implemented |
| --- | --- | --- |
| `PR-CONFIG-001` | The full configuration parameter set exists, is validated and is applied locally; the supported integer-scalar subset is distributable remotely. | Structured schedules and the remaining fields are not distributable over the bus; the MCC offers readback only and no structured write path. |
| `PR-CONFIG-002` | `CONFIG_READ` / `CONFIG_WRITE` / `CONFIG_ACK` with authorization, version ordering, atomic application, readback verification and rejection handling, for the supported subset. | The complete parameter set is not on the bus (same subset as above). |
| `PR-FAULT-007` | Confirmed faults are notified, tracked on the fault record and reported to the operator layer through the polled `FAULT_REPORT` path. | The poll carries one active-fault snapshot, so two concurrent confirmed faults on one lamp cannot both be propagated, and a fault closed while another is being reported is not recorded as cleared upstream. A bounded fault-set report is the direction for the physical prototype and is not implemented here. |
| `PR-FAULT-011` | `VERIFYING` state, comparison against the retained original evidence, closure on success and return to `UNDER_REPAIR` on failure. | The verified outcome is supplied by an authorized external actor; there is no automatic comparison of arbitrary physical repair evidence. |
| `PR-STORAGE-007` | Configuration is separate object state from records, and firmware, configuration and calibration are separate storage classes. | A physically separate configuration/calibration medium is not modelled; calibration storage itself is not implemented. |
| `PR-OFFLINE-005` | The documented `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM` sequence is implemented as one deterministic step and verified end to end, including interrupted recovery. | The automatic *trigger* for recovery: the model has no background scheduler, so recovery is detected by the caller before the step runs. |
| `PR-COMM-008` | The communication state machine, deadlines, retries and the `COMM_FAULT -> RECOVERY -> COMM_HEALTHY` path with `COMM_RECOVERED` evidence. | Automatic conversion of link health into a managed per-lamp fault record. |
| `PR-SCALABILITY-002` | Multi-group, multi-site identity, aggregation and containment, exercised with 2 sites x 2 groups x 16 lamps. | A production multi-site deployment with persistence, resource bounds and hardware timing. |

## 6. Planned requirements

| Requirement | Why it is planned |
| --- | --- |
| `PR-SECURITY-004` | Tamper detection needs a real tamper source; only the fault category and event vocabulary exist. |
| `PR-SECURITY-005` | Security validation (key management, authentication strength, cryptography) is outside what a digital model can establish. The requirement is satisfied as a documentation boundary. |
| `PR-TIME-005` | Physical RTC accuracy and backup duration need hardware measurement. |

No security mechanism, cryptography or hardware behaviour is simulated to make
these requirements look complete.

## 7. Related documents

* [architecture.md](architecture.md) - how the requirements are implemented.
* [system_behaviour.md](system_behaviour.md) - the behaviour in narrative form.
* [validation.md](validation.md) - test evidence, limitations and open items.
* [hardware_reference.md](hardware_reference.md) - hardware inputs for the physical prototype.
