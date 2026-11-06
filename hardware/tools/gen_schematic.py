#!/usr/bin/env python3
"""Generates hardware/rdio.kicad_sch (KiCad 10) from the netlist described below.

Every pin gets a short wire stub with a net label (or power symbol), so the
connectivity is exactly what is written in this file. Run:

    python3 -I hardware/tools/gen_schematic.py

KiCad's stock symbol libraries are read from the KiCad install and embedded in
the schematic. The DRA818V has no stock symbol; it is defined here and also
written to hardware/rdio.kicad_sym.
"""
import copy, os, re, sys, uuid

KICAD = "/Applications/KiCad/KiCad.app/Contents/SharedSupport"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCH_VERSION = os.environ.get("SCH_VERSION", "20250114")

# ---------------------------------------------------------------- s-expr ----
def parse(txt):
    toks = re.findall(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()]+', txt)
    pos = 0
    def rd():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == "(":
            l = []
            while toks[pos] != ")": l.append(rd())
            pos += 1
            return l
        if t.startswith('"'): return ("S", t[1:-1])
        return t
    out = []
    while pos < len(toks): out.append(rd())
    return out

def nm(x): return x[1] if isinstance(x, tuple) else x

def dump(x, ind=0):
    t = "\t" * ind
    if isinstance(x, tuple): return '"%s"' % x[1]
    if isinstance(x, str): return x
    if all(not isinstance(c, list) for c in x): return "(" + " ".join(dump(c) for c in x) + ")"
    head = []
    i = 0
    while i < len(x) and not isinstance(x[i], list): head.append(dump(x[i])); i += 1
    s = "(" + " ".join(head)
    for c in x[i:]: s += "\n" + t + "\t" + dump(c, ind + 1)
    return s + "\n" + t + ")"

def uid(): return str(uuid.uuid4())
def q(s): return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

# ------------------------------------------------------------ symbol libs ---
_libs = {}
def lib(name):
    if name not in _libs:
        t = parse(open(f"{KICAD}/symbols/{name}.kicad_sym").read())[0]
        _libs[name] = {nm(s[1]): s for s in t if isinstance(s, list) and s[0] == "symbol"}
    return _libs[name]

def flatten(libname, sym):
    d = lib(libname); s = d[sym]
    ext = [c for c in s if isinstance(c, list) and c[0] == "extends"]
    if not ext: return copy.deepcopy(s)
    parent = nm(ext[0][1])
    p = flatten(libname, parent)
    def rename(n):
        if isinstance(n, list):
            for i, c in enumerate(n):
                if isinstance(c, tuple) and c[1].startswith(parent) and i == 1:
                    n[i] = ("S", sym + c[1][len(parent):])
                elif isinstance(c, list): rename(c)
    rename(p)
    p[1] = ("S", sym)
    for c in s:
        if isinstance(c, list) and c[0] == "property":
            for i, pc in enumerate(p):
                if isinstance(pc, list) and pc[0] == "property" and nm(pc[1]) == nm(c[1]):
                    p[i] = c
    return p

def pins_of(sym):
    res = []
    def walk(n):
        for c in n:
            if isinstance(c, list):
                if c[0] == "pin" and len(c) > 3:
                    g = lambda k: [x for x in c if isinstance(x, list) and x[0] == k][0]
                    at = g("at")
                    res.append(dict(num=nm(g("number")[1]), name=nm(g("name")[1]),
                                    x=float(at[1]), y=float(at[2]), a=int(float(at[3])), type=c[1]))
                else: walk(c)
    walk(sym)
    return res

# ---- custom DRA818 / SA818 symbol --------------------------------------------
def dra818v_symbol():
    def pin(t, x, y, a, name, num):
        return f'''(pin {t} line (at {x} {y} {a}) (length 2.54)
			(name {q(name)} (effects (font (size 1.27 1.27))))
			(number {q(num)} (effects (font (size 1.27 1.27)))))'''
    pins = [
        pin("output", -12.7, 12.7, 0, "SQ", "1"), pin("output", -12.7, 10.16, 0, "AF_OUT", "3"),
        pin("input", -12.7, 7.62, 0, "MIC_IN", "18"), pin("input", -12.7, -2.54, 0, "PD", "6"),
        pin("input", -12.7, -5.08, 0, "PTT", "5"), pin("input", -12.7, -7.62, 0, "RXD", "16"),
        pin("output", -12.7, -10.16, 0, "TXD", "17"), pin("input", -12.7, -12.7, 0, "H/L", "7"),
        pin("passive", 12.7, 0, 180, "ANT", "12"),
        pin("power_in", 0, 20.32, 270, "VBAT", "8"),
        pin("power_in", 0, -20.32, 90, "GND", "9"), pin("passive", 0, -20.32, 90, "GND", "10"),
    ]
    for i, n in enumerate(["2", "4", "11", "13", "14", "15"]):
        x = [-7.62, -5.08, -2.54, 2.54, 5.08, 7.62][i]
        pins.append(pin("no_connect", x, -20.32, 90, "NC", n))
    props = "".join(f'''
		(property {q(k)} {q(v)} (at 0 0 0) (effects (font (size 1.27 1.27)){' (hide yes)' if h else ''}))'''
                    for k, v, h in [("Reference", "U", False), ("Value", "DRA818", False),
                                    ("Footprint", "", True),
                                    ("Datasheet", "https://www.dorji.com/docs/data/DRA818V.pdf", True),
                                    ("Description", "Dorji DRA818V/U or NiceRF SA818 VHF/UHF transceiver module, UART, 18 pins", True)])
    txt = f'''(symbol "DRA818V"
		(exclude_from_sim no) (in_bom yes) (on_board yes){props}
		(symbol "DRA818V_0_1"
			(rectangle (start -10.16 17.78) (end 10.16 -17.78)
				(stroke (width 0.254) (type default)) (fill (type background))))
		(symbol "DRA818V_1_1"
			{chr(10).join(pins)}
		))'''
    return parse(txt)[0]


# ---- ESP32 DevKit (38-pin) rows: only the pins used on the board are drawn ----------------
def devkit_symbol(name, right, left, top_mm, bottom_mm, desc):
    def pin(t, x, y, a, nm_, num):
        return f'''(pin {t} line (at {x} {y} {a}) (length 2.54)
			(name {q(nm_)} (effects (font (size 1.27 1.27))))
			(number {q(str(num))} (effects (font (size 1.27 1.27)))))'''
    pins = [pin(t, 15.24, y, 180, n, num) for (n, num, t, y) in right] + [pin(t, -15.24, y, 0, n, num) for (n, num, t, y) in left]
    props = "".join(f'''
		(property {q(k)} {q(v)} (at 0 0 0) (effects (font (size 1.27 1.27)){' (hide yes)' if hd else ''}))'''
                    for k, v, hd in [("Reference", "J", False), ("Value", name, False),
                                     ("Footprint", "rdio:PinHoles_1x19_P2.54mm", True),
                                     ("Datasheet", "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html", True),
                                     ("Description", desc, True)])
    return parse(f'''(symbol {q(name)}
		(exclude_from_sim no) (in_bom yes) (on_board yes){props}
		(symbol {q(name + "_0_1")}
			(rectangle (start -12.7 {top_mm}) (end 12.7 {bottom_mm}) (stroke (width 0.254) (type default)) (fill (type background))))
		(symbol {q(name + "_1_1")}
			{chr(10).join(pins)}
		))''')[0]

def j2_symbol():
    return devkit_symbol("DEVKIT_J2",
        right=[("IO32/SQ", 7, "bidirectional", 5.08), ("IO34/ADC_IN", 5, "input", 2.54),
               ("IO25/TX_AUDIO", 9, "bidirectional", 0), ("IO26/ADC_BIAS", 10, "bidirectional", -2.54)],
        left=[("3V3", 1, "power_out", 5.08), ("5V", 19, "power_out", 2.54), ("GND", 14, "power_out", 0)],
        top_mm=7.62, bottom_mm=-5.08,
        desc="ESP32 DevKit 38-pin, left header row J2 (3V3 ... 5V, pin 1 at the antenna end). Only the pins used here are drawn; the footprint has all 19 holes.")

def j3_symbol():
    return devkit_symbol("DEVKIT_J3",
        right=[("IO19/PD", 8, "bidirectional", 5.08), ("IO18/PTT", 9, "bidirectional", 2.54),
               ("IO17/UART_TX", 11, "bidirectional", 0), ("IO16/UART_RX", 12, "bidirectional", -2.54),
               ("IO23/H_L", 2, "bidirectional", -5.08)],
        left=[("GND", 1, "passive", 2.54), ("GND", 7, "passive", 0)],
        top_mm=7.62, bottom_mm=-7.62,
        desc="ESP32 DevKit 38-pin, right header row J3 (GND ... CLK). Only the pins used here are drawn; the footprint has all 19 holes.")

# ---- plain pin holes (the DevKit's own male pins are soldered straight into the carrier) --------
def pinholes_footprint():
    pads = []
    for i in range(19):
        shape = "rect" if i == 0 else "circle"
        pads.append(f'(pad "{i + 1}" thru_hole {shape} (at {round(i * 2.54, 3)} 0) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask"))')
    return f'''(footprint "PinHoles_1x19_P2.54mm"
	(version 20241229)
	(generator "rdio")
	(generator_version "10.0")
	(layer "F.Cu")
	(descr "19 plated holes, 2.54 mm pitch, for the pins of a dev board pin header (pin 1 = square pad)")
	(property "Reference" "REF**" (at 22.86 -2.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
	(property "Value" "PinHoles_1x19" (at 22.86 2.2 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(attr through_hole)
	(fp_rect (start -1.27 -1.27) (end 47.0 1.27) (stroke (width 0.12) (type default)) (fill no) (layer "F.SilkS"))
	(fp_rect (start -1.5 -1.5) (end 47.25 1.5) (stroke (width 0.05) (type default)) (fill no) (layer "F.CrtYd"))
	{chr(10).join("	" + p for p in pads)}
)
'''

GAP = 3.0         # height of the DevKit's pin-header plastic = distance between the carrier and the DevKit board
BOARD_T = 1.6
def devkit_boxes():
    z0 = -BOARD_T                                   # underside of the carrier
    zp = z0 - GAP - BOARD_T / 2                     # centre of the DevKit board
    zc = z0 - GAP - BOARD_T                         # underside of the DevKit board
    b = []
    for y in (-11.43, 11.43): b.append((0, y, z0 - GAP / 2, 48.26, 2.54, GAP, (0.08, 0.08, 0.08)))                  # header plastic
    b.append((0, 0, zp, 48.26, 25.4, BOARD_T, (0.05, 0.07, 0.12)))                                                 # DevKit PCB
    b.append((-24.13 + 6.5 + 9.5, 0, zc - 1.55, 19.0, 18.0, 3.1, (0.78, 0.78, 0.80)))                               # WROOM shield
    b.append((-24.13 + 3.25, 0, zc - 0.4, 6.5, 18.0, 0.8, (0.03, 0.03, 0.03)))                                      # antenna area
    b.append((24.13 - 2.9 + 1.0, 0, zc - 1.35, 5.8, 7.6, 2.7, (0.80, 0.80, 0.82)))                                 # micro-USB
    for y in (-11.43, 11.43):
        for i in range(19):
            b.append((-22.86 + 2.54 * i, y, (1.0 + zc) / 2, 0.64, 0.64, 1.0 - zc, (0.85, 0.7, 0.2)))               # pins
    return b

def radio_boxes():
    return [(0, 0, 0.4, 35.6, 19.0, 0.8, (0.06, 0.25, 0.12)), (0, 0, 2.0, 35.0, 18.4, 2.4, (0.8, 0.8, 0.82))]

def wrl(boxes):
    out = "#VRML V2.0 utf8\n"
    for cx, cy, cz, sx, sy, sz, (r, g, bl) in boxes:
        out += (f"Transform {{ translation {cx} {cy} {cz} children Shape {{ appearance Appearance {{ material Material {{ "
                f"diffuseColor {r} {g} {bl} specularColor 0.3 0.3 0.3 shininess 0.3 }} }} geometry Box {{ size {sx} {sy} {sz} }} }} }}\n")
    return out

MODEL_SCALE = "(scale (xyz 0.3937008 0.3937008 0.3937008))"    # the .wrl files are written in mm; KiCad reads 2.54 mm per unit
def model_line(name):
    return f'(model "${{KIPRJMOD}}/rdio.3dshapes/{name}" (offset (xyz 0 0 0)) {MODEL_SCALE} (rotate (xyz 0 0 0)))'

def devkit_body_footprint():
    return f'''(footprint "ESP32_DevKit_38pin"
	(version 20241229)
	(generator "rdio")
	(generator_version "10.0")
	(layer "F.Cu")
	(descr "ESP32 DevKit 38-pin board below the carrier, component side facing down: 3D body only, no pads")
	(property "Reference" "DK1" (at 0 -16 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(property "Value" "ESP32 DevKit" (at 0 16 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(attr smd board_only exclude_from_bom)
	(fp_rect (start -24.13 -12.7) (end 24.13 12.7) (stroke (width 0.1) (type default)) (fill no) (layer "F.Fab"))
	{model_line("ESP32_DevKit_38pin.wrl")}
)
'''


# ---- TE/Linx CONSMA020.062-G: SMA jack, edge mount, 0.062" (1.57 mm) board. Geometry from the Linx drawing
# CONSMA020.062-G (sheet 2 "recommended footprint"): RF pad 1.5 x 5.6 mm (top only), ground pads 4 x (1.6 x 4.9 mm) at +-4.26 mm
# (two on top, two on the bottom). The 6.5 mm "mounting hole" in the drawing is a panel cut-out, not a PCB hole.
# Footprint origin = centre of the board edge, connector body toward +x (outside the board), pads toward -x.
def consma_footprint(model_path):
    def pad(num, layer, x, y, sx, sy):
        sfx = "F" if layer == "F.Cu" else "B"
        return f'(pad "{num}" smd rect (at {x} {y}) (size {sx} {sy}) (layers "{sfx}.Cu" "{sfx}.Paste" "{sfx}.Mask"))'
    pads = [pad("1", "F.Cu", -2.8, 0, 5.6, 1.5)]
    for y in (-4.26, 4.26):
        pads.append(pad("2", "F.Cu", -2.45, y, 4.9, 1.6)); pads.append(pad("2", "B.Cu", -2.45, y, 4.9, 1.6))
    def rect(x1, y1, x2, y2, layer, w=0.1):
        return f'(fp_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type default)) (fill no) (layer "{layer}"))'
    return f'''(footprint "CONSMA020_062_G"
	(version 20241229)
	(generator "rdio")
	(generator_version "10.0")
	(layer "F.Cu")
	(descr "TE Connectivity / Linx CONSMA020.062-G, SMA jack (female), edge mount for 0.062 in (1.57 mm) boards. Pads from the Linx drawing, recommended footprint: RF 1.5 x 5.6, ground 4x 1.6 x 4.9 at 4.26 mm. Origin = board edge.")
	(tags "SMA jack edge mount TE Linx CONSMA020.062-G")
	(property "Reference" "REF**" (at -3 -7 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
	(property "Value" "CONSMA020.062-G" (at -3 7 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(attr smd)
	(fp_line (start 0 -5.5) (end 0 5.5) (stroke (width 0.1) (type dash)) (layer "Dwgs.User"))
	{rect(0, -4.76, 1.6, 4.76, "F.Fab")}
	{rect(1.6, -3.175, 9.5, 3.175, "F.Fab")}
	{rect(-5.85, -5.3, 9.7, 5.3, "F.CrtYd", 0.05)}
	{chr(10).join("	" + p_ for p_ in pads)}
	(model "{model_path}" (offset (xyz 0 0 0)) (scale (xyz 0.3937008 0.3937008 0.3937008)) (rotate (xyz 0 0 0)))
)
'''

def prism_x(x0, x1, cy, cz, r, col, n=16):
    import math as _m
    pts = [(xx, cy + r * _m.cos(2 * _m.pi * i / n), cz + r * _m.sin(2 * _m.pi * i / n)) for xx in (x0, x1) for i in range(n)]
    faces = [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)] + [list(range(n)), [n + i for i in reversed(range(n))]]
    pt = ", ".join(f"{x:.3f} {y:.3f} {z:.3f}" for x, y, z in pts)
    idx = ", ".join(" ".join(map(str, f)) + " -1" for f in faces)
    return (f"Shape {{ appearance Appearance {{ material Material {{ diffuseColor {col} specularColor 0.5 0.5 0.5 shininess 0.5 }} }} "
            f"geometry IndexedFaceSet {{ solid FALSE coord Coordinate {{ point [ {pt} ] }} coordIndex [ {idx} ] }} }}\n")

def consma_wrl():
    """simple placeholder body (mm): flange 9.52 x 7.92 x 1.6, threaded barrel 7.9 long, board 1.57 mm, axis 0.5 mm above the top face"""
    zc = 0.5
    w = "#VRML V2.0 utf8\n"
    w += wrl([(0.8, 0, zc, 1.6, 9.52, 7.92, (0.85, 0.7, 0.2))])
    w += prism_x(1.6, 9.5, 0, zc, 3.175, "0.85 0.7 0.2")
    w += prism_x(9.48, 9.55, 0, zc, 2.0, "0.1 0.1 0.1")
    return w

# ---- footprint: DRA818 / SA818 (same outline: 35.6 x 19 mm, castellated pads, 4.45 mm pitch) -----
def radio_footprint():
    # Land pattern: 0.9 mm under the module edge, 0.6 mm outside it (the header rows are only 22.86 mm apart,
    # so the 19 mm wide module has about 1 mm to spare on each side).
    pads = []
    for i in range(7):
        pads.append(f'(pad "{i + 1}" smd rect (at {round(-13.35 + 4.45 * i, 3)} -9.35) (size 1.5 1.5) (layers "F.Cu" "F.Paste" "F.Mask"))')
        pads.append(f'(pad "{12 + i}" smd rect (at {round(13.35 - 4.45 * i, 3)} 9.35) (size 1.5 1.5) (layers "F.Cu" "F.Paste" "F.Mask"))')
    for k, n in enumerate((8, 9, 10)):
        pads.append(f'(pad "{n}" smd rect (at 17.65 {round(-6.9 + 4.6 * k, 3)}) (size 1.5 1.5) (layers "F.Cu" "F.Paste" "F.Mask"))')
    def rect(x1, y1, x2, y2, layer, w=0.12):
        return f'(fp_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type default)) (fill no) (layer "{layer}"))'
    return f'''(footprint "DRA818_SA818"
	(version 20241229)
	(generator "rdio")
	(generator_version "10.0")
	(layer "F.Cu")
	(descr "Dorji DRA818V/U and NiceRF SA818S-V/U (same outline), 35.6 x 19 mm, 18 castellated pads. Pads 2, 4, 11, 13, 14, 15 are NC and not drawn. Pin 1 top left, 8-11 right, 12 bottom right to 18 bottom left. Land pattern derived from the module outline drawings, check against your module.")
	(tags "dra818 sa818 radio module")
	(property "Reference" "REF**" (at 0 -13 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
	(property "Value" "DRA818_SA818" (at 0 13 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(attr smd)
	{rect(-17.8, -9.5, 17.8, 9.5, "F.SilkS")}
	{rect(-17.8, -9.5, 17.8, 9.5, "F.Fab", 0.1)}
	{rect(-19.0, -9.6, 19.0, 9.6, "F.CrtYd", 0.05)}
	(fp_line (start -18.6 -11) (end -18.6 -9.5) (stroke (width 0.2) (type default)) (layer "F.SilkS"))
	{chr(10).join("	" + p for p in pads)}
	{model_line("DRA818_SA818.wrl")}
)
'''
# ------------------------------------------------------------ schematic -----
# All layout coordinates are in "units" of 1.27 mm (the KiCad grid): x right, y down.
G = 1.27
POWER = {"GND", "+3V3", "+5V"}
ROOT = uid()

def mm(v): return round(v * G, 2)
def rot_vec(x, y, r):
    import math
    c, s = round(math.cos(math.radians(r))), round(math.sin(math.radians(r)))
    return x * c - y * s, x * s + y * c

class Sch:
    def __init__(self):
        self.syms = {}; self.items = []; self.segs = []; self.conn_pts = []
        self.pp = {}          # ref -> {pin number: (x_u, y_u, outward angle)}
        self.pwr_n = 0
        self.warn = []
        self.ox, self.oy = 12, 14     # sheet offset in units (inside the A3 border)

    def T(self, pt): return (pt[0] + self.ox, pt[1] + self.oy)

    # -- library -----------------------------------------------------------
    def need(self, lib_id):
        if lib_id in self.syms: return self.syms[lib_id]
        if lib_id == "rdio:DRA818V": s = dra818v_symbol()
        elif lib_id == "rdio:DEVKIT_J2": s = j2_symbol()
        elif lib_id == "rdio:DEVKIT_J3": s = j3_symbol()
        else:
            ln, sn = lib_id.split(":", 1)
            s = flatten(ln, sn)
        s = copy.deepcopy(s); s[1] = ("S", lib_id)
        self.syms[lib_id] = s
        return s

    def prop(self, sym, k):
        for c in sym:
            if isinstance(c, list) and c[0] == "property" and nm(c[1]) == k: return nm(c[2])
        return ""

    # -- primitives (arguments in units) --------------------------------------
    def wire(self, *pts):
        for a, b in zip(pts, pts[1:]):
            a, b = self.T(a), self.T(b)
            if a == b: continue
            (x1, y1), (x2, y2) = (mm(a[0]), mm(a[1])), (mm(b[0]), mm(b[1]))
            assert x1 == x2 or y1 == y2, f"diagonal wire {a}->{b}"
            self.segs.append(((x1, y1), (x2, y2)))
            self.items.append(f'(wire (pts (xy {x1:.2f} {y1:.2f}) (xy {x2:.2f} {y2:.2f})) (stroke (width 0) (type default)) (uuid "{uid()}"))')

    def lab(self, name, pt, ang=0):
        pt = self.T(pt)
        j = "left bottom" if ang in (0, 90) else "right bottom"
        self.items.append(f'(label {q(name)} (at {mm(pt[0]):.2f} {mm(pt[1]):.2f} {ang}) (effects (font (size 1.27 1.27)) (justify {j})) (uuid "{uid()}"))')

    def nc(self, pt):
        pt = self.T(pt)
        self.items.append(f'(no_connect (at {mm(pt[0]):.2f} {mm(pt[1]):.2f}) (uuid "{uid()}"))')

    def text(self, s, pt, size=1.27, bold=False, color=None):
        pt = self.T(pt)
        b = " bold" if bold else ""
        self.items.append(f'(text {q(s)} (at {mm(pt[0]):.2f} {mm(pt[1]):.2f} 0) (effects (font (size {size} {size}){b}) (justify left top)) (uuid "{uid()}"))')

    def frame(self, x1, y1, x2, y2, title):
        (ax, ay), (bx, by) = self.T((x1, y1)), self.T((x2, y2))
        self.items.append(f'(rectangle (start {mm(ax):.2f} {mm(ay):.2f}) (end {mm(bx):.2f} {mm(by):.2f}) (stroke (width 0.2) (type dash)) (fill (type none)) (uuid "{uid()}"))')
        self.text(title, (x1 + 2, y1 + 2), 2.0, True)

    def pwr(self, net, pt, out=None):
        """power symbol with its pin at pt; body points toward out (default: up, GND down)."""
        pt = self.T(pt)
        if out is None: out = 270 if net == "GND" else 90
        lib_id = "power:" + net
        self.need(lib_id)
        natural = 270 if net == "GND" else 90
        self.pwr_n += 1
        ref = f"#PWR{self.pwr_n:03d}"
        dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[out]
        x, y = mm(pt[0]), mm(pt[1])
        vpos = (x + dx * 4.4, y + dy * 4.4 - (0.0 if dy else 0.0))
        self.items.append(self._symbol(lib_id, ref, net, x, y, (out - natural) % 360, ["1"], hide_ref=True, power=True,
                                       val_at=vpos, show_val=(net != "GND"), just=""))
        self.conn_pts.append((x, y))

    def flag(self, pt):
        pt = self.T(pt)
        self.need("power:PWR_FLAG")
        self.pwr_n += 1
        ref = f"#FLG{self.pwr_n:03d}"
        self.items.append(self._symbol("power:PWR_FLAG", ref, "PWR_FLAG", mm(pt[0]), mm(pt[1]), 0, ["1"], hide_ref=True, power=True))
        self.conn_pts.append((mm(pt[0]), mm(pt[1])))

    def _symbol(self, lib_id, ref, value, x, y, rot, pin_nums, hide_ref=False, power=False, fp="", dnp=False,
                ref_at=None, val_at=None, datasheet="~", just="left", show_val=False):
        props = [("Reference", ref, ref_at or (x + 2.54, y - 1.27), hide_ref, just),
                 ("Value", value, val_at or (x + 2.54, y + 1.27), power and not show_val, just),
                 ("Footprint", fp, (x, y), True, ""), ("Datasheet", datasheet, (x, y), True, "")]
        s = f'(symbol (lib_id {q(lib_id)}) (at {x:.2f} {y:.2f} {rot}) (unit 1) (exclude_from_sim no) '
        s += f'(in_bom {"no" if power else "yes"}) (on_board {"no" if power else "yes"}) (dnp {"yes" if dnp else "no"}) (uuid "{uid()}")\n'
        for k, v, (px, py), hide, j in props:
            jj = f" (justify {j})" if j else ""
            h = " (hide yes)" if hide else ""
            pa = (-rot) % 360 if rot in (90, 270) else 0
            s += f'\t(property {q(k)} {q(v)} (at {px:.2f} {py:.2f} {pa}) (effects (font (size 1.27 1.27)){jj}{h}))\n'
        for num in pin_nums: s += f'\t(pin {q(num)} (uuid "{uid()}"))\n'
        s += f'\t(instances (project "rdio" (path "/{ROOT}" (reference {q(ref)}) (unit 1))))\n)'
        return s

    # -- parts ---------------------------------------------------------------
    def place(self, lib_id, ref, value, pos, rot=0, nc=(), ports=None, fp=None, dnp=False, datasheet=None,
              ref_at=None, val_at=None, _mm=False, just="left", inside=False, dx=0, hz=False):
        """pos in units. nc: pin numbers to flag no-connect. ports: {pin: (net, stub length in units)}"""
        sym = self.need(lib_id)
        pins = pins_of(sym)
        x, y = (pos if _mm else (mm(pos[0] + self.ox), mm(pos[1] + self.oy)))
        horizontal2 = len(pins) == 2 and rot in (90, 270)
        if inside:
            ref_at = (x - 20.32, y - 20.32); val_at = (x - 20.32, y - 17.78)
        elif len(pins) > 2 and rot == 0:
            xs = [p["x"] for p in pins]; ys = [p["y"] for p in pins]
            extra = 3.81 if max(ys) < 10 else 0
            ref_at = ref_at or (x + min(xs), y - max(ys) - 3.81 - extra)
            val_at = val_at or (x + min(xs), y - max(ys) - 1.27 - extra)
        elif horizontal2 or hz:
            ref_at = ref_at or (x, y - 3.81); val_at = val_at or (x, y + 5.08); just = ""
        if dx and not ref_at: ref_at = (x + 2.54 + dx, y - 1.27); val_at = (x + 2.54 + dx, y + 1.27)
        fpv = fp if fp is not None else self.prop(sym, "Footprint")
        ds = datasheet if datasheet is not None else (self.prop(sym, "Datasheet") or "~")
        self.items.append(self._symbol(lib_id, ref, value, x, y, rot, [p["num"] for p in pins], fp=fpv, dnp=dnp,
                                       ref_at=ref_at, val_at=val_at, datasheet=ds, just=just))
        ends = {}
        for p in pins:
            rx, ry = rot_vec(p["x"], p["y"], rot)
            ex, ey = round((x + rx) / G, 2), round((y - ry) / G, 2)
            self.conn_pts.append((mm(ex), mm(ey)))
            ex, ey = round(ex - self.ox, 2), round(ey - self.oy, 2)
            ends[p["num"]] = (ex, ey, (p["a"] + rot + 180) % 360)
        self.pp[ref] = ends
        for n in nc:
            self.nc(ends[n][:2])
        for n, (net, ln) in (ports or {}).items():
            ex, ey, out = ends[n]
            dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[out]
            end = (ex + dx * ln, ey + dy * ln)
            self.wire((ex, ey), end)
            if net in POWER: self.pwr(net, end, out)
            else: self.lab(net, end, out)
        return ends

    def place2(self, lib_id, ref, value, anchor, direction, pins=("1", "2"), fp=None, dnp=False, dx=0):
        """two-terminal part: pin pins[0] sits at anchor, pin pins[1] lies toward direction (up/down/left/right).
        Returns the far pin end (units)."""
        sym = self.need(lib_id)
        pl = {p["num"]: p for p in pins_of(sym)}
        want = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[direction]
        for rot in (0, 90, 180, 270):
            r0 = rot_vec(pl[pins[0]]["x"], pl[pins[0]]["y"], rot)
            r1 = rot_vec(pl[pins[1]]["x"], pl[pins[1]]["y"], rot)
            vx, vy = r1[0] - r0[0], -(r1[1] - r0[1])
            if abs(vx) < 0.01 and want[0] == 0 and vy * want[1] > 0 or abs(vy) < 0.01 and want[1] == 0 and vx * want[0] > 0:
                break
        else: raise SystemExit("no rotation for " + ref)
        xc = mm(anchor[0] + self.ox) - r0[0]; yc = mm(anchor[1] + self.oy) + r0[1]
        self.place(lib_id, ref, value, (xc, yc), rot=rot, fp=fp, dnp=dnp, _mm=True, dx=dx, hz=(direction in ("left", "right")))
        return self.pp[ref][pins[1]][:2]

    def tp(self, xu, yu): return (mm(xu + self.ox), mm(yu + self.oy))

    def P(self, ref, pin): return self.pp[ref][pin][:2]

    # -- output ------------------------------------------------------------
    def junctions(self):
        from collections import Counter
        cnt = Counter()
        for a, b in self.segs: cnt[a] += 1; cnt[b] += 1
        for p in self.conn_pts: cnt[p] += 1
        pts = set(cnt)
        for (x1, y1), (x2, y2) in self.segs:
            for (px, py) in pts:
                if x1 == x2 == px and min(y1, y2) < py < max(y1, y2): cnt[(px, py)] += 2
                elif y1 == y2 == py and min(x1, x2) < px < max(x1, x2): cnt[(px, py)] += 2
        return [p for p, n in cnt.items() if n >= 3]

    def build(self, comments):
        libsyms = "\n".join("\t\t" + dump(s, 2) for s in self.syms.values())
        jn = "\n".join(f'(junction (at {x:.2f} {y:.2f}) (diameter 0) (color 0 0 0 0) (uuid "{uid()}"))' for x, y in self.junctions())
        body = "\n".join("\t" + i.replace("\n", "\n\t") for i in self.items + [jn] if i)
        cm = "\n".join(f'\t\t(comment {i + 1} {q(c)})' for i, c in enumerate(comments))
        return f'''(kicad_sch
	(version {SCH_VERSION})
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "{ROOT}")
	(paper "A4")
	(title_block
		(title "rdio - ESP32 DevKit + DRA818/SA818 radio carrier")
		(date "2026-11-05")
		(rev "A")
{cm}
	)
	(lib_symbols
{libsyms}
	)
{body}
	(sheet_instances
		(path "/"
			(page "1")
		)
	)
	(embedded_fonts no)
)
'''

S = Sch()
R, C = "Device:R", "Device:C"
R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
SW_FP = "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92"

def res(ref, val, anchor, direction, pin0="1"):
    return S.place2(R, ref, val, anchor, direction, pins=(pin0, "2" if pin0 == "1" else "1"), fp=R0603)
def cap(ref, val, anchor, direction, pin0="1", fp=C0603, lib=C):
    return S.place2(lib, ref, val, anchor, direction, pins=(pin0, "2" if pin0 == "1" else "1"), fp=fp)
W = S.wire
def gnd(pt): S.pwr("GND", pt)
def p33(pt): S.pwr("+3V3", pt)
def p5(pt): S.pwr("+5V", pt)

# ============================================================ 1. dev board ====
S.ox, S.oy = 12, 12
S.frame(0, 0, 48, 70, "1  ESP32 DevKit")
S.place("rdio:DEVKIT_J2", "J2", "ESP32 DevKit, row J2", (30, 24), fp="rdio:PinHoles_1x19_P2.54mm", ref_at=S.tp(22, 11), val_at=S.tp(22, 13.5))
S.place("rdio:DEVKIT_J3", "J3", "ESP32 DevKit, row J3", (30, 36), fp="rdio:PinHoles_1x19_P2.54mm", ref_at=S.tp(22, 43), val_at=S.tp(22, 45.5))
v3 = S.P("J2", "1"); v5 = S.P("J2", "19"); g2 = S.P("J2", "14")
W(v3, (v3[0] - 6, v3[1]), (v3[0] - 6, v3[1] - 4)); p33((v3[0] - 6, v3[1] - 4))
W(v5, (v5[0] - 10, v5[1]), (v5[0] - 10, v5[1] - 4)); p5((v5[0] - 10, v5[1] - 4))
W(g2, (g2[0] - 6, g2[1]), (g2[0] - 6, g2[1] + 4)); gnd((g2[0] - 6, g2[1] + 4))
ga, gb = S.P("J3", "1"), S.P("J3", "7")
W(ga, (ga[0] - 4, ga[1]), (ga[0] - 4, gb[1] + 4)); W(gb, (gb[0] - 4, gb[1])); gnd((ga[0] - 4, gb[1] + 4))
S.text("Its own pins are soldered into\nthe carrier (no sockets), about\n3 mm gap. NodeMCU-32S / DevKitC V4\norder, rows 22.86 mm apart:\nJ2 = left row (3V3 ... 5V)\nJ3 = right row (GND ... CLK)", (2, 50), 1.27)

# ================================================ 2. radio, bus, antenna, audio ====
S.frame(52, 0, 140, 100, "2  Radio module: DRA818V/U or SA818-V/U")
S.place("rdio:DRA818V", "U6", "DRA818V/U or SA818-V/U", (106, 30), fp="rdio:DRA818_SA818", ref_at=S.tp(110, 11), val_at=S.tp(110, 13.5))
vb_ = S.P("U6", "8"); W(vb_, (vb_[0], vb_[1] - 4)); p5((vb_[0], vb_[1] - 4))
gnd(S.P("U6", "9"))
bus = [("SQ", "J2", "7", "1"), ("PD", "J3", "8", "6"), ("PTT", "J3", "9", "5"), ("DRA_RXD", "J3", "11", "16"),
       ("DRA_TXD", "J3", "12", "17"), ("HL", "J3", "2", "7")]
for name, jr, jp, mp in bus:
    a_, b_ = S.P(jr, jp), S.P("U6", mp)
    assert a_[1] == b_[1], (name, a_, b_)
    W(a_, b_); S.lab(name, (68, a_[1]), 0)
for jp, mp, ne, nm_ in (("5", "3", "ADC_IN", "AF_OUT"), ("9", "18", "TX_AUDIO", "MIC_IN")):
    a_, b_ = S.P("J2", jp), S.P("U6", mp)
    W(a_, (a_[0] + 6, a_[1])); S.lab(ne, (a_[0] + 6, a_[1]), 0)
    W(b_, (b_[0] - 6, b_[1])); S.lab(nm_, (b_[0] - 6, b_[1]), 180)
a_ = S.P("J2", "10"); W(a_, (a_[0] + 6, a_[1])); S.lab("ADC_BIAS", (a_[0] + 6, a_[1]), 0)
S.text("DRA_RXD = module RXD (IO17)\nDRA_TXD = module TXD (IO16)\nSQ is active low", (56, 48), 1.27)
S.text("H/L: floating = 1 W, low = 0.5 W.\nIO23: output LOW or input,\nnever drive it HIGH.", (100, 48), 1.27)
# antenna
S.place("Connector:Conn_Coaxial", "J1", "CONSMA020.062-G", (130, 30), fp="rdio:CONSMA020_062_G")
W(S.P("U6", "12"), S.P("J1", "1")); gnd(S.P("J1", "2"))
# PTT pull-up
p33((124, 58)); r12 = res("R12", "10k", (124, 58), "down"); W(r12, (124, 68)); S.lab("PTT", (124, 68), 0)
S.text("R12: PTT held high,\nmodule stays in receive\nwhile the ESP32 boots.", (106, 72), 1.27)
# RX audio
S.text("RX: AF_OUT -> 1uF -> IO34.\nIO26 biases it to 1.75 V\nthrough 10k (as the firmware expects).", (56, 58), 1.27)
y = 76
W((58, y), (62, y)); S.lab("AF_OUT", (58, y), 180)
f = cap("C15", "1uF", (62, y), "right")
W(f, (92, y)); S.lab("ADC_IN", (92, y), 0)
fr = S.place2(R, "R15", "10k", (78, y), "up", pins=("2", "1"), fp=R0603)
W(fr, (fr[0], fr[1] - 2)); S.lab("ADC_BIAS", (fr[0], fr[1] - 2), 0)
# TX audio
S.text("TX: IO25 (PDM) -> 22k / 220R divider with 220nF\nlow-pass (module wants about 10 mV) -> 100nF -> MIC_IN.\nAudio values are first-pass; compare with the working board.", (56, 84), 1.27)
y = 94
W((58, y), (62, y)); S.lab("TX_AUDIO", (58, y), 180)
f = res("R16", "22k", (62, y), "right")
W(f, (92, y)); gnd(res("R19", "220R", (76, y), "down")); gnd(cap("C16", "220nF", (86, y), "down"))
f = cap("C18", "100nF", (98, y), "right")
W((92, y), (98, y)); W(f, (118, y)); S.lab("MIC_IN", (118, y), 0)

# ============================================================ 3. radio supply ====
S.ox = -8
S.frame(164, 0, 226, 56, "3  Radio supply")
p5((170, 14)); W((170, 14), (170, 26), (208, 26))
c20 = cap("C20", "47uF", (200, 26), "down", fp="Capacitor_SMD:C_1206_3216Metric"); gnd(c20)
c21 = cap("C21", "100nF", (208, 26), "down"); gnd(c21)
S.text("From the dev board's 5 V pin, straight to the module.\nModule: 3.3-4.5 V, 0.75 A at TX; the dev board's\n5 V pin is already diode-dropped (about 4.5 V).", (166, 36), 1.27)

# ------------------------------------------------------------------ write ----
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "rdio.kicad_sch"), "w").write(S.build([
    "Same pin map as the firmware (GPIO16/17/18/19/25/26/32/34), plus GPIO23 for H/L",
    "Audio and power values are first-pass; verify on the bench"]))
open(os.path.join(OUT, "rdio.kicad_sym"), "w").write(
    '(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "kicad_symbol_editor")\n\t(generator_version "10.0")\n\t'
    + dump(dra818v_symbol(), 1) + "\n\t" + dump(j2_symbol(), 1) + "\n\t" + dump(j3_symbol(), 1) + "\n)\n")
open(os.path.join(OUT, "sym-lib-table"), "w").write(
    '(sym_lib_table\n\t(version 7)\n\t(lib (name "rdio")(type "KiCad")(uri "${KIPRJMOD}/rdio.kicad_sym")(options "")(descr "Project symbols"))\n)\n')
os.makedirs(os.path.join(OUT, "rdio.pretty"), exist_ok=True)
open(os.path.join(OUT, "rdio.pretty", "DRA818_SA818.kicad_mod"), "w").write(radio_footprint())
open(os.path.join(OUT, "rdio.pretty", "PinHoles_1x19_P2.54mm.kicad_mod"), "w").write(pinholes_footprint())
open(os.path.join(OUT, "rdio.pretty", "CONSMA020_062_G.kicad_mod"), "w").write(consma_footprint("${KIPRJMOD}/rdio.3dshapes/CONSMA020_062_G.wrl"))
open(os.path.join(OUT, "rdio.pretty", "ESP32_DevKit_38pin.kicad_mod"), "w").write(devkit_body_footprint())
os.makedirs(os.path.join(OUT, "rdio.3dshapes"), exist_ok=True)
open(os.path.join(OUT, "rdio.3dshapes", "ESP32_DevKit_38pin.wrl"), "w").write(wrl(devkit_boxes()))
open(os.path.join(OUT, "rdio.3dshapes", "DRA818_SA818.wrl"), "w").write(wrl(radio_boxes()))
open(os.path.join(OUT, "rdio.3dshapes", "CONSMA020_062_G.wrl"), "w").write(consma_wrl())
open(os.path.join(OUT, "fp-lib-table"), "w").write(
    '(fp_lib_table\n\t(version 7)\n\t(lib (name "rdio")(type "KiCad")(uri "${KIPRJMOD}/rdio.pretty")(options "")(descr "Project footprints"))\n)\n')
pro = os.path.join(OUT, "rdio.kicad_pro")
if not os.path.exists(pro):
    open(pro, "w").write('{\n  "meta": {\n    "filename": "rdio.kicad_pro",\n    "version": 3\n  }\n}\n')
print("symbols:", len(S.syms), "wires:", len(S.segs), "junctions:", len(S.junctions()))
