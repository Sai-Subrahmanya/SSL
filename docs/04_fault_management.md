# 04 - Fault Management

## 1. Document purpose

This document defines the **fault model** for Smart Street Light V1: fault
classification, the distinction between observation and conclusion, the
fault lifecycle state machine, confirmation and latching policy,
notification and escalation, repair, verification and closure.

It is derived from `PR-FAULT-*`, `PR-DIAG-*` and `PR-CONTROL-006` in
[02_product_requirements.md](02_product_requirements.md).

---

## 2. Fundamental concept separation

The system shall maintain three distinct levels. Conflating them is a defect.

| Level | Meaning | Who creates it |
| --- | --- | --- |
| **Measurement abnormality** | A measurement is outside its expected range. No conclusion is drawn. | Measurement handling |
| **Suspected fault** | Diagnostic evidence suggests a fault, but confirmation criteria are not yet met. | Diagnostics |
| **Confirmed fault** | Confirmation criteria have been satisfied; the fault enters the managed lifecycle. | Fault lifecycle |

```text
measurement abnormality
        |
        v
   SUSPECTED  ------------------+
        |                       |  evidence disappears
        | criteria met          v
        v                    (abnormality cleared)
   CONFIRMED
```

A measurement abnormality alone shall never create a confirmed fault
(`PR-DIAG-007`).

---

## 3. Diagnostic evidence model

Lamp health shall not be classified using current alone (`PR-DIAG-001`).
Evidence combined for diagnosis:

- command state,
- relay feedback,
- supply voltage,
- current,
- power,
- light level,
- sensor validity,
- communication state,
- controller state.

### 3.1 Approved diagnostic rules

| # | Evidence combination | Classification |
| --- | --- | --- |
| 1 | ON command + relay ON + voltage present + normal current + normal light level | Normal operation |
| 2 | ON command + relay ON + voltage present + near-zero current | Suspected open-load / lamp fault |
| 3 | OFF command + relay OFF + significant current | Suspected unexpected current / switching-path issue / external condition |
| 4 | ON command + voltage absent | Suspected supply / voltage issue |
| 5 | Abnormal light level + invalid sensor | Sensor problem - **not** a confirmed lamp failure |

These rules are **diagnostic rules, not physical proof**. They indicate
where attention is required; they do not establish a physical root cause.

---

## 4. Fault type catalogue

| Fault type | Description | Typical evidence |
| --- | --- | --- |
| `LAMP_LOAD` | Lamp load condition inconsistent with the commanded state (including open load). | Rule 2 / Rule 3 |
| `UNDER_CURRENT` | Current below the expected band for the commanded state. | Rule 2 |
| `OVER_CURRENT` | Current above the expected band for the commanded state. | Current above band with relay ON |
| `SUPPLY_VOLTAGE` | Supply voltage absent or outside the expected band. | Rule 4 |
| `LIGHT_SENSOR` | Light sensor invalid, stuck or inconsistent. | Rule 5 |
| `COMMUNICATION` | Node or group communication fault. | Communication state machine |
| `CONTROLLER` | Node controller health problem (including restart loops). | Controller status |
| `ENVIRONMENTAL` | Environmental condition outside expected range. | Environmental inputs |
| `TAMPER` | Indication of unauthorized interference. | Tamper input |
| `UNKNOWN` | Evidence does not map to a known category. | Any |
| `INSPECTION_REQUIRED` | Evidence warrants physical inspection; no automated conclusion. | Any |

### 4.1 Notes

- `UNKNOWN` and `INSPECTION_REQUIRED` exist so that the system never has to
  invent a root cause it cannot support.
- Fault types are a **controlled vocabulary**; new types require a decision
  record in [12_engineering_decisions.md](12_engineering_decisions.md).

---

## 5. Fault severity

Each fault carries a severity that drives notification and escalation
behaviour. The severity scale is a design choice and is not fixed by this
document (`PR-FAULT-002`).

---

## 6. Fault lifecycle state machine

### 6.1 State diagram

```text
                         +--------+
                         | NORMAL |
                         +---+----+
                             |
              abnormality    |  evidence persists
              observed       v
                         +-----------+   confirmation criteria met
                         | SUSPECTED +------------------+
                         +-----+-----+                  |
                               |                        |
                     evidence   |                        v
                     disappears +----------------+  +-----------+
                                          (clear)|  | CONFIRMED |
                                                  |  +-----+-----+
                                                  |        |
                                                  |        | notify
                                                  |        v
                                                  |  +-----------+
                                                  |  | NOTIFIED  |
                                                  |  +-----+-----+
                                                  |        |
                                                  |        | acknowledged
                                                  |        v
                                                  |  +--------------+
                                                  |  | ACKNOWLEDGED |
                                                  |  +------+-------+
                                                  |         |
                                                  |         | repair starts
                                                  |         v
                                                  |  +--------------+
                                                  |  | UNDER_REPAIR |
                                                  |  +------+-------+
                                                  |         |
                                                  |         | repair reported
                                                  |         v
                                                  |  +------------+
                                                  |  | VERIFYING  |
                                                  |  +------+-----+
                                                  |         |
                                    verification|         | verification passed
                                    failed      |         v
                                                  |  +---------+
                                                  +->| CLOSED  |
                                                     +---------+
```

### 6.2 State definitions

| State | Meaning |
| --- | --- |
| `NORMAL` | No active fault condition for the lamp. |
| `SUSPECTED` | Evidence present; confirmation incomplete. |
| `CONFIRMED` | Confirmation criteria met; fault is now managed. |
| `NOTIFIED` | Confirmed fault has been notified to the operator layer. |
| `ACKNOWLEDGED` | An authorized actor has acknowledged the notification. |
| `UNDER_REPAIR` | Repair activity is in progress. |
| `VERIFYING` | Repair is being checked against the original evidence. |
| `CLOSED` | Fault resolved and closed with recorded closure data. |

### 6.3 Permitted transitions

| From | To | Condition |
| --- | --- | --- |
| `NORMAL` | `SUSPECTED` | Measurement abnormality observed. |
| `SUSPECTED` | `CONFIRMED` | Confirmation criteria met. |
| `SUSPECTED` | `NORMAL` | Evidence cleared before confirmation (no fault record retained as confirmed). |
| `CONFIRMED` | `NOTIFIED` | Notification issued. |
| `NOTIFIED` | `ACKNOWLEDGED` | Acknowledgement received. |
| `NOTIFIED` | `ACKNOWLEDGED` | Escalation issued, then acknowledged. |
| `ACKNOWLEDGED` | `UNDER_REPAIR` | Repair started. |
| `UNDER_REPAIR` | `VERIFYING` | Repair reported complete. |
| `VERIFYING` | `CLOSED` | Verification passed. |
| `VERIFYING` | `UNDER_REPAIR` | Verification failed; fault returns to an active state. |
| `CLOSED` | `SUSPECTED` | The same condition recurs (new fault record). |

### 6.4 Failed verification

Failed verification shall return the fault to an **active fault state**
(`UNDER_REPAIR`), not to `CLOSED` and not to `NORMAL`
(`PR-FAULT-011`). The fault remains in the lifecycle until it is genuinely
resolved.

### 6.5 Illegal transitions

Any transition not listed in 6.3 is illegal and shall be rejected and
recorded as an event (`PR-FAULT-004`). Examples of illegal transitions:

- `NORMAL` -> `CLOSED` (nothing to close),
- `SUSPECTED` -> `ACKNOWLEDGED` (acknowledging an unconfirmed condition),
- `CONFIRMED` -> `CLOSED` (skipping notification and verification),
- `CLOSED` -> `UNDER_REPAIR` without re-opening,
- `VERIFYING` -> `NORMAL`.

---

## 7. Confirmation, latching and hysteresis

### 7.1 Purpose

Threshold oscillation must not repeatedly create new alerts
(`PR-FAULT-006`).

### 7.2 Anti-oscillation example

```text
measurement:  39  41  39  41  39  41
threshold:    40

naive behaviour: alert, clear, alert, clear, alert, clear   <-- PROHIBITED
required behaviour: one suspected fault, one confirmed fault,
                    latched until conditions genuinely clear
```

### 7.3 Confirmation policy

| Parameter | Meaning | Requirement |
| --- | --- | --- |
| Observation count | Number of consecutive confirming observations required. | `PR-FAULT-005` |
| Confirmation window | Time window within which the observations must occur. | `PR-FAULT-005` |
| Hysteresis | Separate enter/exit thresholds to prevent oscillation. | `PR-FAULT-006` |

All three are configurable and shall not be hardcoded (`PR-CONFIG-006`).

### 7.4 Latching rules

1. A suspected fault is raised once and remains latched while evidence
   persists.
2. Confirmation counts observations; it does not create a new fault per
   observation.
3. A latched fault is cleared only when the exit condition (including
   hysteresis) is satisfied for the configured clear policy.
4. Recurrence of a cleared condition creates a **new** fault record linked to
   the previous one, rather than silently reusing the old record.

---

## 8. Notification, acknowledgement and escalation

### 8.1 Flow

```text
CONFIRMED -> NOTIFIED -> (reminder)* -> ACKNOWLEDGED
                              |
                              +--> escalation timeout reached -> ESCALATED
```

### 8.2 Configurable parameters

| Parameter | Purpose |
| --- | --- |
| Reminder interval | How often an unacknowledged notification is repeated. |
| Escalation timeout | When an unacknowledged notification escalates. |
| Escalation destination | Where the escalation is sent. |

### 8.3 Acknowledgement is not a cure

Acknowledging a fault records operator awareness. It does **not** close the
fault, does not clear evidence, and does not change lamp operation
(`PR-FAULT-008`).

### 8.4 Unacknowledged alerts never switch the lamp OFF

Failure to acknowledge shall not, by itself, cause the lamp to be switched
OFF (`PR-FAULT-009`).

---

## 9. No automatic shutdown for non-protective conditions

The system shall not automatically switch a lamp OFF merely because:

- power is unusually high,
- a fault has been detected,
- an alert has not been acknowledged.

Normal behaviour is:

```text
continue operation -> monitor -> log -> notify -> escalate
```

Automatic protective shutdown is reserved for genuine protection conditions
that will be explicitly defined later. **No such condition is defined in
V1**, therefore no automatic shutdown behaviour is specified
(`PR-CONTROL-006`).

---

## 10. Repair workflow

| Step | State | Recorded information |
| --- | --- | --- |
| Repair started | `UNDER_REPAIR` | Actor, timestamp, intent. |
| Repair in progress | `UNDER_REPAIR` | Progress events as available. |
| Repair reported complete | `VERIFYING` | Actor, timestamp, reported action. |

The system does not assume the repair worked. It moves to verification
(`PR-FAULT-010`).

---

## 11. Verification workflow

| Step | Check | Outcome |
| --- | --- | --- |
| Enter verification | `VERIFYING` | Original evidence captured for comparison. |
| Evaluate evidence | Compare current evidence against original evidence. | |
| Pass | `CLOSED` | Closure timestamp and actor recorded. |
| Fail | `UNDER_REPAIR` | Fault returns to an active state; verification failure recorded as an event. |

Verification shall compare against the **original evidence** stored on the
fault record, so that a fault cannot be closed merely because a transient
condition changed (`PR-FAULT-011`).

---

## 12. Fault closure

Closure requires:

- verification passed,
- closure timestamp,
- closure actor,
- closed fault retained in history (never deleted; automatic deletion is
  off by default - `PR-STORAGE-005`).

Closure is auditable (`PR-SECURITY-003`).

---

## 13. Failure containment

| Situation | Required behaviour |
| --- | --- |
| One node has a fault | Other nodes and the group continue normally. |
| One node reports a fault storm | Contained at node/bus level; must not degrade other nodes. |
| One node stops communicating | Reported as `COMMUNICATION` fault after policy; group continues. |
| Group Controller unavailable | Nodes continue local fault handling autonomously. |
| Sensor invalid on one node | Treated as a sensor problem on that node only. |

`PR-FAULT-012`, `PR-SCALABILITY-003`.

---

## 14. Traceability

| Topic | Requirements |
| --- | --- |
| Evidence-based diagnosis | `PR-DIAG-001` .. `PR-DIAG-007` |
| Fault classification | `PR-FAULT-001`, `PR-FAULT-002` |
| Lifecycle | `PR-FAULT-003`, `PR-FAULT-004`, `PR-FAULT-012` |
| Confirmation and latching | `PR-FAULT-005`, `PR-FAULT-006`, `PR-CONFIG-006` |
| Notification and escalation | `PR-FAULT-007`, `PR-FAULT-008`, `PR-FAULT-009` |
| Repair and verification | `PR-FAULT-010`, `PR-FAULT-011` |
| Containment | `PR-FAULT-012`, `PR-SCALABILITY-003` |
| No automatic shutdown | `PR-CONTROL-006` |
| Auditability | `PR-SECURITY-003` |

---

## 15. Implementation status

| Item | Status |
| --- | --- |
| Fault model defined | Yes |
| Fault lifecycle defined | Yes |
| Confirmation parameters | Configurable - values not yet decided |
| Implementation | **Not started** (Phase 6) |

---

## 16. Related documents

- [02_product_requirements.md](02_product_requirements.md)
- [03_data_model.md](03_data_model.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [07_configuration.md](07_configuration.md)
- [08_testing_strategy.md](08_testing_strategy.md)
- [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
