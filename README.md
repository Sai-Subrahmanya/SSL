# Smart Street Light V1

## Repository status

### EARLY ENGINEERING / DIGITAL PROTOTYPE DEVELOPMENT

This repository contains engineering documentation and, in later phases, a
**digital prototype** (simulation) of the Smart Street Light V1 system.

It is **not** production firmware, **not** a certified product, and **not**
fitness-approved for connection to mains voltage.

---

## 1. Project title

**Smart Street Light V1** (abbreviated **SSL V1**).

---

## 2. Project purpose

Smart Street Light V1 is a **smart street-light monitoring and control
system** that interfaces with an *existing, external* street-light
luminaire.

Its purpose is to provide:

- per-lamp ON/OFF control,
- per-lamp measurement and monitoring,
- expected-versus-actual diagnostics,
- fault detection, confirmation, latching, acknowledgement and repair
  workflow,
- offline-capable local operation with store-and-forward communication,
- group-level aggregation and reporting,
- a scalable multi-lamp architecture that can be reviewed by an
  engineering/manufacturing partner (for example Minewing) as the basis for
  a physical prototype.

The long-term engineering goal is a **digitally validated** system whose
behaviour, state machines and failure handling have been demonstrated before
any physical hardware exists.

---

## 3. System boundary

### 3.1 In boundary (what this product is)

A smart street-light **monitoring and control system** attached to an
external, already-existing street-light luminaire.

### 3.2 Out of boundary (what this product is NOT, initially)

- It is **not** a complete street-light luminaire.
- It does **not** replace the lamp, driver, optics or luminaire enclosure.
- It does **not** perform billing-grade energy metering.
- It does **not** provide electrical safety, isolation, or protective
  functions for the mains network.

### 3.3 Architectural boundary of this repository

The digital prototype validates **logic, state machines, data flow and
communication behaviour**. It does not validate physical hardware.

---

## 4. Architecture at a glance

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

- Initial target: approximately **16 lamp nodes per group**.
- The architecture must remain **scalable** (more nodes per group, more
  groups per site).
- The failure of one lamp node must **not** bring down the group.

For details see
[docs/01_system_architecture.md](docs/01_system_architecture.md).

---

## 5. Operating modes

| Mode | Description |
| --- | --- |
| `AUTO_SENSOR` | Automatic operation based on measured light level. |
| `AUTO_SCHEDULE_SENSOR` | Configurable time window with sensor-based control. |
| `FIXED_SCHEDULE` | ON/OFF according to configured times. |
| `FORCE_ON` | Authorized operator forces ON. |
| `FORCE_OFF` | Authorized operator forces OFF. |
| `RETURN_TO_AUTO` | Return to the configured automatic mode. |

Priority order (highest first):

```text
1. Safety / hardware protection
2. Authorized manual override
3. Normal automatic mode
4. Sensor / schedule logic
```

---

## 6. Planned development stages

Development follows a controlled sequence. No stage is implemented before
its requirements, architecture and design are documented.

| Phase | Name | Status |
| --- | --- | --- |
| Phase 0 | Repository foundation | **In progress (this change)** |
| Phase 1 | Core domain model | Not started |
| Phase 2 | Lamp Node | Not started |
| Phase 3 | Lighting control | Not started |
| Phase 4 | Measurement model | Not started |
| Phase 5 | Diagnostics | Not started |
| Phase 6 | Fault lifecycle | Not started |
| Phase 7 | Event / logging | Not started |
| Phase 8 | Persistent storage simulation | Not started |
| Phase 9 | RS-485 protocol | Not started |
| Phase 10 | Group Controller | Not started |
| Phase 11 | Communication failure / recovery | Not started |
| Phase 12 | Configuration | Not started |
| Phase 13 | Multi-node simulation | Not started |
| Phase 14 | Fault injection | Not started |
| Phase 15 | Master Control Center data layer | Not started |
| Phase 16 | Full integration | Not started |
| Phase 17 | System validation | Not started |
| Phase 18 | Engineering audit | Not started |

See [docs/00_project_overview.md](docs/00_project_overview.md) for the full
roadmap description.

---

## 7. Digital prototype scope

### 7.1 In scope

- control logic and state machines,
- monitoring and measurement handling,
- expected-versus-actual diagnostics,
- fault detection, confirmation, latching, acknowledgement, repair and
  verification,
- communication behaviour, communication loss and recovery,
- offline operation, local logging, store-and-forward,
- configuration handling,
- event history,
- RS-485 protocol behaviour,
- multi-lamp group behaviour,
- failure containment,
- deterministic fault injection and recovery behaviour.

### 7.2 Out of scope

- mains electrical safety,
- PCB safety and layout,
- isolation, creepage and clearance,
- EMC, surge and ESD,
- relay lifetime,
- LED inrush behaviour,
- thermal performance of real hardware,
- enclosure and IP rating,
- actual RF performance,
- certification.

See [docs/09_digital_prototype_scope.md](docs/09_digital_prototype_scope.md).

---

## 8. Physical validation boundary

The intended workflow is:

```text
Digital engineering
      -> internal validation
      -> engineering package
      -> Minewing engineering review
      -> physical prototype
      -> physical validation
      -> iteration
```

Nothing in this repository substitutes for physical engineering validation.
Hardware components referenced anywhere in the documentation are
**engineering candidates**, not production-frozen selections.

---

## 9. No-certification disclaimer

> **No certification, safety approval, regulatory approval, or compliance
> claim of any kind is made or implied by this repository.**
>
> All content is early engineering documentation and/or digital prototype
> work. Terms such as "validated" in this repository refer to **digital
> validation of modelled behaviour only**, unless a document explicitly and
> separately states otherwise.

---

## 10. Repository layout

```text
.
|-- README.md                                  This file
|-- .markdownlint-cli2.jsonc                   Markdown lint configuration (docs only)
`-- docs/
    |-- 00_project_overview.md                 Purpose, scope, roadmap, glossary
    |-- 01_system_architecture.md              Architecture baseline
    |-- 02_product_requirements.md             Structured requirements (PR-*)
    |-- 03_data_model.md                       Future data model
    |-- 04_fault_management.md                 Fault model and fault lifecycle
    |-- 05_communication_architecture.md       RS-485 and communication state
    |-- 06_storage_and_logging.md              Storage and logging behaviour
    |-- 07_configuration.md                    Configuration model
    |-- 08_testing_strategy.md                 Test and validation strategy
    |-- 09_digital_prototype_scope.md          Digital prototype in/out of scope
    |-- 10_hardware_reference.md               Hardware candidates (not final)
    |-- 11_assumptions.md                      Assumptions register
    |-- 12_engineering_decisions.md            Engineering decision log
    |-- requirements_traceability.md           Requirement -> architecture -> test
    |-- review/                                Independent technical review records
    `-- demo/                                  Demonstration material
```

---

## 11. How this repository will evolve

1. **Documentation first.** Requirements are written before architecture,
   architecture before design, design before implementation.
2. **Traceability.** Every future implementation element must be traceable
   to at least one `PR-*` requirement.
3. **Controlled phases.** Implementation proceeds phase by phase
   (Phase 1 onward), each phase ending with test evidence and an audit
   record.
4. **Explicit assumptions.** Anything not yet decided is recorded in
   [docs/11_assumptions.md](docs/11_assumptions.md) rather than silently
   assumed.
5. **Review.** Significant decisions are recorded in
   [docs/12_engineering_decisions.md](docs/12_engineering_decisions.md) and
   reviewed in [docs/review/](docs/review/).

The mandatory engineering sequence is:

```text
REQUIREMENT -> ARCHITECTURE -> DESIGN -> IMPLEMENTATION -> TEST -> AUDIT -> VALIDATION
```

---

## 12. Current status summary

| Item | Status |
| --- | --- |
| Repository foundation | Complete |
| Requirements baseline | Drafted for review |
| Architecture baseline | Drafted for review |
| Assumptions register | Drafted for review |
| Engineering decision log | Initial entries only |
| Requirements traceability | Structure established; implementation/test references `TBD` |
| Simulation code | **Not started (intentionally)** |

---

## 13. Related documents

- [docs/00_project_overview.md](docs/00_project_overview.md)
- [docs/01_system_architecture.md](docs/01_system_architecture.md)
- [docs/02_product_requirements.md](docs/02_product_requirements.md)
- [docs/11_assumptions.md](docs/11_assumptions.md)
- [docs/12_engineering_decisions.md](docs/12_engineering_decisions.md)
- [docs/requirements_traceability.md](docs/requirements_traceability.md)
