# 06 - Storage and Logging

## 1. Document purpose

This document defines the **storage and logging architecture** for Smart
Street Light V1: what is stored, where it is stored, how records are
structured and protected, how power-loss and corruption are handled, how
retention works, and how store-and-forward operates.

It is derived from `PR-STORAGE-*`, `PR-OFFLINE-*` and `PR-TIME-*` in
[02_product_requirements.md](02_product_requirements.md).

---

## 2. Storage architecture

```text
+------------------------------------------------------------------+
| LAMP NODE                                                        |
|                                                                  |
|  MCU INTERNAL FLASH              EXTERNAL SPI NOR FLASH          |
|  +---------------------+         +----------------------------+  |
|  | firmware            |         | measurements               |  |
|  | configuration       |         | events                     |  |
|  | calibration         |         | faults                     |  |
|  +---------------------+         | buffered records           |  |
|                                   +----------------------------+  |
+------------------------------------------------------------------+
```

| Storage | Contents | Notes |
| --- | --- | --- |
| Lamp Node MCU internal Flash | Firmware, configuration, calibration | Separate from record storage (`PR-STORAGE-007`). |
| Lamp Node external SPI NOR | Measurements, events, faults, buffered records | Append-heavy record storage. |
| Group Controller local storage/buffer | Node data, communication events, configuration transactions, synchronization state, upstream-failure buffering | **Abstract only.** Physical medium deliberately not selected; deferred to the hardware architecture phase. |

External SPI NOR candidate: **S25FL128L, 16 MB**. This is an engineering
candidate, not a frozen selection
([10_hardware_reference.md](10_hardware_reference.md)).

---

## 3. Record classes

| Class | Content | Source |
| --- | --- | --- |
| Measurement record | Per-lamp measurement snapshot. | Measurement handling |
| Event record | Discrete occurrence with actor and reason. | Event/logging |
| Fault record | Fault lifecycle state and evidence. | Fault lifecycle |
| Buffered record | Any record awaiting upload confirmation. | Store-and-forward |

---

## 4. Record envelope

Every persisted record is wrapped in an envelope:

| Field | Purpose |
| --- | --- |
| `sequence_number` | Monotonic ordering of records. |
| `timestamp` | Record time, with validity/uncertainty indication. |
| `record_type` | Measurement / event / fault / buffered. |
| `payload` | The record body. |
| `crc` | Integrity check over the record. |
| `commit_marker` | Indicates the record is complete and valid. |

A record is valid only when its commit marker indicates completion
(`PR-STORAGE-002`, `PR-STORAGE-003`).

---

## 5. Write and commit semantics

```text
1. append record body
2. compute CRC
3. write commit marker
4. record becomes visible and uploadable
```

If power is lost before step 3 completes, the record is incomplete and is
discarded on recovery - it is never treated as valid data.

| Requirement | Behaviour |
| --- | --- |
| `PR-STORAGE-003` | Recoverable to a consistent state after power loss at any point. |
| `PR-STORAGE-004` | Corrupt records detected, reported, excluded from upload. |

---

## 6. Corruption handling

| Condition | Required behaviour |
| --- | --- |
| CRC mismatch | Record rejected; corruption event recorded; record excluded from upload. |
| Missing commit marker | Record treated as incomplete; discarded on recovery; event recorded. |
| Sequence gap | Detected and reported; gap is visible, not silently ignored. |
| Unreadable storage region | Reported as a storage condition; never silently skipped. |

Corrupt records shall never be silently accepted or silently deleted
(`PR-STORAGE-004`).

---

## 7. Retention and storage-full behaviour

### 7.1 Retention policy model

| Rule | Requirement |
| --- | --- |
| Automatic deletion | **Disabled by default** (`PR-STORAGE-005`). |
| Configurable retention policy | Supported once the policy is decided; no numeric period is committed yet. |
| Hard minimum retention | A minimum retention period shall be enforced regardless of policy. The numeric value is **not yet decided**. |
| Authorized deletion | Deletion requires explicit authorization by an authorized actor. |
| Deletion audit event | Every deletion is recorded as an auditable event. |
| No silent deletion | No record is ever removed without an audit event. |
| Storage-full visibility | A storage-full condition must be explicitly visible. |
| Policy/acknowledgement separation | A deletion policy must never be confused with upload acknowledgement. |

### 7.2 Retention

Automatic deletion of stored records is **disabled by default**
(`PR-STORAGE-005`). Any deletion policy must be explicitly configured and
auditable.

### 7.3 Storage-full

A storage-full condition must be **explicitly visible**:

- reported as a node condition,
- recorded as a `STORAGE_FULL` event,
- surfaced in node status.

Behaviour on storage-full is explicit rather than implicit. The available
options are recorded below as **candidates for decision**, not as decided
behaviour:

| Option | Description | Status |
| --- | --- | --- |
| Stop recording new records | Preserves existing evidence; new data lost. | Candidate |
| Overwrite oldest records | Preserves newest data; requires explicit configuration because it contradicts default retention. | Candidate |
| Raise condition and continue buffering in memory | Risk of loss on power failure. | Candidate |

The selection among these options is an open engineering decision and is
recorded in [11_assumptions.md](11_assumptions.md).

---

## 8. Local logging

### 8.1 What is logged locally

| Data | Interval | Notes |
| --- | --- | --- |
| Measurements | Configurable measurement interval | Snapshot per interval. |
| Events | On occurrence | Discrete, with actor and reason. |
| Fault lifecycle transitions | On occurrence | Full lifecycle audit. |
| Communication state changes | On occurrence | Supports communication diagnosis. |

### 8.2 Timestamps

- Local RTC provides timestamps (`PR-TIME-001`).
- Records created while unsynchronized carry a time-validity/uncertainty
  indication (`PR-TIME-002`).
- Record ordering is preserved by sequence number even when time is
  uncertain (`PR-TIME-004`).

---

## 9. Offline operation and store-and-forward

### 9.1 Principle

Local operation continues without Internet, without the Master Control
Center, and without the Group Controller (`PR-OFFLINE-001` ..
`PR-OFFLINE-003`). Records are buffered and delivered after recovery.

### 9.2 Store-and-forward sequence

```text
STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM
```

| Step | Meaning |
| --- | --- |
| `STORE` | Record written to local storage and marked as buffered. |
| `RECOVERY` | Communication link re-established. |
| `SYNCHRONIZE` | Time and state re-synchronized. |
| `UPLOAD` | Buffered records transmitted. |
| `CONFIRM` | Upload confirmed; the record leaves the pending upload queue and is marked `RETAINED`. |

### 9.3 Upload confirmation is not deletion

```text
CREATED -> STORED -> PENDING_UPLOAD -> UPLOADED -> CONFIRMED -> RETAINED
```

`CONFIRMED` means only that the record may be **removed from the pending
upload queue**. The retained historical record is **not** deleted. Removal
from a temporary upload queue and deletion of a retained historical record
are distinct operations (`PR-STORAGE-009`).

### 9.4 No silent loss

```text
record created -> stored locally -> uploaded -> confirmed -> retained
```

At no point may a record disappear without either being confirmed as
delivered or being explicitly reported as lost/corrupt
(`PR-OFFLINE-005`).

---

## 10. Storage behaviour summary

| Condition | Behaviour |
| --- | --- |
| Normal operation | Records appended, uploaded as available. |
| Communication loss | Records appended and buffered. |
| Communication recovery | Records synchronized and uploaded, then moved out of the pending upload queue (retained copy preserved). |
| Power loss | Consistent state recovered; incomplete records discarded. |
| Corruption | Detected, reported, excluded from upload. |
| Storage full | Explicitly visible; behaviour to be decided. |
| Restart | Storage state re-validated on startup. |

---

## 11. Storage sizing considerations (indicative, not requirements)

The following considerations inform the Phase 8 design. They are **not**
requirements and no capacity figure is committed here:

- number of nodes per group (~16 initial target),
- measurement interval and reporting interval (configurable),
- record size,
- target retention duration,
- upload cadence.

Storage sizing is deferred to Phase 8, when intervals and record layout are
designed.

---

## 12. Traceability

| Topic | Requirements |
| --- | --- |
| Local persistence | `PR-STORAGE-001` |
| Record structure | `PR-STORAGE-002` |
| Power-loss safety | `PR-STORAGE-003` |
| Corruption handling | `PR-STORAGE-004` |
| Retention | `PR-STORAGE-005` |
| Storage-full visibility | `PR-STORAGE-006` |
| Configuration/calibration separation | `PR-STORAGE-007` |
| Store-and-forward | `PR-STORAGE-008`, `PR-OFFLINE-004`, `PR-OFFLINE-005` |
| Offline operation | `PR-OFFLINE-001` .. `PR-OFFLINE-003` |
| Time | `PR-TIME-001`, `PR-TIME-002`, `PR-TIME-004` |

---

## 13. Implementation status

| Item | Status |
| --- | --- |
| Storage architecture | Defined |
| Record envelope | Defined (field level) |
| Commit and corruption semantics | Defined |
| Physical layout, wear levelling, capacity | **Not defined** - Phase 8 |
| Implementation | **Not started** (Phase 8) |

---

## 14. Related documents

- [02_product_requirements.md](02_product_requirements.md)
- [03_data_model.md](03_data_model.md)
- [04_fault_management.md](04_fault_management.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [07_configuration.md](07_configuration.md)
- [08_testing_strategy.md](08_testing_strategy.md)
- [10_hardware_reference.md](10_hardware_reference.md)
- [11_assumptions.md](11_assumptions.md)
