# System Behaviour

This document describes what the implemented system does: lighting control,
measurement and diagnostics, fault handling, operator commands, time, identity,
authorization and offline operation. It is the behavioural companion to
[architecture.md](architecture.md).

## 1. Lighting control

### 1.1 Modes and override

Three values are modelled separately and never conflated:

| Value | Meaning |
| --- | --- |
| `configured_mode` | The persistent automatic mode configured for the lamp. |
| `active_override` | The active forced override, or `NONE`. |
| `effective_mode` | The mode actually in force right now, derived from the two above. |

Persistent automatic modes:

| Mode | Behaviour |
| --- | --- |
| `AUTO_SENSOR` | ON when the measured light level falls below the configured ON threshold, OFF when it rises above the OFF threshold, hysteresis applied. |
| `AUTO_SCHEDULE_SENSOR` | Sensor control inside the configured time window; the configured out-of-window state outside it. |
| `FIXED_SCHEDULE` | ON/OFF strictly by configured time windows, independent of the light level. |

Override states (`FORCE_ON`, `FORCE_OFF`) are temporary, not persistent modes.
`RETURN_TO_AUTO` is an operator **command** that clears the override; it is not
a mode and never appears in the mode domains.

### 1.2 Priority

When several control intents are active, the highest wins:

```text
1. Safety / hardware protection
2. Authorized manual override
3. Normal automatic mode
4. Sensor / schedule logic
```

No protection condition is defined in V1, so layer 1 is a reserved hook. The
protection state exists in the model, is never engaged by the fault path, and
is reported as inactive.

### 1.3 Hysteresis and dead band

The ON and OFF light thresholds are ordered and separated by an explicit
hysteresis margin. Inside the dead band the previous state is retained, so a
light level oscillating around a threshold does not produce repeated switching.

### 1.4 Schedule handling

Schedules are daily windows expressed in ticks of day. A window whose start is
later than its end wraps past midnight, so a single schedule can cover the
whole night. Bounds must be non-negative and lie inside the day, the day length
must be positive, and a window must not be empty. Overlapping windows are
permitted and combine as a union: a tick is inside the schedule when any window
contains it. Outside every window the configured out-of-window state applies in
`AUTO_SCHEDULE_SENSOR`.

### 1.5 Restart behaviour

A node restart restores the configured restart-default state, emits a
`NODE_RESTARTED` warning event, resumes normal operation and fails any command
that was still pending. Identity, configuration and retained records survive
the restart; in-flight and volatile state does not.

The Group Controller restart keeps identity, configuration, node
registrations, the per-link replay window and the retained record store
(including the pending upload queue). It clears state a restarted device cannot
have: queued requests and pending commands, which are failed explicitly and
reported. This is object re-initialisation in the model, not a claim about
flash, brown-out or MCU power-loss behaviour.

## 2. Measurement and validity

Sampling and reporting intervals are independently configurable. Each snapshot
carries voltage, current, power, energy and light level together with sensor,
communication and controller status. Values that are unavailable stay `None`
across the model rather than becoming zero.

* `energy` accumulates from valid, finite, non-negative power samples over the
  measurement interval; invalid samples are excluded instead of subtracting.
  Accumulation survives a restart and is cleared only by an authorized
  energy-reset action.
* A measurement is assessed for range and physical consistency before it is
  used as evidence; an inconsistent observation cannot verify a command.
* Light-level values outside the configured sensor range or marked invalid by
  the sensor are treated as sensor problems, not as lamp failures.

Measurements are engineering monitoring values. They are not a billing-grade
measurement, and no accuracy class is claimed.

## 3. Diagnostics

Diagnosis is evidence-based, never single-value. The evidence set is the
commanded state, switching feedback, supply voltage, current, power, light
level, sensor validity, communication state and controller state. Current
alone never classifies lamp health, and a measurement abnormality is never
itself reported as a lamp failure.

The rules are evaluated in a fixed order so that the same evidence always
produces the same result. The first rule that matches decides:

| # | Rule | Classification | Fault category |
| --- | --- | --- | --- |
| 1 | Controller status is not normal | `CONTROLLER_ABNORMALITY` | `CONTROLLER` |
| 2 | Communication fault: the evidence itself may be stale | `COMMUNICATION_ABNORMALITY` | `COMMUNICATION` |
| 3 | Electrical evidence is non-finite or negative | `MEASUREMENT_ABNORMALITY` | `UNKNOWN` |
| 4 | ON commanded, no valid supply voltage | `SUPPLY_ABNORMALITY` | `SUPPLY_VOLTAGE` |
| 5 | ON commanded, switching path ON, voltage present, current at or below the near-zero threshold | `POSSIBLE_OPEN_LOAD` | `UNDER_CURRENT` |
| 6 | Current above the configured maximum | `POSSIBLE_OVER_CURRENT` | `OVER_CURRENT` |
| 7 | OFF commanded, switching path OFF, yet current is present | `UNEXPECTED_CURRENT` | `LAMP_LOAD` |
| 8 | OFF commanded, drawing no current, while the measured light level is at or above the OFF threshold and the sensor is valid | `ENVIRONMENTAL_OR_EXTERNAL` | `ENVIRONMENTAL` |
| 9 | Switching feedback known and different from the commanded state | `SWITCHING_PATH_INCONSISTENCY` | `LAMP_LOAD` |
| 10 | ON commanded and current below the expected band but above the near-zero threshold | `POSSIBLE_UNDER_CURRENT` | `UNDER_CURRENT` |
| 11 | Light sensor reports invalid data | `SENSOR_ABNORMALITY` | `LIGHT_SENSOR` |
| 12 | Light level outside the configured sensor range | `SENSOR_ABNORMALITY` | `LIGHT_SENSOR` |
| 13 | The measurement set is physically inconsistent (power versus voltage and current) | `MEASUREMENT_ABNORMALITY` | `UNKNOWN` |
| 14 | Evidence is insufficient to classify (for example no switching feedback) | `INSUFFICIENT_EVIDENCE` | `INSPECTION_REQUIRED` |
| 15 | Nothing above matched | `NORMAL` | - |

Two consequences of that order are deliberate. A sensor problem is evaluated
after the supply and load rules, so a bad sensor never masks a clear supply or
load condition and is never reported as a lamp failure. External illumination
is an observation, not a lamp fault: the note that a lamp commanded OFF in
bright ambient is drawing no current does not become a managed fault, which
would otherwise raise a confirmed fault and a notification every daylight
period.

Three levels are kept distinct, and conflating them is a defect:

| Level | Meaning |
| --- | --- |
| Measurement abnormality | A value is outside its expected range. No conclusion. |
| Suspected fault | Evidence suggests a fault; confirmation criteria are not met. |
| Confirmed fault | Confirmation criteria are met; the fault is managed. |

A fault carries a **category** (the reporting bucket, such as `UNDER_CURRENT`),
a **diagnostic classification** (the evidence-based interpretation, such as
`POSSIBLE_OPEN_LOAD`) and a **confidence**. None of these is a confirmed
physical root cause; that is established by inspection and repair, never by the
model. `UNKNOWN` and `INSPECTION_REQUIRED` exist so the system never invents a
cause it cannot support.

## 4. Fault management

### 4.1 Lifecycle

```text
NORMAL -> SUSPECTED -> CONFIRMED -> ACKNOWLEDGED -> UNDER_REPAIR -> VERIFYING -> CLOSED
```

| Transition | Condition |
| --- | --- |
| `NORMAL → SUSPECTED` | A measurement abnormality is observed. |
| `SUSPECTED → CONFIRMED` | Confirmation criteria are met. |
| `SUSPECTED → NORMAL` | Evidence clears before confirmation; no confirmed fault is retained. |
| `CONFIRMED → ACKNOWLEDGED` | An authorized actor acknowledges. |
| `ACKNOWLEDGED → UNDER_REPAIR` | Repair starts. |
| `UNDER_REPAIR → VERIFYING` | Repair is reported complete. |
| `VERIFYING → CLOSED` | Verification passes against the original evidence. |
| `VERIFYING → UNDER_REPAIR` | Verification fails; the fault stays active. |
| `CLOSED → SUSPECTED` | The same condition recurs, as a new fault record linked to the previous one. |

Any other transition is rejected and recorded as an event. There is no
`NOTIFIED` lifecycle state: notification progress is tracked independently.

### 4.2 Confirmation and latching

Confirmation requires a configured number of consecutive matching observations
inside a configured time window. A confirmed fault latches: a single
contradicting measurement does not clear it, and threshold oscillation produces
one fault, not one alert per crossing. When evidence genuinely clears, an
unconfirmed suspicion returns to normal; a confirmed fault follows the repair
workflow instead of disappearing.

### 4.3 Notification and escalation

Notification state is tracked separately from the fault lifecycle:
`NOT_REQUIRED → PENDING → SENT → ACK_PENDING`, with `REMINDER_DUE`,
`ESCALATED` and `DELIVERY_FAILED` as the outcomes of an unacknowledged or
undeliverable notification. A reminder is issued once when the reminder
interval elapses; it is not re-sent every cycle, and re-entering
`REMINDER_DUE` is an illegal transition. Delivery failure retries through
`PENDING` up to the configured retry count and otherwise rests in
`DELIVERY_FAILED` with an audit event.

Acknowledgement records operator awareness on the fault lifecycle and emits a
`FAULT_ACKNOWLEDGED` event; it does not close the fault, does not clear
evidence and does not change lamp operation. Notification failure never changes
lighting and never closes a fault.

### 4.4 Repair, verification and closure

| Step | State | Recorded |
| --- | --- | --- |
| Repair started | `UNDER_REPAIR` | actor, timestamp, intent |
| Repair reported complete | `VERIFYING` | actor, timestamp, reported action |
| Verification passed | `CLOSED` | closure timestamp, actor, retained history |
| Verification failed | `UNDER_REPAIR` | failure event, fault stays active |

Verification compares against the evidence captured on the fault record, so a
fault cannot be closed because an unrelated transient changed. Verification
takes an authorized externally supplied outcome: the model enforces the
lifecycle and preserves the evidence, but it does not independently prove a
physical repair.

### 4.5 Containment

| Situation | Behaviour |
| --- | --- |
| One node has a fault | Other nodes and the group continue normally. |
| One node reports a fault storm | Contained at node/bus level; other nodes are unaffected. |
| One node stops communicating | Tracked as link health with communication events; the group continues. |
| The Group Controller is offline | Nodes continue local fault handling autonomously. |
| A sensor is invalid on one node | Treated as a sensor problem on that node only. |

## 5. Operator commands

Commands are authorized before they leave the controller, and success is never
inferred from transmission or receipt alone. The lifecycle is `CREATED →
RECEIVED → EXECUTED → ACKNOWLEDGED → ACTUAL_STATE_VERIFIED`, with `REJECTED`
and `FAILED` as terminal outcomes, and each stage has its own observable
timestamp.

* Duplicate command identities are reported and not executed twice. Re-using an
  identity for a different intent is rejected.
* Unauthorized commands are rejected, audited and never transmitted.
* A physical ON/OFF command is verified only against a fresh measurement that
  shows the expected state; a missing measurement is not evidence of success.
* Mode, override and energy-reset actions verify the state they actually
  change.
* Command, configuration, fault and deletion paths carry the originating actor
  into the audit trail end to end.

### 5.1 No automatic shutdown

The system never switches a lamp off merely because power is unusually high,
because a fault was detected, or because an alert was not acknowledged. It
continues to operate, monitor, log, notify and escalate. `RESET_ENERGY` and
other privileged actions require engineering-or-higher authorization, and a
`VIEWER` can cause no remote control or configuration traffic at all.

## 6. Time

The model keeps **logical** time: a monotonic tick counter per device with an
explicit synchronisation state (`SYNCHRONIZED`, `UNSYNCHRONIZED`, `UNCERTAIN`,
`LOST`). Time never moves backwards, delayed synchronisation does not back-date
records, and a record's validity is fixed when it is created. A node that has
never synchronised records honest uncertainty rather than claiming
synchronisation; sampling itself continues either way.

Physical RTC accuracy, drift, backup retention and power-interruption
behaviour are properties of hardware and are outside what the model can
establish.

## 7. Identity and commissioning

The identity hierarchy is product → site → group → lamp → MCU unique ID.
Identity is value-based and deterministic across restarts. The bus address is
group-scoped, assigned at commissioning, and duplicates are detected and
reported as conflicts. An `IDENTIFY` / `IDENTIFY_ACK` exchange returns the
node's own identity, which is how a technician verifies that the intended node
answers at the intended address.

Commissioning and node replacement are not specified beyond identity and
address: how a replacement node's MCU unique ID is bound to an existing lamp
identity, and what a factory or service reset means, are product decisions that
remain open (see [validation.md](validation.md) section 5).

## 8. Authorization

Preliminary roles, from least to most privileged:

| Role | Purpose |
| --- | --- |
| `VIEWER` | Read-only visibility. |
| `OPERATOR` | Lamp control and fault acknowledgement. |
| `ENGINEER` | Configuration, energy reset and repair actions. |
| `ADMIN` | Record deletion and administration. |
| `OWNER` | Full authority. |

Authorization is a deterministic role/action check, free of cryptography: an
actor asserts an identity and role, and the service decides. Authentication
strength, key management and replay protection are not implemented, and the
model must not be used to claim security validation. A detailed production
permission matrix remains an open item.

All state-changing paths — commands, configuration, fault workflow, record
deletion — check authorization before mutating anything, and every rejection is
audited.

## 9. Offline operation and recovery

Local lighting operation continues without the internet, without the Master
Control Center and without the Group Controller. Records produced during the
outage are stored and queued locally; nothing is lost and nothing is claimed as
delivered before the far end confirms it.

```text
STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM
```

* While the link is down, records accumulate in the pending upload queue.
* On recovery the controller re-synchronises, replays the backlog and keeps
  every record pending until it is accepted upstream.
* A confirmed record leaves the pending queue; the retained copy stays.
* An interrupted replay confirms exactly what was accepted and reports the rest
  as still pending, so a half-finished recovery is never reported as complete.
* Replays are idempotent: a repeated record identity is answered but stored
  once, and no duplicate history is created.

The recovery *step* is deterministic; the trigger is driven by the caller,
because the model contains no background scheduler or daemon.

## 10. Related documents

* [architecture.md](architecture.md) — layers, data model, protocol, storage and configuration.
* [requirements.md](requirements.md) — the requirements this behaviour implements.
* [validation.md](validation.md) — how the behaviour is verified and what remains open.
