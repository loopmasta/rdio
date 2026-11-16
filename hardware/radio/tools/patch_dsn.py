"""Patches a Specctra DSN exported by KiCad before Freerouting reads it.
Usage: patch_dsn.py in.dsn out.dsn [--plane In1.Cu] [--only-nets VBAT,/VIN_ESP] [--clearance 230]
  --plane       make that layer a GND power plane (the router keeps wires off it; vias still pass through)
  --only-nets   route only these nets (every other net is dropped from the network section, its pads stay as obstacles)
  --clearance   router clearance in um (a little above the DRC rule, so the DRC does not trip on rounding)
"""
import argparse, re
ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--plane"); ap.add_argument("--only-nets"); ap.add_argument("--clearance", type=int)
a = ap.parse_args()
s = open(a.src).read()
if a.plane:
    old = f"(layer {a.plane}\n      (type signal)"
    assert old in s, "layer not found: " + a.plane
    s = s.replace(old, f"(layer {a.plane}\n      (type power)")
    pts = re.search(r"\(path pcb 0\s+([-\d\s]+)\)", s).group(1).split()      # board outline
    s = s.replace("    (boundary\n", f"    (plane GND (polygon {a.plane} 0  {' '.join(pts)}))\n    (boundary\n", 1)
if a.only_nets:
    keep = set(a.only_nets.split(","))
    i = s.index("  (network"); j = s.index("    (class ", i)
    blocks = re.findall(r"    \(net .*?\n    \)\n", s[i:j], re.S)
    kept = [b for b in blocks if b.split()[1].strip('"') in keep]
    assert kept, "none of the nets found"
    s = s[:i] + "  (network\n" + "".join(kept) + s[j:]
if a.clearance:
    s = s.replace("(clearance 200)", f"(clearance {a.clearance})")
open(a.dst, "w").write(s)
