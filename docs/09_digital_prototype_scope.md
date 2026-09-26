# 09 - Digital Prototype Scope

## 1. Document purpose

This document defines the boundary of the **digital prototype**: what it will
validate, what it will not validate, and what claims may and may not be made
from it.

It exists to prevent the digital prototype from being mistaken for physical
validation.

---

## 2. Purpose of the digital prototype

The digital prototype is a **simulation of the system's logic, state
machines, data flow and communication behaviour**. Its purpose is to make the
engineering reviewable before hardware exists, and to provide a controlled
environment in which behaviour can be demonstrated deterministically.

---

## 3. In scope

| Area | What is validated (logically) |
| --- | --- |
| Control logic | Operating modes, priority resolution, override handling. |
| State machines | Fault lifecycle, communication states, command lifecycle. |
| Monitoring | Measurement handling, sensor validity, status reporting. |
| Diagnostics | Expected-versus-actual rules and evidence combination. |
| Communication | RS-485 framing, message types, sequencing, CRC, polling, timeout, retry. |
| Storage behaviour | Record structure, commit semantics, corruption detection, retention, store-and-forward. |
| Event handling | Event model, logging, audit trail. |
| Fault handling | Detection, confirmation, latching, notification, acknowledgement, escalation, repair, verification, closure. |
| Recovery | Communication loss/recovery, restart recovery, re-synchronization. |
| Group simulation | Multi-node behaviour, aggregation, scalability. |
| Deterministic fault injection | Explicit, repeatable fault conditions. |
| Failure containment | Single-node failure isolation. |
| Configuration | Distribution, validation, persistence, auditability. |
| Offline operation | Local autonomy and buffering without upstream connectivity. |

---

## 4. Out of scope

| Area | Why it is out of scope |
| --- | --- |
| Physical electrical validation | Requires real hardware and instrumentation. |
| PCB design and safety | Requires physical design and review. |
| Mains safety | Requires physical engineering validation. |
| Isolation, creepage, clearance | Physical design properties. |
| EMC | Requires physical test facilities. |
| Surge | Requires physical test facilities. |
| ESD | Requires physical test facilities. |
| Relay lifetime | Requires physical endurance testing. |
| LED inrush behaviour | Requires physical measurement. |
| Thermal performance | Requires physical thermal measurement. |
| Enclosure and IP rating | Requires physical design and testing. |
| Actual RF performance | Requires physical RF measurement. |
| Current-transformer (CT) measurement accuracy | Requires physical calibration. |
| ADE7953 accuracy on the final PCB | Requires physical measurement. |
| Actual AC switching behaviour and LED inrush | Requires physical measurement. |
| Relay contact life | Requires physical endurance testing. |
| Mains isolation | Requires physical design and test. |
| Ethernet physical-layer performance | Requires physical measurement. |
| Cellular RF performance | Requires physical RF measurement. |
| Actual RTC backup duration | Requires physical measurement. |
| Certification | Requires accredited physical testing. |

---

## 5. Claim discipline

### 5.1 Permitted claims

| Permitted phrasing | Meaning |
| --- | --- |
| "Digitally validated" | Behaviour demonstrated in the digital prototype. |
| "Modelled behaviour verified" | The model's logic was tested. |
| "Simulated" | Executed in the digital prototype, not on hardware. |

### 5.2 Prohibited claims

| Prohibited phrasing | Reason |
| --- | --- |
| "Safety validated" | Not testable digitally. |
| "Certified" / "compliant" | Requires accredited physical testing. |
| "EMC proven" | Requires physical test facilities. |
| "Metering-grade accuracy" | Requires calibration and traceability. |
| "Field proven" | Requires physical deployment. |
| "Production ready" | No production validation has occurred. |

Any document, demo or presentation derived from this repository must respect
this distinction.

---

## 6. Modelling assumptions

The digital prototype models physical quantities (voltage, current, power,
light level, time) as simulated values. Consequences:

- measured values in the prototype are **not** physical measurements,
- injected faults represent **modelled conditions**, not physical failures,
- timing behaviour represents **logical timing**, not hardware timing,
- power-loss and restart behaviour represents **modelled semantics**, not
  measured hardware behaviour.
- the RTC represents **logical clock semantics**, not the physical
  RV-3028-C7 with its supercapacitor backup, leakage, temperature effects or
  oscillator accuracy. Physical RTC backup duration is **not** validated
  digitally.

---

## 7. Relationship to physical validation

```text
Digital engineering
      -> internal validation
      -> engineering package
      -> Minewing engineering review
      -> physical prototype
      -> physical validation
      -> iteration
```

The digital prototype produces an **engineering package** for review. It does
not replace physical validation, and physical validation may change
requirements, architecture or design.

---

## 8. Deliverables of the digital prototype

| Deliverable | Description |
| --- | --- |
| Behavioural model | Implemented logic and state machines. |
| Test evidence | Deterministic test results per requirement. |
| Traceability record | Requirement -> module -> test mapping. |
| Assumptions register | Explicit unknowns and their effect if changed. |
| Decision log | Engineering decisions with reasons and consequences. |
| Demonstration material | Reproducible demonstrations of behaviour (see `docs/demo/`). |

---

## 9. Explicit non-goals for the current phase

The current phase (Phase 0) produces **documentation only**:

- no simulation source code,
- no test code,
- no build system, packaging or dependency configuration,
- no hardware design files.

The only non-documentation file added is a Markdown lint configuration
(`.markdownlint-cli2.jsonc`), which exists solely to validate the formatting
of this documentation set.

---

## 10. Related documents

- [00_project_overview.md](00_project_overview.md)
- [02_product_requirements.md](02_product_requirements.md)
- [08_testing_strategy.md](08_testing_strategy.md)
- [10_hardware_reference.md](10_hardware_reference.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
