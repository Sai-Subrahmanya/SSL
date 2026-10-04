# Design Decisions

This document records the engineering decisions behind the implemented model.
Each decision states what was decided and why; alternatives are noted where a
different choice was seriously available. The identifiers (`D-NNN`) are
referenced from the source code and the tests.

## Decisions

### D-001 — Product boundary

A smart street-light **monitoring and control system** that interfaces with an
external, existing street-light luminaire; not a complete luminaire. Keeps the
scope reviewable and leaves the lamp, driver, optics and enclosure as separate
product concerns.

### D-003 — Layered architecture

Master Control Center → Group Controller → RS-485 bus → Lamp Nodes. Separates
supervision, group coordination and field execution, and keeps aggregation and
buffering at the group layer.

### D-004 — Single RS-485 master

The Group Controller is the sole bus master; nodes transmit only when
addressed. This gives deterministic, collision-free communication and removes
the need for arbitration.

### D-005 — One lamp node per physical lamp

Per-lamp identity, measurement and fault attribution; node count equals lamp
count.

### D-006 — Initial group size of approximately 16 lamps

A stated target that balances bus loading against wiring practicality. The
architecture must scale beyond it without redesign.

### D-007 — Operating modes and priority ordering

Persistent automatic modes are `AUTO_SENSOR`, `AUTO_SCHEDULE_SENSOR` and
`FIXED_SCHEDULE`. `FORCE_ON` and `FORCE_OFF` are temporary overrides, not
modes, and priority is resolved as: safety/protection, authorized override,
automatic mode, sensor/schedule logic.

### D-008 — No automatic shutdown for non-protective conditions

The system never switches a lamp off merely because power is high, a fault was
detected or an alert was unacknowledged. Switching off public lighting on an
unconfirmed condition creates a hazard and destroys evidence. No protective
shutdown condition is defined in V1.

### D-009 — Multi-evidence expected-versus-actual diagnosis

Lamp health is diagnosed from command state, switching feedback, supply
voltage, current, power, light level, sensor validity, communication state and
controller state. Current alone cannot distinguish a lamp, supply, sensor or
measurement problem.

### D-010 — Fault type vocabulary

`LAMP_LOAD`, `UNDER_CURRENT`, `OVER_CURRENT`, `SUPPLY_VOLTAGE`,
`LIGHT_SENSOR`, `COMMUNICATION`, `CONTROLLER`, `ENVIRONMENTAL`, `TAMPER`,
`UNKNOWN`, `INSPECTION_REQUIRED`. The last two exist so the system never
invents a root cause it cannot support.

### D-011 — Fault lifecycle state machine

`NORMAL → SUSPECTED → CONFIRMED → ACKNOWLEDGED → UNDER_REPAIR → VERIFYING →
CLOSED`, with failed verification returning to `UNDER_REPAIR`. A fault is never
closed by silence, and illegal transitions are rejected and recorded.

### D-012 — Fault latching with configurable confirmation

Confirmation requires a configured number of consecutive matching observations
inside a configured window, so threshold oscillation produces one fault rather
than one alert per crossing. Parameters are configuration, never hardcoded.

### D-013 — Acknowledgement, reminder and escalation

Notifications may require acknowledgement, with configurable reminder
interval, escalation timeout and destination. Failure to acknowledge never
switches the lamp off.

### D-014 — Offline operation and store-and-forward

Local operation continues without the internet, without the Master Control
Center and without the Group Controller. Records are stored locally and
delivered after recovery following `STORE → RECOVERY → SYNCHRONIZE → UPLOAD →
CONFIRM`.

### D-016 — Identity hierarchy

`Product ID → Site ID → Group ID → Lamp ID → MCU Unique ID`, deterministic and
persistent. The bus address is group-scoped and is not a substitute for the
lamp identity.

### D-017 — Command success requires verified actual state

A command is not successful because it was received. Lifecycle: `CREATED →
RECEIVED → EXECUTED → ACKNOWLEDGED → ACTUAL_STATE_VERIFIED`, with `REJECTED`
and `FAILED` terminal. Receipt, execution, acknowledgement and verified state
are different engineering facts.

### D-019 — Communication state machine

`COMM_HEALTHY → RETRY → DEGRADED → COMM_FAULT → RECOVERY → COMM_HEALTHY`.
Degradation is visible and testable rather than a binary online/offline flag.

### D-021 — Local time with explicit validity

Each node keeps local time, timestamps records locally when unsynchronised,
marks uncertainty rather than claiming synchronisation, and re-synchronises
after recovery. Ordering relies on sequence numbers when time is uncertain.

### D-022 — Configuration model with audit and validation

All operational values — modes, thresholds, hysteresis, schedules, intervals,
confirmation policy, communication and notification parameters — are
configuration, validated and audited. No operational threshold is hardcoded.

### D-023 — Hardware components are candidates only

Referenced components are engineering candidates, not frozen selections; no
software behaviour depends on a specific part, and hardware interfaces are
modelled abstractly.

### D-024 — Claim discipline

The repository distinguishes "digitally validated" model behaviour from
physical validation. Safety, certification, metering-grade accuracy and
production readiness are never claimed.

### D-025 — International engineering scope

India and China as initial target markets, international adaptability desired,
wide-range AC input (90–305 VAC) and a nominal 230 VAC switched lamp output,
single-phase line-to-neutral. Design targets, not certification.

### D-029 — Measurements are engineering monitoring values

Voltage, current, power, energy and light level are monitoring values and are
never described as billing-grade metering; no accuracy class is claimed.

### D-030 — Master Control Center is a logical layer

The MCC is a logical operator/control and data layer. No graphical user
interface, cloud service, database or web backend is part of this repository.

### D-031 — Configured mode, active override and effective state are separate

Three values are modelled independently and the effective state is derived
deterministically. Conflating configuration with a temporary override corrupts
the audit trail and the operator mental model. `RETURN_TO_AUTO` is a command,
not a mode.

### D-032 — "Switching feedback" replaces "relay feedback"

The observed state of the switching path is modelled abstractly; no specific
physical realisation (sensed switched-output voltage, auxiliary contact, other)
is assumed. The assumption that *some* feedback mechanism exists is recorded as
an open item (A-18).

### D-033 — Notification state is independent of the fault lifecycle

Notification and escalation are tracked in their own state machine
(`NOT_REQUIRED`, `PENDING`, `SENT`, `ACK_PENDING`, `REMINDER_DUE`,
`ESCALATED`, `DELIVERY_FAILED`). A fault can stay `CONFIRMED` for a long time
while its notification state changes, so `NOTIFIED` is deliberately not a
fault lifecycle state.

### D-034 — Fault category, diagnostic classification and root cause are distinct

A fault carries a reporting category and an evidence-based classification;
neither is a confirmed physical root cause, which only inspection and repair
establish.

### D-035 — Record lifecycle and retention

`CREATED → STORED → PENDING_UPLOAD → UPLOADED → CONFIRMED → RETAINED`.
Confirmation only allows removal from the pending upload queue; the retained
record is never deleted by confirmation. Deletion is explicit, authorized and
audited, and automatic deletion is off by default.

### D-036 — Preliminary operator roles

`VIEWER`, `OPERATOR`, `ENGINEER`, `ADMIN`, `OWNER`, distinguished conceptually.
The detailed production permission matrix is deferred (A-27).

### D-037 — Group Controller storage is an abstract capability

The controller's local buffer is modelled as an abstract capability; no
physical memory device is selected (A-28).

### D-038 — `RESET_ENERGY` is a control subtype

Resetting accumulated energy is carried as a subtype inside `CONTROL_COMMAND`
rather than as a new message type, which keeps the message set small and the
validation surface bounded.

### D-039 — Physical RTC performance is outside digital validation

The model covers logical time semantics only; backup duration, leakage,
temperature effects, oscillator accuracy and power-interruption behaviour
require physical measurement (A-26).

### D-040 — Python implementation, no runtime dependencies

The model is implemented in Python under `src/sslv1/` using only the standard
library, with pytest as the test runner. The domain layer stays
hardware-independent and unit-testable, and can later sit behind a hardware
abstraction layer without rewriting core logic.

### D-041 — The Master Control Center is a consumer of existing components

The MCC aggregates and orchestrates over the existing Lamp Node, Group
Controller, authorization and command components. A second implementation
would create two sources of truth for status, faults, audit and authorization.
The MCC keeps no persistence and no second record format.

### D-042 — Restart re-initialises transient state only

A restart keeps identity, configuration, registrations, the per-link replay
window and retained records, and clears what a restarted device cannot have:
queued requests and pending commands, which are failed explicitly and reported.
Presenting an in-flight transaction as still pending would be a false claim
about a dead transaction.

### D-043 — Upstream record intake semantics

The MCC accepts an upload only when it is valid, attributable to the delivering
controller and consistent with the scope the record declares. A duplicate is
answered as received but stored once (the sender's confirmation semantics are
"the far end has it"); an unattributable record is refused and stays pending at
the sender, so a mis-delivered record cannot be filed under the wrong scope.

## Directions not yet implemented

These are recorded so that a limit is not mistaken for an oversight. None of
them is implemented or simulated.

| Item | Direction | Why it matters |
| --- | --- | --- |
| Fault-set reporting (`D-044`) | The physical prototype's fault report should carry the lamp's bounded active fault **set**, with per-fault open/close transitions, instead of the single active-fault snapshot used today. | Two concurrent confirmed faults on one lamp cannot both be propagated today, and a fault closed while another is reported is not recorded as cleared upstream. |
| Automatic recovery trigger | A scheduler or event source that runs the post-recovery upload step without waiting for a caller. | Today the recovery step is deterministic but caller-driven. |
| Repair-evidence comparison | Automatic comparison of returned repair evidence against the fault's original evidence. | Today verification uses an authorized externally supplied outcome. |
| Security architecture | Operator identity, key management, secure update, transport security and replay protection. | Today authorization is an asserted actor on a trusted bus. |

## Related documents

* [architecture.md](architecture.md) — the structures these decisions define.
* [system_behaviour.md](system_behaviour.md) — the behaviour they produce.
* [validation.md](validation.md) — the open engineering items and limitations.
