# Smart Street Light V1 - Implementation Report

**Date:** 2026-09-26
**Branch:** `arena/01a0d86e-ssl`
**Repository:** `Sai-Subrahmanya/SSL`

---

## 1. Branch

`arena/01a0d86e-ssl`, pushed to `origin`. This is the only branch used; no
other branch was created, switched to, or deleted.

## 2. Commit SHAs

| Commit | Description |
| --- | --- |
| `b3af216` | Initial commit (README only) - pre-existing |
| `048e41c` | `docs: establish smart street light v1 engineering foundation` - Phase 0 documentation, pre-existing on the remote |
| `dd447bb` | Phase 0 documentation foundation and Phase 1 hardware-independent domain model |
| `8d08302` | Merge of `origin/arena/01a0d86e-ssl` (integrates `048e41c` without force-push or history rewrite) - **current HEAD** |

`git ls-remote origin refs/heads/arena/01a0d86e-ssl` returns `8d08302`.

> **Correction to a prior conclusion:** an earlier audit concluded that the
> Phase 0 commits were lost and that the repository was documentation-only on
> GitHub. That was wrong. `048e41c` was present on the remote and was fetched
> and merged non-destructively rather than overwritten.

## 3. Files added

**Build configuration (1):**

- `pyproject.toml` - pytest configuration with `pythonpath = ["src", "."]`

**Source, Phase 1 hardware-independent domain model (24 files):**

| File | Responsibility |
| --- | --- |
| `src/sslv1/__init__.py` | Public API re-exports |
| `src/sslv1/enums.py` | All domain enumerations (message types, modes, states, classifications) |
| `src/sslv1/errors.py` | Domain error hierarchy |
| `src/sslv1/identity.py` | Identity hierarchy: site / group / node / lamp |
| `src/sslv1/configuration.py` | Configuration objects with validation |
| `src/sslv1/control.py` | Control model: safety > override > automatic mode > sensor/schedule |
| `src/sslv1/measurement.py` | Measurement + validity |
| `src/sslv1/diagnostics.py` | Expected-versus-actual diagnostic evidence and classification |
| `src/sslv1/fault.py` | Fault model and fault lifecycle |
| `src/sslv1/notification.py` | Independent notification state machine |
| `src/sslv1/event.py` | Event model and event log |
| `src/sslv1/command.py` | Command model, `CommandService`, authorization gate |
| `src/sslv1/authorization.py` | Authorization roles and permission check |
| `src/sslv1/time_model.py` | Logical clock, time state, synchronization state, uncertainty |
| `src/sslv1/storage.py` | Storage record lifecycle and retention policy |
| `src/sslv1/comm/__init__.py` | Communication layer public API |
| `src/sslv1/comm/crc.py` | CRC-16 calculation |
| `src/sslv1/comm/frame.py` | Frame encode/decode with SOF/version/addresses/type/length/payload/sequence/CRC |
| `src/sslv1/comm/protocol.py` | Per-message-type payload codecs |
| `src/sslv1/comm/state_machine.py` | Communication state machine (response matching, timeouts, retry) |
| `src/sslv1/comm/bus.py` | Simulated multi-drop bus, addressing, duplicate handling |
| `src/sslv1/nodes/__init__.py` | Node layer public API |
| `src/sslv1/nodes/lamp_node.py` | Lamp Node behaviour |
| `src/sslv1/nodes/group_controller.py` | Group Controller with abstract local storage/buffer |

**Tests (14 files):**

`tests/conftest.py`, `tests/test_identity.py`, `tests/test_control.py`,
`tests/test_command.py`, `tests/test_measurement.py`, `tests/test_time.py`,
`tests/test_configuration.py`, `tests/test_diagnostics.py`,
`tests/test_fault.py`, `tests/test_storage.py`, `tests/test_comm.py`,
`tests/test_group_controller.py`, `tests/test_scenarios.py`.

**Tooling (2):**

- `.gitignore` - excludes `__pycache__`, build artefacts, virtualenvs, `node_modules`
- `.markdownlint-cli2.jsonc` - markdownlint configuration

**Documentation (18 files) - Phase 0, carried forward from `048e41c` and extended:**

`docs/00_project_overview.md`, `01_system_architecture.md`,
`02_product_requirements.md`, `03_data_model.md`,
`04_fault_management.md`, `05_communication_architecture.md`,
`06_storage_and_logging.md`, `07_configuration.md`,
`08_testing_strategy.md`, `09_digital_prototype_scope.md`,
`10_hardware_reference.md`, `11_assumptions.md`,
`12_engineering_decisions.md`, `requirements_traceability.md`,
`review/README.md`, `demo/README.md`.

## 4. Files modified

- `README.md` - §5 operating-mode model split into three subsections; §12
  current-status table corrected to reflect reality
- `docs/00_project_overview.md` - §7 split into persistent modes / temporary
  override states / operator command / control model
- `docs/02_product_requirements.md` - PR-LIGHT-005 design boundary;
  per-requirement status lines aligned to the traceability matrix; status
  vocabulary section added
- `docs/05_communication_architecture.md` - §9 `CONFIRM` row corrected;
  "Upload confirmation is not deletion" section added
- `docs/06_storage_and_logging.md` - duplicate section numbers fixed (7.2 -> 7.3)
- `docs/12_engineering_decisions.md` - D-007 operating-mode model; D-011
  failed-verification return state made explicit; mode-resolution consequence row
- `docs/review/README.md` - §5.3 persistent-mode count corrected; §5.5
  conditions updated to record that implementation has begun
- `src/sslv1/enums.py` - `OperatingMode` docstring corrected
- `src/sslv1/nodes/lamp_node.py` - restored a function-local import deleted by
  an unfinished edit; removed a redundant import

## 5. Documentation corrections (Part 1, 14 items)

All 14 items were incorporated and re-audited.

| # | Item | Disposition |
| --- | --- | --- |
| 1 | `RETURN_TO_AUTO` modelled as a persistent operating mode | **Fixed.** Persistent operating modes are now exactly `AUTO_SENSOR`, `AUTO_SCHEDULE_SENSOR`, `FIXED_SCHEDULE`. `FORCE_ON`/`FORCE_OFF` are temporary `active_override` states; `RETURN_TO_AUTO` is an operator command. Corrected in `README.md` §5, `docs/00` §7, D-007, PR-LIGHT-005, and the `OperatingMode` docstring. |
| 2 | "Relay feedback" terminology coupled diagnostics to an undecided hardware assumption | **Verified correct.** Zero `relay_feedback` occurrences. The abstraction `switching_feedback` is used throughout (`docs/03`, `src/sslv1/measurement.py`, `src/sslv1/diagnostics.py`, PR-MEASURE-001). Assumption A-18 is worded as "a switching-feedback mechanism is available". |
| 3 | Digital modelling implied validation of physical RTC behaviour | **Verified correct.** PR-TIME-001 carries an explicit digital-versus-physical boundary; PR-TIME-005 states physical RTC performance is not digitally validated; assumption A-26 is open. |
| 4 | Upload confirmation implied deletion of the retained record | **Fixed.** `docs/05` §9 `CONFIRM` row corrected to "Upload confirmed"; an explicit "Upload confirmation is not deletion" section added. `docs/06` §9.3 states the same rule. |
| 5 | Fault lifecycle conflated notification with fault state | **Verified correct.** Fault lifecycle is `NORMAL -> SUSPECTED -> CONFIRMED -> ACKNOWLEDGED -> UNDER_REPAIR -> VERIFYING -> CLOSED` (7 states). Notification state is a separate 7-state machine. `ESCALATED` is not a fault state. |
| 6 | `NOTIFIED` was a fault lifecycle state | **Verified correct.** Notification state is independent: `NOT_REQUIRED`, `PENDING`, `SENT`, `ACK_PENDING`, `REMINDER_DUE`, `ESCALATED`, `DELIVERY_FAILED`. |
| 7 | Retention policy without a hard minimum or authorized deletion | **Fixed and verified.** `docs/06` §7.1 documents the full retention policy model. Automatic deletion disabled by default. Deletion requires explicit authorization and produces an audit event. **No numeric retention period was invented**; A-29 remains open. |
| 8 | No operator roles defined | **Verified correct.** PR-SECURITY-006 defines `VIEWER`, `OPERATOR`, `ENGINEER`, `ADMIN`, `OWNER` conceptually; the detailed permission matrix is explicitly deferred to A-27. |
| 9 | Group Controller had no local storage/buffer capability | **Verified correct.** PR-SCALABILITY-005 specifies an abstract local storage/buffer; the physical medium is deliberately not selected (A-28). |
| 10 | `RESET_ENERGY` as a distinct message type | **Fixed and verified.** `RESET_ENERGY` is a `CONTROL_COMMAND` subtype (PR-COMM-010, D-038, `docs/05` §5). |
| 11 | `LAMP_LOAD` / `UNDER_CURRENT` treated as independent root causes | **Verified correct.** Fault category, diagnostic classification and confirmed physical root cause are separated (PR-FAULT-014, D-034). |
| 12 | `REVIEW-000` recorded as pending | **Fixed.** Recorded as `APPROVED WITH REQUIRED CORRECTIVE ACTIONS` with 10 findings, corrective actions, dispositions, residual risks and remaining open assumptions. §5.5 records that implementation has begun and that no residual risk is discharged. |
| 13 | README status did not reflect reality | **Fixed.** §5 and §12 rewritten. §12 now records the implemented source and the 266-test suite, and explicitly states that physical validation has not started. |
| 14 | Contradictory phase / status references across documents | **Fixed.** All 88 requirement status lines in `docs/02` were stale (`Proposed - not implemented`) and contradicted the traceability matrix. They now match it exactly: 84 `VERIFIED (digital prototype)`, 1 `IMPLEMENTED (digital prototype)`, 3 `Proposed - not implemented` (the three inspection/physical-only requirements). |

## 6. REVIEW-000 status

**`APPROVED WITH REQUIRED CORRECTIVE ACTIONS`**

All 10 corrective actions (RC-01 to RC-10) are implemented and re-audited. The
review record is not stated as a full approval, and it explicitly does not
claim that all engineering decisions are final. Residual risks are recorded as
open: physical RTC backup duration (A-26), numeric retention period (A-29),
storage-full behaviour (A-09), switching-feedback mechanism existence (A-18),
and the deferred role permission matrix (A-27).

## 7. Phase 1 status

**Complete (digital prototype).** The hardware-independent domain model is
implemented in `src/sslv1/` and verified by 266 deterministic tests.

| Model | Where | Status |
| --- | --- | --- |
| Identity hierarchy | `identity.py` | Implemented, tested |
| Configured mode / active override / effective mode | `control.py`, `enums.py` | Implemented, tested |
| Commanded / actual state | `measurement.py`, `enums.py` | Implemented, tested |
| Measurement + validity | `measurement.py` | Implemented, tested |
| Diagnostic evidence + classification | `diagnostics.py` | Implemented, tested |
| Fault + lifecycle | `fault.py` | Implemented, tested |
| Notification state (independent) | `notification.py` | Implemented, tested |
| Event | `event.py` | Implemented, tested |
| Command | `command.py` | Implemented, tested |
| Configuration | `configuration.py` | Implemented, tested |
| Authorization role | `authorization.py` | Implemented, tested |
| Time state | `time_model.py` | Implemented, tested |
| Storage record lifecycle | `storage.py` | Implemented, tested |
| Communication state | `comm/state_machine.py` | Implemented, tested |
| Lamp Node | `nodes/lamp_node.py` | Implemented, tested |
| Group Controller | `nodes/group_controller.py` | Implemented, tested |

**Control model** implements safety > authorized override > automatic mode >
sensor/schedule, with `light <= ON` -> ON, `light >= OFF` -> OFF, between ->
retain; `ON >= OFF` is rejected; no automatic OFF on an unacknowledged
notification.

**Command model** implements `COMMAND_SENT`, `RECEIVED`, `EXECUTED`,
`ACKNOWLEDGED`, `ACTUAL_STATE_VERIFIED`, duplicate `command_id` suppression, an
authorization gate, actor, timestamp and execution/verification results. A
command is never successful merely because it was received.

**Measurement model** carries explicit validity; measurements are engineering
monitoring values and are asserted never to be billing grade.

**Diagnostic model** provides 13 classifications (requirement was at least 10)
and makes no root-cause claims from symptoms alone.

**Fault model** uses configurable confirmation count, confirmation window,
latching and hysteresis. No "two readings" value is hardcoded.

**Storage model** keeps the pending-upload queue separate from retained
history. Automatic deletion is disabled by default. Upload confirmation never
implies deletion.

**Communication model** uses a frame with SOF, protocol version, source
address, destination address, message type, payload length, payload, sequence
number and CRC, across all 17 documented message types, with addressing,
sequence and duplicate handling, CRC checking, response matching, timeouts and
retry.

**Group Controller** has a configurable node count with a default target of 16
and an abstract local storage/buffer. One node failure does not bring down the
group.

## 8. Source files

24 files under `src/sslv1/`, listed in section 3. The domain layer imports
stdlib only - **zero external runtime dependencies**.

## 9. Tests created

14 files under `tests/`: `conftest.py` plus 12 focused modules and
`test_scenarios.py` (50 numbered end-to-end scenarios).

| Test module | Tests |
| --- | --- |
| `test_scenarios.py` | 50 |
| `test_comm.py` | 29 |
| `test_control.py` | 25 |
| `test_fault.py` | 23 |
| `test_diagnostics.py` | 23 |
| `test_group_controller.py` | 20 |
| `test_time.py` | 19 |
| `test_measurement.py` | 18 |
| `test_storage.py` | 18 |
| `test_configuration.py` | 17 |
| `test_command.py` | 13 |
| `test_identity.py` | 11 |

## 10. Tests executed

`python3 -m pytest` from the repository root, with `pytest` 9.1.1 and
`pythonpath = ["src", "."]` from `pyproject.toml`.

## 11. Test result

**266 passed, 0 failed, 0 skipped, 0 errors.**

`python3 -m pyflakes` over `src/` and `tests/` reports only three
re-export notices in `__init__.py` files (`.enums.*`, `.errors.*` star
re-exports and a duplicate `MessageType` re-export), which are intentional
public-API re-exports.

`npx markdownlint-cli2 "docs/**/*.md" "README.md"` reports **0 issues**.

Determinism was audited: no test uses `time.time`, `time.monotonic`,
`time.sleep`, `random`, `os.environ`, `datetime.now` or `uuid`.

## 12. Requirements implemented

88 requirements are defined in `docs/02_product_requirements.md`. 85 are
implemented in `src/sslv1/` (84 `VERIFIED`, 1 `IMPLEMENTED`).

## 13. Requirements digitally verified

**84 of 88** are marked `VERIFIED` in `docs/requirements_traceability.md`,
each with a named test in `tests/`. 106 test references and 20 module
references were checked to exist; none are missing.

The 3 not implemented are the physical and inspection-only requirements:

- `PR-SECURITY-004` - tamper detection (requires a physical tamper source)
- `PR-SECURITY-005` - security validation boundary (inspection)
- `PR-TIME-005` - physical RTC performance (inspection)

**No physical requirement is marked digitally verified.** `VERIFIED` here
means deterministic digital prototype behaviour only.

## 14. Remaining requirements

The 3 requirements above remain unimplemented because they are physical or
inspection-only. All other Phase 14-18 requirements remain open because their
phases have not started: fault injection, Master Control Center data layer,
full integration, system validation and the engineering audit.

## 15. Remaining assumptions

29 assumptions are registered in `docs/11_assumptions.md`, of which the
following remain **open** and are the highest-impact items:

| Assumption | Impact |
| --- | --- |
| A-09 | Storage-full behaviour undecided (stop / overwrite / buffer) - must be resolved before Phase 8 storage design is frozen |
| A-18 | A switching-feedback mechanism is assumed to exist - if none exists, `PR-DIAG-003` and `PR-DIAG-004` must be revised |
| A-26 | Physical RTC backup duration unmeasured |
| A-27 | Detailed role permission matrix deferred to a security design phase |
| A-29 | Numeric retention period and hard minimum retention undecided |

## 16. Remaining hardware / physical validation items

None of these are validated by the digital prototype, and none are claimed:

- Mains safety, PCB safety, galvanic isolation
- Creepage and clearance
- EMC (emission and immunity)
- Surge immunity, ESD immunity
- Relay lifetime and switching endurance
- LED inrush current
- Thermal behaviour
- Enclosure sealing and IP rating
- Actual RF / radio behaviour
- Product certification
- **Actual RTC backup duration**
- Tamper detection using a physical tamper source

## 17. Engineering issues discovered

| Issue | Resolution |
| --- | --- |
| An unfinished edit had deleted the function-local `encode_payload` import in `LampNode._respond`, causing a `NameError` and 16 test failures. | Import restored; 266 tests pass. |
| A redundant `encode_payload` import in `LampNode._handle_control_command`. | Removed. |
| All 88 requirement status lines read `Proposed - not implemented`, contradicting the traceability matrix. | Aligned to the matrix; status vocabulary documented. |
| `docs/06` had two sections numbered 7.2. | Renumbered to 7.2 / 7.3. |
| `docs/05` said `CONFIRM` meant "buffered records released", which reads as deletion. | Corrected to "Upload confirmed" and supplemented with an explicit non-deletion section. |
| D-011 did not state the return state after a failed verification. | Made `VERIFYING -> UNDER_REPAIR` an explicit decision with rationale; a return to `CONFIRMED` is rejected. |
| `docs/review/README.md` §5.3 listed 5 persistent operating modes including `FORCE_ON`/`FORCE_OFF`. | Corrected to 3. |
| A merge was required because the remote branch held `048e41c`. | Merged non-destructively with `-X ours`; no force push, no history rewrite, no branch deletion. The resulting tree is byte-identical to the pre-merge tree, so nothing was lost. |
| `__pycache__` directories were about to be committed. | `.gitignore` added; staged artefacts removed. |

**No genuine engineering decision, missing physical information, external
credential or purchase requirement blocked the work.** No hardware, software,
instrument or service purchase is required for anything delivered here.

## 18. Next phase

**Phase 2 - Lamp Node** is the next phase in the mandatory engineering
sequence. It is partially anticipated by the existing
`src/sslv1/nodes/lamp_node.py`, which already implements node-level behaviour
in the digital prototype; Phase 2 formalises it against the Lamp Node
requirements with the Phase 2 audit.

Phases 14-18 remain open, in order: fault injection, Master Control Center
data layer (no GUI), full integration, system validation and the engineering
audit.

The mandatory sequence is unchanged:

```text
REQUIREMENT -> ARCHITECTURE -> DESIGN -> IMPLEMENTATION -> TEST -> AUDIT -> VALIDATION
```

---

*This report describes deterministic digital prototype behaviour only. No
physical property has been validated, and no certification claim is made.*
