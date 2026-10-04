# Smart Street Light V1

A monitoring and control system for street lighting: a **Master Control
Center**, a **Group Controller** per group of lamps and a **Lamp Node** per
lamp, connected over an RS-485 field bus. The system supervises and controls
an external, existing street-light luminaire — it is not a luminaire, and it
is not a mains or hardware product.

This repository contains a **deterministic digital implementation of the
system's logic, state machines, data flow and communication behaviour**,
written in Python with no runtime dependencies. It exists to make the design
reviewable and demonstrable before any physical prototype, and it deliberately
implements no hardware.

## Overview

A street-lighting installation is organised into a hierarchy:

```text
MASTER CONTROL CENTER
        |
        |  upstream link
        |
GROUP CONTROLLER  (one per group, RS-485 master)
        |
        |  RS-485 field bus
        |
LAMP NODE 1 ... LAMP NODE N  (one per lamp)
        |
external street-lamp load  (existing luminaire, not part of this product)
```

What the system does:

* **Controls** each lamp according to a configured operating mode — automatic
  sensor control, schedule-with-sensor control or fixed schedule — with
  authorized manual override and deterministic priority resolution.
* **Measures** voltage, current, power, energy and light level per lamp, with
  explicit validity and plausibility handling.
* **Diagnoses** expected-versus-actual behaviour from combined evidence and
  manages faults through a full lifecycle: detection, confirmation, latching,
  notification, escalation, acknowledgement, repair, verification and closure.
* **Keeps working offline**: lighting control, measurement, logging and fault
  handling continue without the internet, without the Master Control Center
  and without the Group Controller.
* **Buffers and replays** records produced during a communication outage and
  delivers them upstream after recovery, without duplicates and without
  claiming delivery that did not happen.
* **Audits** every state change: commands, configuration, fault workflow and
  record deletion all record their actor and reason.

## System Architecture

The architecture has three software layers plus the bus between them. Each
layer has a single clear responsibility; no layer re-implements the layer
below it.

| Layer | Element | Responsibility |
| --- | --- | --- |
| Control layer | **Master Control Center** | Operator/control and data layer. Site → group → lamp registry and identity validation, derived status views, command forwarding, aggregation of reported records and faults, configuration readback, audit readback. Owns no persistence and no device logic. |
| Group layer | **Group Controller** | RS-485 bus master for one group. Cyclic polling of status, measurements, faults and events; per-node communication and health state; configuration distribution and time synchronisation; command forwarding and correlation; local buffering and upstream store-and-forward with post-recovery re-synchronisation. |
| Field layer | **Lamp Node** | Per-lamp control, override handling, measurement, sensor validity, diagnostics, fault lifecycle, notification, repair and verification, local event log, record storage and retention, and full local autonomy. |
| Link layer | **RS-485 bus** | Deterministic wired master/slave communication. Nodes transmit only when addressed. |
| Load | **External street-lamp load** | The existing luminaire, driver and enclosure. The system switches and monitors it; it is outside the product boundary. |

Key structural rules, enforced by the implementation:

* one owner per concern — lamp control, diagnostics, fault and notification
  lifecycle live in the Lamp Node; the Group Controller only forwards,
  correlates and buffers; the Master Control Center decides nothing that is
  already decided lower down;
* a physical ON/OFF command is successful only when a fresh measurement shows
  the expected state — transmission, receipt and acknowledgement are distinct
  from verified state;
* unknown values stay unknown — never reported as zero or as a default;
* one node's failure, fault storm or communication loss never degrades the
  rest of the group, and never switches a lamp off.

Details: [docs/architecture.md](docs/architecture.md).

## Key Features

Implemented and covered by tests (see
[docs/requirements.md](docs/requirements.md) for the requirement set and its
status):

### Lighting control

* `AUTO_SENSOR`, `AUTO_SCHEDULE_SENSOR` and `FIXED_SCHEDULE` modes, with
  hysteresis and dead-band retention.
* `FORCE_ON` / `FORCE_OFF` overrides, and a `RETURN_TO_AUTO` command that
  clears them; configured mode, active override and effective state are always
  distinguishable.
* Deterministic priority: protection (reserved), authorized override,
  automatic mode, sensor/schedule logic.
* Defined behaviour after a node or controller restart, including explicit
  failure of pending commands.

### Monitoring and diagnostics

* Voltage, current, power, energy and light-level handling with per-value
  validity, plausibility checks and a stable `None` for unavailable values.
* Multi-evidence diagnostics (command state, switching feedback, voltage,
  current, power, light level, sensor validity, communication and controller
  state) — a single reading never becomes a lamp failure.
* Engineering monitoring values only: no billing-grade or accuracy claim.

### Fault management

* Confirmation counts and windows, latching, recurrence with a new fault
  identity, and separate fault category, diagnostic classification and
  evidence.
* Full lifecycle `NORMAL → SUSPECTED → CONFIRMED → ACKNOWLEDGED → UNDER_REPAIR
  → VERIFYING → CLOSED`, with failed verification returning the fault to an
  active state and illegal transitions rejected.
* Independent notification state machine with reminders, escalation and
  delivery failure; acknowledgement is an audit action that never closes a
  fault, and notification failure never changes lighting.

### Communication

* Versioned binary protocol (version 2) with framing, addressing, CRC-16
  integrity, payload codecs, sequence tracking, duplicate and stale detection.
* Communication state machine `COMM_HEALTHY → RETRY → DEGRADED → COMM_FAULT →
  RECOVERY → COMM_HEALTHY`, with deadlines, retries and audit events.

### Storage and offline operation

* Record envelope with commit semantics, corruption detection, retention
  policy and authorized, audited deletion; automatic deletion is off by
  default.
* Store-and-forward across outages, single delivery of every record, and a
  recovery step that reports exactly what was delivered and what is still
  pending.
* Full local autonomy without the internet, the Master Control Center or the
  Group Controller.

### System-level

* Identity hierarchy (product → site → group → lamp → MCU), bus addressing,
  duplicate detection and an `IDENTIFY` handshake.
* Preliminary role-based authorization (viewer → owner) applied to every
  state-changing path, with audit records for accepted and rejected actions.
* Multi-group, multi-site aggregation with containment, exercised at
  2 sites × 2 groups × 16 lamps.

## Software Architecture

The code lives in `src/sslv1/`. Each concern has exactly one implementation.

| Module | Responsibility |
| --- | --- |
| `enums.py` | Controlled vocabularies: modes, states, fault types and severities, event types, record types, roles, permissions, message types. |
| `errors.py` | Domain exception types. |
| `identity.py` | Product/site/group/lamp/MCU identity hierarchy, bus addressing, duplicate detection. |
| `time_model.py` | Logical clock, timestamps, synchronisation state and validity. |
| `authorization.py` | Roles, permissions and the authorization service used by every mutating path. |
| `configuration.py` | Lamp configuration value object: modes, thresholds, hysteresis, schedules, intervals, fault, communication, notification and retention parameters, with validation. |
| `control.py` | Operating modes, override handling, priority resolution and hysteresis. |
| `command.py` | Command model, lifecycle (`CREATED → … → ACTUAL_STATE_VERIFIED`), duplicate suppression and command service. |
| `measurement.py` | Measurement snapshot, validity assessment and energy accumulation. |
| `diagnostics.py` | Evidence-based expected-versus-actual diagnostic rules. |
| `fault.py` | Fault model, lifecycle state machine, confirmation, repair, verification and the fault engine. |
| `notification.py` | Notification/escalation state machine and engine. |
| `event.py` | Event model and event log (the audit trail). |
| `storage.py` | Record envelope, commit semantics, retention, deletion and the record store. |
| `mcc.py` | Master Control Center: registry, derived availability/freshness/health views, aggregation, configuration readback, upstream record intake and recovery orchestration. |
| `comm/crc.py`, `comm/frame.py`, `comm/protocol.py` | Frame format, CRC-16/XMODEM, payload codecs and privileged-message actor validation. |
| `comm/sequence.py`, `comm/state_machine.py`, `comm/bus.py` | Sequence window tracking, communication state machine and the in-memory bus used by tests. |
| `nodes/lamp_node.py` | Lamp Node model: control, measurement, diagnostics, faults, notification, storage, commands, restart and autonomous operation. |
| `nodes/group_controller.py` | Group Controller model: polling, retries and deadlines, aggregation, configuration distribution, time sync, buffering and upstream re-synchronisation. |

## Repository Structure

```text
.
|-- README.md
|-- pyproject.toml                    packaging, pytest configuration, dev extra
|-- .gitignore
|-- .markdownlint-cli2.jsonc          markdown lint configuration
|-- src/
|   `-- sslv1/
|       |-- __init__.py
|       |-- authorization.py
|       |-- command.py
|       |-- configuration.py
|       |-- control.py
|       |-- diagnostics.py
|       |-- enums.py
|       |-- errors.py
|       |-- event.py
|       |-- fault.py
|       |-- identity.py
|       |-- mcc.py
|       |-- measurement.py
|       |-- notification.py
|       |-- storage.py
|       |-- time_model.py
|       |-- comm/
|       |   |-- __init__.py
|       |   |-- bus.py
|       |   |-- crc.py
|       |   |-- frame.py
|       |   |-- protocol.py
|       |   |-- sequence.py
|       |   `-- state_machine.py
|       `-- nodes/
|           |-- __init__.py
|           |-- group_controller.py
|           `-- lamp_node.py
|-- tests/
|   |-- conftest.py                   shared fixtures
|   |-- fault_injection.py            deterministic fault-injection helpers
|   |-- mcc_harness.py                multi-site / multi-group harness
|   |-- test_comm.py
|   |-- test_command.py
|   |-- test_configuration.py
|   |-- test_control.py
|   |-- test_diagnostics.py
|   |-- test_fault.py
|   |-- test_fault_injection.py
|   |-- test_group_controller.py
|   |-- test_identity.py
|   |-- test_integration.py
|   |-- test_mcc.py
|   |-- test_measurement.py
|   |-- test_regressions.py
|   |-- test_scenarios.py
|   |-- test_storage.py
|   |-- test_time.py
|   `-- test_validation.py
`-- docs/
    |-- architecture.md
    |-- system_behaviour.md
    |-- requirements.md
    |-- design_decisions.md
    |-- validation.md
    `-- hardware_reference.md
```

## Requirements

**Functional requirements** are listed with their implementation status in
[docs/requirements.md](docs/requirements.md): 88 requirements in thirteen
categories, each citing the test modules that cover it. Current status:
77 implemented, 8 partial (documented subsets), 3 planned (physical or
security properties this repository cannot implement or verify).

Two areas are recorded as product-scope gaps rather than implemented:
commissioning and node replacement (identity hierarchy, duplicate detection and
the `IDENTIFY` handshake exist; rebinding a replacement node's MCU unique ID to
an existing lamp identity is unspecified) and tamper detection (the `TAMPER`
fault category and event vocabulary exist; no tamper source exists).

### Runtime requirements

* Python 3.9 or later.
* No third-party runtime dependencies: the implementation uses the standard
  library only.

### Test requirements

* pytest 7 or later (installed by the `dev` extra).

## Installation

The package is a standard `src`-layout Python project. From the repository
root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

This installs the `sslv1` package in editable mode together with pytest. The
installation is optional for running the tests: the test configuration puts
`src/` on the import path itself, so any interpreter that already has pytest
can run the suite from the repository root without installing anything.

## Running the System

This repository is a model, not a service: it has no daemon, no server and no
entry-point script, so there is nothing to start. The system is run by
constructing the objects in a Python session or script, driving the logical
clock and stepping the nodes. The smallest useful exercise builds one Group
Controller with one Lamp Node, polls it and reads the result:

```python
from sslv1.comm import InMemoryBus
from sslv1.configuration import LampConfiguration, Schedule, TimeWindow
from sslv1.enums import LampState
from sslv1.identity import BusAddress, DeviceIdentity, Identifier, McuUniqueId
from sslv1.nodes import GroupController, GroupControllerConfig, LampNode, LampNodeSources
from sslv1.time_model import LogicalClock

DAY = 24 * 60 * 60 * 1000  # logical ticks per day

clock = LogicalClock()
bus = InMemoryBus()

node = LampNode(
    identity=DeviceIdentity(
        product_id=Identifier("SSL-V1"),
        site_id=Identifier("SITE-A"),
        group_id=Identifier("GRP-01"),
        lamp_id=Identifier("LAMP-01"),
        mcu_unique_id=McuUniqueId(bytes.fromhex("0a0b0c0d")),
    ),
    bus_address=BusAddress(1),
    config=LampConfiguration(
        lamp_id=Identifier("LAMP-01"),
        bus_address=BusAddress(1),
        site_id=Identifier("SITE-A"),
        group_id=Identifier("GRP-01"),
        product_id=Identifier("SSL-V1"),
        schedule=Schedule(day_length_ticks=DAY, windows=(TimeWindow(0, DAY - 1),)),
    ),
    clock=clock,
)
node.start(ticks=0)

# Drive the lamp with sensor/electrical inputs for one interval.
node.step(
    LampNodeSources(
        voltage=230.0,
        current=0.45,
        power=103.5,
        light_level=10.0,
        switching_feedback=LampState.ON,
    ),
    ticks=clock.ticks,
)

controller = GroupController(
    identity=DeviceIdentity(
        product_id=Identifier("SSL-V1"),
        site_id=Identifier("SITE-A"),
        group_id=Identifier("GRP-01"),
    ),
    config=GroupControllerConfig(max_nodes=16),
    clock=clock,
    bus=bus,
)
controller.register_node(node.lamp_id, node.bus_address)

controller.poll()                        # the master sends the status request
for frame in node.process_incoming():    # the node answers
    bus.send(frame)
controller.collect_responses()           # the master collects the response

print("communication:", controller.communication_summary())
print("lamp state   :", node.last_measurement.actual_state)
```

A complete lamp-control chain (command, execution, acknowledgement and
verification) and an upstream cycle are exercised end to end in
`tests/test_integration.py`, which is the best worked example of the intended
usage; `tests/test_scenarios.py` contains smaller scenarios built from the
public API. The Master Control Center is layered on top of a Group Controller
in `tests/test_mcc.py`.

Note that the model advances only when it is stepped: measurement sampling,
scheduling, polling and time synchronisation are driven by the logical clock,
and the upstream recovery step is invoked by the caller because the model has
no background scheduler.

## Running Tests

```bash
.venv/bin/python -m pytest
```

From an activated virtual environment, `python -m pytest` is equivalent. To run
a subset:

```bash
.venv/bin/python -m pytest tests/test_control.py tests/test_fault.py
.venv/bin/python -m pytest tests/test_integration.py
```

The suite is deterministic: it uses an explicit logical clock, contains no
randomness and no wall-clock or hardware dependencies.

## Validation

The suite drives the real model objects — Lamp Nodes, Group Controller, Master
Control Center, and the command, fault, notification, storage and protocol
components — with only the sensor inputs and the upstream link injected, and
verifies:

* **control**: every mode, override handling, priority, hysteresis, schedules
  and restart state;
* **commands**: the full lifecycle, duplicate suppression, authorization and
  verification against observed state rather than acknowledgement;
* **measurement and diagnostics**: validity, plausibility, energy accumulation
  and every documented diagnostic rule;
* **faults**: confirmation, latching, recurrence, notification/escalation,
  acknowledgement, repair, verification, illegal transitions and containment
  between nodes;
* **communication**: framing, integrity, addressing, sequencing, duplicates,
  staleness, retries, deadlines and the communication state machine;
* **storage**: envelope and commit semantics, corruption, retention versus
  upload confirmation, authorized deletion and power-loss recovery;
* **offline operation**: autonomy, buffering, single-delivery replay and
  interrupted recovery;
* **integration**: end-to-end command routing, fault reporting to the operator
  layer, configuration distribution and verification, restart and
  reconstruction, group/site isolation, and a 2 sites × 2 groups × 16 lamps
  run.

Committed fault-injection helpers (`tests/fault_injection.py`) drive
deterministic sensor, electrical, switching, communication, command, fault,
notification, storage and time conditions, including a simulated power loss at
every point of a record write.

All results are statements about the **model**. See
[docs/validation.md](docs/validation.md) for what the suite establishes, the
digital/physical boundary, and the open engineering items.

## System Scope

This repository is a **digital/software implementation of the system's
behaviour** — a prototype model intended for engineering review and
demonstration. It is not:

* production firmware or a released product;
* a mains, electrical or hardware design: there is no schematic, PCB, BOM,
  enclosure or harness;
* a certified or certifiable implementation of any safety, EMC, RF or
  electrical standard;
* a field deployment, cloud service, database or web application;
* a security solution: authorization is an asserted actor and role on a trusted
  bus, without cryptography or authenticated transport.

Nothing in this repository validates physical behaviour. The model does not
simulate mains safety, isolation, EMC, surge, ESD, relay endurance, LED-driver
inrush, thermal performance, enclosure or IP rating, RF behaviour, measurement
accuracy or production readiness. Those require a physical prototype and
physical test facilities; the hardware-side inputs still needed are listed in
[docs/hardware_reference.md](docs/hardware_reference.md).

## Limitations

Current, genuine limitations of the implementation:

* **Fault reporting is a single snapshot.** The upstream `FAULT_REPORT` poll
  carries one active fault, so two concurrent confirmed faults on one lamp
  cannot both be propagated, and a fault closed while another is being
  reported is not recorded as cleared upstream. A bounded fault-set report is
  the intended direction for a physical prototype; it is not implemented here.
* **No automatic recovery trigger.** The post-recovery store-and-forward
  sequence (`STORE → RECOVERY → SYNCHRONIZE → UPLOAD → CONFIRM`) is
  implemented as one deterministic step, but a caller must invoke it: there is
  no scheduler or daemon.
* **Link failures are not converted into lamp faults.** A node that stops
  communicating is tracked as link health with communication events; it is not
  turned into a managed per-lamp fault record.
* **Repair verification is externally supplied.** The `VERIFYING` state
  compares against the retained evidence of the fault and enforces the
  lifecycle, but the verification outcome comes from an authorized actor; it
  is not derived from physical repair evidence.
* **Remote configuration covers a subset.** `CONFIG_READ` / `CONFIG_WRITE`
  handle an explicit integer-scalar subset (modes, thresholds, hysteresis,
  intervals, confirmation policy, communication parameters, retention).
  Structured schedules and the remaining parameters are set locally, and the
  Master Control Center offers readback only.
* **No compliance or metering claim.** Voltage, current, power, energy and
  light level are engineering monitoring values; the model carries no
  accuracy class and no billing-grade measurement.
* **Security is preliminary.** Roles and permissions are modelled and enforced
  on every mutating path, but authentication strength, key management and
  replay protection are not implemented.
* **Scale is software-only.** Multi-site behaviour is exercised with 2 sites ×
  2 groups × 16 lamps in memory. Persistence, resource bounds and hardware
  timing are unverified.
* **Commissioning and tamper detection are unspecified.** See Requirements
  above.
* **Storage and retention are modelled, not physical.** Commit markers,
  corruption handling and deletion are logical; flash programming, wear and
  real power-failure windows are not simulated.

## License

This repository is an engineering prototype, and `pyproject.toml` declares the
package as proprietary (`Proprietary - engineering prototype`). No open-source
license is granted and no `LICENSE` file is included. Do not redistribute
without the owner's permission.
