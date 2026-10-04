# Requirements Traceability

## 1. Document purpose

This document maps every requirement to its implementation module, its
deterministic test evidence, and its verification status. It is the mechanism
that enforces the project principle:

```text
REQUIREMENT -> ARCHITECTURE -> DESIGN -> IMPLEMENTATION -> TEST -> AUDIT -> VALIDATION
```

## 2. Column definitions

| Column | Meaning |
| --- | --- |
| Requirement ID | Identifier from [02_product_requirements.md](02_product_requirements.md). |
| Requirement | Short title of the requirement. |
| Architecture element | Element of [01_system_architecture.md](01_system_architecture.md) that carries it. |
| Implementation module | Module in [`src/sslv1/`](../src/sslv1/) that implements it, or `Documentation only` where no code is appropriate. |
| Test evidence | Deterministic test in [`tests/`](../tests/) that exercises it. |
| Verification status | One of `VERIFIED`, `PARTIAL`, `IMPLEMENTED`, `PLANNED` (see section 3). |

`VERIFIED` is bounded to the explicit digital behavior and cited evidence. A
module/test merely existing, or the suite passing, is not sufficient proof.
Physical properties are never validated by these rows. PARTIAL rows identify
remaining model/integration scope rather than masking it with passing tests.

## 3. Status definitions

| Status | Meaning |
| --- | --- |
| `VERIFIED` | The bounded digital behavior is implemented and exercised by the cited tests; no physical validation. |
| `PARTIAL` | Some behavior is modeled/tested, but the explicit limitation below prevents full requirement verification. |
| `IMPLEMENTED` | Implemented in `src/sslv1/` but not yet covered by a named test. |
| `PLANNED` | Not implemented. Reserved for physical-only requirements, requirements needing a real tamper source, and work belonging to a later phase. |

## 4. Verification summary

| Status | Count |
| --- | --- |
| `VERIFIED` | 77 |
| `PARTIAL` | 8 |
| `IMPLEMENTED` | 0 |
| `PLANNED` | 3 |

Reproduce with `python3 -m pytest` from the repository root. The suite is
deterministic: no wall-clock time, no randomness, no hardware access.

Phase 14 adds deterministic fault-injection evidence (section 7). Phase 16 adds
full digital integration evidence (section 9): 19 requirements that already
cited the Phase 16 integration test now cite real integration tests, and one
status changed - `PR-FAULT-007` moved from `VERIFIED` to `PARTIAL` because the
integration run exposed the concurrent-fault limit of the single-snapshot
`FAULT_REPORT` pull (section 5.1 of [13_integration_validation.md](13_integration_validation.md)).
Neither phase verifies anything at the physical level.

## 5. Traceability matrix

### 5.1 Lighting control (Lamp Node)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-LIGHT-001` | Automatic sensor-based control (AUTO_SENSOR) | Lighting control (Lamp Node) | src/sslv1/control.py (ControlModel), src/sslv1/nodes/lamp_node.py | test_scenarios.py::test_scenario_01_automatic_sensor_on_when_dark; test_control.py::test_automatic_sensor_switches_lamp_on_below_threshold | `VERIFIED` |
| `PR-LIGHT-002` | Schedule-with-sensor control (AUTO_SCHEDULE_SENSOR) | Lighting control (Lamp Node) | src/sslv1/control.py (ControlModel), src/sslv1/configuration.py (Schedule) | test_scenarios.py::test_scenario_06_schedule_plus_sensor; test_control.py::test_schedule_sensor_mode_uses_sensor_inside_window, ::test_schedule_sensor_mode_applies_out_of_window_state | `VERIFIED` |
| `PR-LIGHT-003` | Fixed-schedule control (FIXED_SCHEDULE) | Lighting control (Lamp Node) | src/sslv1/configuration.py (Schedule), src/sslv1/control.py (ControlModel) | test_scenarios.py::test_scenario_05_fixed_schedule_ignores_light_level; test_control.py::test_fixed_schedule_ignores_light_level, ::test_fixed_schedule_handles_window_wrapping_midnight | `VERIFIED` |
| `PR-LIGHT-004` | Authorized operator override (FORCE_ON / FORCE_OFF) | Lighting control (Lamp Node) | src/sslv1/control.py (apply_override), src/sslv1/nodes/lamp_node.py | test_scenarios.py::test_scenario_07_force_on, ::test_scenario_08_force_off; test_control.py::test_force_on_overrides_automatic_logic, ::test_force_off_overrides_automatic_logic; test_integration.py::test_scenario_b_force_on_survives_the_automatic_decision, ::test_scenario_c_force_off_survives_the_automatic_decision, ::test_scenario_d_return_to_auto_resumes_automatic_control | `VERIFIED` |
| `PR-LIGHT-005` | Return to automatic mode (RETURN_TO_AUTO operator command) | Lighting control (Lamp Node) | src/sslv1/control.py (clear_override), src/sslv1/nodes/lamp_node.py | test_scenarios.py::test_scenario_09_return_to_auto_is_a_command_not_a_mode; test_control.py::test_return_to_auto_clears_override, test_control.py::test_return_to_auto_is_not_a_persistent_mode | `VERIFIED` |

### 5.2 RS-485 field bus / Group Controller

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-COMM-001` | RS-485 master/slave discipline | RS-485 field bus / Group Controller | src/sslv1/comm/bus.py (InMemoryBus master/slave discipline), src/sslv1/nodes/lamp_node.py | test_group_controller.py::test_group_controller_manages_multiple_nodes | `VERIFIED` |
| `PR-COMM-002` | Node addressing and group size | RS-485 field bus / Group Controller | src/sslv1/identity.py (BusAddress), src/sslv1/nodes/group_controller.py (register_node) | test_group_controller.py::test_group_controller_supports_the_initial_group_target, ::test_group_controller_is_not_limited_to_sixteen; test_scenarios.py::test_scenario_47_group_controller_capacity, ::test_scenario_48_duplicate_registration_is_rejected; test_integration.py::test_commands_and_faults_reach_only_the_intended_group_and_lamp, ::test_scale_aggregation_keeps_every_lamp_addressable | `VERIFIED` |
| `PR-COMM-003` | Frame format | RS-485 field bus / Group Controller | src/sslv1/comm/frame.py (Frame, encode_frame, decode_frame) | test_comm.py::test_frame_contains_every_required_field, ::test_frame_round_trip, ::test_bad_start_of_frame_is_rejected, ::test_unknown_message_type_code_is_rejected, ::test_address_range_is_enforced | `VERIFIED` |
| `PR-COMM-004` | Initial message type set | RS-485 field bus / Group Controller | src/sslv1/enums.py (MessageType, 17 values) | test_comm.py::test_message_type_set_is_complete | `VERIFIED` |
| `PR-COMM-005` | Sequence numbering, duplicate and replay handling | RS-485 field bus / Group Controller | `src/sslv1/nodes/group_controller.py` (`SequenceTracker`, `_handle_frame`) | `test_group_controller.py::test_increasing_sequence_numbers_are_accepted`; `test_group_controller.py::test_duplicate_frame_is_detected_and_reported`; `test_group_controller.py::test_duplicate_is_reported_not_processed`; `test_group_controller.py::test_out_of_window_sequence_is_reported_as_stale`; `test_group_controller.py::test_sequence_wraparound_is_handled`; `test_group_controller.py::test_sequence_tracking_is_per_source`; `test_group_controller.py::test_duplicate_detection_does_not_disturb_communication_state` | `VERIFIED` |
| `PR-COMM-006` | CRC integrity verification | RS-485 field bus / Group Controller | src/sslv1/comm/crc.py, src/sslv1/comm/frame.py | test_comm.py::test_crc_failure_is_detected, ::test_bus_corruption_is_detectable | `VERIFIED` |
| `PR-COMM-007` | Polling, timeout and retry policy | RS-485 field bus / Group Controller | src/sslv1/nodes/group_controller.py (poll, poll_timeout_ticks, poll_retry_count) | test_group_controller.py::test_communication_fault_is_detected_after_retries; test_integration.py::test_mcc_polling_uses_the_existing_poll_and_timeout_paths, ::test_a_silent_node_is_unavailable_at_the_mcc_while_its_neighbours_report | `VERIFIED` |
| `PR-COMM-008` | Communication state machine | RS-485 field bus / Group Controller | src/sslv1/comm/state_machine.py (CommunicationStateMachine) | test_comm.py::test_healthy_to_retry_to_degraded_to_fault, ::test_recovery_returns_to_healthy, ::test_retry_recovers_to_healthy; test_integration.py::test_a_silent_node_is_unavailable_at_the_mcc_while_its_neighbours_report (COMM_FAULT -> RECOVERY -> COMM_HEALTHY with COMM_RECOVERED evidence), ::test_one_groups_link_failure_cannot_contaminate_another_group | `PARTIAL` |
| `PR-COMM-009` | Communication failure must not stop local operation | RS-485 field bus / Group Controller | src/sslv1/nodes/lamp_node.py (local control independent of the bus) | test_group_controller.py::test_communication_fault_does_not_stop_local_lighting; test_scenarios.py::test_scenario_38_communication_retry_then_degraded | `VERIFIED` |
| `PR-COMM-010` | Command subtypes carried inside CONTROL_COMMAND | RS-485 field bus / Group Controller | src/sslv1/enums.py (ControlSubtype), src/sslv1/comm/protocol.py (CONTROL_COMMAND payload) | test_command.py::test_reset_energy_is_a_control_subtype_not_a_message_type; test_comm.py::test_control_command_payload_carries_reset_energy_subtype | `VERIFIED` |

### 5.3 Configuration management

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-CONFIG-001` | Configuration parameter set | Configuration management | src/sslv1/configuration.py (LampConfiguration) | test_configuration.py::test_configuration_covers_every_documented_parameter; test_integration.py::test_configuration_change_is_authorized_applied_and_verified_end_to_end, ::test_configuration_accepted_is_not_configuration_applied (supported subset only) | `PARTIAL` |
| `PR-CONFIG-002` | Configuration read and write over the bus | Configuration management | src/sslv1/nodes/group_controller.py (distribute_configuration), src/sslv1/nodes/lamp_node.py (configuration read and write handlers) | test_group_controller.py::test_configuration_distribution_is_acknowledged, ::test_invalid_configuration_is_rejected_by_the_node; test_integration.py::test_configuration_change_is_authorized_applied_and_verified_end_to_end, ::test_configuration_write_requires_privilege_and_a_newer_version | `PARTIAL` |
| `PR-CONFIG-003` | Configuration validation | Configuration management | src/sslv1/configuration.py (LampConfiguration.validate / validated) | test_scenarios.py::test_scenario_44_configuration_validation; test_configuration.py::test_validation_rejects_every_invalid_threshold, ::test_hysteresis_wider_than_the_dead_band_is_rejected | `VERIFIED` |
| `PR-CONFIG-004` | Configuration change auditability | Configuration management | src/sslv1/event.py (EventLog), src/sslv1/nodes/lamp_node.py (_record_event) | test_scenarios.py::test_scenario_49_important_transitions_generate_events, ::test_scenario_50_rejected_command_is_audited; test_integration.py::test_configuration_change_is_authorized_applied_and_verified_end_to_end, ::test_configuration_write_requires_privilege_and_a_newer_version | `VERIFIED` |
| `PR-CONFIG-005` | Configuration persistence and versioning | Configuration management | src/sslv1/nodes/lamp_node.py (config_version, _apply_config_parameters) | test_group_controller.py::test_configuration_distribution_is_acknowledged (config_version is carried) | `VERIFIED` |
| `PR-CONFIG-006` | No hardcoded operational thresholds | Configuration management | src/sslv1/configuration.py (every threshold is a field, none is a module constant) | test_scenarios.py::test_scenario_45_every_threshold_is_configurable; test_configuration.py::test_no_operational_threshold_is_hardcoded, ::test_two_nodes_can_use_different_thresholds | `VERIFIED` |

### 5.4 Control model (Lamp Node)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-CONTROL-001` | Mode priority ordering | Control model (Lamp Node) | src/sslv1/control.py (ControlLayer, ControlModel.decide) | test_scenarios.py::test_scenario_10_override_beats_automatic_mode, ::test_scenario_11_safety_outranks_the_override; test_control.py::test_override_beats_automatic_mode, ::test_safety_protection_beats_override | `VERIFIED` |
| `PR-CONTROL-002` | Command lifecycle and success definition | Control model (Lamp Node) | src/sslv1/command.py (CommandLifecycle, CommandService) | test_scenarios.py::test_scenario_13_command_lifecycle_reaches_verification; test_command.py::test_command_lifecycle_reaches_actual_state_verified, ::test_receipt_alone_is_not_success; test_integration.py::test_scenario_b_force_on_survives_the_automatic_decision, ::test_node_restart_keeps_identity_and_configuration_and_fails_the_command | `VERIFIED` |
| `PR-CONTROL-003` | Duplicate command handling | Control model (Lamp Node) | src/sslv1/command.py (CommandService.submit duplicate suppression) | test_scenarios.py::test_scenario_14_duplicate_command_is_suppressed; test_command.py::test_duplicate_command_is_not_executed_twice, ::test_duplicate_command_does_not_toggle_the_lamp; test_integration.py::test_force_on_is_idempotent_and_never_reaches_a_second_lamp | `VERIFIED` |
| `PR-CONTROL-004` | Command authorization status | Control model (Lamp Node) | src/sslv1/command.py (CommandService authorization), src/sslv1/authorization.py | test_scenarios.py::test_scenario_15_unauthorized_command_is_rejected; test_command.py::test_unauthorized_operator_cannot_force_the_lamp, ::test_unauthenticated_actor_is_rejected; test_integration.py::test_unauthorized_operator_actions_never_reach_the_field_layer | `VERIFIED` |
| `PR-CONTROL-005` | Safe state restoration after restart | Control model (Lamp Node) | src/sslv1/nodes/lamp_node.py (start, restart and the configured restart default) | test_control.py::test_return_to_auto_clears_override; test_integration.py::test_node_restart_keeps_identity_and_configuration_and_fails_the_command, ::test_controller_restart_drops_transient_state_and_keeps_persistence, ::test_mcc_reconstruction_from_the_same_controllers_reproduces_the_view | `VERIFIED` |
| `PR-CONTROL-006` | No automatic shutdown for non-protective conditions | Control model (Lamp Node) | src/sslv1/control.py (ProtectionState, no automatic shutdown path) | test_control.py::test_no_protection_condition_is_defined_in_v1; test_scenarios.py::test_scenario_12_fault_acknowledgement_is_not_a_lighting_input | `VERIFIED` |
| `PR-CONTROL-007` | Separation of configured mode, active override and effective state | Control model (Lamp Node) | src/sslv1/control.py (ControlModel: configured_mode / active_override / effective_mode) | test_control.py::test_control_model_separates_configured_override_and_effective; test_identity.py::test_identity_hierarchy_is_complete | `VERIFIED` |

### 5.5 Diagnostics (Lamp Node)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-DIAG-001` | Multi-evidence diagnosis | Diagnostics (Lamp Node) | src/sslv1/diagnostics.py (DiagnosticEvidence, DiagnosticEngine) | test_scenarios.py::test_scenario_27_lamp_health_never_uses_current_alone; test_diagnostics.py::test_evidence_can_be_built_from_a_measurement, ::test_engine_is_deterministic | `VERIFIED` |
| `PR-DIAG-002` | Normal-operation diagnostic rule | Diagnostics (Lamp Node) | src/sslv1/diagnostics.py rule 13 (NORMAL) | test_diagnostics.py::test_normal_on_operation; test_scenarios.py::test_scenario_17_normal_measurement | `VERIFIED` |
| `PR-DIAG-003` | Open-load / lamp-fault diagnostic rule | Diagnostics (Lamp Node) | src/sslv1/diagnostics.py rules 4 and 8 (POSSIBLE_OPEN_LOAD, POSSIBLE_UNDER_CURRENT) | test_scenarios.py::test_scenario_18_under_current_and_open_load; test_diagnostics.py::test_open_load_is_not_claimed_as_a_lamp_failure | `VERIFIED` |
| `PR-DIAG-004` | Unexpected-current diagnostic rule | Diagnostics (Lamp Node) | src/sslv1/diagnostics.py rule 6 (UNEXPECTED_CURRENT) | test_scenarios.py::test_scenario_19_unexpected_current_while_commanded_off; test_diagnostics.py::test_unexpected_current_while_commanded_off | `VERIFIED` |
| `PR-DIAG-005` | Supply-voltage diagnostic rule | Diagnostics (Lamp Node) | src/sslv1/diagnostics.py rule 3 (SUPPLY_ABNORMALITY) | test_scenarios.py::test_scenario_20_supply_failure; test_diagnostics.py::test_supply_voltage_absent_while_commanded_on | `VERIFIED` |
| `PR-DIAG-006` | Sensor-fault diagnostic rule | Diagnostics (Lamp Node) | src/sslv1/diagnostics.py rules 9 and 10 (SENSOR_ABNORMALITY) | test_scenarios.py::test_scenario_21_light_sensor_failure; test_diagnostics.py::test_invalid_sensor_is_not_a_lamp_failure | `VERIFIED` |
| `PR-DIAG-007` | Diagnostic classification levels and evidential status | Diagnostics (Lamp Node) | src/sslv1/diagnostics.py (Confidence, classification enum), src/sslv1/fault.py | test_diagnostics.py::test_fault_category_and_classification_are_distinct, ::test_insufficient_evidence_when_switching_feedback_unknown; test_scenarios.py::test_scenario_25_unknown_behaviour_requires_inspection | `VERIFIED` |

### 5.6 Fault management (Lamp Node)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-FAULT-001` | Fault type categories | Fault management (Lamp Node) | src/sslv1/enums.py (FaultType) | test_diagnostics.py::test_fault_category_and_classification_are_distinct | `VERIFIED` |
| `PR-FAULT-002` | Fault severity classification | Fault management (Lamp Node) | src/sslv1/enums.py (FaultSeverity), src/sslv1/fault.py (severity mapping) | test_scenarios.py::test_scenario_23_controller_failure_is_reported | `VERIFIED` |
| `PR-FAULT-003` | Fault lifecycle state machine | Fault management (Lamp Node) | src/sslv1/fault.py (FaultLifecycle, Fault) | test_fault.py::test_legal_fault_transitions_are_permitted; test_scenarios.py::test_scenario_31_repair_and_verification | `VERIFIED` |
| `PR-FAULT-004` | Rejection of illegal fault transitions | Fault management (Lamp Node) | src/sslv1/fault.py (FaultLifecycle.can_transition / transition raising IllegalTransitionError) | test_fault.py::test_illegal_fault_transitions_are_rejected | `VERIFIED` |
| `PR-FAULT-005` | Configurable fault confirmation | Fault management (Lamp Node) | src/sslv1/fault.py (ConfirmationPolicy, FaultEngine.observe) | test_fault.py::test_fault_is_confirmed_only_after_configured_count, ::test_confirmation_count_is_configurable; test_scenarios.py::test_scenario_28_fault_confirmation_count | `VERIFIED` |
| `PR-FAULT-006` | Fault latching and hysteresis | Fault management (Lamp Node) | src/sslv1/fault.py (latching in observe), src/sslv1/configuration.py (confirmation window) | test_fault.py::test_confirmed_fault_latches_against_a_single_normal_measurement, ::test_threshold_oscillation_creates_one_fault_not_many; test_scenarios.py::test_scenario_29_fault_latching | `VERIFIED` |
| `PR-FAULT-007` | Fault notification | Fault management (Lamp Node) | src/sslv1/notification.py (NotificationEngine) | test_fault.py::test_not_required_when_ack_not_configured; test_integration.py::test_fault_path_from_measurement_to_mcc_and_back_to_clear, ::test_fault_records_reach_the_mcc_upstream_end_after_recovery, ::test_a_fault_clear_is_scoped_to_its_own_fault_and_keeps_history, ::test_fault_visibility_never_claims_a_fault_the_group_did_not_receive, ::test_concurrent_confirmed_faults_are_bounded_by_the_single_fault_report_pull (limitation evidence) | `PARTIAL` |
| `PR-FAULT-008` | Acknowledgement, reminder and escalation | Fault management (Lamp Node) | src/sslv1/notification.py (tick, acknowledge, delivery failure handling) | test_fault.py::test_reminder_and_escalation_do_not_change_fault_state, ::test_notification_failure_is_retried_then_reported, ::test_delivery_failure_retry_path_still_returns_to_pending, ::test_delivery_failure_beyond_retry_limit_does_not_crash, ::test_notification_reminder_is_idempotent, ::test_notification_reminder_does_not_spam_events, ::test_notification_escalates_after_timeout_without_crash, ::test_notification_tick_is_legal_from_every_resting_state; test_integration.py::test_fault_path_from_measurement_to_mcc_and_back_to_clear | `VERIFIED` |
| `PR-FAULT-009` | Unacknowledged alerts must not switch the lamp OFF | Fault management (Lamp Node) | src/sslv1/nodes/lamp_node.py (no notification-to-lighting coupling) | test_scenarios.py::test_scenario_30_fault_acknowledgement_does_not_dim_the_light | `VERIFIED` |
| `PR-FAULT-010` | Repair workflow | Fault management (Lamp Node) | src/sslv1/fault.py (acknowledge, start_repair, report_repaired) | test_fault.py::test_repair_workflow, ::test_repair_cannot_start_before_acknowledgement | `VERIFIED` |
| `PR-FAULT-011` | Verification workflow and failed verification | Fault management (Lamp Node) | src/sslv1/fault.py (verify) | test_fault.py::test_successful_verification_closes_the_fault, ::test_failed_verification_returns_to_an_active_fault_state; test_scenarios.py::test_scenario_32_failed_verification_reopens_the_fault | `PARTIAL` |
| `PR-FAULT-012` | Fault closure and failure containment | Fault management (Lamp Node) | src/sslv1/fault.py (FaultLifecycle CLOSED transition), src/sslv1/nodes/lamp_node.py (per-node engines) | test_fault.py::test_one_nodes_fault_does_not_affect_another_node; test_scenarios.py::test_scenario_46_multi_node_isolation; test_integration.py::test_fault_path_from_measurement_to_mcc_and_back_to_clear, ::test_a_fault_clear_is_scoped_to_its_own_fault_and_keeps_history, ::test_fault_visibility_never_claims_a_fault_the_group_did_not_receive | `VERIFIED` |
| `PR-FAULT-013` | Notification state independent of fault lifecycle | Fault management (Lamp Node) | src/sslv1/notification.py (NotificationLifecycle, independent of FaultLifecycle) | test_fault.py::test_notification_state_is_independent_of_fault_lifecycle, ::test_notified_is_not_a_fault_lifecycle_state, ::test_notify_from_any_waiting_state_does_not_crash, ::test_notification_tick_is_legal_from_every_resting_state; test_scenarios.py::test_scenario_33_notification_state_independent | `VERIFIED` |
| `PR-FAULT-014` | Fault category, diagnostic classification and root cause | Fault management (Lamp Node) | src/sslv1/diagnostics.py (classification vs category), src/sslv1/fault.py (no root-cause field) | test_diagnostics.py::test_fault_category_and_classification_are_distinct; test_scenarios.py::test_scenario_18_under_current_and_open_load | `VERIFIED` |

### 5.7 Device identity and addressing

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-IDENTITY-001` | Identity hierarchy | Device identity and addressing | src/sslv1/identity.py (DeviceIdentity, Identifier, McuUniqueId), src/sslv1/mcc.py (registry) | test_identity.py::test_identity_hierarchy_is_complete; test_mcc.py::test_lamp_inventory_preserves_the_identity_hierarchy, ::test_identical_lamp_ids_in_different_groups_are_different_lamps; test_integration.py::test_same_identifier_in_two_sites_is_two_different_systems, ::test_a_command_to_a_missing_or_foreign_target_is_refused_locally | `VERIFIED` |
| `PR-IDENTITY-002` | Deterministic and persistent identity | Device identity and addressing | src/sslv1/identity.py (Identifier is value-based) | test_identity.py::test_identity_is_deterministic_and_value_based | `VERIFIED` |
| `PR-IDENTITY-003` | Bus address uniqueness | Device identity and addressing | src/sslv1/identity.py (BusAddress, MIN/MAX), src/sslv1/nodes/group_controller.py (register_node) | test_identity.py::test_bus_address_range_is_enforced, ::test_duplicate_registration_is_rejected; test_integration.py::test_scale_aggregation_keeps_every_lamp_addressable (an address is unique inside its group) | `VERIFIED` |
| `PR-IDENTITY-004` | Identity query | Device identity and addressing | src/sslv1/nodes/group_controller.py (identify), src/sslv1/nodes/lamp_node.py (identify handler) | test_group_controller.py::test_group_snapshot_reports_communication_state; test_comm.py::test_identify_payload_round_trip | `VERIFIED` |

### 5.8 Measurement handling (Lamp Node)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-MEASURE-001` | Per-lamp measurement set | Measurement handling (Lamp Node) | src/sslv1/measurement.py (Measurement), src/sslv1/nodes/lamp_node.py (measurement construction) | test_scenarios.py::test_scenario_17_normal_measurement; test_measurement.py | `VERIFIED` |
| `PR-MEASURE-002` | Configurable measurement and reporting intervals | Measurement handling (Lamp Node) | src/sslv1/configuration.py (reporting_interval_ticks), src/sslv1/nodes/lamp_node.py | test_configuration.py::test_reporting_interval_is_configurable; test_integration.py::test_scenario_a_automatic_operation_from_registration_to_mcc_view, ::test_stale_measurements_are_never_presented_as_current | `VERIFIED` |
| `PR-MEASURE-003` | Energy accumulation | Measurement handling (Lamp Node) | src/sslv1/nodes/lamp_node.py (energy accumulation and reset) | test_command.py::test_energy_reset_requires_authorization | `VERIFIED` |
| `PR-MEASURE-004` | Sensor validity reporting | Measurement handling (Lamp Node) | src/sslv1/measurement.py (MeasurementValidator), src/sslv1/enums.py (SensorStatus) | test_measurement.py::test_invalid_sensor_is_reported_not_guessed_around, ::test_invalid_sensor_retains_the_previous_lighting_decision | `VERIFIED` |
| `PR-MEASURE-005` | Monitoring values, not billing-grade metering | Measurement handling (Lamp Node) | src/sslv1/measurement.py (Measurement carries no billing flag) | test_scenarios.py::test_scenario_17_normal_measurement (asserts no billing-grade field) | `VERIFIED` |

### 5.9 Offline operation and buffering

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-OFFLINE-001` | Local operation without Internet | Offline operation and buffering | src/sslv1/nodes/lamp_node.py (no upstream dependency) | test_group_controller.py::test_communication_fault_does_not_stop_local_lighting | `VERIFIED` |
| `PR-OFFLINE-002` | Local operation without the Master Control Center | Offline operation and buffering | src/sslv1/nodes/lamp_node.py (local control only), src/sslv1/mcc.py (consumer only, not a dependency) | test_group_controller.py::test_communication_fault_does_not_stop_local_lighting; test_mcc.py::test_lamps_keep_operating_while_the_mcc_has_never_polled, ::test_local_records_are_kept_while_the_mcc_is_unreachable | `VERIFIED` |
| `PR-OFFLINE-003` | Local operation without the Group Controller | Offline operation and buffering | src/sslv1/nodes/lamp_node.py (operates with no controller traffic) | test_group_controller.py::test_communication_fault_does_not_stop_local_lighting | `VERIFIED` |
| `PR-OFFLINE-004` | Offline record buffering | Offline operation and buffering | src/sslv1/storage.py (RecordStore buffering), src/sslv1/nodes/group_controller.py (pending queue) | test_group_controller.py::test_records_are_buffered_while_upstream_is_unavailable; test_integration.py::test_offline_cycle_buffers_everything_and_replays_it_once | `VERIFIED` |
| `PR-OFFLINE-005` | Post-recovery synchronization without silent loss | Offline operation and buffering | src/sslv1/nodes/group_controller.py (forward_upstream confirmed-only removal, no duplicate upload) | test_group_controller.py::test_buffered_records_are_uploaded_after_recovery, ::test_no_duplicate_upload_of_the_same_record, ::test_communication_recovery_resynchronizes; test_integration.py::test_offline_cycle_buffers_everything_and_replays_it_once, ::test_lost_confirmation_replays_without_duplicating_mcc_history, ::test_fault_records_reach_the_mcc_upstream_end_after_recovery | `PARTIAL` |

### 5.10 Group Controller / node management

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-SCALABILITY-001` | Lamps per group | Group Controller / node management | src/sslv1/nodes/group_controller.py (GroupControllerConfig.max_nodes) | test_scenarios.py::test_scenario_47_group_controller_capacity; test_group_controller.py::test_group_controller_supports_the_initial_group_target | `VERIFIED` |
| `PR-SCALABILITY-002` | Groups per site | Group Controller / node management | src/sslv1/identity.py (site/group hierarchy), src/sslv1/nodes/group_controller.py, src/sslv1/mcc.py (site aggregation over groups) | test_group_controller.py::test_group_snapshot_reports_communication_state (group identity carried); test_mcc.py::test_two_group_site_aggregates_each_group_and_the_site, ::test_one_group_failure_does_not_hide_the_other_groups_health, ::test_site_fault_count_spans_the_groups_without_mixing_them; test_integration.py::test_two_sites_of_two_sixteen_lamp_groups_operate_deterministically, ::test_one_groups_link_failure_cannot_contaminate_another_group, ::test_same_identifier_in_two_sites_is_two_different_systems | `PARTIAL` |
| `PR-SCALABILITY-003` | Failure containment | Group Controller / node management | src/sslv1/nodes/lamp_node.py (per-node state), src/sslv1/nodes/group_controller.py (per-node registration) | test_group_controller.py::test_one_silent_node_does_not_block_the_others, ::test_one_faulty_node_does_not_degrade_the_group; test_scenarios.py::test_scenario_46_multi_node_isolation | `VERIFIED` |
| `PR-SCALABILITY-004` | Architectural headroom | Group Controller / node management | src/sslv1/nodes/group_controller.py (max_nodes is configuration, not a fixed 16) | test_group_controller.py::test_group_controller_is_not_limited_to_sixteen | `VERIFIED` |
| `PR-SCALABILITY-005` | Group Controller local storage abstraction | Group Controller / node management | src/sslv1/nodes/group_controller.py (record buffering into RecordStore), src/sslv1/storage.py | test_group_controller.py::test_group_controller_local_storage_is_abstract | `VERIFIED` |

### 5.11 Authorization and audit

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-SECURITY-001` | Operator authorization for overrides | Authorization and audit | src/sslv1/authorization.py (AuthorizationService.require), src/sslv1/command.py, src/sslv1/mcc.py (routes through the same path) | test_scenarios.py::test_scenario_15_unauthorized_command_is_rejected; test_command.py::test_unauthorized_operator_cannot_force_the_lamp; test_mcc.py::test_unauthorized_command_is_rejected_before_anything_is_transmitted, ::test_engineering_only_action_is_protected_even_through_the_mcc; test_integration.py::test_unauthorized_operator_actions_never_reach_the_field_layer | `VERIFIED` |
| `PR-SECURITY-002` | Command authentication status | Authorization and audit | src/sslv1/command.py (CommandRecord.authorization_status), src/sslv1/enums.py (AuthorizationStatus) | test_command.py::test_unauthenticated_actor_is_rejected; test_integration.py::test_unauthorized_operator_actions_never_reach_the_field_layer, ::test_engineering_only_actions_stay_protected_through_the_whole_path | `VERIFIED` |
| `PR-SECURITY-003` | Audit trail | Authorization and audit | src/sslv1/event.py (EventLog, Event), src/sslv1/mcc.py (reads the existing log, keeps none) | test_scenarios.py::test_scenario_49_important_transitions_generate_events, ::test_scenario_50_rejected_command_is_audited; test_mcc.py::test_mcc_command_is_traceable_to_actor_command_target_and_outcome, ::test_events_are_aggregated_from_the_existing_group_logs; test_integration.py::test_unauthorized_operator_actions_never_reach_the_field_layer, ::test_fault_path_from_measurement_to_mcc_and_back_to_clear | `VERIFIED` |
| `PR-SECURITY-004` | Tamper detection | Authorization and audit | src/sslv1/enums.py (EventType.TAMPER_INDICATION, FaultType.TAMPER) - representation only | No test: no tamper source exists in the digital prototype | `PLANNED` |
| `PR-SECURITY-005` | Security validation boundary | Authorization and audit | Documentation boundary only (no code) | docs/09_digital_prototype_scope.md; src/sslv1/authorization.py docstring | `PLANNED` |
| `PR-SECURITY-006` | Preliminary operator roles | Authorization and audit | src/sslv1/authorization.py (_ROLE_ACTIONS, actions_for_role), src/sslv1/enums.py (Role, Action) | test_command.py::test_authorization_roles_cover_the_expected_actions; test_integration.py::test_engineering_only_actions_stay_protected_through_the_whole_path | `VERIFIED` |

### 5.12 Record storage (Lamp Node / Group Controller)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-STORAGE-001` | Local persistent record storage | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (RecordStore) | test_storage.py::test_records_carry_the_required_envelope; test_scenarios.py::test_scenario_34_storage_record_lifecycle | `VERIFIED` |
| `PR-STORAGE-002` | Record structure | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (StorageRecord, compute_crc, is_valid) | test_storage.py::test_records_carry_the_required_envelope, ::test_uncommitted_record_is_not_valid | `VERIFIED` |
| `PR-STORAGE-003` | Power-loss safety | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (commit_marker, simulate_power_loss, recover) | test_storage.py::test_power_loss_discards_incomplete_records, ::test_power_loss_recovery_keeps_committed_records_uploadable; test_scenarios.py::test_scenario_37_power_loss_recovery | `VERIFIED` |
| `PR-STORAGE-004` | Corruption detection and handling | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (StorageRecord.compute_crc, detect_corruption, corrupt) | test_storage.py::test_corrupted_record_is_detected_and_flagged, ::test_corrupt_record_is_excluded_from_upload | `VERIFIED` |
| `PR-STORAGE-005` | Retention: automatic deletion off by default | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (RetentionPolicy.automatic_deletion defaults to False) | test_storage.py::test_automatic_deletion_is_disabled_by_default, ::test_retention_policy_requires_explicit_configuration | `VERIFIED` |
| `PR-STORAGE-006` | Storage-full visibility | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (StorageFullError, RecordStore.is_full) | test_storage.py::test_storage_full_is_explicit_and_never_silent; test_scenarios.py::test_scenario_36_storage_full_is_visible | `VERIFIED` |
| `PR-STORAGE-007` | Separation of configuration/calibration storage | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (RecordType separation) | test_storage.py::test_records_carry_the_required_envelope (record type is part of the envelope) | `PARTIAL` |
| `PR-STORAGE-008` | Store-and-forward buffering with upload confirmation | Record storage (Lamp Node / Group Controller) | src/sslv1/nodes/group_controller.py (forward_upstream and the pending-upload queue) | test_group_controller.py::test_records_are_buffered_while_upstream_is_unavailable, ::test_buffered_records_are_uploaded_after_recovery, ::test_no_duplicate_upload_of_the_same_record; test_integration.py::test_offline_cycle_buffers_everything_and_replays_it_once, ::test_lost_confirmation_replays_without_duplicating_mcc_history, ::test_offline_upload_of_an_unidentifiable_record_stays_pending | `VERIFIED` |
| `PR-STORAGE-009` | Record lifecycle and retention policy | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (mark_uploaded / mark_confirmed / delete), src/sslv1/enums.py (RecordLifecycleState) | test_storage.py::test_upload_confirmation_does_not_delete_the_record, ::test_queue_removal_and_deletion_are_distinct_operations, ::test_pending_upload_records_cannot_be_deleted; test_scenarios.py::test_scenario_35_upload_confirmation_does_not_delete | `VERIFIED` |

### 5.13 Time model (Lamp Node / Group Controller)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-TIME-001` | RTC-backed local timekeeping | Time model (Lamp Node / Group Controller) | src/sslv1/time_model.py (LogicalClock, TimeModel) - logical only | test_time.py::test_clock_is_deterministic_and_monotonic | `VERIFIED` |
| `PR-TIME-002` | Offline timestamps with validity indication | Time model (Lamp Node / Group Controller) | src/sslv1/time_model.py (Timestamp.sync_state, TimeModel.uncertain) | test_scenarios.py::test_scenario_41_offline_timestamps_are_uncertain; test_group_controller.py::test_offline_timestamps_are_flagged_uncertain; test_integration.py::test_time_synchronization_propagates_and_is_visible_per_lamp, ::test_event_and_fault_timestamps_come_from_the_logical_clock_only | `VERIFIED` |
| `PR-TIME-003` | Time synchronization | Time model (Lamp Node / Group Controller) | src/sslv1/nodes/group_controller.py (synchronize_time), src/sslv1/nodes/lamp_node.py (time-sync handler) | test_scenarios.py::test_scenario_40_time_synchronization; test_group_controller.py::test_time_synchronization_reaches_every_node; test_integration.py::test_time_synchronization_propagates_and_is_visible_per_lamp | `VERIFIED` |
| `PR-TIME-004` | Time-uncertainty handling and recovery | Time model (Lamp Node / Group Controller) | src/sslv1/time_model.py (_refresh_uncertainty, mark_unsynchronized) | test_time.py::test_time_becomes_uncertain_after_the_threshold; test_integration.py::test_time_synchronization_propagates_and_is_visible_per_lamp | `VERIFIED` |
| `PR-TIME-005` | Physical RTC performance is not digitally validated | Time model (Lamp Node / Group Controller) | Documentation boundary only (no code) | docs/09_digital_prototype_scope.md states the boundary; docs/11_assumptions.md A-26 | `PLANNED` |

## 6. Requirements deliberately left unverified

These requirements are not `VERIFIED` because verifying them digitally would
over-claim. Each is a physical or external-dependency property.

| Requirement ID | Why it cannot be verified digitally |
| --- | --- |
| `PR-TIME-005` | Physical RTC accuracy and backup duration need real hardware and time; the digital model only proves the state machine. |
| `PR-SECURITY-004` | Tamper detection needs a real tamper source; only the event vocabulary exists. |
| `PR-SECURITY-005` | Security validation (key management, authentication strength) is explicitly out of the digital prototype's scope. |

## 7. Phase 14 fault-injection evidence

`tests/fault_injection.py` is a deterministic fault-injection harness (logical
clock, in-memory bus, injected readings, link and storage faults). The scenarios
are in `tests/test_fault_injection.py`; the harness and the scenarios are test
support, not production code, and they validate the digital model only.

| Area | Representative tests (`test_fault_injection.py` unless stated) | Requirements exercised |
| --- | --- | --- |
| 1. Lighting and sensor faults | `test_sensor_becoming_invalid_while_on_keeps_the_lamp_on_and_confirms`, `test_sensor_recovery_before_confirmation_leaves_no_stale_fault`, `test_threshold_oscillation_does_not_create_one_alert_per_crossing` | `PR-LIGHT-001`..`PR-LIGHT-005`, `PR-DIAG-005`, `PR-DIAG-006`, `PR-FAULT-005`, `PR-FAULT-006` |
| 2. Electrical measurement faults | `test_under_current_needs_consecutive_evidence_to_confirm`, `test_intervening_normal_evidence_breaks_consecutive_confirmation`, `test_current_while_commanded_off_is_unexpected_current`, `test_original_and_latest_evidence_are_kept_distinct` | `PR-DIAG-001`..`PR-DIAG-004`, `PR-MEASURE-001`, `PR-MEASURE-004`, `PR-FAULT-005`, `PR-FAULT-011` |
| 3. Switching-feedback faults | `test_commanded_state_is_never_confused_with_actual_state`, `test_feedback_on_while_commanded_off_is_not_a_silent_success`, `test_diagnostic_result_is_advisory_and_never_drives_the_switch` | `PR-CONTROL-002`, `PR-DIAG-002`, `PR-DIAG-003` |
| 4. Communication faults | `test_dropped_request_is_retried_only_within_the_absolute_deadline`, `test_corrupted_response_is_excluded_counted_and_recovered`, `test_duplicate_and_stale_frames_do_not_corrupt_receiver_state`, `test_sequence_wrap_keeps_new_traffic_valid_and_replay_detected` | `PR-COMM-003`, `PR-COMM-005`..`PR-COMM-009` |
| 5. Remote-command faults | `test_remote_force_on_lifecycle_is_ordered_and_evidence_based`, `test_every_remote_subtype_is_verified_from_node_evidence`, `test_lost_ack_times_out_to_failed_and_a_late_ack_cannot_resurrect_it`, `test_unauthorized_remote_command_never_reaches_the_bus` | `PR-CONTROL-001`..`PR-CONTROL-003`, `PR-COMM-007`, `PR-SECURITY-001`..`PR-SECURITY-003` |
| 6. Fault lifecycle | `test_confirmation_threshold_confirms_once_per_condition`, `test_recurrence_after_closure_creates_a_linked_new_record`, `test_illegal_fault_transitions_do_not_mutate_state`, `test_failed_verification_reactivates_the_fault` | `PR-FAULT-003`..`PR-FAULT-011` |
| 7. Notification faults | `test_repeated_observations_do_not_reset_notification_timers`, `test_reminder_is_issued_once_and_does_not_spam`, `test_escalation_happens_at_the_configured_deadline_not_before`, `test_delivery_failure_follows_the_configured_retry_path` | `PR-FAULT-007`..`PR-FAULT-009`, `PR-FAULT-013` |
| 8. Storage faults | `test_corrupt_record_is_never_confirmed_or_uploaded_and_recovery_discards_it`, `test_no_silent_loss_across_a_power_loss_cycle`, `test_unauthorized_deletion_is_rejected_audited_and_deletes_nothing` | `PR-STORAGE-001`..`PR-STORAGE-009` |
| 9. Time faults | `test_offline_node_never_claims_synchronized_time`, `test_delayed_sync_never_moves_time_backwards_or_fakes_sync`, `test_offline_records_keep_their_original_time_validity_after_later_sync` | `PR-TIME-001`..`PR-TIME-004` (`PR-TIME-005` stays `PLANNED`: physical RTC behaviour is not modelled) |
| 10. Multi-node containment | `test_sixteen_node_group_with_five_independent_failures_contains_them`, `test_scenario_h_sixteen_nodes_multiple_faults_leave_the_rest_running` | `PR-SCALABILITY-001`, `PR-SCALABILITY-002`, `PR-COMM-009` |
| 11. Store-and-forward | `test_upstream_outage_buffers_without_loss_or_local_impact`, `test_lost_confirmation_during_recovery_never_loses_or_duplicates_history`, `test_event_records_are_forwarded_and_confirmed_without_duplication` | `PR-STORAGE-008`, `PR-STORAGE-009`, `PR-OFFLINE-001`..`PR-OFFLINE-005` |
| 12. Scenarios A-J | `test_scenario_a_...` .. `test_scenario_j_...` (ten tests) | Cross-cutting: `PR-FAULT`, `PR-COMM`, `PR-CONTROL`, `PR-STORAGE`, `PR-TIME`, `PR-CONFIG`, `PR-OFFLINE`, `PR-SCALABILITY` |

`PR-SECURITY-004` (tamper detection) declares a Phase 14 digital test as its
verification method, but the digital model has no tamper source: only the
`TAMPER` fault category and the `TAMPER_INDICATION` event exist. The requirement
therefore stays `PLANNED` and is not claimed as exercised by this phase.

Focused regressions for the defects this phase found are kept out of the
fault-injection layer:

| Defect | Requirement | Focused regression test |
| --- | --- | --- |
| A validated pull left unanswered made a healthy node look like a failed link (`COMM_FAULT`) | `PR-COMM-007`, `PR-COMM-008` | `tests/test_post_merge.py::test_empty_measurement_pull_is_answered_and_buffers_no_record`, `::test_empty_fault_and_event_pulls_are_answered_without_phantom_records` |
| A live-only measurement reply (`record_sequence == 0`) was buffered again as a historical record, so idle polls duplicated history and the upload | `PR-STORAGE-008` (no duplicate upload of a record) | `tests/test_post_merge.py::test_live_only_measurement_reply_does_not_duplicate_the_historical_record` |
| The normal "lamp commanded off in bright ambient" observation was confirmed as a managed `ENVIRONMENTAL` fault and notified | `PR-DIAG-002`, `PR-FAULT-001`, `PR-FAULT-005` | `tests/test_fault.py::test_environmental_observation_never_becomes_a_confirmed_fault` |

## 8. Phase 15 Master Control Center data-layer evidence

`src/sslv1/mcc.py` is an in-memory aggregation layer over the existing
components (D-041). It owns no lamp control, fault lifecycle, event log,
storage or permission rule; it reads Group Controller registrations,
measurements, stored records and the existing event log, and routes operator
commands through the existing authorized command path. `tests/mcc_harness.py`
provides the deterministic system (sites, groups, 16-lamp nodes, controllers,
buses, one logical clock, one `AuthorizationService`).

| Area | Representative tests (`tests/test_mcc.py`) | Requirements exercised |
| --- | --- | --- |
| 1. Site / group / lamp registries | `test_site_is_created_and_listed`, `test_duplicate_site_is_rejected_and_changes_nothing`, `test_duplicate_group_at_one_site_is_rejected`, `test_same_group_id_at_two_sites_is_not_a_conflict`, `test_inconsistent_lamp_hierarchy_is_rejected` | `PR-IDENTITY-001`, `PR-IDENTITY-002`, `PR-SCALABILITY-002` |
| 2. Live snapshot | `test_lamp_status_reports_every_field_the_group_reported`, `test_lamp_status_invents_no_measurements_before_anything_is_reported`, `test_freshness_is_unknown_when_no_limit_is_configured` | `PR-MEASURE-001`, `PR-MEASURE-004`, `PR-CONTROL-002` |
| 3. Aggregation | `test_sixteen_lamp_group_aggregates_independently`, `test_two_group_site_aggregates_each_group_and_the_site`, `test_group_with_no_reported_data_is_unknown_not_healthy` | `PR-SCALABILITY-001`, `PR-SCALABILITY-002`, `PR-SCALABILITY-004` |
| 4. Degradation and containment | `test_one_unavailable_lamp_is_named_and_the_rest_stay_healthy`, `test_multiple_unavailable_lamps_are_all_listed`, `test_one_group_failure_does_not_hide_the_other_groups_health`, `test_degraded_link_is_reported_as_degraded_not_unavailable`, `test_healthy_group_does_not_conceal_a_faulted_lamp` | `PR-SCALABILITY-003`, `PR-COMM-008`, `PR-DIAG-002` |
| 5. Staleness | `test_lamp_status_is_stale_after_the_freshness_limit_and_not_healthy`, `test_invalid_freshness_limit_is_rejected` | `PR-TIME-001`, `PR-TIME-004` |
| 6. Fault visibility | `test_active_fault_visibility_carries_identity_state_and_severity`, `test_repeated_fault_polls_add_records_but_not_fault_identities`, `test_cleared_fault_disappears_from_the_active_view`, `test_fault_visibility_does_not_read_unreported_node_state`, `test_site_fault_count_spans_the_groups_without_mixing_them` | `PR-FAULT-003`, `PR-FAULT-007`, `PR-FAULT-012` |
| 7. Event and audit visibility | `test_events_are_aggregated_from_the_existing_group_logs`, `test_node_events_reach_the_mcc_only_through_the_group_records` | `PR-SECURITY-003`, `PR-STORAGE-008` |
| 8. Operator commands | `test_authorized_force_on_is_verified_from_a_fresh_observation`, `test_authorized_force_off_and_return_to_auto`, `test_every_supported_subtype_can_be_requested_through_the_mcc`, `test_duplicate_command_id_is_idempotent_through_the_mcc` | `PR-CONTROL-001`..`PR-CONTROL-003`, `PR-COMM-007` |
| 9. Authorization | `test_unauthorized_command_is_rejected_before_anything_is_transmitted`, `test_engineering_only_action_is_protected_even_through_the_mcc`, `test_admin_time_distribution_is_not_reachable_through_the_mcc_data_layer`, `test_mcc_command_is_traceable_to_actor_command_target_and_outcome` | `PR-SECURITY-001`, `PR-SECURITY-002`, `PR-SECURITY-003` |
| 10. Configuration readback | `test_configuration_readback_is_exposed_and_bounded`, `test_structured_configuration_writing_is_not_exposed_by_the_mcc` | `PR-CONFIG-001`, `PR-CONFIG-002` (limitation evidence only) |
| 11. Local independence | `test_lamps_keep_operating_while_the_mcc_has_never_polled`, `test_local_records_are_kept_while_the_mcc_is_unreachable` | `PR-OFFLINE-001`, `PR-OFFLINE-002`, `PR-OFFLINE-004` |
| 12. End-to-end scenarios | `test_scenario_two_group_site_with_an_isolated_failure`, `test_scenario_operator_handles_a_faulted_lamp_from_the_mcc`, `test_scenario_command_to_a_node_that_cannot_execute_it`, `test_scenario_second_site_stays_isolated_from_the_first` | Cross-cutting |

---

## 9. Phase 16 full-integration evidence

Phase 16 runs the whole hierarchy - Master Control Center over Group Controller
over Lamp Nodes - in one deterministic system with the real command,
authorization, communication, measurement, fault, notification, storage,
configuration and time components. The harness is
`tests/mcc_harness.py`; every scenario is in `tests/test_integration.py`
(38 tests in 13 sections) and is also summarised in
[13_integration_validation.md](13_integration_validation.md). Nothing in the
integration replaces a subsystem with a mock: the only stand-ins are the
modelled field devices and the in-memory bus.

| Area (integration section) | Tests | Requirements exercised |
| --- | --- | --- |
| Scenario A - normal automatic operation | `test_scenario_a_automatic_operation_from_registration_to_mcc_view`, `test_normal_operation_records_reach_the_mcc_upstream_end`, `test_a_lamp_step_alone_does_not_change_the_mcc_view` | `PR-LIGHT-001`, `PR-MEASURE-002`, `PR-STORAGE-008`, `PR-STORAGE-009` |
| Scenario B - FORCE_ON | `test_scenario_b_force_on_survives_the_automatic_decision`, `test_force_on_is_idempotent_and_never_reaches_a_second_lamp` | `PR-LIGHT-004`, `PR-CONTROL-002`, `PR-CONTROL-003`, `PR-SECURITY-001` |
| Scenario C - FORCE_OFF | `test_scenario_c_force_off_survives_the_automatic_decision` | `PR-LIGHT-004`, `PR-SECURITY-001` |
| Scenario D - RETURN_TO_AUTO | `test_scenario_d_return_to_auto_resumes_automatic_control` | `PR-LIGHT-005`, `PR-CONTROL-002` |
| Fault path to the operator layer | `test_fault_path_from_measurement_to_mcc_and_back_to_clear`, `test_fault_records_reach_the_mcc_upstream_end_after_recovery`, `test_a_fault_clear_is_scoped_to_its_own_fault_and_keeps_history`, `test_fault_visibility_never_claims_a_fault_the_group_did_not_receive`, `test_concurrent_confirmed_faults_are_bounded_by_the_single_fault_report_pull` | `PR-FAULT-003`..`PR-FAULT-012` |
| Offline / store-and-forward A-H | `test_offline_cycle_buffers_everything_and_replays_it_once`, `test_offline_upload_of_an_unidentifiable_record_stays_pending`, `test_lost_confirmation_replays_without_duplicating_mcc_history` | `PR-OFFLINE-001`..`PR-OFFLINE-005`, `PR-STORAGE-008`, `PR-STORAGE-009` |
| Restart / reconstruction | `test_controller_restart_drops_transient_state_and_keeps_persistence`, `test_node_restart_keeps_identity_and_configuration_and_fails_the_command`, `test_mcc_reconstruction_from_the_same_controllers_reproduces_the_view`, `test_record_recovery_discards_damage_without_faking_mcc_history` | `PR-CONTROL-005`, `PR-STORAGE-003`, `PR-STORAGE-004`, `PR-IDENTITY-002` |
| Multi-group / multi-site isolation | `test_commands_and_faults_reach_only_the_intended_group_and_lamp`, `test_one_groups_link_failure_cannot_contaminate_another_group`, `test_same_identifier_in_two_sites_is_two_different_systems` | `PR-IDENTITY-001`, `PR-IDENTITY-003`, `PR-SCALABILITY-002`, `PR-SCALABILITY-003` |
| Communication integration | `test_a_silent_node_is_unavailable_at_the_mcc_while_its_neighbours_report`, `test_wrong_destination_wrong_version_and_duplicate_frames_are_contained`, `test_a_command_to_a_missing_or_foreign_target_is_refused_locally`, `test_mcc_polling_uses_the_existing_poll_and_timeout_paths` | `PR-COMM-003`..`PR-COMM-009` |
| Configuration integration | `test_configuration_change_is_authorized_applied_and_verified_end_to_end`, `test_configuration_write_requires_privilege_and_a_newer_version`, `test_configuration_accepted_is_not_configuration_applied` | `PR-CONFIG-002`..`PR-CONFIG-005` |
| Time / freshness integration | `test_time_synchronization_propagates_and_is_visible_per_lamp`, `test_stale_measurements_are_never_presented_as_current`, `test_a_group_that_never_reported_is_unknown_not_healthy`, `test_event_and_fault_timestamps_come_from_the_logical_clock_only` | `PR-TIME-002`..`PR-TIME-004`, `PR-MEASURE-002` (currency of a reported value) |
| Digital / software-scale validation | `test_two_sites_of_two_sixteen_lamp_groups_operate_deterministically`, `test_scale_aggregation_keeps_every_lamp_addressable` | `PR-SCALABILITY-001`..`PR-SCALABILITY-003` |
| Negative / authorization integration | `test_unauthorized_operator_actions_never_reach_the_field_layer`, `test_engineering_only_actions_stay_protected_through_the_whole_path`, `test_mcc_never_becomes_the_source_of_truth_for_lamp_state` | `PR-SECURITY-001`, `PR-SECURITY-002`, `PR-SECURITY-003`, `PR-SECURITY-006` |

Three findings from this phase are recorded rather than smoothed over:

1. `PR-FAULT-007` **moved to `PARTIAL`**: a lamp may hold concurrent confirmed
   faults (`docs/03`), but the `FAULT_REPORT` pull carries one snapshot, so the
   second fault is not propagated while the first is the snapshot, and a fault
   closed while another is being reported is not cleared at the MCC. The
   limitation is pinned by a test; the fix is a fault-set report, a later-phase
   wire change.
2. `PR-OFFLINE-005` **stays `PARTIAL`**: the
   `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM` orchestration now
   exists as `GroupController.resynchronize_upstream` and is exercised end to
   end, including the not-recovered case; the automatic trigger is not
   implemented because the digital model has no background scheduler.
3. `PR-SCALABILITY-002` **stays `PARTIAL`**: 2 sites x 2 groups x 16 lamps run
   and aggregate in one deterministic system, but this is digital/software-scale
   evidence only - no embedded resource, bus-timing or production deployment
   claim.

The two production fixes made during this phase (all-unavailable group
aggregation; the Group Controller's time-synchronization claim) are recorded
with their requirement, consequence and tests in
[13_integration_validation.md](13_integration_validation.md) section 13.

Phase 16 adds **no** database, no second MCC state copy, no new fault semantics
and no new architecture.

---

This phase changed one status: `PR-FAULT-007` moved from `VERIFIED` to
`PARTIAL` (concurrent-fault limit of the single-snapshot fault pull, section 9).
The consequent eight PARTIAL rows are `PR-CONFIG-001`, `PR-CONFIG-002`,
`PR-FAULT-007`, `PR-FAULT-011`, `PR-COMM-008`, `PR-SCALABILITY-002`,
`PR-STORAGE-007` and `PR-OFFLINE-005`; the three PLANNED rows
(`PR-TIME-005`, `PR-SECURITY-004`, `PR-SECURITY-005`) are unchanged. The
data layer proves deterministic aggregation over the digital model only: it is
not a GUI, application, cloud service, database-backed backend or physical
deployment, and none of those are claimed.

---

## Corrective evidence and scoped limitations

The complete corrective regression suite is `tests/test_post_merge.py`; the
implementation report maps findings to these tests and records final checks.
Existing evidence above remains useful but is not sufficient in isolation for
remote authorization, fresh actual verification, retries, configuration readback
or retention integration.

| Requirement | Remaining scope / reason for PARTIAL |
| --- | --- |
| `PR-CONFIG-001` | Structured clear policies and group-scope mappings remain deferred; see configuration field audit. The Phase 16 integration verifies the supported integer-scalar subset end to end (`test_integration.py::test_configuration_change_is_authorized_applied_and_verified_end_to_end`, `::test_configuration_accepted_is_not_configuration_applied`), but the MCC exposes readback only and adds no configuration writer, and the time-staleness window is not a bus-carried parameter. |
| `PR-CONFIG-002` | The supported remote integer-scalar subset is tested, now including authority, version ordering, atomic application and readback verification in one end-to-end run (`test_integration.py::test_configuration_write_requires_privilege_and_a_newer_version`, `::test_configuration_change_is_authorized_applied_and_verified_end_to_end`). Structured schedules and remaining fields are not on the bus, and the MCC offers no structured write path. |
| `PR-FAULT-011` | Authorized externally supplied verification outcome; no automatic repair-evidence comparator or physical repair proof. |
| `PR-FAULT-007` | The Phase 16 integration verifies detection -> confirmation -> retention -> `FAULT_REPORT` -> MCC summary -> repair/closure end to end, and a clear is scoped to its own fault identity. It also exposed the limit of the single-snapshot `FAULT_REPORT` pull: with concurrent confirmed faults only one is propagated, and a fault closed while another is being reported is not cleared at the MCC (`test_integration.py::test_concurrent_confirmed_faults_are_bounded_by_the_single_fault_report_pull`). A fault-set report is a later-phase wire change, so the requirement is PARTIAL. |
| `PR-COMM-008` | Communication FSM/deadlines/events tested, and the Phase 16 integration now exercises the full `COMM_HEALTHY -> RETRY -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY` path end to end with a `COMM_RECOVERED` event carrying previous/current state (`test_integration.py::test_a_silent_node_is_unavailable_at_the_mcc_while_its_neighbours_report`). Automatic GC link-fault adaptation into the per-lamp managed fault workflow is still not implemented. |
| `PR-SCALABILITY-002` | The Phase 16 integration runs 2 sites x 2 groups x 16 lamps (64 lamps, 4 controllers) in one deterministic system with correct aggregation, isolation and determinism (`test_integration.py::test_two_sites_of_two_sixteen_lamp_groups_operate_deterministically`, `::test_one_groups_link_failure_cannot_contaminate_another_group`), and the measured cycle/aggregation timings are recorded in `docs/13` section 12. This is digital/software-scale evidence only: a production multi-group/multi-site deployment with persistence, resource bounds and hardware timing is not implemented, so the requirement stays PARTIAL. |
| `PR-STORAGE-007` | Configuration is separate from record objects; calibration storage and physical flash separation are not implemented. |
| `PR-OFFLINE-005` | The documented `STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM` sequence is now one deterministic step (`GroupController.resynchronize_upstream`, driven by `MasterControlCenter.recover_upstream`) and is tested end to end, including the not-recovered case where nothing is claimed as delivered (`test_integration.py::test_offline_cycle_buffers_everything_and_replays_it_once`, `::test_fault_records_reach_the_mcc_upstream_end_after_recovery`). What remains unimplemented is the automatic *trigger*: the digital model has no background scheduler, so recovery is detected by the caller before the step runs. |

The local persistence and RTC-backed requirement rows verify **in-memory
restart/logical-time semantics only**, not disk/flash persistence or physical
RTC hardware. Notification delivery is injected, not an external messaging
service. Security metadata is asserted on a trusted simulated bus; no peer
authentication, cryptography or production permission matrix is claimed.
