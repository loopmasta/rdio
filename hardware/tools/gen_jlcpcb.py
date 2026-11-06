#!/usr/bin/env python3
"""Build the JLCPCB order files from KiCad's exports.

Usage: gen_jlcpcb.py radio|vhf|uhf POS.csv
Needs the gerbers and drill files already exported into the board's folder
(`kicad-cli pcb export gerbers` / `drill`) and the position file (`kicad-cli pcb export pos`). Writes bom.csv, cpl.csv and a gerber zip next to them:
  hardware/jlcpcb/radio/            the carrier board
  hardware/jlcpcb/filters/<band>/   the 2 m and 70 cm filters
Only SMD chips are assembled; the SMA connectors, the DevKit headers and the radio module are hand-soldered.
"""
import csv, os, zipfile, glob, sys

board, POS = sys.argv[1], sys.argv[2]
OUT = "hardware/jlcpcb/radio" if board == "radio" else f"hardware/jlcpcb/filters/{board}"
# LCSC part numbers: check each one in JLCPCB's parts library before ordering.
# The filter parts have none: the inductor series is still to be chosen (see filter/README.md).
LCSC = {
    ("10k", "R_0603_1608Metric"): "C25804",
    ("22k", "R_0603_1608Metric"): "C31850",
    ("220R", "R_0603_1608Metric"): "C22962",
    ("1uF", "C_0603_1608Metric"): "C15849",
    ("220nF", "C_0603_1608Metric"): "C23630",
    ("100nF", "C_0603_1608Metric"): "C14663",
    ("47uF", "C_1206_3216Metric"): "C96123",
    ("B5819W", "D_SOD-123"): "C8598",
}
SMD = ("C_", "R_", "L_", "D_")
rows = [r for r in csv.DictReader(open(POS)) if r["Package"].startswith(SMD) and "DNP" not in r["Val"]]
rows.sort(key=lambda r: (r["Ref"][0], int(r["Ref"][1:])))

with open(f"{OUT}/cpl.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in rows:
        w.writerow([r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm',
                    "Top" if r["Side"] == "top" else "Bottom", f'{float(r["Rot"]) % 360:g}'])

groups = {}
for r in rows:
    groups.setdefault((r["Val"], r["Package"]), []).append(r["Ref"])
with open(f"{OUT}/bom.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, pkg), refs in groups.items():
        w.writerow([val, ",".join(refs), pkg, LCSC.get((val, pkg), "")])

with zipfile.ZipFile(f"{OUT}/{'rdio' if board == 'radio' else 'rdio-filter-' + board}-gerber.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(glob.glob(f"{OUT}/gerber/*")):
        if p.endswith((".gbr", ".drl")) and "drl_map" not in p:
            z.write(p, os.path.basename(p))
print(board, len(rows), "parts")
