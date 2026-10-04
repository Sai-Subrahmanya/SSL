# 14 - Phase 17 System Validation

## 1. Purpose

Phase 16 proved that the implemented subsystems **operate together**. Phase 17
asks a different question:

> Given everything implemented so far, which requirements are genuinely
> demonstrated, which remain only partially demonstrated, which are weakly or
> wrongly evidenced, and what must be fixed before the final engineering audit?

This phase is therefore a **validation phase, not a feature phase**. It added no
product behavior: the only code changes are tests. Every other change is
evidence, traceability or documentation that the audit found to be wrong,
missing or capable of being read as a stronger claim than the repository
supports.

The complete audit record, including the requirement-by-requirement disposition
of all 88 requirements, is this document; the row-level result is in
[requirements_traceability.md](requirements_traceability.md) section 10.

---

## 2. Method

| Step | What was done |
| --- | --- |
| 1. Repository audit | Branch, HEAD, parent commit, remote refs, `main` and PR #2 checked before any change; working tree confirmed to match the Phase 16 commit exactly |
| 2. Baseline | Full suite run before any edit: **639 passed** (`tests/`, 1.8 s), integration subset **38 passed** |
| 3. Requirement sweep | All 88 requirements in [02_product_requirements.md](02_product_requirements.md) matched to their matrix row, implementation module and cited tests |
| 4. Citation resolution | Every `test_file.py::test_name` in the matrix resolved against the real test modules; wrong file, non-existent name and duplicate evidence flagged |
| 5. Semantic check | Each cited test read for what it *asserts*, not for what it is named; statuses challenged individually (section 4) |
| 6. Code-vs-document check | Architecture, data model, fault lifecycle, storage, configuration, communication, time, security and scale documents read against the implementation |
| 7. Assumption and decision audit | Every assumption and decision entry checked for currency (sections 17 and 18) |
| 8. Test-quality audit | Mechanical scan plus manual reading for tautologies, internal-only assertions, duplicate bodies and tests with no assertion |
| 9. Second pass | The changed files re-read as if written by someone else (section 21), then the full suite re-run |

The mechanical parts are reproducible:

```bash
python3 -m pytest tests/                                   # 645 passed
python3 -m pytest tests/test_integration.py                # 38 passed
python3 -m pytest tests/test_system_validation.py          # 6 passed
python3 -m compileall -q src tests
pyflakes src/sslv1 tests/*.py
npx markdownlint-cli2
```

---

## 3. Requirement disposition summary

| Status | Count | Change in Phase 17 |
| --- | --- | --- |
| `VERIFIED` | 77 | No change (all 77 challenged; none downgraded) |
| `PARTIAL` | 8 | No change (each re-verified against the code) |
| `PLANNED` | 3 | No change (still not digitally validatable) |
| **Total** | **88** | |

**No requirement changed status in this phase.** Two rows were nonetheless
materially improved, because their `VERIFIED` claim rested on evidence that did
not demonstrate the claim (section 5). Both were closed with real evidence
rather than by downgrading a behavior that does exist, and the reasoning is
recorded per row in the traceability matrix.

---

## 4. Challenging the 77 `VERIFIED` rows

Every `VERIFIED` row was challenged with the same four questions:

1. **What does the requirement actually require?** (the text in `docs/02`, not
   the row title)
2. **Does a named implementation exist, and is it the only implementation?**
3. **Does the cited test fail if that implementation is broken?** (a test that
   asserts a constant, a type or an internal counter without behavior was
   treated as no evidence)
4. **Is the claim bounded by the digital model** - and is that boundary stated?

Result: **no `VERIFIED` row was found to be unsupported.** The rows that came
closest to the boundary are recorded here rather than left implicit:

| Row | Why it was challenged | Disposition |
| --- | --- | --- |
| `PR-TIME-001` - "RTC-backed local timekeeping" | The requirement says "continues to run while the node is otherwise unpowered"; a logical clock cannot prove that | Kept `VERIFIED` for the modelled semantics (local time advances with no synchronization and validity is never invented) with the physical part explicitly owned by `PR-TIME-005` (PLANNED) and `docs/09` section 6. Evidence widened. |
| `PR-STORAGE-001` - "local persistent record storage" | In-memory store; "persistent" could be read as flash | Kept `VERIFIED` bound to the modelled store; `docs/09` states persistence is simulated object retention, not hardware persistence. Evidence widened with buffering, power-loss recovery and restart retention. |
| `PR-MEASURE-003` - "energy accumulation" | The only cited test was an authorization test | **Evidence gap** - accumulation, proportionality, restart survival and authorized reset are implemented but were untested. A system-validation test now demonstrates them. |
| `PR-CONFIG-005` - "configuration persistence and versioning" | The cited test only showed that a version number travels on the wire | **Evidence gap** - an *applied* change surviving a restart was untested. A system-validation test now applies a change, restarts the node, reads it back, and proves the version persisted by refusing a stale re-use. |
| `PR-MEASURE-005`, `PR-SECURITY-005`, `PR-TIME-005` | Claim-discipline requirements; their declared verification method is inspection, not behavior | Correct as written: they constrain *what may be claimed*. They are not treated as behavioral proofs and their boundaries are stated in `docs/09`. |
| `PR-STORAGE-007` | Mixes an inspection method (physical separation) with a digital test (field audit) | Correct as written and `PARTIAL`: the digital side (configuration is separate object state from records) is tested; the physical side (separate calibration/flash medium) is not modelled. |
| `PR-COMM-002`, `PR-SCALABILITY-001`, `PR-SCALABILITY-004` | Capacity claims can drift into hardware claims | Kept `VERIFIED` for the digital sizing facts (configurable group size, 16-lamp target, no fixed 16 limit); no embedded-resource claim is made anywhere, and `PR-SCALABILITY-002` stays `PARTIAL` for the production-scale question. |

Nothing was upgraded and nothing was downgraded on the strength of "the module
exists" or "the suite passes".

---

## 5. The 8 `PARTIAL` rows, re-verified against the code

Each stated reason was checked in the implementation, not in the prose.

| Row | What is implemented (checked) | What is genuinely missing (checked) | Can digital close it? |
| --- | --- | --- | --- |
| `PR-CONFIG-001` | Configuration covers every documented parameter locally; the remote path carries an explicit integer-scalar subset, and unknown/unsupported keys are rejected rather than truncated (`lamp_node._apply_config_parameters`) | Structured schedules, group-scope mappings and clear policies are not on the bus; the time-staleness window is not a bus-carried parameter | No, not without changing the wire contract - and no such change is required by V1's digital scope |
| `PR-CONFIG-002` | `CONFIG_WRITE`/`CONFIG_ACK` with version ordering, atomic application, rejection of stale versions and readback (`CONFIG_READ`) | No MCC-side configuration writer; only readback | No; the node/controller path is complete, the operator path is intentionally read-only in this phase |
| `PR-FAULT-007` | Detection, confirmation, retention, `FAULT_REPORT` propagation, MCC summary, closure, notification state per fault | The `FAULT_REPORT` pull returns `active_faults[0]` - a single snapshot. With two confirmed faults only one propagates; a fault closed while another is the snapshot is not cleared upstream | No. Closing it means a fault-set report (wire change). Inference at the GC/MCC would either invent a clear or hide a live fault, so none was added |
| `PR-FAULT-011` | `VERIFYING` state, failed verification returning the fault to `UNDER_REPAIR`, original evidence preserved, authorization on every step (`verify_repair(..., verified: bool, evidence=...)`) | The verification *outcome* is supplied by an authorized actor; there is no automatic comparator against the original evidence, and no physical repair proof (out of digital scope by definition) | No; a physical repair cannot be established by a model |
| `PR-COMM-008` | The full FSM `COMM_HEALTHY -> RETRY -> DEGRADED -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY`, deadlines, retries, events, and end-to-end visibility at the MCC | `COMM_FAULT` is tracked as link health; it is not converted into a managed per-lamp `FaultEngine` fault with its own lifecycle | No, not without adding fault semantics that the requirements do not currently define for link loss |
| `PR-SCALABILITY-002` | Multiple groups per site with deterministic aggregation, isolation and a 64-lamp / 4-controller software run including per-lamp command routing | Production multi-site deployment: persistence, resource bounds, bus timing, hardware | No; hardware and deployment evidence is out of the digital boundary |
| `PR-STORAGE-007` | Configuration is versioned and separate from record objects; records carry their own envelope and lifecycle | No physically separate configuration/calibration medium; no calibration store | No; it is a storage-medium property |
| `PR-OFFLINE-005` | The documented `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM` sequence as one deterministic step, confirmation-gated removal, no duplicate upload, accurate failure reporting, and now an interrupted-recovery test | The *automatic trigger*: nothing in the model initiates recovery by itself, because the digital model has no background execution anywhere (polling, control cycles and timers are all caller-advanced) | Not without inventing an execution environment the rest of the prototype does not have. The requirement's substance - the sequence and no silent loss - is demonstrated; the missing piece is a scheduler, and it is recorded as such |

One clarifying result: the phrase "caller-driven recovery" is accurate but
should not be read as a per-requirement defect. **Every** time-driven behavior
in this prototype is caller-advanced (node control cycles, polling deadlines,
notification reminders, escalation). Recovery is consistent with that design,
which is why `PR-OFFLINE-005` stays `PARTIAL` for the *trigger* while the
sequence and no-loss properties are `VERIFIED`-grade evidence.

---

## 6. The 3 `PLANNED` rows

| Row | Why `PLANNED` is still correct |
| --- | --- |
| `PR-TIME-005` | Requires measuring physical RTC accuracy and backup duration. The model implements logical time semantics; a digital test cannot become a measurement of a supercapacitor-backed RTC. No substitute test was invented. |
| `PR-SECURITY-004` | Requires a tamper source. The repository has the `TAMPER` fault category and the `TAMPER_INDICATION` event, but no sensor, no tamper input and no wiring - so no behavior to test. |
| `PR-SECURITY-005` | Requires a cryptographic/security architecture that the digital prototype deliberately does not contain: authorization is an asserted actor on a trusted in-memory bus. Validating it digitally would mean inventing the mechanism and then testing the invention. |

---

## 7. Traceability audit

| Finding | Severity | Action |
| --- | --- | --- |
| `PR-IDENTITY-003` cited `test_identity.py::test_duplicate_registration_is_rejected`, which does not exist | Wrong evidence | Replaced with the real duplicate-handling tests (`test_duplicate_bus_address_is_detected`, `test_duplicate_lamp_id_is_detected`, `test_scenario_48_duplicate_registration_is_rejected`) |
| `PR-IDENTITY-004` cited `test_group_snapshot_reports_communication_state`, which does not exercise `IDENTIFY` | Wrong evidence | Replaced with `test_identity_time_heartbeat_ack_dispatch`, which asserts the `IDENTIFY_ACK` carries the node's own identity |
| `PR-MEASURE-003` and `PR-CONFIG-005` were `VERIFIED` on evidence that does not demonstrate the claim | **Evidence gap** | Real tests added (`tests/test_system_validation.py`) and cited |
| `PR-TIME-001`, `PR-STORAGE-001` had thin citations (one test each) | Weak evidence | Widened to the tests that carry the meaning (offline time validity, power-loss recovery, restart retention) |
| Seven requirements name "system validation (Phase 17)" as a verification method | Method not yet exercised | `tests/test_system_validation.py` added, section 10 of the matrix records it per row |
| Sections 9 and 10 of the matrix are consistent with the rows | - | No further change needed |
| Every other citation (≈290 references) resolved to an existing test in the named file | - | Verified mechanically; no other change |

---

## 8. Architecture consistency

The audit re-checked the single-hierarchy claim (`MCC -> Group Controller ->
Lamp Node`) and looked for a second implementation of anything:

| Concern | Finding |
| --- | --- |
| Control model | One `ControlModel` per `LampNode`; the MCC holds none |
| Fault lifecycle | One `FaultEngine` per node; the GC keeps only reported fault identity records; the MCC derives its fault view from records it received |
| Authorization | One `AuthorizationService`; the MCC calls it and adds no permission rules of its own |
| Command handling | One `CommandService`; the MCC routes through it with the original actor identity |
| Event logging | One `EventLog` per device; the MCC holds no log and reads the controllers' |
| Storage | One `RecordStore` per node/controller; the MCC has no storage engine and no second record format; `ReceivedRecord` wraps the controller's own `StorageRecord` object |
| Configuration | One configuration object per node, mutated only through the versioned, authorized write path |
| Communication | One frame codec, one sequence tracker per link, one comm state machine per node link |
| Time | One `LogicalClock`/`TimeModel` per device; no component keeps a private time of its own |
| MCC lamp state | Not stored at all - `LampRegistration` keeps identity only, and every reported value is read back from the controller (`D-041`) |

Result: **no duplicated source of truth and no competing implementation was
found.** The only state the MCC owns is the list of records it received (an
intake log, not derived state) plus the duplicate counter; both are documented
as such.

---

## 9. Fault management validation

Checked against the documented lifecycle
(`NORMAL -> SUSPECTED -> CONFIRMED -> ACKNOWLEDGED -> UNDER_REPAIR -> VERIFYING
-> CLOSED`):

| Property | Result |
| --- | --- |
| Legal transitions identical in `docs/04` and `FaultLifecycle.TRANSITIONS` | Match, including the `VERIFYING -> UNDER_REPAIR` failure return and `CLOSED -> SUSPECTED` recurrence |
| Illegal transitions rejected and non-mutating | `test_fault.py::test_illegal_fault_transitions_are_rejected` |
| Confirmation rules (count + window, hysteresis, latching) | `test_fault.py` confirmation/latching tests; configurable, nothing hardcoded |
| Recurrence links to the previous fault identity | `Fault.previous_fault_id` and the recurrence test |
| Clearing | A cleared fault is closed with its history retained; a clear record is written once per clearing, and only then |
| Repair and verification | Repair requires acknowledgement; verification is an authorized external outcome; failure returns the fault to `UNDER_REPAIR` |
| Notification independence | Notification state never changes the fault lifecycle and never changes lighting (Phase 17 test asserts this across every resting state and past every deadline) |
| Fault identity | Per-node counters, so identity is `(site, group, lamp, fault_id)`; the tests never compare fault ids across lamps |
| Timestamps | Every fault stamp comes from the device's logical clock |
| GC visibility | `FAULT_REPORT` pull (single snapshot - the `PR-FAULT-007` limit) plus buffered `FAULT` records |
| MCC visibility | Derived from received records only; the MCC cannot see an unpropagated fault, and the limitation is documented rather than hidden |
| Communication faults vs lamp faults | Kept distinct: a link fault is a `CommState` plus events, never a lamp diagnosis |
| Unknown vs unavailable | Freshness `UNKNOWN`/availability `UNKNOWN` for never-reported lamps, `UNAVAILABLE` for unreachable ones, and one unreachable lamp does not make a whole group `UNAVAILABLE` |

No fault-architecture change was made: no defect was found in the lifecycle.

---

## 10. Offline and recovery validation

The end-to-end property checked was: *local operation -> local record -> storage
-> upstream loss -> recovery -> synchronization -> upload -> confirmation ->
retained history*, with no loss, no duplicate insertion, no fabricated
timestamp and no incorrect delivery claim.

| Property | Evidence |
| --- | --- |
| Local operation with no upstream at all | `test_system_validation.py::test_local_operation_survives_a_total_supervision_outage` |
| Records accumulate while offline and stay pending | `test_group_controller.py::test_records_are_buffered_while_upstream_is_unavailable`, `test_integration.py::test_offline_cycle_buffers_everything_and_replays_it_once` |
| Nothing is removed from the queue without confirmation | `forward_upstream` marks confirmed only after `upload()` returns `True`; `mark_confirmed` then moves the record to retained |
| Interrupted replay claims nothing | `test_system_validation.py::test_recovery_interrupted_midway_claims_nothing_and_loses_nothing` |
| No duplicate insertion on re-delivery | `receive_upstream` identity set + `duplicate_uploads` counter; `test_integration.py::test_lost_confirmation_replays_without_duplicating_mcc_history` |
| Ordering | Per-device sequence order is preserved in arrival order (asserted, not assumed) |
| Unattributable record stays pending | `test_integration.py::test_offline_upload_of_an_unidentifiable_record_stays_pending` |
| Corrupt record excluded from upload and never faked upstream | `test_integration.py::test_record_recovery_discards_damage_without_faking_mcc_history` |
| Restart interaction | Retained store and pending queue survive a controller restart; in-flight commands are failed, not resurrected |
| Timestamps | Records keep the device's own logical stamp; the MCC never re-stamps what it received |

The `PR-OFFLINE-005` boundary (no autonomous trigger) is recorded in section 5.

---

## 11. Configuration validation

| Property | Evidence |
| --- | --- |
| Versioned writes; strictly newer version required | `test_integration.py::test_configuration_write_requires_privilege_and_a_newer_version`, `test_system_validation.py::test_an_applied_configuration_and_its_version_survive_a_restart` |
| Authorization on the write path, refusal before the bus | `test_configuration.py`, `test_integration.py` authorization cases |
| Atomicity: an invalid write changes nothing | `test_post_merge.py::test_invalid_config_is_atomic_and_nacks`, `test_integration.py::test_configuration_accepted_is_not_configuration_applied` |
| "Accepted" is never "applied" | Verification requires the node's `CONFIG_ACK` with the applied parameters, and the tests assert the *resulting node configuration* |
| Readback | `CONFIG_READ` -> `registration.configuration`; the MCC exposes readback only |
| Persistence boundary | Object retention across restart (tested); no separate persistent configuration medium (documented as `PR-STORAGE-007`/`PR-CONFIG-001` scope) |
| Authority | The node validates and applies; the controller distributes; the MCC routes and reads back - one configuration object per node |

---

## 12. Communication validation

| Property | Finding |
| --- | --- |
| Message types | Fixed set of 17; `RESET_ENERGY` is a `CONTROL_COMMAND` subtype, not a message type |
| Payload validation | Per-type strict payload checks; malformed payloads are rejected, counted and never silently truncated |
| Destination/version validation | Unregistered source, wrong destination and unsupported version are rejected and audited |
| Sequence handling | New/duplicate/stale classification per source, wraparound handled, per-source tracking |
| Retries and timeouts | Bounded retries inside an absolute deadline; retry exhaustion fails the command and raises the comm fault |
| Recovery | `COMM_FAULT -> RECOVERY -> COMM_HEALTHY` with a `COMM_RECOVERED` event carrying previous/current state |
| Command ACK vs actual verification | `CONTROL_ACK` is delivery/execution evidence only; success requires post-command measurement evidence |
| Determinism | Every transition is driven by an explicit call with an explicit tick; no wall-clock, no randomness, no hidden thread |

Not claimed: RS-485 electrical behaviour, baud-rate timing, collision/bias
behaviour, cable length, termination or EMC. The bus is modelled in memory.

---

## 13. Storage and logging validation

| Property | Finding |
| --- | --- |
| Sequence numbers | Monotonic per store |
| Timestamps | From the device's logical clock, with validity (`sync_state`) attached |
| Integrity | CRC over the record envelope; corruption detectable and never uploadable |
| Commit | A record is valid only when committed; power-loss discards incomplete records and keeps committed ones uploadable |
| Lifecycle | `CREATED -> STORED -> PENDING_UPLOAD -> UPLOADED -> CONFIRMED -> RETAINED` (confirmation never deletes); deletion is a separate, authorized, audited act |
| Duplicate handling | Upload identity set at the receiver; queue removal happens once |
| Retention | Automatic deletion off by default; minimum retention enforced when configured; numeric retention period is an open decision (`A-29`) |
| Configuration vs records | Separate objects; no configuration is stored inside a record, and no record is stored inside configuration |
| Power-loss model | Modelled semantics only - `docs/09` states this is not flash behaviour and no physical retention is claimed |

Documentation check: no document claims physical flash persistence. The phrase
"persistent" is used for the modelled store and is bounded in `docs/09`
section 6.

---

## 14. Time validation

| Property | Finding |
| --- | --- |
| Logical clock | Monotonic, deterministic, never moved backwards (a backwards sync is refused) |
| Timestamp source | The device clock only; no host time anywhere in the validated path |
| TIME_SYNC/TIME_ACK | The node accepts the distributed tick and acknowledges it; the controller records the ACK |
| Controller-side validity | A record the Group Controller stamps is `UNCERTAIN` until a node `TIME_ACK` has been verified (Phase 16 fix, still tested) |
| Node-side validity | Offline nodes never claim synchronized time; old samples are never rewritten |
| Uncertainty window | Configurable; a node that is not resynchronized falls out of validity and the MCC stops presenting its time as synchronized |
| Freshness | Age beyond `status_max_age_ticks` is `STALE` with availability `UNKNOWN`, never silently "current" |
| Restart | Time validity evidence is transient and is cleared by a restart |

---

## 15. Security boundary

What the digital model validates: **authorization** - an actor with a role is
permitted or refused for each action, refusals happen before the bus and are
audited, and the audit trail links actor, command, target and outcome.

What it does **not** validate, and must not be claimed anywhere:
cryptographic authentication, secure boot, key management, TLS, cryptographic
anti-replay, tamper detection, physical security, or a production permission
matrix. The communication path is a trusted in-memory bus and actors are
asserted objects; there is no peer authentication. `PR-SECURITY-004` and
`PR-SECURITY-005` remain `PLANNED`, `A-19` and `A-27` remain open/accepted, and
`docs/09` sections 4 and 5 prohibit security claims.

---

## 16. Scale validation

The scale evidence is one deterministic software run:

* 2 sites x 2 groups x 16 lamps = **64 lamps, 4 controllers**, all in one system;
* registration, per-lamp status, group and site aggregation, and per-lamp
  command routing (Phase 17 addition: one of the 64 lamps is addressed and
  exactly that lamp changes);
* fault/link isolation: one group's nodes going silent leaves the other group,
  the other site and the remaining 48 lamps healthy;
* deterministic repeatability: an identical twin system produces identical
  aggregate state and identical record sequences;
* measured wall-clock timing of one full cycle (~51 ms locally) and memory
  growth (~0.7 MB peak, recorded in
  [13_integration_validation.md](13_integration_validation.md) section 12).

These are **software measurements on the test machine**, used only as a
sanity guard (`elapsed < 10 s`). No embedded CPU, RAM, flash, bus-timing,
power or production-deployment claim is made, and
`PR-SCALABILITY-002` stays `PARTIAL` for exactly that reason.

---

## 17. Assumptions register audit

| Assumption | Status | Phase 17 finding |
| --- | --- | --- |
| `A-09` storage-full behaviour | **Open** | The model detects and reports storage-full deterministically and never silently drops a record; the *policy* (stop / overwrite / raise) is still not selected. No Phase 17 evidence resolves a policy choice. |
| `A-10` retention duration | **Open** | No numeric retention period exists; the abstraction enforces whatever floor is configured. Unchanged. |
| `A-18` switching-feedback mechanism | **Open** | The model consumes an abstract `switching_feedback`; which physical mechanism provides it is a hardware decision. Unchanged - and `PR-DIAG-003/004` remain conditional on it, as documented. |
| `A-26` physical RTC backup | **Open** | Cannot be resolved digitally; `PR-TIME-005` stays `PLANNED`. |
| `A-27` detailed permission matrix | **Accepted (deferred)** | Preliminary roles are implemented and tested; the production matrix is still deferred. No change. |
| `A-29` numeric retention period | **Open** | Same as `A-10`; supplied floors are enforced without selecting a default. |

No assumption was silently converted into a decision, and no assumption was
closed by this phase.

---

## 18. Engineering decision log audit

| Finding | Action |
| --- | --- |
| 41 decisions were recorded before this audit, all `Established`; the log showed no contradictions or superseded entries | No change to the existing entries |
| Phase 15's MCC role was recorded as `D-041` | Correct as written |
| **Phase 16 made two decisions that were implemented but not recorded in the log** | Added `D-042` (Group Controller restart persistence boundary) and `D-043` (MCC upstream record-intake semantics) with their reason, alternatives and consequences |
| Documentation-implementation divergences found | Three documents described behavior more strongly than the code delivers: `docs/05` section 8 ("`COMM_FAULT` produces a `COMMUNICATION` fault through the normal fault lifecycle"), `docs/04` section 13 (same claim in the containment table) and `docs/03` (duplicate section numbers and a duplicated status row). All corrected in this phase. |
| Decisions documented but not implemented | None found; the log's deferred items (`A-27` matrix, physical RTC, hardware candidates) are explicitly not-implemented decisions, not claims. |

---

## 19. Test-suite quality audit

A mechanical scan of all 645 tests plus manual reading:

| Check | Result |
| --- | --- |
| Tautological assertions (`assert True`, `assert x >= 0` as a non-requirement) | None found |
| Tests with no assertion | One: `test_fault.py::test_notification_tick_is_legal_from_every_resting_state`. It is a "must not raise" sweep, which is legitimate, but it asserted nothing about the result - **strengthened** with the invariant that a notification tick never changes the fault lifecycle and never leaves the notification state undefined |
| Tests asserting only private attributes | Two, both about the energy accumulator (`_energy`). The value is also published on the measurement; the new Phase 17 energy test asserts through `last_measurement.energy`, so the behavior is covered through the public surface |
| Duplicate test bodies | One pair: `test_configuration.py::test_validation_rejects_every_invalid_threshold` and `test_scenarios.py::test_scenario_44_configuration_validation`. The scenario suite intentionally restates unit behavior at scenario level; retained, not counted twice in any claim |
| Tests that bypass the real interface | None found; the harness drives real `LampNode`/`GroupController`/`MasterControlCenter` objects and pumps real frames |
| Tests whose setup forces the result | Reviewed in the fault, storage, configuration and integration suites; the suspicious patterns (asserting the value just assigned, asserting a constant) were not found in the cited evidence |
| Negative behavior | Present for unauthorized commands, wrong/failed targets, missing nodes, comm failure, stale status, fault-clear mismatch, duplicate command/record, corrupt record, restart with incomplete state, interrupted recovery and cross-site identity collision |

Tests added: **6** (`tests/test_system_validation.py`), all closing named
evidence gaps. Tests modified: `tests/test_integration.py` (scale test gained
per-lamp command routing) and `tests/test_fault.py` (invariant added to an
assertion-free test). No test was deleted, and no test count was padded.

---

## 20. Defects found and fixed in this phase

| # | Defect | Class | Fix |
| --- | --- | --- | --- |
| 1 | `PR-IDENTITY-003` cited a test that does not exist | Traceability | Citation corrected to the real duplicate-handling tests |
| 2 | `PR-IDENTITY-004` cited a test that does not exercise `IDENTIFY` | Traceability | Citation corrected to the dispatch test that asserts the identity acknowledgement |
| 3 | `PR-MEASURE-003` and `PR-CONFIG-005` were `VERIFIED` on evidence that does not demonstrate the claim | Evidence | System-validation tests added; evidence recorded per row |
| 4 | `PR-TIME-001` and `PR-STORAGE-001` cited thin evidence for broad claims | Evidence | Citations widened to the tests that carry the meaning; claim boundaries restated |
| 5 | `docs/05` section 8 and `docs/04` section 13 stated that a `COMM_FAULT` becomes a managed fault through the fault lifecycle; the code tracks link health plus events and does not create a managed fault | Documentation vs implementation | Statements corrected and pointed at the `PR-COMM-008` limitation |
| 6 | `docs/03` had duplicate section numbers (`5.5`, `11`, `12`) and a duplicated "Physical storage layout" status row | Documentation | Renumbered; duplicate row removed |
| 7 | `docs/04` had two sections numbered 12 | Documentation | Renumbered |
| 8 | The MCC's derived read-model vocabulary (availability, freshness, aggregate health) was not in the data model | Documentation | Added to `docs/03` with the "derived, never stored" rule |
| 9 | `test_notification_tick_is_legal_from_every_resting_state` asserted nothing | Test quality | Invariant added |

**No production code defect was found.** The three Phase 16 production fixes
(all-unavailable group aggregation, controller time validity, restart failing
in-flight commands) were re-verified and are unchanged and still tested. Each
fix in this phase is reviewable in the diff and covered by the suite; no
requirement was closed artificially.

---

## 21. Second-pass review

After the fixes, the changed files were re-read as if written by someone else,
specifically challenging:

* **Statuses** - would any of the corrected rows now be overstated? No: each
  corrected row's new evidence is asserted by a test that fails if the behavior
  regresses (mutation-checked by inspection of what each assertion depends on).
* **The new tests** - do they test the requirement or the implementation? The
  energy test asserts the public measurement value and the proportionality of
  accumulation, not the internal accumulator; the configuration test asserts
  the node's configuration and version, not the command record; the offline
  tests assert pending queues and the MCC's record set, not internal counters.
* **The interrupted-recovery test** - does it prove no loss, or does it just
  pass? It asserts the confirmed count equals what the link accepted, that the
  remainder stays pending, that the MCC holds no phantom receipt, and that the
  final received sequence set equals the retained store exactly.
* **Scope drift** - did Phase 17 add behavior? No: `git diff` for the phase
  touches tests and documentation only.
* **Consistency of the counts** - 639 + 6 = 645; per-file counts sum to 645;
  every count quoted in the documents was updated.

One finding from the second pass was fixed during it: the new energy test
initially asserted on the private accumulator and on a stale measurement
object after a reset; it now asserts the published value and the restarted
accumulation.

---

## 22. Digital-only validation boundary

**Proven digitally (and only in the model):** control modes and priorities,
override handling, command lifecycle and actual-state verification, fault
detection/confirmation/latching/notification/repair/verification/closure,
authorization and audit, RS-485 *logic* (framing, sequencing, duplicate/stale
handling, CRC, retry, timeout, recovery), record storage semantics (commit,
integrity, lifecycle, retention, store-and-forward), configuration versioning
and readback, time semantics (logical clock, synchronization, uncertainty,
freshness), multi-group/multi-site aggregation and isolation, and software-scale
behavior.

**Not proven - requires hardware, bench or accredited testing:** mains
behavior and isolation, creepage/clearance, EMC, surge and ESD, relay contact
life, LED inrush, thermal behavior, enclosure/IP rating, physical RTC accuracy
and backup duration, real RS-485 electrical behavior (levels, termination,
timing, long-cable behavior), RF/cellular performance, Ethernet physical layer,
metering accuracy and calibration traceability, tamper detection, certification,
and production readiness.

Nothing in this repository claims any of the second list. The prohibition is
stated in [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
sections 4-6 and repeated in every phase summary.

---

## 23. Readiness for the final engineering audit

| Question | Answer |
| --- | --- |
| Is every requirement's status justified by evidence? | Yes, after the two evidence gaps and two wrong citations were fixed |
| Are the remaining `PARTIAL` rows real gaps or documentation hedging? | Real gaps, each with a checked code location (section 5) |
| Are the `PLANNED` rows genuinely physical/external? | Yes (section 6) |
| Is there a single source of truth per concern? | Yes (section 8) |
| Is the digital boundary stated wherever a claim is made? | Yes (section 22, `docs/09`) |
| Did this phase invent work to look complete? | No - the only code changes are six evidence tests; status counts are unchanged |
| What remains outstanding before/alongside physical validation? | Fault-set reporting (`PR-FAULT-007`), automatic recovery triggering (`PR-OFFLINE-005`), structured remote configuration (`PR-CONFIG-001/002`), managed link faults (`PR-COMM-008`), separate persistent configuration/calibration storage (`PR-STORAGE-007`), production-scale evidence (`PR-SCALABILITY-002`), automatic repair verification (`PR-FAULT-011`), and the physical items in section 22 |

---

## 24. Related documents

* [requirements_traceability.md](requirements_traceability.md) - sections 9, 10
* [13_integration_validation.md](13_integration_validation.md) - Phase 16
* [08_testing_strategy.md](08_testing_strategy.md)
* [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
* [11_assumptions.md](11_assumptions.md)
* [12_engineering_decisions.md](12_engineering_decisions.md)
* [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md) - section 13

---

Phase 18 ([15_engineering_audit.md](15_engineering_audit.md)) re-audited every
claim in this report against the code and the tests as part of the final
engineering audit: the disposition (77 `VERIFIED` / 8 `PARTIAL` / 3 `PLANNED`)
and all limitations recorded here were confirmed unchanged, and the two test
corrections it made (a specific exception instead of a generic one, and an
assertion on the published energy value instead of a private attribute) are
Phase 18 test-quality fixes, not status changes.
