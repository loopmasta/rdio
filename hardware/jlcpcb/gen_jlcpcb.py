#!/usr/bin/env python3
"""Builds the JLCPCB order files for the boards of this repository from their KiCad boards.

Usage (from the repository root):  python3 -I hardware/jlcpcb/gen_jlcpcb.py [radio] [vhf] [uhf]      (no argument = all three)

For every board it runs kicad-cli (gerbers, drill files, position file) and writes, next to the output:
  gerber/            the gerber and drill files, one per layer
  <name>-gerber.zip  the same files in one archive, ready to upload
  bom.csv            bill of materials of the parts JLCPCB assembles
  cpl.csv            their positions (component placement list)
Only SMD chips are assembled. Electrolytic capacitors, the SMA connectors, the DevKit's header pins and the radio module are soldered by hand.
Parts marked DNP are left out.

Output folders: hardware/jlcpcb/radio/ for the carrier board, hardware/jlcpcb/filters/<band>/ for the filters.
Needs KiCad 10 (kicad-cli); set KCLI if it is not in the usual place.
"""
import csv, glob, os, re, shutil, subprocess, sys, tempfile, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KCLI = os.environ.get("KCLI") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"

BOARDS = {   # name: (board file, output folder, name of the gerber archive)
    "radio": ("hardware/radio/rdio.kicad_pcb", "hardware/jlcpcb/radio", "rdio-gerber.zip"),
    "vhf": ("hardware/filter/vhf/rdio-filter-vhf.kicad_pcb", "hardware/jlcpcb/filters/vhf", "rdio-filter-vhf-gerber.zip"),
    "uhf": ("hardware/filter/uhf/rdio-filter-uhf.kicad_pcb", "hardware/jlcpcb/filters/uhf", "rdio-filter-uhf-gerber.zip"),
}
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

# LCSC part numbers by (value, footprint). An empty entry in the BOM means: no number chosen yet.
# Check every number in JLCPCB's parts library before you order (stock, package and value).
LCSC = {
    ("1uF", "C_0603_1608Metric"): "C15849",       # Samsung CL10A105KB8NNNC, 1 uF X5R 50 V
    ("100nF", "C_0603_1608Metric"): "C14663",     # Yageo CC0603KRX7R9BB104, 100 nF X7R 50 V
    ("33nF", "C_0603_1608Metric"): "C21117",      # Samsung CL10B333KB8NNNC, 33 nF X7R 50 V
    ("10k", "R_0603_1608Metric"): "C25804",       # UNI-ROYAL 0603WAF1002T5E, 1 %
    ("100k", "R_0603_1608Metric"): "C25803",      # UNI-ROYAL 0603WAF1003T5E, 1 %
    ("1k", "R_0603_1608Metric"): "C21190",        # UNI-ROYAL 0603WAF1001T5E, 1 %
    ("0R link", "R_0603_1608Metric"): "C21189",   # UNI-ROYAL 0603WAF0000T5E, 0 ohm
}
# Looked up on LCSC (product data of each number) on 2026-11-16. The filter boards have no numbers yet: the inductor series is still to be chosen
# (see hardware/filter/README.md).
SMD = ("C_", "R_", "L_", "D_")


def run(*args):
    subprocess.run([KCLI, *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build(name):
    pcb, out, zipname = (os.path.join(ROOT, p) if i < 2 else p for i, p in enumerate(BOARDS[name]))
    gerber = os.path.join(out, "gerber")
    shutil.rmtree(gerber, ignore_errors=True)
    os.makedirs(gerber)
    run("pcb", "export", "gerbers", "--no-protel-ext", "-l", LAYERS, "-o", gerber + "/", pcb)
    run("pcb", "export", "drill", "--format", "excellon", "--drill-origin", "absolute", "--excellon-zeros-format", "decimal",
        "--excellon-units", "mm", "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", "-o", gerber + "/", pcb)
    pos = os.path.join(tempfile.mkdtemp(), "pos.csv")
    run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", pos, pcb)

    rows = [r for r in csv.DictReader(open(pos)) if r["Package"].startswith(SMD) and "DNP" not in r["Val"].upper()]
    rows.sort(key=lambda r: (r["Ref"][0], int(re.sub(r"\D", "", r["Ref"]) or 0)))
    with open(os.path.join(out, "cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            w.writerow([r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm',
                        "Top" if r["Side"] == "top" else "Bottom", f'{float(r["Rot"]) % 360:g}'])
    groups = {}
    for r in rows:
        groups.setdefault((r["Val"], r["Package"]), []).append(r["Ref"])
    with open(os.path.join(out, "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, pkg), refs in groups.items():
            w.writerow([val, ",".join(refs), pkg, LCSC.get((val, pkg), "")])
    with zipfile.ZipFile(os.path.join(out, zipname), "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(glob.glob(os.path.join(gerber, "*"))):
            if p.endswith((".gbr", ".drl", ".gbrjob")) and "drl_map" not in p:
                z.write(p, os.path.basename(p))
    missing = sorted(f"{val} {pkg}" for (val, pkg) in groups if (val, pkg) not in LCSC)
    print(f"{name}: {len(rows)} parts in {len(groups)} lines, {len(os.listdir(gerber))} gerber/drill files" + (f"; no LCSC number yet: {', '.join(missing)}" if missing else ""))


if __name__ == "__main__":
    for b in sys.argv[1:] or list(BOARDS):
        build(b)
