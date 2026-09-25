# 10 - Hardware Reference

## 1. Document purpose

This document records **hardware candidates** for Smart Street Light V1.

> **These are engineering candidates, not production-frozen selections.**
>
> No software shall depend directly on these components at this stage. Any
> future selection requires a decision record in
> [12_engineering_decisions.md](12_engineering_decisions.md) and may change
> the architecture, requirements or assumptions.

---

## 2. Lamp Node candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32G474RE | Candidate MCU for the lamp node. |
| Energy metering / measurement IC | ADE7953 | Candidate measurement front end. |
| Ambient light sensor | OPT3001-Q1 | Candidate light-level sensor. |
| Real-time clock | RV-3028-C7 | Candidate RTC for local timekeeping. |
| External storage | S25FL128L (16 MB, SPI NOR) | Candidate record storage. |
| Digital isolator | ISOW7741 | Candidate isolation for a digital interface. |
| Digital isolator | ISOW1412 | Candidate isolation for a digital interface. |
| Relay family | Omron G5RL family | Candidate switching element. |
| Isolated power supply | Mean Well IRM-10-5 | Candidate auxiliary supply. |
| Voltage regulator | TLV767 | Candidate linear regulator. |

---

## 3. Group Controller candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32H563RG | Candidate MCU for the group controller. |
| Ethernet PHY | LAN8742Ai | Candidate wired upstream connectivity. |
| Cellular module | Quectel EG915U-CN / regional family | Candidate upstream connectivity; regional variant to be selected. |
| Isolated power supply | Mean Well IRM-20-12 | Candidate auxiliary supply. |
| DC-DC converter | TPS543620 | Candidate power conversion. |

---

## 4. Electrical targets (design targets, not certification)

| Target | Value | Status |
| --- | --- | --- |
| Controller input voltage range | 90-305 VAC | Engineering design target |
| Nominal V1 switched lamp output | 230 VAC | Engineering design target |
| Supply configuration | Single-phase, line-to-neutral | Engineering design target |
| Initial target markets | India and China | Commercial/engineering context |
| International adaptability | Desired | Direction, not a specification |

These are **engineering design targets**. They are not compliance statements
and imply no certification.

---

## 5. Component status summary

| Item | Status |
| --- | --- |
| All components listed above | **Engineering candidates** |
| Production-frozen selection | **None** |
| Software dependency on specific components | **Not permitted at this stage** |
| Schematic / PCB design | Not started |
| Component qualification | Not started |

---

## 6. Consequences of the candidate status

1. The digital prototype shall not hardcode component-specific behaviour.
2. Hardware interfaces shall be modelled abstractly (measurement source,
   switching element, time source, storage medium).
3. A change of candidate component shall not invalidate the requirements or
   the digital prototype unless a requirement depends on it.
4. Any component change requires a new decision record.

---

## 7. Physical validation items deferred to hardware phases

| Item | Deferred to |
| --- | --- |
| Mains electrical safety | Physical prototype validation |
| PCB safety and layout | Physical design |
| Isolation, creepage, clearance | Physical design |
| EMC, surge, ESD | Physical test |
| Relay lifetime | Physical endurance test |
| LED inrush behaviour | Physical test |
| Thermal performance | Physical test |
| Enclosure and IP rating | Physical design and test |
| Actual RF performance | Physical test |
| Certification | Accredited testing |

---

## 8. Related documents

- [01_system_architecture.md](01_system_architecture.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
