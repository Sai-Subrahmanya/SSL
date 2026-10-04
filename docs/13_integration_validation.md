# Phase 16 - Full Digital Integration Validation

## 1. Document purpose

This document records what Phase 16 integrated, how the end-to-end digital
behaviour is demonstrated, and exactly where the demonstrated behaviour stops.
It is the companion of
[requirements_traceability.md](requirements_traceability.md), which carries the
per-requirement evidence, and of
[09_digital_prototype_scope.md](09_digital_prototype_scope.md), which carries the
claim discipline.

Phase 16 added **no parallel architecture and no new product feature**. It
connected the existing subsystems - Master Control Center (MCC), Group
Controller (GC), Lamp Node, command service, authorization service, fault
engine, event log, record store, communication layer, configuration, time model
and offline buffering - into one executable end-to-end system, and it fixed two
genuine defects that only became visible once the layers ran together
(section 13).

The integration is **digital only**. Nothing in this document validates
electrical safety, mains behaviour, EMC/RF, surge/ESD, enclosure/IP rating,
relay lifetime, metering accuracy, physical RTC behaviour, certification or
production readiness.

---

## 2. What was integrated

Every object in the integration is a real project class. The harness
(`tests/mcc_harness.py`) constructs real `LampNode`, `GroupController` and
`MasterControlCenter` objects, shares one deterministic `LogicalClock` and one
`AuthorizationService`, and only pumps frames between them: it is a transport
stand-in on an in-memory bus, not a substitute for a subsystem. The only
stand-ins are the field devices themselves (modelled lamps) and the physical
serial link, both of which cannot exist in a digital prototype.

| Layer | Existing element used | Phase 16 role |
| --- | --- | --- |
| Operator/control layer | `src/sslv1/mcc.py` (`MasterControlCenter`) | Reads hierarchy, issues authorized control, aggregates, and now terminates the upstream link |
| Site/group aggregation | `MasterControlCenter.group_status/site_status` | Derived view over what the group controllers actually reported |
| Group layer | `src/sslv1/nodes/group_controller.py` (`GroupController`) | Polling, retries, deadlines, registration, command routing, record buffering and upload |
| Field layer | `src/sslv1/nodes/lamp_node.py` (`LampNode`) | Local control, measurement, diagnostics, fault lifecycle, notification, storage, configuration, time |
| Transport | `src/sslv1/comm/` (frame, codec, CRC, sequences, state machine, bus) | Frame exchange, duplicate/stale/malformed handling, communication states |
| Records | `src/sslv1/storage.py` (`RecordStore`) | Creation, upload lifecycle, confirmation, retention, corruption recovery |
| Authority | `src/sslv1/authorization.py`, `src/sslv1/command.py` | Role checks before transmission and the command lifecycle |

Phase 16 additions (all minimal, all in the two places the end-to-end flow was
genuinely incomplete):

| File | Addition | Why it was needed |
| --- | --- | --- |
| `src/sslv1/mcc.py` | `ReceivedRecord`, `MccUpstreamLink`, `receive_upstream`, `upstream_records`, `duplicate_uploads`, `forward_upstream`, `recover_upstream` | The GC already had an abstract `UpstreamLink`; nothing implemented its MCC end, so buffered records had no destination in the integrated system |
| `src/sslv1/mcc.py` | Group aggregation: all lamps `UNAVAILABLE` -> group `UNAVAILABLE` | A wholly unreachable group was reported as merely `DEGRADED`, understating a total group outage |
| `src/sslv1/nodes/group_controller.py` | `restart()` | The architecture promises object retention across restart; the GC had no restart path, so that promise was untested at group level |
| `src/sslv1/nodes/group_controller.py` | `resynchronize_upstream()` | Implements the documented `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM` recovery sequence as one deterministic step with a stage report |
| `src/sslv1/nodes/group_controller.py` | `COMM_RECOVERED` on node link recovery | The event vocabulary documents recovery, but the GC emitted only the degradation and never its end, leaving recovery invisible to every upstream layer |
| `src/sslv1/nodes/group_controller.py` | `_time_sync_state()` gated on a verified `TIME_ACK` | The GC stamped its own records `SYNCHRONIZED` although no synchronization had ever been performed - an invented validity claim |
| `tests/mcc_harness.py` | `upstream_factory`, `cycle`, `restart_group`, `restart_lamp`, `site_count`, `silence_group` | Lets the integration tests drive the real hierarchy deterministically |

---

## 3. The end-to-end flow

```text
MCC (operator layer)
  |  authorized command / configuration distribution / time distribution
  v
Group Controller  (per site+group)
  |  CONTROL_COMMAND / CONFIG_WRITE / TIME_SYNC / *_REQUEST frames
  v
Lamp Nodes (16 per group)
  |  local control decision, measurement, diagnostics, fault engine, events
  v
CONTROL_ACK / STATUS_RESPONSE / MEASUREMENT_RESPONSE / FAULT_REPORT / EVENT_REPORT
  |
Group Controller: registration views, records, events, retries, deadlines
  |  upstream upload -> CONFIRM
  v
MCC: received records, derived lamp/group/site aggregates
```

Two rules are preserved by every step and are asserted throughout the tests:

1. **The MCC shows only what was reported.** A lamp step that the group
   controller has not polled yet does not change the MCC view
   (`test_a_lamp_step_alone_does_not_change_the_mcc_view`), and no view is
   rebuilt from simulation internals instead of the reported values.
2. **Delivery, execution and verification stay distinct.** An ACK is not
   verification: a command is only `ACTUAL_STATE_VERIFIED` when the node's
   evidence matches the requested action
   (`test_node_restart_keeps_identity_and_configuration_and_fails_the_command`,
   `test_configuration_accepted_is_not_configuration_applied`).

### 3.1 Command path

`MCC.request_control` -> `GroupController.forward_control`
(`CommandService.submit`, role check, `CONTROL_COMMAND`) -> node authorization ->
node applies -> node ACK carrying execution status and observed state -> GC
validates the ACK against the requested action -> `ACTUAL_STATE_VERIFIED`, or
`FAILED`/`REJECTED` with a reason. Duplicate command IDs are idempotent
(`test_force_on_is_idempotent_and_never_reaches_a_second_lamp`).

### 3.2 Reporting and aggregation path

The GC polls each registered node (`STATUS_REQUEST`, `MEASUREMENT_REQUEST`,
`FAULT_REPORT`, `EVENT_REPORT`) with retries and deadlines. It stores what it
received, and the MCC derives `lamp_status`, `group_status` and `site_status`
from the registrations and records of the controllers it holds. The MCC keeps no
lamp state of its own (`test_mcc_never_becomes_the_source_of_truth_for_lamp_state`).

### 3.3 Upstream path

Records are buffered per group, uploaded through the GC's abstract upstream link
(`MccUpstreamLink` connects that link to the MCC), confirmed by the MCC and only
then removed from the pending queue - the retained copy stays. A record the MCC
cannot attribute to that group's controller is refused and stays pending at the
sender (`test_offline_upload_of_an_unidentifiable_record_stays_pending`).

---

## 4. Integration scenarios A-D

| Scenario | Test | Demonstrated behaviour |
| --- | --- | --- |
| A - normal automatic operation | `test_scenario_a_automatic_operation_from_registration_to_mcc_view`, `test_normal_operation_records_reach_the_mcc_upstream_end` | Registration in both layers, dark room switches a lamp on, bright room switches it off, status/measurement report, GC aggregation, MCC lamp/group/site view, records uploaded |
| B - FORCE_ON | `test_scenario_b_force_on_survives_the_automatic_decision`, `test_force_on_is_idempotent_and_never_reaches_a_second_lamp` | Authorized command routed to the node, override applied and verified, override survives an automatic decision, event/audit retained, MCC reports FORCE_ON |
| C - FORCE_OFF | `test_scenario_c_force_off_survives_the_automatic_decision` | Same path with the opposite state; the lamp stays off in a dark room, the other lamp keeps automatic behaviour |
| D - RETURN_TO_AUTO | `test_scenario_d_return_to_auto_resumes_automatic_control` | Override cleared, automatic control resumes and is verified, MCC reflects `AUTO_SENSOR` |

Scenario B/C/D assertions are made on: the node's own override and lamp state,
the command record state, the MCC `active_override`/`effective_mode`/
`actual_state`, and the other lamp's untouched override.

---

## 5. Fault path to the operator layer

`tests/test_integration.py`, section *FAULT -> MCC END TO END*:

- detect -> confirm (consecutive-evidence rule) -> retain locally (fault engine
  plus the node's own event history) -> `FAULT_REPORT` -> GC record ->
  MCC fault summary with site, group, lamp, category, identity, severity,
  notification state and state;
- the group/site aggregates name the faulted lamp without hiding the healthy
  ones (`DEGRADED`, not `HEALTHY` and not `UNAVAILABLE`);
- repair through the existing lifecycle (acknowledge, repair started, repaired,
  verification, closure) removes the fault from the active view while keeping
  both records readable;
- a clear is scoped to its own fault identity: repairing one lamp of two does
  not clear the other, and the cleared record remains in history;
- a fault the group never received is never presented as active;
- a fault raised while the upstream link is down is retained, uploaded after
  recovery and delivered unchanged.

### 5.1 Documented fault-reporting boundary (concurrent faults)

`docs/03` records that a lamp may hold **concurrent** faults, and the node's
fault engine really does hold more than one confirmed fault at a time. The
`FAULT_REPORT` pull, however, carries a **single active-fault snapshot**
(`docs/05`, section 5), and the payload has no fault-set form.

Consequence, pinned by
`test_concurrent_confirmed_faults_are_bounded_by_the_single_fault_report_pull`:

- with two confirmed faults on one lamp, only the first (`active_faults[0]`) is
  propagated; the second is not reported to the GC until the first is no longer
  the active snapshot;
- if the first fault is closed while the second is being reported, the GC never
  records a clear for the first identity (the node did not answer "no active
  fault"), so the MCC keeps presenting the closed fault as active next to the
  new one.

No fix was applied in Phase 16, and none was invented at the GC or MCC level: a
clear record that was never observed would be a fabricated claim, and dropping
the older identity would hide a fault that may genuinely still be active. The
correct fix is a fault-set report (a wire-contract change, therefore a later
phase, not an integration step). The MCC does not invent a record for a fault it
was never told about, and the limitation is recorded in
[requirements_traceability.md](requirements_traceability.md) as an explicit
bound on `PR-FAULT-007`.

---

## 6. Offline / store-and-forward integration

`tests/test_integration.py`, section *OFFLINE / STORE-AND-FORWARD INTEGRATION*,
covers the requested A-H grid in one deterministic run
(`test_offline_cycle_buffers_everything_and_replays_it_once`) plus the two
negative cases:

| Item | Demonstrated behaviour |
| --- | --- |
| A - loss before the event | Upstream link goes down before the new field events; failed uploads change nothing |
| B - event while offline | Lamps keep operating locally; the local change is measured and stored |
| C - records accumulate | Records accumulate per group; failed forwarding is reported as failed, not delivered |
| D - restore | Link returns; `recover_upstream` runs the documented sequence |
| E - recovered/transferred | Exactly the buffered records are replayed; the pending queue empties; confirmation is per record |
| F - MCC receives | The MCC holds the previously retained information, including the offline state change, in sequence order |
| G - duplicate delivery | Re-offering an already received record is accepted, counted as duplicate and stored once |
| H - deterministic ordering | Arrival order follows sequence order; every confirmed record stays readable in the retained history |
| Unattributable upload | A record the MCC cannot attribute to the group's controller is refused and stays pending at the sender |
| Lost confirmation | When the MCC receives a record but the confirmation is lost, the record stays pending and the retry delivers it once |

Record lifecycle after upload: `PENDING_UPLOAD -> UPLOADED -> RETAINED`
(confirmation never deletes the retained record).

---

## 7. Restart and reconstruction

Digital restart only: objects are re-initialised in memory. No physical
power-loss, brown-out, flash-retention or MCU-behaviour claim is made.

### 7.1 Group Controller restart (`GroupController.restart`)

Kept (the documented persistence model, `docs/09`): identity, configuration,
registrations, replay-sequence history, per-node communication state, and the
retained record store including the pending upload queue.

Cleared (transaction state a restarted device cannot have): queued inbound
frames, pending requests and their deadlines, in-flight command transactions
(they end `FAILED` - a dead transaction must not sit `ACKNOWLEDGED` waiting for
evidence that no longer exists), and the volatile per-node views (last
measurement, last status, last ACK payloads, awaiting-response flags). The
restart itself is audited with what it cleared (`nodes`, `cleared_requests`,
`failed_commands`).

Consequence asserted: after a restart the MCC shows `UNKNOWN` for a lamp whose
link is healthy - no stale pre-restart data is presented as current - a fresh
poll rebuilds the view, and the retained record count is unchanged. A lamp whose
link is itself degraded or faulted keeps showing `DEGRADED`/`UNAVAILABLE`,
because communication health outranks freshness in the availability rule.

### 7.2 Lamp Node restart

Kept: identity, configuration and configuration version, stored records.
Cleared: the override (documented restart default `OFF`), in-flight command
transactions (they end `FAILED` - never verified) and protection state.

### 7.3 MCC reconstruction

`test_mcc_reconstruction_from_the_same_controllers_reproduces_the_view` builds
a second `MasterControlCenter` over the same controllers and shows the same
group health, fault count, fault identity, aggregate power, lamp inventory and
site totals. The reconstruction invents nothing: it holds only what it re-read,
and its own received-record history is empty until records are uploaded again.

### 7.4 Persistence decision (no database)

Phase 16 deliberately adds **no database and no second MCC copy of state**:

- the authoritative records live in the existing per-device `RecordStore`
  objects, and the MCC's view is *derived* from the controllers it holds;
- the MCC keeps only what actually arrived upstream (`ReceivedRecord`, with
  origin and arrival order) - not a re-derived or parallel model;
- deterministic reconstruction is by re-reading the controllers, which the test
  above demonstrates;
- a durable, process-crossing store remains out of scope for the digital
  prototype (`PR-STORAGE-007` stays PARTIAL).

---

## 8. Multi-group / multi-site isolation

Demonstrated with 2 sites x 2 groups and with the same lamp/group identifiers
repeated everywhere:

- a command reaches only its addressed lamp (`test_commands_and_faults_reach_only_the_intended_group_and_lamp`);
- "LAMP-01" in two groups, and "GRP-01" in two sites, are different objects and
  different identities (`test_same_identifier_in_two_sites_is_two_different_systems`,
  `test_scale_aggregation_keeps_every_lamp_addressable`);
- a fault is associated with the correct site/group/lamp and appears in no
  other scope;
- one group's communication failure leaves the other group and the other site
  unchanged, and the site aggregate names the unhealthy group
  (`test_one_groups_link_failure_cannot_contaminate_another_group`);
- an unknown site or group cannot be queried into existence; a command to a
  missing/foreign lamp/group/site is refused before any frame is transmitted
  (`test_a_command_to_a_missing_or_foreign_target_is_refused_locally`).

---

## 9. Communication integration

The existing frame abstraction is exercised end to end, with the real GC
receiver and node receiver:

- valid command/response/report/ACK exchanges (sections 3-7);
- a malformed or wrong-destination frame and a wrong protocol version change
  nothing: no sequence state is consumed, the response is not accepted and the
  rejection is audited;
- a duplicate frame is detected, reported and not applied as a new observation;
- a silent node degrades through the communication state machine
  (`COMM_HEALTHY -> RETRY -> COMM_FAULT`), becomes `UNAVAILABLE` at the MCC
  while its neighbours stay `HEALTHY`, produces no fault claim about the lamp
  itself, and returns through `RECOVERY` to `COMM_HEALTHY` with a
  `COMM_RECOVERED` event carrying the previous and current state;
- polling uses the existing poll/deadline/retry paths, and `MCC.poll` fans out
  to the controllers rather than implementing a second poller.

No real serial or network stack is claimed; the bus is in-memory and
deterministic.

---

## 10. Configuration integration

- an authorized `CONFIG_WRITE` is distributed by the GC, applied atomically by
  the node with a version that must be newer, verified by readback
  (`CONFIG_ACK` parameters), and only then reported as `ACTUAL_STATE_VERIFIED`;
  the MCC shows the resulting configured mode;
- the configuration applies to the addressed lamp only;
- an operator without the required role is `REJECTED` before transmission and
  the node's configuration is unchanged;
- a stale version (not newer than the one in effect) is refused by the node and
  the previous valid configuration stays in effect;
- acceptance is not application: a write the node refuses ends `FAILED`, the
  previous configuration stays in effect and the readback reports
  `accepted: false`.

Not implemented (unchanged): structured schedules and the remaining
configuration fields are not carried on the bus, the MCC exposes readback only
and has no configuration writer, and configuration is held as object state, not
in a physically separate persistent store. `PR-CONFIG-001`, `PR-CONFIG-002` and
`PR-STORAGE-007` therefore stay **PARTIAL**.

---

## 11. Time and freshness integration

- before any synchronization, **no layer invents synchronized time**: the node
  stamps its samples `UNCERTAIN`, the controller stamps its own records
  `UNCERTAIN` (Phase 16 fix, section 13.2) and the MCC repeats what it received;
- a viewer cannot distribute time, and a refused attempt changes nothing;
- an authorized distribution is acknowledged (`TIME_SYNC`/`TIME_ACK`), the
  acknowledgement is validated against the requested tick, and the node records
  `TIME_SYNCHRONIZED` with `SYNCHRONIZED` validity;
- within the node's configured staleness window the samples the MCC shows carry
  `SYNCHRONIZED`; a node that is **not** re-synchronized falls out of that
  window and the MCC stops presenting its time as synchronized;
- earlier uncertain records are not rewritten when time becomes valid;
- freshness is a separate property: an unchanged value past
  `status_max_age_ticks` is `STALE` (availability `UNKNOWN`), never silently
  presented as current, and a group that never reported is `UNKNOWN`, not
  `HEALTHY`;
- all timestamps come from the logical clock; no wall-clock value is
  substituted, and event timestamps are monotonic in the recorded order.

Boundary: the staleness window is a `TimeModel` setting, not yet a configuration
parameter carried on the bus, and the GC's own stamp records "a time
distribution has been verified in this controller's lifetime" - it has no
expiry window of its own. Physical RTC retention and accuracy remain
unvalidated (`PR-TIME-005` stays PLANNED).

---

## 12. Digital / software-scale validation

`tests/test_integration.py`, section *SCALE / SOFTWARE RESOURCE BOUNDS*: two
sites x two groups x 16 lamps = **64 lamps, 4 group controllers**, plus
aggregation, polling, command routing, fault isolation and determinism checks,
and the same cycle replayed on an identical second system yields identical
aggregates and record sequence numbers.

Measured on this repository's sandbox (Python 3.11, in-memory bus; single
observation, not a benchmark and not a hardware claim):

| Observation | Value |
| --- | --- |
| Lamps registered at the MCC / nodes per controller | 64 / 16 |
| One full integrated cycle (64 lamp steps, 4 message-type poll sets per group, upstream forward) | ~51 ms, later cycles ~57 ms |
| Records per controller after one cycle | 32 (128 total), all 128 received at the MCC, 0 duplicates |
| `group_status` over 16 lamps | ~0.6 ms |
| `site_status` over 2 x 16 lamps | ~0.6 ms |
| Issuing 16 commands | ~0.2 ms each |
| Allocation during one cycle | ~0.7 MB peak (tracemalloc) |

Isolation at scale: silencing one 16-lamp group turns that group
`UNAVAILABLE` while the other group, the other site and all 32 lamps of the
other site remain `HEALTHY`.

This is **digital/software-scale validation**. It says nothing about embedded
MCU memory, RTOS timing, bus turnaround, interrupt latency or field deployment
scale. `PR-SCALABILITY-002` therefore stays **PARTIAL**.

---

## 13. Defects found and fixed by the integration

### 13.1 A group with every lamp unreachable was reported as only degraded

- **Requirement affected:** `PR-SCALABILITY-003` (failure containment and
  visibility), `PR-COMM-008`.
- **Defect:** `MasterControlCenter.group_status` classified a group as
  `DEGRADED` even when every lamp in it was `UNAVAILABLE`, understating a total
  loss of the group.
- **Consequence:** an operator could not distinguish "one lamp is late" from
  "the whole group is unreachable".
- **Fix:** all lamps unreachable -> group `UNAVAILABLE`; one unreachable lamp
  among reporting lamps stays `DEGRADED`; an all-`UNKNOWN` group is still
  `UNKNOWN` (first branch).
- **Evidence:** `test_a_silent_node_is_unavailable_at_the_mcc_while_its_neighbours_report`,
  `test_one_groups_link_failure_cannot_contaminate_another_group`,
  `test_two_sites_of_two_sixteen_lamp_groups_operate_deterministically`.

### 13.2 The Group Controller claimed synchronized time without any synchronization

- **Requirement affected:** `PR-TIME-002`, `PR-TIME-003`, `PR-TIME-004`
  (offline timestamps and validity indication).
- **Defect:** `GroupController._time_sync_state()` returned `SYNCHRONIZED`
  unconditionally, so every record the controller stamped itself claimed a time
  validity that had never been established - the same invented claim the node
  layer already refuses.
- **Consequence:** offline/GC-authored records would present unsynchronized
  time as trustworthy, and the MCC view inherits that claim.
- **Fix:** the stamp is `UNCERTAIN` until a node's `TIME_ACK` has been verified
  against the distributed tick; a controller restart clears it.
- **Evidence:** `test_time_synchronization_propagates_and_is_visible_per_lamp`,
  `test_event_and_fault_timestamps_come_from_the_logical_clock_only`.

Neither fix adds a requirement or a subsystem. Both are bounded, tested and
recorded with their evidence.

### 13.3 Corrections made by the Phase 16 self-audit

Three issues in the new Phase 16 code were found by the second-pass audit and
fixed before the phase was closed:

1. `GroupController.restart()` cleared pending requests but left in-flight
   command records in `RECEIVED`/`EXECUTED`/`ACKNOWLEDGED`, so a restarted
   controller could present a dead transaction as one still awaiting evidence.
   It now fails them (`FAILED`, reason `group controller restarted before
   verification`) and reports `failed_commands`; evidenced by
   `test_controller_restart_drops_transient_state_and_keeps_persistence`.
2. The MCC's received-record view exposed `received_ticks`, a name that implied
   the MCC re-stamps arrival time. It is now `timestamp_ticks`, documented as the
   *record's own* logical stamp - the MCC never rewrites what it received, and
   the tests assert that it receives the controller's own record object.
3. `report()`'s convergence helper could spin for 100 rounds on a lamp that had
   never sampled, because it read "the controller has no measurement" as "the
   controller is behind". A lamp with no measurement now has nothing to catch up
   to, and the "never reported" case is asserted on its own.

---

## 14. Requirement status effects

| Requirement | Before | After | Reason |
| --- | --- | --- | --- |
| `PR-FAULT-007` | VERIFIED | **PARTIAL** | The integration exercised the fault path end to end and revealed that concurrent confirmed faults cannot both be propagated by the single-snapshot `FAULT_REPORT` pull (section 5.1). A fault-set report is a later-phase wire change |
| `PR-OFFLINE-005` | PARTIAL | **PARTIAL** (limitation narrowed) | The `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM` orchestration now exists as one deterministic, stage-reporting step and is exercised end to end, including the link-still-down case; the automatic *trigger* remains unimplemented because the digital model has no background scheduler |
| `PR-COMM-008` | PARTIAL | **PARTIAL** (evidence widened) | `COMM_RECOVERED` and the DEGRADED/RECOVERY->HEALTHY path are now visible and tested at the MCC; the automatic link-fault-to-managed-fault adaptation is still not implemented |
| `PR-CONFIG-001`, `PR-CONFIG-002` | PARTIAL | **PARTIAL** (evidence widened) | End-to-end authorization, atomic application, version ordering and readback verification are now demonstrated; structured fields, an MCC write path and persistent separate configuration storage are still missing |
| `PR-STORAGE-007` | PARTIAL | **PARTIAL** (evidence widened) | Configuration remains separate object state from records; physical separation and calibration storage are still not modelled |
| `PR-SCALABILITY-002` | PARTIAL | **PARTIAL** (evidence widened) | 2 sites x 2 groups x 16 lamps now run and aggregate in one deterministic system; production deployment with persistence and resource bounds is still not implemented |
| `PR-TIME-005` | PLANNED | **PLANNED** | Physical RTC behaviour is not digitally validatable |
| `PR-SECURITY-004`, `PR-SECURITY-005` | PLANNED | **PLANNED** | No tamper source and no security validation claim in a digital model |

Summary after Phase 16: **77 VERIFIED, 8 PARTIAL, 3 PLANNED** (of 88
requirements). The 20 requirements whose verification method already cited the
Phase 16 integration test now cite real integration tests in
[requirements_traceability.md](requirements_traceability.md) section 9 (one of
them, `PR-OFFLINE-005`, keeps its PARTIAL status for the reason above), and
further rows - including `PR-TIME-002`..`PR-TIME-004`, which the time-sync fix
directly affected - gained integration evidence as well: 28 requirement rows in
total.

---

## 15. Known limitations

1. **Concurrent faults at the operator layer** (section 5.1): one snapshot per
   pull; a closed fault can remain listed as active while another fault is the
   reported one. Fix requires a fault-set report (wire change).
2. **Recovery is caller-driven**: `resynchronize_upstream` / `recover_upstream`
   implement the documented sequence, but nothing detects upstream recovery by
   itself (no background scheduler in the digital model); `PR-OFFLINE-005`
   stays PARTIAL for that reason.
3. **Configuration** is verified end to end for the integer-scalar subset;
   structured schedules, the remaining fields, an MCC write path and separate
   persistent configuration storage are not implemented
   (`PR-CONFIG-001`/`002`, `PR-STORAGE-007`).
4. **MCC state is in-memory and derived**: no database, no durable MCC store;
   reconstruction is by re-reading controllers
   (`test_mcc_reconstruction_from_the_same_controllers_reproduces_the_view`).
5. **Restart is digital object re-initialisation**: no process restart, no
   flash-retention or power-loss behaviour is modelled or claimed.
6. **The time-staleness window** is a `TimeModel` setting, not yet a
   configuration parameter on the bus, and the GC's own time stamp has no expiry
   window.
7. **Scale evidence is software-scale only** (section 12): no embedded
   resource, bus-timing or RTOS claim; `PR-SCALABILITY-002` stays PARTIAL.
8. **The upstream link is modelled**, not a network: no transport timeouts,
   retransmission windows, TLS, authentication or congestion behaviour.
9. **Security** remains an asserted actor on a trusted in-memory bus; no
   cryptography, key management, tamper detection or RF security
   (`PR-SECURITY-004`/`005` stay PLANNED).
10. **Repair verification** is an authorized external outcome, not an automatic
    evidence comparator (`PR-FAULT-011` stays PARTIAL).

---

## 16. How to run

```bash
python3 -m pytest tests/test_integration.py      # the 38 Phase 16 integration tests
python3 -m pytest                                # the full deterministic suite
```

The integration module is deterministic: one explicit logical clock, no
randomness, no wall-clock dependency in the assertions, no I/O, no hardware.

---

## 17. What this does not validate

Not validated by Phase 16, and not to be inferred from it: electrical safety,
isolation/creepage/clearance, mains behaviour, EMC/RF, surge/ESD, relay life or
inrush, thermal and enclosure/IP properties, metering accuracy, physical RTC
accuracy or backup retention, encryption/authentication, real RS-485 electrical
behaviour and timing, certification, or production readiness. Simulated
integration is not physical validation.

## 18. Phase 17 re-audit of this document

Phase 17 re-audited every claim in this document against the code and the tests
([14_system_validation.md](14_system_validation.md)). The three production
fixes, the `PR-FAULT-007` limitation and the integration evidence recorded here
were all confirmed unchanged; Phase 17 added the system-validation evidence for
the requirements that name it as their verification method and corrected four
documentation-vs-code divergences (the two link-fault statements in `docs/04`
and `docs/05`, the duplicate section numbering in `docs/03`, and the section
numbering in `docs/04`).

## 19. Related documents

- [02_product_requirements.md](02_product_requirements.md)
- [requirements_traceability.md](requirements_traceability.md)
- [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
- [08_testing_strategy.md](08_testing_strategy.md)
- [14_system_validation.md](14_system_validation.md)
- [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)
