# Design notes: rdio carrier board

Background for the board in this folder: where the values come from, what was measured, and what is still open. The short description is in [README.md](README.md).

These notes are based on the text of the datasheet (`SA818S V1.8.pdf`). The block diagram and the typical-application schematic on pages 4 and 5 are images; they still have to be compared with the circuit (see the open points at the end).

## Datasheet numbers

| Item | Value |
|---|---|
| Supply (VBAT) | 3.3 – 5.5 V (RF power specified at 4.0 V) |
| Current | RX 60 mA, TX high 650–750 mA, TX low 450–550 mA, sleep ≤ 1 µA |
| AF_OUT | 700 mV amplitude, 200 Ω output impedance |
| MIC_IN | nominal modulation at about 10 mV (1.5 / 2.5 kHz deviation test) |
| Serial | 9600 8N1, AT commands, CR LF |
| PTT | 0 = TX, 1 = RX |
| PD | 0 = power down, 1 = normal |
| H/L | open = high power, low = low power. **Never drive it high, never tie it to VDD** |
| Pin 1 | the datasheet calls it "Audio ON" (low while the module is active or receiving). It acts as squelch / carrier detect and is called SQ here |
| RXD | pull RXD low before sleep (PD low) to avoid leakage |

## Audio

**AF_OUT to the ESP32 ADC (C1 1 µF, 100 k / 100 k).** The source is 200 Ω into a 50 k bias node: no loading, and 1 µF with 50 k gives a 3 Hz high-pass. 700 mV amplitude around 1.65 V stays inside the ADC range. It is not known whether 700 mV is peak or peak to peak: measure it with the module volume at the chosen level (`AT+DMOSETVOLUME` 1–8). Wiring: AF_OUT (pin 3) → C1 → node B → GPIO34.

**GPIO25 (DAC) to MIC_IN (about 40 dB attenuation).** The DAC signal is about 0.7 V peak (60 codes × 12 mV) on 1.6 V DC, and MIC_IN wants roughly 10 mV. A direct connection would over-deviate and distort. The network: GPIO25 → C4 1 µF (DC block) → R3 100 k in series → MIC_IN node, with R4 1 k (fixed) to ground at that node and C5 33 nF across it.

- ratio about 1/100: 0.7 V becomes about 7 mV,
- 33 nF with about 1 k gives a corner near 4.8 kHz, removes the 40 kHz DAC stepping, and costs about 0.5 dB at 1750 Hz,
- the MIC_IN input impedance and internal bias are not in the datasheet text. If it is a few kΩ, scale the shunt up or the series resistor down and check again,
- check the 1750 Hz deviation (about 3 kHz) on a receiver or an SDR and change R4 if needed.

Module filters: `AT+SETFILTER` (pre-emphasis, high-pass, low-pass); `AT+SETTAIL=0` for repeater use.

## Pin assignment

Constraints: ADC1 only (GPIO34), the DAC on GPIO25, no strapping pins (0, 2, 5, 12, 15), no flash pins (6–11), no UART0 (1, 3), and none of the header neighbours of GPIO34 and GPIO25 (35, 36, 39, 26, 27, 32, 33). The DevKit has a WROOM module, so GPIO16 and GPIO17 are free (they would not be on a WROVER with PSRAM).

| SA818S pin | Signal | ESP32 | Direction | Boot and fail-safe parts |
|---|---|---|---|---|
| 16 RXD | UART in | GPIO17 (UART2 TX) | ESP → module | none |
| 17 TXD | UART out | GPIO16 (UART2 RX) | module → ESP | direct (works without a series resistor with VBAT at 5 V; not measured with a meter) |
| 5 PTT | TX request | GPIO21 | open-drain output | **10 k pull-up to 3.3 V**: floating, crash or reset = receive |
| 6 PD | power down | none | tied directly to 3.3 V | the module is always on; this saves a GPIO and a part |
| 7 H/L | power level | GPIO19 | open-drain output (low = low power, release = high power) | software controlled, no jumper, no pull-up. At boot it floats (= high power), but PTT is pulled high (receive), so it cannot transmit; the firmware has to drive H/L low before the first PTT |
| 1 SQ | carrier detect | GPIO22 | module → ESP (input) | direct (works without a series resistor) |

PTT and the other control signals come from the upper right header pins and the UART from the lower ones, so no tracks cross.

Firmware: create the UART driver and the SQ interrupt from a task pinned to core 0, so they do not touch the audio interrupts on core 1. SQ can also be polled every 20 ms.

## Power

- Do **not** power the module from the DevKit's 3.3 V pin (AMS1117, about 800 mA, shared with Wi-Fi peaks).
- VBAT comes from a 5 V supply rated at least 2 A (or a single Li-ion cell at 4.2 V), with a common ground with the ESP32. USB 500 mA from a computer browns out in high-power TX.
- At VBAT: C6 100 µF (at least 10 V, 16 V used, SMD electrolytic 6.3 mm diameter, 5.4 mm tall in the FOSAN part; the footprint is the 6.3 × 5.8 mm one; it fits the 7–8 mm gap under the DevKit). 220 µF was first planned but is not available at 16 V; the dip on a 0.75 A TX step is about twice as large with 100 µF (estimate: 0.3 V becomes about 0.5 V), which C7 and the module's own regulation have to absorb: check VBAT with a scope in high-power TX and C7 100 nF close to pins 8 and 9. Ripple shortens the range (datasheet FAQ). Expected supply dip in a 0.75 A TX step: about 0.3 V (estimate).
- **FB1 and C8 are marked DO NOT POPULATE.** The DevKit's VIN is fed through the 0 Ω link R9, in parallel with FB1. To try the filter, fit FB1 and C8 and remove R9. FB1 is an SMD 0805 ferrite bead, at least 1 A (2 A preferred), and C8 is a 100 µF SMD capacitor, at least 10 V, on the ESP32 side. A bead mostly filters noise in the MHz range; for slow current steps the 100 µF does the work. If Wi-Fi still drops, replace FB1 with about 0.5 Ω (0.3 A gives about 0.15 V drop). Build without them first.
- No USB-C jack on the carrier: 5 V comes from the DevKit's own USB-C through its VIN pin (pin 19). The radio draws up to 0.75 A in TX, all of it through the DevKit's USB path, its VIN pin and the USB source: use a source rated at least 1 A and check the DevKit's input protection.
- Check the DevKit's VIN and USB backfeed behaviour before powering both from USB and an external 5 V at the same time.
- Start the bench tests at low power (the firmware drives H/L low).

## RF

Use a 50 Ω antenna or a dummy load on pin 12 **before the first transmission**. Keep the antenna away from the ESP32's antenna and the analog wiring. Transmitting needs the proper amateur licence and an allowed frequency.

## SA818S symbol and footprint

- Symbol U2 follows the module's real pin layout (datasheet pinout, top view): pins 7 to 1 along the top (left to right), 12 to 18 along the bottom (left to right), 8 to 11 down the left side (VBAT, GND, GND, NC).
- Footprint `rdio:DRA818_SA818` (`rdio.pretty/DRA818_SA818.kicad_mod`, library table `fp-lib-table`): 35.6 × 19.0 mm, castellated pads 1.8 mm, pitch 4.45 mm, first top and bottom pad 4.5 mm from the left edge, left pads at 2.66 / 6.96 / 12.04 / 16.34 mm from the top edge. Pads extend 1.0 mm beyond the module edge for soldering.
- The datasheet drawing shows two large unnumbered pads on the right edge (about 6.2 mm tall). They are not in the footprint or the symbol (the datasheet does not say what they are, probably ground or shield); the module is held by its 17 signal pads.
- The pad pattern is the one of the earlier rdio carrier board, which was built and probed, and it was confirmed against the real module. It is the mirror of the pattern read from the datasheet pinout figure in a first version of this board, which was therefore wrong. The module is mounted turned by 180° so its ANT pad faces the SMA connector. The NC pads are not drawn (KiCad notes that pin 11 has no pad, which is harmless).

## The board

- 57.4 × 26.0 mm, 2 layers, GND pours on both layers stitched with about 80 GND vias (grid every 3 mm, a fence beside the audio chain, a via for every separate piece of pour). Seen from the top (the DevKit side): top row = DevKit pins 1 to 19, bottom row = pins 38 to 20, antenna end at the right, USB end at the left. The generator scripts build the board the other way round (module and SMA on the top side, small parts on the bottom, antenna end at the left); `tools/flip_pcb.py` turns it over as the last step, so the text below about the generator (`y = −9.1`, the footprint layers) refers to that unflipped frame.
- A 4-layer variant with a solid GND plane on In1.Cu exists too (`LAYERS=4 hardware/radio/tools/make_pcb.sh`). Order it as 4-layer 1.6 mm with about 0.2 mm prepreg between F.Cu and In1.Cu (for example JLCPCB JLC04161H-7628); its antenna trace is 0.4 mm (about 50 Ω).
- Bottom side: only the SA818S and the SMA edge connector. Top side, in the 7–8 mm gap under the DevKit (confirmed on the real DevKit): C6 100 µF, C2 and C8 100 µF electrolytics, the 0603 resistors and capacitors, and FB1 (0805).
- Height rule for the electrolytics: part height plus about 1 mm. With the 7.5 mm gap under the DevKit, C6 (5.8 mm) has 1.7 mm and C2 / C8 (5.4 mm) have 2.1 mm to spare; a 6.3 × 7.7 mm can would not fit.
- C6 was once a 470 µF 8 × 10 part on the module side at the SMA end. It is now 100 µF 16 V (6.3 × 5.8 mm footprint) under the DevKit near module pin 8, and the board is 3 mm shorter.
- Routed with Freerouting (power 0.5 mm, signals 0.25 mm, vias 0.6 / 0.3 mm). The 0.8 mm antenna trace (SMA pad to module pin 12, straight along y = −9.1, about 9.8 mm) is drawn by hand. Copper on the module side is kept off the module's underside test pads (two rectangles), and there is no pour on that side under the module body.
- Confirmed against real parts: the SA818S pad pattern, the DevKit pin-row spacing, the room at the DevKit's USB-C end, and the SMA-KE measurements.
- Risk: Wi-Fi range was a concern because the SA818S sits above the DevKit's antenna end. The DevKit and its antenna are about 8 mm below the carrier, and this was judged fine. RF coupling between the ESP32 and the SA818S is still open, see the section on interference below.

## SMA connectors: J2 (KooingTech SMA-KE, edge mount) or J3 (right angle, on top)

The board has two footprints for the antenna connection, both on the antenna net (`Net-(J2-In)` and GND). The builder fits one of them. The schematic has both symbols (J3 was added at the end of `gen_schematic.py`, so no earlier id changed), and a note says to fit one.

- **J3** is the BAT Wireless BWSMA-KWE-Z001 (LCSC C496551, through hole, right angle). The footprint is KiCad's `Connector_Coaxial:SMA_BAT_Wireless_BWSMA-KWE-Z001` copied into `rdio.pretty` (centre pad 2.3 mm, four ground pads 2.2 mm, drill 1.4 mm, pads 5.1 mm apart), without its silkscreen box, which would run over the pads of J2. It is placed on the DevKit side (the bottom side in the generator, where the passives are), turned by 90° so that the barrel points off the antenna end, at x = −29.0, y = −9.1 (`J3_X` in `build_pcb.py`). That puts the centre pin on the antenna trace and the outer ground legs 0.5 mm inside the board edge; its body (7.8 mm square, assumed) stays clear of the DevKit headers, and it is on the other side of the board from the radio module.
- The ground legs are 2.55 mm either side of the antenna line, and that line is only 3.6 mm from the long edge, so the **long edge on the antenna-track side is 0.5 mm further out** than the other (`HALF_N = 13.2` in `build_pcb.py`, board height 26.0 mm instead of 25.5 mm). The extra strip is carried by the GND pours.
- The two footprints overlap by design (same pads, same nets). `rdio.kicad_dru` tells the DRC not to report their overlapping courtyards (and J3's outer leg, 0.05 mm inside the module's courtyard, which is on the other side of the board).
- The J3 model in `gen_3d_placeholders.py` is a placeholder (KiCad models use y up and the board y down, so the barrel is along +y in the model file although it is at −y in the footprint; the first version had it the wrong way, with the barrel pointing over the board): a 7.82 mm cube with the same hollow barrel as J2's model; the body height and the barrel length are assumptions. Check them against the datasheet before relying on the clearance to the DevKit.
- Showing and hiding in KiCad's 3D viewer: a footprint cannot sit on a layer of its own, so the two connectors carry different footprint flags that the viewer can switch separately. **J2 is marked "Do not populate"** (the default build uses J3; FB1 and C8 are DNP too), **J3 is marked "Exclude from position files"** (it is hand soldered; nothing else has that flag). Hide "Do not populate" footprints to see J3 alone, hide "Exclude from position files" ones to see J2 alone (with DNP shown). The README pictures are rendered with DNP hidden, so they show J3 only. To build with J2 instead, clear the DNP flag of J2, mark J3 DNP and update the schematic the same way.

### J2: KooingTech SMA-KE, edge mount

- There is no KooingTech drawing or KiCad library. The footprint and the model were built from the generic SMA-KE dimension drawing (same part type, matching the real part according to measurements; the listing of the part only says SMA female edge mount, 50 Ω, brass, 1.6 mm board, 0–6 GHz): 4 legs 0.9 mm wide, 4 mm long, 4.2 mm gap (6.0 mm outer), PCB slot 1.7 mm, centre pin 0.8 mm, flange 6.5 × 6.5 × 1.5 mm, thread 1/4-36 UNS 8 mm long, overall 13.5 mm.
- Footprint: origin at the board edge on the centre pin; RF pad (1.0 × 4.5 mm) and two ground pads (1.5 × 4.5 mm, 5.1 mm apart) on the top layer of the footprint, two ground pads on its bottom layer, all recessed 0.25 mm from the edge (on the finished board the footprint sits on the bottom side, so these layers are swapped there). The signal pin side is assumed to be the top of the footprint: flip the footprint if the real part is the other way round.
- Measured on the real part: leg gap 4.2 mm (6.0 mm outer), slot 1.7 mm, leg length 4 mm, overall 13.5 mm, centre pin side.
- In the board the RF pad is level with the module's antenna pad (y = −9.1), so the antenna trace is a short straight line; the ground pads sit at y = −11.65 and −6.55 (the lower one merges into the ground pour).

## SA818S assembly aid (bottom silkscreen)

- Pin numbers 1 to 18 sit inside the module outline next to every pad (upright when the bottom side is turned towards you), and an open ring (2.3 mm across) marks the ring on the module's top: put the module's ring over the board's ring. The position was measured from a photo of the real module: the ring is almost centred across the module, about 3.4 mm from the short edge opposite the four-pad edge (pins 8 to 11), at footprint (−14.45, −0.65). With the SMA connector on the left it is in the right half of the module outline, just above the middle line.
- Both are generated by `tools/build_pcb.py` (they are not part of the footprint), so they follow the module placement. They are hidden under the module once it is soldered on.

## 3D placeholders (`rdio.3dshapes`, generated by `tools/gen_3d_placeholders.py`)

- Simple boxes to judge the finished board in KiCad's 3D viewer, not accurate models. DevKit model: two 1 × 19 pin headers (black, 2.54 × 48.26 mm, 5 mm tall) soldered to the carrier with their pins through it, the DevKit's own 2.5 mm sockets (grey, same footprint) plugged onto them (5 + 2.5 = the 7.5 mm gap), the DevKit board (48.26 × 25.4 × 1.6 mm) on top of the sockets with its module (19 × 18 × 3.1 mm shield plus the 6.5 mm antenna end) and USB-C (7.3 × 8.94 × 3.2 mm) standing on it. SA818S model: 35.6 × 19 mm PCB plus a 35 × 18.4 mm shield, 3.2 mm tall. SMA model: four legs, centre pin, 6.5 mm square flange and a 6.35 mm barrel that is hollow, with the white insulator recessed 1 mm and a socket-type centre contact (all faces point outwards; the first version had them inverted, which showed as a black, hollow part).
- Assumptions: header 5 mm plus socket 2.5 mm (measured on the real DevKit), the DevKit board directly above the sockets, USB-C 1 mm beyond the board edge. The position of the DevKit's parts is not checked.

## Interference between the ESP32 and the SA818S (copper as a shield)

- Goal: keep ESP32 noise (Wi-Fi at 2.4 GHz, digital edges, the DAC) out of the SA818S MIC_IN, and the 1 W 433 MHz transmitter out of the ESP32 (ADC input, UART, control lines).
- A first 2-layer board had no large copper layer: the pours covered 34 % (bottom) and 53 % (top) of the board in 4 and 7 separate pieces with 5 GND vias, and the top layer carried 273 mm of signals including the audio chain.
- The 2-layer board now (`tools/post_pcb.py`): bottom 69 % and top 74 % copper, 81 GND vias. What made the difference: the pour clearance is 0.25 mm (it was KiCad's default 0.5 mm; the design rule is 0.2 mm); the bottom pour is allowed under the SA818S body (only the two test-pad areas stay free; set `POUR_UNDER_MODULE=0` to keep the whole body free); a stitching grid every 3 mm (about λ/20 at 2.4 GHz in FR4); a via fence beside the audio chain (80 % of the audio traces are within 3 mm of a GND via, the worst 6.9 mm); and a via for every separate piece of pour, otherwise KiCad deletes it as an island.
- Still true for 2 layers: the top layer carries the signals and cuts the plane, so this is a well-stitched pour, not a solid plane.
- 4-layer option (`LAYERS=4`): In1.Cu is a solid GND plane (66 % fill, the rest is the drilled DevKit header holes), with signals on F.Cu, In2.Cu and B.Cu; a solid plane lies under 100 % of the antenna trace and MIC_A, 81 % of MIC_B, 76 % of NODE_B, 68 % of DAC_OUT and 57 % of AF_OUT. It is routed in two stages (the long VBAT and VIN_ESP runs first) with `patch_dsn.py`.
- What copper cannot fix (not done; ask before adding parts):
  1. The 433 MHz antenna is on the SMA at the same end as the DevKit's Wi-Fi antenna: a whip on the connector sits 1–3 cm from it. A short coax pigtail or an antenna mounted away from the board helps more than any copper.
  2. 2.4 GHz pickup into MIC_IN: C5 (33 nF) is useless above about 20 MHz. A small NP0 capacitor (47–100 pF) across R4 at the module pin would bypass RF. The same idea applies at the ESP32 ADC input (NODE_B, 100 pF to GND at the DevKit pin) and with a series 100 Ω and 100 pF on PTT, H/L, SQ and the UART against 433 MHz pickup. It was decided to leave the circuit as it is.
  3. Transmit power: use low power (H/L low) on the bench.

## Open points to verify at the bench

1. The typical-application schematic on page 5 of the datasheet: the MIC_IN coupling and the AF_OUT bias against the values above.
2. The idle and active voltage levels of pin 1.
3. The AF_OUT amplitude (peak or peak to peak) at each volume setting.
4. The MIC_IN impedance, then change R4 (1 k) so that 1750 Hz gives the right deviation.
