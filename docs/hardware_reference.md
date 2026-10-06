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

Sections 2 and 3 list the candidates. Sections 4 to 9 list what is **not**
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
| Isolated RS-485 transceiver | ISOW1412 | Candidate field-bus interface. Datasheet: reinforced isolated RS-485/RS-422 transceiver (the `B` suffix is the basic-isolation variant) with integrated isolated DC-DC, 500 kbps, 1/8 unit load, failsafe on an open, shorted or idle bus. It is a **full-duplex** part and its supply current is a first-order rail load — see sections 7.3 and 7.7. |
| Relay family | Omron G5RL family | Candidate switching element. Datasheet: 6000 VAC coil-to-contact dielectric strength for 1 minute, 8 mm creepage and clearance, coil-to-contact insulation classified reinforced on the standard sheet — variant dependent (section 6.4). Coil ratings (400 mW; 5 V / 80 mA or 12 V / 33.3 mA, latching variants pulse-driven) and their rail consequences are in section 7.5. Contact rating, inrush capability and endurance are **not established** (section 6). |
| Isolated power supply | Mean Well IRM-10-5 | Candidate auxiliary supply. Datasheet: 85–305 VAC input, 5 V / 2 A, Class II design with no FG pin, I/P-O/P withstand 4.2 kVac, encapsulated wide-temperature module. Its isolation attributes and the product-level coordination are part of the safety decision (A-30), section 6.5. |
| Voltage regulator | TLV767 | Candidate linear regulator for the 3.3 V rail (1 A, 2.5-16 V in, 800 mV typical dropout, thermal shutdown). Its dissipation arithmetic and the thermal verdict are in section 7.5; the load current is not yet established. |

## 3. Group Controller candidates

| Function | Candidate | Notes |
| --- | --- | --- |
| Microcontroller | STM32H563RG | Candidate MCU for the group controller. |
| Ethernet PHY | LAN8742Ai | Candidate wired upstream connectivity. Needs magnetics, connector, clocking and ESD protection (section 4). |
| Cellular module | Quectel EG915U-CN / regional family | Candidate upstream connectivity. Datasheet evidence: 3.3–4.3 V supply (typ. 3.8 V); the module's hardware design guide requires a supply able to deliver at least 2 A (LTE only) and 3 A (LTE plus GSM) peak, with the RF rail rated up to 2.5 A, and recommends a VBAT TVS. The regional variant is undecided (A-15). |
| Isolated power supply | Mean Well IRM-20-12 | Candidate auxiliary supply. Datasheet: 85–305 VAC input, 12 V / 1.8 A, Class II design with no FG pin, I/P-O/P withstand 4.2 kVac. Its isolation attributes and the product-level coordination are part of the safety decision (A-30), section 6.5. |
| DC-DC converter | TPS543620 | Candidate power conversion for the low-voltage rails (4-18 V in, 6 A, 0.5-7 V out, selectable soft start, power-good, adjustable UVLO). Whether one converter or several are used, and how the cellular peak is supported, is a power-tree input (section 7.4). |

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
| **(D)** Metering interface (lamp node) | Whether the metering front end is mains-referenced with an isolated host interface, or low-voltage-referenced with isolated sensing | **OPEN** — the metering candidate is not an isolated device and is conventionally neutral-referenced (section 6.5); this placement decides what the SELV domain actually contains. The two options and their consequences are analysed in section 8.9 |
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

The intended hierarchy exists as a direction; **no rail budget has been
computed**. This section records the preliminary power-tree analysis: the
derived rails, the loads that are actually known, the arithmetic the datasheet
evidence supports, the risks, and the inputs still needed. Nothing here selects
a component, freezes a rail voltage beyond the existing direction, or claims a
power margin. Evidence labels are as in section 6; *(inference)* marks
engineering reasoning, and every value that could not be established from the
repository or a manufacturer datasheet is marked **OPEN** rather than filled in.

### 7.1 Lamp Node power tree

```text
 90-305 VAC single phase L-N
      |
      +-- protection: fuse / MOV-TVS / EMI filter / inrush limit   [not selected]
      |
      +-- isolated AC/DC  candidate IRM-10-5   5 V / 2 A = 10 W
      |        (efficiency 77% typ; setup 600 ms + rise 30 ms;
      |         hold-up 30 ms at 230 VAC; derating below)
      |
      +-- 5 V rail ------------------------------------------------+
               |
               +-- relay coil (5 V G5RL variant, 400 mW, 80 mA)
               |      driven by a low-side driver from the 3.3 V logic;
               |      energised whenever the lamp is ON
               |
               +-- ISOW1412 supply input (VDD, 3-5.5 V)
               |      OPEN: 5 V or 3.3 V rail
               |      datasheet: IDD 123 mA typ / 207 mA max at
               |      VDD = 5 V, VISOOUT = 5 V, 500 kbps loopback;
               |      peak pulse currents up to ~250 mA; PD 1060 mW
               |      max; isolated DC-DC spare output 20 mA
               |
               +-- 3.3 V LDO input  candidate TLV767  (see 7.5)
               |
               +-- support / indicators
               |
      +-- 3.3 V rail (LDO output)
               |
               +-- STM32G474RE          3.3 V   current OPEN
               +-- ADE7953 / metering interface   3.3 V, 7 mA typ / 9 mA max
               |        placement OPEN (A-30): on this rail only if
               |        the metering island is isolated from it
               +-- ISOW7741 / isolation interface
               |        logic side 3.3 V; isolated side limited by its
               |        own converter budget (<= ~0.5 W) and by the
               |        metering decision above
               +-- S25FL128L            3.3 V   15 mA typ read @50 MHz;
               |                                 40 mA typ program/erase;
               |                                 20 uA typ standby
               +-- RV-3028-C7           3.3 V   45 nA typ timekeeping
               +-- OPT3001-Q1           3.3 V   1.8 uA typ active
               +-- relay coil driver    3.3 V   gate/base drive only
               +-- service / debug header        current OPEN

 Relay contacts: mains side, switched output to the external luminaire.
 SELV extent depends on the A-30 metering decision (section 6.4).
```

### 7.2 Group Controller power tree

```text
 90-305 VAC single phase L-N
      |
      +-- protection: fuse / MOV-TVS / EMI filter / inrush limit   [not selected]
      |
      +-- isolated AC/DC  candidate IRM-20-12   12 V / 1.8 A = 21.6 W
      |        (efficiency 84% typ; setup 1000 ms + rise 20 ms;
      |         hold-up 40 ms at 230 VAC; derating below)
      |
      +-- 12 V rail
               |
               +-- DC/DC  candidate TPS543620  (4-18 V in, 6 A, 0.5-7 V out,
               |         soft start 0.5-4 ms, power-good, adjustable UVLO)
               |    OPEN: rail count and topology
               |
               +-- 5 V rail          loads OPEN
               +-- 3.3 V rail        STM32H563RG (current OPEN),
               |                     LAN8742Ai (1.8-3.3 V supply range;
               |                     its own datasheet power-supply
               |                     configuration and supply-current
               |                     tables still to be read -> OPEN),
               |                     Ethernet magnetics/clock OPEN,
               |                     ISOW1412 RS-485 supply input
               |                     (as in 7.1),
               |                     storage (A-28 OPEN), RTC (45 nA class)
               +-- cellular rail ~3.8 V
                    EG915U-CN / regional family (A-15 OPEN)
                    3.3-4.3 V supply, ~3.8 V nominal
                    >= 2 A peak (LTE only), 3 A peak (LTE + GSM)
                    RF rail guidance up to 2.5 A; VBAT TVS recommended
                    bulk capacitance and burst specification OPEN
```

### 7.3 Lamp Node loads

Current values are manufacturer datasheet values *(datasheet)* where a number is
shown; everything else is **OPEN**, with the missing input named.

| Block | Rail | Supply | Typical current | Peak | Continuous / intermittent | Source | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Relay coil (5 V variant) | 5 V | 5 VDC | 80 mA (400 mW, 62.5 Ω) | same | **Continuous while the lamp is ON** (energised all night for a non-latching relay) | G5RL coil ratings | Coil variant OPEN (A-30/§6.4); duty is a design consequence |
| Relay coil (12 V variant) | needs a 12 V rail | 12 VDC | 33.3 mA (400 mW, 360 Ω) | same | as above | G5RL coil ratings | **Not compatible with a 5 V module chain** — included to show why the rail choice and coil choice are coupled |
| Isolated RS-485 (ISOW1412) | 5 V or 3.3 V (OPEN) | 3-5.5 V | 123 mA typ (VDD = 5 V, VISOOUT = 5 V, 500 kbps loopback) | up to ~250 mA pulse; 207 mA max in that table | Continuous when the port is powered | ISOW1412 datasheet | Rail OPEN; duplex/topology check also open (7.6) |
| Isolated DC-DC spare output | isolated side | 3.3 V or 5 V | 20 mA available | — | — | ISOW1412 datasheet | Provision, not a load |
| 3.3 V regulator input | 5 V | — | I(3.3 V) + 1.5 mA ground current at 1 A | — | Continuous | TLV767 datasheet | Reflects the 3.3 V load (OPEN) |
| STM32G474RE | 3.3 V | 1.71-3.6 V | **OPEN** | **OPEN** | Continuous (clock domain) | — | Datasheet IDD table required at the intended clock and temperature: Run-mode IDD versus frequency, typical and maximum, at 25 °C and 85 °C |
| ADE7953 / metering | 3.3 V (only if isolated from the island) | 3.0-3.6 V | 7 mA typ | 9 mA max | Continuous when measuring | ADE7953 datasheet | Rail placement OPEN (A-30, §6.5) |
| ISOW7741 interface | 3.3 V logic side | 1.71-5.5 V | **OPEN** | — | Continuous | — | Depends on the metering decision and on what it actually powers; isolated-side budget ≤ ~0.5 W |
| S25FL128L | 3.3 V | 2.7-3.6 V | 15 mA typ read at 50 MHz; 40 mA typ program/erase | 30 mA typ at 133 MHz read | Intermittent, record-write driven | S25FL128L datasheet | Capacity/retention still open (A-16); current is known |
| RV-3028-C7 | 3.3 V | 1.1-5.5 V | 45 nA typ | 60 nA max | Continuous | RV-3028-C7 datasheet | Backup source/retention open (A-26) |
| OPT3001-Q1 | 3.3 V | 1.6-3.6 V | 1.8 µA typ active | 2.5 µA max | Continuous (or single-shot) | OPT3001-Q1 datasheet | Mounting/window open (§6.4) |
| Relay coil driver | 3.3 V | — | **OPEN** (gate/base drive) | — | Only during transition | — | Driver not selected (section 4) |
| Service/debug header | 3.3 V | — | **OPEN** | — | Only while a tool is attached | — | Access policy open (§6.4); tool power must not be assumed |
| Support, indicators, supervisor | 3.3 V | — | **OPEN** | — | — | — | Not specified yet (section 4) |

### 7.4 Group Controller loads

| Block | Rail | Supply | Typical current | Peak | Continuous / intermittent | Source | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cellular module (EG915U-CN family) | cellular ~3.8 V | 3.3-4.3 V | **OPEN** (idle and connected averages not established) | ≥ 2 A (LTE), 3 A (LTE + GSM) guidance; RF rail guided to 2.5 A | Bursty: high peak, low duty | Module hardware design guide (as recorded in section 3) | Variant OPEN (A-15); bulk capacitance OPEN |
| STM32H563RG | 3.3 V | 1.71-3.6 V | **OPEN** | **OPEN** | Continuous | — | Datasheet IDD table required at 250 MHz, with the LDO or SMPS core-supply option |
| LAN8742Ai | 3.3 V (rail arrangement OPEN) | 1.8-3.3 V | **OPEN** | **OPEN** | Continuous when the link is up | — | Its own datasheet power-supply configuration and supply-current tables must be read; sibling-PHY figures must not be substituted |
| Ethernet magnetics, clock, connector | 3.3 V | — | **OPEN** | — | Continuous | — | Magnetics not selected (section 4) |
| ISOW1412 RS-485 | 5 V or 3.3 V | 3-5.5 V | 123 mA typ (same table as 7.3) | ~250 mA pulse | Continuous | ISOW1412 datasheet | Same open rail question |
| Storage (GC buffer) | 3.3 V | — | **OPEN** | — | Write-burst driven | — | Medium not selected (A-28) |
| RTC and backup | 3.3 V | — | 45 nA class | — | Continuous | (same class as 7.3) | Device not selected |
| SIM / eSIM support | 3.3 V / 1.8 V | — | **OPEN** | **OPEN** | Intermittent | — | Interface arrangement not selected |
| Indicators, support, monitoring | 3.3 V / 5 V | — | **OPEN** | — | — | — | Not specified |
| DC/DC conversion losses | 12 V input | — | Efficiency dependent: TPS543620 is a 6 A synchronous buck; loss curves are in its datasheet | — | Continuous | TPS543620 datasheet | Rail count and operating points OPEN |

### 7.5 What the arithmetic does and does not establish

**Module capacity and its real limits.** The AC/DC candidates are quoted at
their nameplate rating, but both available datasheets derate the *output* with
ambient temperature. This is the single most important constraint in the whole
power tree, because street-light enclosures are hot:

| Module | Nameplate | Efficiency (typ) | Ambient derating from the datasheet |
| --- | --- | --- | --- |
| IRM-10-5 | 10 W (5 V / 2 A) | 77% | 100% load to 50 °C; 75% at 60 °C; 50% at 70 °C; 23% at 80 °C |
| IRM-20-12 | 21.6 W (12 V / 1.8 A) | 84% | 100% load to 40 °C; 90% at 50 °C; 75% at 60 °C; 50% at 70 °C; 20% at 80 °C |

So the lamp node's usable budget is 10 W only in a cool enclosure: at 60 °C it
is about 7.5 W and at 70 °C about 5 W. **An adequate-looking budget at 25 °C is
not evidence of an adequate budget in the product**, and the enclosure ambient
is not yet known *(open)*.

**Startup and hold-up.** The modules need 600 ms (IRM-10) / 1000 ms (IRM-20)
setup plus 20-30 ms rise at full load, with 30 ms (IRM-10) / 40 ms (IRM-20)
hold-up at 230 VAC and only 8 ms at 115 VAC. Cold-start inrush is 20 A at
115 VAC and 40 A at 230 VAC. Consequences *(inference)*: the MCU cannot begin
work for roughly a second after AC is applied; the relay must not chatter during
that window; a brown-out shorter than the hold-up time may not even reset the
system; and the input protection must tolerate the inrush without nuisance
tripping.

**The 5 V rail is not optional.** The G5RL family's standard non-latching coil
ratings are 5, 12 and 24 VDC; the latching `-U` variants list a wider 3 to
24 VDC range *(datasheet)*. A 3.3 V rail therefore does not directly drive the
standard coil, and a 5 V module naturally matches a 5 V coil; a 3 V latching
coil would change the fail-state behaviour as well as the rail, so the pairing
is a decision rather than a given. This matters for the rail budget because the coil is a *continuous*
load whenever the lamp is on: 400 mW, about 8% of the IRM-10-5 nameplate and
even more of its hot-ambient budget. A latching variant changes that load to a
pulse but changes the fail-state behaviour with it — that trade is not made
here *(open)*.

**Regulator dissipation (TLV767).** The candidate is a 1 A linear regulator with
800 mV typical / 1.4 V maximum dropout, 50 µA typical quiescent current, 1.5 mA
ground current at 1 A, internal soft start and thermal shutdown. Its thermal
figure is package dependent — the datasheet's low-thermal-resistance package
(around 52 °C/W) is quoted here, and the smaller package option is materially
worse, so the package choice is part of the thermal case rather than a detail
*(datasheet for the quoted package; the selected package is OPEN)*. From a 5 V
input to a 3.3 V output the dissipation is dominated by the headroom term:

```text
P = (5 V - 3.3 V) x I(3.3 V) + 5 V x I_Q        (I_Q is negligible here)
  = 1.7 V x I(3.3 V)

  100 mA -> 170 mW      250 mA -> 425 mW
  150 mA -> 255 mW      300 mA -> 510 mW
  200 mA -> 340 mW
```

At the datasheet thermal resistance those figures correspond to roughly
9-27 °C of rise at 100-300 mA. With an enclosure ambient of 60-70 °C the
junction stays inside the device's limit but the margin at the top of that range
is thin, and the real figure depends on copper area and airflow *(inference,
with the ambient OPEN)*. Verdict for the TLV767 as a linear regulator: **cannot
be confirmed yet** — it is plausible across the expected 3.3 V load range, it
becomes marginal at high ambient and high load, and a switching pre-regulator
may be preferable on the Group Controller side where the 12 V input makes the
linear option clearly worse. No regulator is replaced here.

**Isolator power is a first-order load, not a detail.** The ISOW1412's own
datasheet shows the integrated isolated DC-DC pulling 123 mA typical (207 mA
maximum in that table) from its supply, with peak pulses up to about 250 mA and
a 1060 mW dissipation limit, providing only 20 mA of spare isolated output
*(datasheet)*. Any argument that treats "the RS-485 chip" as a few milliamps is
wrong by more than an order of magnitude, and whichever rail feeds it (5 V or
3.3 V) must be sized for that *(inference)*. The ISOW7741 adds up to about
0.5 W of isolated-side capability when the metering interface uses it.

**What cannot be concluded.** The budgets cannot be completed from the
repository today, and therefore no margin can be stated. The blocking inputs
are: the MCU run currents (both nodes), the PHY current, the cellular idle and
average currents and its burst specification, the relay coil variant and duty,
the storage medium on the Group Controller, and — most importantly — a
**defined simultaneous-load and temperature case**. Until those exist, any
"10 W is enough" or "21.6 W is enough" statement would be an assumption dressed
as a result. What can be said is only the negative form: nothing found so far
*contradicts* the candidate AC/DC modules, and the two candidates that dominate
the known loads (relay coil, isolated RS-485) leave room at the nameplate
rating while narrowing it at high ambient.

**Bulk capacitance (Group Controller).** The cellular burst requirement cannot
be turned into a capacitance value without inputs that do not exist here. The
relationship is:

```text
C >= I_step x t_burst / V_droop_allowed
```

where `I_step` is the burst current minus what the regulator can supply
smoothly, `t_burst` is the burst duration (not established), and
`V_droop_allowed` follows from the module's 3.3-4.3 V window and the regulator's
transient response *(datasheet formula, open inputs)*. The module vendor's own
hardware design guide is the authoritative source for its recommended VBAT bulk
capacitance and TVS arrangement; that document is an input to obtain, not
something to estimate here *(open)*.

### 7.6 Power architecture risks

| Risk | Evidence | Classification |
| --- | --- | --- |
| AC/DC startup delay and inrush: ~0.6-1.0 s to rail-up, 20-40 A cold-start inrush | Module datasheets | **Confirmed issue** (values are datasheet); the mitigation (protection sizing, no relay activity before rails are good) must be designed |
| Relay coil as a continuous nightly load (400 mW) plus its thermal contribution inside a sealed enclosure | G5RL coil ratings + IRM derating | **Confirmed issue**; the latching-versus-continuous trade is open |
| High-ambient derating of the AC/DC modules erodes the nameplate budget | Module datasheets | **Confirmed issue**; magnitude depends on the unknown enclosure ambient |
| Isolated RS-485 supply current (123 mA typ, pulses to ~250 mA) treated as negligible | ISOW1412 datasheet | **Confirmed issue** if the rail is not sized for it |
| 3.3 V linear regulator dissipation at high ambient | TLV767 datasheet + arithmetic above | **Likely issue** at the upper load/ambient corner; needs the load list and the thermal case |
| Cellular burst current (2-3 A) with insufficient bulk capacitance causing VBAT droop or module reset | Module guidance + absent capacitance inputs | **Likely issue**; cannot be sized yet |
| Cellular burst coinciding with Ethernet traffic, storage writes and RF activity (simultaneous-load case) | Inference from the load list | **Open engineering question** — no defined worst case exists |
| 12 V rail brown-out/droop during bursts reaching the buck converter's limits | TPS543620 4-18 V input, 12 V nominal | **Open engineering question** (plenty of headroom on paper; the source's transient response is unmeasured) |
| Rail sequencing and reset behaviour: MCU reset while the relay is energised | Modules' setup time + MCU BOR/POR/PVD availability | **Open engineering question**; tied to A-08 (restart default) and the relay fail state |
| Watchdog/supervisor and brown-out threshold selection | MCU features exist (POR/PDR/PVD/BOR) | **Open engineering question** — thresholds not chosen, behaviour not specified |
| Storage write current (40 mA class) interacting with the 3.3 V rail and with record traffic | S25FL128L datasheet (as a representative class) | **Likely issue** only as a load-list item; magnitude known, duty unknown (A-16, A-28) |
| RF burst coupling into the supply and the analog/metering path | Inference | **Open engineering question** — PCB layout and decoupling dependent |
| PCB thermal coupling: relay coil, isolator, regulator and module losses in one small enclosure | Inference | **Open engineering question** |
| Enclosure ambient: the derating and thermal cases both hinge on it | §6.5, §7.5 | **Open engineering question** (A-30 coupled) |
| Isolation-related power constraints: the ISOW1412's 20 mA isolated spare limits what else can live on the isolated side | ISOW1412 datasheet | **Confirmed issue** if the isolated side is expected to carry more than the transceiver |
| Service/debug tool power and back-powering through a header | Inference from §6.4 | **Open engineering question** |

### 7.7 Coupling to the A-30 analysis

No part of this power analysis contradicts section 6; several parts depend on it.

| Coupled item | How the power tree depends on it | Status |
| --- | --- | --- |
| Mains-to-LV boundary | Defines which loads sit on the isolated side at all, and hence the 5 V and 3.3 V rail contents | Coupled / OPEN (A-30) |
| Metering island ambiguity | The ADE7953's 7 mA sits on the SELV 3.3 V rail only if the island is isolated from it; otherwise it is a mains-referenced load with its own supply and an isolated host interface | Coupled / OPEN (A-30, §6.5) |
| ISOW7741 power budget | Its isolated-side capability (≤ ~0.5 W) must cover whatever the metering interface needs; if the island is mains-referenced the interface instead needs a barrier | Coupled / OPEN |
| Isolated AC/DC role | The modules provide the SELV source; the product-level coordination (not merely the module rating) is the open part | Consistent with §6.4; product-level part OPEN |
| RS-485 isolation | The isolated port's power (123 mA class from the local rail) and its touch-safety are separate questions from the barrier rating | Consistent; bus reference OPEN (§6.4) |
| Relay coil/contact domains | The coil is a 5 V SELV load; the contacts are mains. This is the (B) crossing in §6.3 and is unchanged by the power analysis | Consistent |
| Service/debug interface | Whether a tool may be attached decides whether the header is a load to budget and whether it can back-power the rail | Coupled / OPEN |
| PE / class status | Class I would add no load to these rails (PE carries fault current, not operating current), but it changes enclosure materials and therefore the thermal path | Class still OPEN (A-30) |

One interface observation surfaced by the load review and recorded here because
it changes both the power and the wiring picture: the ISOW1412 is a
**full-duplex** RS-485/RS-422 transceiver *(datasheet)*, while the modelled field
bus is a linear multi-drop bus in which nodes transmit only when addressed
(`D-004`). A full-duplex part implies a 4-wire arrangement with a continuously
driven pair; a 2-wire half-duplex arrangement would need a different part or
configuration. The repository does not decide the wire count, and this is
recorded as an **open interface question** to close with the physical-layer
inputs, not as a defect in the protocol model.

### 7.8 Inputs to close before schematic capture (power)

Ranked by what blocks what. HIGH items block the power tree itself; MEDIUM items
block component selection; LOW items can follow the first layout.

| # | Input | Priority | Why |
| --- | --- | --- | --- |
| 1 | MCU run current for both nodes (datasheet IDD tables at the intended clock, typical and maximum, at 25 °C and 85 °C) | **HIGH** | Two of the largest active loads are currently unknown |
| 2 | Relay coil variant (5 V non-latching versus latching), its rail and its duty-cycle policy | **HIGH** | 400 mW continuous versus a pulse changes the rail budget, the thermal case and the fail state |
| 3 | Enclosure ambient temperature range and the thermal path | **HIGH** | Both module ratings derate with ambient; without this no margin statement is possible |
| 4 | Simultaneous-load and worst-case operating case (all rails active, cellular burst, storage write, relay transition) | **HIGH** | The definition of "peak" that every budget must close against |
| 5 | Which rail feeds the isolated RS-485 port, and the duplex/topology decision behind it | **HIGH** | 123 mA class load plus a wiring decision |
| 6 | Metering front-end power arrangement (isolated island versus isolated sensing) | **HIGH** | Coupled to A-30 and decides what the SELV rails contain |
| 7 | Cellular module variant and its hardware design guide: burst specification, VBAT bulk capacitance, TVS | **HIGH** | The critical Group Controller load cannot be sized without it |
| 8 | Rail count and topology on the Group Controller (one buck per rail versus buck plus LDOs) | **MEDIUM** | Determines efficiency, sequencing and board area |
| 9 | Regulator choice and the 3.3 V load list (linear versus switching at each point) | **MEDIUM** | Thermal feasibility of the linear option at high ambient |
| 10 | Group Controller storage medium (A-28) and its write-burst current | **MEDIUM** | Load and duty-cycle input |
| 11 | Rail sequencing, power-good usage, brown-out thresholds and the MCU reset behaviour | **MEDIUM** | Prevents relay chatter and false resets; ties to A-08 |
| 12 | Fuse/protection sizing against inrush and derating | **MEDIUM** | The 20-40 A cold-start inrush is a datasheet fact that protection must tolerate |
| 13 | Ethernet PHY current and the magnetics/clock arrangement | **MEDIUM** | Load-list completion for the Group Controller |
| 14 | Service/debug header access policy and whether it can back-power | **MEDIUM** | Coupled to A-30 service access |
| 15 | Watchdog/supervisor arrangement and threshold selection | **LOW** | Follows from the reset/brown-out decisions |
| 16 | Indicator, support and monitoring circuit currents | **LOW** | Completes the budget; small but not zero |
| 17 | PCB thermal coupling and copper-area assumptions for the regulator and isolator | **LOW** | Layout-stage input, not a blocker |
| 18 | RF burst coupling and decoupling strategy | **LOW** | Layout-stage input |

Open checks: behaviour at cellular transmit bursts, brown-out behaviour of both
nodes, and whether the candidate converters deliver the peak currents with
margin. No value is frozen in this document.

## 8. Measurement-chain analysis (A-22)

The model carries voltage, current, power, energy and light level as engineering
monitoring values (`D-029`, `PR-MEASURE-005`). This section reconstructs the
intended hardware chain, assesses the candidate front end against its datasheet,
states what can be calculated today, and records what remains **OPEN** before
schematic capture. Evidence labels are as in section 6; **CALCULATED** marks
arithmetic derived from datasheet values with its inputs stated.

Two figures that are sometimes attributed to this repository are **not** in it:
there is no current-transformer ratio and no maximum lamp-current target
anywhere (the only "3 A" figure in the project is the cellular module's peak),
and there is no worked resistor-divider example with values. Those inputs are
analysed as missing rather than adopted.

### 8.1 Reconstruction: what the repository actually says

The following is inferred directly from sections 2, 4, 6.3-6.5 and 7.7.

* The lamp node measures **per lamp** (`PR-MEASURE-001`): voltage, current,
  power, energy and light level, each nullable and accompanied by sensor
  validity (`PR-MEASURE-004`); energy accumulates monotonically, survives a
  restart and is reset only by an authorized command (`PR-MEASURE-003`).
* The front-end candidate is the **ADE7953**, described as a candidate for
  engineering **monitoring**, never billing-grade metering (`D-029`).
* Current sensing is "current transformer (or equivalent current sensor) with
  burden and protection" — **not selected**. Voltage sensing is "divider /
  isolation arrangement" — **not selected**.
* The device's **domain is not decided**. Section 6.5 records that the ADE7953
  carries no isolation rating, that manufacturer application guidance refers it
  to neutral in the conventional configuration, and that its host interface
  therefore crosses the mains boundary. Section 6.4 (row D) and section 7.7
  keep the metering interface and its power arrangement **OPEN** and coupled to
  A-30. The repository is genuinely ambiguous between a mains-referenced island
  and a low-voltage device with isolated sensing; that ambiguity is preserved
  below because it changes the safety boundary, the power arrangement and the
  component set.
* A third possibility is not excluded by anything in the repository: a different
  front end (no ADE7953). Nothing here selects it; it is listed so the option
  space is not silently narrowed.

```text
 Lamp Node measurement path (derived from sections 4, 6.3 and 7.1)

  MAINS DOMAIN  (A-30: hazardous live, class not decided)
                                                                     |
   L --[ input protection ]--+--------------[ relay ]-- switched L --+-->
                             |                 external luminaire -----> N
                             |                          |
                             |          current path through the lamp
                             |                          |
                             |                          v
                             |         [ current sensor: CT or equivalent ]
                             |           not selected; secondary winding
                             |                          |
                             +--[ voltage sensing: divider / isolation ]
                             |           not selected
                             |                          |
                             |                          v
   +--------------------------------------------------------------+  |
   |  METERING FRONT END -- ADE7953 (candidate)                   |  |
   |  domain UNDECIDED:                                           |  | barrier
   |    option A  mains-referenced island (AGND at N)             |  | position
   |    option B  SELV-side device with isolating sensing         |  | depends
   +--------------------------------------------------------------+  | on the
                             |                                       | option
                             |  host interface: SPI / I2C / UART     |
                             |  (isolation REQUIRED for option A) ---+--> across
                             v
        MCU STM32G474RE  (SELV 3.3 V)
             |
             v
        measurement values -> 15-rule diagnostic chain
        (system_behaviour.md section 3) -> fault engine -> records -> MCC
```

Interaction with the existing system elements: the AC line and neutral are the
measured pair; the CT encircles the lamp conductor; the voltage sensing
references L to N; the ADE7953 is the front end; the MCU consumes its results;
the isolated power supply feeds the SELV domain only; RS-485 isolation is
independent of the metering decision; the external luminaire is the load and an
out-of-product current path; PE and the service/debug interface become
constrained by whichever option is chosen (section 8.9).

### 8.2 ADE7953 assessment against the intended application

The table below is datasheet evidence unless marked otherwise.

| Aspect | Datasheet fact | Consequence for this design |
| --- | --- | --- |
| Supply | 3.3 V ±10%; I_DD 7 mA typical, 9 mA maximum | CALCULATED: 23 mW typical, 30 mW maximum — small on any rail (section 8.10) |
| Measurement channels | Three Σ-Δ ADCs: Current A (phase), Current B (neutral), Voltage channel | Current B is available for a second current path (neutral/tamper); using it is a decision, not a default |
| Current channel A | Fully differential IAP/IAN, ±500 mV maximum differential, ±250 mV single-ended; PGA ×1/2/4/8/16/**22** (×22 on A only); common mode < ±25 mV recommended; 50 MΩ input impedance | Sets the CT burden ceiling (section 8.3) and favours differential drive from a burden resistor |
| Current channel B | Differential IBP/IBN ±500 mV; PGA ×1-16; 540 kΩ | Same sensor class, lower gain range |
| Voltage channel | VP/VN, typically single-ended, ±500 mV with respect to VN; PGA ×1-16; 540 kΩ | Sets the divider ratio target (section 8.4) |
| Reference | Internal 1.2 V on REF, error ±0.9 mV at 25 °C, tempco 10-50 ppm/°C; REF may be overdriven externally | Reference drift is a small but non-zero error term; an external reference is an option, not a requirement |
| Clock | CLKIN 3.58 MHz, crystal ESR 30-200 Ω | An external crystal is part of the BOM and the layout |
| ADC/output rate | 24-bit words at 6.99 kSPS; VRMS full-scale ≈ 9 032 007; full-scale AWATT ≈ 4 862 401 | Firmware scaling constants follow from these; no value is frozen here |
| Energy performance | Active and reactive energy error < 0.1% over a 3000:1 dynamic range (channel A); IRMS error < 0.2% over 1000:1; **gain error ±3% uncalibrated** | The IC is capable; the uncalibrated gain error means calibration is mandatory for any accuracy claim (section 8.7) |
| Phase calibration | Current-channel phase correction: 0.02°/LSB at 50 Hz with ±7.66° range (±9.192° at 60 Hz) | A CT's phase shift can be compensated in the IC — this is what makes CT sensing viable at low power factor |
| No-load behaviour | Fixed internal no-load threshold at 1250:1 of input full scale, per channel | CALCULATED: for a plausible lamp scale of 1.5-5 A that floor is ≈1.2-4 mA, far below the model's 50 mA near-zero default; the IC floor does not limit that detection — the CT and burden do |
| Bandwidth | 1.23 kHz (−3 dB), SNR 74/72/70 dB, SFDR 68/65 dB | Adequate for 50/60 Hz power with harmonics; not a harmonic-analysis instrument |
| Interface | SPI, I²C or UART | **OPEN**, with a real constraint: SPI needs SCLK/MOSI/CS forward and MISO reverse = exactly the four channels of the ISOW7741 candidate, leaving nothing for the IRQ pin; I²C needs a bidirectional isolator |
| Isolation | No isolation rating; not an isolated device | Decisive for section 8.9 |

Can the device reside safely and meaningfully in the proposed domain? Only once
the domain is chosen: in option A it is a mains-referenced part whose interface
is isolated; in option B it must be fed by isolating sensing on **both** the
current and voltage paths. What the datasheet does confirm is that the device is
suitable for a *monitoring* function and that it provides active, reactive and
apparent quantities rather than only a current reading.

### 8.3 Current sensing (CT) analysis

**Required range.** The repository records no current target. The digital
model's *configurable defaults* imply an assumed lamp scale of order 1.5 A /
400 W at 230 V (`over_current_max` 1.5, `power_max` 400, voltage band
180-260 V), but these are logic thresholds, not hardware inputs: they are
validated configuration (`D-022`) and can be set differently per site. The
hardware range must therefore come from the external luminaire's data
(normal current, maximum current, LED-driver inrush) plus the configured
over-current threshold it must be able to observe. Until then the range is
**OPEN**, and the ratio of full scale to normal current is itself a design
input: a range set far above the normal current wastes the very dynamic range
the fault thresholds rely on.

**Why ratio, burden, input range, maximum current and accuracy must be chosen
together.** The chain is a current divider into a voltage input:

```text
 I_secondary(rms) = I_primary(rms) / N
 V_burden(peak)   = sqrt(2) x I_secondary(rms) x R_burden
 P_burden         = I_secondary(rms)^2 x R_burden

 so, for a chosen input full scale V_fs(peak) and a headroom factor k < 1:

   R_burden = V_fs(peak) x k / ( sqrt(2) x I_primary(max) / N )

 and conversely, for a chosen N, the burden that just fits the input range:

   N = sqrt(2) x I_primary(max) x R_burden / ( V_fs(peak) x k )
```

Every term is an input. `V_fs` is a datasheet value (500 mV differential at
PGA ×1 on channel A, less at higher gain — Table 6 of the datasheet), while
`N`, `I_primary(max)` and `k` are decisions. Changing any one of them changes
the burden, the burden dissipation, the signal at normal load (and therefore
the SNR actually used), and the accuracy achievable. No burden value is
recorded here because that would freeze the other four inputs by implication.

| Item | Status | Note |
| --- | --- | --- |
| CT ratio | **OPEN** | No ratio in the repository; must follow from the lamp data and the input range |
| Burden resistor | **OPEN** | Follows from the equation above; power rating follows from `P_burden` |
| Burden tolerance / tempco | **OPEN** | Part of the current-gain error budget (section 8.7) |
| CT saturation | **OPEN** | Must be specified for maximum load **and** LED-driver inrush; decide whether accuracy during inrush is required or only survival |
| CT linearity / accuracy class | **OPEN** | The CT's own error is a first-order term in the gain budget |
| CT phase error | **OPEN**, compensable | The ADE7953's phase-calibration register covers ±7.66° at 50 Hz (0.02°/LSB) — the compensation must be performed during calibration |
| Frequency range | Design target 50/60 Hz | CT specified over the band including harmonics of interest |
| Open-secondary protection | **Required** *(inference)* | An unloaded CT secondary develops a high voltage; the burden path must be protected against an open or failed burden (for example a clamp across the burden). Not a datasheet item — standard practice |
| Insulation / barrier role | **OPEN, A-30 coupled** | In option B the CT's primary-to-secondary insulation is part of the safety barrier and must be a rated component; in option A it is a functional sensor only |
| Physical placement | **OPEN** | Determined by the barrier, the conductor routing and creepage (section 8.11) |
| Calibration | **Required** | Current gain and phase, per node (section 8.7) |

**Is a CT alone sufficient?** No:

* **Load-present and under-current detection** — yes in principle, because both
  are current-magnitude thresholds and the ADE7953's no-load floor sits far
  below them (CALCULATED above). The practical limit is CT/burden noise at the
  chosen ratio, not the IC.
* **Over-current detection** — yes, provided the channel's full scale and the
  CT's saturation behaviour cover the largest current the configuration can
  declare plus headroom. This is exactly why the range decision cannot be
  deferred.
* **Energy measurement** — **not from a CT alone**: energy is `∫ VI dt`, so the
  voltage channel is equally required, and the CT's phase error must be
  calibrated out (section 8.5).
* **Anything about the physical cause** — no single current measurement can
  separate a failed lamp, a failed driver, a supply problem or a sensing
  problem; that is why diagnosis is multi-evidence (`D-009`, `PR-DIAG-001`).
* **Tamper / neutral current** — only with a second current path (channel B),
  which is a decision the repository has not made.

### 8.4 Mains voltage sensing

Nominal 230 VAC, 90-305 VAC single-phase L-N are documented design targets
(`A-02`-`A-04`). No divider values exist in the repository.

What any divider must satisfy, in order:

1. **Scale the maximum working voltage into the input range.** CALCULATED:
   305 VAC RMS is 431 V peak; with a 500 mV single-ended full scale the implied
   ratio is about 862 000:1 (equivalently, a top-chain resistance of roughly
   862 kΩ per volt of bottom resistance). With a lower PGA full scale the ratio
   falls proportionally. This is a **derived relationship, not a frozen value**
   — the working voltage, the chosen full scale and the headroom factor are the
   inputs.
2. **Survive its own voltage.** CALCULATED: a single resistor cannot stand the
   working voltage, so the top arm is a series chain, each element rated for its
   share, with the chain's creepage/clearance and any slotting providing the
   separation. Total dissipation is `V²/R_total` — CALCULATED: 53 mW at 230 V
   and 93 mW at 305 V for a 1 MΩ total, split across the chain. The high-value
   chain that *was* assumed informally (hundreds of kΩ to MΩ) is therefore
   **reasonable in principle** — it keeps dissipation small and the current into
   the sense node negligible — but it is not frozen, and its element count,
   ratings and tolerances follow from the safety analysis, not from convenience.
3. **Reference correctly.** The divider's bottom node defines the measurement
   reference. In option A that node is neutral/AGND (manufacturer guidance for
   the conventional configuration); in option B a divider from L to the SELV
   side would bridge the barrier and become a safety-critical element in its own
   right (section 8.9).
4. **Filter and protect.** Anti-alias filtering appropriate to the 1.23 kHz
   bandwidth and 6.99 kSPS rate; surge/transient protection coordinated with the
   input protection concept; series resistance limiting fault current into the
   sense node.
5. **Keep the ratio stable.** Ratio error is a gain error and is trimmed by
   calibration, but the trim is only valid while the divider's tempco is
   matched across the arms — otherwise the calibration drifts with temperature.
6. **Respect the input.** Common mode < ±25 mV recommended; differential/single-
   ended range as in section 8.2.

Divider ratio, element values, element count, protection and filtering are
therefore **OPEN**; what can be stated now is the topology constraint set above.

### 8.5 Active power, apparent power and power factor

The quantities are distinct and must not be conflated:

| Quantity | Definition | Where it comes from |
| --- | --- | --- |
| RMS voltage, RMS current | `V_rms`, `I_rms` | ADE7953 provides both (datasheet registers) |
| Apparent power | `S = V_rms x I_rms` (VA) | ADE7953 provides apparent power/energy |
| Active power | `P = S x PF` (W) | ADE7953 provides active power/energy |
| Reactive power | `Q = sqrt(S^2 - P^2)` (var) | ADE7953 provides reactive power/energy |
| Power factor | `PF = P / S` | **Derived in firmware** — the datasheet provides no PF register, and the division must guard `S ≈ 0` |
| Energy | `integral of P dt` (Wh) | Active-energy registers, or firmware integration (section 8.6) |

**The existing digital logic assumes unity power factor.** The measurement
validator compares the reported power against `voltage × current` — that product
is *apparent* power — within the configured tolerance
(`power_consistency_tolerance`, default 0.25), and diagnostic rule 13
("measurement set physically inconsistent") is built on that comparison
(`docs/system_behaviour.md` section 3). This is already recorded as an open
engineering item in `validation.md` section 6; the measurement-layer consequence
is:

* the diagnostic input must be **defined explicitly** as either active or
  apparent power;
* if active power is used, the comparison must include the measured power factor
  (`P` against `V_rms × I_rms × PF`) instead of an assumed PF of 1;
* PF must come from the measurement chain (via P and S), never from an assumed
  constant — no PF value is assumed anywhere here.

This does not change the current-based detections, which are PF-independent and
remain the robust primary evidence. It is a change to how the *power*
consistency evidence must be interpreted on hardware, and it is not a source
change: the model is unchanged by this analysis.

### 8.6 Energy source of record

| Option | Strength | Weakness |
| --- | --- | --- |
| ADE7953 energy registers | Hardware accumulation with < 0.1% active-energy error over a wide dynamic range; independent of MCU scheduling jitter | Registers are volatile and must be read and roll-over-handled; `RESET_ENERGY` must reset the IC baseline coherently with the persisted value |
| MCU integration of sampled power | Trivial reset semantics; no dependency on the IC's register set | Accrues sampling, jitter and missed-sample error; the model's present behaviour, and the weaker metering choice |
| Hybrid (IC accumulates, firmware owns the persisted record and deltas) | Best accuracy with correct persistence semantics | Requires the read cadence, roll-over handling and reset interaction to be specified |

`PR-MEASURE-003` requires the accumulated energy to be monotonic, to survive a
restart and to reset only on an authorized command, and the IC's registers are
volatile — so **in every option the persisted record of record is firmware-
managed**; the question is only where the accumulation arithmetic happens.
Technical preference *(inference, not a decision)*: the IC's registers as the
primary accumulator, with firmware owning persistence, deltas, roll-over and the
`RESET_ENERGY` interaction. This remains **OPEN** as an architecture choice, and
if it stays open it must be closed together with: the calibration location
(`PR-STORAGE-007` separates calibration from records), the persisted-energy
store, the configured reporting interval (`PR-MEASURE-002`), and the records and
MCC reporting that depend on the value.

### 8.7 Accuracy and calibration

No accuracy class may be claimed and none is defined (`PR-MEASURE-005`), so a
numeric acceptance target is **OPEN** pending a product decision. What the
engineering analysis can say without inventing a number:

* **What the accuracy is needed for.** Fault detection works on thresholds
  expressed against the sense scale: the model's logical defaults place the
  near-zero and expected-current thresholds at 0.05 A and 0.20 A against a
  scale of order 1.5 A — CALCULATED, about 3% and 13% of scale. Percent-level
  errors therefore do not threaten detection; they matter for the power checks
  and for energy reporting usefulness.
* **Which errors matter most.** For magnitude thresholds, gain errors dominate
  (CT accuracy, burden tolerance, divider tolerance, the IC's ±3% uncalibrated
  gain error). For energy at low power factor, **phase** dominates: CALCULATED,
  a fixed phase error `Δφ` (radians) produces an active-power error of roughly
  `tan(φ) x Δφ`, so at PF 0.5 (φ = 60°, tan φ ≈ 1.73) a 1° error is about a 3%
  power error. Near zero, offset and the no-load floor dominate, which is what
  the "commanded OFF but current present" detection depends on.
* **Error-budget components** (no percentages invented): CT ratio/linearity/
  phase, burden tolerance and tempco, divider ratio and tempco, ADC gain and
  offset (datasheet offset examples: −12 mV at PGA ×1 and −1 mV at ×16/×22 on
  channel A), reference error and tempco (10-50 ppm/°C), and the phase term
  above.
* **Calibration architecture needed** (not implemented, not selected): voltage
  gain, current gain, phase (in the IC's phase register, range and resolution as
  in section 8.2), power/energy trim against a reference, and channel offsets —
  per node, with coefficients stored as the separate storage class required by
  `PR-STORAGE-007` and loaded into the IC at start-up.
* **Manufacturing and field calibration.** A production calibration rig needs a
  reference source and a reference load; the CT, burden and divider are stable
  components, so a re-calibration in the field is probably unnecessary *(open)*
  — the decision belongs with the accuracy target and the service concept.

### 8.8 What the chain can and cannot observe (fault cross-check)

The 15-rule chain (`docs/system_behaviour.md` section 3) is unchanged; this
table states what each relevant rule needs from the hardware, and whether the
measurement chain can supply it.

| Detection | Rule | Evidence needed | Measurement-chain provision | Limitation to record |
| --- | --- | --- | --- | --- |
| Lamp ON, no current | 5 | Current below the near-zero threshold, with voltage valid and switching feedback ON | Current channel + voltage channel + switching feedback sensor (`A-18`) | Near-zero detection is limited by CT/burden noise and offset, not by the IC floor |
| Lamp ON, low current | 10 | Current in the band between near-zero and expected minimum | Current channel, scaled so the band sits well above the noise floor | The scale-versus-normal-current ratio decides how well this band resolves |
| Lamp ON, excessive current | 6 | Current above the configured maximum | Current channel with full-scale and CT saturation headroom | A saturated CT under-reads; over-current may then be missed unless the range is sized for it |
| Lamp OFF, current present | 7 | Current above the near-zero threshold while OFF | Current channel + offset stability | Must not be masked by offset drift or by the no-load threshold |
| Abnormal supply voltage | 4 | Voltage outside the configured band or invalid | Voltage channel + validity | A **divider failure can imitate a supply fault** — the hardware must supply a validity signal to disambiguate |
| Missing voltage / invalid current | 3, 14 | Null, non-finite or negative values | `PR-MEASURE-004` validity, `sensor_status` | Requires the AFE-to-MCU path to report failure explicitly rather than send stale numbers |
| CT or voltage-sense failure | — | Cross-evidence: current absent while voltage and light are consistent, or voltage invalid while the controller is healthy | Multi-evidence diagnosis | A failed sensor is **not identifiable by that sensor alone**; the classification is `MEASUREMENT_ABNORMALITY`/`INSUFFICIENT_EVIDENCE`, not a lamp verdict |
| Stuck sensor | — | No change across known state transitions | Not currently modelled | Recorded as a possible future consideration, not implemented |
| Implausible power | 13 | Power against `V x I` | Active/apparent distinction (section 8.5) | The present comparison is apparent-power-based; PF must be measured, not assumed |
| Implausible PF | — | PF outside a plausible band | PF derived from P and S | Not currently modelled; a PF band would be a new diagnostic input |
| Metering IC failure | — | Host-interface failure, status/IRQ indication | Interface read failure mapped to `sensor_status` `INVALID`/`DEGRADED` | The mapping itself is a firmware/hardware requirement to be specified |
| Metering↔MCU communication failure | — | Integrity of the digital link | Same as above, plus the isolator's own failure mode | Must never degrade silently into stale values |

No single current measurement can identify every physical fault: a CT sees the
current path, a divider sees the voltage, neither sees the lamp's optics or the
driver's internals. The multi-evidence philosophy (`D-009`) is preserved, and
the measurement layer's obligation is to mark its own uncertainty rather than
imply a root cause.

### 8.9 Isolation: the placement options and their consequences (A-30 coupling)

The decisive question is whether the metering front end sits at mains potential.

| | Option A — mains-referenced island | Option B — SELV-side device |
| --- | --- | --- |
| ADE7953 reference | AGND tied to N (conventional configuration) | Same ground as the MCU/3.3 V rail |
| Current sensing | Shunt (conventional) or CT; the CT's isolation is not needed for safety | CT **is** the isolating element; its primary-secondary insulation is part of the barrier and must be a rated part |
| Voltage sensing | Divider L→N inside the island | Requires an isolating voltage element: a voltage transformer, an isolated amplifier, or a barrier-spanning resistor chain |
| Barrier location | The digital isolator between island and MCU | The sensing elements themselves (CT plus the voltage-sense element) |
| Island supply | Its own mains-referenced supply (or a dedicated isolated DC-DC whose output references N) | None — powered from the existing 3.3 V rail |
| Service/debug | The island must be inaccessible; a debug tool must never touch it | No extra constraint beyond the existing service rule |
| RS-485 interaction | None — already isolated independently | None |
| PE / class interaction | Class-agnostic: the island must stay inaccessible under either class; Class I additionally bonds exposed metal | Class-agnostic in the same way; Class II demands reinforced separation in every direction |
| Main open risk | Island supply design and the isolator's channel/power budget | Single-fault integrity of the barrier-spanning voltage element; accuracy/phase of a VT or isolated amplifier |

**Does the CT's isolation remove the need to isolate the voltage measurement?**
No, and this is the point most easily got wrong. A CT isolates *its own*
secondary winding, so the current channel can be read from the low-voltage side.
But the ADE7953's voltage channel must be referenced to the same node as its
ground, and in the conventional configuration that node is N. If the device is
placed on the low-voltage side, then the divider that feeds VP/VN has to reach
L and N: a divider from L to the low-voltage side **bridges the isolation
barrier through its own resistors**. So either (A) the device is mains-referenced
and its *data interface* is isolated, or (B) the voltage path is itself isolated
by a rated element. Choosing a CT does not decide this.

**Does the measurement architecture change the A-30 classification decision?**
No. It changes where the boundary runs, how many components sit on the
hazardous side, and what the PCB must separate — but the class question
(exposed metal, PE, enclosure) remains exactly where section 6 left it. This
analysis is **coupled** to A-30, not a resolution of it, and it must not be read
as closing either the boundary or the class.

These two options are compared criterion by criterion in section 9, which
records a **preliminary preferred direction** (option A). That direction is not
a decision: it freezes no component and no interface, it does not close A-30,
and it carries the closure checks and fallback conditions listed in section 9.11.

### 8.10 Power-tree implications (tightening section 7.7)

CALCULATED: the front end itself is a small load — 3.3 V × 7 mA = 23 mW typical,
30 mW at the datasheet maximum. Consequences:

* **Option B** (device on the SELV rail): the ~23-30 mW sits on the 3.3 V rail
  exactly as section 7.3 assumed, and the isolating sensing elements add their
  own small loads.
* **Option A** (mains-referenced island): the same ~23-30 mW must be supplied
  *inside the island*, so the island needs its own supply conversion and its
  losses land there, not on the SELV rails.
* **Isolator budget:** the ISOW7741 candidate's isolated output (up to ~0.5 W)
  comfortably carries a ~30 mW metering IC — but it must not be conflated with
  the isolated RS-485 port, which is a different, much larger load (123 mA class,
  section 7.3). If the metering island shares that isolated rail, the two loads
  must be added before the budget is declared.

Net effect on section 7: the "metering arrangement OPEN" item can be tightened
to "≈23-30 mW on whichever domain the device occupies; the isolator's isolated
power is sufficient for the metering IC alone; the mains-referenced alternative
adds an island supply whose conversion losses are not yet counted." No other
rail figure changes.

### 8.11 Physical and PCB implications (no layout)

* **Barrier first:** the placement decision (8.9) fixes where the isolation
  barrier, its creepage/clearance and any slotting must run, and whether the
  divider, burden and front end sit on the hazardous side.
* **CT placement and conductor routing:** the primary conductor's routing
  through the CT determines the isolation distance and the creepage to the rest
  of the board; the CT belongs near the mains conductor and away from the relay
  and the bus.
* **High-impedance nodes:** the divider chain and the CT burden are the most
  noise-sensitive nodes on the board; they must be kept short, away from the
  switching relay, the RS-485 pair and the cellular RF path, with their own
  analog return.
* **Analog/digital grounding:** the datasheet's own test circuit ties AGND and
  DGND together — that single-point reference and the decoupling layout are part
  of the metering accuracy, not a formality.
* **Thermal:** divider dissipation (CALCULATED 53-93 mW for a 1 MΩ chain) and
  proximity to the AC/DC module and relay affect the front end's reference
  temperature and therefore the calibration's stability.
* **Service access:** a debug header must not bridge the barrier, and in option
  A it must not be reachable from the island.
* **Sequencing:** the front end must be powered and clocked before the MCU
  trusts its readings, and the cross-check rules assume values are either valid
  or explicitly marked invalid — the reset and start-up ordering is a hardware
  input here.

### 8.12 Decision status

| Item | Current direction | Status | Why not frozen / what is needed |
| --- | --- | --- | --- |
| Metering IC | ADE7953 | **CANDIDATE** | Suitability confirmed from datasheet for monitoring; selection requires the placement decision and a decision record (`D-023`) |
| Current sensor | CT (or equivalent) with burden and protection | **CANDIDATE** | Type not selected; range and ratio unrecorded |
| CT ratio | none recorded | **OPEN** | Needs maximum/normal lamp current from the luminaire data and the chosen input full scale |
| Burden resistor | none recorded | **OPEN** | Follows from ratio, input range and headroom (`BLOCKED` on the row above) |
| Voltage divider | "divider / isolation arrangement" | **OPEN** | Needs full scale, working voltage, protection concept and the option A/B decision |
| Voltage-sense protection | none recorded | **OPEN** | Follows from the divider and the input protection concept |
| Current-sense protection | "with burden and protection" | **OPEN** | Open-secondary and transient protection not specified |
| ADE7953 placement | mains-referenced island (option A) — **preliminary preferred direction** | **OPEN as a decision — BLOCKED BY A-30** | Compared with option B in section 9; the direction freezes no component and the island's construction still needs the A-30 distances |
| Isolation architecture | one reinforced-capable iso-power barrier carrying the host interface and the island supply — **preliminary preferred direction** | **OPEN as a decision — BLOCKED BY A-30** | Section 9.7 and 9.11; the barrier component's certification status is unconfirmed and its isolated output must still be shown to meet the metering IC's supply requirements |
| Host interface (SPI/I²C/UART) | SPI with polled status/registers — **practical default, not frozen** | **OPEN as a decision** | SPI fits the 4-channel isolator exactly and IRQ is not required for V1 (section 9.9); I²C would need a bidirectional isolator; UART is two-channel but its register access is unverified |
| Active power source | ADE7953 provides active power | **CANDIDATE** | Whether the *diagnostic* consumes active or apparent power is the open part (8.5) |
| Energy source of record | IC integration vs firmware integration vs hybrid | **OPEN** | Firmware owns persistence in all cases; see 8.6 for the dependent items |
| PF handling | none; the model compares `V x I` | **OPEN** | PF must be derived from P and S; no PF value may be assumed |
| Calibration | none | **OPEN** | Architecture sketched in 8.7; coefficients and rig not specified |
| Measurement accuracy target | none, and no claim permitted | **OPEN** | Product decision; `PR-MEASURE-005` forbids claiming a class in the meantime |
| Light sensor | OPT3001-Q1 candidate | **CANDIDATE** | Placement, window and stray-light inputs remain open (section 6.4) |
| Measurement fault plausibility | 15-rule first-match chain | **CONFIRMED (software)** | The rule chain exists and is tested (`PR-DIAG-001`); the hardware validity signals it needs are **OPEN** |

### 8.13 Inputs to close before schematic capture (measurement chain)

Ranked by what blocks what.

| # | Input | Priority | Why |
| --- | --- | --- | --- |
| 1 | ADE7953 placement / isolation architecture (option A or B, or a different front end) | **HIGH** | Decides the barrier, the supply arrangement and the component set; blocked by A-30. A preliminary direction is recorded in section 9.11 and needs its closure checks (barrier certification, isolated-supply quality, island distances) before it becomes a decision |
| 2 | Maximum and normal lamp current from the luminaire data (plus LED-driver inrush) | **HIGH** | Sizes ratio, burden, full scale and the over-current headroom |
| 3 | CT selection and ratio | **HIGH** | Follows from input 2 and the input full scale |
| 4 | Burden value, tolerance and power rating | **HIGH** | Follows from inputs 2-3; sets the signal at normal load |
| 5 | Input full scale and PGA choice (compatibility of the whole current chain with the ADE7953 inputs) | **HIGH** | The bridge between the sensor and the IC; also sets usable dynamic range |
| 6 | Voltage-sensing topology (divider placement, isolating element if option B) | **HIGH** | Determines whether the divider is a barrier element |
| 7 | Measurement accuracy target for detection and for energy reporting | **HIGH** | Drives the calibration scope and the component tolerances |
| 8 | Energy source of record | **HIGH** | Determines what is accumulated where, and the persistence/reset design |
| 9 | Active-power / PF handling definition (which quantity the diagnostics consume) | **HIGH** | Correctness of the power-consistency evidence at PF < 1 |
| 10 | A-30 isolation boundary closure | **HIGH** | Parent of input 1 |
| 11 | Calibration method, per-node coefficients and their storage | **MEDIUM** | Needed before production, not before layout |
| 12 | Protection design: open-secondary, divider surge, input protection coordination | **MEDIUM** | Safety and damage prevention; follows from the placement |
| 13 | Filtering and anti-alias values at both inputs | **MEDIUM** | Accuracy and noise; follows from the IC's bandwidth |
| 14 | Light-sensor physical placement, window and stray light | **MEDIUM** | Already open in section 6.4; affects the environmental rule |
| 15 | Analog/digital partitioning and grounding plan | **MEDIUM** | Layout-stage input for metering accuracy |
| 16 | Host-interface choice and its isolator channel budget | **MEDIUM** | Narrowed in section 9.9: SPI with polled status fits the quad iso-power arrangement and IRQ is not required for V1; the final choice and the SPI timing budget remain open |
| 17 | Service-calibration details and whether field recalibration is needed | **LOW** | Follows from the accuracy target and the service concept |
| 18 | Secondary diagnostics: stuck-sensor detection, PF plausibility band | **LOW** | New diagnostic inputs, not needed for a first prototype |
| 19 | Indicator and support-circuit details around the metering block | **LOW** | Completes the load list |

## 9. Metering front-end architecture trade study (A-22, A-30)

Section 8 established that the measurement chain is technically coherent but
**not placeable**, because the domain of the metering front end is undecided.
This section compares the two architectures the repository preserves, states the
requirements each one has to satisfy, and records which should become the
preferred V1 direction. It is an architecture study: no component is selected,
no value is frozen, no accuracy figure is invented, and **no safety class is
declared**. Evidence labels are as in section 6; CALCULATED marks arithmetic
with its inputs stated. The option names A and B are the ones already used in
section 8.9.

**What this section does not do.** It does not close A-30, does not select the
isolator, the ADE7953, the current sensor or the voltage-sensing part, does not
freeze the host interface, and does not create a decision record (`D-023` still
governs: every component named here is a candidate). The outcome is recorded as
a **preliminary preferred direction**, not as a frozen decision, because A-30
and the product inputs listed in sections 6.7, 7.8 and 8.13 are still open.

### 9.1 The option space as it actually stands

| | Option A | Option B |
| --- | --- | --- |
| Domain of the metering device | Mains-referenced island (AGND at N in the conventional configuration) | SELV side, same reference as the MCU |
| Current sensing | CT with burden inside the island (a shunt is equally possible, because the sensor no longer has to provide isolation) | CT, whose primary-to-secondary insulation is part of the safety barrier |
| Voltage sensing | Resistive divider chain L to N, inside the island | An isolating voltage element on the mains side: passive magnetic voltage transformer, or active isolated amplifier |
| Isolation barrier | The digital interface and the island supply across one rated component | The sensing elements themselves, plus the high-side supply path of an active element |
| Island supply | Required (the metering IC and its crystal live at mains potential) | None for the passive variant; required for the active variant's input side |

Three points fix the option space before the comparison:

* Neither option is disqualified by section 8. The ADE7953 is suitable for
  engineering monitoring in either domain *(datasheet, section 8.2)*, the sensor
  classes needed in both exist, and the repository's power and safety analyses
  contain nothing that rules either one out.
* **Option B is not one architecture.** Its voltage-isolation element may be a
  **passive magnetic voltage transformer**, which needs no supply on the mains
  side, or an **active isolated amplifier**, which does: that device class
  requires a floating supply on its mains-referenced input side *(datasheet,
  see 9.3)*. The two variants fail differently and cost differently, so they are
  compared separately wherever that matters. Neither is selected.
* The third possibility — a different front end — is kept as an option and is
  assessed in 9.4.

### 9.2 Option A defined precisely

```text
 MAINS DOMAIN  (hazardous live; class undecided, A-30 open)
 L --[ input protection ]--+-----[ relay ]-- switched L --> external luminaire
                           |                                (returns to N)
                           |   measured current path
                           |          |
                           |       [ CT ]  secondary + burden,
                           |          |    all inside the island
                           +--[ divider chain L -> island reference ]
                                      |
   +------ metering island, reference = island AGND = N ----------------+
   |  ADE7953: VP/VN from the divider, IAP/IAN from the CT burden, 3.58  |
   |  MHz crystal, decoupling, 3.3 V island rail                          |
   +----------------------------------+-----------------------------------+
                                      |  SPI: SCLK / MOSI / CS forward,
                                      |  MISO reverse (4 signals)
                                      |  island power from the isolator's
                                      |  integrated isolated DC-DC
                                      ||
                                      ||  ONE rated barrier component
                                      ||  (data + power)
                                      v
 SELV DOMAIN (3.3 V)
   STM32G474RE ---- polled register reads on the measurement cycle
                    (no IRQ channel required for V1, section 9.9)
   RS-485 isolation, relay coil driver, storage, RTC, light sensor
```

| Aspect | Position in option A | Basis / status |
| --- | --- | --- |
| Required isolated interface signals | SPI uses four pins — CS, SCLK and MOSI toward the island, MISO back — so a quad-channel isolator is exactly consumed; I²C uses two shared pins (SDA bidirectional, SCL) and UART uses two (Rx, Tx) *(datasheet)* | Channel count is *(inference)*; the interface set and pin sharing are *(datasheet)* |
| SPI feasibility | Feasible. The ADE7953 is an SPI slave clocked up to 5 MHz *(datasheet)*, so the usable clock is set by the isolator's propagation delay, not by the IC; the timing budget must be derived from both datasheets | Feasible *(datasheet)*; timing budget *(open)* |
| I²C feasibility | Feasible in principle (100 kHz standard / 400 kHz fast mode *(datasheet)*) but needs a **bidirectional** isolator. An I²C isolator without an integrated DC-DC does not by itself power the island, so the island supply becomes a separate part — i.e. a second barrier element | *(inference)* |
| UART feasibility | Two channels only, leaving the isolator's channel budget free. Whether the UART path exposes the full register set the diagnostics need must be established from the datasheet, and is not assumed here | Usable in principle *(datasheet)*; register-access equivalence *(open)* |
| IRQ handling | **Not required for V1** (9.9). Events are not lost without the pin: the IC's power-quality events (overcurrent, overvoltage, peak, sag), no-load and zero-crossing conditions are also readable as status registers, so a polled design can still see them | *(inference)* on the polled cadence; the flag set is *(datasheet)* |
| Isolated power requirement | The island's load is the metering IC at 23–30 mW (CALCULATED in section 8.10) plus a crystal and housekeeping — negligible against the isolator candidate's integrated isolated output of about 0.5 W | Load *(calculated)*; isolator capability *(datasheet, section 6.5)* |
| Metering-island power source | The isolator's integrated isolated DC-DC, its output referenced to the island (i.e. to N). If it proves unsuitable, a separate isolated DC-DC is the alternative, at the cost of a second barrier element. Whether the integrated output meets the metering IC's supply tolerance and noise requirements directly, or needs filtering/post-regulation, is not established | *(open)* |
| Grounding / reference arrangement | AGND is the island's reference; the divider's bottom node and the burden's low node return to it, and the isolated DC-DC's return is the same node, so the analog sense returns and the supply return must be separated locally in the layout. Common-mode constraints on the current channel are naturally satisfied by referencing the burden to AGND | *(inference)* |
| CT connection | Secondary and burden sit inside the island, referenced to AGND. The CT's primary-to-secondary insulation is a **functional** requirement here, not a safety barrier — this is the structural difference from option B. A shunt is equally admissible, which keeps the current-sensor choice open (section 8.3) | *(inference)* |
| Voltage-divider reference | The divider is L to N with its bottom node at the island reference. Two consequences are design inputs rather than details: the sense polarity follows the L/N labelling (a reversed installation inverts it), and the island's reference is a mains conductor, so its integrity depends on the neutral connection | *(inference)*; both *(open)* |
| Service / debug implications | The island must stay inaccessible; the SWD header remains in the SELV domain and must never bridge the barrier; probing the metering block needs isolated/differential instrumentation. One trap to record: the island supply must be **its own** isolated output — reusing the isolated RS-485 port's spare output for it would tie the bus-side reference to a mains-referenced island and bypass the barrier | *(inference)*, consistent with section 6.4 row (E) and section 7.7 |
| PCB isolation implications | One barrier line, crossed by one wide-body barrier component with datasheet distances; the island's own copper must satisfy the class distances, and the high-impedance sense nodes need their own return away from the relay, the bus pair and the RF path | *(inference, section 8.11)* |
| A-30 implications | Does not change the class question. It **extends the existing mains-side region** rather than introducing a barrier type the product does not already need (the RS-485 interface already contemplates a reinforced isolator). The island distances, the working voltage and the barrier component's certification remain A-30 inputs | Coupled *(open)* |
| Thermal implications | The island dissipates roughly 30 mW plus the isolated DC-DC's conversion losses; the divider chain dissipates 53–93 mW at 1 MΩ (CALCULATED, section 8.4). Both are small next to the relay coil and the module, but they set the front end's local temperature and therefore the calibration's thermal stability | *(inference)* |
| Calibration implications | The IC sits in the same domain as its sensors, which is the configuration the manufacturer's calibration methods describe: one significant phase term (the CT), trimmed in the IC's current-channel phase registers, and gain terms trimmed per node. Calibration requires a mains-voltage reference and a reference load | *(inference, section 8.7)* |

### 9.3 Option B defined precisely

```text
 MAINS / HAZARDOUS-LIVE SIDE                        SELV SIDE
 L --[protection]--+---[relay]--- switched L ---> external luminaire
                   |   measured current path            (returns to N)
                   |          |
                   |       [ CT ]--------------------> secondary and
                   |          |                       burden on the
                   |          |                       SELV side
                   +--[divider]--+
                                 |
                 (passive)   [ VT ]      (active)  [ isolated amplifier ]
                                 |                     |
                                 |        needs a floating high-side supply
                                 |        referenced to the mains-side node
                                 |                     |
        ======================== v =================== v ================
        ============== the sensing elements' insulation ================
        ========================== is the barrier ======================
                                 |
 SELV DOMAIN (3.3 V)             v
   ADE7953 on the same rail as the MCU: direct SPI / I2C / UART,
   IRQ directly available to the MCU, no island, no isolated supply
   for the metering IC  -->  STM32G474RE
```

#### 9.3.1 What the voltage-isolation element must provide

Whatever class is chosen, the eventual part has to satisfy this requirement
set. These are requirements on a class, not a selection:

| # | Requirement | Why |
| --- | --- | --- |
| 1 | A safety separation that the product's insulation coordination can use — reinforced-capable in itself, or a construction with two independent layers — at the declared working voltage and impulse withstand | The SELV domain must be separated from mains by double/reinforced insulation **whatever the class** (sections 6.2, 6.7); a single basic-insulation element is not enough for a SELV output |
| 2 | Ratio scaling from 305 VAC (431 V peak) down to the ADE7953 voltage input, over the whole 90–305 VAC range | Section 5's design target and section 8.4's input range |
| 3 | A **small, stable, calibratable phase error** in the voltage path, which together with the CT's term stays inside the IC's phase-register range | PF and energy at low PF depend on the relative phase (9.6); the register covers 0.02°/LSB over ±7.66° at 50 Hz and ±9.192° at 60 Hz *(datasheet)* |
| 4 | Ratio and phase stability over temperature **and over the 3.4:1 excitation range** of the design target, not merely at nominal voltage | A calibration constant is only valid while the error it corrects stays constant |
| 5 | Continuous mains-side stress capability: the element's primary side is energised for the product's life, and it must not degrade its own insulation under that stress | A sensing element carrying safety duty must stay safe while it ages |
| 6 | Primary-side protection (fuse/limiting element) coordinated with the input protection concept | Fault current and component failure in the primary path |
| 7 | Creepage and clearance across the component's own package and pins, to the class requirement | A component whose body spans the barrier must not undermine the PCB barrier |
| 8 | A **defined failure mode** that the diagnostics can observe: what the sensing path reports when the element degrades, differs or opens | A voltage-sense failure can imitate a supply fault (section 8.8), so the link must not degrade silently |
| 9 | An output that the ADE7953's voltage channel can actually accept | Its input range and reference are fixed (section 8.2); anything else needs an adaptation network with its own error terms |

The last two requirements are what make option B a sensing-design task rather
than a part swap, and they are recorded here so a later schematic design cannot
proceed on a hidden assumption.

#### 9.3.2 The two realisations, and why they are not equivalent

| | Passive variant (voltage transformer) | Active variant (isolated amplifier) |
| --- | --- | --- |
| Mains-side supply | **None** — the element is passive, which is its main attraction | **Required**: the class needs a floating high-side supply referenced to the mains-side node. Representative published figures for such a part: 6.0–8.4 mA on the high side where that supply is 3.0–3.6 V (the condition the datasheet publishes for its tighter grade, which also lists a 4.5–5.5 V high-side supply for the other grade) *(datasheet, representative of the class, not a selection)*, i.e. roughly 20–30 mW at 3.3 V, plus that supply's own conversion losses |
| Barrier elements in the metering path | The CT and the voltage transformer — two | The CT, the isolated amplifier, and the high-side supply's own isolation — three |
| Magnitude accuracy | Vendor data for the common 2 mA:2 mA class: linearity of order 0.1–0.2%, a claimed 0.2 accuracy class. This is **vendor data, and the sources disagree** (linearity 0.1% vs 0.2%, dielectric 4000 V vs 3000 VAC), so it can support no safety or accuracy argument; the selected part's own datasheet governs | The class is specified precisely: offset error ±9.9 mV max (±1.5 mV on the tighter grade), gain error ±1% max (±0.2% on the tighter grade), nonlinearity 0.04% max, gain drift of order tens of ppm/°C, output bandwidth of hundreds of kHz *(datasheet, representative of the class)* |
| Phase behaviour | Phase error is specified as a bound at a rated burden (tens of arcminutes for the common class), and it varies with burden, excitation and temperature. Compensation is possible, but the corrected value is load- and excitation-dependent over the 3.4:1 range | Phase contribution at the line frequency is small — the part is not the dominant phase term. The real work is the **output adaptation** to the ADE7953's input (a differential output centred on an internal common-mode, not on the IC's own reference), which adds matched-resistor gain/offset error terms of its own |
| Failure signalling | Passive: an open winding looks like a missing voltage | The class offers a **missing high-side supply indication** and a defined failsafe output level when the high side is absent *(datasheet)* — useful evidence for section 8.8's requirement |
| Continuous mains-side dissipation | The primary is fed through a series limiting element that carries the full mains voltage. CALCULATED for a 2 mA-class rated current: about 0.4 W at 230 VAC, an order of magnitude above option A's divider dissipation (53–93 mW, section 8.4). To be recomputed from the selected part's data | A divider chain is still needed to scale the mains into the amplifier's input, with dissipation comparable to option A's chain |
| Size and sourcing | A sealed magnetic of centimetres-scale footprint, and its insulation construction is the barrier | A wide-body SOIC with a rated barrier (representative class data: reinforced, 5000 V RMS isolation, 1500 V RMS working voltage, at least 8.5 mm creepage/clearance) plus its high-side supply components |
| Number of parts on the mains side | Two passive elements (CT, VT) plus the limiting element | CT plus the divider, the amplifier and the high-side supply |

The isolated-amplifier figures above also settle a question the option diagram
raises: the high-side supply could not be borrowed from the existing isolated
RS-485 port, because that converter's isolated output is referenced to the
bus-side domain; using it here would tie the bus-side reference to a
mains-referenced node. Any active variant therefore needs its **own** floating
supply, and that supply's isolation is part of the barrier.

#### 9.3.3 The remaining aspects

| Aspect | Position in option B | Basis / status |
| --- | --- | --- |
| CT suitability | The CT remains suitable and becomes more useful: it is the reason the current path needs no high-side electronics. It must be a **rated barrier component** (or a two-layer construction), the burden moves to the SELV side, and open-secondary protection is still required | *(inference, section 8.3)* |
| Isolation requirements | The barrier is now constructed from sensing elements rather than bought as one certified part. Its adequacy depends on the selected parts' insulation data, on the PCB distances around them and on the construction — i.e. on inputs that overlap A-30 | *(open)* |
| PCB implications | Several barrier crossings (the CT's conductor and body, the voltage element's package, the high-side supply if active) instead of one, each with its own keep-out; the active variant also carries a small mains-referenced zone around the amplifier and its supply | *(inference)* |
| Calibration implications | Two or more sensing elements contribute gain and phase terms, and in the passive variant the phase term moves with burden and excitation. Per-node calibration is mandatory, and its validity depends on the elements' stability (section 8.7) | *(inference)* |
| Safety implications | Less mains-referenced active circuitry than option A (none in the passive variant), at the price of a barrier whose layers, distances and single-fault behaviour must be engineered and qualified rather than quoted from one certificate. A-30 is not closed by this, and no class is implied | *(inference, A-30 open)* |
| Service / debug implications | The metering IC and its interface are on the SELV side and can be probed with ordinary instruments; the sensing front end is still mains-referenced and still requires the same care as any primary-side measurement | *(inference)* |
| Component-count implications | Passive variant: CT, voltage transformer, limiting element, burden, divider — no isolator, no island. Active variant: CT, burden, divider, isolated amplifier, high-side supply, output adaptation network — more parts than option A | *(inference)* |
| Power / PF implications | PF still comes from the measurement (P/S, section 8.5); the new element adds a phase term to the relative phase (9.6) and, in the active variant, a mains-side supply load (9.8) | *(inference)* |

### 9.4 The third possibility: a different front end

Section 8.1 keeps a different front end as an option, and this study checked
whether either ADE7953 architecture has a **substantive engineering problem**
that would force it. Neither does: option A's configuration is the one the
metrology datasheets document, and option B's difficulties are structural costs
(barrier construction, an extra phase or supply term), not impossibilities. The
third option therefore stays an option, not a requirement, and no evaluation of
a replacement part is performed here.

It is worth recording what that option class looks like, because it is **not a
way around the domain question**. Metering front ends exist that integrate the
barrier, and in some families the high-side supply as well — for example an
isolated three-channel Σ-Δ ADC family whose published data includes an
integrated isolated DC-DC, a 5 kV-RMS-rated barrier per UL 1577, a wide-body
package with more than 8 mm clearance and creepage, a 4-wire SPI interface,
±31.25 mV current channels and ±500 mV voltage channels on a single 3.3 V supply
*(datasheet, published for that family; that family is not a candidate here and
is not selected)*. Such a device would make the isolation *invisible* to this
product's board, but it is still **mains-referenced sensing**: the sensors, the
divider and the device's first stage remain in the hazardous-live domain, and
the digital interface emerges on the SELV side. In the terms of this study it is
a **variant of option A**, with two consequences that keep it out of scope:

* it is an ADC, so the metering arithmetic (RMS, power, PF, energy) moves into
  the MCU, which changes the energy-source-of-record answer in section 8.6
  rather than merely the part number; and
* its current channel suits a low-level sensor such as a shunt, so adopting it
  would reopen the current-sensor decision (section 4) as well.

Trigger conditions for evaluating it later are recorded in 9.11.

### 9.5 Comparison

The table compares the two architectures criterion by criterion. It is **not a
score**: no weights and no numbers are assigned, and the "preferred" column is a
judgement about the engineering evidence for that criterion only. Where the two
are genuinely equivalent, or where the evidence does not support a preference,
that is stated rather than forced.

| Criterion | Option A | Option B | Preferred | Reason |
| --- | --- | --- | --- | --- |
| Electrical safety (overall) | One rated barrier component; a mains-referenced metering block | Less live circuitry (passive) or a small live bias zone (active); a barrier built from sensing elements | **No preference** | Different trades, not different safety levels; the class and distances are A-30's to fix either way (9.7) |
| Hazardous-live active circuitry | Metering IC, crystal and island supply at mains potential | Passive: none. Active: the amplifier's high side and its supply | **B** | Less active circuitry at mains potential |
| Isolation complexity and barrier clarity | One barrier element carrying data and power | Two (passive) or three (active) barrier elements | **A** | One datasheet-defined barrier instead of a construction |
| New barrier elements introduced | None beyond the digital-isolator class the RS-485 port already contemplates | The sensing elements become safety-barrier elements | **A** | Reuses an existing component class instead of creating a new qualification task |
| Voltage measurement | Resistive divider in the IC's own reference domain | Passive: a magnetic with load-dependent ratio. Active: a well-specified amplifier, but its output must be adapted to the IC's input | **A (narrow)** | Fewest new error terms; the active variant is close behind on magnitude accuracy |
| Current measurement | CT or shunt in the island; element insulation functional | CT; element insulation is the barrier | **No preference** | Same sensor class, different duty |
| Active power | One phase term (CT), corrected in the channel the IC compensates | A second phase term in the voltage path | **A** | Phase structure (9.6) |
| Apparent power | V_rms × I_rms from the same IC | Same IC, same arithmetic | **No preference** | The domain does not change this quantity |
| Power factor | PF = P / S; phase structure as the active-power row | Same derivation; a second phase term | **A** | PF is the quantity most exposed to a relative phase error |
| Energy accumulation | IC registers plus firmware persistence | Same device, same accumulation question | **No preference** | Section 8.6 is independent of the domain |
| Measurement accuracy (magnitude) | CT, burden, divider, IC — trimmed once per node | Passive: adds the magnetic's ratio error and its variation. Active: adds the amplifier's DC errors and the adaptation network | **A (narrow)** | The calibration path is the documented one; the active variant is comparable but has more terms |
| Phase error | One dominant term, in a channel the IC calibrates | Passive: a second, load- and excitation-dependent term. Active: a small term plus an adaptation network | **A** | See 9.6 |
| Calibration | Single domain; one sensor's phase; standard method; a mains reference is needed | Several elements and, in the passive variant, a load-dependent term; the same rig is needed | **A** | Fewer coefficients and less coupling to load and temperature |
| Host interface to the MCU | Isolated SPI/I²C/UART; with SPI a quad isolator has no channel left for IRQ | Direct, unisolated interface; IRQ available to the MCU | **B** | No channel budget, no propagation delay, interrupt available |
| Power consumption | IC at 23–30 mW behind the isolator's converter, plus the divider's 53–93 mW on the mains side | Passive: IC at 23–30 mW on the SELV rail, but a continuous mains-side limiting element of order 0.4 W (CALCULATED for the 2 mA class, 9.3.2). Active: IC plus high-side supply (20–30 mW class) and its conversion | **No preference (A ≈ B active); the passive variant is heaviest on the mains side** | Absolute differences are small against a 10 W module whose real limit is derating; what changes is *where* the load lands (9.8) |
| PCB segregation / barrier geometry | One barrier line through one wide-body component | Several component-level crossings and keep-outs | **A** | Easier to demonstrate, review and inspect |
| Board area at mains potential | A two-IC island with its own decoupling | Passive: passive elements only. Active: a small amplifier zone | **B** | Smaller hazardous-live footprint |
| Component count | IC, isolator, crystal, burden, divider | Passive: no isolator or island, but a large magnetic. Active: amplifier, a second isolated supply, adaptation network, on top of A's parts | **A vs the active variant; no preference vs the passive one** | The active variant adds parts to A's list; the passive variant instead trades active parts for magnetics and a load-dependent sensor |
| Serviceability | Live island; probing needs isolated/differential instruments | Metering electronics are SELV-probeable | **B** | Bench and service safety |
| Debug access | SWD header is SELV in both; metering debug needs island-safe instruments | Same SWD situation; metering debug directly probeable | **B** | As above |
| Fault diagnosis | A link failure makes the whole block observably unavailable; sensor failures still imitate other faults | Sensor-level failures are not distinguishable by the MCU; the active variant adds supply failure modes | **No preference** | Section 8.8's multi-evidence obligations are unchanged in both; neither removes the "a divider or sensing failure can imitate a supply fault" problem |
| Thermal impact | Island ≈30 mW plus converter loss, plus the divider's 53–93 mW | Passive: a mains-side element in the hundreds of milliwatts (9.3.2). Active: divider plus amplifier plus supply | **A (narrow)** | Lower continuous dissipation, but the difference is small at module level |
| Manufacturability | Conventional metering circuit; one critical barrier part | A large magnetic whose insulation construction carries barrier duty (passive), or several new active parts (active) | **A (narrow)** | Fewer new qualification and assembly items |
| Cost direction | Cost concentrates in the barrier component with integrated isolated power | Passive: cost concentrates in the magnetics. Active: an amplifier plus a second isolated supply | **OPEN** | No quotations are available; a volume comparison is an input, not an estimate to invent |
| Scalability | The island is a self-contained block; the isolator/interface variant can change locally | The front end is coupled to the sensor and barrier construction | **A (narrow)** | Block separation makes later changes more local |
| Minewing prototype practicality | Mains-referenced island needs bench discipline (isolated supply, differential probing) but adds no new sensing-characterisation task | Passive: bench-friendly electronics, but the voltage element's ratio and phase over load, excitation and temperature must be characterised. Active: additionally a floating supply and an adaptation network to design and verify | **A (narrow, and split)** | The bench discipline is required for this product anyway; the new unknowns are fewer |
| Future production practicality | One barrier component to keep certified; the island construction is fixed by layout | Several sensing parts whose insulation data and consistency carry the barrier; the passive variant adds magnetic batch consistency | **A (narrow)** | Fewer safety-critical part qualifications to control |

The deciding rows are the structural ones — barrier clarity, new barrier
elements, active-power and PF phase structure, calibration, PCB segregation and
component count — not the number of rows that happen to favour one option. The
rows where B is preferred (live-circuitry volume, interface simplicity,
serviceability) are real advantages and are the reasons B remains the fallback
rather than being discarded.

### 9.6 Phase error, PF and energy

The product needs active power, energy and PF, and PF must come from the
measurement (P/S), never from an assumed value (section 8.5). For a load whose
PF is below unity the relative phase between the voltage and current paths is
therefore a first-order error term, not a detail: a fixed phase error `Δφ`
produces a power error of roughly `tan(φ) × Δφ`, so at PF 0.5 a 1° error is
already about a 3% power error (CALCULATED, section 8.7).

The IC's own contribution is small: the manufacturer specifies the phase
matching between its current and voltage channels as within ±0.05° from 45 Hz to
65 Hz *(datasheet)*. The sensing elements dominate, and the two options differ
in how many of them there are:

* **Option A.** The current path contributes one significant term. The
  manufacturer states that a phase error of 0.1° to 0.3° is not uncommon for a
  current transformer, that it varies from part to part, that it must be
  corrected for accurate power readings and that it is particularly noticeable
  at low power factor *(datasheet)*. The device corrects exactly this, in the
  current channel, with a 10-bit sign-magnitude phase register whose LSB is
  1.117 µs of delay or advance — 0.02°/LSB at 50 Hz over a total of ±7.66°, and
  0.024°/LSB at 60 Hz over ±9.192° *(datasheet)*. The voltage path is a
  resistive divider, whose phase contribution at the line frequency is
  negligible compared with the CT's; the anti-alias filter adds a small term
  that forms part of the same compensation. The device also provides an
  angle/time-delay measurement register pair for the current-to-voltage delay
  *(datasheet)*, which is the calibration aid for this term. In short: one
  dominant, measurable, IC-compensable phase term.
* **Option B, passive variant.** A second phase term appears in the voltage
  path. Class data bounds it in the tens of arcminutes at a rated burden — the
  same order as a CT's — but it is specified at a burden and varies with
  burden, excitation and temperature. The relative phase therefore becomes a
  two-element, load-dependent quantity: a single calibrated constant is only as
  valid as the stability behind it, and the combined terms must still fit the
  IC's compensation range.
* **Option B, active variant.** The amplifier's phase contribution at the line
  frequency is small, because its output bandwidth is in the hundreds of kHz
  *(datasheet, representative of the class)* — it is not the phase problem. Its
  DC errors and, more importantly, the **output adaptation network** are: the
  amplifier's differential output is centred on its own internal common-mode
  voltage, not on the ADE7953's reference, so it has to be level-shifted and
  scaled, and that network's matched resistors add gain, offset and temperature
  terms that must be calibrated and kept stable.

Two cautions belong with this analysis. First, phase compensation is a **time
shift**, and the manufacturer's own documentation for that technique (quoted for
a related ADE device, same mechanism) warns that large phase errors corrected
this way can introduce errors at higher harmonics — the correction is exact at
the fundamental. The sensing element should therefore keep its residual phase
error small rather than have a large error calibrated away; that is an input to
the CT selection and, in option B, to the voltage-element selection. Second,
nothing here assumes a PF: PF is measured, and the accuracy target stays **OPEN**
(no number is invented). What can be said is structural: option A keeps the
relative phase a single term that the device was designed to correct, while
option B either makes it load-dependent or adds an adaptation network whose
stability becomes part of the accuracy argument.

### 9.7 Safety and isolation, cross-checked against A-30

Neither option closes A-30, neither declares a class, and neither fixes a
creepage/clearance value. What they change is **where the boundary runs and what
it is made of**, and that is what this section compares. The class-agnostic
requirement from section 6.7 applies to both: the SELV domain must be separated
from mains by double or reinforced insulation whatever the class turns out to
be, so the barrier has to be reinforced-capable in either architecture.

| Question | Option A | Option B |
| --- | --- | --- |
| What the barrier is | One component: a reinforced digital isolator with an integrated isolated DC-DC, whose barrier carries data and power. The candidate's published data gives reinforced classification with defined creepage/clearance, working voltage and surge ratings — while its certification status must still be confirmed with the manufacturer (section 6.5) | A construction: the CT's insulation plus the voltage element's insulation, plus the high-side supply's isolation in the active variant. For typical parts of these classes the published data gives withstand voltages, not insulation classes, and the sources found disagree with each other (9.3.2) — so reinforced-capable parts, or a two-layer construction, must be found or created |
| Single-fault behaviour | The barrier is a solid-state component rated for its working voltage and surge; its failure modes are the component's, and the island's inaccessibility is a mechanical/enclosure requirement | Must be analysed element by element: the repo already records "single-fault integrity of the barrier-spanning voltage element" as option B's main open risk (section 8.9), and the same question now applies to the CT and the bias supply |
| Mains-referenced active circuitry | Present: the metering IC and its supply | Passive variant: none. Active variant: the amplifier's high side and its floating supply |
| Isolation crossings | One | Two or three |
| PCB segregation | One barrier line, crossed by one wide-body part with datasheet geometry | Several component-level crossings, each with its own keep-out and distances |
| Service / debug | The island must be inaccessible; probing it requires isolated/differential instruments; the debug header stays SELV | The metering electronics are SELV-probeable with ordinary instruments; the sensing front end is still mains-referenced |
| Coupling to A-30 | The barrier is a component rating, independent of the enclosure; the island still needs the class's distances and an inaccessible construction | The barrier's adequacy depends on the parts chosen and on the enclosure/class decisions — the coupling is tighter |

**Which option wins which safety question.** Least hazardous-live active
circuitry: **B**. Fewest isolation crossings: **A**. Safer service and debug:
**B** for the metering electronics. Simplest PCB segregation: **A**. Fewest
ambiguous safety boundaries: **A**.

**The actual trade-off, stated plainly.** Option A is not preferred because it
"looks safer" — it puts *more* electronics at mains potential, and that has real
consequences for bench work and service. It is preferred on boundary clarity
because its barrier is a single component with published ratings and a
certification path, of the same class the RS-485 interface already needs, while
option B asks the product to *construct* a barrier out of sensing elements whose
insulation data are weaker and whose single-fault behaviour has to be argued
from scratch — and, in the active variant, to do that while also adding a third
barrier element and a residual mains-referenced bias island. The remaining A-30
inputs (working voltage, overvoltage category, pollution degree, altitude,
enclosure, installation) are still prerequisites for either option, and no
distance, class, PE treatment or certification is recorded here.

### 9.8 Power cross-check against section 7

The comparison is relative, not a new budget; no current value is invented. What
each option changes is **where** the metering load lands.

* **Option A.** The island carries the metering IC's 23–30 mW and the local
  dissipation of its supply conversion, but the *input power* of that conversion
  comes from the SELV 3.3 V rail through the isolator. Section 7's 3.3 V load
  list therefore gains the isolator's input current rather than the IC's 7 mA
  directly, which makes the SELV-side figure **larger** than 30 mW by the
  converter's conversion loss. This refines section 8.10 rather than
  contradicting it: what stays in the island is the load, but the energy is paid
  for on the SELV rail. The two unknown values are the isolator's input current
  at this load and the converter's light-load efficiency; neither is in the
  repository *(open)*. If the island were instead fed from a mains-referenced
  supply, the loss would land on the mains side, but that route brings its own
  standby, leakage and safety questions and is not the candidate path here.
* **Option B, passive variant.** The metering IC's 23–30 mW sits on the 3.3 V
  rail exactly as section 7.3 assumed. The voltage transformer's primary path is
  a continuous mains-side load: the series limiting element carries the mains
  voltage, and for the class's 2 mA rated current that is about 0.4 W at 230 VAC
  (CALCULATED, 9.3.2 — to be recomputed from the selected part). It does not
  consume the AC/DC module's 10 W budget, but it is a continuous load inside the
  enclosure and an input-protection sizing item.
* **Option B, active variant.** The IC's 23–30 mW is on the 3.3 V rail, plus the
  amplifier's low-side supply *(open)*, plus its high-side supply — the
  representative class figure is 20–30 mW *(datasheet)*, whose own conversion
  losses land on whichever domain feeds it — plus the divider chain that scales
  the mains into the amplifier's input, which dissipates comparably to option A's
  chain. The adaptation network is negligible.

The absolute differences are tens to a few hundred milliwatts, against a 10 W
module whose real constraint is high-ambient derating (section 7.5) and a
Group-Controller side where the cellular burst dominates. None of the three
variants threatens the power tree, and section 7's conclusion that the budget
**cannot be closed** is unchanged. What the comparison supplies is the item
section 7.7 and 8.10 were missing: the metering arrangement's load, its domain
and its direction of flow.

### 9.9 Host interface and the IRQ question

| Interface | Signals across the barrier | Cost / consequence | V1 suitability |
| --- | --- | --- | --- |
| SPI | CS, SCLK, MOSI toward the island, MISO back = **4** | Consumes a quad isolator's whole channel budget, so no IRQ channel is left. Usable clock set by the isolator's propagation delay rather than the IC's 5 MHz maximum *(datasheet)*, so the timing budget must be derived from both datasheets *(open)* | **Suitable** for a polled design; the practical default for the quad iso-power arrangement |
| I²C | SDA (bidirectional) and SCL = **2** | Leaves channels free, but needs a bidirectional isolator. If that isolator has no integrated DC-DC, the island supply becomes a separate part — a second barrier element | Suitable in principle (100 kHz / 400 kHz, *(datasheet)*) |
| UART | Rx and Tx = **2** | Same channel benefit as I²C. Whether this path exposes the full register set the diagnostics need is a datasheet/interface input, not assumed *(open)* | Suitable in principle |
| IRQ (either as a pin or as an event source) | One additional channel if routed | Not required for V1 — see below | **Not required**; the events remain readable as status registers |

**Why IRQ is not mandatory for V1.** (1) The measurement and reporting cadences
are configured and polled (`PR-MEASURE-002`), so the MCU already owns the timing.
(2) The diagnostic evidence is per-interval values combined over configured
confirmation windows (`D-012`), not edges. (3) The information behind the pin is
not lost without it: the device's overcurrent, overvoltage, peak, sag, no-load
and zero-crossing conditions are readable as status/event registers over
whichever interface is used *(datasheet)* — only the immediate interrupt delivery
is given up. (4) No protective function exists in V1 (`D-008`: no protective
shutdown is defined), so no sub-cycle response is required by the current
requirements. Any additional island-side control signal (for example a chip
reset) must either be generated on the island or budgeted as a channel *(open)*.

**Condition.** If a future requirement introduces a protective action or a
sub-cycle response, IRQ (or a zero-crossing output) becomes a real
channel-budget requirement and the isolator/interface choice must be replanned.
That is recorded as a trigger, not as a hidden assumption.

### 9.10 Decision criteria

| # | Criterion (from the task's decision list) | Option A | Option B | Reason |
| --- | --- | --- | --- | --- |
| 1 | Safe and defensible architecture | **Met**, with a single rated barrier and a mains-referenced island | **Met differently**, with less live circuitry and a constructed barrier | Both are defensible; A is clearer to demonstrate (9.7) |
| 2 | Compatible with the 90–305 VAC target | **Met** — divider chain and CT, per section 8.4 | **Met in principle**; the voltage element's ratio and phase must hold over the 3.4:1 range | A's scaling path is the documented one |
| 3 | Supports voltage, current, power, PF and energy | **Met** — all quantities from the IC, PF derived from P and S | **Met**, with an extra phase term in the voltage path | Phase structure (9.6) |
| 4 | Supports multi-evidence fault diagnosis | **Met** — the same evidence set; the link's health is one observable block | **Met** — the same evidence set | Neither removes the need for validity signals (9.5, fault-diagnosis row) |
| 5 | No billing-grade accuracy required | **Met** — monitoring values only; no class claimed | **Met** — same | `D-029`, `PR-MEASURE-005` |
| 6 | Realistically manufacturable | **Met** — conventional circuit, one barrier part | **Met with more new items** — a construction-dependent barrier, or extra active parts | A has fewer new qualification and assembly items (9.5) |
| 7 | Practical for Minewing to prototype | **Met**, with bench discipline for the live island | **Bench-friendly electronics**, but new characterisation work | Split: A is fewer unknowns overall; B is easier to probe (9.5) |
| 8 | No unnecessary complexity | **Met** — the IC in its conventional configuration plus one isolator | **Higher complexity** — VT plus limiting element, or amplifier plus a second isolated supply and an adaptation network | A adds the fewest new elements |
| 9 | Clear isolation boundary | **Met** — one barrier line, one component | **Less clear** — several crossings whose adequacy depends on parts and construction | 9.7 |
| 10 | Allows detailed schematic design without hidden assumptions | **Met, with a named closure list** (9.11) | **Met, with a longer list** — the voltage element's class, the bias supply's derivation, the adaptation network | A's open items are fewer and better bounded |

Criteria 2 and 5 are satisfied by both. Criterion 7 is genuinely split. The
remaining criteria favour A, but for structural reasons (barrier definition,
phase structure, number of new elements, absence of hidden assumptions) rather
than because A is "safer" or cheaper — the cost direction is **OPEN** for both.

### 9.11 Preliminary preferred direction

**PRELIMINARY PREFERRED DIRECTION — Option A: a mains-referenced ADE7953
metering island, with the host interface and the island supply crossing one
reinforced-capable iso-power barrier, and a polled interface (SPI the practical
default, no IRQ channel required for V1).**

This is a direction, not a decision: no component is selected, no interface is
frozen, and no D-number is created. It is recorded as preliminary because A-30
and the product inputs remain open, and because the closure checks below have
not been performed.

**Why A.** Four structural reasons, in order of weight: (1) it keeps the
isolation boundary as **one rated component of a class the product already
needs**, instead of a barrier constructed from sensing elements whose insulation
classes are not published as such; (2) it keeps the voltage path a resistive
divider, so the relative V/I phase stays a **single CT term that the device is
designed to measure and correct** — the criterion the PF and low-PF energy
requirements are most sensitive to; (3) it adds the **fewest new parts and new
engineering unknowns** (no voltage transformer, no isolated amplifier, no
floating high-side supply, no output-adaptation network); and (4) its interface
and power are already bounded by evidence in this repository — a four-signal SPI
fits the quad iso-power isolator candidate exactly, and the island's ~30 mW fits
that candidate's isolated output by a wide margin.

**Closure checks before this becomes a decision.**

1. The barrier component is available with **confirmed** reinforced
   certification and a working voltage/surge rating that suits the declared
   working voltage (section 6.5 records the candidate's certification status as
   unconfirmed).
2. The isolator's integrated isolated supply meets the metering IC's supply
   tolerance and noise requirements directly — or the design accepts a
   post-regulator, which must be counted as an island part and as a thermal item.
3. The island's construction and distances satisfy the class distances that
   A-30 fixes, including around the divider, the burden and the crystal.
4. The SPI timing budget is derived from the IC's timing and the isolator's
   propagation delay.
5. The polling cadence covers the IC's energy-register behaviour (roll-over),
   which together with the maximum measurable power sizes the read interval.
6. The island's presence does not conflict with the enclosure, installation or
   thermal concept.

**Conditions that would move the recommendation to option B.** If the required
mains-referenced distances cannot be realised in the enclosure; if no
iso-power barrier is obtainable with confirmed reinforced certification and
adequate isolated-output quality; if the product concept forbids active
mains-referenced electronics beyond the existing module; or if safe access to
the metering electronics during build and service is made a hard requirement.
In those cases the **passive** variant is the more attractive part of option B
(no live bias island), accepting a load-dependent phase term and a continuous
mains-side dissipation, while the **active** variant keeps the phase and
magnitude performance but needs its own floating supply, a third barrier element
and an adaptation network.

**Conditions that would reopen the third option** (a different front end,
section 9.4): if the interface cannot be isolated within the available channel
and power budget; if the island's switching supply proves incompatible with the
accuracy target after mitigation; if the current sensor changes class for other
reasons; or if a later accuracy requirement makes the MCU-side arithmetic
(and therefore an isolated-ADC front end) the better fit.

### 9.12 What remains blocking

The ranked input list in section 8.13 remains the master list; this study
changes two of its entries and confirms the rest.

| Item | Status after this study |
| --- | --- |
| Front-end placement (section 8.13 input 1) | Direction identified (9.11), still **OPEN** as a decision and still **coupled to A-30** |
| Host interface and isolator channel budget (input 16) | **Narrowed**: SPI with polled status fits the quad iso-power arrangement; IRQ is not required for V1 (9.9). The final interface and isolator variant remain OPEN |
| All other inputs (current data, CT ratio/burden, divider values, accuracy target, energy source of record, PF definition, calibration, protection, filtering) | Unchanged and still open |

Additional items this study raises, all **OPEN**: the isolator's input current
and light-load efficiency at the metering load; the isolation barrier's
certification confirmation; the island's supply quality against the metering
IC's tolerance; the polling cadence against the energy-register behaviour; and
the cost comparison, which needs quotations rather than estimates.

No class, distance, PE treatment, component selection or accuracy figure is
recorded by this section, and A-30 remains exactly where section 6 left it.

## 10. Component status summary

| Item | Status |
| --- | --- |
| Components in sections 2 and 3 | Engineering candidates |
| Function blocks in section 4 | Not selected |
| Production-frozen selection | None |
| Software dependency on specific components | None |
| Schematic / PCB design | Not started |
| Component qualification | Not started |
| Safety class and isolation boundary (A-30) | **Undecided** — preliminary analysis in section 6; still gates schematic capture |
| Power-tree budget | **Not closed** — preliminary analysis, load tables and the prioritised closure list are in section 7; no margin is claimed |
| Measurement-chain design | **Not frozen** — analysis and ranked inputs are in section 8; the architecture comparison and the preliminary preferred direction (option A, one iso-power barrier, polled interface) are in section 9; still coupled to A-30 |

## 11. Validation items deferred to hardware

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

## 12. Related documents

* [architecture.md](architecture.md) — where these functions sit in the system.
* [validation.md](validation.md) — open engineering items and the digital/physical boundary.
* [design_decisions.md](design_decisions.md) — the decisions that constrain the hardware.
