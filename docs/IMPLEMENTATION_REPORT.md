# Smart Street Light V1 - Implementation Report

**Date:** 2026-09-26
**Branch:** `arena/01a0d86e-ssl`
**Repository:** `Sai-Subrahmanya/SSL`

> This report was corrected after an independent audit. It supersedes the
> previous version, which (a) named a stale commit as the current HEAD and
> (b) described Phases 2-13 as "next" when they were already implemented and
> tested. Both errors are fixed below. Nothing in this report is a claim of
> physical validation.

---

## 1. Branch

`arena/01a0d86e-ssl`, pushed to `origin`. This is the only branch used; no
other branch was created, switched to, or deleted, and no history was
rewritten.

## 2. Commit SHAs

| Commit | Description |
| --- | --- |
| `b3af216` | Initial commit (README only) - pre-existing |
| `048e41c` | Phase 0 documentation foundation - pre-existing on the remote |
| `dd447bb` | Phase 0 foundation + Phase 1 hardware-independent domain model |
| `8d08302` | Merge integrating `048e41c` (non-destructive; no force push) |
| `407053b` | Implementation report added - **HEAD at the start of this audit** |
| later | Corrections from this audit (see `git log`) |

`git ls-remote origin refs/heads/arena/01a0d86e-ssl` returns the current HEAD.
At the start of this audit the branch pointed at
`407053be554a8730a5cac02fce9771e6f30fea23`, **not** at `8d08302` as the
previous version of this report stated.

## 3. Files changed in this audit

**Source (4 files):**

- `src/sslv1/nodes/lamp_node.py` - fixed the `set_protection` field bug;
  `protection` is now a property over the `ControlModel`'s single instance;
  added the `RECORD_DELETED` audit event; populated
  `Fault.related_event_ids`
- `src/sslv1/nodes/group_controller.py` - added `SequenceTracker` and
  duplicate/stale frame detection in `_handle_frame`; removed the dead
  `NodeRegistration.last_fault` field and its now-unused import
- `src/sslv1/configuration.py` - `storage_full_behaviour` now defaults to
  `None` instead of naming an option
- `src/sslv1/storage.py` - added the optional `on_delete` audit hook
- `src/sslv1/notification.py` - `tick()` no longer re-enters `REMINDER_DUE`;
  `SENT` removed from the escalation-eligible tuple

**Tests (5 files):**

- `tests/test_control.py` - 10 protection regression tests
- `tests/test_group_controller.py` - 7 sequence/duplicate/replay tests
- `tests/test_storage.py` - deletion-audit and retention tests
- `tests/test_measurement.py` - `effective_mode` semantics tests
- `tests/test_fault.py` - fault-to-event association tests and 4
  notification-tick regression tests

**Documentation (9 files):**

- `README.md`, `docs/00_project_overview.md`,
  `docs/02_product_requirements.md`, `docs/03_data_model.md`,
  `docs/05_communication_architecture.md`, `docs/06_storage_and_logging.md`,
  `docs/07_configuration.md`, `docs/12_engineering_decisions.md`,
  `docs/review/README.md`, `docs/requirements_traceability.md`,
  `docs/IMPLEMENTATION_REPORT.md`

## 4. Genuine issues found

| # | Issue | Severity |
| --- | --- | --- |
| 1 | `LampNode.set_protection()` wrote `self.protection.safe_state`, but `ProtectionState` declares `forced_state` and `ControlModel.decide()` reads `forced_state`. The write landed on a dynamically-created attribute that nothing ever read, so the requested protection state was silently ignored. Every existing protection test used `LampState.OFF`, which is also the default of `forced_state`, so the bug was invisible. | **Major** |
| 2 | `PR-COMM-005` ("Sequence numbering, duplicate and replay handling", MUST) was marked `VERIFIED` with **no implementation at all**. No duplicate or out-of-window sequence detection existed anywhere. `comm/__init__.py` and `docs/05` section 6 both claimed the capability. The two tests cited as evidence (`test_unregistered_frame_is_rejected`, `test_message_type_codes_are_stable`) test addressing and code stability - neither touches a sequence number. | **Major** |
| 3 | `PR-TIME-001` was marked `IMPLEMENTED` ("not yet covered by a named test") while a named test, `test_time.py::test_clock_is_deterministic_and_monotonic`, exists and passes. | Minor (under-claim) |
| 4 | `Measurement.operating_mode` was ambiguous: it carried the **effective** mode, not the configured mode and not an override. `docs/03` section 4.2 also mislabelled `FORCE_ON`/`FORCE_OFF` as "persistent modes", and `docs/07` called the configuration field `operating_mode`. | Moderate |
| 5 | `LampConfiguration.storage_full_behaviour` defaulted to `RAISE_CONDITION_ONLY` while `docs/06` records storage-full behaviour as an **open** decision (A-09) and the enum's own docstring says "no option is selected yet". A default that names an option reads as a decision. | Moderate |
| 6 | `Fault.related_event_ids` is documented in `docs/03` section 5 as the fault-to-event association but was declared and never populated. | Moderate |
| 7 | `NodeRegistration.last_fault` was declared, never assigned and never read - a genuinely dead field. | Minor |
| 8 | Deletion of a retained record produced **no audit event**, although `PR-STORAGE-009` requires one and `docs/03` lists `RECORD_DELETED`. `RecordStore` has no event hook and nothing emitted the event. | Moderate |
| 9 | `docs/06` had two sections numbered 7.2. | Minor |
| 10 | `IMPLEMENTATION_REPORT.md` named `8d08302` as HEAD and described Phases 2-13 as "next", contradicting the README and the actual code. | Moderate |
| 11 | Phase 7 (event / logging) has **no `PR-*` requirement identifiers of its own**. The event model is implemented and exercised, but the audit-trail requirement `PR-SECURITY-003` is formally verified at Phase 15/16. | Moderate (requirements-baseline gap) |
| 12 | `NotificationEngine.tick()` raised `IllegalTransitionError` on `REMINDER_DUE -> REMINDER_DUE` whenever a confirmed fault stayed unacknowledged past `ack_reminder_interval_ticks` but before `escalation_timeout_ticks`. `LampNode.step()` calls `tick()` for every active confirmed fault on every cycle, so the node crashed on the **second** cycle after the reminder fired. Reachable, but the 295-test suite passed because no test stepped far enough past the reminder interval without acknowledging or escalating. | **Major** |
| 13 | `tick()` listed `SENT` in its escalation-eligible state tuple, but the state machine allows only `SENT -> {ACK_PENDING, DELIVERY_FAILED}`. `SENT` is transient inside `notify()` (it moves `SENT -> ACK_PENDING` atomically), so no fault ever *rests* in `SENT`; the entry was therefore unreachable rather than live, but it made the code contradict its own table. | Minor (latent) |

## 5. Fixes made

1. **Protection bug fixed at the source.** `LampNode.protection` is now a
   read-only property returning `self.control.protection`, so the node can
   never hold a second, divergent copy. `set_protection()` delegates to
   `ControlModel.set_protection()`, which writes `forced_state` - the field
   `decide()` reads. `_apply_restart_default()` clears the whole protection
   state. The dead `safe_state` write is gone. Ten regression tests were added;
   four of them fail against the old code (verified by temporarily restoring
   the bug).
2. **Duplicate/replay detection implemented.** `SequenceTracker` performs
   16-bit wrap-aware classification (`new` / `duplicate` / `stale` / `invalid`)
   per source address. `_handle_frame` checks it *before* payload decoding, so
   a repeated or replayed frame is reported rather than reprocessed. It emits
   `DUPLICATE_FRAME_DETECTED` and `STALE_FRAME_DETECTED`, which were previously
   dead event types. A reported duplicate does not count as a communication
   failure. Seven tests were added; four fail with the detection disabled.
3. **Traceability corrected.** `PR-COMM-005` now cites the seven real sequence
   tests and `group_controller.py (SequenceTracker, _handle_frame)`.
   `PR-TIME-001` is `VERIFIED`. Counts are now 85 `VERIFIED` / 0 `IMPLEMENTED`
   / 3 `PLANNED`, and `docs/02` per-requirement statuses were re-aligned.
4. **Terminology made unambiguous.** `Measurement.operating_mode` is renamed
   `effective_mode` everywhere in source, tests and the protocol payload keys,
   with a docstring stating exactly which of the three values it carries.
   `docs/03` section 4.2 now presents the canonical three-valued model
   (`configured_mode` / `active_override` / `effective_mode`) and states that
   `RETURN_TO_AUTO` is a command that appears in none of them. `docs/07` now
   uses `configured_mode`. The legacy name survives only as an explicit
   deprecation note.
5. **A-09 left open.** `storage_full_behaviour` defaults to `None`.
   `docs/06` gained section 7.4 stating that the store's raise-and-refuse
   behaviour is a simulation implementation detail, not an engineering
   decision, and must not be read as closing A-09.
6. **Documented association made real.** `_on_fault_event` appends each
   emitted event's id to `fault.related_event_ids` (deduplicated).
7. **Dead field removed** (`NodeRegistration.last_fault`) along with its
   import.
8. **Deletion is audited.** `RecordStore` takes an optional `on_delete`
   hook; `LampNode` wires it to emit `RECORD_DELETED` naming the actor and the
   record.
9. **Section numbering fixed** in `docs/06`.
10. **Phase status reconciled** - see section 6.
11. **Notification crash fixed.** `tick()` now returns without attempting a
    transition when a fault is already in `REMINDER_DUE`: re-entering the state
    is illegal, and re-emitting on every cycle would flood the event log. The
    only ways out of `REMINDER_DUE` are acknowledgement, delivery failure and
    escalation, all of which are handled elsewhere. `SENT` was removed from the
    escalation-eligible tuple because `notify()` never leaves a fault resting in
    `SENT`. Four regression tests were added
    (`test_notification_reminder_is_idempotent`,
    `test_notification_reminder_does_not_spam_events`,
    `test_notification_escalates_after_timeout_without_crash`,
    `test_notification_tick_is_legal_from_every_resting_state`); the last one
    exercises `tick()` from every resting state. Restoring either defect makes
    the suite fail, which was verified by mutation.

## 6. Phase 1-13 audited status

The audit mapped every requirement to the phase its own *verification method*
names, then checked each against real implementation modules and real tests.
A phase is `COMPLETE (digital prototype)` only when **every** requirement the
digital prototype can satisfy is `VERIFIED`.

| Phase | Name | Reqs | Verified | Status | Implementation | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Core domain model | 1 | 1 | **COMPLETE (digital prototype)** | `enums.py`, `identity.py`, `authorization.py`, `time_model.py`, `configuration.py`, `errors.py` | `test_identity.py`, `test_time.py`, `test_command.py`, `test_configuration.py` |
| 2 | Lamp Node | 3 | 3 | **COMPLETE (digital prototype)** | `nodes/lamp_node.py`, `nodes/__init__.py` | `test_group_controller.py`, `test_control.py`, `test_scenarios.py` |
| 3 | Lighting control | 7 | 7 | **COMPLETE (digital prototype)** | `control.py` | `test_control.py`, `test_scenarios.py` |
| 4 | Measurement model | 4 | 4 | **COMPLETE (digital prototype)** | `measurement.py` | `test_measurement.py`, `test_scenarios.py` |
| 5 | Diagnostics | 8 | 8 | **COMPLETE (digital prototype)** | `diagnostics.py` | `test_diagnostics.py`, `test_scenarios.py` |
| 6 | Fault lifecycle | 17 | 17 | **COMPLETE (digital prototype)** | `fault.py`, `notification.py` | `test_fault.py`, `test_scenarios.py` |
| 7 | Event / logging | 1 | 1 | **COMPLETE (digital prototype)** | `event.py` | `test_scenarios.py`, `test_command.py`, `test_fault.py` |
| 8 | Persistent storage simulation | 10 | 10 | **COMPLETE (digital prototype)** | `storage.py` | `test_storage.py`, `test_scenarios.py` |
| 9 | RS-485 protocol | 10 | 10 | **COMPLETE (digital prototype)** | `comm/` (`crc.py`, `frame.py`, `protocol.py`, `state_machine.py`, `bus.py`) | `test_comm.py`, `test_group_controller.py` |
| 10 | Group Controller | 4 | 4 | **COMPLETE (digital prototype)** | `nodes/group_controller.py` | `test_group_controller.py` |
| 11 | Communication failure / recovery | 6 | 6 | **COMPLETE (digital prototype)** | `comm/state_machine.py`, `comm/bus.py`, `nodes/group_controller.py` | `test_group_controller.py`, `test_scenarios.py` |
| 12 | Configuration | 8 | 8 | **COMPLETE (digital prototype)** | `configuration.py`, `nodes/group_controller.py` (`distribute_configuration`) | `test_configuration.py`, `test_group_controller.py` |
| 13 | Multi-node simulation | 4 | 4 | **COMPLETE (digital prototype)** | `nodes/group_controller.py`, `comm/bus.py`, `nodes/lamp_node.py` | `test_group_controller.py`, `test_scenarios.py` |

**Result: Phases 1-13 are all COMPLETE (digital prototype).** The previous
version of this report was wrong to say "Phase 2 is next".

Phase-level notes:

- **Phase 7 (event / logging):** no `PR-*` requirement identifiers are
  assigned to this phase. The event model and logging are implemented and
  exercised, but the audit-trail requirement `PR-SECURITY-003` is formally
  verified at Phase 15/16. This is a **requirements-baseline gap**, not an
  implementation gap, and is recorded as an open engineering issue.
- **Phase 14 and Phase 18** hold the three `PLANNED` requirements
  (`PR-SECURITY-004`, `PR-SECURITY-005`, `PR-TIME-005`), all of which are
  physical or inspection-only.

## 7. Requirement verification summary

| Status | Count | Meaning |
| --- | --- | --- |
| `VERIFIED` | 85 | Implemented in `src/sslv1/` and covered by a deterministic test that passes. Digital prototype only. |
| `IMPLEMENTED` | 0 | - |
| `PLANNED` | 3 | Physical-only or inspection-only: `PR-SECURITY-004` (tamper detection, needs a physical tamper source), `PR-SECURITY-005` (security validation boundary, inspection), `PR-TIME-005` (physical RTC performance, inspection). |

Total: 88 requirements. No physical-only requirement is marked digitally
verified.

## 8. Test command actually executed

```text
python3 -m pytest
```

run from the repository root, with `pytest` 9.1.1 and
`pythonpath = ["src", "."]` from `pyproject.toml`.

## 9. Exact test result

**299 passed, 0 failed, 0 skipped, 0 errors.**

Test counts by module:

| Module | Tests |
| --- | --- |
| `test_scenarios.py` | 50 |
| `test_control.py` | 35 |
| `test_comm.py` | 29 |
| `test_group_controller.py` | 27 |
| `test_storage.py` | 23 |
| `test_diagnostics.py` | 23 |
| `test_fault.py` | 29 |
| `test_measurement.py` | 21 |
| `test_configuration.py` | 19 |
| `test_time.py` | 19 |
| `test_command.py` | 13 |
| `test_identity.py` | 11 |

The suite is deterministic: no `time.time`, `time.monotonic`, `time.sleep`,
`random`, `os.environ`, `datetime.now` or `uuid` appears anywhere in `tests/`.

## 10. Static / lint result

- `python3 -m pyflakes` over `src/` and `tests/`: only three intentional
  re-export notices remain (`__init__.py` star re-exports of `.enums.*` and
  `.errors.*`, and a duplicate `MessageType` re-export in `comm/__init__.py`).
  No unused imports, no undefined names, no redefinitions.
- `npx markdownlint-cli2 "docs/**/*.md" "README.md"`: **0 issues**.
- `python3 -c "import ast; ast.parse(...)"` over every changed file: syntax OK.
- A scripted consistency check confirms every cited test and module in the
  traceability matrix exists, and that the 88 requirement statuses in
  `docs/02` match the traceability matrix exactly.

## 11. Remaining open assumptions

29 assumptions are registered in `docs/11_assumptions.md`. The following remain
**open** and are the highest-impact items:

| Assumption | Impact |
| --- | --- |
| A-09 | Storage-full behaviour undecided (stop recording / overwrite oldest / buffer in memory). Must be resolved before Phase 8 storage design is frozen. The code raises `StorageFullError` as a simulation detail only. |
| A-18 | A switching-feedback mechanism is assumed to exist. If none exists, `PR-DIAG-003` and `PR-DIAG-004` must be revised. Highest-impact assumption in the diagnostics area. |
| A-26 | Physical RTC backup duration unmeasured. |
| A-27 | Detailed role permission matrix deferred to a security design phase. |
| A-29 | Numeric retention period and hard minimum retention undecided. No numeric value is invented; the defaults are `automatic_deletion = False` and `minimum_retention_ticks = None`. |

## 12. Remaining physical-only validation

None of the following is validated by the digital prototype, and none is
claimed:

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
- **Physical RTC backup duration**
- **Physical tamper sensing**

## 13. Unresolved engineering issues

| Issue | Status |
| --- | --- |
| Phase 7 has no `PR-*` requirement identifiers of its own; the audit-trail requirement is formally verified at Phase 15/16. | **Open.** A requirements-baseline gap, not an implementation gap. Recommend adding event/logging requirements or re-pointing `PR-SECURITY-003`. |
| A-09 (storage-full behaviour) | Open. The code's behaviour is documented as a simulation detail. |
| A-18 (switching-feedback mechanism) | Open. If no mechanism exists, `PR-DIAG-003`/`PR-DIAG-004` need revision. |
| A-29 (numeric retention) | Open. |
| A-26 (RTC backup duration) | Open. |
| A-27 (role permission matrix) | Open, accepted for V1. |
| `NotificationEngine.notify()` lists `REMINDER_DUE`, `ESCALATED` and `DELIVERY_FAILED` as sources for `SENT`, but the state machine allows none of them (`SENT` is reachable only from `PENDING`). Currently unreachable because `LampNode.step()` only calls `notify()` on newly confirmed faults and `delivery_failed()` routes retries through `PENDING`. | **Open (latent).** Any future caller that re-notifies a fault already in one of those states will raise `IllegalTransitionError`. Closing it needs a decision on whether re-notification after escalation is permitted at all; that decision is deliberately **not** invented here. |

**No unresolved engineering decision, missing physical information, external
credential or purchase requirement blocked this audit.** No hardware,
software, instrument or service purchase is required for anything delivered
here.

## 14. Exact next phase

**Phase 14 - Fault injection** is the first genuinely incomplete phase.

Phases 1-13 are complete as digital prototypes and must not be rebuilt merely
because the original plan called Phase 2 "next". Phase 14 introduces
deterministic fault injection and recovery behaviour, and is also where
`PR-SECURITY-004` (tamper detection) is scheduled - which requires a physical
tamper source and therefore cannot be completed digitally.

After Phase 14: Phase 15 (Master Control Center data layer, no GUI), Phase 16
(full integration), Phase 17 (system validation), Phase 18 (engineering audit).

The mandatory sequence is unchanged:

```text
REQUIREMENT -> ARCHITECTURE -> DESIGN -> IMPLEMENTATION -> TEST -> AUDIT -> VALIDATION
```

---

*This report describes deterministic digital prototype behaviour only. No
physical property has been validated, and no certification claim is made.*
