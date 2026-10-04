# 07 - Configuration

## 1. Document purpose

This document defines the **configuration model** for Smart Street Light V1:
the parameter set, its scope, how it is distributed, validated, persisted and
audited.

It is derived from `PR-CONFIG-*` in
[02_product_requirements.md](02_product_requirements.md).

---

## 2. Configuration scope

```text
SITE scope     -> applies to all groups and lamps at a site
GROUP scope    -> applies to all lamps in a group
LAMP scope     -> applies to a single lamp node
```

The mapping of each parameter to a scope is a design decision for Phase 12.
This document defines the parameter set, not the scope assignment.

---

## 3. Parameter set

### 3.1 Lighting control

| Parameter | Description | Type |
| --- | --- | --- |
| `configured_mode` | Persistent automatic mode (see [03_data_model.md](03_data_model.md#4-2-value-domains)). | enum |
| `light_on_threshold` | Light level below which the lamp switches ON. | quantity |
| `light_off_threshold` | Light level above which the lamp switches OFF. | quantity |
| `hysteresis` | Hysteresis applied to light thresholds. | quantity |
| `schedule` | Time windows and fixed ON/OFF times. | structure |

### 3.2 Measurement and reporting

| Parameter | Description | Type |
| --- | --- | --- |
| `measurement_interval` | Measurement sampling interval. | duration |
| `reporting_interval` | Reporting interval to the Group Controller. | duration |

### 3.3 Fault handling

| Parameter | Description | Type |
| --- | --- | --- |
| `fault_confirmation_count` | Observations required to confirm a fault. | integer |
| `fault_confirmation_window` | Time window for confirmation observations. | duration |
| `fault_clear_policy` | Conditions required to clear a latched fault. | structure |

### 3.4 Communication

| Parameter | Description | Type |
| --- | --- | --- |
| `comm_retry_count` | Retry attempts before declaring a communication fault. | integer |
| `comm_timeout` | Response timeout. | duration |

### 3.5 Notification and escalation

| Parameter | Description | Type |
| --- | --- | --- |
| `ack_required` | Whether a fault notification requires acknowledgement. | boolean |
| `ack_reminder_interval` | Reminder interval for unacknowledged notifications. | duration |
| `escalation_timeout` | Time before an unacknowledged notification escalates. | duration |
| `escalation_destination` | Escalation destination (actor or role). | identifier |
| `notification_retry_count` | Notification delivery retry attempts. | integer |

### 3.6 Identity

| Parameter | Description | Type |
| --- | --- | --- |
| `product_id` | Product identifier. | identifier |
| `site_id` | Site identifier. | identifier |
| `group_id` | Group identifier. | identifier |
| `lamp_id` | Lamp identifier. | identifier |
| `bus_address` | RS-485 address within the group. | integer |

### 3.7 System

| Parameter | Description | Type |
| --- | --- | --- |
| `restart_default_state` | State applied after restart. | enum |
| `retention_policy` | Record retention configuration (default: no automatic deletion). | structure |
| `minimum_retention` | Hard minimum retention enforced regardless of policy (value not yet decided). | duration |
| `storage_full_behaviour` | Behaviour when storage is full (to be decided). | enum |
| `energy_reset_authorization` | Authorization rule required to reset accumulated energy. | structure |

---

## 4. Defaults

| Parameter group | Default status |
| --- | --- |
| `configured_mode` | Not specified in this document; site configuration (`AUTO_SENSOR` in the digital prototype fixture). |
| Thresholds and hysteresis | **No default values are specified in this document.** Values are site configuration. |
| `retention_policy` | Automatic deletion **disabled** (`PR-STORAGE-005`). |
| `minimum_retention` | **Undecided** - open assumption (A-29). |
| `storage_full_behaviour` | **Undecided** - open assumption (A-09). |
| `restart_default_state` | **Undecided** - open assumption (A-08). |

No numeric operational threshold is committed by this document
(`PR-CONFIG-006`).

---

## 5. Distribution

```text
Master Control Center / operator
            |
            v
     GROUP CONTROLLER
            |
            | CONFIG_WRITE
            v
       LAMP NODE(S)
            |
            | CONFIG_ACK
            v
     GROUP CONTROLLER
```

| Step | Behaviour |
| --- | --- |
| Read | `CONFIG_READ` requests the current configuration. |
| Write | `CONFIG_WRITE` pushes new configuration. |
| Acknowledge | `CONFIG_ACK` reports acceptance or rejection with a reason. |

`PR-CONFIG-002`.

---

## 6. Validation

| Rule | Behaviour |
| --- | --- |
| Range check | Values outside permitted range are rejected. |
| Consistency check | Mutually inconsistent values (for example ON threshold above OFF threshold without hysteresis) are rejected. |
| Enum check | Unknown enum values are rejected. |
| Rejection handling | Previous valid configuration remains in effect; rejection is reported and recorded. |

`PR-CONFIG-003`.

---

## 7. Auditability

Every configuration change is recorded as an event containing:

| Field | Description |
| --- | --- |
| `timestamp` | When the change occurred. |
| `actor` | Who or what made the change. |
| `parameter` | Which parameter changed. |
| `previous_value` | Value before the change. |
| `new_value` | Value after the change. |
| `result` | Accepted or rejected. |

`PR-CONFIG-004`, `PR-SECURITY-003`.

---

## 8. Persistence and versioning

| Aspect | Behaviour |
| --- | --- |
| Persistence | Configuration survives restart (`PR-CONFIG-005`). |
| Versioning | Each configuration set carries a reportable version identifier. |
| Storage location | MCU internal Flash, separate from record storage (`PR-STORAGE-007`). |
| Invalid configuration | Node falls back to the last known valid configuration. |

---

## 9. Configuration change workflow

```text
1. operator issues configuration change
2. authorization checked
3. configuration validated
4. configuration distributed (CONFIG_WRITE)
5. node applies configuration
6. node acknowledges (CONFIG_ACK)
7. change recorded as an auditable event
8. new configuration version reported
```

A change is not effective until it has been applied and acknowledged.

---

## 10. Configuration and requirements

Configuration values are **not** requirements. The requirement is that the
parameter exists, is configurable, is validated, is persisted and is
auditable. The values themselves are site engineering decisions.

| Item | Classification |
| --- | --- |
| Existence of a parameter | Requirement (`PR-CONFIG-001`) |
| Configurability of a parameter | Requirement (`PR-CONFIG-001`, `PR-CONFIG-006`) |
| Numeric value of a parameter | Configuration / design choice |

---

## 11. Traceability

| Topic | Requirements |
| --- | --- |
| Parameter set | `PR-CONFIG-001` |
| Read/write over bus | `PR-CONFIG-002` |
| Validation | `PR-CONFIG-003` |
| Auditability | `PR-CONFIG-004`, `PR-SECURITY-003` |
| Persistence and versioning | `PR-CONFIG-005` |
| No hardcoded thresholds | `PR-CONFIG-006` |
| Related storage behaviour | `PR-STORAGE-005`, `PR-STORAGE-006`, `PR-STORAGE-007` |

---

## 12. Implementation status

| Item | Status |
| --- | --- |
| Parameter set defined | Yes |
| Validation rules defined | Yes (rule level) |
| Audit model defined | Yes |
| Default values | **Not decided** |
| Implementation | Digital implementation; bounded remote subset (see corrective contract below) |

---

## 13. Related documents

- [02_product_requirements.md](02_product_requirements.md)
- [03_data_model.md](03_data_model.md)
- [04_fault_management.md](04_fault_management.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)

## Corrective implementation contract and field audit

The immutable `LampConfiguration` held by `ControlModel.config` is the single
configured-mode authority; `LampNode.config` delegates to it. Node command
and supported bus configuration paths keep consumers synchronized. Direct
mutation of component internals is a test hook, not an authorized configuration
API. Node startup configuration version is **0**. Writes must have a positive
strictly newer version; version 1 is accepted first, then 2; stale, duplicate
and zero versions are rejected atomically with version/acceptance/reason in
CONFIG_ACK. Identical transport retries return the cached original ACK without
reapplying a write. SET_MODE also increments the configuration version.

The prototype's explicit numeric hysteresis convention is symmetric margin:
ON at `light <= light_on_threshold - light_hysteresis/2`; OFF at
`light >= light_off_threshold + light_hysteresis/2`; retain the previous state
between these inclusive boundaries. Zero margin preserves the original nominal
threshold dead band. The existing constraint `0 <= light_hysteresis <=
light_off_threshold - light_on_threshold` remains. This is a documented
simulation interpretation of configurable hysteresis, not a selected site
threshold or hardware sensor specification. Invalid light input retains state.

Every field below is declared/validated in `src/sslv1/configuration.py`.
Numeric configuration is finite and type checked; identity, enum, boolean,
ordering, count and duration constraints are checked before application.
The table accounts for all LampConfiguration fields, not merely field names.

| Fields | Consumer / validation focus | Tests and scope |
| --- | --- | --- |
| lamp_id, site_id, group_id, product_id, bus_address | Node constructor hierarchy/address agreement; identity, measurement, event and protocol reporting | test_identity.py; test_configuration.py; identity ACK integration |
| configured_mode | ControlModel, SET_MODE and versioned configuration | test_mode_single_source_through_both_paths; test_mode_command_is_versioned_and_audited |
| light_on_threshold, light_off_threshold, light_hysteresis | Ordered nominal thresholds and bounded margin; ControlModel sensor decisions | test_control.py; test_hysteresis_margin_affects_both_boundaries |
| schedule, out_of_window_state | Schedule and ControlModel; valid bounds, exclusive ends, ON/OFF out-of-window value | test_control.py; test_always_on_all_boundaries_and_no_transition |
| measurement_interval_ticks | Simulation sample/energy interval; positive integer | test_measurement.py; test_configuration.py |
| reporting_interval_ticks | LampNode measurement record cadence; positive integer | test_reporting_interval_is_configurable |
| voltage_min, voltage_max | MeasurementValidator, DiagnosticEngine, command verification supply evidence; ordered band | test_measurement.py; test_diagnostics.py |
| under_current_min, expected_current_min, over_current_max | DiagnosticEngine; ordered nonnegative current bands | test_diagnostics.py; test_current_bands_must_be_ordered |
| unexpected_current_min | DiagnosticEngine and actual-state derivation | test_diagnostics.py; test_missing_current_cannot_verify_off |
| power_max, power_consistency_tolerance | MeasurementValidator and command evidence checks | test_measurement.py; test_observation_mismatch_fails_instead_of_false_verification |
| light_level_min, light_level_max | MeasurementValidator and DiagnosticEngine sensor range | test_measurement.py; test_diagnostics.py |
| fault_confirmation_count, fault_confirmation_window_ticks | FaultEngine consecutive confirmation policy | test_fault.py; test_confirmation_requires_consecutive_matching_classification |
| comm_retry_count | Lamp Node's injectable communication health machine; GC polling has its own group-level retry count | test_comm.py; remote reconfiguration updates the node machine limit; autonomous node link-watchdog scheduling is not implemented |
| comm_timeout_ticks | Node pending remote physical-verification timeout, driven by process_incoming | test_command_timeout_and_late_response_cannot_resurrect; GC transaction deadlines use group configuration |
| ack_required | NotificationEngine; false selects NOT_REQUIRED in this model | test_not_required_when_ack_not_configured |
| ack_reminder_interval_ticks, escalation_timeout_ticks | NotificationEngine deadlines; escalation exceeds reminder | test_persistent_fault_does_not_reset_notification_deadlines |
| escalation_destination, escalation_role | NotificationPolicy, escalation audit destination/role; abstract delivery only | test_fault.py |
| notification_retry_count | NotificationEngine bounded delivery retries | test_fault.py delivery-failure/retry tests |
| restart_default_state | LampNode restart; only ON/OFF | test_control.py restart tests; pending commands fail across restart |
| automatic_deletion, minimum_retention_ticks | RecordStore retention and candidate selection; deletion still explicit/authorized | test_storage.py; test_configured_retention_is_enforced_by_node; test_remote_retention_update_changes_store_policy |
| storage_full_behaviour | Reserved open A-09; only None accepted; no selected product policy is silently ignored | test_storage_full_behaviour_defaults_to_undecided; test_storage_full_behaviour_is_a_simulation_detail_not_a_decision |
| energy_reset_role | Additional engineering-or-higher minimum for RESET_ENERGY; cannot weaken base engineering authorization | test_energy_reset_requires_authorization; remote subtype role matrix |
| max_nodes_in_group | Reserved per-lamp advisory field, not a second group capacity authority | Explicitly deferred: GroupControllerConfig.max_nodes alone governs registration; test_group_controller_supports_the_initial_group_target |

GroupControllerConfig fields: `max_nodes` is consumed by registration;
`poll_timeout_ticks` and `poll_retry_count` drive request deadlines/retries;
`storage_capacity` constructs the bounded RecordStore. Validation lives in
GroupControllerConfig.validated and RecordStore. Group tests and the
post-merge silent-node/corrupt-request tests exercise these consumers.

Remote CONFIG_READ/WRITE currently supports an explicit integer-scalar subset:
configured_mode, light_on_threshold, light_off_threshold, light_hysteresis,
measurement_interval_ticks, reporting_interval_ticks, fault_confirmation_count,
fault_confirmation_window_ticks, comm_retry_count, comm_timeout_ticks,
ack_reminder_interval_ticks, escalation_timeout_ticks, minimum_retention_ticks.
For the nullable minimum, -1 means unspecified. Unknown keys and invalid modes
are rejected; identity/address cannot be overwritten through this path. Fractional
wire scalars and mode indices are rejected, not silently truncated.
Structured schedules, arbitrary fractional thresholds and the other fields are
local construction-time configuration, **not a fully implemented remote schema**.
PR-CONFIG-001/002 are therefore marked PARTIAL rather than claiming every
configuration parameter is remotely distributable. No production schema or
site retention value is invented by this corrective pass.
