# 00 - Project Overview

## 1. Document purpose

This document establishes the shared understanding of what Smart Street
Light V1 is, what it is not, how it is expected to be developed, and the
vocabulary used by the rest of the engineering documentation set.

It is a **requirements-adjacent** document: it frames the project but does
not itself introduce numbered requirements. Numbered requirements live in
[02_product_requirements.md](02_product_requirements.md).

---

## 2. Project identity

| Field | Value |
| --- | --- |
| Project name | Smart Street Light V1 (SSL V1) |
| Repository | `Sai-Subrahmanya/SSL` |
| Current stage | Phase 0 - Repository foundation |
| Repository classification | Early engineering / digital prototype development |
| Production status | Not production firmware |

---

## 3. Purpose and product concept

Smart Street Light V1 is a **digitally validated, scalable smart
street-light monitoring and control system**.

The V1 product boundary is:

> A smart street-light monitoring/control system interfacing with an
> external existing street-light/luminaire.

It is **not** initially a complete street-light luminaire.

The system attaches to an existing lamp installation and provides control,
measurement, diagnostics, fault management and communication. The
luminaire, lamp and its optics remain outside the product boundary.

---

## 4. Engineering principle

The project follows a strict sequence:

```text
REQUIREMENT -> ARCHITECTURE -> DESIGN -> IMPLEMENTATION -> TEST -> AUDIT -> VALIDATION
```

The following anti-pattern is explicitly prohibited:

```text
CODE FIRST -> invent requirements afterwards
```

Every future implementation element must be traceable to an engineering
requirement. Traceability is maintained in
[requirements_traceability.md](requirements_traceability.md).

---

## 5. Digital prototype purpose

The digital prototype will eventually validate (logically, not physically):

- lamp-node logic,
- lighting control,
- manual override,
- measurement handling,
- expected-versus-actual diagnostics,
- fault detection,
- fault confirmation,
- fault latching,
- fault acknowledgement,
- repair workflow,
- verification workflow,
- fault closure,
- communication behaviour,
- communication loss and recovery,
- offline operation,
- local logging,
- store-and-forward,
- configuration,
- event history,
- RS-485 protocol behaviour,
- multi-lamp group behaviour,
- failure containment,
- fault injection,
- recovery behaviour.

The digital prototype must **not** claim to validate:

- mains electrical safety,
- PCB safety,
- isolation,
- creepage and clearance,
- EMC,
- surge,
- ESD,
- relay lifetime,
- LED inrush behaviour,
- thermal performance of real hardware,
- enclosure and IP rating,
- actual RF performance,
- certification.

These require later physical engineering validation.

---

## 6. System summary

### 6.1 Architecture

```text
                MASTER CONTROL CENTER
              (operator / control layer)
                         |
                         |  upstream link
                         |
                  GROUP CONTROLLER
                 (RS-485 bus master)
                         |
                         |
                      RS-485
                         |
   +---------------------+---------------------+
   |                     |                     |
LAMP NODE 1         LAMP NODE 2  ...      LAMP NODE N
(one per lamp)
```

Initial target: approximately 16 lamps per group. The architecture must
remain scalable.

### 6.2 Element summary

| Element | Role |
| --- | --- |
| Master Control Center | Logical operator/control layer: sites, groups, lamps, status, faults, configuration, schedules, overrides, audit history. |
| Group Controller | RS-485 master: polling, aggregation, configuration distribution, time synchronization, command forwarding, retry/timeout, upstream connectivity, buffering. |
| Lamp Node | One node per physical lamp: control, measurement, diagnostics, fault lifecycle, local logging, offline operation, identity. |
| RS-485 bus | Deterministic wired multi-drop link between Group Controller and Lamp Nodes. |

---

## 7. Operating modes

| Mode | Description |
| --- | --- |
| `AUTO_SENSOR` | Automatic operation based on light level. |
| `AUTO_SCHEDULE_SENSOR` | Configurable time window with sensor-based control. |
| `FIXED_SCHEDULE` | ON/OFF according to configured times. |
| `FORCE_ON` | Authorized operator forces ON. |
| `FORCE_OFF` | Authorized operator forces OFF. |
| `RETURN_TO_AUTO` | Return to the configured automatic mode. |

Priority concept (highest first):

```text
Safety / hardware protection
        >
Authorized manual override
        >
Normal automatic mode
        >
Sensor / schedule logic
```

These modes are the **approved behavioural requirement**. They are not
implemented in this repository yet.

---

## 8. Operator behaviour principle

The system must **not** automatically shut a lamp OFF merely because:

- power is unusually high,
- a fault is detected,
- the operator has not acknowledged an alert.

The system should normally:

```text
continue operation -> monitor -> log -> notify -> escalate
```

Automatic protective shutdown is reserved for genuine protection conditions
that will be explicitly defined later. Until those conditions are defined,
no automatic shutdown behaviour shall be implemented.

---

## 9. Measurement model (summary)

Each lamp conceptually provides:

- voltage,
- current,
- power,
- energy,
- light level,
- commanded state,
- relay feedback,
- actual state,
- sensor status,
- communication status,
- controller status,
- operating mode.

These are **engineering monitoring values**. They must not be described as
billing-grade metering.

---

## 10. Fault model (summary)

Fault categories:

`LAMP_LOAD`, `UNDER_CURRENT`, `OVER_CURRENT`, `SUPPLY_VOLTAGE`,
`LIGHT_SENSOR`, `COMMUNICATION`, `CONTROLLER`, `ENVIRONMENTAL`, `TAMPER`,
`UNKNOWN`, `INSPECTION_REQUIRED`.

Fault lifecycle:

```text
NORMAL -> SUSPECTED -> CONFIRMED -> NOTIFIED -> ACKNOWLEDGED
       -> UNDER_REPAIR -> VERIFYING -> CLOSED
```

Three distinct concepts must be maintained:

1. **Measurement abnormality** - a measurement is out of expected range.
2. **Suspected fault** - evidence suggests a fault but confirmation is
   incomplete.
3. **Confirmed fault** - confirmation criteria have been met.

Details in [04_fault_management.md](04_fault_management.md).

---

## 11. Development roadmap

| Phase | Name | Scope summary | Status |
| --- | --- | --- | --- |
| Phase 0 | Repository foundation | Structure, documentation, requirements baseline, assumptions, traceability, development rules. | In progress |
| Phase 1 | Core domain model | Core entities, identifiers, value objects, enums, state definitions. | Not started |
| Phase 2 | Lamp Node | Lamp Node module: responsibilities, interfaces, lifecycle, identity. | Not started |
| Phase 3 | Lighting control | Operating modes, priority handling, override handling. | Not started |
| Phase 4 | Measurement model | Voltage/current/power/energy/light-level handling, sampling, sensor health. | Not started |
| Phase 5 | Diagnostics | Expected-versus-actual diagnostic rules, evidence combination. | Not started |
| Phase 6 | Fault lifecycle | Detection, confirmation, latching, notification, acknowledgement, repair, verification, closure. | Not started |
| Phase 7 | Event / logging | Event model, local event and measurement logging. | Not started |
| Phase 8 | Persistent storage simulation | Record format, integrity, power-loss recovery, retention, store-and-forward. | Not started |
| Phase 9 | RS-485 protocol | Framing, message types, sequencing, CRC, addressing. | Not started |
| Phase 10 | Group Controller | Polling, aggregation, command forwarding, retry/timeout, buffering. | Not started |
| Phase 11 | Communication failure / recovery | Communication state machine, degradation, recovery, re-synchronization. | Not started |
| Phase 12 | Configuration | Configuration model, distribution, validation, auditability. | Not started |
| Phase 13 | Multi-node simulation | Multiple lamp nodes, group behaviour, scalability. | Not started |
| Phase 14 | Fault injection | Deterministic fault injection and recovery behaviour. | Not started |
| Phase 15 | Master Control Center data layer | Sites, groups, lamps, aggregation, history, no GUI in early phases. | Not started |
| Phase 16 | Full integration | End-to-end integration of all layers. | Not started |
| Phase 17 | System validation | Validation against requirements, test evidence, traceability closure. | Not started |
| Phase 18 | Engineering audit | Independent audit, engineering package preparation for partner review. | Not started |

Later phases are not implemented in advance. Each phase begins only after its
requirements are documented and reviewed.

---

## 12. Glossary

| Term | Meaning in this project |
| --- | --- |
| Lamp Node | The controller associated with exactly one physical lamp. |
| Group Controller | The RS-485 master for a group of lamp nodes. |
| Master Control Center (MCC) | The logical operator/control layer above the Group Controller. |
| Commanded state | The state the system has commanded the lamp into (ON/OFF). |
| Relay feedback | The reported state of the switching element, as distinct from the command. |
| Actual state | The observed state of the lamp derived from measurement evidence. |
| Expected-versus-actual diagnosis | Comparison of the commanded/expected operating point against measured evidence. |
| Measurement abnormality | A measurement outside its expected range; not yet a fault. |
| Suspected fault | Evidence-based suspicion, before confirmation criteria are met. |
| Confirmed fault | A fault whose confirmation criteria have been satisfied. |
| Latching | Holding a fault active so that threshold oscillation does not create repeated alerts. |
| Hysteresis | Separate enter/exit thresholds to prevent oscillation. |
| Store-and-forward | Buffering records locally during communication loss and forwarding them after recovery. |
| Engineering candidate | A component or value proposed for consideration, not a frozen selection. |
| Digital validation | Demonstration of modelled behaviour in the digital prototype; not physical validation. |

---

## 13. International engineering scope (context)

- India and China are important initial target markets.
- International adaptability is desired.
- Controller input target: 90-305 VAC.
- Nominal V1 switched lamp output: 230 VAC.
- Scope is single-phase, line-to-neutral.

These are **engineering design targets**, not certification claims. See
[docs/10_hardware_reference.md](10_hardware_reference.md) and
[docs/11_assumptions.md](11_assumptions.md).

---

## 14. Related documents

- [01_system_architecture.md](01_system_architecture.md)
- [02_product_requirements.md](02_product_requirements.md)
- [04_fault_management.md](04_fault_management.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
