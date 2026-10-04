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

The repository now contains executable Python domain and integration models,
packaging and tests. The earlier Phase 0 documentation-only description is
historical, not the current implementation status. Current verified behavior
and partial/deferred requirements are recorded in the implementation report
and traceability matrix. Passing digital tests does not mean every product
requirement is complete or that the model is physical PCB firmware.

---

## 10. Related documents

- [00_project_overview.md](00_project_overview.md)
- [02_product_requirements.md](02_product_requirements.md)
- [08_testing_strategy.md](08_testing_strategy.md)
- [10_hardware_reference.md](10_hardware_reference.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)

## Phase 14 fault-injection boundaries

Phase 14 is a **deterministic fault-injection layer over the digital model**,
not hardware validation. `tests/fault_injection.py` builds simulated lamp nodes
and a Group Controller on the in-memory bus and injects readings, link faults,
storage faults and time conditions; `tests/test_fault_injection.py` contains
the scenarios (12 fault categories plus the A-J end-to-end scenarios). The
harness uses the documented hooks only and never bypasses the domain layer, and
the scenarios assert the state before the injection, the immediate response,
retry/deadline behaviour, the eventual state, the audit evidence and the fact
that unaffected nodes stayed unaffected.

What the layer demonstrates:

- injected sensor, electrical, switching-feedback, communication, command,
  fault-lifecycle, notification, storage and time faults produce the documented
  states, retries, deadlines, containment and recovery, with audit evidence;
- a corrupt or unconfirmed record is never silently lost or duplicated, and
  delivery, execution and verification remain distinct stages;
- one node's fault does not propagate to healthy nodes in a 16-node group.

What it does not demonstrate (unchanged by this phase): electrical safety,
mains wiring, isolation/creepage/clearance, EMC/RF, surge/ESD, relay life or
inrush, thermal/enclosure/IP properties, metering accuracy, physical RTC
behaviour, certification or production readiness. Injected faults are modelled
conditions, and their timing is logical time, not hardware timing.

Two open engineering questions surfaced while injecting faults; neither is
answered here and neither is a product requirement change:

1. A FORCE_ON/FORCE_OFF command whose execution is confirmed can only reach
   `ACTUAL_STATE_VERIFIED` from a *fresh* measurement. When the configured
   measurement interval is longer than the absolute command deadline, the
   command record ends `FAILED` although the node executed it. The correct
   relationship between those parameters remains open (no numeric value is
   frozen); the current bounded behaviour is pinned by a test.
2. A notification that has entered `DELIVERY_FAILED` after the configured
   retry limit rests there: a later successful delivery is not modelled as
   recovering it. Whether an operator-triggered resend path is required
   remains open; the current resting behaviour and its audit event are pinned
   by a test.

---

## Remaining model boundaries after the corrective pass

Authentication remains an asserted Actor flag/role on a trusted in-memory bus,
not peer authentication or cryptographic replay protection. Record/identity/
configuration persistence is simulated object retention across restart, not
process or hardware persistence. Repair verification is an authorized external
outcome, not proof of physical repair. Structured remote configuration,
physical calibration storage and automatic GC-link-to-managed-fault adaptation
are not completed features. The Phase 15 Master Control Center is an in-memory
data/orchestration layer over the existing controllers: it has no GUI, no
persistence, no production backend and no validated production multi-site
deployment.
See PARTIAL/PLANNED rows in requirements_traceability.md; no blanket completion
claim supersedes those limitations.
