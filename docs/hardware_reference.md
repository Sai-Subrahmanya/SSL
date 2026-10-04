# Hardware Reference

## 1. Purpose

This document records the **hardware candidates** for Smart Street Light V1
and the **engineering inputs that must be closed before schematic capture and
PCB layout**.

> **These are engineering candidates, not production-frozen selections.**
>
> No software depends on a specific component, and any future selection
> requires a decision record and may change the architecture, the requirements
> or the open items listed in [validation.md](validation.md) section 6.

Sections 2 and 3 list the candidates. Sections 4 to 8 list what is **not**
decided yet. Nothing in those sections is a selection, a bill of materials or a
compliance statement; datasheet figures are quoted only to show that a
candidate is plausible for the intended function.

## 2. Lamp Node candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32G474RE | Candidate MCU for the lamp node. |
| Measurement front end | ADE7953 | Candidate for engineering **monitoring**, not billing-grade metering. Accuracy, input range and calibration are hardware items (section 8). |
| Ambient light sensor | OPT3001-Q1 | Candidate light-level sensor. Placement, window, saturation and stray light from the luminaire are hardware inputs (section 6). |
| Real-time clock | RV-3028-C7 | Candidate RTC for local timekeeping. Backup retention is unproven (open item A-26). |
| External storage | S25FL128L (16 MB, SPI NOR) | Candidate record storage. Capacity, endurance and partitioning are not decided (A-16). |
| Digital isolator | ISOW7741 | Candidate isolation for a digital interface (for example the metering front-end SPI). Datasheet evidence: quad-channel isolator with an integrated isolated DC-DC of up to about 0.55 W — the isolated-side load must fit that budget. |
| Isolated RS-485 transceiver | ISOW1412 | Candidate field-bus interface. Datasheet evidence: isolated RS-485/RS-422 transceiver with integrated isolated DC-DC, 500 kbps, 1/8 unit load, failsafe on an open, shorted or idle bus. |
| Relay family | Omron G5RL family | Candidate switching element. Contact rating, inrush capability and endurance are **not established** (section 6). |
| Isolated power supply | Mean Well IRM-10-5 | Candidate auxiliary supply. Distributor data: 85–305 VAC input, 5 V / 2 A, wide-temperature encapsulated module. The official datasheet and its isolation attributes must be confirmed as part of the safety decision (A-30). |
| Voltage regulator | TLV767 | Candidate linear regulator for the 3.3 V rail. Dissipation follows from the 3.3 V load and must close within the thermal budget (section 7). |

## 3. Group Controller candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32H563RG | Candidate MCU for the group controller. |
| Ethernet PHY | LAN8742Ai | Candidate wired upstream connectivity. Needs magnetics, connector, clocking and ESD protection (section 4). |
| Cellular module | Quectel EG915U-CN / regional family | Candidate upstream connectivity. Datasheet evidence: 3.3–4.3 V supply (typ. 3.8 V); the module's hardware design guide requires a supply able to deliver at least 2 A (LTE only) and 3 A (LTE plus GSM) peak, with the RF rail rated up to 2.5 A, and recommends a VBAT TVS. The regional variant is undecided (A-15). |
| Isolated power supply | Mean Well IRM-20-12 | Candidate auxiliary supply. Distributor data: 85–305 VAC input, 12 V / about 1.8 A. Official datasheet attributes, including isolation class, must be confirmed before they are used in a safety argument (A-30). |
| DC-DC converter | TPS543620 | Candidate power conversion for the low-voltage rails; its suitability for the cellular peak current is a power-tree input (section 7). |

## 4. Required function blocks not yet selected

These functions are needed by the architecture. No candidate has been chosen
and no part number is implied.

| Subsystem | Function block |
| --- | --- |
| Lamp Node | Current transformer (or equivalent current sensor) with burden and protection |
| Lamp Node | Mains voltage sensing (divider / isolation arrangement) |
| Lamp Node | Relay coil driver (transistor or MOSFET, gate/base network, flyback clamp) |
| Lamp Node | Switching-feedback sensing (A-18: sensed switched output, auxiliary contact or equivalent) |
| Lamp Node | Input protection (fuse, surge/MOV, EMI filter, inrush limiting) |
| Lamp Node | RTC backup storage (supercapacitor or battery) and its charging circuit |
| Lamp Node | SWD/service connector and its protection |
| Lamp Node | Watchdog/supervisor (internal or external) and brown-out behaviour |
| Lamp Node | Temperature sensing, if a thermal fault category is required |
| Group Controller | RS-485 transceiver, isolation, termination and biasing network; physical-layer parameters (baud rate — 9.6 or 19.2 kbps candidates, A-05 — UART framing, cable type and protection) |
| Group Controller | Record storage medium for the buffer (internal flash, external memory or other) (A-28) |
| Group Controller | Real-time clock and its backup |
| Group Controller | Ethernet magnetics, connector and ESD protection |
| Group Controller | Cellular SIM/eSIM, antenna connector or keep-out, RF matching |
| Group Controller | Cellular supply rail: bulk capacitance, peak-current path, VBAT protection |
| Group Controller | Service/debug connector and its protection |
| Both | Mechanical: enclosure, mounting, cable entry, thermal path, IP concept |

## 5. Electrical targets

| Target | Value | Status |
| --- | --- | --- |
| Controller input voltage range | 90–305 VAC | Engineering design target (A-03) |
| Nominal switched lamp output | 230 VAC | Engineering design target (A-02) |
| Supply configuration | Single-phase, line-to-neutral | Engineering design target (A-04) |
| Input frequency range | **Not documented** | Design input; the selected AC/DC module's datasheet value becomes the product's documented range. |
| Initial target markets | India and China | Commercial/engineering context |
| International adaptability | Desired | Direction, not a specification (D-025) |

These are engineering design targets. They are not compliance statements and
imply no certification.

## 6. Inputs required before schematic capture

The product-safety architecture is **not decided** (A-30). These inputs must be
closed with a qualified hardware/safety engineer and the enclosure concept;
several of them gate PCB layout. Nothing here is a compliance claim.

| Input | Why it is needed | Depends on |
| --- | --- | --- |
| Safety class: Class I (protective earth) or Class II (double insulated) | Sets the insulation coordination, the earth path and the connector requirements | Enclosure and installation concept (A-30) |
| Protective-earth treatment, if Class I: terminal, bonding, earthing of exposed metal | Required for the safety concept and layout | Installation environment |
| Isolation boundary and its rated voltage (mains side to SELV side) | Defines what is isolated: field bus, service interface, sensor and metering interfaces | Safety class (A-30) |
| Creepage/clearance table (working voltage, overvoltage category, pollution degree, altitude) | Directly sizes the layout | Safety class and installation environment |
| Input protection: fuse/over-current, surge (MOV/TVS), EMI filtering, inrush limiting | Required for the AC input stage and for later certification | Target market, certification path |
| Relay contact rating versus the real lamp load: continuous current, LED-driver inrush (peak and duration), endurance cycles, switching policy | The relay candidate's suitability cannot be established without the load data | The external luminaire and its LED driver |
| Switching-path fail state and its interaction with reset, watchdog and brown-out | Determines post-reset behaviour on hardware | Relay driver design |
| Accessible surfaces and connectors: field bus, service interface, sensors | Determines isolation, surge/ESD and touch-safety requirements | Safety class, enclosure |
| Thermal: relay coil, converter and isolator losses, regulator dissipation, enclosure ambient | Sizes the thermal path and the enclosure | All of the above; module temperature ratings are the module's, not the product's |
| Mechanical: mounting, dimensions, cable entry, sensor window, antenna keep-out, service access, tamper | Derived from the electronics above, not invented independently | Enclosure concept, site survey |
| Enclosure/IP requirement and environmental exposure | Follows from the installation location | Site policy, target market |
| Input frequency range and installation practice | Documented design input of the AC/DC stage | Selected module datasheet, target market |

Mechanical requirements follow from the electronics: the enclosure must provide
the creepage distance the safety class demands, keep the mains side separated
from the low-voltage side, expose the light sensor to ambient light rather than
to the luminaire's own output, give the cellular antenna its keep-out and its
path to the outside, and provide service access for the debug interface.

## 7. Power architecture inputs

The intended hierarchy exists as a direction; no rail budget has been computed.
The entries below are the inputs to establish, not results.

| Node | Chain | Inputs to close |
| --- | --- | --- |
| Lamp Node | AC input → protection → isolated AC/DC (candidate 5 V) → 3.3 V regulator → loads: MCU, metering front end, isolators, RS-485, storage, RTC, light sensor, relay coil driver | Load budget per rail; relay coil current and duty; dissipation in the 5 V → 3.3 V linear regulator; startup and inrush; brown-out and reset thresholds; decoupling and switching-path reset behaviour |
| Group Controller | AC input → protection → isolated AC/DC (candidate 12 V) → DC-DC → 3.3 V / 5 V rails, cellular rail (3.8 V typ.) | Cellular peak current (datasheet guidance: at least 2 A for LTE, 3 A for LTE plus GSM); bulk capacitance and VBAT protection; Ethernet PHY and its clock supply; converter thermal load; rail sequencing |

Open checks: behaviour at cellular transmit bursts, brown-out behaviour of both
nodes, and whether the candidate converters deliver the peak currents with
margin. No value is frozen in this document.

## 8. Measurement-chain inputs

The model carries voltage, current, power, energy and light level as
engineering monitoring values. Before hardware, the following must be
established; none of them is a metering-accuracy claim:

* current-sensor type and ratio, burden resistor and its protection;
* metering front-end input range, isolation of its interface, and its supply;
* mains voltage sensing arrangement and divider tolerance;
* energy source of record: whether energy is accumulated by the metering IC or
  integrated by firmware from sampled power — the model integrates sampled
  power, and this choice also decides where calibration lives;
* calibration procedure and coefficients, and where they are stored (assuming
  separately from records);
* phase relationship and power-factor treatment (the model carries neither);
* light-sensor placement, window, field of view, saturation and stray light;
* sensor-validity and plausibility rules against real measurement noise.

## 9. Component status summary

| Item | Status |
| --- | --- |
| Components in sections 2 and 3 | Engineering candidates |
| Function blocks in section 4 | Not selected |
| Production-frozen selection | None |
| Software dependency on specific components | None |
| Schematic / PCB design | Not started |
| Component qualification | Not started |
| Safety class and isolation boundary (A-30) | Undecided — gates schematic capture |

## 10. Validation items deferred to hardware

| Item | Deferred to |
| --- | --- |
| Mains electrical safety | Physical prototype validation |
| PCB safety and layout | Physical design |
| Isolation, creepage and clearance | Physical design |
| EMC, surge and ESD | Physical test |
| Relay lifetime and LED inrush | Physical endurance and measurement |
| Thermal performance | Physical test |
| Enclosure and IP rating | Physical design and test |
| RF performance | Physical test |
| Certification | Accredited testing |
| RTC backup retention and accuracy | Physical measurement |

## 11. Related documents

* [architecture.md](architecture.md) — where these functions sit in the system.
* [validation.md](validation.md) — open engineering items and the digital/physical boundary.
* [design_decisions.md](design_decisions.md) — the decisions that constrain the hardware.
