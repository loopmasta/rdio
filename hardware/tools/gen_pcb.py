"""Builds hardware/rdio.kicad_pcb: places the parts, routes the signals with a small grid router,
pours GND on both layers. Run with KiCad's own Python:

  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 hardware/tools/gen_pcb.py

Needs hardware/rdio.net.xml (kicad-cli sch export netlist --format kicadxml).
Geometry (from the user's NodeMCU-32S photo): header rows 22.86 mm apart (centre to centre), 2.54 mm pitch, board
25.4 x 48.26 mm, pin 1 at the antenna end, USB end at +x.
"""
import heapq, math, os, re, sys, xml.etree.ElementTree as ET
import numpy as np
import pcbnew
from pcbnew import FromMM as mm_, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.join(HERE, "..")
FP = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"

ROW = float(os.environ.get("ROW", 22.86))      # centre to centre distance of the two header rows
PITCH = 2.54
X1 = -22.86                                     # pin 1 x
EXT = float(os.environ.get("EXT", 9.0))              # extra length at the SMA end, so the SMA and its ground sit beyond the DevKit's antenna
EDGE_W, EDGE_E = -24.13 - EXT, 24.13            # board outline in x (the DevKit is 48.26 mm long: 1.27 mm beyond the end pins)
HALF_W = 12.7                                   # board half width: the DevKit is 25.4 mm wide
CX = float(os.environ.get("CX", -7.5))                                       # radio module centre x
TRACK, PWR, ANT_W, VIA_D, VIA_DRILL, CLR = 0.25, 0.5, 0.8, 0.6, 0.3, 0.2
RCLR = float(os.environ.get("RCLR", 0.32))   # router clearance, a little above the DRC rule so diagonal tracks keep their margin
GRID = 0.1

# ---------------------------------------------------------------- netlist ---
tree = ET.parse(os.path.join(HW, "rdio.net.xml"))
netof = {}                 # (ref, pad) -> net name
for net in tree.getroot().iter("net"):
    nm = net.get("name")
    if nm.startswith("unconnected"): continue
    for node in net.iter("node"): netof[(node.get("ref"), node.get("pin"))] = nm
vals = {c.get("ref"): (c.findtext("value") or "") for c in tree.getroot().iter("comp")}

# ---------------------------------------------------------------- board -----
brd = pcbnew.BOARD()
brd.GetDesignSettings().m_MinClearance = mm_(CLR)
brd.GetDesignSettings().m_CopperEdgeClearance = mm_(0.25)
nets = {}
def getnet(n):
    if n not in nets:
        ni = pcbnew.NETINFO_ITEM(brd, n); brd.Add(ni); nets[n] = ni
    return nets[n]
getnet("")

def load(lib, name):
    path = os.path.join(HW, lib + ".pretty") if lib == "rdio" else FP + lib + ".pretty"
    return pcbnew.FootprintLoad(path, name)

def add(ref, libname, x, y, rot=0, bottom=False):
    lib, name = libname.split(":")
    fp = load(lib, name)
    fp.SetReference(ref); fp.SetValue(vals.get(ref, ""))
    brd.Add(fp)
    fp.Value().SetVisible(False)
    fp.SetPosition(pcbnew.VECTOR2I(mm_(x), mm_(y)))
    if rot: fp.SetOrientationDegrees(rot)
    if bottom: fp.Flip(fp.GetPosition(), True)
    for p in fp.Pads():
        n = netof.get((ref, p.GetNumber()))
        if n: p.SetNet(getnet(n))
    return fp

parts = {}
def add_socket(ref, y_row):
    """1x19 pin holes on the BOTTOM side (the DevKit's pins are soldered in from below). Finds the flip/rotation that puts pin 1 at
    (X1, y_row) and the pins in a row along +x."""
    for flip_lr in (True, False):
        for rot in (0, 90, 180, 270):
            fp = load("rdio", "PinHoles_1x19_P2.54mm")
            brd.Add(fp)
            fp.SetPosition(pcbnew.VECTOR2I(mm_(X1), mm_(y_row)))
            if rot: fp.SetOrientationDegrees(rot)
            fp.Flip(fp.GetPosition(), flip_lr)
            pos = {p.GetNumber(): (ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in fp.Pads()}
            if (abs(pos["1"][0] - X1) < 0.01 and abs(pos["1"][1] - y_row) < 0.01 and abs(pos["19"][0] - (X1 + 18 * PITCH)) < 0.01
                    and abs(pos["19"][1] - y_row) < 0.01 and fp.GetLayer() == pcbnew.B_Cu):
                fp.SetReference(ref); fp.SetValue(vals.get(ref, "")); fp.Value().SetVisible(False)
                for pd in fp.Pads():
                    n = netof.get((ref, pd.GetNumber()))
                    if n: pd.SetNet(getnet(n))
                return fp
            brd.Remove(fp)
    raise SystemExit("no orientation found for " + ref)
# DevKit under the board, antenna end at -x and USB end at +x: seen from above its rows swap (J2 north, J3 south)
parts["J2"] = add_socket("J2", -ROW / 2)
parts["J3"] = add_socket("J3", +ROW / 2)
parts["DK1"] = add("DK1", "rdio:ESP32_DevKit_38pin", 0, 0)     # the DevKit itself (3D body only), below the carrier
parts["U6"] = add("U6", "rdio:DRA818_SA818", CX, 0, 180)     # turned round: its antenna pin faces the SMA at the west end
SMA_Y = float(os.environ.get("SMA_Y", -4.7))      # shifted toward the module's antenna pin to keep that track short
parts["J1"] = add("J1", "rdio:CONSMA020_062_G", EDGE_W + 0.25, SMA_Y, 180)    # TE/Linx jack, pads recessed 0.25 mm from the edge   # opposite end to the DevKit's USB port
R0603, C0603 = "Resistor_SMD:R_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric"
place = {   # bottom side, rough positions; the router connects them
    "C20": ("Capacitor_SMD:C_1206_3216Metric", -12.5, -1.6, 0), "C21": (C0603, -7.6, -3.0, 0),
    "R12": (R0603, -3.0, 6.0, 0),
    "C15": (C0603, 3.0, 5.5, 0), "R15": (R0603, -1.0, 3.8, 0),
    "R16": (R0603, 5.0, -1.0, 0), "R19": (R0603, 9.0, -4.5, 90), "C16": (C0603, 6.0, -4.5, 90), "C18": (C0603, 12.0, -6.5, 0),
}
SHIFT = CX - 1.0     # the layout below was made for CX = 1.0
for ref, (lib, x, y, r) in place.items():
    parts[ref] = add(ref, lib, x + SHIFT, y, r, bottom=True)

for ref in ("J1", "J2", "J3"):     # solid ground connections for the connector and socket pads
    for pad in parts[ref].Pads():
        if pad.GetNetname() == "GND": pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

# outline
def edge(x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(brd); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(pcbnew.VECTOR2I(mm_(x1), mm_(y1))); s.SetEnd(pcbnew.VECTOR2I(mm_(x2), mm_(y2))); s.SetWidth(mm_(0.1)); brd.Add(s)
for a, b in [((EDGE_W, -HALF_W), (EDGE_E, -HALF_W)), ((EDGE_E, -HALF_W), (EDGE_E, HALF_W)), ((EDGE_E, HALF_W), (EDGE_W, HALF_W)), ((EDGE_W, HALF_W), (EDGE_W, -HALF_W))]:
    edge(*a, *b)

# ---------------------------------------------------------------- router ----
X0, Y0 = EDGE_W - 1.0, -HALF_W - 1.0
NX, NY = int((EDGE_E - EDGE_W + 3) / GRID), int((2 * HALF_W + 2) / GRID)
def ix(x): return int(round((x - X0) / GRID))
def iy(y): return int(round((y - Y0) / GRID))
def wx(i): return X0 + i * GRID
def wy(j): return Y0 + j * GRID
F, B = 0, 1
items = []        # (kind, net, layers(set), geom, halfwidth)   kinds: rect, circ, seg

def pad_items():
    for fp in brd.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            bb = p.GetBoundingBox()
            x1, y1, x2, y2 = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
            layers = set()
            if p.IsOnLayer(pcbnew.F_Cu): layers.add(F)
            if p.IsOnLayer(pcbnew.B_Cu): layers.add(B)
            if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
                items.append(("circ", n, layers, ((x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) / 2), 0))
            elif p.GetShape() == pcbnew.PAD_SHAPE_OVAL and abs((x2 - x1) - (y2 - y1)) > 0.01:
                items.append(("rect", n, layers, (x1, y1, x2, y2), 0))
            else:
                items.append(("rect", n, layers, (x1, y1, x2, y2), 0))
pad_items()
# the module body: no top copper at its test pads
# (from the module drawing: test pads P1 right of centre and P2/P3 at the left edge; keep top copper away from them)
items.append(("rect", "#keepout", {F}, (CX - 15.0, -3.6, CX - 7.5, 4.0), 0))
items.append(("rect", "#keepout", {F}, (CX + 15.4, -9.0, CX + 17.9, 9.0), 0))
# board edge margin
def edge_block(e):
    for x1, y1, x2, y2 in [(EDGE_W - 3, -HALF_W - 3, EDGE_E + 3, -HALF_W + e), (EDGE_W - 3, HALF_W - e, EDGE_E + 3, HALF_W + 3),
                           (EDGE_W - 3, -HALF_W - 3, EDGE_W + e, HALF_W + 3), (EDGE_E - e, -HALF_W - 3, EDGE_E + 3, HALF_W + 3)]:
        items.append(("rect", "#edge", {F, B}, (x1, y1, x2, y2), 0))
edge_block(0.3)

def stamp(grid, kind, geom, e, hw):
    """mark cells whose centre is closer than e (+hw) to the shape"""
    e = e + hw
    if kind == "rect":
        x1, y1, x2, y2 = geom
        i0, i1 = max(ix(x1 - e), 0), min(ix(x2 + e) + 1, NX)
        j0, j1 = max(iy(y1 - e), 0), min(iy(y2 + e) + 1, NY)
        grid[i0:i1, j0:j1] = True
    elif kind == "circ":
        cx, cy, r = geom
        R = r + e
        i0, i1 = max(ix(cx - R), 0), min(ix(cx + R) + 1, NX); j0, j1 = max(iy(cy - R), 0), min(iy(cy + R) + 1, NY)
        xs = (np.arange(i0, i1) * GRID + X0)[:, None]; ys = (np.arange(j0, j1) * GRID + Y0)[None, :]
        grid[i0:i1, j0:j1] |= (xs - cx) ** 2 + (ys - cy) ** 2 <= R * R
    elif kind == "seg":
        x1, y1, x2, y2 = geom
        R = e
        i0, i1 = max(ix(min(x1, x2) - R), 0), min(ix(max(x1, x2) + R) + 1, NX); j0, j1 = max(iy(min(y1, y2) - R), 0), min(iy(max(y1, y2) + R) + 1, NY)
        xs = (np.arange(i0, i1) * GRID + X0)[:, None]; ys = (np.arange(j0, j1) * GRID + Y0)[None, :]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = np.clip(((xs - x1) * dx + (ys - y1) * dy) / L2, 0, 1) if L2 > 0 else 0
        grid[i0:i1, j0:j1] |= (xs - (x1 + t * dx)) ** 2 + (ys - (y1 + t * dy)) ** 2 <= R * R

def build_grids(net, w):
    blk = [np.zeros((NX, NY), bool), np.zeros((NX, NY), bool)]
    viab = [np.zeros((NX, NY), bool), np.zeros((NX, NY), bool)]
    for kind, n, layers, geom, hw in items:
        if n == net: continue
        for L in layers:
            stamp(blk[L], kind, geom, RCLR + w / 2, hw)
            stamp(viab[L], kind, geom, RCLR + VIA_D / 2, hw)
    return blk, viab

tracks, vias = [], []     # output: (net, layer, x1,y1,x2,y2,w) / (net,x,y)

def inside_cells(kind, geom, m=0.06):
    cells = set()
    if kind == "rect":
        x1, y1, x2, y2 = geom
        for i in range(math.ceil((x1 + m - X0) / GRID), math.floor((x2 - m - X0) / GRID) + 1):
            for j in range(math.ceil((y1 + m - Y0) / GRID), math.floor((y2 - m - Y0) / GRID) + 1): cells.add((i, j))
    else:
        cx, cy, r = geom
        r = r - m
        for i in range(ix(cx - r), ix(cx + r) + 1):
            for j in range(iy(cy - r), iy(cy + r) + 1):
                if (wx(i) - cx) ** 2 + (wy(j) - cy) ** 2 <= r * r: cells.add((i, j))
    return cells

dropped = []
def route_net(name, pads, w, best_effort=False):
    """pads: list of (layer set, (x,y)) per pad; connect them all."""
    blk, viab = build_grids(name, w)
    # cells owned by this net's pads are passable
    own = [set(), set()]
    nitems = [it for it in items if it[1] == name]
    for kind, n, layers, geom, hw in nitems:
        for L in layers:
            g = np.zeros((NX, NY), bool); stamp(g, kind, geom, -0.0, hw)
            own[L] |= inside_cells(kind, geom)
    def nearest_pad_cells(L, px, py):
        best, bd = None, 1e9
        for kind, n, layers, geom, hw in nitems:
            if L not in layers: continue
            if kind == "rect": cx, cy = (geom[0] + geom[2]) / 2, (geom[1] + geom[3]) / 2
            else: cx, cy = geom[0], geom[1]
            d = (cx - px) ** 2 + (cy - py) ** 2
            if d < bd: bd, best = d, (kind, geom)
        kind, geom = best
        cells = inside_cells(kind, geom)
        return cells
    groups = []
    for layers, (px, py) in pads:
        g = {F: set(), B: set()}
        for L in layers: g[L] = nearest_pad_cells(L, px, py)
        groups.append(g)
    tree_cells = {F: set(), B: set()}
    for L in (F, B): tree_cells[L] |= groups[0][L]
    remaining = groups[1:]
    paths = []
    while remaining:
        goal = {}
        for gi, g in enumerate(remaining):
            for L in (F, B):
                for c in g[L]: goal[(c[0], c[1], L)] = gi
        # multi-source Dijkstra with a simple heuristic-free search (grid is small enough)
        dist = {}
        pq = []
        prev = {}
        for L in (F, B):
            for c in tree_cells[L]:
                s = (c[0], c[1], L); dist[s] = 0; heapq.heappush(pq, (0, s))
        found = None
        gx = np.array([k[0] for k in goal]); gy = np.array([k[1] for k in goal])
        while pq:
            d, s = heapq.heappop(pq)
            if d > dist.get(s, 1e18): continue
            if s in goal: found = s; break
            i, j, L = s
            for di, dj, c in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
                ni, nj = i + di, j + dj
                if not (0 <= ni < NX and 0 <= nj < NY): continue
                if blk[L][ni, nj]: continue
                if di and dj and (blk[L][i + di, j] or blk[L][i, j + dj]): continue
                nd = d + c * (1.0 + (0.02 if L == B else 0))
                t = (ni, nj, L)
                if nd < dist.get(t, 1e18): dist[t] = nd; prev[t] = s; heapq.heappush(pq, (nd, t))
            # via: both layers must be free (or belong to this net's own pad)
            if all(not viab[LL][i, j] for LL in (F, B)):
                O = 1 - L
                nd = d + 12
                t = (i, j, O)
                if nd < dist.get(t, 1e18): dist[t] = nd; prev[t] = s; heapq.heappush(pq, (nd, t))
        if not found:
            if best_effort:
                remaining.pop(0) if False else None
                dropped.append(remaining[0]); remaining.pop(0); continue
            return False
        path = [found]
        while path[-1] in prev: path.append(prev[path[-1]])
        path.reverse()
        paths.append(path)
        gi = goal[found]
        for L in (F, B):
            tree_cells[L] |= remaining[gi][L]
        for (i, j, L) in path: tree_cells[L].add((i, j))
        remaining.pop(gi)
    # turn the paths into tracks and vias, and register them as obstacles
    for path in paths:
        seg_start = path[0]
        for k in range(1, len(path)):
            a, b = path[k - 1], path[k]
            if a[2] != b[2]:
                vias.append((name, wx(a[0]), wy(a[1])))
                items.append(("circ", name, {F, B}, (wx(a[0]), wy(a[1]), VIA_D / 2), 0))
        # split at layer changes, merge straight runs
        run = [path[0]]
        runs = []
        for k in range(1, len(path)):
            if path[k][2] != run[-1][2]:
                runs.append(run); run = [path[k]]
            else: run.append(path[k])
        runs.append(run)
        for r in runs:
            L = r[0][2]
            pts = [(wx(c[0]), wy(c[1])) for c in r]
            # merge collinear
            out = [pts[0]]
            for k in range(1, len(pts) - 1):
                d1 = (round(pts[k][0] - pts[k - 1][0], 3), round(pts[k][1] - pts[k - 1][1], 3))
                d2 = (round(pts[k + 1][0] - pts[k][0], 3), round(pts[k + 1][1] - pts[k][1], 3))
                if d1 != d2: out.append(pts[k])
            out.append(pts[-1])
            for k in range(1, len(out)):
                if out[k - 1] == out[k]: continue
                tracks.append((name, L, out[k - 1][0], out[k - 1][1], out[k][0], out[k][1], w))
                items.append(("seg", name, {L}, (out[k - 1][0], out[k - 1][1], out[k][0], out[k][1]), w / 2))
    return True

def pads_of(name):
    res = []
    for fp in brd.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == name:
                layers = set()
                if p.IsOnLayer(pcbnew.F_Cu): layers.add(F)
                if p.IsOnLayer(pcbnew.B_Cu): layers.add(B)
                res.append((layers, (ToMM(p.GetPosition().x), ToMM(p.GetPosition().y))))
    return res

ORDER = [("Net-(J1-In)", ANT_W), ("/AF_OUT", TRACK), ("Net-(C16-Pad1)", TRACK), ("/ADC_IN", TRACK), ("/ADC_BIAS", TRACK), ("+5V", PWR),
         ("/MIC_IN", TRACK), ("/TX_AUDIO", TRACK), ("/PTT", TRACK), ("+3V3", TRACK),
         ("/SQ", TRACK), ("/DRA_RXD", TRACK), ("/DRA_TXD", TRACK), ("/HL", TRACK), ("/PD", TRACK), ("GND", 0.4)]
failed = []
for name, w in ORDER:
    pads = pads_of(name)
    if len(pads) < 2: continue
    ok = route_net(name, pads, w, best_effort=(name == "GND"))
    print(("routed " if ok else "FAILED ") + name, len(pads), "pads", ("(dropped %d)" % len(dropped)) if name == "GND" else "")
    if not ok: failed.append(name)

for net, L, x1, y1, x2, y2, w in tracks:
    t = pcbnew.PCB_TRACK(brd)
    t.SetStart(pcbnew.VECTOR2I(mm_(x1), mm_(y1))); t.SetEnd(pcbnew.VECTOR2I(mm_(x2), mm_(y2)))
    t.SetWidth(mm_(w)); t.SetLayer(pcbnew.F_Cu if L == F else pcbnew.B_Cu); t.SetNet(getnet(net)); brd.Add(t)
for net, x, y in vias:
    v = pcbnew.PCB_VIA(brd)
    v.SetPosition(pcbnew.VECTOR2I(mm_(x), mm_(y))); v.SetWidth(mm_(VIA_D)); v.SetDrill(mm_(VIA_DRILL))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetNet(getnet(net)); brd.Add(v)

# ground stitching vias along the RF track (ANT pad to SMA), on both sides, where the top pour exists
# (not under the module body, which has no top pour). Each one keeps clear of every pad, track and via.
def _seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    u = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + u * dx), py - (y1 + u * dy))
def _rect_dist(px, py, r):
    return math.hypot(max(r[0] - px, 0, px - r[2]), max(r[1] - py, 0, py - r[3]))
def _stitch_ok(x, y):
    m = VIA_D / 2 + CLR + 0.1
    if x > CX - 16.8 - VIA_D / 2 - 0.2 or abs(y) > HALF_W - 1.0 or x < EDGE_W + 1.0: return False
    for net, L, x1, y1, x2, y2, w in tracks:
        if _seg_dist(x, y, x1, y1, x2, y2) < m + w / 2: return False
    for net, vx, vy in vias:
        if math.hypot(x - vx, y - vy) < m + VIA_D / 2: return False
    for it in items:
        if it[0] == "rect" and it[1] != "#keepout" and _rect_dist(x, y, it[3]) < m: return False
    return True
STITCH_OFF, STITCH_STEP, stitch = 1.5, 1.2, []
for net, L, x1, y1, x2, y2, w in [t_ for t_ in tracks if t_[0] == "Net-(J1-In)"]:
    n = max(1, int(math.hypot(x2 - x1, y2 - y1) / STITCH_STEP))
    ln = math.hypot(x2 - x1, y2 - y1) or 1.0
    nx, ny = -(y2 - y1) / ln, (x2 - x1) / ln
    for i in range(n + 1):
        cx_, cy_ = x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n
        for sgn in (-1, 1):
            vx, vy = round(cx_ + sgn * STITCH_OFF * nx, 2), round(cy_ + sgn * STITCH_OFF * ny, 2)
            if all(math.hypot(vx - a, vy - b) >= 2.0 for a, b in stitch) and _stitch_ok(vx, vy):
                stitch.append((vx, vy))
for vx, vy in stitch:
    vias.append(("GND", vx, vy))
    v = pcbnew.PCB_VIA(brd)
    v.SetPosition(pcbnew.VECTOR2I(mm_(vx), mm_(vy))); v.SetWidth(mm_(VIA_D)); v.SetDrill(mm_(VIA_DRILL))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetNet(getnet("GND")); brd.Add(v)
print("RF stitching vias:", len(stitch), stitch)

# GND pours, kept off the ESP32 antenna area (x < -19) and out from under the module's top side
def zone(layer, pts):
    z = pcbnew.ZONE(brd); z.SetLayer(layer); z.SetNet(getnet("GND"))
    z.SetMinThickness(mm_(0.2)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm_(0.3)); z.SetThermalReliefSpokeWidth(mm_(0.4))
    ch = z.Outline(); ch.NewOutline()
    for x, y in pts: ch.Append(mm_(x), mm_(y))
    brd.Add(z)
box = [(EDGE_W + 0.2, -HALF_W + 0.2), (EDGE_E - 0.2, -HALF_W + 0.2), (EDGE_E - 0.2, HALF_W - 0.2), (EDGE_W + 0.2, HALF_W - 0.2)]
zone(pcbnew.F_Cu, box); zone(pcbnew.B_Cu, box)
# (no pour keep-out for the DevKit antenna: the DevKit is under the board with its antenna side facing away)
# no top-layer pour under the module body (its underside has test pads)
kb = pcbnew.ZONE(brd); kb.SetIsRuleArea(True); kb.SetDoNotAllowZoneFills(True); kb.SetDoNotAllowTracks(False); kb.SetDoNotAllowVias(False)
kb.SetDoNotAllowPads(False); kb.SetDoNotAllowFootprints(False); kb.SetLayer(pcbnew.F_Cu)
ch = kb.Outline(); ch.NewOutline()
for x, y in [(CX - 16.8, -9.5), (CX + 17.8, -9.5), (CX + 17.8, 9.5), (CX - 16.8, 9.5)]: ch.Append(mm_(x), mm_(y))
brd.Add(kb)
pcbnew.ZONE_FILLER(brd).Fill(brd.Zones())

# ---- assembly markers: where the DevKit's USB port sits (east end). The DevKit is under the board, so the main marker
# is on the bottom silkscreen; the top carries a short hint.
def silk_line(x1, y1, x2, y2, w=0.2, layer=None):
    l = pcbnew.PCB_SHAPE(brd); l.SetShape(pcbnew.SHAPE_T_SEGMENT); l.SetLayer(layer or pcbnew.F_SilkS); l.SetWidth(mm_(w))
    l.SetStart(pcbnew.VECTOR2I(mm_(x1), mm_(y1))); l.SetEnd(pcbnew.VECTOR2I(mm_(x2), mm_(y2))); brd.Add(l)
def silk_text(txt, x, y, size=1.2, angle=0, thick=0.2, layer=None):
    layer = layer or pcbnew.F_SilkS
    t = pcbnew.PCB_TEXT(brd); t.SetText(txt); t.SetLayer(layer)
    t.SetPosition(pcbnew.VECTOR2I(mm_(x), mm_(y))); t.SetTextSize(pcbnew.VECTOR2I(mm_(size), mm_(size)))
    t.SetTextThickness(mm_(thick)); t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    if layer == pcbnew.B_SilkS: t.SetMirrored(True)
    brd.Add(t)
# ---- SA818 placement aid (top silkscreen). The module covers the inside of its outline once it is soldered on, so
# the pin numbers and the name sit inside the outline for the bare board; a "1" next to the footprint's own pin-1 tick stays visible.
# Module pads in board coordinates (the module is turned 180 degrees): pins 1-7 along y = +9.35 (pin 1 at the east end),
# pins 12-18 along y = -9.35 (12 = antenna at the west end), pins 8-11 along the west edge (8 at +y).
for i in range(7):
    silk_text(str(1 + i), CX + 13.35 - 4.45 * i, 7.3, 1.0, 0, 0.15)
    silk_text(str(12 + i), CX - 13.35 + 4.45 * i, -7.3, 1.0, 0, 0.15)
for k in range(4):
    silk_text(str(8 + k), CX - 15.1, 6.9 - 4.6 * k, 1.0, 0, 0.15)
silk_text("SA818 / DRA818", CX - 1.0, 0.0, 1.3, 0, 0.18)
silk_text("ANT", CX - 13.35, -4.6, 0.9, 0, 0.15)          # under pin 12
silk_text("pin 1", CX + 13.35, 4.3, 0.9, 0, 0.15)         # above pin 1
silk_text("1", CX + 12.0, 8.2, 1.4, 0, 0.2)
ux1, ux2, uy = EDGE_E - 5.3, EDGE_E - 0.35, 3.8          # micro-USB connector outline (about 7.6 mm wide)
for L in (pcbnew.B_SilkS,):
    for a_, b_ in (((ux1, -uy), (ux2, -uy)), ((ux2, -uy), (ux2, uy)), ((ux2, uy), (ux1, uy)), ((ux1, uy), (ux1, -uy))): silk_line(*a_, *b_, layer=L)
    silk_line(ux2 + 0.2, -uy, ux2 + 0.2, uy, 0.5, layer=L)
    silk_text("USB", (ux1 + ux2) / 2 - 0.2, 0, 1.4, 90, 0.25, layer=L)
    silk_line(ux1 - 0.8, 0, ux1 - 3.0, 0, layer=L); silk_line(ux1 - 0.8, 0, ux1 - 1.6, -0.7, layer=L); silk_line(ux1 - 0.8, 0, ux1 - 1.6, 0.7, layer=L)
    silk_text("DevKit USB end", ux1 - 3.4, 0, 0.9, 90, 0.15, layer=L)
    silk_text("ANT end (SMA side)", -24.6 - 1.2, 0, 0.9, 90, 0.15, layer=L)
silk_text("USB", EDGE_E - 2.4, 0, 1.2, 90, 0.2)
silk_text("ESP32 DevKit below", 12.0, 0, 0.9, 0, 0.15) if False else None

out = os.path.join(HW, "rdio.kicad_pcb")
brd.Save(out)
print("saved", out, "tracks", len(tracks), "vias", len(vias), "failed", failed)
