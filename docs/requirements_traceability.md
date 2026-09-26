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
| Verification status | One of `VERIFIED`, `IMPLEMENTED`, `PLANNED` (see section 3). |

`VERIFIED` means: the module exists, the named test exists, and the full suite
passes. `VERIFIED` is a **digital prototype** verification only. It never means
that a physical property (electrical safety, EMC, RF, thermal, enclosure/IP,
relay lifetime, RTC backup duration or certification) has been validated.

## 3. Status definitions

| Status | Meaning |
| --- | --- |
| `VERIFIED` | Implemented in `src/sslv1/` and covered by a deterministic test that passes. Digital prototype only. |
| `IMPLEMENTED` | Implemented in `src/sslv1/` but not yet covered by a named test. |
| `PLANNED` | Not implemented. Reserved for physical-only requirements, requirements needing a real tamper source, and work belonging to a later phase. |

## 4. Verification summary

| Status | Count |
| --- | --- |
| `VERIFIED` | 84 |
| `IMPLEMENTED` | 1 |
| `PLANNED` | 3 |

Reproduce with `python3 -m pytest` from the repository root. The suite is
deterministic: no wall-clock time, no randomness, no hardware access.

## 5. Traceability matrix

### 5.1 Lighting control (Lamp Node)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-LIGHT-001` | Automatic sensor-based control (AUTO_SENSOR) | Lighting control (Lamp Node) | src/sslv1/control.py (ControlModel), src/sslv1/nodes/lamp_node.py | test_scenarios.py::test_scenario_01_automatic_sensor_on_when_dark; test_control.py::test_automatic_sensor_switches_lamp_on_below_threshold | `VERIFIED` |
| `PR-LIGHT-002` | Schedule-with-sensor control (AUTO_SCHEDULE_SENSOR) | Lighting control (Lamp Node) | src/sslv1/control.py (ControlModel), src/sslv1/configuration.py (Schedule) | test_scenarios.py::test_scenario_06_schedule_plus_sensor; test_control.py::test_schedule_sensor_mode_uses_sensor_inside_window, ::test_schedule_sensor_mode_applies_out_of_window_state | `VERIFIED` |
| `PR-LIGHT-003` | Fixed-schedule control (FIXED_SCHEDULE) | Lighting control (Lamp Node) | src/sslv1/configuration.py (Schedule), src/sslv1/control.py (ControlModel) | test_scenarios.py::test_scenario_05_fixed_schedule_ignores_light_level; test_control.py::test_fixed_schedule_ignores_light_level, ::test_fixed_schedule_handles_window_wrapping_midnight | `VERIFIED` |
| `PR-LIGHT-004` | Authorized operator override (FORCE_ON / FORCE_OFF) | Lighting control (Lamp Node) | src/sslv1/control.py (apply_override), src/sslv1/nodes/lamp_node.py | test_scenarios.py::test_scenario_07_force_on, ::test_scenario_08_force_off; test_control.py::test_force_on_overrides_automatic_logic, ::test_force_off_overrides_automatic_logic | `VERIFIED` |
| `PR-LIGHT-005` | Return to automatic mode (RETURN_TO_AUTO operator command) | Lighting control (Lamp Node) | src/sslv1/control.py (clear_override), src/sslv1/nodes/lamp_node.py | test_scenarios.py::test_scenario_09_return_to_auto_is_a_command_not_a_mode; test_control.py::test_return_to_auto_clears_override, test_control.py::test_return_to_auto_is_not_a_persistent_mode | `VERIFIED` |

### 5.2 RS-485 field bus / Group Controller

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-COMM-001` | RS-485 master/slave discipline | RS-485 field bus / Group Controller | src/sslv1/comm/bus.py (InMemoryBus master/slave discipline), src/sslv1/nodes/lamp_node.py | test_group_controller.py::test_group_controller_manages_multiple_nodes | `VERIFIED` |
| `PR-COMM-002` | Node addressing and group size | RS-485 field bus / Group Controller | src/sslv1/identity.py (BusAddress), src/sslv1/nodes/group_controller.py (register_node) | test_group_controller.py::test_group_controller_supports_the_initial_group_target, ::test_group_controller_is_not_limited_to_sixteen; test_scenarios.py::test_scenario_47_group_controller_capacity, ::test_scenario_48_duplicate_registration_is_rejected | `VERIFIED` |
| `PR-COMM-003` | Frame format | RS-485 field bus / Group Controller | src/sslv1/comm/frame.py (Frame, encode_frame, decode_frame) | test_comm.py::test_frame_contains_every_required_field, ::test_frame_round_trip, ::test_bad_start_of_frame_is_rejected, ::test_unknown_message_type_code_is_rejected, ::test_address_range_is_enforced | `VERIFIED` |
| `PR-COMM-004` | Initial message type set | RS-485 field bus / Group Controller | src/sslv1/enums.py (MessageType, 17 values) | test_comm.py::test_message_type_set_is_complete | `VERIFIED` |
| `PR-COMM-005` | Sequence numbering, duplicate and replay handling | RS-485 field bus / Group Controller | src/sslv1/comm/protocol.py + src/sslv1/nodes/group_controller.py (sequence tracking) | test_group_controller.py::test_unregistered_frame_is_rejected; test_comm.py::test_message_type_codes_are_stable | `VERIFIED` |
| `PR-COMM-006` | CRC integrity verification | RS-485 field bus / Group Controller | src/sslv1/comm/crc.py, src/sslv1/comm/frame.py | test_comm.py::test_crc_failure_is_detected, ::test_bus_corruption_is_detectable | `VERIFIED` |
| `PR-COMM-007` | Polling, timeout and retry policy | RS-485 field bus / Group Controller | src/sslv1/nodes/group_controller.py (poll, poll_timeout_ticks, poll_retry_count) | test_group_controller.py::test_communication_fault_is_detected_after_retries | `VERIFIED` |
| `PR-COMM-008` | Communication state machine | RS-485 field bus / Group Controller | src/sslv1/comm/state_machine.py (CommunicationStateMachine) | test_comm.py::test_healthy_to_retry_to_degraded_to_fault, ::test_recovery_returns_to_healthy, ::test_retry_recovers_to_healthy | `VERIFIED` |
| `PR-COMM-009` | Communication failure must not stop local operation | RS-485 field bus / Group Controller | src/sslv1/nodes/lamp_node.py (local control independent of the bus) | test_group_controller.py::test_communication_fault_does_not_stop_local_lighting; test_scenarios.py::test_scenario_38_communication_retry_then_degraded | `VERIFIED` |
| `PR-COMM-010` | Command subtypes carried inside CONTROL_COMMAND | RS-485 field bus / Group Controller | src/sslv1/enums.py (ControlSubtype), src/sslv1/comm/protocol.py (CONTROL_COMMAND payload) | test_command.py::test_reset_energy_is_a_control_subtype_not_a_message_type; test_comm.py::test_control_command_payload_carries_reset_energy_subtype | `VERIFIED` |

### 5.3 Configuration management

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-CONFIG-001` | Configuration parameter set | Configuration management | src/sslv1/configuration.py (LampConfiguration) | test_configuration.py::test_configuration_covers_every_documented_parameter | `VERIFIED` |
| `PR-CONFIG-002` | Configuration read and write over the bus | Configuration management | src/sslv1/nodes/group_controller.py (distribute_configuration), src/sslv1/nodes/lamp_node.py (configuration read and write handlers) | test_group_controller.py::test_configuration_distribution_is_acknowledged, ::test_invalid_configuration_is_rejected_by_the_node | `VERIFIED` |
| `PR-CONFIG-003` | Configuration validation | Configuration management | src/sslv1/configuration.py (LampConfiguration.validate / validated) | test_scenarios.py::test_scenario_44_configuration_validation; test_configuration.py::test_validation_rejects_every_invalid_threshold, ::test_hysteresis_wider_than_the_dead_band_is_rejected | `VERIFIED` |
| `PR-CONFIG-004` | Configuration change auditability | Configuration management | src/sslv1/event.py (EventLog), src/sslv1/nodes/lamp_node.py (_record_event) | test_scenarios.py::test_scenario_49_important_transitions_generate_events, ::test_scenario_50_rejected_command_is_audited | `VERIFIED` |
| `PR-CONFIG-005` | Configuration persistence and versioning | Configuration management | src/sslv1/nodes/lamp_node.py (config_version, _apply_config_parameters) | test_group_controller.py::test_configuration_distribution_is_acknowledged (config_version is carried) | `VERIFIED` |
| `PR-CONFIG-006` | No hardcoded operational thresholds | Configuration management | src/sslv1/configuration.py (every threshold is a field, none is a module constant) | test_scenarios.py::test_scenario_45_every_threshold_is_configurable; test_configuration.py::test_no_operational_threshold_is_hardcoded, ::test_two_nodes_can_use_different_thresholds | `VERIFIED` |

### 5.4 Control model (Lamp Node)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-CONTROL-001` | Mode priority ordering | Control model (Lamp Node) | src/sslv1/control.py (ControlLayer, ControlModel.decide) | test_scenarios.py::test_scenario_10_override_beats_automatic_mode, ::test_scenario_11_safety_outranks_the_override; test_control.py::test_override_beats_automatic_mode, ::test_safety_protection_beats_override | `VERIFIED` |
| `PR-CONTROL-002` | Command lifecycle and success definition | Control model (Lamp Node) | src/sslv1/command.py (CommandLifecycle, CommandService) | test_scenarios.py::test_scenario_13_command_lifecycle_reaches_verification; test_command.py::test_command_lifecycle_reaches_actual_state_verified, ::test_receipt_alone_is_not_success | `VERIFIED` |
| `PR-CONTROL-003` | Duplicate command handling | Control model (Lamp Node) | src/sslv1/command.py (CommandService.submit duplicate suppression) | test_scenarios.py::test_scenario_14_duplicate_command_is_suppressed; test_command.py::test_duplicate_command_is_not_executed_twice, ::test_duplicate_command_does_not_toggle_the_lamp | `VERIFIED` |
| `PR-CONTROL-004` | Command authorization status | Control model (Lamp Node) | src/sslv1/command.py (CommandService authorization), src/sslv1/authorization.py | test_scenarios.py::test_scenario_15_unauthorized_command_is_rejected; test_command.py::test_unauthorized_operator_cannot_force_the_lamp, ::test_unauthenticated_actor_is_rejected | `VERIFIED` |
| `PR-CONTROL-005` | Safe state restoration after restart | Control model (Lamp Node) | src/sslv1/nodes/lamp_node.py (start, restart and the configured restart default) | test_control.py::test_return_to_auto_clears_override | `VERIFIED` |
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
| `PR-FAULT-007` | Fault notification | Fault management (Lamp Node) | src/sslv1/notification.py (NotificationEngine) | test_fault.py::test_not_required_when_ack_not_configured | `VERIFIED` |
| `PR-FAULT-008` | Acknowledgement, reminder and escalation | Fault management (Lamp Node) | src/sslv1/notification.py (tick, acknowledge, delivery failure handling) | test_fault.py::test_reminder_and_escalation_do_not_change_fault_state, ::test_notification_failure_is_retried_then_reported | `VERIFIED` |
| `PR-FAULT-009` | Unacknowledged alerts must not switch the lamp OFF | Fault management (Lamp Node) | src/sslv1/nodes/lamp_node.py (no notification-to-lighting coupling) | test_scenarios.py::test_scenario_30_fault_acknowledgement_does_not_dim_the_light | `VERIFIED` |
| `PR-FAULT-010` | Repair workflow | Fault management (Lamp Node) | src/sslv1/fault.py (acknowledge, start_repair, report_repaired) | test_fault.py::test_repair_workflow, ::test_repair_cannot_start_before_acknowledgement | `VERIFIED` |
| `PR-FAULT-011` | Verification workflow and failed verification | Fault management (Lamp Node) | src/sslv1/fault.py (verify) | test_fault.py::test_successful_verification_closes_the_fault, ::test_failed_verification_returns_to_an_active_fault_state; test_scenarios.py::test_scenario_32_failed_verification_reopens_the_fault | `VERIFIED` |
| `PR-FAULT-012` | Fault closure and failure containment | Fault management (Lamp Node) | src/sslv1/fault.py (FaultLifecycle CLOSED transition), src/sslv1/nodes/lamp_node.py (per-node engines) | test_fault.py::test_one_nodes_fault_does_not_affect_another_node; test_scenarios.py::test_scenario_46_multi_node_isolation | `VERIFIED` |
| `PR-FAULT-013` | Notification state independent of fault lifecycle | Fault management (Lamp Node) | src/sslv1/notification.py (NotificationLifecycle, independent of FaultLifecycle) | test_fault.py::test_notification_state_is_independent_of_fault_lifecycle, ::test_notified_is_not_a_fault_lifecycle_state; test_scenarios.py::test_scenario_33_notification_state_independent | `VERIFIED` |
| `PR-FAULT-014` | Fault category, diagnostic classification and root cause | Fault management (Lamp Node) | src/sslv1/diagnostics.py (classification vs category), src/sslv1/fault.py (no root-cause field) | test_diagnostics.py::test_fault_category_and_classification_are_distinct; test_scenarios.py::test_scenario_18_under_current_and_open_load | `VERIFIED` |

### 5.7 Device identity and addressing

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-IDENTITY-001` | Identity hierarchy | Device identity and addressing | src/sslv1/identity.py (DeviceIdentity, Identifier, McuUniqueId) | test_identity.py::test_identity_hierarchy_is_complete | `VERIFIED` |
| `PR-IDENTITY-002` | Deterministic and persistent identity | Device identity and addressing | src/sslv1/identity.py (Identifier is value-based) | test_identity.py::test_identity_is_deterministic_and_value_based | `VERIFIED` |
| `PR-IDENTITY-003` | Bus address uniqueness | Device identity and addressing | src/sslv1/identity.py (BusAddress, MIN/MAX), src/sslv1/nodes/group_controller.py (register_node) | test_identity.py::test_bus_address_range_is_enforced, ::test_duplicate_registration_is_rejected | `VERIFIED` |
| `PR-IDENTITY-004` | Identity query | Device identity and addressing | src/sslv1/nodes/group_controller.py (identify), src/sslv1/nodes/lamp_node.py (identify handler) | test_group_controller.py::test_group_snapshot_reports_communication_state; test_comm.py::test_identify_payload_round_trip | `VERIFIED` |

### 5.8 Measurement handling (Lamp Node)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-MEASURE-001` | Per-lamp measurement set | Measurement handling (Lamp Node) | src/sslv1/measurement.py (Measurement), src/sslv1/nodes/lamp_node.py (measurement construction) | test_scenarios.py::test_scenario_17_normal_measurement; test_measurement.py | `VERIFIED` |
| `PR-MEASURE-002` | Configurable measurement and reporting intervals | Measurement handling (Lamp Node) | src/sslv1/configuration.py (reporting_interval_ticks), src/sslv1/nodes/lamp_node.py | test_configuration.py::test_reporting_interval_is_configurable | `VERIFIED` |
| `PR-MEASURE-003` | Energy accumulation | Measurement handling (Lamp Node) | src/sslv1/nodes/lamp_node.py (energy accumulation and reset) | test_command.py::test_energy_reset_requires_authorization | `VERIFIED` |
| `PR-MEASURE-004` | Sensor validity reporting | Measurement handling (Lamp Node) | src/sslv1/measurement.py (MeasurementValidator), src/sslv1/enums.py (SensorStatus) | test_measurement.py::test_invalid_sensor_is_reported_not_guessed_around, ::test_invalid_sensor_retains_the_previous_lighting_decision | `VERIFIED` |
| `PR-MEASURE-005` | Monitoring values, not billing-grade metering | Measurement handling (Lamp Node) | src/sslv1/measurement.py (Measurement carries no billing flag) | test_scenarios.py::test_scenario_17_normal_measurement (asserts no billing-grade field) | `VERIFIED` |

### 5.9 Offline operation and buffering

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-OFFLINE-001` | Local operation without Internet | Offline operation and buffering | src/sslv1/nodes/lamp_node.py (no upstream dependency) | test_group_controller.py::test_communication_fault_does_not_stop_local_lighting | `VERIFIED` |
| `PR-OFFLINE-002` | Local operation without the Master Control Center | Offline operation and buffering | src/sslv1/nodes/lamp_node.py (local control only) | test_group_controller.py::test_communication_fault_does_not_stop_local_lighting | `VERIFIED` |
| `PR-OFFLINE-003` | Local operation without the Group Controller | Offline operation and buffering | src/sslv1/nodes/lamp_node.py (operates with no controller traffic) | test_group_controller.py::test_communication_fault_does_not_stop_local_lighting | `VERIFIED` |
| `PR-OFFLINE-004` | Offline record buffering | Offline operation and buffering | src/sslv1/storage.py (RecordStore buffering), src/sslv1/nodes/group_controller.py (pending queue) | test_group_controller.py::test_records_are_buffered_while_upstream_is_unavailable | `VERIFIED` |
| `PR-OFFLINE-005` | Post-recovery synchronization without silent loss | Offline operation and buffering | src/sslv1/nodes/group_controller.py (forward_upstream confirmed-only removal, no duplicate upload) | test_group_controller.py::test_buffered_records_are_uploaded_after_recovery, ::test_no_duplicate_upload_of_the_same_record, ::test_communication_recovery_resynchronizes | `VERIFIED` |

### 5.10 Group Controller / node management

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-SCALABILITY-001` | Lamps per group | Group Controller / node management | src/sslv1/nodes/group_controller.py (GroupControllerConfig.max_nodes) | test_scenarios.py::test_scenario_47_group_controller_capacity; test_group_controller.py::test_group_controller_supports_the_initial_group_target | `VERIFIED` |
| `PR-SCALABILITY-002` | Groups per site | Group Controller / node management | src/sslv1/identity.py (site/group hierarchy), src/sslv1/nodes/group_controller.py | test_group_controller.py::test_group_snapshot_reports_communication_state (group identity carried) | `VERIFIED` |
| `PR-SCALABILITY-003` | Failure containment | Group Controller / node management | src/sslv1/nodes/lamp_node.py (per-node state), src/sslv1/nodes/group_controller.py (per-node registration) | test_group_controller.py::test_one_silent_node_does_not_block_the_others, ::test_one_faulty_node_does_not_degrade_the_group; test_scenarios.py::test_scenario_46_multi_node_isolation | `VERIFIED` |
| `PR-SCALABILITY-004` | Architectural headroom | Group Controller / node management | src/sslv1/nodes/group_controller.py (max_nodes is configuration, not a fixed 16) | test_group_controller.py::test_group_controller_is_not_limited_to_sixteen | `VERIFIED` |
| `PR-SCALABILITY-005` | Group Controller local storage abstraction | Group Controller / node management | src/sslv1/nodes/group_controller.py (record buffering into RecordStore), src/sslv1/storage.py | test_group_controller.py::test_group_controller_local_storage_is_abstract | `VERIFIED` |

### 5.11 Authorization and audit

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-SECURITY-001` | Operator authorization for overrides | Authorization and audit | src/sslv1/authorization.py (AuthorizationService.require), src/sslv1/command.py | test_scenarios.py::test_scenario_15_unauthorized_command_is_rejected; test_command.py::test_unauthorized_operator_cannot_force_the_lamp | `VERIFIED` |
| `PR-SECURITY-002` | Command authentication status | Authorization and audit | src/sslv1/command.py (CommandRecord.authorization_status), src/sslv1/enums.py (AuthorizationStatus) | test_command.py::test_unauthenticated_actor_is_rejected | `VERIFIED` |
| `PR-SECURITY-003` | Audit trail | Authorization and audit | src/sslv1/event.py (EventLog, Event) | test_scenarios.py::test_scenario_49_important_transitions_generate_events, ::test_scenario_50_rejected_command_is_audited | `VERIFIED` |
| `PR-SECURITY-004` | Tamper detection | Authorization and audit | src/sslv1/enums.py (EventType.TAMPER_INDICATION, FaultType.TAMPER) - representation only | No test: no tamper source exists in the digital prototype | `PLANNED` |
| `PR-SECURITY-005` | Security validation boundary | Authorization and audit | Documentation boundary only (no code) | docs/09_digital_prototype_scope.md; src/sslv1/authorization.py docstring | `PLANNED` |
| `PR-SECURITY-006` | Preliminary operator roles | Authorization and audit | src/sslv1/authorization.py (_ROLE_ACTIONS, actions_for_role), src/sslv1/enums.py (Role, Action) | test_command.py::test_authorization_roles_cover_the_expected_actions | `VERIFIED` |

### 5.12 Record storage (Lamp Node / Group Controller)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-STORAGE-001` | Local persistent record storage | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (RecordStore) | test_storage.py::test_records_carry_the_required_envelope; test_scenarios.py::test_scenario_34_storage_record_lifecycle | `VERIFIED` |
| `PR-STORAGE-002` | Record structure | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (StorageRecord, compute_crc, is_valid) | test_storage.py::test_records_carry_the_required_envelope, ::test_uncommitted_record_is_not_valid | `VERIFIED` |
| `PR-STORAGE-003` | Power-loss safety | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (commit_marker, simulate_power_loss, recover) | test_storage.py::test_power_loss_discards_incomplete_records, ::test_power_loss_recovery_keeps_committed_records_uploadable; test_scenarios.py::test_scenario_37_power_loss_recovery | `VERIFIED` |
| `PR-STORAGE-004` | Corruption detection and handling | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (StorageRecord.compute_crc, detect_corruption, corrupt) | test_storage.py::test_corrupted_record_is_detected_and_flagged, ::test_corrupt_record_is_excluded_from_upload | `VERIFIED` |
| `PR-STORAGE-005` | Retention: automatic deletion off by default | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (RetentionPolicy.automatic_deletion defaults to False) | test_storage.py::test_automatic_deletion_is_disabled_by_default, ::test_retention_policy_requires_explicit_configuration | `VERIFIED` |
| `PR-STORAGE-006` | Storage-full visibility | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (StorageFullError, RecordStore.is_full) | test_storage.py::test_storage_full_is_explicit_and_never_silent; test_scenarios.py::test_scenario_36_storage_full_is_visible | `VERIFIED` |
| `PR-STORAGE-007` | Separation of configuration/calibration storage | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (RecordType separation) | test_storage.py::test_records_carry_the_required_envelope (record type is part of the envelope) | `VERIFIED` |
| `PR-STORAGE-008` | Store-and-forward buffering with upload confirmation | Record storage (Lamp Node / Group Controller) | src/sslv1/nodes/group_controller.py (forward_upstream and the pending-upload queue) | test_group_controller.py::test_records_are_buffered_while_upstream_is_unavailable, ::test_buffered_records_are_uploaded_after_recovery, ::test_no_duplicate_upload_of_the_same_record | `VERIFIED` |
| `PR-STORAGE-009` | Record lifecycle and retention policy | Record storage (Lamp Node / Group Controller) | src/sslv1/storage.py (mark_uploaded / mark_confirmed / delete), src/sslv1/enums.py (RecordLifecycleState) | test_storage.py::test_upload_confirmation_does_not_delete_the_record, ::test_queue_removal_and_deletion_are_distinct_operations, ::test_pending_upload_records_cannot_be_deleted; test_scenarios.py::test_scenario_35_upload_confirmation_does_not_delete | `VERIFIED` |

### 5.13 Time model (Lamp Node / Group Controller)

| Requirement ID | Requirement | Architecture element | Implementation module | Test evidence | Verification status |
| --- | --- | --- | --- | --- | --- |
| `PR-TIME-001` | RTC-backed local timekeeping | Time model (Lamp Node / Group Controller) | src/sslv1/time_model.py (LogicalClock, TimeModel) - logical only | test_time.py::test_clock_is_deterministic_and_monotonic | `IMPLEMENTED` |
| `PR-TIME-002` | Offline timestamps with validity indication | Time model (Lamp Node / Group Controller) | src/sslv1/time_model.py (Timestamp.sync_state, TimeModel.uncertain) | test_scenarios.py::test_scenario_41_offline_timestamps_are_uncertain; test_group_controller.py::test_offline_timestamps_are_flagged_uncertain | `VERIFIED` |
| `PR-TIME-003` | Time synchronization | Time model (Lamp Node / Group Controller) | src/sslv1/nodes/group_controller.py (synchronize_time), src/sslv1/nodes/lamp_node.py (time-sync handler) | test_scenarios.py::test_scenario_40_time_synchronization; test_group_controller.py::test_time_synchronization_reaches_every_node | `VERIFIED` |
| `PR-TIME-004` | Time-uncertainty handling and recovery | Time model (Lamp Node / Group Controller) | src/sslv1/time_model.py (_refresh_uncertainty, mark_unsynchronized) | test_time.py::test_time_becomes_uncertain_after_the_threshold | `VERIFIED` |
| `PR-TIME-005` | Physical RTC performance is not digitally validated | Time model (Lamp Node / Group Controller) | Documentation boundary only (no code) | docs/09_digital_prototype_scope.md states the boundary; docs/11_assumptions.md A-26 | `PLANNED` |

## 6. Requirements deliberately left unverified

These requirements are not `VERIFIED` because verifying them digitally would
over-claim. Each is a physical or external-dependency property.

| Requirement ID | Why it cannot be verified digitally |
| --- | --- |
| `PR-TIME-005` | Physical RTC accuracy and backup duration need real hardware and time; the digital model only proves the state machine. |
| `PR-SECURITY-004` | Tamper detection needs a real tamper source; only the event vocabulary exists. |
| `PR-SECURITY-005` | Security validation (key management, authentication strength) is explicitly out of the digital prototype's scope. |
