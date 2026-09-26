# 05 - Communication Architecture

## 1. Document purpose

This document defines the preliminary **communication architecture** for
Smart Street Light V1: the RS-485 field bus, framing, message types,
polling and command flow, the communication state machine, and
communication failure and recovery behaviour.

It is derived from `PR-COMM-*`, `PR-OFFLINE-*` and `PR-TIME-*` in
[02_product_requirements.md](02_product_requirements.md).

The protocol has a **deterministic digital implementation** in
[`src/sslv1/comm/`](../src/sslv1/comm/), exercised by
[`tests/test_comm.py`](../tests/test_comm.py). That implementation models the
frame, the codecs, integrity, ordering, duplicate detection and the
communication state machine in software. It deliberately models **no UART, no
transceiver, no timing and no electrical behaviour**: those belong to a later
hardware abstraction layer and are not validated here.

---

## 2. Architecture

```text
                MASTER CONTROL CENTER
                         |
                         |  upstream link
                         |
                  GROUP CONTROLLER   <-- RS-485 MASTER
                         |
                         |
        +----------------+----------------+
        |                |                |
     NODE 1           NODE 2   ...     NODE N
   (addressed)       (addressed)       (addressed)
```

| Property | Preliminary value |
| --- | --- |
| Physical layer | RS-485 |
| Topology | Linear multi-drop bus |
| Master | Group Controller (sole master) |
| Nodes | Lamp Nodes, individually addressed |
| Nodes per group | Approximately 16 (initial target) |
| Termination | End-of-bus termination concept |
| Baud rate candidates | 9.6 kbps or 19.2 kbps |

Lamp nodes transmit only in response to a request addressed to them
(`PR-COMM-001`).

---

## 3. Bus parameters

| Parameter | Status | Notes |
| --- | --- | --- |
| Baud rate | **Candidate** | 9.6 kbps or 19.2 kbps. Low baud rate favours noise immunity on long runs. |
| Data bits / parity / stop bits | **Not decided** | To be fixed in Phase 9. |
| Node addressing | Unique per group | `PR-IDENTITY-003` |
| Termination | End-of-bus termination concept | Physical detail deferred to hardware phase. |
| Maximum node count | Approximately 16 initial target; must scale | `PR-SCALABILITY-001` |

Baud rate and electrical details are **engineering candidates**, not
decisions. See [11_assumptions.md](11_assumptions.md) and
[12_engineering_decisions.md](12_engineering_decisions.md).

---

## 4. Frame format

```text
+--------+------------------+-----------------+---------------------+
| SOF    | Protocol Version | Source Address  | Destination Address |
+--------+------------------+-----------------+---------------------+
| Message Type | Payload Length | Payload | Sequence Number | CRC |
+-------------------------------------------------------------------+
```

| Field | Purpose |
| --- | --- |
| `SOF` | Start-of-frame delimiter. |
| `Protocol Version` | Enables version mismatch detection. |
| `Source Address` | Originator of the frame. |
| `Destination Address` | Intended recipient (node address, broadcast, or master). |
| `Message Type` | One of the message types in section 5. |
| `Payload Length` | Length of the payload field. |
| `Payload` | Message-specific data. |
| `Sequence Number` | Ordering and duplicate detection. |
| `CRC` | Integrity check over the frame. |

The digital prototype fixes the following concrete encodings for the frame
fields (see [`src/sslv1/comm/frame.py`](../src/sslv1/comm/frame.py)):

| Field | Encoding in the digital prototype |
| --- | --- |
| `SOF` | single byte `0xA5` |
| `Protocol Version` | single byte, current value `0x02` |
| `Source Address` | single byte, `0x01`..`0xF7` for nodes, `0x00` for the master |
| `Destination Address` | single byte, `0xFF` is broadcast |
| `Message Type` | single byte, the ordinal position of the type in section 5 |
| `Payload Length` | 2 bytes, big-endian |
| `Payload` | message-specific encoding (see below) |
| `Sequence Number` | 2 bytes, big-endian |
| `CRC` | 2 bytes, big-endian, CRC-16/XMODEM over every preceding byte |

The minimum frame size is 11 bytes. These encodings are a **digital
prototype convention**, not a physical-layer decision: byte order, CRC
polynomial and address range can be changed in software without affecting the
architecture, and nothing here validates electrical behaviour.

Frames failing the CRC check are discarded, counted and reported, never
acted upon (`PR-COMM-006`).

---

## 5. Message types

| Message type | Direction | Purpose |
| --- | --- | --- |
| `STATUS_REQUEST` | Master -> Node | Request node status. |
| `STATUS_RESPONSE` | Node -> Master | Node status report. |
| `MEASUREMENT_REQUEST` | Master -> Node | Request measurement data. |
| `MEASUREMENT_RESPONSE` | Node -> Master | Measurement report. |
| `CONTROL_COMMAND` | Master -> Node | Control command to a node. |
| `CONTROL_ACK` | Node -> Master | Acknowledgement of a control command. |
| `FAULT_REPORT` | Node -> Master | Fault report from a node. |
| `EVENT_REPORT` | Node -> Master | Event report from a node. |
| `CONFIG_READ` | Master -> Node | Request configuration. |
| `CONFIG_WRITE` | Master -> Node | Push configuration. |
| `CONFIG_ACK` | Node -> Master | Configuration acknowledgement. |
| `TIME_SYNC` | Master -> Node | Time distribution. |
| `TIME_ACK` | Node -> Master | Time acknowledgement. |
| `IDENTIFY` | Master -> Node | Identity query. |
| `IDENTIFY_ACK` | Node -> Master | Identity response. |
| `HEARTBEAT` | Master -> Node | Liveness request. |
| `HEARTBEAT_ACK` | Node -> Master | Liveness response. |

Command actions such as resetting accumulated energy are carried as
**subtypes inside `CONTROL_COMMAND`** (for example `RESET_ENERGY`) and do not
introduce new message types. See
[03_data_model.md](03_data_model.md#7-command).

### 5.1 Payload encodings in the digital prototype

Each message type has a fixed binary payload encoding in
[`src/sslv1/comm/protocol.py`](../src/sslv1/comm/protocol.py). Enum-valued
fields are transmitted as their ordinal position in the corresponding enum, so
the wire code convention is consistent with the message type code above. The
notable payloads are:

| Message type | Payload contents |
| --- | --- |
| `MEASUREMENT_RESPONSE` | timestamp (8 bytes), voltage in mV, current in mA, power in mW (4 bytes each), energy in mWh and light level (8 bytes each, big-endian), then one byte each for effective mode, commanded state, switching feedback, actual state, sensor status, communication status and controller status |
| `CONTROL_COMMAND` | subtype (1 byte), target state (1 byte), parameter (4 bytes), length-prefixed command id |
| `CONTROL_ACK` | execution status (1 byte), actual state (1 byte), length-prefixed command id |
| `FAULT_REPORT` | fault id, fault type, diagnostic classification, fault state, notification state, severity, confirmation count |
| `CONFIG_WRITE` | configuration version (2 bytes) followed by length-prefixed integer parameters |
| `TIME_SYNC` | master time in ticks (8 bytes) |
| `IDENTIFY_ACK` | product, site, group and lamp ids and the MCU unique id |

`RESET_ENERGY` is transmitted as a `CONTROL_COMMAND` **subtype**; no new
message type is added for it (`PR-COMM-010`, `D-038`).

---

## 6. Integrity, ordering and duplicate handling

| Concern | Mechanism | Requirement |
| --- | --- | --- |
| Corruption | CRC per frame | `PR-COMM-006` |
| Ordering | Sequence number | `PR-COMM-005` |
| Duplicate delivery | Sequence-number window check | `PR-COMM-005` |
| Version mismatch | Protocol version field | `PR-COMM-003` |
| Misaddressing | Destination address check | `PR-COMM-003` |

Duplicate or out-of-window frames are reported, not silently processed
(`PR-COMM-005`).

---

## 7. Polling and command flow

### 7.1 Cyclic polling

```text
for each node in group:
    STATUS_REQUEST / MEASUREMENT_REQUEST
    wait for response (timeout)
    on timeout: retry up to configured retry count
    on repeated failure: mark node communication state
```

### 7.2 Command flow

```text
COMMAND_SENT -> RECEIVED -> EXECUTED -> ACKNOWLEDGED -> ACTUAL_STATE_VERIFIED
```

| Stage | Evidence |
| --- | --- |
| `COMMAND_SENT` | Command issued by an authorized sender. |
| `RECEIVED` | Node reports receipt (`CONTROL_ACK` receipt indication). |
| `EXECUTED` | Node reports execution. |
| `ACKNOWLEDGED` | Acknowledgement received and matched to `command_id`. |
| `ACTUAL_STATE_VERIFIED` | Measured/observed actual state matches the commanded state. |

A command is **not** successful merely because it was received
(`PR-CONTROL-002`).

### 7.3 Timeout and retry

| Parameter | Purpose |
| --- | --- |
| `comm_timeout` | Time to wait for a response. |
| `comm_retry_count` | Retry attempts before declaring a communication fault. |

Both are configurable (`PR-CONFIG-001`).

---

## 8. Communication state machine

```text
COMM_HEALTHY -> RETRY -> DEGRADED -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY
```

| State | Meaning |
| --- | --- |
| `COMM_HEALTHY` | Communication within expected performance. |
| `RETRY` | A response was missed; retry in progress. |
| `DEGRADED` | Repeated misses; performance reduced but link usable. |
| `COMM_FAULT` | Communication with the node is considered lost. |
| `RECOVERY` | Link re-established; re-synchronization in progress. |
| `COMM_HEALTHY` | Normal operation restored. |

`COMM_FAULT` produces a `COMMUNICATION` fault through the normal fault
lifecycle ([04_fault_management.md](04_fault_management.md)).

---

## 9. Communication failure and recovery

### 9.1 Failure scope

| Scope | Behaviour |
| --- | --- |
| Single node silent | Retry, then `COMM_FAULT` for that node; group continues. |
| Single node noisy/invalid frames | Contained at node level; counted and reported; group continues. |
| Bus fault | Detected and reported; nodes continue local operation. |
| Group Controller loses upstream link | Local group operation continues; records buffered in the Group Controller's abstract local storage/buffer. |
| Group Controller restart | Nodes continue local operation; state re-synchronized. |
| Total communication loss | Full local operation continues; store-and-forward engaged. |

### 9.2 Recovery sequence

```text
STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM
```

| Step | Meaning |
| --- | --- |
| `STORE` | Records buffered locally while communication was unavailable. |
| `RECOVERY` | Link re-established; communication state machine enters `RECOVERY`. |
| `SYNCHRONIZE` | Time and state re-synchronized with the master. |
| `UPLOAD` | Buffered records uploaded. |
| `CONFIRM` | Upload confirmed. |

No silent loss of records is permitted (`PR-STORAGE-008`,
`PR-OFFLINE-005`).

**Upload confirmation is not deletion.** When the master confirms an upload,
the record is removed from the *pending-upload queue* only. The retained
historical record stays in local storage and remains subject to the retention
policy. See [06_storage_and_logging.md](06_storage_and_logging.md) §4.

---

## 10. Local operation during communication loss

Loss of communication with the Group Controller, the Master Control Center
or the Internet shall not stop local lighting operation
(`PR-COMM-009`, `PR-OFFLINE-001`, `PR-OFFLINE-002`, `PR-OFFLINE-003`).

A lamp node continues to:

- operate its lamp in its configured mode,
- measure and log locally,
- detect, confirm and latch faults locally,
- buffer records for later upload.

---

## 11. Time synchronization

| Aspect | Behaviour |
| --- | --- |
| Distribution | Group Controller distributes time to nodes. |
| Acknowledgement | `TIME_SYNC` / `TIME_ACK`. |
| Unsynchronized nodes | Local RTC time used; time uncertainty flagged. |
| Recovery | Time re-synchronized after communication recovery. |

`PR-TIME-001` .. `PR-TIME-004`.

---

## 12. Scalability

| Dimension | Initial target | Architectural requirement |
| --- | --- | --- |
| Nodes per group | ~16 | Must scale without redesign. |
| Polling cycle time | Determined by node count and baud rate | Must remain within the configured reporting interval. |
| Bus loading | Determined by polling and reporting intervals | Measurement and reporting intervals are independently configurable. |

Polling cycle time and baud rate selection are **not yet decided**; they are
recorded as assumptions pending a Phase 9 decision.

---

## 13. Traceability

| Topic | Requirements |
| --- | --- |
| Bus discipline | `PR-COMM-001`, `PR-COMM-002` |
| Framing and integrity | `PR-COMM-003`, `PR-COMM-004`, `PR-COMM-005`, `PR-COMM-006` |
| Polling, timeout, retry | `PR-COMM-007` |
| Communication states | `PR-COMM-008` |
| Local autonomy during loss | `PR-COMM-009`, `PR-OFFLINE-001`..`PR-OFFLINE-003` |
| Recovery and synchronization | `PR-COMM-009`, `PR-OFFLINE-005`, `PR-TIME-003`, `PR-TIME-004` |
| Addressing and identity | `PR-IDENTITY-003`, `PR-IDENTITY-004` |
| Containment | `PR-SCALABILITY-003` |

---

## 14. Implementation status

| Item | Status |
| --- | --- |
| Architecture defined | Yes |
| Frame format | Defined (field level) |
| Message types | Defined (initial set) |
| Encoding, timing, electrical details | **Not defined** - Phase 9 |
| Implementation | **Not started** (Phase 9 / Phase 10 / Phase 11) |

---

## 15. Related documents

- [01_system_architecture.md](01_system_architecture.md)
- [02_product_requirements.md](02_product_requirements.md)
- [03_data_model.md](03_data_model.md)
- [04_fault_management.md](04_fault_management.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [07_configuration.md](07_configuration.md)
- [10_hardware_reference.md](10_hardware_reference.md)
- [11_assumptions.md](11_assumptions.md)

## Revision 2 digital protocol and transaction contract

The 17 message types are unchanged. The payload extension changes the wire
layout, so the prototype now uses **protocol version 2** and rejects version 1
and unknown versions before receiver state changes. This is a digital codec
revision, not a frozen physical protocol or a new product generation.

`encode_payload` / `decode_payload` are the complete wire payload API.
`MessageCodec` implements the inner message body. The complete envelope is a
2-byte big-endian body length, that many body bytes, then typed metadata.
Strings use 2-byte UTF-8 byte lengths. Decoding rejects invalid enum codes,
truncation, trailing bytes, duplicate/noncanonical parameter encodings and
noncanonical booleans. Empty ordinary requests also accept the empty-payload
shorthand. `FAULT_REPORT` polls use an empty payload; `EVENT_REPORT` polls use
a 4-byte confirmed event ID (zero initially). These are direction-specific
pull requests using the existing report types, not new types.

| Metadata | Wire representation / meaning |
| --- | --- |
| Every response | Signed 4-byte `request_sequence`, matched to source and expected response type |
| CONTROL_COMMAND, CONFIG_WRITE, TIME_SYNC | Actor-present byte, length-prefixed actor ID, role byte, authenticated byte; missing actors cannot perform privileged actions |
| CONTROL_ACK | Effective mode, active override, configured mode (one byte each), energy accumulator (8-byte binary float), in addition to command ID, execution status and observed actual state |
| CONFIG_ACK | Version, acceptance, reason and applied/read-back scalar parameter map |
| MEASUREMENT_REQUEST | 8-byte confirmed stored-record sequence (zero initially) |
| MEASUREMENT_RESPONSE | 8-byte stored-record sequence (zero for live-only readings), time-sync-state byte and availability-mask byte; missing readings do not become valid zeros |
| EVENT_REPORT response | Actor string, in addition to event identity/type/severity/reason |

Actor metadata is an **assertion supplied by the trusted simulation**. CRC is
not authentication. This does not protect against a hostile peer forging a
role or master address; authentication, cryptography and keys remain outside
this prototype. The receiver authorizes the asserted actor for the actual
subtype instead of manufacturing a privileged role from the subtype.

Both receivers use bounded modular 16-bit sequence history. Transmit counters
wrap. A malformed or unprocessed response does not consume sequence state.
The Lamp Node caches recent replies to identical retried requests; conflicting
reuse or stale requests are rejected. Command-ID idempotency and configuration
version ordering are additional safeguards, independent of frame sequence.

| Request / report | Sender / receiver and actual response path | Regression evidence |
| --- | --- | --- |
| STATUS_REQUEST / STATUS_RESPONSE | GC poll -> node snapshot -> matched registration.status | test_malformed_frame_does_not_consume_sequence_or_finish_poll |
| MEASUREMENT_REQUEST / MEASUREMENT_RESPONSE | GC poll -> oldest valid buffered measurement (or live sample) -> aggregation/buffering; next request confirms receipt | test_offline_measurement_history_is_replayed_and_retained |
| CONTROL_COMMAND / CONTROL_ACK | Authorized GC pending request -> node authorization/execution -> correlated ACK and subsequent verification evidence | test_remote_role_matrix_before_transmission; test_delivery_and_ack_are_not_actual_verification |
| CONFIG_READ / CONFIG_ACK | GC read_configuration -> node scalar readback -> registration.configuration | test_config_ordering_and_readback |
| CONFIG_WRITE / CONFIG_ACK | Authorized GC pending write -> atomic versioned node update -> readback validation | test_config_ordering_and_readback; test_unauthorized_config_never_transmitted |
| TIME_SYNC / TIME_ACK | ADMINISTER-authorized distribution -> monotonic node synchronization -> validated requested/local tick match | test_identity_time_heartbeat_ack_dispatch; test_time_distribution_denied_before_bus |
| IDENTIFY / IDENTIFY_ACK | GC identify -> node identity -> checked against registered product/site/group/lamp | test_identity_time_heartbeat_ack_dispatch |
| HEARTBEAT / HEARTBEAT_ACK | GC poll -> local tick response -> matched registration.heartbeat_ack | test_identity_time_heartbeat_ack_dispatch |
| FAULT_REPORT | GC pull -> active fault snapshot -> fault aggregation | test_fault_report_is_aggregated_without_mutating_local_lifecycle |
| EVENT_REPORT | GC pull/confirmation -> retained event -> idempotent buffering; node advances only after confirmation | test_event_report_loss_retry_and_confirm_does_not_lose_history |

Tests above are in `tests/test_post_merge.py`. Existing codec, sequence and
multi-node tests remain in `tests/test_comm.py` and `test_group_controller.py`.

`poll()` starts requests on idle nodes and returns the previous validated
poll-result flags, **not bus delivery results**. Initially the flags are false.
`collect_responses()` dispatches replies then services deadlines;
`service_timeouts()` can also be driven explicitly after advancing the logical
clock. Each node has independent pending requests, deadlines and bounded
retries. Exhaustion marks communication fault and fails pending commands;
late responses cannot resurrect them. Retry deadlines are capped by the initial
absolute transaction expiry; exhaustion does not invent missed exchanges. No wall-clock waiting or background
thread is implied. Scenarios must pump node responses onto the bus.

Commands remain RECEIVED in the GC after authorization/transmission. A matched
execution ACK advances EXECUTED and ACKNOWLEDGED. Physical ON/OFF commands
require a fresh post-command observation with consistent electrical evidence,
matching actual state, effective mode and override before ACTUAL_STATE_VERIFIED.
The node may return a later response to the same outstanding request after a
sample; this is delayed completion, not an unsolicited command. A mode change,
RETURN_TO_AUTO and RESET_ENERGY verify their respective configuration, override
and accumulator state, not electrical actuation. Local ON/OFF commands also
wait for fresh observations; a commanded boolean is never measured feedback.
