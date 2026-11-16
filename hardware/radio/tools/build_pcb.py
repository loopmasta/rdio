"""Builds a placed (unrouted) rdio.kicad_pcb from the schematic netlist.

Usage (with KiCad's python): build_pcb.py <netlist.net> <out.kicad_pcb>
Layout = the earlier rdio carrier board: DevKit under a thin carrier, SA818S on top, SMA at the antenna end, everything else on the bottom
side in the gap under the DevKit. Edit the `place` table below to move parts. Writes anchors.json (antenna pad positions, board
edges) and rf_path.json into the current directory for post_pcb.py.
"""
import os, re, sys, json, pcbnew
from pcbnew import FromMM as MM, VECTOR2I, ToMM
NET, OUT = sys.argv[1], sys.argv[2]
FPL = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
RDIO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rdio.pretty")

def parse(t):
    tok = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', t); pos = 0
    def rd():
        nonlocal pos
        if tok[pos] == '(':
            pos += 1; out = []
            while tok[pos] != ')': out.append(rd())
            pos += 1; return out
        v = tok[pos]; pos += 1
        return v[1:-1] if v.startswith('"') else v
    return rd()
tree = parse(open(NET).read())
find = lambda node, key: [c for c in node if isinstance(c, list) and c and c[0] == key]
comps = {}
for c in find(find(tree, 'components')[0], 'comp'):
    comps[find(c,'ref')[0][1]] = dict(value=find(c,'value')[0][1], fp=find(c,'footprint')[0][1], uuid=find(c,'tstamps')[0][1])
nets = {}
for n in find(find(tree, 'nets')[0], 'net'):
    nets[find(n,'name')[0][1]] = [(find(nd,'ref')[0][1], find(nd,'pin')[0][1]) for nd in find(n,'node')]
print("components", len(comps), "nets", len(nets))

b = pcbnew.BOARD()
ds = b.GetDesignSettings()
LAYERS = int(os.environ.get("LAYERS", "2"))   # 2 = two-layer board (default), 4 = solid GND plane on In1.Cu
ds.SetCopperLayerCount(LAYERS)
ds.m_TrackMinWidth = MM(0.2); ds.m_MinClearance = MM(0.2); ds.m_CopperEdgeClearance = MM(0.25)
ds.m_HoleClearance = MM(0.15); ds.m_ViasMinSize = MM(0.5); ds.m_ViasMinAnnulus = MM(0.15); ds.m_MinThroughDrill = MM(0.3)
ns = ds.m_NetSettings
dn = ns.GetDefaultNetclass(); dn.SetTrackWidth(MM(0.25)); dn.SetClearance(MM(0.2)); dn.SetViaDiameter(MM(0.6)); dn.SetViaDrill(MM(0.3))
pw = pcbnew.NETCLASS("Power"); pw.SetTrackWidth(MM(0.5)); pw.SetClearance(MM(0.2)); pw.SetViaDiameter(MM(0.7)); pw.SetViaDrill(MM(0.35))
ns.SetNetclass("Power", pw)
for pat in ("VBAT", "/VIN_ESP"): ns.SetNetclassPatternAssignment(pat, "Power")

# ---- geometry (frame of the rdio project): DevKit centre at 0,0, antenna end -x, USB end +x
EXT = 9.0                        # extra length at the antenna/SMA end: room for the SMA connector and the bulk capacitor
EDGE_W, EDGE_E, HALF = -24.13 - EXT, 24.13, 12.7
CX = -7.5                        # SA818S centre (as in the rdio project)
SMA_Y = -9.1                     # KooingTech SMA-KE: RF pad level with the module ANT pad (its ground pads sit at +-2.55)

def load(fpid):
    lib, name = fpid.split(':')
    fp = pcbnew.FootprintLoad(RDIO if lib == 'rdio' else f"{FPL}/{lib}.pretty", name)
    assert fp, fpid
    return fp
# ref: (x, y, rot, bottom)
place = {
 "U1": (0, 0, 0, False), "U2": (CX, 0, 180, False), "J2": (EDGE_W, SMA_Y, 180, False),
 "C6": (-19.0, 6.6, 0, True), "C7": (-26.8, 9.8, 0, True),
 "C1": (-3.0, 5.0, 0, True), "R1": (-9.0, -5.0, 90, True), "R2": (-11.0, -5.0, 90, True),
 "C4": (-2.0, -6.5, 0, True), "R3": (2.0, -6.5, 0, True), "C5": (9.0, -5.0, 90, True), "R4": (12.0, -5.0, 90, True),
 "R5": (-9.0, 6.0, 0, True),
 "C2": (-18.0, -3.5, 0, True), "C3": (-12.0, -9.0, 0, True),
 "R9": (19.0, -7.5, 0, True), "FB1": (14.5, -7.5, 0, True), "C8": (19.0, -3.0, 0, True),
}
DNP = {"FB1", "C8"}
fps = {}
for ref, c in comps.items():
    fp = load(c['fp']); fp.SetReference(ref); fp.SetValue(c['value'])
    lib, name = c['fp'].split(':'); fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetPath(pcbnew.KIID_PATH('/' + c['uuid']))
    b.Add(fp)
    x, y, r, bot = place[ref]
    fp.SetPosition(VECTOR2I(MM(x), MM(y)))
    if r: fp.SetOrientationDegrees(r)
    if bot: fp.Flip(fp.GetPosition(), True)
    if ref in DNP: fp.SetDNP(True)
    fps[ref] = fp

ni = {}
for name in list(nets):
    n = pcbnew.NETINFO_ITEM(b, name); b.Add(n); ni[name] = n
for name, nodes in nets.items():
    for ref, pin in nodes:
        for p in fps[ref].Pads():
            if p.GetNumber() == pin: p.SetNet(ni[name])
# GPIO reassignment test: header hole nearest to each module pin (pin number of the symbol -> net)
REMAP = {"36": None, "31": None, "28": None, "27": "/SQ", "37": "/HL", "10": "/SA_RXD", "11": "/SA_TXD"}
import os
if os.environ.get("REMAP") == "1":
    for p in fps["U1"].Pads():
        if p.GetNumber() in REMAP:
            nm = REMAP[p.GetNumber()]
            p.SetNet(ni[nm] if nm else b.FindNet("")) if nm else p.SetNetCode(0)
anchors = {}
for ref, pin, key in (("U2", "12", "ant_module"), ("J2", "1", "ant_sma")):
    p = [q for q in fps[ref].Pads() if q.GetNumber() == pin][0]
    bb = p.GetBoundingBox()
    anchors[key] = dict(x=ToMM(p.GetPosition().x), y=ToMM(p.GetPosition().y), left=ToMM(bb.GetLeft()), right=ToMM(bb.GetRight()))
anchors["edges"] = dict(w=EDGE_W, e=EDGE_E, half=HALF, cx=CX)
anchors["layers"] = LAYERS
anchors["ant_width"] = 0.4 if LAYERS == 4 else 0.8      # 0.4 mm over the 0.21 mm prepreg to the In1 plane is about 50 ohm
json.dump(anchors, open("anchors.json", "w"))

def line(x1, y1, x2, y2, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(layer)
    s.SetStart(VECTOR2I(MM(x1), MM(y1))); s.SetEnd(VECTOR2I(MM(x2), MM(y2))); s.SetWidth(MM(w)); b.Add(s)
for a, c in (((EDGE_W,-HALF),(EDGE_E,-HALF)),((EDGE_E,-HALF),(EDGE_E,HALF)),((EDGE_E,HALF),(EDGE_W,HALF)),((EDGE_W,HALF),(EDGE_W,-HALF))): line(*a, *c)

def area(pts, name, layers, tracks=True, pours=True):
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName(name)
    z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(tracks); z.SetDoNotAllowZoneFills(pours)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    z.SetLayerSet(ls)
    o = z.Outline(); o.NewOutline()
    for px, py in pts: o.Append(MM(px), MM(py))
    b.Add(z)
F, B = pcbnew.F_Cu, pcbnew.B_Cu
rect = lambda x1, y1, x2, y2: [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
# SA818S underside test pads (from the rdio project): no top copper there
area(rect(CX-15.0, -3.6, CX-7.5, 4.0), "sa818_testpads_1", [F])
area(rect(CX+15.4, -9.0, CX+17.9, 9.0), "sa818_testpads_2", [F])
# no top pour under the module body (tracks allowed)
# reserved corridor (top layer only, pours allowed) for the 0.8 mm antenna trace: SMA pad -> module pin 12, straight along y = SMA_Y
area(rect(EDGE_W + 1.0, SMA_Y - 0.9, CX - 13.35 + 0.4, SMA_Y + 0.9), "ant_corridor", [F], pours=False)

def text(t, x, y, size=1.0, angle=0, layer=pcbnew.F_SilkS, th=0.15):
    o = pcbnew.PCB_TEXT(b); o.SetText(t); o.SetLayer(layer); o.SetPosition(VECTOR2I(MM(x), MM(y)))
    o.SetTextSize(VECTOR2I(MM(size), MM(size))); o.SetTextThickness(MM(th)); o.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    if layer == pcbnew.B_SilkS: o.SetMirrored(True)
    b.Add(o)
text("rdio v2", 18.0, 6.5, 1.0)
text("<- USB end (DevKit below)", 11.0, 9.5, 0.8, 0, pcbnew.B_SilkS)
# USB-C receptacle of the DevKit: on the DevKit's underside, +x end, centred on y=0 (outline on the bottom silkscreen)
x1, x2, yy = 16.7, 23.8, 4.5
for a_, c_ in (((x1,-yy),(x2,-yy)),((x2,-yy),(x2,yy)),((x2,yy),(x1,yy)),((x1,yy),(x1,-yy))): line(*a_, *c_, pcbnew.B_SilkS, 0.2)
text("USB-C", 20.2, 0.0, 1.1, 90, pcbnew.B_SilkS)
text("USB-C end ->", 18.0, -8.3, 0.9, 0, pcbnew.F_SilkS)
text("ANT end (SMA side)", -24.6, 0.0, 0.8, 90, pcbnew.B_SilkS)
# ---- SA818S assembly aid (top silkscreen, inside the module outline, upright as placed): pin numbers next to every pad and a dot at
# the ring marker on the module's top, read from a photo of the real module: an open ring about 2.3 mm across, almost centred across the module,
# 3.4 mm from the short edge opposite the four-pad edge (pins 8-11): footprint (-14.45, -0.65). The module is placed turned by 180 degrees:
# board = (CX - fx, -fy).
def mod_to_board(fx, fy): return CX - fx, -fy
for n in range(1, 19):
    if 1 <= n <= 7:    fx, fy, lx, ly = -13.35 + 4.45*(n-1), -9.35, -13.35 + 4.45*(n-1), -9.35 + 2.1
    elif 12 <= n <= 18: fx, fy, lx, ly = 13.35 - 4.45*(n-12), 9.35, 13.35 - 4.45*(n-12), 9.35 - 2.1
    else:              fx, fy = 17.65, -6.9 + 4.6*(n-8); lx, ly = fx - 2.2, fy        # pins 8..11 on the right of the footprint
    text(str(n), *mod_to_board(lx, ly), 1.0, 0)
ring = pcbnew.PCB_SHAPE(b); ring.SetShape(pcbnew.SHAPE_T_CIRCLE); ring.SetLayer(pcbnew.F_SilkS)
cx_, cy_ = mod_to_board(-14.45, -0.65)
ring.SetCenter(VECTOR2I(MM(cx_), MM(cy_))); ring.SetEnd(VECTOR2I(MM(cx_ + 1.1), MM(cy_)))
ring.SetWidth(MM(0.2)); ring.SetFilled(False); b.Add(ring)
pcbnew.SaveBoard(OUT, b)
print("saved", OUT)
