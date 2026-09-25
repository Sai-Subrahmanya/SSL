# Demo

## 1. Purpose

This directory holds **demonstration material** for Smart Street Light V1.

Demonstrations exist to show modelled behaviour in the digital prototype.
They are not evidence of physical performance and must respect the claim
discipline defined in [../09_digital_prototype_scope.md](../09_digital_prototype_scope.md).

---

## 2. Claim discipline for demonstrations

| Permitted | Prohibited |
| --- | --- |
| "digitally validated behaviour" | "safety validated" |
| "modelled behaviour verified" | "certified" / "compliant" |
| "simulated fault injection" | "EMC proven" |
| "simulated measurement values" | "metering-grade accuracy" |
| "simulated recovery behaviour" | "field proven" / "production ready" |

Every demonstration must state that it shows **simulated** behaviour and that
physical validation (mains safety, EMC, thermal, enclosure, RF,
certification) is out of scope.

---

## 3. Planned demonstrations

Demonstrations are produced only after the corresponding phase is
implemented. No demonstration exists yet.

| Demo | Depends on phase | Status |
| --- | --- | --- |
| D-01 Lamp node operating modes | Phase 3 | Not started |
| D-02 Measurement handling and sensor validity | Phase 4 | Not started |
| D-03 Expected-versus-actual diagnostics | Phase 5 | Not started |
| D-04 Fault lifecycle and latching | Phase 6 | Not started |
| D-05 Event and measurement logging | Phase 7 | Not started |
| D-06 Storage commit, corruption and power-loss recovery | Phase 8 | Not started |
| D-07 RS-485 protocol behaviour | Phase 9 | Not started |
| D-08 Group controller polling and aggregation | Phase 10 | Not started |
| D-09 Communication loss and recovery | Phase 11 | Not started |
| D-10 Configuration distribution and audit | Phase 12 | Not started |
| D-11 Multi-node group and failure containment | Phase 13 | Not started |
| D-12 Deterministic fault injection matrix | Phase 14 | Not started |
| D-13 Master control center data layer | Phase 15 | Not started |
| D-14 Full integration | Phase 16 | Not started |

---

## 4. Demonstration record structure

```text
DEMO-<NNN>
Title
Phase
Requirements demonstrated
Scenario
Steps
Observed behaviour
Evidence location
Claim statement (simulated behaviour only)
```

---

## 5. Current state

| Item | Status |
| --- | --- |
| Demonstrations produced | 0 |
| Simulation source code | Not started (Phase 0 is documentation only) |

---

## 6. Related documents

- [../00_project_overview.md](../00_project_overview.md)
- [../09_digital_prototype_scope.md](../09_digital_prototype_scope.md)
- [../08_testing_strategy.md](../08_testing_strategy.md)
- [../requirements_traceability.md](../requirements_traceability.md)
