# 10 - Hardware Reference

## 1. Document purpose

This document records **hardware candidates** for Smart Street Light V1 and
the **engineering inputs that must be closed before schematic capture and PCB
layout**.

> **These are engineering candidates, not production-frozen selections.**
>
> No software shall depend directly on these components at this stage. Any
> future selection requires a decision record in
> [12_engineering_decisions.md](12_engineering_decisions.md) and may change
> the architecture, requirements or assumptions.

Sections 2 and 3 list the candidates that already exist in the project
direction. Sections 4 to 8 list what is **not** decided yet. Nothing in those
sections is a selection, a bill of materials or a compliance statement; where a
datasheet figure is quoted it is marked as datasheet evidence and is only used
to show that a candidate is plausible for the intended function.

---

## 2. Lamp Node candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32G474RE | Candidate MCU for the lamp node. |
| Measurement front end | ADE7953 | Candidate for engineering **monitoring**, not billing-grade metering (`PR-MEASURE-005`). Its accuracy, input range and calibration are hardware items (section 8). |
| Ambient light sensor | OPT3001-Q1 | Candidate light-level sensor. Placement, window, saturation and stray light from the luminaire are hardware inputs (section 6). |
| Real-time clock | RV-3028-C7 | Candidate RTC for local timekeeping. Backup retention is unproven (`A-26`). |
| External storage | S25FL128L (16 MB, SPI NOR) | Candidate record storage. Capacity, endurance and partitioning are not decided (`A-16`). |
| Digital isolator | ISOW7741 | Candidate isolation for a digital interface (for example the metering front-end SPI). Datasheet evidence: quad-channel isolator with an integrated isolated DC-DC of up to about 0.55 W - the isolated-side load must fit that budget. |
| Isolated RS-485 transceiver | ISOW1412 | Candidate field-bus interface. Datasheet evidence: isolated RS-485/RS-422 transceiver with integrated isolated DC-DC, 500 kbps, 1/8 unit load, failsafe on an open/short/idle bus. This is the RS-485 interface candidate, not a generic digital isolator. |
| Relay family | Omron G5RL family | Candidate switching element. Contact rating, inrush capability and endurance are **not established** (section 6); the exact suffix must be fixed against the real lamp load. |
| Isolated power supply | Mean Well IRM-10-5 | Candidate auxiliary supply. Distributor data: 85-305 VAC input, 5 V / 2 A, wide-temperature encapsulated module. The official datasheet and its isolation attributes must be confirmed as part of the safety decision (`A-30`). |
| Voltage regulator | TLV767 | Candidate linear regulator for the 3.3 V rail. Its dissipation follows from the 3.3 V load and must close within the thermal budget (section 7). |

## 3. Group Controller candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32H563RG | Candidate MCU for the group controller. |
| Ethernet PHY | LAN8742Ai | Candidate wired upstream connectivity. Needs magnetics, connector, clocking and ESD protection (section 4). |
| Cellular module | Quectel EG915U-CN / regional family | Candidate upstream connectivity. Datasheet evidence: 3.3-4.3 V supply (typ. 3.8 V); the module's hardware design guide requires a supply able to deliver at least 2 A (LTE only) and 3 A (LTE plus GSM) peak, with VBAT_RF rated up to 2.5 A, and recommends a VBAT TVS. Regional variant is undecided (`A-15`). |
| Isolated power supply | Mean Well IRM-20-12 | Candidate auxiliary supply. Distributor data: 85-305 VAC input, 12 V / about 1.8 A. Official datasheet attributes (including its isolation class) must be confirmed before they are used in a safety argument (`A-30`). |
| DC-DC converter | TPS543620 | Candidate power conversion for the low-voltage rails; its suitability for the cellular peak current is a power-tree input (section 7). |

---

## 4. Required function blocks not yet selected

The architecture needs these functions. No candidate has been chosen, and no
part number is implied; each must be selected with the hardware engineer.

| Subsystem | Function block | Status |
| --- | --- | --- |
| Lamp Node | Current transformer (or equivalent current sensor) with burden and protection | Not selected |
| Lamp Node | Mains voltage sensing (divider / isolation arrangement) | Not selected |
| Lamp Node | Relay coil driver (transistor/MOSFET, gate or base network, flyback clamp) | Not selected |
| Lamp Node | Switching feedback sensing (`A-18`: switched-output voltage sensing, auxiliary contact or equivalent) | Not selected |
| Lamp Node | Input protection (fuse, surge/MOV, EMI filter, inrush limiting) | Not selected |
| Lamp Node | RTC backup storage (supercapacitor/battery) and its charging circuit | Not selected |
| Lamp Node | SWD/service connector and its protection | Not selected |
| Lamp Node | Watchdog/supervisor (internal or external) and brown-out behaviour | Not selected |
| Lamp Node | Temperature sensing (if a thermal fault category is required) | Not selected |
| Group Controller | RS-485 transceiver, isolation, termination and biasing network | Not selected |
| Group Controller | Record storage medium for the buffer (internal flash, external memory or other) | Not selected (`A-28`) |
| Group Controller | Real-time clock and backup | Not selected |
| Group Controller | Ethernet magnetics, connector and ESD protection | Not selected |
| Group Controller | Cellular SIM/eSIM, antenna connector/keep-out and RF matching | Not selected |
| Group Controller | Cellular supply rail (bulk capacitance, peak-current path, VBAT protection) | Not selected |
| Group Controller | Service/debug connector and its protection | Not selected |
| Both | Mechanical: enclosure, mounting, cable entry, thermal path, IP concept | Not selected (section 6) |

---

## 5. Electrical targets (design targets, not certification)

| Target | Value | Status |
| --- | --- | --- |
| Controller input voltage range | 90-305 VAC | Engineering design target (`A-03`) |
| Nominal V1 switched lamp output | 230 VAC | Engineering design target (`A-02`) |
| Supply configuration | Single-phase, line-to-neutral | Engineering design target (`A-04`) |
| Input frequency range | **Not documented** | Design input; the selected AC/DC module's datasheet value becomes the product's documented range. It is not yet recorded and no value is invented here. |
| Initial target markets | India and China | Commercial/engineering context |
| International adaptability | Desired | Direction, not a specification (`D-025`) |

These are **engineering design targets**. They are not compliance statements
and imply no certification.

---

## 6. Mains, safety and mechanical inputs required before schematic capture

The product-safety architecture is **not decided** (`A-30`). These inputs must
be closed with a qualified hardware/safety engineer and the enclosure concept;
several of them gate PCB layout. Nothing here is a compliance claim.

| Input | Why it is needed | Depends on |
| --- | --- | --- |
| Safety class: Class I (protective earth) or Class II (double insulated) | Sets the insulation coordination, the earth path and the connector requirements | Enclosure/installation concept (`A-30`) |
| Protective-earth treatment (if Class I): terminal, bonding, earthing of any exposed metal | Required for the safety concept and layout | Installation environment |
| Isolation boundary and its rated voltage (mains side to SELV side) | Defines what is isolated: field bus, service interface, sensor interface, metering interface | Safety class, `A-30` |
| Creepage/clearance table (working voltage, overvoltage category, pollution degree, altitude) | Directly sizes the layout | Safety class and installation environment |
| Input protection: fuse/over-current, surge (MOV/TVS), EMI filtering, inrush limiting | Required for the AC input stage and for certification later | Target market, certification path |
| Relay contact rating vs the real lamp load: continuous current, LED-driver inrush (peak and duration), endurance cycles, switching policy | The relay candidate's suitability cannot be established without the load data | The external luminaire/LED driver (out of product scope, but its data is an input) |
| Switching-path fail state and its interaction with reset/watchdog/brown-out (`PR-CONTROL-005`) | Determines post-reset behaviour on hardware | Relay driver design |
| Accessible surfaces and connectors: RS-485 field bus, service interface, sensors | Determines isolation, surge/ESD and touch-safety requirements | Safety class, enclosure |
| Thermal: relay coil, converter/isolator losses, regulator dissipation, enclosure ambient | Sizes the thermal path and the enclosure | All of the above; module temperature ratings are the module's, not the product's |
| Mechanical: mounting, dimensions, cable entry, sensor window, antenna keep-out, service access, tamper | Derived from the electronics above, not invented independently | Enclosure concept, site survey |
| Enclosure/IP requirement and environmental exposure | Must follow the installation location | Site policy, target market |
| Input frequency range and installation practice | Documented design input of the AC/DC stage | Selected module datasheet, target market |

**Mechanical requirements follow from the electronics**: the enclosure must
provide the creepage distance the safety class demands, keep the mains side
separated from the low-voltage side, expose the light sensor to ambient light
(not to the luminaire), give the cellular antenna its keep-out and provide a
service opening for the SWD/debug access - none of these may be invented
independently of the electrical design.

---

## 7. Power architecture inputs (to be closed)

The intended hierarchy exists as a direction; no rail budget has been computed.
The numbers below are the **inputs** that must be established, not results.

| Node | Chain | Inputs to close |
| --- | --- | --- |
| Lamp Node | AC input -> protection -> isolated AC/DC (candidate IRM-10-5, 5 V) -> 3.3 V regulator (candidate TLV767) -> loads: MCU, metering front end, isolators, RS-485, storage, RTC, light sensor, relay coil driver | Load budget per rail; relay coil current and its duty; dissipative loss in the 5 V -> 3.3 V linear regulator; startup/inrush behaviour; brown-out and reset thresholds; decoupling and resetting of the switching path |
| Group Controller | AC input -> protection -> isolated AC/DC (candidate IRM-20-12, 12 V) -> DC-DC (candidate TPS543620) -> 3.3 V/5 V rails, cellular rail (3.8 V typ.) | Cellular peak current (datasheet guidance: at least 2 A for LTE, 3 A for LTE plus GSM), bulk capacitance and VBAT protection, Ethernet PHY and PHY clock supply, converter thermal load, rail sequencing |

Open checks: transient behaviour at the cellular transmit bursts, brown-out
behaviour of both nodes, and whether the candidate converters deliver the peak
currents with margin. No value is frozen in this document.

---

## 8. Measurement-chain inputs (to be closed)

The digital model carries voltage, current, power, energy and light level as
engineering monitoring values (`PR-MEASURE-005`). Before hardware, the
following must be established, and none of them is a metering-accuracy claim:

- current sensor type and ratio, burden resistor, and its protection;
- metering front-end input range, isolation of its interface and its supply;
- mains voltage sensing arrangement and divider tolerance;
- energy source of record: whether energy is accumulated by the metering IC
  (typical) or integrated by firmware from sampled power - the digital model
  integrates sampled power, and this choice also determines where calibration
  lives (`PR-STORAGE-007`);
- calibration procedure and coefficients, and where they are stored
  (assuming separately from records, `PR-STORAGE-007`);
- phase relationship and power-factor treatment (the model carries neither);
- light-sensor placement, window, field of view, saturation and stray light;
- sensor-validity and plausibility rules against the real measurement noise.

---

## 9. Component status summary

| Item | Status |
| --- | --- |
| Components listed in sections 2 and 3 | **Engineering candidates** |
| Function blocks in section 4 | **Not selected** |
| Production-frozen selection | **None** |
| Software dependency on specific components | **Not permitted at this stage** |
| Schematic / PCB design | Not started |
| Component qualification | Not started |
| Safety class and isolation boundary (`A-30`) | **Undecided** - gates schematic capture |

---

## 10. Consequences of the candidate status

1. The digital prototype shall not hardcode component-specific behaviour.
2. Hardware interfaces shall be modelled abstractly (measurement source,
   switching element, time source, storage medium).
3. A change of candidate component shall not invalidate the requirements or
   the digital prototype unless a requirement depends on it.
4. Any component change requires a new decision record.

---

## 11. Physical validation items deferred to hardware phases

| Item | Deferred to |
| --- | --- |
| Mains electrical safety | Physical prototype validation |
| PCB safety and layout | Physical design |
| Isolation, creepage, clearance | Physical design |
| EMC, surge, ESD | Physical test |
| Relay lifetime and LED inrush | Physical endurance/measurement test |
| Thermal performance | Physical test |
| Enclosure and IP rating | Physical design and test |
| Actual RF performance | Physical test |
| Certification | Accredited testing |

---

## 12. Related documents

- [01_system_architecture.md](01_system_architecture.md)
- [05_communication_architecture.md](05_communication_architecture.md)
- [06_storage_and_logging.md](06_storage_and_logging.md)
- [09_digital_prototype_scope.md](09_digital_prototype_scope.md)
- [11_assumptions.md](11_assumptions.md)
- [12_engineering_decisions.md](12_engineering_decisions.md)
- [15_engineering_audit.md](15_engineering_audit.md)
