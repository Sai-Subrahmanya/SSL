# 01 - System Architecture

## 1. Document purpose

This document establishes the **architectural baseline** for Smart Street
Light V1. It is derived from the requirements in
[02_product_requirements.md](02_product_requirements.md) and precedes any
design or implementation work.

It is descriptive of *structure and responsibility*, not of code.

---

## 2. Architecture overview

```text
                MASTER CONTROL CENTER
              (operator / control layer)
                         |
                         |  upstream link (site connectivity)
                         |
                  GROUP CONTROLLER
                 (RS-485 bus master)
                         |
                         |
                      RS-485 bus
                         |
   +---------------------+---------------------+
   |                     |                     |
LAMP NODE 1         LAMP NODE 2  ...      LAMP NODE N
(one per lamp)
```

| Layer | Element | Primary responsibility |
| --- | --- | --- |
| Control layer | Master Control Center | Operator-facing logical control and aggregation. |
| Group layer | Group Controller | Bus master, aggregation, distribution, buffering. |
| Field layer | Lamp Node | Per-lamp control, measurement, diagnostics, fault handling, local autonomy. |
| Link layer | RS-485 bus | Deterministic wired master/slave communication. |

Initial target: approximately **16 lamp nodes per group**. The architecture
must remain scalable in node count and group count.

---

## 3. Architectural principles

1. **Local autonomy first.** A lamp node must remain able to operate its lamp
   without the Group Controller, the Master Control Center, or the Internet.
2. **Failure containment.** Failure of any single lamp node must not
   degrade or stop the rest of the group.
3. **Explicit state.** Every element exposes state (commanded, relay
   feedback, actual, sensor, communication, controller) rather than
   inferring health from a single measurement.
4. **No silent data loss.** Records produced while communication is
   unavailable are stored and forwarded after recovery.
5. **Traceability.** Every architectural element exists to satisfy one or
   more `PR-*` requirements.
6. **Candidates are not decisions.** Hardware and parameter values described
   here are engineering candidates until decided in
   [12_engineering_decisions.md](12_engineering_decisions.md).
7. **Digital/physical separation.** The architecture separates modelled
   logic from physical hardware so that digital validation does not imply
   physical validation.

---

## 4. Lamp Node

### 4.1 Concept

One Lamp Node is associated with **one physical lamp**.

### 4.2 Responsibilities

| # | Responsibility | Notes |
| --- | --- | --- |
| 1 | Lamp ON/OFF control | Switching the associated lamp. |
| 2 | Switching command handling | Receiving and executing control commands. |
| 3 | Relay feedback | Reporting the state of the switching element separately from the command. |
| 4 | Voltage measurement | Supply-side voltage at the node. |
| 5 | Current measurement | Load current through the switched path. |
| 6 | Power measurement | Derived from voltage and current. |
| 7 | Energy accumulation | Accumulated energy for the lamp. |
| 8 | Light-level measurement | Ambient/measured light level input to automatic control. |
| 9 | Sensor-health monitoring | Validity state of each sensor input. |
| 10 | Expected-versus-actual diagnosis | Multi-evidence diagnostic evaluation. |
| 11 | Fault detection | Raising measurement abnormalities and suspected faults. |
| 12 | Fault confirmation | Configurable observation count and time window. |
| 13 | Fault latching | Preventing repeated alerts from threshold oscillation. |
| 14 | Local event logging | Recording events with timestamps. |
| 15 | Local measurement logging | Recording measurement history. |
| 16 | RTC-based timestamps | Time source for local records. |
| 17 | RS-485 communication | Responding as an addressed node on the bus. |
| 18 | Offline operation | Continuing lamp operation without upstream connectivity. |
| 19 | Communication recovery | Detecting loss and recovery, re-synchronizing buffered records. |
| 20 | Configuration handling | Storing, applying and reporting configuration. |
| 21 | Diagnostics | Self-reporting controller/sensor/communication health. |
| 22 | Watchdog / restart recovery behaviour | Restoring safe, known state after reset. |
| 23 | Identity | Reporting its stable identity. |

### 4.3 Lamp Node internal functional blocks

```text
+------------------------------------------------------------------+
| LAMP NODE                                                         |
|                                                                  |
|  +--------------+   +---------------+   +---------------------+  |
|  | Identity     |   | Configuration |   | Time / RTC          |  |
|  +--------------+   +---------------+   +---------------------+  |
|                                                                  |
|  +--------------+   +---------------+   +---------------------+  |
|  | Lighting     |   | Measurement   |   | Diagnostics         |  |
|  | Control      |-->| Handling      |-->| (expected vs actual)|  |
|  +--------------+   +---------------+   +----------+----------+  |
|                                                    |             |
|  +--------------+   +---------------+   +----------v----------+  |
|  | Fault        |<--| Event Log     |<--| Fault Detection     |  |
|  | Lifecycle    |   | (local)       |   | / Confirmation      |  |
|  +--------------+   +---------------+   +---------------------+  |
|                                                                  |
|  +--------------+   +---------------+   +---------------------+  |
|  | RS-485       |   | Offline /     |   | Local Storage       |  |
|  | Node Stack   |   | Store & Fwd   |   | (records)           |  |
|  +--------------+   +---------------+   +---------------------+  |
|                                                                  |
|  +--------------+                                                |
|  | Watchdog /   |                                                |
|  | Restart      |                                                |
|  +--------------+                                                |
+------------------------------------------------------------------+
```

### 4.4 Lamp Node states reported upstream

The Lamp Node reports, at minimum:

- operating mode,
- commanded state,
- relay feedback,
- actual state,
- voltage, current, power, energy,
- light level,
- sensor status,
- communication status,
- controller status,
- active faults.

---

## 5. Group Controller

### 5.1 Concept

The Group Controller is the **RS-485 master** for a group of lamp nodes and
the aggregation point between the field layer and the Master Control Center.

### 5.2 Responsibilities

| # | Responsibility | Notes |
| --- | --- | --- |
| 1 | RS-485 master | Sole bus master; nodes respond only when addressed. |
| 2 | Node polling | Cyclic status and measurement polling. |
| 3 | Node status | Per-node communication and health state. |
| 4 | Measurement aggregation | Collecting and consolidating per-lamp measurements. |
| 5 | Event aggregation | Collecting per-lamp events. |
| 6 | Fault aggregation | Collecting and consolidating per-lamp faults. |
| 7 | Configuration distribution | Pushing validated configuration to nodes. |
| 8 | Time synchronization | Distributing time to nodes. |
| 9 | Command forwarding | Forwarding authorized commands to target nodes. |
| 10 | Acknowledgement handling | Tracking command acknowledgement and verification. |
| 11 | Retry / timeout processing | Detecting non-response and retrying within policy. |
| 12 | Communication-fault detection | Detecting degraded and failed node communication. |
| 13 | Recovery | Managing re-synchronization after communication recovery. |
| 14 | Upstream connectivity | Link toward the Master Control Center. |
| 15 | Buffering / store-and-forward | Buffering records during upstream loss. |

### 5.3 Group isolation requirement

The failure of one lamp node must **not** bring down the group. The Group
Controller must isolate node-level failures (no response, invalid frames,
fault storms) from group-level operation and from other nodes.

---

## 6. Master Control Center

### 6.1 Concept

The Master Control Center is the **logical operator/control layer**. It is a
logical role in V1 and does not require a graphical user interface in the
early phases.

### 6.2 Information it must eventually represent

- sites,
- groups,
- lamps,
- current status,
- measurements,
- faults,
- communication state,
- event history,
- acknowledgement,
- repair,
- verification,
- configuration,
- schedules,
- overrides,
- audit history.

### 6.3 Explicit non-goal for the current phase

No graphical UI is built in this phase. The Master Control Center is defined
here as a logical layer and data model only.

---

## 7. RS-485 link layer

### 7.1 Preliminary architecture

| Property | Preliminary value |
| --- | --- |
| Physical layer | RS-485 |
| Topology | Linear multi-drop bus |
| Master | Group Controller |
| Nodes | Lamp Nodes (addressed) |
| Nodes per group | Approximately 16 (initial target) |
| Termination | End-of-bus termination concept |
| Baud rate candidates | 9.6 kbps or 19.2 kbps |

### 7.2 Preliminary frame structure

```text
+--------+------------------+----------------+---------------------+
| SOF    | Protocol Version | Source Address | Destination Address |
+--------+------------------+----------------+---------------------+
| Message Type | Payload Length | Payload | Sequence Number | CRC |
+------------------------------------------------------------------+
```

### 7.3 Initial message types

`STATUS_REQUEST`, `STATUS_RESPONSE`, `MEASUREMENT_REQUEST`,
`MEASUREMENT_RESPONSE`, `CONTROL_COMMAND`, `CONTROL_ACK`, `FAULT_REPORT`,
`EVENT_REPORT`, `CONFIG_READ`, `CONFIG_WRITE`, `CONFIG_ACK`, `TIME_SYNC`,
`TIME_ACK`, `IDENTIFY`, `IDENTIFY_ACK`, `HEARTBEAT`, `HEARTBEAT_ACK`.

The protocol is **not** implemented yet. See
[05_communication_architecture.md](05_communication_architecture.md).

---

## 8. Communication state machine

```text
COMM_HEALTHY -> RETRY -> DEGRADED -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY
```

Communication failure must not stop local lighting operation.

---

## 9. Offline operation and store-and-forward

```text
STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM
```

No silent loss of records is permitted.

---

## 10. Failure containment and degradation

| Failure | Required architectural behaviour |
| --- | --- |
| Single lamp node fails | Remaining nodes and the group continue; node reported as communication fault after policy. |
| Single lamp node misbehaves (fault storm, invalid frames) | Contained at bus/node level; must not degrade other nodes. |
| Group Controller loses upstream link | Local group operation continues; records buffered. |
| Group Controller restarts | Nodes continue local operation; state re-synchronized. |
| Bus fault / short / open | Detected and reported; nodes continue local operation. |
| Sensor invalid | Diagnostics treat as sensor problem, not confirmed lamp failure. |
| Storage full | Condition visible; behaviour explicit, never silent deletion by default. |
| RTC invalid / time uncertain | Timestamps flagged as uncertain; ordering preserved by sequence. |

---

## 11. Scalability

| Dimension | Initial target | Architectural requirement |
| --- | --- | --- |
| Lamp nodes per group | ~16 | Must scale without redesign. |
| Groups per site | Not fixed in V1 | Group Controller aggregation must be repeatable per group. |
| Sites | Not fixed in V1 | Identity hierarchy must be site-aware. |
| Records per node | Bounded by storage design | Retention and wraparound behaviour must be explicit. |

---

## 12. Architectural exclusions

The following are explicitly **outside** this architecture's validation
claims:

- mains electrical safety,
- PCB safety and layout,
- isolation, creepage, clearance,
- EMC, surge, ESD,
- relay lifetime,
- LED inrush,
- thermal performance,
- enclosure and IP rating,
- actual RF performance,
- certification.

---

## 13. Architectural traceability

| Architecture element | Related requirements |
| --- | --- |
| Master Control Center | `PR-SCALABILITY-002`, `PR-OFFLINE-002`, `PR-FAULT-007`, `PR-SECURITY-003` |
| Group Controller | `PR-COMM-001`, `PR-COMM-002`, `PR-COMM-007`, `PR-SCALABILITY-001`, `PR-SCALABILITY-003`, `PR-OFFLINE-003`, `PR-TIME-003` |
| RS-485 link | `PR-COMM-003`, `PR-COMM-004`, `PR-COMM-005`, `PR-COMM-006`, `PR-COMM-008`, `PR-COMM-009` |
| Lamp Node control | `PR-LIGHT-001`..`PR-LIGHT-005`, `PR-CONTROL-001`..`PR-CONTROL-006` |
| Lamp Node measurement | `PR-MEASURE-001`..`PR-MEASURE-005` |
| Lamp Node diagnostics | `PR-DIAG-001`..`PR-DIAG-007` |
| Fault lifecycle | `PR-FAULT-001`..`PR-FAULT-012` |
| Storage / logging | `PR-STORAGE-001`..`PR-STORAGE-008`, `PR-TIME-001`, `PR-TIME-002` |
| Configuration | `PR-CONFIG-001`..`PR-CONFIG-006` |
| Identity | `PR-IDENTITY-001`..`PR-IDENTITY-004` |
| Security / audit | `PR-SECURITY-001`..`PR-SECURITY-005` |
| Offline behaviour | `PR-OFFLINE-001`..`PR-OFFLINE-005` |

The authoritative mapping is
[requirements_traceability.md](requirements_traceability.md).

---

## 14. Related documents

- [00_project_overview.md](00_project_overview.md)
- [02_product_requirements.md](02_product_requirements.md)
- [03_data_model.md](03_data_model.md)
- [04_fault_management.md](04_fault_management.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [07_configuration.md](07_configuration.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
