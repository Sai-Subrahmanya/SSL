# Smart Street Light V1 — Corrective Implementation and Audit Report

Date: 2026-09-26 (Phase 15 addition: 2026-10-04, section 11). Scope: **digital engineering prototype only**.

## 1. Provenance and assessment

The audit started from actual GitHub main
`9e2fa26f46de421afbd432d65d580a44314d7129`, verified with git ls-remote.
The session branch is `arena/01a0dcf6-ssl`. The previous unpublished corrective
commit was not used. Main is not modified by this pass.

The unchanged baseline passed **302 tests**, yet direct executions demonstrated
unauthorized remote control/configuration, premature ACTUAL_STATE_VERIFIED,
sequence poisoning, broken configuration reads and other integration defects.
Passing tests were therefore treated as evidence to inspect, not as proof of
correctness. Existing tests that encoded these defects have corrected
expectations, not weaker final assertions.

The corrected model is suitable for further **digital engineering review**,
not production deployment. The requirement matrix now distinguishes **78
VERIFIED digital behaviors, 7 PARTIAL requirements, and 3 PLANNED requirements**.
The partial scope is explicit in section 7; this report does not claim that
all V1 product functionality or hardware has been completed.

Process deviation: implementation began before the requested complete audit-first
gate had finished. The subsequent full review and separate final diff pass do
not retroactively satisfy that ordering constraint; this deviation is disclosed,
not presented as compliant sequencing.

## 2. Repository-wide audit coverage

The review covered the repository tree, runtime modules, tests, project/check
configuration and the requirements/design/assumption/decision/traceability
set. Execution paths were traced across both nodes rather than inferred from
filenames or prior reports.

| Area | Review paths and evidence |
| --- | --- |
| Authorization and commands | Actor/role mapping, command/subtype consistency, duplicates/conflicts, local/remote submission, execution, deferred observation, ACK correlation, late response, timeout and reset |
| Control/configuration | All three automatic modes, overrides/protection priority, exclusive schedule bounds, aggregate transitions, configured-mode ownership, numeric hysteresis, every configuration field and consumer |
| Protocol/bus | All 17 enums/codecs and directional handlers; version/CRC, strict decoding, source/destination, both receivers' sequence state, full-cycle reuse, retry caches and report confirmation |
| Group Controller | Unique addressing, 16/24-node tests, independent pending requests, real logical deadlines, retries/exhaustion/recovery, aggregation and upstream buffering |
| Lamp Node | Construction/identity, control/measurement cycle, local restart, commands, configuration version/readback, response pumping, retained measurement/event reporting |
| Diagnostics/measurement | Multi-evidence classification, missing/invalid/nonfinite inputs, current/voltage/power consistency, sensor state, unavailable values, energy reset/accumulation and wire range |
| Fault/notification | Legal/illegal transitions, consecutive confirmation, latching, original/latest evidence, recurrence, notification deadlines/retries, actor/timestamp/event linkage, authorized repair/closure |
| Storage | CRC/commit marker, corruption and power-loss recovery, upload/confirmation/retention distinction, authorized audited deletion, minimum retention and explicit capacity failure |
| Time | Monotonic shared logical sampling, synchronization/uncertainty, drift, backwards sync, timestamp validity on wire and in CRC; physical RTC excluded |
| Documentation | Requirements 02, model 03, fault 04, protocol 05, storage 06, configuration 07, testing 08, scope 09, overview/architecture/hardware, assumptions 11, decisions 12, traceability, README and review/demo claims |

The complete field declaration/validation/consumer/test audit is in
[07_configuration.md](07_configuration.md). The every-message sender/receiver/
response/test matrix is in [05_communication_architecture.md](05_communication_architecture.md).
Existing focused tests and scenarios were run together with new security,
malformed-input, timeout, recovery and state-machine counterexamples.

## 3. Findings and disposition

A = real defect; B = integration defect; C = test gap; D = documentation or
traceability error; E = open engineering decision; F = acceptable bounded
prototype limitation; G = physical validation. Where a defect also required
regression coverage, the principal classification is listed below.

| ID | Finding | Classification | Action / evidence |
| --- | --- | --- | --- |
| PM-01 | Unsupported versions accepted | A | Reject unsupported wire and receiver versions before processing; unsupported-version and receiver-state tests |
| PM-02 | Malformed payload consumed sequence and changed communication state | B | Commit sequence only after decoded, validated, matched processing; valid retransmission regression |
| PM-03 | Bus delivery reported as response; no real poll deadlines | B | Independent pending requests, deadlines, configured retries, final fault and response-based recovery; attached-silent-node test |
| PM-04 | VIEWER control transmitted and executed before local rejection | B | Authorize before encode/send; 25 subtype/role combinations plus unauthenticated rejection |
| PM-05 | VIEWER configuration changed the node despite rejection | B | Authorize before transmission and again at the node; assert zero traffic and unchanged state |
| PM-06 | Forwarding unconditionally declared ACTUAL_STATE_VERIFIED | B | Pending lifecycle; matched execution ACK; fresh consistent observed state for ON/OFF; mismatch/late/timeout tests |
| PM-07 | Status and ACK codecs existed but responses were ignored | B | Meaningful dispatch/correlation for status, control/config/time/identify/heartbeat and data reports |
| PM-08 | CONTROL_ACK lacked mode/override context and called commanded state actual | B | Retain existing message type; observed actual state, effective/configured mode, override and energy evidence; codec/integration tests |
| PM-09 | Configured mode had stale mutable shadow state | B | One immutable configuration authority through ControlModel and LampNode; both supported change paths tested |
| PM-10 | Config writes ignored transmitted version | A | Explicit initial 0, positive strictly newer writes, atomic rejection/readback; 1/2/stale/duplicate/0 regressions |
| PM-11 | CONFIG_READ omitted required ACK fields and crashed | B | Working readback with version, accepted, reason and supported applied parameters |
| PM-12 | Transport manufactured roles; subtype mapping inconsistent | B | Asserted original actor preserved; actual action authorized; type/subtype conflicts rejected before execution, including local privilege-escalation counterexample |
| PM-13 | always_on excluded final tick; next_transition returned non-transitions | A | Full-day exclusive-end correction; aggregate-state transition filtering; day lengths 1/2/100/86400000 and overlapping windows |
| PM-14 | light_hysteresis validated but unused | B | Explicit symmetric margin, inclusive thresholds and dead-band retention; boundary tests and documented simulation convention |
| PM-15 | Illegal fault transitions rejected without audit | A | Rejection events with actor/time/fault linkage; no state mutation |
| PM-16 | Fault-to-event relationship alleged missing | F | Already present in main; preserved and expanded to all newly emitted rejection/repair/notification events |
| PM-17 | Confirmation versus deletion distinction | F | Already present in main; preserved, with stricter integrity/lifecycle guards |
| PM-18 | Deletion accepted arbitrary strings, lacked structured actor/identity and GC audit | B | Authenticated administrative Actor required; denial/success audited; minimum retention; store audit even without callbacks; node and GC structured audit |
| PM-19 | GC accepted actor argument but discarded it | A | Propagate actor to EventLog and buffered audit data; direct regression |
| PM-20 | Sequence history never expired and transmit counters overflowed | A | Shared bounded modular tracker, 16-bit transmit wrap, both-receiver replay handling and cached identical replies |
| PM-21 | Node ignored configured retention | B | Apply construction-time and supported remote retention to actual store; enforcement tests |
| PM-22 | Persistent fault reset notification timers on every observation | B | One initialization per fault, preserved retry/reminder/escalation state; persistent-fault integration tests |
| PM-23 | Operator-facing fault APIs bypassed authorization | B | Authorize acknowledgement/repair/report/verification before mutation; VIEWER denial for all four paths |
| PM-24 | Corrupt record uploaded and confirmed as retained | B | Integrity/commit/lifecycle checks before upload/confirmation; explicit corruption events; corrupted time-validity regression |
| PM-25 | Tests asserted delivery/premature success | C | Preserve tests, add pending assertions, advance deadlines and supply fresh observations before final-success assertions |
| PM-26 | Blanket VERIFIED/module-exists claims and stale documentation | D | Requirement-specific PARTIAL status, reconciled protocol widths/version, current scope, field/message matrices and this report |
| PM-27 | Invalid/missing/nonfinite evidence could appear normal or decrement/poison energy | A | Finite/type checks, missing-evidence classification, invalid light retains control, invalid energy samples excluded, consistent electrical evidence required |
| PM-28 | Shared clock advanced once per node despite explicit same sample time; backwards sync claimed synchronized | B | Explicit sample ticks advance only to requested time; backwards samples rejected; backwards sync remains uncertain; supplied action times reach audit |
| PM-29 | Confirmation counts survived intervening classifications; original evidence overwritten; recurrence unlinked | A | Consecutive matching counters, separate latest evidence and previous_fault_id link; regressions |
| PM-30 | Event advanced before receipt; historical measurements not replayed to GC | B | Existing message types now carry confirmation IDs; retry-safe retained event and oldest-valid measurement transfer; lost-response and offline-history tests |
| PM-31 | Audit string/energy wire ranges could block legitimate history | A | Revision 2 length-delimited strings and 64-bit energy; long audit text and large energy round trips |
| PM-32 | Conflicting command-ID reuse could return another intent's success | A | Reject/audit conflicting type/subtype/target/actor/parameters, retain idempotency for identical intent, never retransmit |
| PM-33 | Permissive payload decode accepted trailing/noncanonical data | A | Canonical body/metadata validation and normalized protocol errors; trailing-byte regressions |
| PM-34 | Notification overwrote confirmation reason; repair-report transition lacked event | B | Independent notification_reason, explicit notification/repair-report event types, preserved actor/time and linked IDs |
| PM-35 | Final ACK could win after total deadline if timeout service had not run | A | Absolute transaction expiry checked before response processing; late response cannot verify or poison sequence |
| PM-36 | Reset/unregistration left pending commands able to complete later | B | Fail pending commands across node reset or unregister; terminal state stays terminal |
| PM-37 | Group audit data was not included in store-and-forward buffer | B | Buffer command/configuration/communication/synchronization audit, without recursive storage-full logging |
| PM-38 | Reserved/open configuration fields could imply implemented policy | D | A-09 selection rejected rather than silently ignored; max_nodes_in_group explicitly advisory/deferred; GC max_nodes is authoritative |
| PM-39 | Full remote schema, automatic repair comparator, MCC and calibration claims exceeded implementation | D | Expose seven PARTIAL requirements; no speculative product/hardware implementation added |
| PM-40 | A-09/A-10/A-27/A-29 unresolved | E | Preserve open/accepted-deferral statuses; no product policy or numeric retention invented |
| PM-41 | A-18/A-26 cannot be physically established by Python | G | Preserve physical feedback/RTC review and measurement requirements |
| PM-42 | Fractional wire configuration/control values and local mode codes silently truncated | A | Reject noninteger scalar wire values and local mode indices before mutation/transmission; fractional local/remote regressions |
| PM-43 | Invalid actor metadata leaked a nonprotocol decode exception | A | Normalize actor validation failure to ProtocolError; malformed-actor regression |
| PM-44 | Group numeric configuration accepted NaN/fractional/boolean values, bypassing capacity or deadline semantics | A | Require integer group limits/timeouts/retries and positive integer or unspecified capacity; 16 parameterized cases |

## 4. Production changes

- `authorization.py`: validate role/authentication assertions.
- `command.py`: pending submission, observable asynchronous transitions,
  deferred verification, evidence/transmission fields, conflict-safe idempotency,
  action mapping and consistent type/subtype validation.
- `configuration.py` / `control.py`: schedule bounds/transitions, finite/type/
  enum configuration validation, explicit reserved policy behavior, one mode
  authority, consumed numeric hysteresis and invalid/out-of-range light suppression.
- `comm/frame.py`, `comm/protocol.py`, new `comm/sequence.py`: revision 2 early
  rejection, strict binary envelope/metadata, original actor context, matched
  responses, readback/evidence, retained-record/event confirmation, uncertainty/
  availability, bounded sequence reuse with half-space window validation, wider
  audit/energy encodings and rejection rather than lossy scalar coercion.
- `comm/state_machine.py`: explicit retry exhaustion through legal states without
  inventing missed exchanges; GC retry deadlines cannot extend absolute expiry.
- `nodes/group_controller.py`: pre-transmission authorization, pending request/
  command state, strict numeric group configuration, retries/absolute expiry, all meaningful response handlers,
  actual verification checks, report aggregation/deduplication, safe unregister,
  corrupt-upload rejection and structured/buffered actor audit.
- `nodes/lamp_node.py`: reauthorization without invented roles, validated request
  replay cache, deferred observed verification, complete ACKs, strict atomic
  config version/readback, history transfer, retention integration, authorized
  fault actions, restart invalidation, strict local mode indices and clock/event consistency.
- `diagnostics.py` / `measurement.py`: missing/nonfinite evidence cannot be
  called normal/consistent; measurement-to-evidence helper can use configuration;
  invalid light is not trusted by automatic control.
- `fault.py`, `notification.py`, `enums.py`: auditable rejection and repair
  report, consecutive confirmation, original/latest evidence and recurrence,
  independent notification reason and once-only deadlines; appended event types.
- `storage.py`: stronger CRC envelope, legal valid upload/confirmation,
  authorized/retention-guarded audited tombstone deletion and explicit recovery
  audit; deletion does not mean secure physical erasure.
- `identity.py`: broadcast constant reconciled to 0xFF, distinct from master 0.
- `time_model.py`: backwards synchronization preserves monotonic ticks and
  reports uncertainty rather than false synchronization.

## 5. Validation results

Results below were obtained from the full working branch, not copied from the prior report.
They describe the corrective pass; Phase 14 additions and results are reported in
section 9.

| Check | Result |
| --- | --- |
| Full pytest suite | 438 passed; 0 failed; 0 skipped; no warnings reported |
| Baseline | 302 passing cases; no existing test deleted |
| New regression cases | 136 collected cases in test_post_merge.py, including parameterized combinations |
| Warning policy | pytest filterwarnings=error remains enabled |
| Compileall | Passed for src and tests |
| Markdownlint | Passed: 0 issues across all 19 Markdown files |
| Pyflakes | Five inherited diagnostic lines only: four star-import diagnostics in `sslv1/__init__.py` and one duplicate MessageType import in `comm/__init__.py`; no new diagnostic |
| Ruff / mypy | No configured project check; not installed/run |
| Whitespace/diff | Passed for staged and unstaged changes |

Pytest and the existing documented pyflakes check run in an ignored `.venv`;
markdownlint runs with npx and the existing configuration. No runtime or project
lint dependency was added. Generated caches/artifacts are not committed.

Targeted probes are reproducible as tests: VIEWER control/configuration causes
zero bus transmissions; direct transport cannot manufacture RESET_ENERGY or
SET_MODE privilege; a matching pre-command sample is stale; received/executed
ACK alone is not verification; inconsistent or expired ACK does not complete a
command; corruption cannot enter upstream retained history. A focused rerun of
56 authorization/corruption/forged-ACK/deadline/numeric-boundary cases also passed.
AST checks confirmed the full 73-function new-test inventory, no deleted existing
test functions and coverage of every changed existing test in section 10. All 88
requirement statuses were programmatically reconciled between documents.

## 6. Final review method

The completed second pass reviewed the actual main-to-working-tree diff, all changed
production paths and test expectations, with focused probes for false success,
permission escalation, sequence poisoning/reuse, partial mutation, stale
observations, timeout boundaries and retained-history loss. It is a separate
review pass by the same coding agent, **not a claimed independent human or
Minewing approval**. Documentation is reconciled against actual behavior, not
against prior counts or commit messages. External engineering review remains.

## 7. Remaining model scope and decisions

Seven requirements were explicitly PARTIAL, not waived (Phase 16 later added `PR-FAULT-007`; see section 12.3):

- PR-CONFIG-001/002: the full remotely distributable structured schema and scope
  assignment are not implemented; the exact supported scalar subset is listed.
- PR-FAULT-011: authorized external repair outcome/evidence, not an automatic
  repair comparator or proof of physical repair.
- PR-COMM-008: health FSM/deadlines/events exist; automatic GC-link-to-managed
  per-lamp fault-lifecycle integration is not implemented.
- PR-SCALABILITY-002: group identities/controllers exist; complete multi-group
  MCC application/aggregation remains deferred.
- PR-STORAGE-007: configuration/record objects are separated; calibration and
  physical memory separation are not implemented.
- PR-OFFLINE-005: retained report replay/confirmation works; complete recovery/
  synchronization orchestration remains explicitly driven by the scenario.

Other bounded limitations: trusted actor assertions are not authenticated
peers; caches/logs/stores are in memory and a simulated restart retains objects;
no cross-process persistence is claimed. Fault reporting is an active snapshot,
not a full historical fault-record transport. Notification delivery is injected;
ack_required=False selects NOT_REQUIRED under the existing model. Autonomous
node-side communication-watchdog scheduling is not implemented; the GC drives
real bus health deadlines. Automatic deletion exposes policy candidates but
has no deletion worker; every actual deletion remains explicitly authorized.

A-09 storage-full behavior, A-10 retention duration, A-18 physical switching
feedback, A-26 physical RTC backup and A-29 numeric retention remain open.
A-27 remains an accepted deferral of detailed production permissions. Numeric
site thresholds, physical storage media and security policy are not frozen.

## 8. Physical validation exclusions

No electrical/mains safety, isolation/creepage/clearance, EMC, RF, surge/ESD,
relay life or inrush, thermal/enclosure/IP, RTC backup duration/leakage/
oscillator accuracy/temperature/interruption behavior, metering accuracy,
certification or production readiness is established by this Python work.

The sequence remains requirements → architecture → design → implementation →
test → audit → validation → Minewing engineering review → physical prototype →
real-world validation. The corrective pass does not skip those gates.

## 9. Phase 14 - deterministic fault injection (2026-10-04)

Phase 14 was executed on the corrected branch after the corrective pass above.
It adds no product requirements: it attacks the existing digital model with
controlled faults and checks behaviour against the existing requirement set.

| Item | Value |
| --- | --- |
| Harness | `tests/fault_injection.py` - `GroupSim` (1-16 nodes), injectable upstream link, injected readings, bus/storage/time hooks, injection counters |
| Scenarios | `tests/test_fault_injection.py` - 12 fault categories plus the ten A-J end-to-end scenarios |
| Coverage | sensor/light, electrical, switching feedback, communication, remote commands, fault lifecycle, notification, storage and store-and-forward, time, 16-node containment |
| Full suite | 546 passed, 0 failed (438 before Phase 14) |
| Phase 14 module | 104 passed |
| Determinism | logical clock only; no wall clock, randomness, network or hardware access; repeated runs produce identical event sequences |

### 9.1 Defects found and fixed

Each defect was fixed in the production model with a focused regression test;
none is hidden inside the fault-injection layer.

| # | Defect | Effect | Fix | Regression test |
| --- | --- | --- | --- | --- |
| 1 | A validated pull request for which there is nothing to report was left unanswered (`MEASUREMENT_REQUEST`, `FAULT_REPORT_REQUEST`, `EVENT_REPORT_REQUEST`) | A healthy idle node exhausted `poll_retry_count` and was escalated to `COMM_FAULT`; a zero-length event body was also indistinguishable from a malformed one | The node now answers explicitly with an empty result set; the Group Controller skips the explicit-empty answer instead of buffering a phantom record; wire event id 0 maps to an empty body | `tests/test_post_merge.py::test_empty_measurement_pull_is_answered_and_buffers_no_record`, `::test_empty_fault_and_event_pulls_are_answered_without_phantom_records` |
| 2 | A live-only measurement reply (`record_sequence == 0`) was buffered again as a new historical record | Every idle poll duplicated the last measurement, growing the upload and the upstream history without bound | The Group Controller refreshes the live view and returns early for live-only replies; only stored-record identities enter the buffer | `tests/test_post_merge.py::test_live_only_measurement_reply_does_not_duplicate_the_historical_record` |
| 3 | The normal "lamp commanded off, no current, bright ambient" observation was confirmed as a managed `ENVIRONMENTAL` fault and notified after the observation count | Every daylight period produced a confirmed fault and a notification | `ENVIRONMENTAL_OR_EXTERNAL` is treated as an observation-only classification by the fault engine (no fault, no confirmation, no notification); the diagnostic result is still reported and any unconfirmed suspicion still clears | `tests/test_fault.py::test_environmental_observation_never_becomes_a_confirmed_fault` |

The three regressions were mutation-checked: reverting the production change
makes the corresponding regression test fail.

### 9.2 Bounded behaviour and open questions

- Storage-full (A-09), retention duration (A-10) and numeric limits remain
  open; the injected scenarios pin the currently implemented bounded
  behaviour only (explicit `STORAGE_FULL` event, typed `StorageFullError`,
  retired capacity after authorized deletion).
- Two open engineering questions surfaced (see
  `docs/09_digital_prototype_scope.md`, "Phase 14 fault-injection boundaries"):
  command verification versus measurement interval, and the resting state of a
  notification that exhausted its delivery retries. Both are pinned by tests
  and neither changes a requirement.
- No physical claim is introduced: the injected faults are modelled conditions
  and the demonstrated timing is logical time.

### 9.3 Traceability

Every Phase 14 area maps to existing requirements in
`docs/requirements_traceability.md` section 7. No requirement status changed in
Phase 14. (Phase 16 later re-based the matrix to 77 `VERIFIED`, 8 `PARTIAL`,
3 `PLANNED`; see section 12.)

---

## 10. Test change inventory

The existing test bodies changed below retain their original final behavior
assertions. Changes supply measured evidence, authenticated Actors, valid
response frames or elapsed logical deadlines instead of relying on the defects.

### tests/test_command.py

- `test_command_lifecycle_reaches_actual_state_verified`
- `test_duplicate_command_is_not_executed_twice`

### tests/test_control.py

- `test_force_on_overrides_automatic_logic`

### tests/test_group_controller.py

- `run_cycle`
- `test_group_controller_manages_multiple_nodes`
- `test_one_silent_node_does_not_block_the_others`
- `test_time_synchronization_reaches_every_node`
- `test_configuration_distribution_is_acknowledged`
- `_feed`

Private helper replaced: `_status_frame`.

### tests/test_scenarios.py

- `test_scenario_07_force_on`
- `test_scenario_08_force_off`
- `test_scenario_13_command_lifecycle_reaches_verification`
- `test_scenario_21_light_sensor_failure`
- `test_scenario_38_communication_retry_then_degraded`
- `test_scenario_39_communication_recovery`
- `test_scenario_40_time_synchronization`
- `test_scenario_49_important_transitions_generate_events`

### tests/test_storage.py

- `test_queue_removal_and_deletion_are_distinct_operations`
- `test_pending_upload_records_cannot_be_deleted`
- `test_deletion_inside_minimum_retention_is_refused`
- `test_deletion_raises_an_audit_event_through_the_node`
- `test_deletion_audit_reports_the_actor`
- `test_store_without_a_hook_still_deletes`

### Added: tests/test_post_merge.py

- `test_remote_role_matrix_before_transmission`
- `test_unauthorized_config_never_transmitted`
- `test_direct_transport_does_not_manufacture_privilege`
- `test_delivery_and_ack_are_not_actual_verification`
- `test_observation_mismatch_fails_instead_of_false_verification`
- `test_command_timeout_and_late_response_cannot_resurrect`
- `test_duplicate_command_never_retransmits`
- `test_unsupported_version_rejected_before_payload`
- `test_malformed_frame_does_not_consume_sequence_or_finish_poll`
- `test_wrong_destination_or_version_does_not_poison_receive`
- `test_full_sequence_reuse_and_bounded_history`
- `test_transmit_wraps_on_both_nodes`
- `test_attached_silent_node_waits_retries_and_recovers`
- `test_corrupt_request_does_not_abort_other_nodes`
- `test_first_configuration_version`
- `test_config_ordering_and_readback`
- `test_invalid_config_is_atomic_and_nacks`
- `test_mode_single_source_through_both_paths`
- `test_identity_time_heartbeat_ack_dispatch`
- `test_time_distribution_denied_before_bus`
- `test_always_on_all_boundaries_and_no_transition`
- `test_schedule_overlapping_boundaries_are_not_false_transitions`
- `test_hysteresis_margin_affects_both_boundaries`
- `test_persistent_fault_does_not_reset_notification_deadlines`
- `test_illegal_fault_transition_is_audited_without_mutation`
- `test_fault_actor_authorization_before_action`
- `test_configured_retention_is_enforced_by_node`
- `test_retained_deletion_requires_administration`
- `test_bare_store_audits_deletion_and_reclaims_capacity`
- `test_corrupt_record_never_uploaded_or_confirmed`
- `test_ack_round_trip_has_execution_evidence`
- `test_payload_trailing_bytes_rejected`
- `test_measurement_uncertainty_and_absence_survive_bus`
- `test_nonfinite_or_nonnumeric_config_rejected`
- `test_negative_or_nonfinite_energy_samples_do_not_decrement`
- `test_missing_current_cannot_verify_off`
- `test_backwards_sync_is_not_falsely_synchronized`
- `test_invalid_sensor_cannot_drive_automatic_control`
- `test_lamp_replay_cache_is_idempotent_and_rejects_changed_payload`
- `test_event_report_loss_retry_and_confirm_does_not_lose_history`
- `test_fault_report_is_aggregated_without_mutating_local_lifecycle`
- `test_notification_does_not_overwrite_confirmation_reason`
- `test_repair_event_actor_and_original_evidence_are_preserved`
- `test_restart_invalidates_unverified_command`
- `test_mode_command_is_versioned_and_audited`
- `test_remote_retention_update_changes_store_policy`
- `test_bad_measurement_numbers_cannot_classify_as_normal`
- `test_missing_evidence_cannot_classify_as_normal`
- `test_storage_crc_protects_time_validity`
- `test_sample_time_is_shared_consistently`
- `test_unregistration_fails_pending_command`
- `test_large_energy_payload_round_trip`
- `test_gc_deletion_audits_structured_actor`
- `test_confirmation_requires_consecutive_matching_classification`
- `test_recurrence_links_to_closed_fault`
- `test_conflicting_duplicate_id_is_rejected_without_action`
- `test_forged_actual_verification_ack_cannot_complete_command`
- `test_long_audit_reason_round_trips_without_loss`
- `test_offline_measurement_history_is_replayed_and_retained`
- `test_lost_measurement_response_retries_without_duplicate_history`
- `test_group_buffers_command_and_sync_audit`
- `test_denied_deletion_is_audited_with_identity`
- `test_late_ack_is_rejected_even_if_timeouts_were_not_serviced`
- `test_command_audit_uses_supplied_action_time`
- `test_inconsistent_command_subtype_cannot_escalate_local_privileges`

- `test_delayed_timeout_service_cannot_extend_absolute_deadline`
- `test_retry_exhaustion_does_not_invent_missed_exchanges`
- `test_sequence_window_must_fit_modular_half_space`
- `test_fractional_wire_config_is_rejected_not_silently_coerced`
- `test_malformed_actor_is_a_protocol_error`
- `test_fractional_local_mode_is_rejected_without_mutation`
- `test_invalid_light_value_does_not_drive_automatic_control`
- `test_group_configuration_rejects_invalid_numeric_types`

### Added: tests/mcc_harness.py

- Phase 15 deterministic MCC system harness (`MccSim`, identifier helpers,
  `advance`/`step`/`step_group`/`pump`/`round`/`rounds`, condition injection);
  test support only, not production code.

### Added: tests/test_mcc.py

- `test_site_is_created_and_listed`, `test_duplicate_site_is_rejected_and_changes_nothing`, `test_unknown_site_is_reported_not_invented`, `test_multiple_sites_are_distinct`
- `test_group_is_registered_and_listed_per_site`, `test_duplicate_group_at_one_site_is_rejected`, `test_same_group_id_at_two_sites_is_not_a_conflict`, `test_group_identity_mismatch_is_rejected`, `test_group_controller_with_a_foreign_clock_is_rejected`
- `test_lamp_inventory_preserves_the_identity_hierarchy`, `test_lamp_listing_is_scoped_by_group_and_site`, `test_duplicate_lamp_registration_is_rejected`, `test_identical_lamp_ids_in_different_groups_are_different_lamps`, `test_inconsistent_lamp_hierarchy_is_rejected`, `test_lamp_that_belongs_to_another_site_is_rejected`, `test_unknown_lamp_lookup_is_rejected`
- `test_lamp_status_reports_every_field_the_group_reported`, `test_lamp_status_invents_no_measurements_before_anything_is_reported`, `test_lamp_status_is_stale_after_the_freshness_limit_and_not_healthy`, `test_freshness_is_unknown_when_no_limit_is_configured`, `test_invalid_freshness_limit_is_rejected`, `test_group_must_be_selected_with_its_site`
- `test_sixteen_lamp_group_aggregates_independently`, `test_two_group_site_aggregates_each_group_and_the_site`, `test_group_with_no_reported_data_is_unknown_not_healthy`
- `test_one_unavailable_lamp_is_named_and_the_rest_stay_healthy`, `test_multiple_unavailable_lamps_are_all_listed`, `test_one_group_failure_does_not_hide_the_other_groups_health`, `test_group_and_site_health_are_unavailable_when_all_groups_are_unreachable`, `test_degraded_link_is_reported_as_degraded_not_unavailable`, `test_healthy_group_does_not_conceal_a_faulted_lamp`
- `test_active_fault_visibility_carries_identity_state_and_severity`, `test_repeated_fault_polls_add_records_but_not_fault_identities`, `test_cleared_fault_disappears_from_the_active_view`, `test_fault_visibility_does_not_read_unreported_node_state`, `test_site_fault_count_spans_the_groups_without_mixing_them`, `test_identical_group_ids_at_two_sites_never_mix_their_faults`
- `test_events_are_aggregated_from_the_existing_group_logs`, `test_node_events_reach_the_mcc_only_through_the_group_records`
- `test_authorized_force_on_is_verified_from_a_fresh_observation`, `test_authorized_force_off_and_return_to_auto`, `test_every_supported_subtype_can_be_requested_through_the_mcc`, `test_unauthorized_command_is_rejected_before_anything_is_transmitted`, `test_engineering_only_action_is_protected_even_through_the_mcc`, `test_admin_time_distribution_is_not_reachable_through_the_mcc_data_layer`
- `test_mcc_command_is_traceable_to_actor_command_target_and_outcome`, `test_duplicate_command_id_is_idempotent_through_the_mcc`
- `test_configuration_readback_is_exposed_and_bounded`, `test_structured_configuration_writing_is_not_exposed_by_the_mcc`
- `test_lamps_keep_operating_while_the_mcc_has_never_polled`, `test_local_records_are_kept_while_the_mcc_is_unreachable`
- `test_scenario_two_group_site_with_an_isolated_failure`, `test_scenario_operator_handles_a_faulted_lamp_from_the_mcc`, `test_scenario_command_to_a_node_that_cannot_execute_it`, `test_scenario_second_site_stays_isolated_from_the_first`

---

## 11. Phase 15 - Master Control Center data layer (2026-10-04)

Phase 15 adds the logical operator/data layer defined in `docs/01` section 6 and
D-030/D-041. It adds no product requirements and no new control, diagnosis,
notification, storage or authorization mechanism: it **reads** what the existing
Lamp Nodes and Group Controllers already report and routes operator commands
through the existing authorized command path.

| Item | Value |
| --- | --- |
| Production module | `src/sslv1/mcc.py` - `MasterControlCenter`, `MasterControlCenterConfig`, registry and read-model dataclasses |
| Enum additions | `Freshness`, `LampAvailability`, `AggregateHealth` in `src/sslv1/enums.py` |
| Harness | `tests/mcc_harness.py` - `MccSim` (sites, groups, 16-lamp nodes, controllers, in-memory buses, one logical clock, one `AuthorizationService`) |
| Scenarios | `tests/test_mcc.py` - 55 tests in 13 sections plus 4 end-to-end scenarios |
| Full suite | 601 passed, 0 failed (546 before Phase 15) |
| Determinism | logical clock only; no wall clock, randomness, network or hardware access |

### 11.1 Architecture delivered

- **Registries:** sites, groups (unique within a site; the same group id at two
  sites is not a conflict) and lamps (unique within a group; identical lamp
  indexes in different groups are different lamps). Inconsistent hierarchy
  (site/group/lamp mismatch, foreign controller or clock, duplicates) is
  rejected before it changes the registry.
- **Live view:** per-lamp commanded/actual state, effective/configured mode,
  active override, sensor/controller/communication status, voltage, current,
  power, energy and light level - all read from the Group Controller's stored
  measurement and the node's status answer; missing data stays missing.
- **Aggregation:** group and site totals, reachable/unreachable/unknown
  members, active-fault count and highest severity, aggregate power/energy
  where the existing model provides them, latest observation time and the
  group's pending-upload/storage figures. Healthy members never conceal an
  unhealthy one, and one group's failure never changes another group's verdict.
- **Freshness:** observation time, age and time-sync state come from the
  existing logical time model; an observation older than
  `status_max_age_ticks` (or with no configured limit and no observation) is
  reported `STALE`/`UNKNOWN`, never as current or healthy.
- **Faults and history:** fault summaries are built from the `FAULT` records the
  group actually received (one summary per fault identity, no MCC lifecycle),
  and events are read from the existing `EventLog` of each controller. No
  second event log, no second fault lifecycle and no MCC-side storage exist.
- **Commands:** FORCE_ON/FORCE_OFF/RETURN_TO_AUTO (and the supported
  `CONTROL_COMMAND` subtypes where the architecture already allows them) are
  submitted to the Group Controller's existing command path, so authorization,
  idempotent ids, the CREATED -> RECEIVED -> EXECUTED -> ACKNOWLEDGED ->
  ACTUAL_STATE_VERIFIED sequence and the original actor identity are unchanged.
  Denied actions are rejected before any frame is transmitted.
- **Configuration:** readback of what the controller stored; no writer, no
  structured remote configuration and no privileged administration action is
  exposed by the data layer.

### 11.2 Defects found and fixed

| # | Defect | Effect | Fix | Regression test |
| --- | --- | --- | --- | --- |
| 1 | A fault the node stopped reporting (closed/cleared) was never recorded as cleared, because the "no active fault" answer to a validated pull was discarded as an empty answer | Every upstream layer would keep presenting the old fault as active forever, contradicting "missing information is not current truth" | The Group Controller records the clearing exchange once per clearing (linked to the fault identity it clears) and the MCC excludes cleared faults from the active view while keeping the record readable | `tests/test_mcc.py::test_cleared_fault_disappears_from_the_active_view` |
| 2 | A lamp with an active fault was still counted as a healthy lamp in its group | A group could report `HEALTHY` totals while one of its lamps carried a confirmed fault | Availability is degraded by an active fault (after communication/freshness verdicts, so stale fault data never looks current) | `tests/test_mcc.py::test_healthy_group_does_not_conceal_a_faulted_lamp` |
| 3 | A fault summary re-derived its site from the group id alone, so a fault in `SITE-B/GRP-01` was reported as belonging to `SITE-A/GRP-01` | Identical group ids at two sites were mixed at the aggregation layer, misattributing fault identity and history | The site from the queried registration is part of the fault identity key (site, group, lamp, fault id), and the redundant lookup helper was removed | `tests/test_mcc.py::test_identical_group_ids_at_two_sites_never_mix_their_faults` |

All three fixes were mutation-checked: reverting any production change makes its
regression test fail (or, for defect 3, its specific assertion fail), and no
other test changes state.

### 11.3 Bounded behaviour and boundaries

- The existing fault-report transport carries the one fault a node reports
  first, so a lamp with several concurrent faults is visible one fault at a
  time; a fault is only shown as cleared when the node reports no active fault
  (the pre-existing "active snapshot" property recorded in section 7).
- The seven PARTIAL requirements and the three PLANNED requirements are
  unchanged for Phase 15 (Phase 16 later moved `PR-FAULT-007` to PARTIAL; see
  section 12.3). `PR-SCALABILITY-002` stays PARTIAL: the data layer aggregates two
  16-lamp groups per site deterministically, but production multi-group/multi-site
  deployment, persistence, resource bounds and scale validation remain out of
  scope. `PR-CONFIG-001/002` stay PARTIAL (readback only, no structured write
  path) and `PR-OFFLINE-005` stays PARTIAL (the MCC does not orchestrate
  recovery, upload or confirmation).
- No GUI, cloud service, database, web framework, REST/web/auth server, mobile
  application or paid service was added, and no physical networking, hardware,
  telemetry or firmware dependency exists.
- **No physical validation was performed.** The Phase 15 evidence is
  deterministic execution of the digital model only; it says nothing about
  electrical safety, EMC/RF, relay/surge behaviour, mains or IP rating,
  physical RTC retention/accuracy, certification or production readiness.
- Documentation updated: `README.md`, `docs/00`, `docs/01` (section 6),
  `docs/03` (MCC persistence), `docs/08` (section 7.2, inventory),
  `docs/09` (remaining boundaries), `docs/12` (D-030 consequence, new D-041 and
  reconciled decision count), `docs/requirements_traceability.md` (section 8 and
  scoped-limitation notes) and this report.
- Pre-existing documentation defects found while reconciling: the traceability
  document cited a non-existent `PR-STORAGE-010` and `docs/11` cited it as a
  related requirement of A-29; both now reference the existing
  `PR-STORAGE-009` (record lifecycle and retention policy).

---

## 12. Phase 16 - full digital integration (2026-10-04)

### 12.1 What was integrated

The existing subsystems were connected into one executable system - Master
Control Center over Group Controller over Lamp Nodes, with the real command,
authorization, communication, measurement, fault, notification, storage,
configuration and time components - and driven end to end. No parallel
architecture, no second fault engine, no second record store, no second
authorization path and no new product feature were added.

Production additions (minimal, all in places where the end-to-end flow was
genuinely incomplete):

| File | Addition |
| --- | --- |
| `src/sslv1/mcc.py` | `ReceivedRecord`, `MccUpstreamLink` (the MCC end of the existing abstract upstream link), `receive_upstream` (identity-checked, duplicate-safe), `upstream_records`, `duplicate_uploads`, `forward_upstream`, `recover_upstream` |
| `src/sslv1/mcc.py` | Group aggregation: all lamps unreachable -> group `UNAVAILABLE` |
| `src/sslv1/nodes/group_controller.py` | `restart()` (documented retention kept, transaction state cleared, in-flight commands failed, restart audited with `nodes`/`cleared_requests`/`failed_commands`) |
| `src/sslv1/nodes/group_controller.py` | `resynchronize_upstream()` (one deterministic `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM` step with a stage report) |
| `src/sslv1/nodes/group_controller.py` | `COMM_RECOVERED` emitted when a node link returns to `COMM_HEALTHY` from `DEGRADED`/`RECOVERY` |
| `src/sslv1/nodes/group_controller.py` | `_time_sync_state()` gated on a verified node `TIME_ACK` |
| `tests/mcc_harness.py` | `site_count`, `upstream_factory`, `cycle`, `restart_group`, `restart_lamp`, `silence_group`, `set_upstream`, accessors |

### 12.2 Defects found and fixed

| # | Defect | Consequence if unfixed | Fix | Evidence |
| --- | --- | --- | --- | --- |
| 1 | A group whose every lamp was unreachable was aggregated as `DEGRADED` | A total group outage looked like a partial degradation | All lamps `UNAVAILABLE` -> group `UNAVAILABLE`; one lamp among reporting lamps stays `DEGRADED`; all-`UNKNOWN` unchanged | `test_integration.py::test_a_silent_node_is_unavailable_at_the_mcc_while_its_neighbours_report`, `::test_one_groups_link_failure_cannot_contaminate_another_group`, `::test_two_sites_of_two_sixteen_lamp_groups_operate_deterministically` |
| 2 | The Group Controller stamped its own records `SYNCHRONIZED` although no synchronization had ever been performed | Unsynchronized time presented as trustworthy, inherited by every upstream view | Stamp is `UNCERTAIN` until a node `TIME_ACK` is verified against the distributed tick; controller restart clears it | `test_integration.py::test_time_synchronization_propagates_and_is_visible_per_lamp`, `::test_event_and_fault_timestamps_come_from_the_logical_clock_only` |

Three self-audit corrections to the Phase 16 code (a restarted controller now
fails its in-flight commands instead of leaving them `ACKNOWLEDGED`; the MCC's
received-record member is named `timestamp_ticks` because the MCC never
re-stamps what it received; the integration report helper no longer treats "no
measurement yet" as "behind") are recorded in `docs/13` section 13.3.

### 12.3 Limitation discovered (documented, not hidden)

The `FAULT_REPORT` pull carries a single active-fault snapshot, while
`docs/03` allows concurrent faults on one lamp. With two confirmed faults only
one is propagated, and a fault closed while another fault is the reported
snapshot is never cleared upstream, so the MCC can keep listing a closed fault
as active. No GC/MCC inference was added (it would either invent a clear or hide
a possibly active fault); the fix is a fault-set report, a later-phase wire
change. `PR-FAULT-007` therefore moved from `VERIFIED` to `PARTIAL`; the
limitation is pinned by
`test_integration.py::test_concurrent_confirmed_faults_are_bounded_by_the_single_fault_report_pull`
and recorded in `docs/13` section 5.1.

### 12.4 Validation results

| Check | Result |
| --- | --- |
| Baseline before Phase 16 | 601 tests passed (`de03bc6`) |
| `python3 -m pytest tests/test_integration.py` | 38 passed |
| `python3 -m pytest` (full suite) | 639 passed |
| `python3 -m compileall -q src tests` | exit 0 |
| `pyflakes src/sslv1 tests/*.py` | 5 pre-existing findings, all in untouched `__init__.py` files; none from Phase 16 |
| Traceability | 28 requirement rows gained real Phase 16 integration evidence (including the 20 whose verification method already cited Phase 16); `PR-FAULT-007` -> PARTIAL; limited rows updated with narrowed scope |
| Main branch / PR #2 | untouched; all work on `arena/01a0dcf6-ssl` |

### 12.5 Boundaries

Only the digital model was exercised: in-memory frames, modelled field devices,
logical time, object-retention restarts and software-scale runs. Nothing here
validates electrical safety, mains behaviour, EMC/RF, surge/ESD, relay lifetime,
metering accuracy, enclosure/IP properties, physical RTC behaviour,
cryptography/tamper resistance, real RS-485 electrical behaviour, certification
or production readiness. The `PARTIAL` and `PLANNED` rows above bound every
claim.
