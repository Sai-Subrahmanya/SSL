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
compliance statement; datasheet figures are quoted as evidence about a
*component* — to show that a candidate is plausible for the intended function,
or to document the part's own published ratings for the safety analysis in
section 6 — and never as a claim about this product.

## 2. Lamp Node candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32G474RE | Candidate MCU for the lamp node. |
| Measurement front end | ADE7953 | Candidate for engineering **monitoring**, not billing-grade metering. Not an isolated device: its conventional configuration is neutral-referenced, so its host interface crosses the mains boundary (section 6.5). Accuracy, input range and calibration are hardware items (section 8). |
| Ambient light sensor | OPT3001-Q1 | Candidate light-level sensor. Placement, window, saturation and stray light from the luminaire are hardware inputs (section 6). |
| Real-time clock | RV-3028-C7 | Candidate RTC for local timekeeping. Backup retention is unproven (open item A-26). |
| External storage | S25FL128L (16 MB, SPI NOR) | Candidate record storage. Capacity, endurance and partitioning are not decided (A-16). |
| Digital isolator | ISOW7741 | Candidate isolation for a digital interface (for example the metering front-end SPI). Datasheet: quad-channel reinforced isolator with an integrated isolated DC-DC of up to about 0.5 W (0.55 W on the automotive variant) — the isolated-side load must fit that budget, and the certification status needs confirmation (section 6.5). |
| Isolated RS-485 transceiver | ISOW1412 | Candidate field-bus interface. Datasheet: reinforced isolated RS-485/RS-422 transceiver (the `B` suffix is the basic-isolation variant) with integrated isolated DC-DC, 500 kbps, 1/8 unit load, failsafe on an open, shorted or idle bus. |
| Relay family | Omron G5RL family | Candidate switching element. Datasheet: 6000 VAC coil-to-contact dielectric strength for 1 minute, 8 mm creepage and clearance, coil-to-contact insulation classified reinforced on the standard sheet — variant dependent (section 6.4). Contact rating, inrush capability and endurance are **not established** (section 6). |
| Isolated power supply | Mean Well IRM-10-5 | Candidate auxiliary supply. Datasheet: 85–305 VAC input, 5 V / 2 A, Class II design with no FG pin, I/P-O/P withstand 4.2 kVac, encapsulated wide-temperature module. Its isolation attributes and the product-level coordination are part of the safety decision (A-30), section 6.5. |
| Voltage regulator | TLV767 | Candidate linear regulator for the 3.3 V rail. Dissipation follows from the 3.3 V load and must close within the thermal budget (section 7). |

## 3. Group Controller candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32H563RG | Candidate MCU for the group controller. |
| Ethernet PHY | LAN8742Ai | Candidate wired upstream connectivity. Needs magnetics, connector, clocking and ESD protection (section 4). |
| Cellular module | Quectel EG915U-CN / regional family | Candidate upstream connectivity. Datasheet evidence: 3.3–4.3 V supply (typ. 3.8 V); the module's hardware design guide requires a supply able to deliver at least 2 A (LTE only) and 3 A (LTE plus GSM) peak, with the RF rail rated up to 2.5 A, and recommends a VBAT TVS. The regional variant is undecided (A-15). |
| Isolated power supply | Mean Well IRM-20-12 | Candidate auxiliary supply. Datasheet: 85–305 VAC input, 12 V / 1.8 A, Class II design with no FG pin, I/P-O/P withstand 4.2 kVac. Its isolation attributes and the product-level coordination are part of the safety decision (A-30), section 6.5. |
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

## 6. Product safety and isolation (A-30)

The product-safety architecture is **not decided** (A-30). This section records
the preliminary engineering analysis of A-30: what the existing architecture
already fixes, what candidate datasheet evidence can already answer, and what
cannot be frozen yet. It is not the safety analysis of a design that does not
exist, and nothing here is a compliance or certification claim.

**How to read these sections.** *(datasheet)* is a manufacturer-published fact
about a component; *(inference)* is engineering reasoning that follows from this
repository's own documents; *(open)* is undecided and must be closed with a
qualified hardware/safety engineer. A component's own approval or isolation
rating is never a statement about this product — the Mean Well datasheets state
this themselves: "the power supply is considered as an independent unit, but the
final equipment still need to re-confirm that the whole system complies" with
the applicable directives *(datasheet, IRM-10/IRM-20 specification, note 5/6)*.

### 6.1 The electrical product boundary

*(inference, from sections 5 and 7 and `D-001`)*

* Both nodes are **mains-connected fixed equipment**: the input stage is a
  90–305 VAC single-phase line-to-neutral design target.
* The lamp node is additionally a **mains switching device**. Its relay contacts
  interrupt the supply of an external luminaire, so mains potential exists at
  the switched-output terminals even though the luminaire itself — lamp, driver,
  optics, luminaire enclosure — is outside the product.
* The metering front end measures mains voltage and load current. The metering
  candidate is not an isolated device, and manufacturer application guidance
  refers it to neutral in the conventional shunt configuration, which makes the
  metering chain a mains-referenced island rather than a low-voltage one unless
  isolated sensing is used (see section 6.5).
* The Group Controller carries the same mains input stage plus three further
  external interfaces: RS-485, Ethernet and cellular RF.
* One further boundary question is **not** settled by the documents: whether the
  node's board sits inside the luminaire's own enclosure (where the accessible
  surfaces and, possibly, the safety class belong to the host luminaire) or in
  its own free-standing enclosure. That choice changes what "accessible
  conductive surface" means for this product *(open)*.

### 6.2 Class I versus Class II: consequences for this product

Both classes protect against electric shock; they place the burden in different
places. The consequences below are engineering reasoning about this architecture
*(inference)*, not a preference for either class.

| Consequence | Class I (basic insulation + protective earth) | Class II (double or reinforced insulation) |
| --- | --- | --- |
| Second means of protection | The protective earth path: all exposed metal is bonded and the installation's PE is relied on | A second layer of insulation everywhere between mains and anything touchable |
| PE requirement | A PE terminal, bonding of exposed metal and a reliable earth path become safety-critical; a broken or absent PE is a single fault that must not create a hazard | No protective earth is used; the equipment must be safe as a two-terminal device. If a PE terminal exists at all it must not carry protection duty |
| Conductive enclosure | Permitted, and normal: bond it | Permitted only if the accessible metal is separated from mains by double/reinforced insulation; an insulating enclosure is the simpler realisation |
| Exposed screws, glands, mounting hardware, connector shells, antenna hardware | All become part of the earth path and must be bonded | Each one must maintain double/reinforced separation from mains; windows, sensor openings and glands count as part of the enclosure |
| Field bus (RS-485) reference | The bus may be earthed at the installation; the bus interface still needs its own isolation decision for other reasons (below) | The bus must stay SELV and separated from mains by the same double/reinforced barrier |
| Surge and EMC return path | PE provides a reference for surge and filter design | No PE reference: input protection is referenced line-to-neutral only, and the EMC/surge strategy must work without an earth |
| Service and debug access | A bonded chassis can reference a service tool; access rules are simpler | A service tool (for example an earthed laptop on a debug header) must not compromise the barrier: the interface needs isolation or tool-restricted access |
| Cost of installation error | A missing or high-impedance PE silently removes protection, so installation instructions and verification matter | Protection does not depend on the installation — its advantage for retrofit work |
| What the layout pays for | Basic insulation distances at the barrier, plus the earth path and its current-carrying capacity | Reinforced distances at the barrier, in every direction, including around the relay, the module, the metering island and any opening |
| Where the decision is constrained | Needs PE to be available and reliable at the installation | Needs the enclosure concept before distances can be fixed |

Two further points follow from the product boundary *(inference)*:

* The classes are properties of **complete equipment**. A Class II
  double-insulated AC/DC module, a reinforced digital isolator or a relay with
  reinforced coil-to-contact insulation does not make this product Class II;
  those parts only make a Class II design *possible*.
* If the node is installed inside the luminaire enclosure, part of the
  assessment is inherited from the host luminaire and the product's own declared
  class may not be the right framing at all *(open)*.

### 6.3 Preliminary isolation boundary

The boundary below follows from the architecture and the candidate list; the
placements marked OPEN are the questions A-30 has to settle.

```text
 +--------------------------------------------------------------------------+
 | MAINS / HAZARDOUS LIVE DOMAIN      single-phase L-N, 90-305 VAC target    |
 |                                                                          |
 |  L --+--[ fuse | MOV/TVS | EMI filter | inrush limit ]                   |
 |  N --+                                                                   |
 |                                                                          |
 |    +----------------------+       +-----------------------------------+  |
 |    | isolated AC/DC       |       | metering island                   |  |
 |    | IRM-10-5 (node)      |       | ADE7953 + shunt / divider         |  |
 |    | IRM-20-12 (GC)       |       | mains / neutral referenced        |  |
 |    | Class II module      |       | (OPEN: island placement)          |  |
 |    +----------+-----------+       +----------------+------------------+  |
 |               |                                    |                     |
 |    G5RL relay: contacts on the mains side, coil driven from the          |
 |    low-voltage side (B); switched terminals go to the external luminaire |
 +---------------|------------------------------------|---------------------+
                 | (A) mains -> SELV                  | (D) metering digital
                 |     provided by the module         |     link: isolation
                 |     (OPEN: product-level           |     REQUIRED if the
                 |      coordination)                 |     island is mains
                 |                                    |     referenced
 +---------------|------------------------------------|---------------------+
 | SELV / LOW-VOLTAGE DOMAIN   (3.3 V / 5 V rails)                          |
 | MCU STM32G474RE (node) / STM32H563RG (GC), S25FL128L, RV-3028-C7,        |
 | TLV767, TPS543620, LAN8742Ai, relay coil driver, RS-485 logic side       |
 | (E) service / debug header: treatment OPEN                               |
 | (F) light sensor: optical window, no galvanic crossing in this sketch    |
 |     (mounting concept OPEN)                                             |
 +----|------------------|-------------------|----------------------------+
      | (C) isolated     | (G) Ethernet      | (H) RF / cellular (GC only)
      |     RS-485       |     magnetics     |     EG915U-CN / regional
      |     ISOW1412     |     NOT SELECTED  |     (variant OPEN, A-15)
      v                  v                   v
 +-----------------+ +------------------+ +-------------------------------+
 | FIELD-BUS       | | ETHERNET         | | RF / ANTENNA DOMAIN           |
 | DOMAIN          | | SEGMENT          | | (external to the enclosure,   |
 | own reference   | | isolated through | |  antenna arrangement OPEN)    |
 | ISOW1412 bus    | | magnetics (OPEN) | |                               |
 | side            | |                  | |                               |
 +-----------------+ +------------------+ +-------------------------------+

 The external luminaire (lamp, driver, optics, enclosure) is outside the product
 boundary; only the switched-output terminals belong to this product.
```

### 6.4 Interface-by-interface status

| Interface | What crosses the boundary | Status |
| --- | --- | --- |
| Mains-side boundary | Where the product's mains terminals are, and whether the node's own supply is tapped upstream of its own relay or shares the switched circuit | **OPEN** — installation arrangement. The upstream-tap question also decides whether the node can lose its own supply when it switches the lamp |
| SELV / low-voltage boundary | Which parts are genuinely SELV: the 3.3 V / 5 V rails, MCU, storage, RTC and light sensor are only SELV if the metering island is separated from them | **OPEN** — depends on the metering placement |
| **(D)** Metering interface (lamp node) | Whether the metering front end is mains-referenced with an isolated host interface, or low-voltage-referenced with isolated sensing | **OPEN** — the metering candidate is not an isolated device and is conventionally neutral-referenced (section 6.5); this placement decides what the SELV domain actually contains |
| Galvanic isolation requirements | What must be isolated rather than merely insulated, and at which working voltage | **OPEN** — needs the declared working voltage, overvoltage category, pollution degree and altitude |
| PE requirement | Whether a protective earth is used at all, and if so its terminal, bonding set and continuity requirement | **OPEN** — follows from the class, the enclosure and the installation |
| Accessible conductive surfaces | The complete set of touchable metal: enclosure, screws, glands, mounting bracket, connector shells, antenna hardware, luminaire mounting interface | **OPEN** — the enclosure is not frozen, so the set is not even enumerable yet |
| **(E)** Service / debug interface | Whether the debug header is exposed, tool-restricted, isolated or bonded | **OPEN** — but it must not breach whichever barrier is chosen |
| **(C)** RS-485 isolation | Safety separation from mains *and* functional separation (ground loop, common-mode over a long outdoor bus) | Partly answered *(datasheet)*: the ISOW1412 reinforced variant is rated for 1000 V RMS / 1500 V PK working voltage, 5000 V RMS UL 1577 isolation, 10 kV PK surge, with at least 8 mm creepage and clearance and altitude up to 5000 m. **OPEN**: the bus-side reference (floating or installation-earthed) and the connector's touch-safety |
| **(F)** Sensor-interface isolation | Whether the light sensor is on the low-voltage rail behind a window, or remotely mounted with a cable crossing a boundary | **OPEN** — mounting concept |
| **(A)** Mains-to-low-voltage isolation | The main barrier, provided on the candidate path by the AC/DC module | Module data confirmed *(datasheet)*: I/P-O/P withstand 4.2 kVac, isolation resistance 100 MΩ / 500 Vdc, leakage current below 0.25 mA at 277 VAC, Class II design with no FG pin. **OPEN**: the product-level insulation coordination, the module's role in the safety argument, and the PCB distances around it |
| **(B)** Mains-to-relay/contact isolation | The relay is a mains-to-low-voltage crossing: contacts on mains, coil driven from the low-voltage rail | Coil-to-contact insulation confirmed *(datasheet)*: 8 mm creepage and 8 mm clearance, 6000 VAC dielectric strength for 1 minute, 10 kV impulse withstand, rated insulation voltage 250 V, pollution degree 3, overvoltage category III, coil-contact insulation classified reinforced on the standard G5RL sheet. **OPEN**: PCB-level distances, the variant actually used (the G5RL-U/-K latching sheets list 6.4 mm clearance, and the 1c variants carry a lower contact rating), and the contact rating against the real luminaire load — the standard sheet lists 250 VAC maximum switching voltage, which the switched output can reach at the top of the 90–305 VAC input span. The insulation values quoted here are catalog values and must be confirmed for the selected model |
| **(G)** Ethernet port (Group Controller) | Network-side isolation and reference | **OPEN** — the magnetics are not selected; the PHY itself provides no isolation |
| **(H)** Cellular RF and SIM (Group Controller) | Antenna arrangement, enclosure opening, SIM access, and whether antenna hardware is touchable | **OPEN** — the regional variant is already open (A-15) |

### 6.5 Candidate datasheet evidence and what it does not establish

Facts below are from manufacturer datasheets and, where stated, the
manufacturer's own application guidance *(datasheet)*. None of them is a
product-level conclusion, and no candidate is production-selected (`D-023`).

| Candidate | What the datasheet establishes | What it does not establish |
| --- | --- | --- |
| Mean Well IRM-10-5, IRM-20-12 | 85–305 VAC / 120–430 VDC input, 47–440 Hz; Class II design with no FG pin; I/P-O/P withstand 4.2 kVac; isolation resistance 100 MΩ at 500 VDC; leakage below 0.25 mA at 277 VAC; operating altitude 2000 m; overvoltage category stated as OVC III under IEC/EN 61558-1/-2-16 (up to 2000 m) and OVC II under IEC/EN/UL 62368-1; safety standards listed for the module as an independent unit | The product's insulation coordination, the product's own overvoltage category and pollution degree, and whether the module's approval can carry any part of a product-level safety argument. Distributor listings for these parts also disagree with the manufacturer (264 VAC and 3 kVac appear in distributor data), so distributor data must not be used for a safety argument |
| TI ISOW1412 | Reinforced variant (the `B` suffix is the basic variant); 5000 V RMS isolation rating per UL 1577; 1000 V RMS / 1500 V PK working voltage; 10 kV PK surge; reinforced per VDE 0884-11 with EN 61010-1 / EN 62368-1 qualifications; at least 8 mm creepage and clearance; altitude to 5000 m | That the assembled bus port is touch-safe, that the enclosure side of the barrier is coordinated, or that the barrier rating suits our declared working voltage and environment |
| TI ISOW7741 | Reinforced quad-channel isolator with an integrated DC-DC converter providing up to about 0.5 W of isolated power (0.55 W on the automotive variant); 1000 V RMS working voltage; 5000 V RMS / 7071 V PK; 20-pin wide-body SOIC | That the metering island fits the isolated power budget, and the current certification status: the datasheet revision consulted lists the safety-related certifications as planned/pending, so certificates must be confirmed with the manufacturer before it enters a safety argument |
| Analog Devices ADE7953 | Single-phase metering IC measuring phase current, neutral current and line voltage; SPI, I²C or UART host interface. The datasheet specifies **no isolation rating**: this is not an isolated device. Manufacturer application guidance for the conventional shunt configuration refers the device ground to neutral, so the host interface necessarily crosses the mains-to-low-voltage boundary | Any isolation. Placing it on the low-voltage rail requires isolated sensing (for example a current transformer plus an isolated voltage path) rather than the conventional shunt-and-divider circuit. Its datasheet's metering-standards support is not a product accuracy or compliance claim (`D-029`, `PR-MEASURE-005`) |
| Omron G5RL family | The coil-to-contact insulation listed in section 6.4, from the manufacturer's datasheets | Which variant is used, the PCB distances around it, its contact rating against the real luminaire load, and whether it can serve as a service disconnector — the open-contact rating is a micro-disconnection only, not an isolating function |
| STM32G474RE, STM32H563RG, OPT3001-Q1, RV-3028-C7, S25FL128L, TPS543620, TLV767 | Low-voltage devices with no isolation function | Anything about the barrier: their requirements follow from the domain they are placed in |
| LAN8742Ai | Ethernet PHY | The network-port barrier: it provides no isolation itself, and the magnetics are not selected (section 4) |
| Quectel EG915U-CN / regional family | Cellular module with its own supply, RF and SIM requirements; the regional variant is open (A-15) | The antenna arrangement and enclosure opening, whether antenna hardware is touchable, and the RF/telecom approval path for the target markets |

### 6.6 Inputs required before schematic capture

These inputs must be closed with a qualified hardware/safety engineer and the
enclosure concept; several of them gate PCB layout. Nothing here is a compliance
claim.

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

### 6.7 Minimum additional inputs to freeze A-30

Until the following are closed, A-30 stays open and no product
creepage/clearance table, class declaration or barrier rating is recorded. These
are physical/product inputs, not engineering preferences.

| Input | Why it gates the safety decision |
| --- | --- |
| Enclosure material and construction | Decides whether touchable surfaces are insulating or conductive, and therefore whether a double-insulated construction is even realisable |
| Installation arrangement | Whether the node sits inside the luminaire, on a mounting bracket or in its own enclosure, and whether its own supply is tapped upstream of its relay |
| Exposed conductive parts | The complete bonded set for Class I, or the set that must maintain reinforced separation for Class II |
| PE availability and reliability | Class I depends on a dependable earth at the installation; Class II must remain safe where there is none |
| Target installation environment | Indoor/outdoor exposure, wet location, pollution degree and condensation drive the whole insulation coordination |
| Overvoltage category, pollution degree and altitude assumptions | Required before any creepage/clearance table can exist; the module's own OVC statement is standard-dependent and altitude-limited (section 6.5) |
| Applicable safety and certification path | The standard set and target markets decide which requirements apply at all; the engineering scope of `D-025` does not fix this |
| Declared rated working voltage and rated impulse withstand | Sizes the barrier across the declared 90–305 VAC span and the mains environment it will see |
| Service-access requirements | Whether a debug header or service connector may be reachable, by whom, and with what tooling |
| Connector accessibility and field-wiring practice | Whether mains, lamp and bus terminals are touchable during installation or maintenance |
| Insulation system | Material group, comparative tracking index and flammability of the enclosure and PCB materials |

**Preliminary engineering direction — inference, not a decision.** The candidate
set is already biased towards a reinforced barrier: a Class II potted AC/DC
module, reinforced digital isolators, and a relay whose coil-to-contact
insulation is classified reinforced. A reinforced barrier is also the
class-agnostic requirement, because a Class II product needs it and a Class I
product can use it (exceeding the basic-insulation demand, with the earth path
added for the metal parts). Designing towards a reinforced-capable barrier
therefore does not pre-empt the class choice, whereas designing basic insulation
first and later finding that only an insulating enclosure is practical would
force a redesign. This is a rework-robustness argument, **not** a safety
conclusion: it does not make the product Class II, does not fix any distance,
and does not close A-30.

## 7. Power architecture inputs

The intended hierarchy exists as a direction; no rail budget has been computed.
The entries below are the inputs to establish, not results.

| Node | Chain | Inputs to close |
| --- | --- | --- |
| Lamp Node | AC input → protection → isolated AC/DC (candidate 5 V) → 3.3 V regulator → loads: MCU, metering front end, isolators, RS-485, storage, RTC, light sensor, relay coil driver | Load budget per rail; relay coil current and duty; dissipation in the 5 V → 3.3 V linear regulator; startup and inrush; brown-out and reset thresholds; decoupling and switching-path reset behaviour |
| Group Controller | AC input → protection → isolated AC/DC (candidate 12 V) → DC-DC → 3.3 V / 5 V rails, cellular rail (3.8 V typ.) | Cellular peak current (datasheet guidance: at least 2 A for LTE, 3 A for LTE plus GSM); bulk capacitance and VBAT protection; Ethernet PHY and its clock supply; converter thermal load; rail sequencing |

The rail assignment above is a direction, not a budget. One placement in it is
coupled to the safety analysis: the metering front end is listed as a low-voltage
rail load, whereas the metering candidate is conventionally referenced to neutral
(section 6.5). Whether the metering island is mains-referenced with an isolated
host interface, or low-voltage-referenced with isolated sensing, is part of A-30
and is not decided here.

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
| Safety class and isolation boundary (A-30) | **Undecided** — preliminary analysis in section 6; still gates schematic capture |

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
