# Order files for JLCPCB

Gerber, drill, bill of materials and placement files for the three boards of this repository:

| Folder | Board | Source | Size |
|---|---|---|---|
| `radio/` | carrier board | [../radio](../radio/README.md) | 57.4 × 25.5 mm, 2 layers, 1.6 mm |
| `filters/vhf/` | 2 m low-pass filter | [../filter](../filter/README.md) | 38.0 × 12.4 mm, 2 layers, 1.6 mm |
| `filters/uhf/` | 70 cm low-pass filter | [../filter](../filter/README.md) | 34.4 × 12.4 mm, 2 layers, 1.6 mm |

Every folder has:

- `*-gerber.zip`: the gerber and drill files in one archive, ready to upload (the loose files are in `gerber/`),
- `bom.csv`: the bill of materials of the parts JLCPCB assembles (Comment, Designator, Footprint, LCSC Part #),
- `cpl.csv`: where those parts go (Designator, Mid X, Mid Y, Layer, Rotation).

## What is assembled, what is soldered by hand

JLCPCB assembles the SMD chips only (resistors, ceramic capacitors, inductors). **Soldered by hand:** the electrolytic capacitors of the carrier board (C2, C6), the SMA connectors, the DevKit's header pins and the radio module. Parts marked DNP (FB1 and C8 on the carrier board) are not in the files.

On the carrier board all the assembled parts are on the **bottom** side, so order assembly for the bottom side (or both sides). The parts are 0603 resistors and capacitors without polarity, so a rotation that is off by 180° does no harm.

## LCSC part numbers

The numbers of the carrier board were looked up in LCSC's product data on 2026-11-16 (value, package and tolerance checked). Check them again in JLCPCB's parts library before you order: stock and basic or extended status change.

| Value | LCSC | Part |
|---|---|---|
| 1 µF 0603 | C15849 | Samsung CL10A105KB8NNNC, X5R, 50 V |
| 100 nF 0603 | C14663 | Yageo CC0603KRX7R9BB104, X7R, 50 V |
| 33 nF 0603 | C21117 | Samsung CL10B333KB8NNNC, X7R, 50 V |
| 100 k 0603 | C25803 | UNI-ROYAL 0603WAF1003T5E, 1 % |
| 10 k 0603 | C25804 | UNI-ROYAL 0603WAF1002T5E, 1 % |
| 1 k 0603 | C21190 | UNI-ROYAL 0603WAF1001T5E, 1 % |
| 0 Ω 0603 (R9) | C21189 | UNI-ROYAL 0603WAF0000T5E |

**The filter boards have no numbers yet:** the capacitors (C0G, 0402) and above all the high-Q inductors still have to be chosen, see [../filter/README.md](../filter/README.md). Their `bom.csv` files have an empty LCSC column.

## Regenerating the files

After a change to a board, run from the repository root (needs KiCad 10, set `KCLI` if `kicad-cli` is not in the usual place):

    python3 -I hardware/jlcpcb/gen_jlcpcb.py            # all three boards
    python3 -I hardware/jlcpcb/gen_jlcpcb.py radio      # or just one: radio, vhf, uhf

The script exports the gerbers, the drill files and the position file with `kicad-cli`, then writes `bom.csv`, `cpl.csv` and the archive. The LCSC numbers are in the table at the top of the script.
