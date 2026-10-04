# 15 - Final Engineering Audit (Phase 18)

## 1. Purpose

This document is the **final engineering audit** of the Smart Street Light V1
digital prototype. It determines whether the design, the implementation and
the engineering documentation are mature enough to freeze the architecture and
begin preparing a preliminary engineering/prototype package for Minewing.

The audit is not a development phase: it added no product behaviour. It
challenged every major engineering decision, corrected the defects it found,
and recorded what remains genuinely open.

---

## 2. Starting SHA

`2a76b8d58935c4c30c3162e9ac6fc4011c68fa92` (Phase 17, system validation),
whose parent is `cf4a8db8c0cc609328502ad12aaa7304550efd36` (Phase 16).

## 3. Final SHA

The audit commit that introduced this report is
`8383c47e63b6ecb94f1cb528ccdb4dcaeacfc1f1` ("Phase 18: final engineering
audit"), whose parent is `2a76b8d58935c4c30c3162e9ac6fc4011c68fa92` (Phase 17).
The branch HEAD at delivery is the record-keeping commit that follows it on
`arena/01a0dcf6-ssl` (it only completes this section, because a commit cannot
contain its own hash); the exact HEAD value, remote-verified, is reported in
the audit's final response. Starting SHA, audit commit and branch HEAD are
therefore all stated explicitly rather than left to inference.

## 4. Repository and branch verification

| Item | Value at audit time |
| --- | --- |
| Working branch | `arena/01a0dcf6-ssl` |
| Local `HEAD` at start | `2a76b8d` - re-anchored after the sandbox pointer was stale (the worktree was proven byte-identical to `2a76b8d` with `git archive` + `diff -rq` before `git reset --mixed`) |
| Parent of `HEAD` | `cf4a8db8c0cc609328502ad12aaa7304550efd36` (Phase 16) |
| Remote branch HEAD | `2a76b8d58935c4c30c3162e9ac6fc4011c68fa92` |
| `main` | `9e2fa26f46de421afbd432d65d580a44314d7129` (untouched) |
| PR #2 | open, `merged=false`, `mergedAt=null` (not merged, not modified) |
| Working tree | clean |

## 5. Baseline validation (before any edit)

| Check | Result |
| --- | --- |
| `python3 -m pytest tests/` | **645 passed** (3.27 s) |
| `python3 -m pytest tests/test_integration.py` | 38 passed |
| `python3 -m pytest tests/test_system_validation.py` | 6 passed |
| `python3 -m compileall -q src tests` | exit 0 |
| `pyflakes src/sslv1 tests/*.py` | 5 findings, all pre-existing in untouched `__init__.py` files |
| `npx markdownlint-cli2` | 21 files, 0 issues |
| `git status` | clean |

The baseline was recorded before any change and was **not** cleaned up or
improved as part of the audit.

## 6. Audit methodology

Every authoritative document was read at its current revision
(`README.md`, `docs/00` to `docs/14`, `requirements_traceability.md`,
`IMPLEMENTATION_REPORT.md`), together with all 24 source files under `src/`
and the test suite. For every major decision the audit asked:

1. Is the requirement clear?
2. Is the architectural decision explicit?
3. Is the implementation consistent with the decision?
4. Is the digital model internally correct?
5. Is the decision physically plausible?
6. Is there an unresolved assumption?
7. If unresolved, is it correctly classified?
8. Does any document imply stronger evidence than exists?
9. Would a competent electronics/product engineer challenge this before PCB design?
10. If challenged, is there enough information to answer?

Mechanical checks used alongside reading:

- a traceability script (88 rows, status counts, `docs/02` versus matrix
  comparison, citation resolution to real tests in the right file);
- a test-quality script (AST scan for missing assertions, tautologies,
  private-only assertions, duplicated bodies, no-assertion tests);
- an import/usage scan of `src/` for orphaned modules and duplicated logic;
- targeted datasheet verification (Mean Well IRM-10/20, TI ISOW7741, TI
  ISOW1412, Quectel EG915U) where a concrete hardware claim needed checking.

Findings are classified as **DEFECT** (fixed now), **ENGINEERING GAP**
(input missing before physical design), **ACCEPTED DIGITAL BOUNDARY**,
**DESIGN DECISION** (frozen) or **FUTURE WORK**.

## 7. Executive engineering verdict

**PASS WITH CONDITIONS.**

The digital architecture is sound, internally consistent and honestly bounded:
one hierarchy with one owner per concern, one implementation of each state
machine, a traceability matrix whose 88 rows match the implemented behaviour,
and a test suite that exercises behaviour rather than internals. No production
defect was found; the audit changed no production code and no requirement
status.

It is **not** a PASS because specific engineering decisions must be resolved
before a schematic or PCB layout is frozen:

1. the mains safety class, protective-earth treatment and isolation boundary
   (`A-30`) - new in this audit, previously unrecorded;
2. the hardware inputs in [10_hardware_reference.md](10_hardware_reference.md)
   sections 4 to 8 (unselected function blocks, power tree, measurement chain,
   relay rating versus LED inrush, enclosure/thermal);
3. the fault-set reporting contract for the physical prototype
   ([12_engineering_decisions.md](12_engineering_decisions.md) `D-044`,
   `Proposed`), which `PR-FAULT-007` depends on.

It is **not** a HOLD: nothing found blocks progression, and no defect requires
architectural change.

---

## 8. Architecture audit

Hierarchy: **MCC -> Group Controller -> Lamp Node -> external luminaire**
(`D-001`, `D-003`, `D-025`). Ownership was verified in the code, not only in
the documents:

| Concern | Owner (verified) | Evidence |
| --- | --- | --- |
| Lamp control, diagnostics, fault lifecycle, notification | Lamp Node | `FaultEngine`, `NotificationEngine` and `DiagnosticsEngine` are instantiated only in `nodes/lamp_node.py` |
| Command authorization | Single `AuthorizationService`, used by command, storage, protocol, MCC and both node layers | `authorization.py` importers |
| Command lifecycle | `command.py`, consumed by both node layers and the MCC | `command.py` importers |
| Record storage and retention | One `RecordStore` per node and per controller (`storage.py`); no MCC store | `storage.py` importers; `mcc.py` instantiates no store |
| Time | One logical time model per device (`time_model.py`); no second clock | `time_model.py` importers |
| Communication state | One state machine (`comm/state_machine.py`) used by both node layers | `state_machine.py` importers |
| Configuration semantics | `configuration.py`, consulted by control, diagnostics, fault, measurement and notification | `configuration.py` importers |
| Aggregation and derived views | MCC reads what the controllers reported; it stores nothing of its own | `mcc.py` docstring and `docs/03` section 13.1 |
| Event/audit trail | Node and controller event logs; the MCC reads them, keeps none | `event.py` importers |

Specific challenges:

- **Does the MCC become a second controller?** No. It forwards commands
  through `GroupController.forward_control` and the existing authorization
  path, holds no lamp state of its own, and derives every view from received
  records. It has no GUI, no persistence and no database (`D-041`).
- **Does the MCC keep a second lamp-state database?** No - it keeps received
  records in arrival order plus a duplicate counter; there is no store engine
  and no independent lifecycle (`D-043`).
- **Does the Group Controller duplicate node fault/control logic?** No - it
  forwards, correlates and buffers; it has no fault engine, no diagnostics
  engine and no control model.
- **Is authorization, fault lifecycle, storage, time, communication state or
  configuration semantics re-implemented anywhere?** No. Every one of them has
  exactly one implementation, and every source module is imported by at least
  one other layer (only `mcc.py` has no `src/` importer, which is correct: it
  is the top layer, consumed by the tests). No orphan module, no duplicated
  engine.

Result: **no duplication, no competing source of truth** - a DESIGN DECISION
that stays frozen.

## 9. Hardware architecture audit

The candidate list in [10_hardware_reference.md](10_hardware_reference.md)
was audited against the functions the architecture needs. Findings:

- The named candidates are plausible for their intended functions. Datasheet
  checks that mattered: `ISOW1412` is an isolated RS-485/RS-422 transceiver
  with an integrated DC-DC (500 kbps, 1/8 unit load, up to 256 nodes) - not a
  generic digital isolator, which is how the document described it;
  `ISOW7741` is a quad-channel isolator with an integrated isolated supply of
  about 0.55 W, so the isolated-side load must fit that budget; the Quectel
  EG915U needs a 3.3-4.3 V rail able to deliver at least 2 A (LTE) and 3 A
  (LTE plus GSM) peak, which is the real constraint on the Group Controller
  power tree.
- The candidate list was **incomplete**: current sensing, mains voltage
  sensing, relay drive, switching feedback, input protection, RTC backup,
  service interface, RS-485 termination/biasing, Ethernet magnetics, SIM/antenna
  and the Group Controller storage medium had no entry at all. That is an
  ENGINEERING GAP: a hardware engineer would have to invent those blocks
  without knowing which are architectural.
- No exact part number or suffix is fixed. Every candidate still needs its
  suffix selected against the real load, tolerance and temperature range - this
  is an ENGINEERING GAP, not a defect, because `D-023` deliberately keeps
  components as candidates.

Fix: `docs/10` was reorganised into candidates (with datasheet facts marked as
such), a "required function blocks not yet selected" table, and explicit
safety, power and measurement input lists. No part number was invented and no
BOM was created.

## 10. Power architecture audit

No rail budget existed anywhere in the repository. The audit recorded the two
chains as **inputs to be closed**, not as results:
`AC -> protection -> isolated 5 V -> 3.3 V -> loads` for the Lamp Node, and
`AC -> isolated 12 V -> DC-DC -> 3.3 V/5 V/3.8 V rails` for the Group
Controller. Open items: relay coil current and duty, the dissipative loss in
the 5 V -> 3.3 V linear regulator, the cellular peak-current path and its bulk
capacitance, converter thermal load, rail sequencing, brown-out thresholds and
startup/inrush behaviour. Datasheet evidence (module input range, isolated
output power, modem peak current) is recorded as evidence; **no number is
presented as a design result**. ENGINEERING GAP, recorded in `docs/10`
section 7. It does not block preliminary CAD; it blocks the PCB power design.

## 11. Mains and safety audit

This is the most significant finding of the audit. The repository consistently
listed "mains safety, isolation, creepage/clearance" as *physical validation*
items, but nowhere recorded that the **product-safety architecture itself is
undecided**: safety class (Class I with protective earth versus Class II
double-insulated), protective-earth treatment, and the location and rating of
the isolation boundary. Grep evidence: the combined terms Class I, Class II,
protective earth and creepage/clearance appeared **nowhere** in the
documentation.

Consequences recorded in the audit:

- the question cannot be answered by digital work, and it must not be silently
  assumed either way;
- it gates schematic capture and is mandatory before PCB layout, because it
  determines creepage/clearance, the earth path, connector requirements and the
  enclosure concept;
- it is the first question a hardware reviewer will ask, and distributor
  documentation listing the candidate isolated AC/DC modules as Class II
  components does **not** decide the product class - that attribute must be
  confirmed from the official datasheets as part of the decision.

Fix: assumption `A-30` now records the open decision, `docs/10` section 6 lists
the mains/safety and mechanical inputs required before schematic capture, and
the assumption register's blocking map now points at schematic/PCB design
instead of completed digital phases. **No compliance claim is made anywhere.**

## 12. Measurement audit

The measurement model carries voltage, current, power, energy and light level
with explicit validity; it carries **no** power factor, frequency or
temperature, and it makes no accuracy claim (`PR-MEASURE-005`, `D-029`).
Digital behaviour is genuinely tested (validity, plausibility, monotonic
energy, authorized reset, restart survival).

ENGINEERING GAP (recorded, `docs/10` section 8): current-sensor type and
burden, metering front-end range and isolation, voltage-sensing arrangement,
the **energy source of record** (metering-IC register versus firmware
integration - the digital model integrates sampled power, which also decides
where calibration lives), calibration procedure and coefficient storage, phase
relationship, and light-sensor placement/saturation. Requirement
`PR-STORAGE-007` remains `PARTIAL` for the physical separation and calibration
storage; nothing here implies billing-grade metering.

## 13. Communication audit

Verified digitally: framing, CRC, protocol version, addressing, sequence
handling, duplicate and stale-frame detection, timeout, retry, the
communication state machine and the recovery path
(`src/sslv1/comm/`, `tests/test_comm.py`, `tests/test_post_merge.py`,
`tests/test_integration.py`). The link-fault path is tracked as link health with
`COMM_STATE_CHANGED` / `COMM_FAULT_DETECTED` / `COMM_RECOVERED` events;
automatic conversion into the managed per-lamp fault workflow is **not**
implemented, so `PR-COMM-008` stays `PARTIAL` (documented in `docs/04` and
`docs/05`, corrected in Phase 17).

Physical inputs still open (now listed in `docs/10` section 4): transceiver
selection and isolation, termination and biasing, cable and unit-load budget,
surge/ESD protection on the external bus, common-mode range, the UART
parameters (data bits/parity/stop bits) and the resulting real cycle time at
the chosen baud rate (`A-05`). The in-memory bus proves protocol behaviour
only; no RS-485 electrical behaviour is claimed.

## 14. Storage, RTC and power-loss audit

The digital model demonstrates the commit-marker protocol, corruption
exclusion, retention-versus-confirmation separation (`D-035`), pending-upload
bookkeeping, recovery from a simulated power loss and restart-retained state.
It is **object retention in memory**, not non-volatile storage: no flash
programming, wear, write timing, file system or real power-fail behaviour is
modelled (`docs/09`).

The conceptual separation the architecture needs already exists: records
(events, faults, measurements, buffered records) in the record store;
configuration as separate object state; identity in the identity model;
firmware and calibration explicitly outside the record store
(`PR-STORAGE-007`, `docs/06` section 2). What is missing is the physical
partitioning and medium decision (`A-09`, `A-10`, `A-16`, `A-28`, `A-29`), and
the storage of calibration coefficients. ENGINEERING GAP, recorded; the
storage architecture is **not** declared final.

RTC: only logical clock semantics are modelled. Physical accuracy, drift and
backup retention are unproven (`A-26`, `PR-TIME-005` stays `PLANNED`); the
physical measurements Minewing would need are listed in section 24.

## 15. Fault and control audit

Fault lifecycle: the seven states and the permitted transitions in `docs/04`
match `FaultLifecycle.TRANSITIONS`; confirmation requires consecutive
observations inside the configured window, latching survives single
oscillations, recurrence produces a new identity with a `previous_fault_id`
link, notification state advances independently of the lifecycle, and failed
verification returns to `UNDER_REPAIR` rather than closing (`PR-FAULT-011`
stays `PARTIAL` because repair verification takes an authorized externally
supplied outcome rather than comparing physical repair evidence).

Control and safety: mode priority (`PR-CONTROL-001`) puts genuine hardware
protection first, then an authorized override, then automatic control; no
protection condition is defined in V1 and none was invented. A fault - even
unacknowledged, even escalated - never switches the lamp off and never engages
the unused protection hook (`PR-CONTROL-006`, `PR-FAULT-009`, verified by
`tests/test_system_validation.py`). The operator requirement is explicit and
unchanged: if the operator commands the lamp ON while measurements are
abnormal, the system keeps it ON and continues measuring, logging, notifying
and escalating. `RETURN_TO_AUTO` is an action, not a mode.

`PR-FAULT-007` determination: the single-snapshot `FAULT_REPORT` pull is a real
limitation with real consequences (a second concurrent fault on the same lamp
is not propagated; a fault closed while another is being reported is not
recorded as cleared upstream). Digital work cannot fix it without inventing a
wire contract, and it must be fixed before firmware freeze rather than after
deployment. It is therefore recorded as **`D-044` (`Proposed`)**: the physical
prototype's fault report carries the bounded active fault **set** with per-fault
open/close transitions. The digital model is unchanged, `PR-FAULT-007` remains
`PARTIAL`, and the limitation stays pinned by
`test_concurrent_confirmed_faults_are_bounded_by_the_single_fault_report_pull`.

## 16. Security audit

The repository is honest about this: the authorization model is an asserted
actor with a preliminary role mapping (`D-036`, `A-19`, `A-27`) on a trusted
bus. There is no peer authentication, no cryptographic integrity, no replay
protection, no key storage, no secure boot, no signed firmware update, no TLS
and no tamper detection. `PR-SECURITY-004` and `PR-SECURITY-005` stay
`PLANNED`, and the audit agrees with that classification: implementing
cryptography now would neither be required by a V1 requirement nor testable in
a digital model, and it must not be added to make the status look better.

What must be defined before a real prototype (recorded as a required input, not
implemented): the operator identity mechanism, key and credential storage,
firmware update and secure-boot policy, upstream transport security, command
replay protection, and the physical security of the service interface and the
enclosure. The security boundary is unchanged and is restated in
`docs/09` section 5.2.

## 17. Time and identity audit

Time: logical clock only - monotonic, deterministic, never silently
synchronized, uncertainty preserved through records and restart, no back-dating
on delayed synchronization. Physical RTC accuracy, drift and backup retention
are unproven (`PR-TIME-005` stays `PLANNED`, `A-26` stays open). Required
physical measurements are listed in section 24.

Identity: the hierarchy `Product -> Site -> Group -> Lamp -> MCU unique ID` is
implemented and deterministic across restart; duplicate bus addresses and
duplicate lamp identities are detected and rejected; `IDENTIFY` / `IDENTIFY_ACK`
returns the node's own identity, which is what commissioning verification needs.

**Gap identified (ENGINEERING GAP, product-scope decision).** The V1 baseline
contains no requirement for **commissioning and node replacement**: how a new
node's MCU unique ID is bound to an existing site/group/lamp identity, what
happens to the replaced node's records and faults, and what a factory/service
reset means. A field technician can verify *that* the right node answers at an
address, but the replacement procedure itself is unspecified. This audit did
**not** invent a requirement (the 88-requirement baseline is frozen and was
reviewed as such); the missing requirement is named here and listed as a
product-owner input in sections 25 and 29. No GUI was built.

## 18. Environmental and mechanical audit

No CAD was produced. The audit recorded which mechanical requirements follow
from the electronics, so that CAD can be created from them rather than
invented independently: enclosure must satisfy the creepage/clearance the
safety class demands (`A-30`), keep the mains side physically separated from
the low-voltage side, mount at/next to the luminaire, provide cable entry for
mains and field bus, expose the light sensor to ambient light (not to the
luminaire's own output), give the cellular antenna its keep-out and the RF path
to the outside, conduct heat away from the relay coil, converters and
regulators, provide a service opening for SWD/debug and include tamper
considerations. The IP rating and environmental exposure follow from the
installation location, which is a site input. All of this is ENGINEERING GAP /
ACCEPTED DIGITAL BOUNDARY: requirements recorded, values not invented.

## 19. International and regional audit

Universal: the wide-input AC/DC architecture, the isolated low-voltage domain,
the switching function and the monitoring architecture are market-independent.
Regional: the cellular variant (`A-15`), the installation practice and the
country-specific certification path. Undecided: the target market for the first
prototype (India and China are the stated initial markets, international
adaptability is a direction, `D-025`), and the input frequency range, which is
a datasheet property of the selected module and is not yet recorded. The
90-305 VAC / 230 VAC / single-phase line-to-neutral targets are design targets
only; **no compliance or certification claim is made**.

## 20. Requirement and traceability audit

Mechanically verified: 88 requirements in `docs/02`, 88 matrix rows in
`requirements_traceability.md`, no missing row, no matrix id without a
requirement, no duplicated requirement id, and 0 status mismatches between
`docs/02` and the matrix. Status counts remain **77 `VERIFIED` / 8 `PARTIAL` /
3 `PLANNED`**. Every cited test (about 200 explicit `file::test` references)
resolves to a real test in the cited file; no stale test id, no wrong-file
citation.

Status integrity was re-challenged rather than assumed: no row was upgraded for
merely having an implementation or a passing test, and none was downgraded
without a concrete reason. The 8 `PARTIAL` rows and 3 `PLANNED` rows were
re-verified against the code and remain correctly classified.

Contradictions found and fixed (documentation defects, not status changes):

- `docs/02` section 6 claimed `PR-MEASURE-005`, `PR-CONTROL-005`,
  `PR-STORAGE-003` and `PR-TIME-001` "cannot be verified digitally" while the
  matrix marks parts of them `VERIFIED`. Section 6 is now the authoritative
  digital-versus-physical split, and `PR-CONTROL-005` and `PR-STORAGE-003` carry
  per-requirement boundary notes.
- `docs/05` section 14 still said the protocol implementation was "not started"
  and that encoding would be fixed "in Phase 9", contradicting section 1 of the
  same document and the code; section 3 and section 12 carried the same stale
  phase references.
- `docs/01` section 7.3 said the protocol "is not implemented yet".
- `docs/03` section 1 and `docs/06` sections 11/13 deferred storage layout to
  "Phase 8", a phase that is complete, instead of the hardware phase.
- `docs/11` mapped open assumptions onto phases (3, 6, 8, 9, 10, 12) that have
  already run.

## 21. Assumption audit

29 assumptions existed; the audit added **A-30** (mains safety class,
protective-earth treatment, isolation boundary), giving **30: 3 `Target`,
19 `Open`, 8 `Accepted`**. No existing status changed. None of the six
assumptions under review was closed by digital work:

| Assumption | Why it is open | Can digital work resolve it? | What resolves it | Blocks PCB? | Blocks Minewing review? | May stay open now? |
| --- | --- | --- | --- | --- | --- | --- |
| `A-09` storage-full behaviour | No policy selected; options have different evidence-retention consequences | No - a product policy, not a logic property | Product/site policy decision | Only the medium's self-protection behaviour | No - must be raised in review | Yes |
| `A-10` retention duration | Depends on site policy, capacity and upload cadence | No - no numeric input exists | Site policy and storage sizing | Yes (capacity) | No | Yes |
| `A-18` switching feedback | Physical realisation undecided (switched-output sensing, auxiliary contact or equivalent) | No - a hardware decision | Hardware design decision | Yes (it is a sense input) | Yes - it changes diagnostics' primary evidence | Yes, with the decision flagged |
| `A-26` RTC backup duration | Requires measurement of the physical RTC and its backup | No - physical property | Hardware validation campaign | No (affects the backup circuit choice) | No | Yes |
| `A-27` detailed permission matrix | Deliberate deferral to the security design phase | No - security design input | Security design | No | No | Yes |
| `A-29` numeric retention period | No numeric floor decided | No - no input exists | Site policy and storage sizing | Only the store's sizing | No | Yes |
| `A-30` safety class / PE / isolation boundary (new) | Never decided, previously unrecorded | No - product/safety decision | Safety decision with the enclosure concept and a qualified engineer | **Yes - gates schematic and layout** | **Yes - first question in review** | Yes, but it must be the first decision taken |

The register now separates what blocks schematic/PCB design, what blocks
prototype/firmware behaviour, what belongs to the physical-validation campaign
and what is a site/commercial input. No assumption was silently converted into
a decision.

## 22. Decision audit

43 `Established` decisions were re-read for contradictions, supersessions,
documented-but-unimplemented entries and implied-but-undocumented decisions.

- Contradictions: none. Statuses remain 43 `Established`, 0 `Superseded`.
  `D-042` and `D-043` (Phase 16 behaviour recorded by the Phase 17 audit) are
  the only entries that were documented after implementation, and they
  describe exactly what the code does.
- Documented but not implemented: none, other than the new `D-044`, which is
  explicitly `Proposed` and explicitly not implemented.
- Implied but undocumented: the fault-reporting determination above
  (`D-044`), and the fact that the physical-prototype wire contract will need a
  protocol revision once the fault set is carried. `D-044` records this.
- Not invented: no decision was added for the safety class (that stays an open
  assumption, `A-30`) or for any future feature.

## 23. Test-quality audit

| Check | Result |
| --- | --- |
| Test functions / collected tests | 575 functions, 645 collected (deterministic, no randomness, no wall-clock dependence) |
| Missing assertions | none (the Phase 17 regression holds) |
| Tautological assertions | none |
| Identical test bodies | none |
| Assertions on private members only | 1 found - fixed |
| Negative paths | present and specific: `pytest.raises` with the concrete exception type across protocol, configuration, storage, identity, fault and time tests |
| Over-broad exception | 1 found (`pytest.raises(Exception)`) - replaced with the concrete `FrozenInstanceError` plus a value check |
| Mocked components | none: the tests drive the real `LampNode`, `GroupController`, `MCC`, command, fault, storage and protocol objects; only the **sensor inputs** are injected, which is the documented abstraction |
| Hidden global state | none: an AST scan found no module-level mutable state (only enum members and class constants) |
| Multi-node isolation | covered (`test_integration.py`, `test_fault_injection.py`, 16-node and 64-lamp scenes) |
| Simultaneous faults | covered, including the *bounded* behaviour of the single-snapshot report |
| Tests that would pass while the feature is broken | inspected for the representative modules (requirements, control, fault, communication, storage, offline, MCC, integration); the state machines are driven through their legal and illegal transitions rather than asserted directly after construction |

Two fixes were made (both LOW): the concrete exception above, and an energy
test that asserted only an internal accumulator now asserts the published
measurement value. No tests were added, so the count is unchanged at 645.

## 24. Digital-versus-physical boundary

**PROVEN DIGITALLY (bounded to the model):** control modes and priority;
command lifecycle and duplicate suppression; fault lifecycle, confirmation,
latching, recurrence, notification, escalation and closure; diagnostics rules
and evidence combination; protocol framing, CRC, sequencing, duplicates,
timeouts, retries and the communication state machine; store-and-forward,
pending-upload bookkeeping, retention versus confirmation, corruption
exclusion; configuration validation, versioning, authorization and readback;
identity hierarchy and duplicate detection; aggregation and derived views;
offline operation and recovery orchestration; restart semantics; audit/event
propagation; the 64-lamp software-scale behaviour.

**PARTIALLY PROVEN DIGITALLY (the model part is proven, the physical part is
not):** restart/power-loss behaviour; recovery of buffered history; storage
commit semantics; configuration persistence; energy accumulation; time
validity and ordering; link-fault handling; scale and resource behaviour;
repair verification (`PR-FAULT-011`).

**NOT PROVEN - REQUIRES HARDWARE:** mains safety, isolation, creepage and
clearance; EMC, surge and ESD; relay contact life and LED-driver inrush; thermal
performance; enclosure and IP; physical RTC accuracy and backup; real RS-485
electrical behaviour and timing; cellular/RF behaviour; metering accuracy;
certification; production readiness.

**NOT PROVEN - REQUIRES AN ENGINEERING/DATASHEET DECISION:** safety class and
isolation boundary (`A-30`); relay rating and switching-element selection; power
tree and rail budget; measurement chain and calibration; storage medium and
partitioning; RTC backup circuit; RS-485 transceiver, termination and biasing;
Ethernet magnetics; cellular supply, antenna, SIM and regional variant; exact
part suffixes; energy source of record.

**NOT PROVEN - REQUIRES SYSTEM/INSTALLATION INFORMATION:** target market and
certification path; installation environment, IP rating and temperature range;
site operating policy (out-of-window behaviour, schedules); retention and
storage-full policy; severity scale and clear policy; environmental sensor set;
commissioning and replacement procedure.

Physical measurements Minewing would eventually need to run: RTC retention and
drift; relay endurance and LED inrush; thermal rise in the enclosure;
isolation/creepage verification; EMC/surge/ESD; metering accuracy against a
reference; RS-485 signal integrity over the real cable; RF performance and
antenna behaviour; power-tree behaviour at cellular transmit bursts.

## 25. Minewing readiness gate

If the repository were handed to Minewing tomorrow, the review material falls
into four groups.

### A. READY FOR ENGINEERING REVIEW

- the product boundary and system architecture (monitoring and control system
  for an *external* luminaire, `D-001`);
- the functional behaviour and its evidence: control and mode priority, command
  lifecycle, fault lifecycle and notification, offline store-and-forward,
  configuration authorization/versioning, communication state machine,
  identity, aggregation;
- the requirement baseline with traceability and bounded statuses (88 rows,
  77 `VERIFIED` / 8 `PARTIAL` / 3 `PLANNED`);
- the explicit limitation list and claim discipline (`docs/09`), the
  digital-versus-physical boundary (section 24) and the assumptions register;
- the test suite as behavioural evidence (645 deterministic tests).

### B. NEEDS CLARIFICATION BEFORE REVIEW

- the missing commissioning/node-replacement requirement (product-owner scope
  decision, section 17);
- the site/product policies still undecided: out-of-window behaviour (`A-07`),
  restart default (`A-08`), storage-full (`A-09`), retention (`A-10`, `A-29`),
  severity scale (`A-11`), clear policy (`A-12`), time-sync cadence (`A-13`);
- whether the fault-set report (`D-044`) is accepted as the prototype's wire
  direction and by when.

### C. REQUIRES MINEWING/HARDWARE ENGINEERING INPUT

- safety class, protective earth and isolation boundary (`A-30`); creepage and
  clearance rules; input protection; relay rating against the real lamp load
  and inrush; thermal and enclosure/IP; mechanical concept; connectors and
  service access;
- RS-485 transceiver, isolation, termination, biasing and cable/protection;
  UART parameters and baud rate (`A-05`);
- Ethernet magnetics and ESD protection; cellular supply, antenna, SIM/eSIM,
  regional variant and certification (`A-14`, `A-15`);
- storage medium and partitioning (`A-16`, `A-28`); RTC backup circuit;
- measurement chain, calibration and the energy source of record; switching
  feedback realisation (`A-18`);
- exact part numbers and suffixes for every block in `docs/10` section 4.

### D. FUTURE / NOT REQUIRED FOR FIRST PROTOTYPE

- production security architecture (authentication, key management, secure
  boot, signed update, transport security, replay protection) - stays
  `PLANNED`;
- production MCC persistence/database, GUI, operator application, cloud
  backend;
- certified metering, formal certification and production firmware/RTOS
  decisions;
- production-scale multi-site deployment and resource engineering.

**Can CAD be started?** **Yes for preliminary enclosure/mechanical concept
work** - the mechanical requirements now derive from the electronics
(`docs/10` section 6) and the drawing set does not need the PCB. **No for PCB
layout or any freeze**: the safety class and isolation boundary (`A-30`) set
creepage/clearance, partitioning and the earth path, and the power/measurement
chains are still open. Preliminary CAD must be labelled as concept work and may
change once those decisions are taken.

## 26. Findings table

| ID | Severity | Finding | Class | Status |
| --- | --- | --- | --- | --- |
| H-01 | HIGH | Mains safety class, protective-earth treatment and isolation boundary undecided and previously unrecorded; gates schematic and PCB layout | DEFECT (documentation) + ENGINEERING GAP | Fixed: `A-30`, `docs/10` section 6, blocking map |
| M-01 | MEDIUM | `docs/02` section 6 contradicted the traceability statuses of four requirements (claimed not digitally verifiable while marked `VERIFIED`) | DEFECT | Fixed: section 6 rewritten, boundary notes added |
| M-02 | MEDIUM | `docs/05` section 14 said the protocol implementation was "not started" and encoding "to be fixed in Phase 9"; section 3/12 carried the same stale references | DEFECT | Fixed |
| M-03 | MEDIUM | `docs/10` was incomplete for a hardware review: missing required function blocks, `ISOW1412` mis-described, no safety/power/measurement inputs and no datasheet grounding | DEFECT + ENGINEERING GAP | Fixed: `docs/10` restructured and extended |
| M-04 | MEDIUM | Assumption register mapped open assumptions onto phases that are already complete | DEFECT | Fixed: blocking map re-mapped to schematic/PCB/prototype/site inputs |
| M-05 | MEDIUM | `PR-FAULT-007` limitation had no determination for the physical prototype | ENGINEERING GAP | Documented: `D-044` `Proposed`; requirement stays `PARTIAL` |
| M-06 | MEDIUM | No commissioning/node-replacement requirement exists in the V1 baseline | ENGINEERING GAP | Identified; product-owner scope decision, not invented |
| L-01 | LOW | `docs/01` section 7.3 said the protocol "is not implemented yet" | DEFECT | Fixed |
| L-02 | LOW | `docs/03` section 1 and `docs/06` sections 11/13 deferred storage layout to completed "Phase 8" | DEFECT | Fixed |
| L-03 | LOW | `test_configuration_is_immutable_once_validated` used `pytest.raises(Exception)`, so any unrelated exception would pass | DEFECT (test) | Fixed: concrete `FrozenInstanceError` plus value check |
| L-04 | LOW | Energy test asserted only a private accumulator instead of the published value | DEFECT (test) | Fixed |
| L-05 | LOW | `PR-CONTROL-005` and `PR-STORAGE-003` lacked the claim-boundary note their wording requires (physical behaviour implied) | DEFECT | Fixed: boundary notes added |
| I-01 | INFO | The Phase 18 brief referred to `docs/06_configuration.md`; the repository has `docs/06_storage_and_logging.md` and `docs/07_configuration.md` | INFO | No change needed |
| I-02 | INFO | Input frequency range not documented; power factor/frequency not represented in the model | ENGINEERING GAP | Recorded as a design input in `docs/10` |
| I-03 | INFO | Energy source of record (metering IC versus firmware) undecided | ENGINEERING GAP | Recorded in `docs/10` section 8 |
| I-04 | INFO | 0 CRITICAL findings; no production defect found | INFO | None |

## 27. Fixes made

No production code changed: the phase's `git diff --stat` touches
documentation, `README.md` and two test files only - `src/` is untouched. All
fixes are documentation or test corrections:

| Fix | Files |
| --- | --- |
| `A-30` recorded; assumption summary, blocking map and revision history updated | `docs/11_assumptions.md` |
| Hardware reference restructured: candidates with datasheet evidence, unselected function blocks, safety/power/measurement inputs | `docs/10_hardware_reference.md` |
| Section 6 rewritten as the digital-versus-physical split; boundary notes on `PR-CONTROL-005` and `PR-STORAGE-003`; audit row and links | `docs/02_product_requirements.md` |
| Stale implementation-status and phase references corrected | `docs/05_communication_architecture.md`, `docs/01_system_architecture.md`, `docs/03_data_model.md`, `docs/06_storage_and_logging.md` |
| Fault-set reporting direction recorded (not implemented) | `docs/12_engineering_decisions.md` (`D-044`) |
| Boundary pointer to the audit added | `docs/09_digital_prototype_scope.md`, `docs/14_system_validation.md` |
| Test-quality corrections | `tests/test_configuration.py`, `tests/test_post_merge.py` |
| This report | `docs/15_engineering_audit.md` |

## 28. Remaining blockers

1. `A-30`: safety class, protective earth, isolation boundary - blocks
   schematic capture and PCB layout.
2. Hardware inputs in `docs/10` sections 4 to 8 - block the PCB design.
3. `D-044` (`Proposed`) - blocks the firmware wire contract for fault
   reporting.
4. Site/product policies (`A-07`, `A-08`, `A-09`, `A-10`, `A-29`, `A-11`,
   `A-12`) - block firmware defaults, not the architecture.
5. Commissioning/replacement requirement - blocks nothing digital, but must be
   scoped before field deployment.

None of these is a HOLD condition: they are partner, hardware or product
inputs, not architectural defects.

## 29. Required inputs for the next phase

For Minewing/hardware engineering: the safety-class decision and its creepage
requirements; the power-tree budget including cellular peaks; the relay/LED
inrush data; the measurement chain and calibration decision; storage medium and
partitioning; RTC backup circuit; the RS-485 and Ethernet/cellular physical
design; the enclosure/thermal/mechanical concept; exact part selections.

For the project/product owner: the target market and certification path;
site operating policy (out-of-window behaviour, schedules, retention,
storage-full); fault severity scale and clear policy; acceptance of `D-044`;
and the commissioning/replacement scope decision.

For the prototype build: the physical measurements listed in section 24.

## 30. Final recommendation

Proceed to preliminary engineering with the architecture frozen as it stands.
Start with the safety-class and isolation decision (`A-30`) and the power and
measurement chains, because they determine the PCB; preliminary enclosure CAD
can start in parallel. Keep every claim bounded exactly as
[09_digital_prototype_scope.md](09_digital_prototype_scope.md) and section 24
state: the digital prototype is proven digitally, and nothing in it is a
physical, certification or production-readiness claim.

## Related documents

- [02_product_requirements.md](02_product_requirements.md)
- [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
- [10_hardware_reference.md](10_hardware_reference.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
- [13_integration_validation.md](13_integration_validation.md)
- [14_system_validation.md](14_system_validation.md)
- [requirements_traceability.md](requirements_traceability.md)
- [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)
