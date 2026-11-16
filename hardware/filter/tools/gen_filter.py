#!/usr/bin/env python3
"""Writes the two harmonic-filter schematics (hardware/filter/vhf and hardware/filter/uhf) and the connector footprints and 3D bodies
(hardware/filter/rdio-filter.pretty and rdio-filter.3dshapes).

Component values come from filter_sim.py (hardware/filter/design.json). From the repository root:

    PYTHONPATH=/tmp/np python3 hardware/filter/tools/filter_sim.py      # only to change the design; needs numpy -> design.json
    python3 -I hardware/filter/tools/gen_filter.py                      # schematics, footprints, 3D bodies
    for b in vhf uhf; do
      kicad-cli sch export netlist --format kicadxml -o hardware/filter/$b/rdio-filter-$b.net.xml hardware/filter/$b/rdio-filter-$b.kicad_sch
      <KiCad's python> hardware/filter/tools/gen_filter_pcb.py $b                              # the board, see that file
    done

Set FILTER_DIR to write somewhere else than hardware/filter (the folder must contain design.json). Needs KiCad 10 (its stock symbol and
footprint libraries are read from the install, see sch_engine.py).
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sch_engine as eng

FILT = os.environ.get("FILTER_DIR") or os.path.join(HERE, "..")
design = json.load(open(os.path.join(FILT, "design.json")))


# ---- SMA male plug (threaded coupling nut), edge mount: same pad pattern as the stock edge-launch jack -----------
STOCK = eng.KICAD + "/footprints/Connector_Coaxial.pretty/SMA_Amphenol_132289_EdgeMount.kicad_mod"

def strip_block(text, start_token):
    """text without the parenthesised block that starts at start_token"""
    i = text.index(start_token); depth = 0; j = i
    while True:
        if text[j] == "(": depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0: break
        j += 1
    return text[:i].rstrip() + "\n" + text[j + 1:].lstrip("\n")

def box(cx, cy, cz, sx, sy, sz, col):
    return (f"Transform {{ translation {cx} {cy} {cz} children Shape {{ appearance Appearance {{ material Material {{ diffuseColor {col} "
            f"specularColor 0.4 0.4 0.4 shininess 0.4 }} }} geometry Box {{ size {sx} {sy} {sz} }} }} }}\n")

def write_plug_library():
    fp = open(STOCK).read()
    fp = fp.replace('(footprint "SMA_Amphenol_132289_EdgeMount"', '(footprint "SMA_Plug_EdgeMount"', 1)
    fp = fp.replace('"SMA_Amphenol_132289_EdgeMount"', '"SMA_Plug_EdgeMount"')
    fp = fp.replace('(tags "SMA")', '(tags "SMA male plug edge launch")')
    i = fp.index("(descr"); j = fp.index("\n", i)
    fp = fp[:i] + ('(descr "SMA male PLUG (threaded coupling nut), edge launch. Pad pattern copied from the Amphenol 132289 edge-launch jack; '
                   'check your plug\'s datasheet. 3D body is a simple model.")') + fp[j:]
    fp = strip_block(fp, "(model ")
    k = fp.rindex(")")
    fp = fp[:k] + ('\t(model "${KIPRJMOD}/../rdio-filter.3dshapes/SMA_Plug_EdgeMount.wrl"\n\t\t(offset (xyz 0 0 0))\n'
                   '\t\t(scale (xyz 0.3937008 0.3937008 0.3937008))\n\t\t(rotate (xyz 0 0 0))\n\t)\n') + fp[k:]
    lib = os.path.join(FILT, "rdio-filter.pretty"); os.makedirs(lib, exist_ok=True)
    open(os.path.join(lib, "SMA_Plug_EdgeMount.kicad_mod"), "w").write(fp)
    # 3D: flange block at the board edge, threaded nut (prism) outward, centre pin inside. mm, board top at z = 0, axis at mid-board.
    zc = -0.8
    wrl = "#VRML V2.0 utf8\n"
    wrl += box(4.0, 0, zc, 3.0, 8.0, 8.0, "0.75 0.75 0.78")                          # square flange
    wrl += eng.prism_x(5.5, 14.4, 0, zc, 4.0, "0.82 0.82 0.86")                       # coupling nut
    wrl += eng.prism_x(14.38, 14.45, 0, zc, 2.8, "0.1 0.1 0.1")                       # dark bore at the nut's end face
    wrl += eng.prism_x(5.5, 14.6, 0, zc, 0.5, "0.85 0.7 0.2", n=8)                    # centre pin
    wrl += box(4.8, 0, zc - 4.6, 3.0, 4.0, 1.2, "0.75 0.75 0.78")                    # tab under the flange
    shp = os.path.join(FILT, "rdio-filter.3dshapes"); os.makedirs(shp, exist_ok=True)
    open(os.path.join(shp, "SMA_Plug_EdgeMount.wrl"), "w").write(wrl)

write_plug_library()
open(os.path.join(FILT, "rdio-filter.pretty", "CONSMA020_062_G.kicad_mod"), "w").write(
    eng.consma_footprint("${KIPRJMOD}/../rdio-filter.3dshapes/CONSMA020_062_G.wrl"))
open(os.path.join(FILT, "rdio-filter.3dshapes", "CONSMA020_062_G.wrl"), "w").write(eng.consma_wrl())
PLUG_FP = "rdio-filter:SMA_Plug_EdgeMount"


def fmt_c(v): return "%g pF" % round(v * 1e12, 1)
def fmt_l(v): return "%g nH" % round(v * 1e9, 1)

BANDS = {
    "vhf": dict(title="rdio - 2 m low-pass filter (144-146 MHz)", band="2 m (144-146 MHz)", lfp="Inductor_SMD:L_0603_1608Metric", lsz="0603"),
    "uhf": dict(title="rdio - 70 cm low-pass filter (430-440 MHz)", band="70 cm (430-440 MHz)", lfp="Inductor_SMD:L_0402_1005Metric", lsz="0402"),
}
CFP = "Capacitor_SMD:C_0402_1005Metric"

for key, cfg in BANDS.items():
    vals = design[key]["values"]            # C1 L1 C2 L2 C3 L3 C4 (F and H)
    S = eng.Sch(cfg["title"])
    W = S.wire
    gnd = lambda pt: S.pwr("GND", pt)
    S.ox, S.oy = 14, 14
    S.frame(0, 0, 124, 64, f"{cfg['band']} harmonic filter, 7th-order Chebyshev low-pass, 50 ohm")
    y = 30
    S.place("Connector:Conn_Coaxial", "J1", "SMA male plug (to radio)", (14, y), rot=180, fp=PLUG_FP)
    in_end = S.P("J1", "1"); ext1 = S.P("J1", "2")
    S.pwr("GND", ext1, 90)
    nodes = [34, 54, 74, 94]
    W(in_end, (nodes[0], y))
    for i, x in enumerate(nodes):
        c = S.place2("Device:C", f"C{i + 1}", fmt_c(vals[(0, 2, 4, 6)[i]]), (x, y), "down", fp=CFP)
        gnd(c)
        if i < 3:
            lv = vals[(1, 3, 5)[i]]
            la = (x + 4, y)
            W((x, y), la)
            far = S.place2("Device:L", f"L{i + 1}", fmt_l(lv), la, "right", pins=("1", "2"), fp=cfg["lfp"])
            W(far, (nodes[i + 1], y))
    S.place("Connector:Conn_Coaxial", "J2", "CONSMA020.062-G jack (antenna)", (114, y), rot=0, fp="rdio-filter:CONSMA020_062_G")
    W((nodes[-1], y), S.P("J2", "1"))
    ext2 = S.P("J2", "2"); gnd(ext2)
    W(ext2, (ext2[0] + 8, ext2[1])); S.flag((ext2[0] + 8, ext2[1]))
    S.text(f"Passband {cfg['band']}. Values chosen with a part-loss simulation (see ../{key}/{key}-response.svg).\n"
           f"C: C0G/NP0 0402, 50 V.  L: high-Q air-core or ceramic {cfg['lsz']} chip inductors, 2-5 %.\n"
           "Shunt-C first: C1-L1-C2-L2-C3-L3-C4. Max about 2 W (this is a harmonic filter for the radio's 1 W).\n"
           "J1 is an SMA male plug (threaded coupling nut) that mates with the carrier's SMA jack; J2 is a jack for the antenna's plug.",
           (4, 50), 1.27)
    d = os.path.join(FILT, key)
    os.makedirs(d, exist_ok=True)
    name = f"rdio-filter-{key}"
    open(os.path.join(d, name + ".kicad_sch"), "w").write(S.build([f"Harmonic filter for the {cfg['band']} band", "Simulated, not yet measured"]))
    open(os.path.join(d, "fp-lib-table"), "w").write(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "rdio-filter")(type "KiCad")(uri "${KIPRJMOD}/../rdio-filter.pretty")(options "")(descr "Filter footprints"))\n)\n')
    if not os.path.exists(os.path.join(d, name + ".kicad_pro")):
        open(os.path.join(d, name + ".kicad_pro"), "w").write('{\n  "meta": {\n    "filename": "%s.kicad_pro",\n    "version": 3\n  }\n}\n' % name)
    print(key, "schematic written:", " ".join(f"{k}={v}" for k, v in
          zip(("C1", "L1", "C2", "L2"), (fmt_c(vals[0]), fmt_l(vals[1]), fmt_c(vals[2]), fmt_l(vals[3])))))
