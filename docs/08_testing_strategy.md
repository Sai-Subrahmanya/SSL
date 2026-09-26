# 08 - Testing Strategy

## 1. Document purpose

This document defines how Smart Street Light V1 will be tested and validated
as the digital prototype is built, phase by phase.

It defines the **test approach**, not the test cases themselves. Test cases
are produced in the phase that implements the corresponding behaviour.

---

## 2. Validation principle

Validation follows the same discipline as development:

```text
REQUIREMENT -> ARCHITECTURE -> DESIGN -> IMPLEMENTATION -> TEST -> AUDIT -> VALIDATION
```

A requirement is not "verified" until test evidence exists and is recorded in
[requirements_traceability.md](requirements_traceability.md).

---

## 3. Test levels

| Level | Scope | Purpose |
| --- | --- | --- |
| L1 - Component test | A single module in isolation (for example one lamp node). | Verify module behaviour against its requirements. |
| L2 - Integration test | Multiple modules together (node + group controller). | Verify interaction, protocol, aggregation and containment. |
| L3 - System test | Complete simulated system (nodes + group + MCC data layer). | Verify end-to-end behaviour and requirements coverage. |
| L4 - Validation review | Documentary review against requirements. | Confirm traceability closure and absence of over-claiming. |

---

## 4. Test types

| Type | Description | Used for |
| --- | --- | --- |
| Functional | Expected input produces expected output/state. | Control, measurement, configuration. |
| State-machine | Legal and illegal transitions exercised. | Fault lifecycle, communication states, command lifecycle. |
| Negative | Invalid, malformed, out-of-range and duplicate inputs. | Protocol, configuration validation, corruption handling. |
| Fault injection | Deterministic injection of faults. | Diagnostics, fault lifecycle, containment. |
| Recovery | Fault removal and re-synchronization. | Communication recovery, store-and-forward, restart. |
| Timing / sequence | Ordering and interval behaviour. | Confirmation windows, polling, escalation timeouts. |
| Property / invariant | Invariants hold across randomized or boundary sequences. | Latching, no-silent-loss, containment. |

---

## 5. Determinism requirement

All digital prototype tests shall be **deterministic**:

- time is simulated and controllable,
- faults are injected explicitly with defined conditions,
- no test depends on wall-clock time, randomness without a fixed seed, or
  external services.

Non-deterministic tests are not acceptable as validation evidence.

---

## 6. Fault injection and recovery

The digital prototype shall support deterministic injection of at least:

| Injection | Purpose |
| --- | --- |
| Open load (ON commanded, no current) | Validate `PR-DIAG-003` and `LAMP_LOAD`. |
| Unexpected current (OFF commanded, current present) | Validate `PR-DIAG-004`. |
| Supply voltage absent | Validate `PR-DIAG-005` and `SUPPLY_VOLTAGE`. |
| Under-current / over-current bands | Validate `UNDER_CURRENT` / `OVER_CURRENT`. |
| Invalid / stuck light sensor | Validate `PR-DIAG-006` and `LIGHT_SENSOR`. |
| Threshold oscillation | Validate latching and hysteresis (`PR-FAULT-006`). |
| Node silence (no response) | Validate retry, timeout and `COMMUNICATION` fault. |
| Corrupted frames | Validate CRC handling (`PR-COMM-006`). |
| Duplicate commands / frames | Validate duplicate handling (`PR-CONTROL-003`, `PR-COMM-005`). |
| Communication loss and recovery | Validate communication state machine and store-and-forward. |
| Power loss during write | Validate commit-marker semantics (`PR-STORAGE-003`). |
| Storage corruption | Validate corruption detection (`PR-STORAGE-004`). |
| Storage full | Validate visibility of the condition (`PR-STORAGE-006`). |
| Watchdog reset / restart | Validate state restoration (`PR-CONTROL-005`). |
| Address conflict | Validate identity conflict detection (`PR-IDENTITY-003`). |
| Unauthorized command | Validate rejection and audit (`PR-SECURITY-001`, `PR-SECURITY-002`). |
| Unacknowledged notification | Validate escalation and no-auto-shutdown (`PR-FAULT-008`, `PR-FAULT-009`). |
| Failed verification | Validate return to active fault state (`PR-FAULT-011`). |

---

## 7. Phase-to-test mapping

| Phase | Primary test focus | Level |
| --- | --- | --- |
| Phase 1 - Core domain model | Entity, identifier and value-object behaviour. | L1 |
| Phase 2 - Lamp Node | Node lifecycle, identity, restart recovery. | L1 |
| Phase 3 - Lighting control | Modes, priority, override, return-to-auto. | L1, L2 |
| Phase 4 - Measurement model | Measurement set, intervals, energy accumulation, sensor validity. | L1 |
| Phase 5 - Diagnostics | Diagnostic rules and evidence combination. | L1 |
| Phase 6 - Fault lifecycle | Detection, confirmation, latching, notification, ack, repair, verification, closure. | L1, L2 |
| Phase 7 - Event / logging | Event model and local logging. | L1 |
| Phase 8 - Persistent storage simulation | Record envelope, commit, corruption, retention, store-and-forward. | L1, L2 |
| Phase 9 - RS-485 protocol | Framing, message types, sequencing, CRC, duplicates. | L1, L2 |
| Phase 10 - Group Controller | Polling, aggregation, command forwarding, retry/timeout. | L2 |
| Phase 11 - Communication failure / recovery | Communication state machine, degradation, recovery, re-sync. | L2 |
| Phase 12 - Configuration | Read/write, validation, audit, persistence, versioning. | L2 |
| Phase 13 - Multi-node simulation | Group behaviour, scalability, failure containment. | L2, L3 |
| Phase 14 - Fault injection | Deterministic injection matrix and recovery. | L2, L3 |
| Phase 15 - Master Control Center data layer | Aggregation, history, audit. | L3 |
| Phase 16 - Full integration | End-to-end behaviour. | L3 |
| Phase 17 - System validation | Requirements coverage and evidence review. | L3, L4 |
| Phase 18 - Engineering audit | Traceability closure and over-claim review. | L4 |

---

## 8. Evidence requirements

Each phase shall produce:

| Evidence | Description |
| --- | --- |
| Test results | Pass/fail per executed test, with the injected conditions. |
| Traceability update | Requirement -> implementation module -> test reference. |
| Deviation record | Any requirement not met, with reason and disposition. |
| Review note | Reviewer comments, recorded under `docs/review/`. |

### 8.1 Evidence produced for Phases 1-13

The deterministic suite now lives in [`tests/`](../tests/) and is run with
`python3 -m pytest` from the repository root. It uses only Python 3.9+ and
pytest.

| Test module | Focus |
| --- | --- |
| `tests/conftest.py` | Shared fixtures: logical clock, in-memory bus, authorization service, lamp and group identities, `make_lamp_config()`, `healthy_sources()`. |
| `tests/test_identity.py` | Identity hierarchy, deterministic identifiers, bus addressing, registration conflicts. |
| `tests/test_control.py` | Modes, priority, override, hysteresis, restart, no-auto-shutdown. |
| `tests/test_command.py` | Command lifecycle, duplicate suppression, authorization, `RESET_ENERGY` as a `CONTROL_COMMAND` subtype. |
| `tests/test_measurement.py` | Measurement field set, validity, sensor validity, wire round-trip. |
| `tests/test_diagnostics.py` | Diagnostic rules, category versus classification, determinism, no AI/ML. |
| `tests/test_fault.py` | Fault confirmation, latching, acknowledgement, repair, verification, notification independence. |
| `tests/test_storage.py` | Record lifecycle, commit markers, corruption, power loss, storage full, retention. |
| `tests/test_time.py` | Deterministic clock, synchronization and uncertainty transitions. |
| `tests/test_comm.py` | Frame structure, CRC, message types, payload codecs, bus behaviour, communication state machine. |
| `tests/test_group_controller.py` | Registration, polling, multi-node isolation, communication failure/retry/recovery, time distribution, store-and-forward. |
| `tests/test_scenarios.py` | 50 numbered end-to-end scenarios cross-referenced to requirements. |

Every `VERIFIED` entry in
[requirements_traceability.md](requirements_traceability.md) names the module
and the test that provide its evidence.

---

## 9. Coverage expectations

| Requirement category | Expected verification approach |
| --- | --- |
| `PR-LIGHT`, `PR-CONTROL` | Functional and state-machine tests. |
| `PR-MEASURE` | Functional tests with injected sensor conditions. |
| `PR-DIAG` | Functional tests per diagnostic rule. |
| `PR-FAULT` | State-machine, fault-injection and recovery tests. |
| `PR-COMM` | Protocol tests including negative and duplicate cases. |
| `PR-STORAGE` | Fault-injection and recovery tests (power loss, corruption, full). |
| `PR-TIME` | Functional tests with simulated unsynchronized periods. |
| `PR-CONFIG` | Functional and negative tests, plus audit inspection. |
| `PR-IDENTITY` | Functional tests including conflict injection. |
| `PR-SECURITY` | Negative tests plus audit inspection. |
| `PR-SCALABILITY` | Integration tests with multiple nodes and injected node failure. |
| `PR-OFFLINE` | Integration tests with communication loss and recovery. |

---

## 10. Physical validation boundary

The following are **not** testable in the digital prototype and are excluded
from all digital test claims:

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

Where a requirement models one of these behaviours (for example power-loss
safety or restart recovery), the digital test demonstrates the **modelled
logic only**. This is stated explicitly in the traceability record.

---

## 11. Entry and exit criteria

### 11.1 Phase entry criteria

- Requirements for the phase are documented and reviewed.
- Architecture for the phase is documented.
- Assumptions affecting the phase are recorded.

### 11.2 Phase exit criteria

- Implementation exists and is traceable to requirements.
- Tests exist for each requirement implemented in the phase.
- Test evidence is recorded.
- Deviations are recorded and dispositioned.
- Traceability is updated.

---

## 12. Status

| Item | Status |
| --- | --- |
| Test strategy defined | Yes |
| Fault injection matrix defined | Yes (candidate list) |
| Test identifiers / tooling | **Not defined** |
| Tests implemented | **None** (intentionally - Phase 0 only) |

---

## 13. Related documents

- [02_product_requirements.md](02_product_requirements.md)
- [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
- [requirements_traceability.md](requirements_traceability.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)

## Post-merge corrective regression evidence

Run `python -m pytest -ra` from an environment installed with `.[dev]`.
The full suite includes the unchanged baseline scenarios plus corrected
asynchronous expectations and `tests/test_post_merge.py`. Tests exercise real
node/controller bus pumps, not only codec round trips: no traffic for denied
control/configuration/time actions; asserted-role separation; pending execution;
fresh actual evidence; mismatched/late ACKs; command timeout/idempotency;
malformed-payload retransmission; bounded full-cycle sequence reuse; genuine
deadlines/retries; recovery; versioned readback; fault/notification integration;
retention, corruption and authorized deletion; and loss/retry of historical
measurement and event reports.

Old tests that equated delivery with response, or a commanded bit with actual
verification, now assert waiting first, supply observations/advance logical time,
and retain strong final-success assertions. No existing test was deleted.
The existing logical/full-suite baseline is not proof of electrical properties.
Final test/static results and audit findings are in IMPLEMENTATION_REPORT.md.
