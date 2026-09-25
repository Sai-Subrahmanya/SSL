# 03 - Data Model

## 1. Document purpose

This document defines the **future data model** for Smart Street Light V1.

It is a design artefact derived from the requirements in
[02_product_requirements.md](02_product_requirements.md). It defines the
*information* the system must carry; it does not define serialization,
field widths, or storage layout (those belong to Phase 8 design).

Field types below are **indicative**. They describe the information content,
not a concrete implementation type.

---

## 2. Model overview

```text
                        +-------------+
                        |   SITE      |
                        +------+------+
                               | 1..N
                        +------v------+
                        |   GROUP     |
                        +------+------+
                               | 1..N
                        +------v------+
                        |    LAMP     |
                        +------+------+
                               | 1
                        +------v------+
                        | LAMP NODE   |
                        +------+------+
                               |
        +----------+-----------+-----------+-----------+
        |          |           |           |           |
   MEASUREMENT   EVENT       FAULT      COMMAND   CONFIGURATION
```

| Entity | Cardinality | Notes |
| --- | --- | --- |
| Site | 1 per physical site | Aggregation root for the Master Control Center. |
| Group | 1..N per site | Served by one Group Controller. |
| Lamp | 1..N per group | Initial target approximately 16. |
| Lamp Node | 1 per lamp | The controller bound to that lamp. |

---

## 3. Identity model

```text
Product ID -> Site ID -> Group ID -> Lamp ID -> MCU Unique ID
```

| Field | Scope | Notes |
| --- | --- | --- |
| `product_id` | Product-wide | Identifies the product/engineering baseline. |
| `site_id` | Site | Identifies the installation site. |
| `group_id` | Group | Identifies the group within the site. |
| `lamp_id` | Lamp | Identifies the lamp within the group. |
| `mcu_unique_id` | Physical device | Silicon-level unique identifier of the node MCU. |

Identity must be deterministic and persistent
(`PR-IDENTITY-001`, `PR-IDENTITY-002`). The bus address is a separate,
group-scoped value and is not a substitute for `lamp_id`
(`PR-IDENTITY-003`).

---

## 4. Measurement

### 4.1 Field list

| Field | Indicative type | Description |
| --- | --- | --- |
| `timestamp` | datetime | Record time, with time-validity indication. |
| `site_id` | identifier | Owning site. |
| `group_id` | identifier | Owning group. |
| `lamp_id` | identifier | Owning lamp. |
| `operating_mode` | enum | Current operating mode (see 4.2). |
| `commanded_state` | enum | State commanded by the system. |
| `relay_feedback` | enum | Reported state of the switching element. |
| `actual_state` | enum | Observed state derived from evidence. |
| `voltage` | quantity | Measured supply voltage. |
| `current` | quantity | Measured load current. |
| `power` | quantity | Derived power. |
| `energy` | quantity | Accumulated energy. |
| `light_level` | quantity | Measured light level. |
| `sensor_status` | enum | Validity of the sensor inputs. |
| `communication_status` | enum | Communication state of the node. |
| `controller_status` | enum | Health state of the node controller. |

### 4.2 Value domains

`operating_mode`:

`AUTO_SENSOR`, `AUTO_SCHEDULE_SENSOR`, `FIXED_SCHEDULE`, `FORCE_ON`,
`FORCE_OFF`, `RETURN_TO_AUTO`.

`commanded_state`, `relay_feedback`, `actual_state`:

`ON`, `OFF`, `UNKNOWN`.

`sensor_status`:

`VALID`, `DEGRADED`, `INVALID`.

`communication_status`:

`COMM_HEALTHY`, `RETRY`, `DEGRADED`, `COMM_FAULT`, `RECOVERY`.

`controller_status`:

`NORMAL`, `DEGRADED`, `FAULT`, `RESTARTED`.

### 4.3 Notes

- These are **engineering monitoring values**, not billing-grade metering
  (`PR-MEASURE-005`).
- Every measurement carries sensor validity (`PR-MEASURE-004`).
- Sampling and reporting intervals are independently configurable
  (`PR-MEASURE-002`).

---

## 5. Fault

### 5.1 Field list

| Field | Indicative type | Description |
| --- | --- | --- |
| `fault_id` | identifier | Stable fault identity. |
| `site_id` | identifier | Owning site. |
| `group_id` | identifier | Owning group. |
| `lamp_id` | identifier | Owning lamp. |
| `created_timestamp` | datetime | When the fault record was created. |
| `confirmed_timestamp` | datetime | When confirmation criteria were met. |
| `closed_timestamp` | datetime | When the fault was closed. |
| `fault_type` | enum | Fault category (see 5.2). |
| `severity` | enum | Severity classification. |
| `state` | enum | Lifecycle state (see 5.3). |
| `evidence` | collection | Measurement/diagnostic evidence supporting the fault. |
| `confirmation_count` | integer | Number of confirming observations so far. |
| `notification_status` | enum | Notification progress. |
| `ack_status` | enum | Acknowledgement progress. |
| `repair_status` | enum | Repair progress. |
| `verification_status` | enum | Verification progress. |
| `related_event_ids` | collection | Events associated with the fault. |

### 5.2 Fault type domain

`LAMP_LOAD`, `UNDER_CURRENT`, `OVER_CURRENT`, `SUPPLY_VOLTAGE`,
`LIGHT_SENSOR`, `COMMUNICATION`, `CONTROLLER`, `ENVIRONMENTAL`, `TAMPER`,
`UNKNOWN`, `INSPECTION_REQUIRED`.

### 5.3 Fault state domain

`NORMAL`, `SUSPECTED`, `CONFIRMED`, `NOTIFIED`, `ACKNOWLEDGED`,
`UNDER_REPAIR`, `VERIFYING`, `CLOSED`.

### 5.4 Sub-status domains

| Field | Values |
| --- | --- |
| `notification_status` | `NOT_NOTIFIED`, `NOTIFIED`, `REMINDED`, `ESCALATED` |
| `ack_status` | `NOT_ACKNOWLEDGED`, `ACKNOWLEDGED`, `ACK_EXPIRED` |
| `repair_status` | `NOT_STARTED`, `IN_PROGRESS`, `REPAIRED`, `NOT_REPAIRED` |
| `verification_status` | `NOT_VERIFIED`, `VERIFYING`, `VERIFIED`, `VERIFICATION_FAILED` |

### 5.5 Notes

- `evidence` retains the measurement snapshot that supported the fault, so
  that verification can compare against the original condition
  (`PR-FAULT-011`).
- `confirmation_count` supports the configurable confirmation policy
  (`PR-FAULT-005`).

---

## 6. Event

### 6.1 Field list

| Field | Indicative type | Description |
| --- | --- | --- |
| `event_id` | identifier | Stable event identity. |
| `timestamp` | datetime | Event time, with time-validity indication. |
| `device_id` | identifier | Reporting device (lamp node or group controller). |
| `site_id` | identifier | Owning site. |
| `group_id` | identifier | Owning group. |
| `lamp_id` | identifier | Owning lamp (nullable for group-level events). |
| `event_type` | enum | Event classification. |
| `source` | enum | Originating subsystem. |
| `severity` | enum | Event severity. |
| `reason` | text | Human-readable reason code/text. |
| `related_fault_id` | identifier | Associated fault, if any. |
| `actor` | identifier | Who or what caused the event (operator, system, scheduler). |
| `event_data` | structure | Event-specific payload. |

### 6.2 Event type domain (indicative, extensible)

| Group | Event types |
| --- | --- |
| Control | `MODE_CHANGED`, `COMMAND_RECEIVED`, `COMMAND_EXECUTED`, `COMMAND_REJECTED`, `COMMAND_VERIFIED`, `OVERRIDE_SET`, `OVERRIDE_CLEARED` |
| Measurement | `MEASUREMENT_OUT_OF_RANGE`, `SENSOR_INVALID`, `SENSOR_RECOVERED` |
| Fault | `FAULT_SUSPECTED`, `FAULT_CONFIRMED`, `FAULT_NOTIFIED`, `FAULT_ACKNOWLEDGED`, `FAULT_ESCALATED`, `FAULT_REPAIR_STARTED`, `FAULT_VERIFICATION_FAILED`, `FAULT_CLOSED` |
| Communication | `COMM_STATE_CHANGED`, `COMM_FAULT_DETECTED`, `COMM_RECOVERED`, `FRAME_REJECTED`, `DUPLICATE_DETECTED` |
| Storage | `RECORD_STORED`, `RECORD_UPLOADED`, `RECORD_CORRUPT`, `STORAGE_FULL` |
| Time | `TIME_SYNCHRONIZED`, `TIME_UNCERTAIN`, `TIME_LOST` |
| System | `NODE_STARTED`, `WATCHDOG_RESET`, `CONFIG_CHANGED`, `CONFIG_REJECTED`, `IDENTITY_CONFLICT`, `TAMPER_INDICATION` |

### 6.3 Notes

- Events are the audit substrate (`PR-SECURITY-003`).
- Events are stored locally and forwarded after recovery
  (`PR-STORAGE-001`, `PR-OFFLINE-004`).

---

## 7. Command

### 7.1 Field list

| Field | Indicative type | Description |
| --- | --- | --- |
| `command_id` | identifier | Stable command identity (used for duplicate detection). |
| `timestamp` | datetime | Command issue time. |
| `sender` | identifier | Command originator. |
| `target` | identifier | Target device (site/group/lamp scope). |
| `command_type` | enum | Command classification. |
| `parameters` | structure | Command-specific parameters. |
| `priority` | enum | Command priority class. |
| `authentication_status` | enum | Authentication result. |
| `received_status` | enum | Receipt state. |
| `execution_status` | enum | Execution state. |
| `verification_status` | enum | Actual-state verification state. |

### 7.2 Command lifecycle domains

```text
COMMAND_SENT -> RECEIVED -> EXECUTED -> ACKNOWLEDGED -> ACTUAL_STATE_VERIFIED
```

| Field | Values |
| --- | --- |
| `authentication_status` | `AUTHENTICATED`, `REJECTED`, `UNKNOWN` |
| `received_status` | `NOT_RECEIVED`, `RECEIVED`, `DUPLICATE` |
| `execution_status` | `NOT_EXECUTED`, `EXECUTED`, `FAILED`, `REJECTED` |
| `verification_status` | `NOT_VERIFIED`, `VERIFIED`, `VERIFICATION_FAILED` |

### 7.3 Command type domain (indicative)

`SET_MODE`, `FORCE_ON`, `FORCE_OFF`, `RETURN_TO_AUTO`, `READ_CONFIG`,
`WRITE_CONFIG`, `TIME_SYNC`, `IDENTIFY`, `RESET_ENERGY`, `ACKNOWLEDGE_FAULT`,
`START_REPAIR`, `VERIFY_REPAIR`, `CLOSE_FAULT`, `HEARTBEAT`.

### 7.4 Notes

- A command is **not** successful merely because it was received
  (`PR-CONTROL-002`).
- Duplicate `command_id` values are reported, not re-executed
  (`PR-CONTROL-003`).

---

## 8. Configuration record

| Field | Indicative type | Description |
| --- | --- | --- |
| `config_version` | identifier | Version of the configuration set. |
| `site_id`, `group_id`, `lamp_id` | identifier | Configuration scope. |
| `operating_mode` | enum | Configured mode. |
| `light_on_threshold` | quantity | ON threshold for sensor control. |
| `light_off_threshold` | quantity | OFF threshold for sensor control. |
| `hysteresis` | quantity | Hysteresis applied to thresholds. |
| `schedule` | structure | Configured time windows / fixed schedule. |
| `measurement_interval` | duration | Sampling interval. |
| `reporting_interval` | duration | Reporting interval. |
| `fault_confirmation_count` | integer | Observations required to confirm. |
| `fault_confirmation_window` | duration | Window for confirmation. |
| `comm_retry_count` | integer | Retry attempts. |
| `comm_timeout` | duration | Response timeout. |
| `ack_reminder_interval` | duration | Acknowledgement reminder interval. |
| `escalation_timeout` | duration | Escalation timeout. |
| `escalation_destination` | identifier | Escalation target. |
| `device_identity` | structure | Identity fields. |
| `last_modified_timestamp` | datetime | Last change time. |
| `last_modified_actor` | identifier | Last change actor. |

Configuration changes are auditable (`PR-CONFIG-004`) and validated
(`PR-CONFIG-003`).

---

## 9. Stored record envelope

Every persisted record is wrapped in an envelope carrying integrity and
ordering information:

| Field | Description |
| --- | --- |
| `sequence_number` | Monotonic record sequence. |
| `timestamp` | Record time with validity indication. |
| `record_type` | Measurement / event / fault / buffered upload. |
| `payload` | The record body. |
| `crc` | Integrity check over the record. |
| `commit_marker` | Indicates the record is complete and valid. |

See [06_storage_and_logging.md](06_storage_and_logging.md).

---

## 10. Relationships

| Relationship | Cardinality | Notes |
| --- | --- | --- |
| Site - Group | 1 : N | |
| Group - Lamp | 1 : N | Initial target ~16 per group. |
| Lamp - Measurement | 1 : N | Append-only over time. |
| Lamp - Event | 1 : N | Append-only over time. |
| Lamp - Fault | 1 : N | A lamp may have sequential and concurrent faults. |
| Fault - Event | 1 : N | Via `related_event_ids` / `related_fault_id`. |
| Command - Event | 1 : N | Command progress is recorded as events. |
| Group - Buffered record | 1 : N | Store-and-forward buffer. |

---

## 11. Design status

| Item | Status |
| --- | --- |
| Field lists | Defined (information level) |
| Value domains | Defined |
| Serialization / wire format | **Not defined** - Phase 9 |
| Physical storage layout | **Not defined** - Phase 8 |
| Master Control Center persistence | **Not defined** - Phase 15 |

---

## 12. Related documents

- [01_system_architecture.md](01_system_architecture.md)
- [02_product_requirements.md](02_product_requirements.md)
- [04_fault_management.md](04_fault_management.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [07_configuration.md](07_configuration.md)
