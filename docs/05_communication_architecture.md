# 05 - Communication Architecture

## 1. Document purpose

This document defines the preliminary **communication architecture** for
Smart Street Light V1: the RS-485 field bus, framing, message types,
polling and command flow, the communication state machine, and
communication failure and recovery behaviour.

It is derived from `PR-COMM-*`, `PR-OFFLINE-*` and `PR-TIME-*` in
[02_product_requirements.md](02_product_requirements.md).

The protocol is **not implemented** in this repository. This document is the
architectural baseline for Phase 9.

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
| Group Controller loses upstream link | Local group operation continues; records buffered. |
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
| `CONFIRM` | Upload confirmed; buffered records released. |

No silent loss of records is permitted (`PR-STORAGE-008`,
`PR-OFFLINE-005`).

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
