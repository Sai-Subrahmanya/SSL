# Architecture

## 1. Overview

Smart Street Light V1 (SSL V1) is a monitoring and control system for street
lighting. It attaches to an **existing, external street-light luminaire**: the
lamp, its driver, its optics and its enclosure are not part of this product.
The system controls and supervises the lamp; it does not replace it.

The system has three software layers plus the field bus between them:

```text
        MASTER CONTROL CENTER            operator/control layer
                 |
                 |  upstream link        supervision, aggregation,
                 |                       command routing
                 |
         GROUP CONTROLLER                bus master for one group
                 |
                 |  RS-485 field bus     deterministic master/slave
                 |
    +------------+------------+
    |            |            |
 LAMP NODE 1  LAMP NODE 2  ...  LAMP NODE N      one node per lamp
    |            |            |
 external     external     external
 street-lamp  street-lamp  street-lamp
 load         load         load
```

| Layer | Element | Primary responsibility |
| --- | --- | --- |
| Control layer | Master Control Center | Operator-facing control and aggregation; no direct device logic. |
| Group layer | Group Controller | RS-485 bus master, polling, aggregation, buffering, upstream link. |
| Field layer | Lamp Node | Per-lamp control, measurement, diagnostics, fault handling, local autonomy. |
| Link layer | RS-485 bus | Deterministic wired master/slave communication. |

The initial target is approximately **16 lamp nodes per group**, and the
architecture is required to scale in nodes per group and groups per site. A
single lamp node failure must not degrade the rest of the group.

The implementation in `src/sslv1/` is a deterministic digital model of this
architecture: it models logic, state machines, data flow and communication
behaviour, and it deliberately models no hardware. See
[validation.md](validation.md) for what that does and does not establish.

## 2. Layer responsibilities

### 2.1 Lamp Node

| # | Responsibility |
| --- | --- |
| 1 | Lamp ON/OFF control according to the effective operating mode. |
| 2 | Timed switching-command handling with duplicate suppression. |
| 3 | Switching feedback: the observed state of the switching path, separate from the command. |
| 4 | Voltage, current, power, energy and light-level handling with explicit validity. |
| 5 | Sensor-health monitoring. |
| 6 | Expected-versus-actual diagnostics over combined evidence. |
| 7 | Fault detection, confirmation, latching, notification, acknowledgement, repair and verification. |
| 8 | Local event and measurement logging with timestamps. |
| 9 | Local record storage, upload queuing and retention. |
| 10 | RS-485 node stack: responding as an addressed node. |
| 11 | Local autonomy without any supervision layer. |
| 12 | Communication state tracking and recovery. |
| 13 | Configuration storage, application and reporting. |
| 14 | Controller health reporting and restart recovery. |
| 15 | Stable identity reporting. |

### 2.2 Group Controller

| # | Responsibility |
| --- | --- |
| 1 | RS-485 master: sole bus master; nodes respond only when addressed. |
| 2 | Cyclic status, measurement, fault and event polling with deadlines and retries. |
| 3 | Per-node communication and health state. |
| 4 | Aggregation of measurements, events and faults. |
| 5 | Configuration distribution to nodes. |
| 6 | Time synchronisation to nodes. |
| 7 | Authorized command forwarding to the target node. |
| 8 | Tracking of command receipt, execution and verification stages. |
| 9 | Buffering of records during upstream loss (store-and-forward). |
| 10 | Upstream link management and post-recovery re-synchronisation. |
| 11 | Failure containment: a failing node never degrades the group. |

### 2.3 Master Control Center

The Master Control Center (MCC) is the logical operator/control layer. It is a
**consumer and orchestration layer**:

* it owns the site → group → lamp registry and the identity validation that
  goes with it;
* it derives every status view from what the Group Controllers actually
  reported (registration, received records, event logs);
* it forwards operator commands through the existing authorized command path,
  preserving the originating actor;
* it exposes configuration readback only;
* it reads the existing audit trail instead of keeping one of its own.

It does **not** implement lamp control, diagnostics, the fault lifecycle, the
notification lifecycle, the command lifecycle, the communication protocol,
storage or authorization, and it keeps no second copy of any of them. It holds
no persistence: what it shows is what arrived. See section 5.

## 3. Module map

```text
src/sslv1/
|-- enums.py              controlled vocabularies (no hardware-specific values)
|-- errors.py             domain exceptions
|-- identity.py           identity hierarchy (product > site > group > lamp > MCU) and bus addressing
|-- time_model.py         logical clock, timestamps, synchronisation state
|-- authorization.py      preliminary roles and the authorization service
|-- configuration.py      lamp configuration value object, schedules, validation
|-- control.py            operating modes, override handling, mode priority, hysteresis
|-- command.py            command model, lifecycle and command service
|-- measurement.py        measurement model and validity assessment
|-- diagnostics.py        evidence-based diagnostic rules
|-- fault.py              fault model, lifecycle state machine, fault engine
|-- notification.py       notification state machine and engine
|-- event.py              event model and event log
|-- storage.py            record lifecycle, retention and the record store
|-- mcc.py                Master Control Center data/orchestration layer
|-- comm/                 RS-485 frame, payload codecs, CRC, sequence tracking,
|                         communication state machine, in-memory bus
`-- nodes/
    |-- lamp_node.py      Lamp Node model
    `-- group_controller.py  Group Controller model
```

## 4. Single source of truth

Each concern has exactly one implementation. This is a design rule, not an
accident of the code layout:

| Concern | Owner | Where |
| --- | --- | --- |
| Lamp control, diagnostics, fault and notification lifecycle | Lamp Node | `nodes/lamp_node.py`, `fault.py`, `notification.py`, `diagnostics.py` |
| Authorization | one service used by every path that mutates state | `authorization.py` |
| Command lifecycle | one implementation, used by node, controller and MCC paths | `command.py` |
| Record storage and retention | one store per node and per controller; the MCC has none | `storage.py` |
| Time | one logical clock per device | `time_model.py` |
| Communication state | one state machine used by both node layers | `comm/state_machine.py` |
| Configuration semantics | one model consulted by control, diagnostics, faults, measurement and notification | `configuration.py` |
| Aggregation and status views | MCC derived views over what the controllers reported | `mcc.py` |
| Event/audit trail | node and controller event logs; the MCC reads them | `event.py` |

The Group Controller forwards, correlates and buffers; it implements no fault,
diagnostic or control logic. The MCC decides nothing that is already decided
lower down. When a value has never been reported, it is reported as unknown —
never invented as zero or as a default.

## 5. Master Control Center derived views

Every MCC status is a **derived read model**, computed from what the Group
Controller reported. Nothing is stored twice.

| View field | Values | Meaning |
| --- | --- | --- |
| `availability` | `HEALTHY`, `DEGRADED`, `RECOVERING`, `UNAVAILABLE`, `UNKNOWN` | Whether the lamp can be supervised now. Link health decides first: upstream loss or `COMM_FAULT` → `UNAVAILABLE`, `RETRY` or `DEGRADED` → `DEGRADED`, `RECOVERY` → `RECOVERING`. Data currency decides next: stale data, or no data at all, → `UNKNOWN` (a stale value is never presented as current, even if it mentioned a fault). An active fault on a current link → `DEGRADED`; otherwise `HEALTHY`. |
| `freshness` | `FRESH`, `STALE`, `UNKNOWN` | Whether the reported value is still current relative to the configured status age limit. A stale value is still displayed, never as current. |
| group / site `health` | `HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `UNKNOWN` | Aggregate of the lamp views. No lamps registered or every lamp never reported → `UNKNOWN`; the group's upstream link unavailable, or every lamp unreachable → `UNAVAILABLE`; every lamp healthy and no active fault → `HEALTHY`; otherwise `DEGRADED` (an individual failure is listed, not hidden). |

`UNKNOWN` and `UNAVAILABLE` are deliberately distinct: "no current view has ever
been received" is not the same claim as "the lamp is unreachable".

### 5.1 Upstream record intake

The MCC accepts an uploaded record only when it is valid, attributable to that
group's controller, and consistent with the scope the record itself declares
(site, group and lamp must match the delivering controller). A record that was
already received is answered as received — the far end has it — but counted as
a duplicate and stored once. A record that cannot be attributed is refused and
stays pending at the sender, so a mis-delivered record can never be filed under
the wrong site, group or lamp.

Received records are kept in arrival order, unchanged. Record identity is
(site, group, record type, sequence number).

## 6. Data model

### 6.1 Identity

```text
Product ID -> Site ID -> Group ID -> Lamp ID -> MCU Unique ID
```

Identity is deterministic and persistent: the same physical node reports the
same identity across restarts. The RS-485 bus address is a separate,
group-scoped value and is not a substitute for the lamp identity; duplicate bus
addresses and duplicate lamp identities are detected and rejected.

### 6.2 Measurement

| Field | Description |
| --- | --- |
| `timestamp` | Record time with a time-validity indication. |
| `site_id`, `group_id`, `lamp_id` | Owning scope. |
| `effective_mode` | Mode in force when the snapshot was taken, including any active override. |
| `commanded_state` | State commanded by the system. |
| `switching_feedback` | Observed state of the switching path (physical realisation is a hardware decision). |
| `actual_state` | Observed state derived from evidence. |
| `voltage`, `current`, `power`, `energy`, `light_level` | Engineering monitoring values, each nullable. |
| `sensor_status` | `VALID`, `DEGRADED`, `INVALID`. |
| `communication_status` | `COMM_HEALTHY`, `RETRY`, `DEGRADED`, `COMM_FAULT`, `RECOVERY`. |
| `controller_status` | `NORMAL`, `DEGRADED`, `FAULT`, `RESTARTED`. |
| `sequence_number` | Monotonic measurement ordering. |

These are engineering monitoring values, never billing-grade metering. Every
measurement carries its validity; a number is never silently treated as
trustworthy.

### 6.3 Fault

| Field | Description |
| --- | --- |
| `fault_id` | Stable fault identity, unique within its node. |
| site/group/lamp | Owning scope. |
| `created_ticks`, `first_observation_ticks`, `last_observation_ticks`, `confirmed_ticks`, `acknowledged_ticks`, `closed_ticks` | Timestamps of the lifecycle steps that have happened. |
| `fault_type` | Fault category (controlled vocabulary). |
| `severity` | Severity classification. |
| `state` | Lifecycle state. |
| `confirmation_count`, `confirmation_reason` | How many observations supported the fault, and why. |
| `evidence`, `latest_evidence`, `verification_evidence` | Evidence that created the fault, the most recent observation, and the evidence kept for verification. |
| `notification_state`, `notification_reason` | Notification/escalation progress, independent of the lifecycle. |
| `repair_status`, `verification_status` | Repair and verification progress. |
| `related_event_ids` | Events associated with the fault. |
| `actor`, `closed_actor` | Who last acted on the fault, and who closed it. |
| `diagnostic_classification` | Evidence-based interpretation, not a confirmed root cause. |
| `previous_fault_id` | Link to the previous fault when a cleared condition recurs. |

Fault categories: `LAMP_LOAD`, `UNDER_CURRENT`, `OVER_CURRENT`,
`SUPPLY_VOLTAGE`, `LIGHT_SENSOR`, `COMMUNICATION`, `CONTROLLER`,
`ENVIRONMENTAL`, `TAMPER`, `UNKNOWN`, `INSPECTION_REQUIRED`.

Lifecycle states: `NORMAL`, `SUSPECTED`, `CONFIRMED`, `ACKNOWLEDGED`,
`UNDER_REPAIR`, `VERIFYING`, `CLOSED`. Notification states: `NOT_REQUIRED`,
`PENDING`, `SENT`, `ACK_PENDING`, `REMINDER_DUE`, `ESCALATED`,
`DELIVERY_FAILED`. Notification progress is tracked separately, so a fault can
stay `CONFIRMED` while its notification state advances.

### 6.4 Event

Events carry identity, scope, timestamp with validity, event type, originating
subsystem, severity, reason, optional related fault, actor and event data.
They are the audit substrate: append-only, never mutated or deleted by the
domain layer, stored locally and forwarded upstream after recovery. Event types
cover control, command, measurement, fault, communication, storage, time and
system occurrences.

### 6.5 Command

| Field | Description |
| --- | --- |
| `command_id` | Stable identity, used for duplicate suppression. |
| `command_type` | `SET_MODE`, `FORCE_ON`, `FORCE_OFF`, `RETURN_TO_AUTO`, `READ_CONFIG`, `WRITE_CONFIG`, `TIME_SYNC`, `IDENTIFY`, `ACKNOWLEDGE_FAULT`, `START_REPAIR`, `VERIFY_REPAIR`, `CLOSE_FAULT`, `HEARTBEAT`. |
| `subtype` | Control subtypes carried inside `CONTROL_COMMAND`: `LAMP_ON`, `LAMP_OFF`, `RESET_ENERGY`, `SET_MODE`, `RETURN_TO_AUTO`. |
| `target`, `actor`, `parameters`, `priority` | Scope, originator, parameters and priority. |
| `created_ticks` | When the command was created. |
| `authorization_status` | `AUTHORIZED`, `UNAUTHORIZED`, `UNKNOWN`. |

Its mutable lifecycle record adds the stage timestamps
(`received_ticks`, `transmitted_ticks`, `executed_ticks`, `acknowledged_ticks`,
`verified_ticks`), the current `state`, `result`, `evidence` and
`verification_reason`.

Lifecycle: `CREATED → RECEIVED → EXECUTED → ACKNOWLEDGED →
ACTUAL_STATE_VERIFIED`, with `REJECTED` and `FAILED` as terminal outcomes.
Each stage is independently observable: receipt at the controller is not
execution, execution acknowledgement is not verified actual state.

### 6.6 Record envelope and lifecycle

Every stored record carries a sequence number, timestamp with validity, record
type, payload, CRC and commit marker. A record is valid only when its commit
marker indicates completion.

```text
CREATED -> STORED -> PENDING_UPLOAD -> UPLOADED -> CONFIRMED -> RETAINED
```

`CONFIRMED` means the record may leave the pending upload queue. The retained
historical record is not deleted; upload confirmation and retention are
different operations. Deletion is explicit, authorized and audited, and
automatic deletion is disabled by default. `CORRUPT` and `DELETED` are
terminal states for a record that failed its integrity check or was explicitly
deleted.

## 7. Communication

### 7.1 Field bus

| Property | Value |
| --- | --- |
| Physical layer | RS-485 (modelled logically; no electrical behaviour is claimed) |
| Topology | Linear multi-drop bus |
| Master | Group Controller (sole master) |
| Nodes | Lamp Nodes, individually addressed; they transmit only when addressed |
| Nodes per group | Approximately 16 initial target, must scale |
| Bus address range | 1–247 for nodes, plus master (0) and broadcast (255) |

The physical layer parameters — baud rate, UART framing, transceiver,
termination, biasing, cable and protection — are hardware-design inputs and are
listed in [hardware_reference.md](hardware_reference.md).

### 7.2 Frame

```text
+--------+------------------+----------------+---------------------+
| SOF    | Protocol Version | Source Address | Destination Address |
+--------+------------------+----------------+---------------------+
| Message Type | Payload Length | Payload | Sequence Number | CRC |
+------------------------------------------------------------------+
```

Frames are big-endian, the start-of-frame delimiter is `0xA5`, and payloads
are limited to 65535 bytes. Integrity is CRC-16/XMODEM over every preceding
byte. The decoder rejects a bad start-of-frame, a truncated frame, a length
mismatch, an unknown message type, an oversized payload, a wrong protocol
version and trailing bytes; the protocol version implemented here is 2.

Protocol version 2, implemented by this model, adds actor assertions, response
correlation, configuration readback and observation metadata to the message
set. It is not wire-compatible with the earlier prototype version 1.

### 7.3 Message types

`STATUS_REQUEST`, `STATUS_RESPONSE`, `MEASUREMENT_REQUEST`,
`MEASUREMENT_RESPONSE`, `CONTROL_COMMAND`, `CONTROL_ACK`, `FAULT_REPORT`,
`EVENT_REPORT`, `CONFIG_READ`, `CONFIG_WRITE`, `CONFIG_ACK`, `TIME_SYNC`,
`TIME_ACK`, `IDENTIFY`, `IDENTIFY_ACK`, `HEARTBEAT`, `HEARTBEAT_ACK`.

Payloads are compact big-endian binary with explicit lengths. A request whose
body is empty is transmitted with a zero-length payload; the decoder accepts
both that form and the canonical empty length envelope for such a message type,
and rejects an empty payload for any type that carries a body. Privileged
message types require an actor assertion, which is validated before the payload
is accepted; a malformed actor is a protocol error.

### 7.4 Ordering, duplicates and staleness

* A `SequenceTracker` provides bounded modular sequence comparison shared by
  both bus receivers.
* A frame whose sequence number has already been seen is detected as a
  duplicate and reported, not re-executed; this is what prevents a retried
  command from toggling a lamp twice.
* A frame outside the accepted sequence window is rejected as stale rather than
  applied out of order.
* A frame addressed to a different node is not acted on.

### 7.5 Polling and command flow

```text
OPERATOR -> MCC -> GROUP CONTROLLER -> RS-485 CONTROL_COMMAND -> LAMP NODE
                 <- RS-485 CONTROL_ACK <- exec/ack
                 <- measurement evidence <- ACTUAL_STATE_VERIFIED at the node
```

Polling is cyclic and request-driven: status, measurement, fault and event
rounds, driven by the Group Controller. Every request has a deadline and a
retry count from configuration; a missing response after the retries moves the
link into the next communication state.

### 7.6 Communication state machine

```text
COMM_HEALTHY -> RETRY -> DEGRADED -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY
```

| From | To | Condition |
| --- | --- | --- |
| `COMM_HEALTHY` | `RETRY` | A polled exchange failed. |
| `RETRY` | `COMM_HEALTHY` | The retry succeeded. |
| `RETRY` | `DEGRADED` | Retries exhausted for this exchange. |
| `DEGRADED` | `COMM_HEALTHY` | Communication recovered before the fault threshold. |
| `DEGRADED` | `COMM_FAULT` | Repeated failure crosses the fault threshold. |
| `COMM_FAULT` | `RECOVERY` | The link answers again. |
| `RECOVERY` | `COMM_HEALTHY` | Re-synchronisation completed. |
| `RECOVERY` | `COMM_FAULT` | The link failed again during recovery. |

Link health changes emit `COMM_STATE_CHANGED`, `COMM_FAULT_DETECTED` and
`COMM_RECOVERED` events. Automatic conversion of link health into a managed
per-lamp fault record is not implemented; the link state is reported and
audited in its own right.

### 7.7 Local operation during communication loss

Communication loss never stops local lighting operation. A node that is not
being polled keeps controlling its lamp, keeps sampling, keeps logging locally
and keeps evaluating faults; only reporting is deferred.

### 7.8 Time distribution

The Group Controller distributes time to its nodes with `TIME_SYNC` /
`TIME_ACK`. A node that has never been synchronised keeps local time and marks
its records as time-uncertain; it never claims to be synchronised. Record
ordering relies on sequence numbers when time is uncertain, and later
synchronisation does not rewrite the validity of already-stored records.

## 8. Storage and logging

### 8.1 Record classes

| Class | Content |
| --- | --- |
| Measurement record | Per-lamp measurement snapshot. |
| Event record | Discrete occurrence with actor and reason. |
| Fault record | Fault lifecycle state and evidence. |
| Buffered record | Any record awaiting upload confirmation. |

### 8.2 Write, commit and corruption

```text
1. append record body
2. compute a CRC-32 over the sequence number, timestamp with its validity,
   record type, device identifier and payload
3. write commit marker
4. record becomes visible and uploadable
```

A record interrupted before its commit marker is incomplete and is discarded on
recovery; corrupt records are detected, reported, excluded from upload and
never silently deleted. Sequence gaps are visible rather than hidden.

### 8.3 Retention

Automatic deletion is disabled by default. A configurable retention policy can
select deletion candidates, but deletion always requires an authorized actor,
is refused for pending or too-young records, and is recorded as an audit event.
A deletion leaves a logical tombstone; it is not secure erasure. Capacity
exhaustion raises an explicit condition rather than overwriting evidence.

### 8.4 Store-and-forward

```text
STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM
```

Records produced while the upstream link is unavailable are buffered locally.
After recovery the Group Controller re-synchronises, uploads the backlog and
keeps every record pending until the far end confirms it. The sequence is
implemented as one deterministic step,
`GroupController.resynchronize_upstream()`, driven by
`MasterControlCenter.recover_upstream()`. The automatic *trigger* for that step
is caller-driven: the model has no background scheduler, so recovery is
detected by the caller before the step runs.

## 9. Configuration

### 9.1 Lamp configuration

| Group | Parameters |
| --- | --- |
| Identity | lamp, site, group, product and bus address. |
| Lighting control | configured mode, ON/OFF light thresholds, hysteresis, schedule, out-of-window state. |
| Measurement and reporting | measurement interval, reporting interval. |
| Measurement validity bands | voltage band, under-current, expected-current, over-current, unexpected-current, power maximum, power consistency tolerance, light-level range. |
| Fault handling | confirmation count, confirmation window. |
| Communication | retry count, timeout. |
| Notification | acknowledgement required, reminder interval, escalation timeout, destination and role, notification retry count. |
| System | restart default state, retention policy, minimum retention, storage-full behaviour, energy-reset role, maximum nodes in group. |

All operational values are configuration and validation rules; no operational
threshold is hardcoded in the logic. Defaults in the model are simulation
defaults, not product-frozen values.

### 9.2 Group controller configuration

`max_nodes` (registration limit), `poll_timeout_ticks`, `poll_retry_count` and
`storage_capacity` (bounded buffer). Validation lives on the configuration
object.

### 9.3 Change workflow

```text
1. operator issues a configuration change
2. authorization is checked
3. the configuration is validated
4. the change is distributed to the node (CONFIG_WRITE)
5. the node applies it atomically
6. the node acknowledges (CONFIG_ACK)
7. the change is recorded as an auditable event
8. the new configuration version is reported and can be read back
```

A rejected configuration leaves the previous valid configuration in effect and
is reported with a reason. Accepted is not the same as applied: application is
verified by readback of the applied values and version.

### 9.4 Remote configuration subset

Remote `CONFIG_READ` / `CONFIG_WRITE` supports an explicit integer-scalar
subset: configured mode, light thresholds, hysteresis, measurement and
reporting intervals, fault confirmation count and window, communication retry
count and timeout, reminder and escalation intervals and the minimum retention
value. Identity and address cannot be overwritten through this path; unknown
keys, invalid modes, fractional and non-finite values are rejected rather than
truncated. Structured schedules and the remaining fields are local
construction-time configuration, not a complete remote schema.

## 10. Related documents

* [system_behaviour.md](system_behaviour.md) — control, diagnostics, faults, commands, time, offline behaviour.
* [requirements.md](requirements.md) — the requirement set and its implementation status.
* [design_decisions.md](design_decisions.md) — the decisions behind this architecture.
* [validation.md](validation.md) — test evidence, limitations and the digital/physical boundary.
* [hardware_reference.md](hardware_reference.md) — hardware candidates and the open hardware inputs.
