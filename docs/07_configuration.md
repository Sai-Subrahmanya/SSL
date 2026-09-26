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
| Implementation | **Not started** (Phase 12) |

---

## 13. Related documents

- [02_product_requirements.md](02_product_requirements.md)
- [03_data_model.md](03_data_model.md)
- [04_fault_management.md](04_fault_management.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
