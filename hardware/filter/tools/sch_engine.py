"""Writes KiCad 10 schematics: the s-expression helpers, KiCad's stock symbol libraries (read from the KiCad install and embedded in
the schematic), the `Sch` class that places parts and wires on a 1.27 mm grid and writes the sheet, and the CONSMA020.062-G footprint
and its simple 3D body. Used by gen_filter.py (the code is the one that wrote the carrier board's first schematic).

Every pin gets a wire; the connectivity is exactly what the generator script writes.
"""
import copy, os, re, sys, uuid

KICAD = "/Applications/KiCad/KiCad.app/Contents/SharedSupport"
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

def wrl(boxes):
    out = "#VRML V2.0 utf8\n"
    for cx, cy, cz, sx, sy, sz, (r, g, bl) in boxes:
        out += (f"Transform {{ translation {cx} {cy} {cz} children Shape {{ appearance Appearance {{ material Material {{ "
                f"diffuseColor {r} {g} {bl} specularColor 0.3 0.3 0.3 shininess 0.3 }} }} geometry Box {{ size {sx} {sy} {sz} }} }} }}\n")
    return out

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

# All layout coordinates are in "units" of 1.27 mm (the KiCad grid): x right, y down.
G = 1.27
POWER = {"GND", "+3V3", "+5V"}

def mm(v): return round(v * G, 2)
def rot_vec(x, y, r):
    import math
    c, s = round(math.cos(math.radians(r))), round(math.sin(math.radians(r)))
    return x * c - y * s, x * s + y * c

class Sch:
    def __init__(self, title):
        self.title = title
        self.root = uid()             # uuid of the sheet
        self.syms = {}; self.items = []; self.segs = []; self.conn_pts = []
        self.pp = {}          # ref -> {pin number: (x_u, y_u, outward angle)}
        self.pwr_n = 0
        self.warn = []
        self.ox, self.oy = 12, 14     # sheet offset in units (inside the A3 border)

    def T(self, pt): return (pt[0] + self.ox, pt[1] + self.oy)

    # -- library -----------------------------------------------------------
    def need(self, lib_id):
        if lib_id in self.syms: return self.syms[lib_id]
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
        s += f'\t(instances (project "rdio" (path "/{self.root}" (reference {q(ref)}) (unit 1))))\n)'
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
	(uuid "{self.root}")
	(paper "A4")
	(title_block
		(title "{self.title}")
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
