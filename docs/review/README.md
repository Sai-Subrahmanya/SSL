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
Conclusion (approved / approved with actions / rejected)
```

---

## 4. Review log

| Review ID | Date | Scope | Status |
| --- | --- | --- | --- |
| REVIEW-000 | 2026-09-25 | Phase 0 - repository foundation, requirements baseline, architecture baseline, assumptions register, decision log, traceability structure | **Pending - not yet performed** |

---

## 5. Current state

No independent review has been performed yet. The Phase 0 baseline is
submitted for review; the outcome will be recorded here as `REVIEW-000`.

Until that review is recorded, the requirements in
[../02_product_requirements.md](../02_product_requirements.md) remain
`Proposed` and no implementation phase may begin.

---

## 6. Related documents

- [../00_project_overview.md](../00_project_overview.md)
- [../02_product_requirements.md](../02_product_requirements.md)
- [../08_testing_strategy.md](../08_testing_strategy.md)
- [../11_assumptions.md](../11_assumptions.md)
- [../12_engineering_decisions.md](../12_engineering_decisions.md)
- [../requirements_traceability.md](../requirements_traceability.md)
