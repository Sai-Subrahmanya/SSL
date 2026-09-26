# Review

## 1. Purpose

This directory holds **independent technical review records** for Smart
Street Light V1.

The project is developed by an implementation/documentation engineer and
reviewed by a system architect acting as an independent technical reviewer.
Review records are kept here so that review findings, dispositions and
residual risks are traceable.

---

## 2. What belongs here

| Record type | Description |
| --- | --- |
| Phase review | Review of a completed phase against its requirements and traceability. |
| Requirement review | Review of the requirements baseline. |
| Architecture review | Review of the architectural baseline. |
| Decision review | Review of engineering decisions in [../12_engineering_decisions.md](../12_engineering_decisions.md). |
| Assumption review | Review of the assumptions register in [../11_assumptions.md](../11_assumptions.md). |
| Claim review | Review that no over-claiming (certification, safety, metering) exists. |

---

## 3. Review record structure

Each review record uses the following structure:

```text
REVIEW-<NNN>
Date
Scope
Reviewer
Documents reviewed
Findings
  - Finding ID
    Severity
    Description
    Affected requirement(s)
    Disposition
Residual risks
Conclusion (approved / approved with required corrective actions / rejected)
```

---

## 4. Review log

| Review ID | Date | Scope | Status |
| --- | --- | --- | --- |
| REVIEW-000 | 2026-09-25 | Phase 0 - repository foundation, requirements baseline, architecture baseline, assumptions register, decision log, traceability structure | **Approved with required corrective actions** - all 10 actions resolved |

---

## 5. REVIEW-000

```text
REVIEW-000
Date:        2026-09-25
Scope:       Phase 0 engineering foundation (documentation baseline)
Reviewer:    System architect / independent technical reviewer
Documents reviewed:
  README.md
  docs/00_project_overview.md
  docs/01_system_architecture.md
  docs/02_product_requirements.md
  docs/03_data_model.md
  docs/04_fault_management.md
  docs/05_communication_architecture.md
  docs/06_storage_and_logging.md
  docs/07_configuration.md
  docs/08_testing_strategy.md
  docs/09_digital_prototype_scope.md
  docs/10_hardware_reference.md
  docs/11_assumptions.md
  docs/12_engineering_decisions.md
  docs/requirements_traceability.md
```

### 5.1 Conclusion

**APPROVED WITH REQUIRED CORRECTIVE ACTIONS.**

The foundation is structurally sound: the engineering sequence is enforced,
requirements are uniquely identified and traceable, assumptions and decisions
are registered, and the digital/physical boundary is stated. However, the
review identified **semantic defects** in the baseline that would have
propagated into implementation. The foundation is therefore **not** recorded
as simply "approved".

All ten corrective actions below have been implemented and re-audited.

### 5.2 Findings and corrective actions

| Finding | Severity | Description | Corrective action taken | Status |
| --- | --- | --- | --- | --- |
| RC-01 | Major | `RETURN_TO_AUTO` was modelled as a persistent operating mode, conflating configuration with temporary override. | Split into `configured_mode`, `active_override` and `effective_mode`. `RETURN_TO_AUTO` is now an operator command that clears the override. New requirement `PR-CONTROL-007`; decision `D-031`. | Resolved |
| RC-02 | Major | "Relay feedback" coupled the diagnostics to an undecided hardware assumption (relay auxiliary contact). | Replaced with the abstraction `switching_feedback` across requirements, data model, architecture, fault management and diagnostics. New decision `D-032`; assumption `A-18` reworded. | Resolved |
| RC-03 | Major | The RTC section implied that digital modelling validates physical RTC behaviour. | Added an explicit digital-model versus physical-validation boundary for time. New requirement `PR-TIME-005`; decision `D-039`; assumption `A-26`; documented in `09_digital_prototype_scope.md`. | Resolved |
| RC-04 | Major | Storage wording implied that upload confirmation could delete the retained record. | Introduced the record lifecycle `CREATED -> STORED -> PENDING_UPLOAD -> UPLOADED -> CONFIRMED -> RETAINED` and separated the pending upload queue from retained history. New requirement `PR-STORAGE-009`; decision `D-035`. | Resolved |
| RC-05 | Moderate | The retention model lacked a hard minimum retention, authorized deletion and deletion audit event. | Documented the full retention policy model. No numeric period invented (open assumption `A-29`). | Resolved |
| RC-06 | Moderate | No operator roles were defined, so authorization requirements were unanchored. | Defined preliminary roles `VIEWER`, `OPERATOR`, `ENGINEER`, `ADMIN`, `OWNER` with conceptual purpose only. New requirement `PR-SECURITY-006`; decision `D-036`; assumption `A-27`. | Resolved |
| RC-07 | Moderate | The Group Controller had no local storage/buffer capability, so upstream outage behaviour was unspecified. | Added an **abstract** Group Controller local storage/buffer; physical medium deliberately not selected. New requirement `PR-SCALABILITY-005`; decision `D-037`; assumption `A-28`. | Resolved |
| RC-08 | Major | `NOTIFIED` was a fault lifecycle state, so notification progress could not advance without changing fault state. | Fault lifecycle is now `NORMAL -> SUSPECTED -> CONFIRMED -> ACKNOWLEDGED -> UNDER_REPAIR -> VERIFYING -> CLOSED`. Notification state is a separate machine (`NOT_REQUIRED`, `PENDING`, `SENT`, `ACK_PENDING`, `REMINDER_DUE`, `ESCALATED`, `DELIVERY_FAILED`). New requirement `PR-FAULT-013`; decision `D-033`. | Resolved |
| RC-09 | Moderate | `LAMP_LOAD` and `UNDER_CURRENT` were presented as independent root causes. | Separated fault category, diagnostic classification and confirmed physical root cause. New requirement `PR-FAULT-014`; decision `D-034`. | Resolved |
| RC-10 | Minor | `RESET_ENERGY` appeared as a distinct command type, risking protocol inflation. | Documented as a `CONTROL_COMMAND` subtype. New requirement `PR-COMM-010`; decision `D-038`. | Resolved |

### 5.3 Baseline changes resulting from the review

| Item | Before | After |
| --- | --- | --- |
| Requirements | 80 | 88 |
| Assumptions | 25 | 29 |
| Engineering decisions | 30 | 40 |
| Persistent operating modes | 6 (including `RETURN_TO_AUTO`, `FORCE_ON`, `FORCE_OFF`) | 3 persistent automatic modes (`AUTO_SENSOR`, `AUTO_SCHEDULE_SENSOR`, `FIXED_SCHEDULE`); `FORCE_ON`/`FORCE_OFF` are override states and `RETURN_TO_AUTO` is a command |
| Fault lifecycle states | 8 (including `NOTIFIED`) | 7 (notification state is separate) |

### 5.4 Residual risks

| Risk | Disposition |
| --- | --- |
| Physical RTC backup duration is unmeasured (`A-26`). | Accepted as a physical-validation item; excluded from digital claims. |
| Numeric retention period and minimum retention are undecided (`A-29`). | Open; must be resolved before storage sizing is frozen. |
| Storage-full behaviour is undecided (`A-09`). | Open; must be resolved before Phase 8 storage design is frozen. |
| A switching-feedback mechanism is assumed to exist (`A-18`). | Open; highest-impact assumption in the diagnostics area. If no mechanism exists, `PR-DIAG-003` and `PR-DIAG-004` must be revised. |
| Detailed role permission matrix deferred (`A-27`). | Accepted for V1; security design phase item. |

### 5.5 Conditions for proceeding to implementation

1. All ten corrective actions incorporated (done).
2. Requirements baseline re-issued at 88 requirements (done).
3. Traceability matrix regenerated against the corrected requirement set (done).
4. No implementation may begin before this review record exists (satisfied).

All four conditions are satisfied, so the documentation baseline is released
for implementation. Phase 1 (deterministic, hardware-independent core domain
model) has since been implemented in [`src/sslv1/`](../../src/sslv1/) and is
covered by the deterministic suite in [`tests/`](../../tests/). That work is
**digital prototype verification only**; it does not discharge any of the
residual risks in section 5.4, and it does not validate any physical
property.

---

## 6. Review record template

```text
REVIEW-<NNN>
Date
Scope
Reviewer
Documents reviewed
Findings
  - Finding ID
    Severity
    Description
    Affected requirement(s)
    Disposition
Residual risks
Conclusion
```

---

## 7. Related documents

- [../00_project_overview.md](../00_project_overview.md)
- [../02_product_requirements.md](../02_product_requirements.md)
- [../08_testing_strategy.md](../08_testing_strategy.md)
- [../11_assumptions.md](../11_assumptions.md)
- [../12_engineering_decisions.md](../12_engineering_decisions.md)
- [../requirements_traceability.md](../requirements_traceability.md)
