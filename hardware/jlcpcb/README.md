# Order files for JLCPCB

Gerber, drill, bill of materials and placement files for the three boards of this repository:

| Folder | Board | Source | Size |
|---|---|---|---|
| `radio/` | carrier board | [../radio](../radio/README.md) | 57.4 × 25.5 mm, 2 layers, 1.6 mm |
| `filters/vhf/` | 2 m low-pass filter | [../filter](../filter/README.md) | 38.6 × 12.4 mm, 2 layers, 1.6 mm |
| `filters/uhf/` | 70 cm low-pass filter | [../filter](../filter/README.md) | 35.0 × 12.4 mm, 2 layers, 1.6 mm |

Every folder has:

- `*-gerber.zip`: the gerber and drill files in one archive, ready to upload (the loose files are in `gerber/`),
- `bom.csv`: the bill of materials of the parts JLCPCB assembles (Comment, Designator, Footprint, LCSC Part #),
- `cpl.csv`: where those parts go (Designator, Mid X, Mid Y, Layer, Rotation).

## What is assembled, what is soldered by hand

JLCPCB assembles the SMD chips only (resistors, ceramic capacitors, inductors). **Soldered by hand:** the electrolytic capacitors of the carrier board (C2, C6), the SMA connectors, the two 19-pin DevKit headers and the radio module. Parts marked DNP (FB1 and C8 on the carrier board) are not in the files.

On the carrier board all the assembled parts are on the **top** side, so order assembly for the top side (the usual choice). The parts are 0603 resistors and capacitors without polarity, so a rotation that is off by 180° does no harm.

## LCSC part numbers

### Carrier board

The numbers were looked up in LCSC's product data on 2026-11-16 (value, package and tolerance checked). Check them again in JLCPCB's parts library before you order: stock and basic or extended status change.

| Value | LCSC | Part |
|---|---|---|
| 1 µF 0603 | C15849 | Samsung CL10A105KB8NNNC, X5R, 50 V |
| 100 nF 0603 | C14663 | Yageo CC0603KRX7R9BB104, X7R, 50 V |
| 33 nF 0603 | C21117 | Samsung CL10B333KB8NNNC, X7R, 50 V |
| 100 k 0603 | C25803 | UNI-ROYAL 0603WAF1003T5E, 1 % |
| 10 k 0603 | C25804 | UNI-ROYAL 0603WAF1002T5E, 1 % |
| 1 k 0603 | C21190 | UNI-ROYAL 0603WAF1001T5E, 1 % |
| 0 Ω 0603 (R9) | C21189 | UNI-ROYAL 0603WAF0000T5E |

### Filter boards

| Value | Board | LCSC | Part |
|---|---|---|---|
| 22 pF 0402 (C1, C4) | 2 m | C70464 | Samsung CL05C220JB5NNNC, C0G, ±5 %, 50 V |
| 39 pF 0402 (C2, C3) | 2 m | C86288 | Samsung CL05C390JB5NNNC, C0G, ±5 %, 50 V |
| 68 nH 0603 (L1, L3) | 2 m | C86135 | Murata LQW18AN68NG00D, wirewound, ±2 % |
| **82 nH 0603 (L2)** | 2 m | **open** | see below |
| 8.2 pF 0402 (C1, C4) | 70 cm | C318599 | Samsung CL05C8R2CB5NNNC, C0G, ±0.25 pF, 50 V |
| **13 pF 0402 (C2, C3)** | 70 cm | **open** | see below |
| 22 nH 0402 (L1, L3) | 70 cm | C86129 | Murata LQW15AN22NG00D, wirewound, ±2 % |
| 27 nH 0402 (L2) | 70 cm | C98057 | Murata LQW15AN27NG00D, wirewound, ±2 % |

Two parts are still open, so those two `bom.csv` lines have an empty LCSC column:

- **82 nH, 0603 (2 m board, L2).** The Murata LQW18AN82NG00D is not in LCSC's library under any number I could find. The two 82 nH ±2 % 0603 parts that are listed (Johanson L-14W82NGV4E, C3911476, and Cal-Chip WB0603T82NSG, C3222451) had no stock on 2026-11-16, and the Chilisin CLH1608T-82NJ-S (C180933) has a Q of only 12 at 100 MHz, which would cost more than 1 dB. Buy the 82 nH inductor elsewhere (for example the Murata LQW18AN82NG00D, or a part of Coilcraft's 0603HP series, from a distributor) and solder it by hand, or pick another source.
- **13 pF, C0G, 0402 (70 cm board, C2 and C3).** No 13 pF part turned up. The nearest values in LCSC's library are 12 pF (FH 0402CG120J500NT, C1547) and 15 pF (Samsung CL05C150JB5NNNC, C86285). The simulation of the filter README (`hardware/filter/tools/filter_sim.py`, with the inductor Q set to 40 as for the Murata parts) gives for the 70 cm filter:

  | C2 = C3 | Loss in band | Return loss | 2nd harmonic |
  |---|---|---|---|
  | 13 pF (design) | 0.99 dB | 26.5 dB | 62.9 dB down |
  | 12 pF | 0.93 dB | 18.9 dB | 60.5 dB down |
  | 15 pF | 1.48 dB | 12.0 dB | 67.2 dB down |

  12 pF would be usable (return loss 19 dB, 2nd harmonic 2 dB less); 15 pF would not (return loss 12 dB). Either is a change to the design, so none is in the BOM.

**Inductor Q.** The simulation assumes inductors with a Q of 70 (2 m) and 90 (70 cm), Coilcraft-type parts. The Murata LQW parts are the high-Q wirewound chips I found in LCSC's library, but their minimum Q is lower (distributor listings give 25 at 250 MHz for the 22 nH and 27 nH parts and 34 at 150 MHz for 82 nH; check the Murata datasheets). The same simulation shows what that costs:

| Inductor Q | 2 m loss | 70 cm loss |
|---|---|---|
| 70 / 90 (design) | 0.56 dB | 0.50 dB |
| 50 | 0.76 dB | 0.82 dB |
| 40 | 0.92 dB | 0.99 dB |
| 30 | 1.20 dB | 1.29 dB |
| 25 | 1.42 dB | 1.53 dB |

Return loss and the rejection of the 2nd harmonic hardly change (2 m: 52 dB, 70 cm: 63 dB down at every Q), so the price is insertion loss: at Q 30 about a quarter of the transmit power is lost in the filter. Measure the finished filters with a NanoVNA, as the filter README says.

## Regenerating the files

After a change to a board, run from the repository root (needs KiCad 10, set `KCLI` if `kicad-cli` is not in the usual place):

    python3 -I hardware/jlcpcb/gen_jlcpcb.py            # all three boards
    python3 -I hardware/jlcpcb/gen_jlcpcb.py radio      # or just one: radio, vhf, uhf

The script exports the gerbers, the drill files and the position file with `kicad-cli`, then writes `bom.csv`, `cpl.csv` and the archive. The LCSC numbers are in the table at the top of the script.
