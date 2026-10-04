# Validation

## 1. What the test suite is

The digital model is verified by a deterministic test suite in `tests/`. The
suite uses an explicit logical clock, contains no randomness, reads no
wall-clock time and touches no hardware; it drives the real model objects
(Lamp Node, Group Controller, Master Control Center, command, fault,
notification, storage and protocol components) rather than mocks. Only the
sensor inputs and the upstream link are injected, which is the abstraction the
model itself defines.

```bash
.venv/bin/python -m pytest
```

Requirements: Python 3.9+ and pytest. There are no runtime dependencies. The
suite runs in a few seconds.

Individual areas can be run on their own, for example:

```bash
.venv/bin/python -m pytest tests/test_control.py tests/test_fault.py
.venv/bin/python -m pytest tests/test_integration.py
```

## 2. Test layout

| Module | Scope |
| --- | --- |
| `test_comm.py` | Frame encoding, CRC, payload codecs, addressing, sequence and duplicate handling, communication state machine. |
| `test_command.py` | Command lifecycle, duplicate suppression, authorization, energy reset. |
| `test_configuration.py` | Configuration parameter set, value-object semantics, validation rules. |
| `test_control.py` | Operating modes, override handling, mode priority, hysteresis, schedules, restart. |
| `test_diagnostics.py` | Diagnostic rules and evidence combination. |
| `test_measurement.py` | Measurement validity, plausibility and accumulation. |
| `test_fault.py` | Fault confirmation, latching, notification, repair and verification. |
| `test_identity.py` | Identity hierarchy, bus addressing, duplicate detection. |
| `test_storage.py` | Record envelope, commit semantics, corruption, retention, deletion, power-loss recovery. |
| `test_time.py` | Logical clock, synchronisation validity, ordering. |
| `test_group_controller.py` | Polling, aggregation, retries and timeouts, buffering, recovery. |
| `test_mcc.py` | Master Control Center registry, derived views, aggregation, config readback, upstream intake. |
| `test_scenarios.py` | End-to-end scenarios built from the public domain API. |
| `test_regressions.py` | Regressions and edge cases: remote authorization, correlation, protocol metadata, deadlines, live-only readings. |
| `test_fault_injection.py` | Deterministic fault injection across sensor, electrical, switching, communication, command, fault-lifecycle, notification, storage and time conditions, plus containment checks. |
| `test_integration.py` | Whole-system integration: MCC → Group Controller → Lamp Nodes → reporting → aggregation, offline/recovery cycles, restart/reconstruction, multi-site scale, field autonomy. |
| `test_validation.py` | System-level validation of properties stated across the whole hierarchy: total supervision outage, interrupted recovery, no fault-driven shutdown, energy and configuration persistence. |
| `conftest.py`, `fault_injection.py`, `mcc_harness.py` | Shared fixtures, fault-injection helpers and the multi-site/multi-group harness. |

## 3. What is verified

The suite demonstrates, deterministically:

* **Control** — automatic sensor control, schedule and schedule-with-sensor
  control, override handling, mode priority, hysteresis and dead-band
  retention, out-of-window behaviour, restart state.
* **Commands** — the full lifecycle, duplicate suppression, authorization
  before transmission, rejection handling, and verification against observed
  state rather than against an acknowledgement.
* **Measurement** — validity and plausibility assessment, sensor-health
  handling, energy accumulation and its authorized reset.
* **Diagnostics** — each documented evidence rule, and the rule that a single
  measurement never becomes a lamp failure.
* **Faults** — confirmation counts and windows, latching under oscillation,
  recurrence with a new identity, the notification/escalation state machine,
  acknowledgement as an audit action, repair and verification, illegal
  transitions, and containment between nodes.
* **Communication** — framing, integrity, addressing, sequence windows,
  duplicates, staleness, retries, deadlines and the communication state
  machine including recovery.
* **Storage** — envelope and commit semantics, corruption detection and
  exclusion, retention versus confirmation, authorized deletion, capacity
  behaviour, and recovery from a simulated power loss.
* **Offline operation** — local operation without any supervision layer,
  buffering during an outage, single-delivery replay after recovery, and an
  interrupted replay that claims nothing it did not deliver.
* **Integration** — a command routed end to end to the addressed lamp only,
  faults reaching the operator layer, configuration applied and verified,
  restart and reconstruction, group/site isolation, and a 2 sites x 2 groups x
  16 lamps run.

## 4. Claims and the digital/physical boundary

Everything above is a statement about the **model**: logical time, an
in-memory bus, modelled devices and object-retention restarts. The following
are not established by this repository and no test result should be read as
establishing them:

| Not validated | Why |
| --- | --- |
| Mains safety, isolation, creepage and clearance | Physical design and safety engineering. |
| EMC, surge and ESD | Physical test facilities. |
| Relay contact life, LED-driver inrush, arc behaviour | Physical endurance and measurement. |
| Thermal performance, enclosure and IP rating | Physical design and test. |
| Physical RTC accuracy, drift and backup retention | Physical measurement. |
| Real RS-485 electrical behaviour and timing | Physical layer and instrumentation. |
| Ethernet and cellular RF behaviour, antenna performance, network certification | Physical RF design and accredited testing. |
| Measurement accuracy against a reference | Calibration and metrology. |
| Security properties (authentication strength, key management, cryptography, replay resistance, tamper detection) | Security design and review; the model uses an asserted actor on a trusted bus. |
| Production readiness, certification, field deployment | Everything above. |

The model also does not simulate: flash programming and wear, real power
interruption, file systems, embedded CPU/memory limits, bus turnaround, or
hardware timing. Statements about scale are statements about software
behaviour on a development machine.

## 5. Known limitations

Implementation limits that are real today and are listed against the
requirements they affect (see [requirements.md](requirements.md) section 5):

* The `FAULT_REPORT` poll carries one active-fault snapshot. Two concurrent
  confirmed faults on a lamp cannot both be propagated, and a fault closed
  while another is reported is not recorded as cleared upstream. A bounded
  fault-set report is the intended direction for the physical prototype; it is
  not implemented here.
* Automatic conversion of a GC link failure into a managed per-lamp fault
  record is not implemented; link health is reported and audited in its own
  right.
* The post-recovery upload sequence is implemented as one deterministic step
  but has no automatic trigger: there is no background scheduler or daemon, so
  recovery is detected by the caller.
* Repair verification accepts an authorized externally supplied outcome; it
  does not independently compare physical repair evidence.
* Remote configuration covers an explicit integer-scalar subset; structured
  schedules and the remaining parameters are not distributable over the bus,
  and the Master Control Center offers readback only.
* Physical separation of configuration/calibration storage is not modelled and
  calibration storage is not implemented.
* Production-scale deployment (multiple sites with persistence and resource
  bounds) is not implemented.

## 6. Open engineering items

These are undecided inputs for the physical product. They are recorded here so
that the limits of the current implementation are explicit; none of them is
implemented or simulated.

| # | Open item | Decided by |
| --- | --- | --- |
| A-05 | RS-485 baud rate (9.6 or 19.2 kbps candidates). | Hardware design; affects real cycle time. |
| A-07 | Out-of-window behaviour of schedule-with-sensor mode. | Site operating policy. |
| A-08 | Restart-default lamp state. | Site operating policy / safety review. |
| A-09 | Storage-full behaviour (stop, overwrite oldest, or raise a condition only). The model raises a condition and never overwrites. | Product policy. |
| A-10 | Target record retention duration. | Site policy and storage sizing. |
| A-11 | Fault severity scale values. | Notification/escalation design. |
| A-12 | Conditions required to clear a latched fault beyond hysteresis. | Fault policy design. |
| A-13 | Time-synchronisation cadence. | System design; affects uncertainty thresholds. |
| A-14 | Upstream link type for the Group Controller. | Hardware design. |
| A-15 | Cellular module regional variant. | Target market and certification. |
| A-16 | External flash capacity versus record volume and retention. | Storage sizing. |
| A-17 | Bus-address assignment method at commissioning. | Commissioning procedure. |
| A-18 | Physical realisation of switching feedback. | Hardware design; it is the primary evidence for switching-path diagnostics. |
| A-19 | Operator identity and authentication mechanism. | Security design. |
| A-20 | Identifier assignment process for sites, groups and lamps. | Deploying organisation. |
| A-21 | Environmental sensor set behind the `ENVIRONMENTAL` fault category. | Product scope. |
| A-22 | Measurement front-end adequacy for the intended monitoring function. | Hardware selection and calibration. |
| A-24 | Operator interface: no graphical user interface is implemented; the control layer is a logical/data layer. | Product scope decision. |
| A-26 | Physical RTC backup duration. | Hardware validation campaign. |
| A-27 | Detailed production permission matrix. | Security design. |
| A-28 | Group Controller storage medium. | Hardware design. |
| A-29 | Numeric minimum retention period. | Site policy and storage sizing. |
| A-30 | Mains safety class, protective-earth treatment and isolation boundary. | Safety decision with a qualified hardware engineer; it gates schematic capture and PCB layout. |

The V1 electrical targets — nominal 230 VAC switched lamp output, a 90–305 VAC
controller input range and a single-phase line-to-neutral scope (`A-02`,
`A-03`, `A-04`) — are documented design targets rather than open questions.
They are engineering targets, not certifications, and the input frequency
range is still to be fixed from the selected AC/DC module's datasheet.

Two further product-scope gaps are recorded rather than implemented:

* **Commissioning and node replacement** — the identity hierarchy, duplicate
  detection and `IDENTIFY` handshake exist, but how a replacement node's MCU
  unique ID is bound to an existing lamp identity, and what a factory or
  service reset means, are not specified.
* **Tamper detection** — the `TAMPER` fault category and event vocabulary exist;
  no tamper source exists to detect.

Two further decisions are pinned by tests because the current behaviour is a
documented consequence rather than a settled choice:

* **Command deadline below one measurement cycle.** Nothing in the
  configuration validation relates the absolute command deadline
  (`comm_timeout_ticks * (comm_retry_count + 1)`) to the measurement interval,
  so such a configuration executes a physical ON/OFF action but can never
  verify it, and every such command ends `FAILED`. Whether the configuration
  must be rejected, or the deadline derived from the measurement interval, is
  open (`tests/test_fault_injection.py`).
* **Undeliverable notification.** After the configured retry count the engine
  rests in `DELIVERY_FAILED` and does not escalate; escalation is driven by the
  acknowledgement timeout. Whether an undeliverable notification must also
  escalate is open (`tests/test_fault_injection.py`).

The hardware-side inputs that these items feed are listed in
[hardware_reference.md](hardware_reference.md).

## 7. Related documents

* [requirements.md](requirements.md) — requirement status and the partial/planned cases.
* [architecture.md](architecture.md) — the structures these tests exercise.
* [system_behaviour.md](system_behaviour.md) — the behaviour under test.
* [hardware_reference.md](hardware_reference.md) — what a physical prototype still needs.
