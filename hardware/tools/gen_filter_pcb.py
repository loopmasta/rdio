"""Builds the PCB of one harmonic filter. Run with KiCad's Python:

  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 hardware/tools/gen_filter_pcb.py vhf
  ... uhf

Needs hardware/filter/<band>/rdio-filter-<band>.net.xml (from gen_filter.py + kicad-cli).
Layout: straight signal line along y = 0 from SMA to SMA, series inductors in the line, shunt capacitors dropping
to ground vias, solid ground pour on both layers, stitching vias. All parts are SMD.
"""
import os, sys, xml.etree.ElementTree as ET
import pcbnew
from pcbnew import FromMM as mm_, ToMM

band = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "..", "filter", band)
NAME = f"rdio-filter-{band}"
FP = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
CFG = {"vhf": dict(pitch=3.6, lfp=("Inductor_SMD", "L_0603_1608Metric"), label="2 m LPF 144-146 MHz"),
       "uhf": dict(pitch=3.0, lfp=("Inductor_SMD", "L_0402_1005Metric"), label="70 cm LPF 430-440 MHz")}[band]
PITCH = CFG["pitch"]
X0 = 8.0                                     # first shunt capacitor
XL = X0 + 6 * PITCH                          # last shunt capacitor
EDGE_E = round(XL + 3.0 + 5.85 + 0.1, 1)    # east edge: leaves room for the output jack's 5.6 mm pad
HALF_W = 6.2
VIA, DRILL = 0.6, 0.3
SIG, LINE = 1.0, 0.5

netof = {}
for net in ET.parse(os.path.join(DIR, NAME + ".net.xml")).getroot().iter("net"):
    for node in net.iter("node"): netof[(node.get("ref"), node.get("pin"))] = net.get("name")
vals = {c.get("ref"): c.findtext("value") or "" for c in ET.parse(os.path.join(DIR, NAME + ".net.xml")).getroot().iter("comp")}

brd = pcbnew.BOARD()
brd.GetDesignSettings().m_CopperEdgeClearance = mm_(0.25)
nets = {}
def getnet(n):
    if n not in nets:
        ni = pcbnew.NETINFO_ITEM(brd, n); brd.Add(ni); nets[n] = ni
    return nets[n]

def add(ref, lib, name, x, y, rot=0):
    libdir = os.path.join(HERE, "..", "filter", lib + ".pretty") if lib == "rdio-filter" else FP + lib + ".pretty"
    fp = pcbnew.FootprintLoad(libdir, name)
    fp.SetReference(ref); fp.SetValue(vals.get(ref, ""))
    brd.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(mm_(x), mm_(y)))
    if rot: fp.SetOrientationDegrees(rot)
    for p in fp.Pads():
        n = netof.get((ref, p.GetNumber()))
        if n: p.SetNet(getnet(n))
    return fp

def padpos(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == num: return ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)

def track(x1, y1, x2, y2, w, net, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(brd); t.SetStart(pcbnew.VECTOR2I(mm_(x1), mm_(y1))); t.SetEnd(pcbnew.VECTOR2I(mm_(x2), mm_(y2)))
    t.SetWidth(mm_(w)); t.SetLayer(layer); t.SetNet(getnet(net)); brd.Add(t)

def via(x, y, net="GND"):
    v = pcbnew.PCB_VIA(brd); v.SetPosition(pcbnew.VECTOR2I(mm_(x), mm_(y))); v.SetWidth(mm_(VIA)); v.SetDrill(mm_(DRILL))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetNet(getnet(net)); brd.Add(v)

# connectors, on the two ends
j1 = add("J1", "rdio-filter", "SMA_Plug_EdgeMount", 2.84, 0, 180)         # male plug to the radio
j2 = add("J2", "rdio-filter", "CONSMA020_062_G", EDGE_E - 0.25, 0, 0)     # TE/Linx jack, pads recessed 0.25 mm from the edge
for j in (j1, j2):
    for p in j.Pads():
        if p.GetNetname() == "GND": p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

# ladder: C1 L1 C2 L2 C3 L3 C4 along the line
sig_pads = []                 # (x, y, net) of the points on the signal line, in order
cap_x = [X0 + 2 * PITCH * i for i in range(4)]
ind_x = [X0 + PITCH + 2 * PITCH * i for i in range(3)]
caps = {}
for i, x in enumerate(cap_x):
    ref = f"C{i + 1}"
    chosen = None
    for rot in (90, 270):                                    # signal pad on the line, ground pad toward +y
        fp = add(ref, "Capacitor_SMD", "C_0402_1005Metric", x, 0, rot)
        p1, p2 = padpos(fp, "1"), padpos(fp, "2")
        if p2[1] > p1[1]: chosen = fp; break
        brd.Remove(fp)
    fp = chosen
    p1 = padpos(fp, "1")
    fp.SetPosition(pcbnew.VECTOR2I(mm_(x + (x - p1[0])), mm_(0 - p1[1] + ToMM(fp.GetPosition().y))))
    p1, p2 = padpos(fp, "1"), padpos(fp, "2")
    caps[ref] = (fp, p1, p2)
    for p in fp.Pads():
        if p.GetNetname() == "GND": p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    via(p2[0], p2[1] + 0.95); track(p2[0], p2[1], p2[0], p2[1] + 0.95, 0.4, "GND")

inds = {}
for i, x in enumerate(ind_x):
    ref = f"L{i + 1}"
    fp = add(ref, CFG["lfp"][0], CFG["lfp"][1], x, 0, 0)
    inds[ref] = (fp, padpos(fp, "1"), padpos(fp, "2"))

# signal line
def net_of(ref, pad): return netof[(ref, pad)]
sp1 = padpos(j1, "1"); sp2 = padpos(j2, "1")
track(sp1[0] + 1.0, 0, caps["C1"][1][0] - 1.2, 0, SIG, net_of("J1", "1"))      # thick feed near the SMA, thin next to the parts
track(caps["C1"][1][0] - 1.2, 0, caps["C1"][1][0], 0, LINE, net_of("J1", "1"))
for i in range(3):
    c, l, c2 = caps[f"C{i + 1}"], inds[f"L{i + 1}"], caps[f"C{i + 2}"]
    track(c[1][0], 0, l[1][0], 0, LINE, net_of(f"L{i + 1}", "1"))
    track(l[2][0], 0, c2[1][0], 0, LINE, net_of(f"L{i + 1}", "2"))
track(caps["C4"][1][0], 0, caps["C4"][1][0] + 1.2, 0, LINE, net_of("J2", "1"))
track(caps["C4"][1][0] + 1.2, 0, sp2[0] - 1.0, 0, SIG, net_of("J2", "1"))

# outline
def edge(x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(brd); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(pcbnew.VECTOR2I(mm_(x1), mm_(y1))); s.SetEnd(pcbnew.VECTOR2I(mm_(x2), mm_(y2))); s.SetWidth(mm_(0.1)); brd.Add(s)
for a, b in [((0, -HALF_W), (EDGE_E, -HALF_W)), ((EDGE_E, -HALF_W), (EDGE_E, HALF_W)), ((EDGE_E, HALF_W), (0, HALF_W)), ((0, HALF_W), (0, -HALF_W))]:
    edge(*a, *b)

# stitching vias: both long edges, and next to the line
x = 6.2
while x < EDGE_E - 5.0:
    via(x, -5.6); via(x, 5.6); x += 3.4
for xx in [X0 + PITCH * k for k in range(0, 7)]:
    via(xx, -2.7)
for xx in [X0 + PITCH * (k + 0.5) for k in range(0, 6)]:
    via(xx, 2.7)

# ground pours
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(brd); z.SetLayer(layer); z.SetNet(getnet("GND")); z.SetMinThickness(mm_(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(mm_(0.25)); z.SetThermalReliefSpokeWidth(mm_(0.3))
    ch = z.Outline(); ch.NewOutline()
    for px, py in [(0.2, -HALF_W + 0.2), (EDGE_E - 0.2, -HALF_W + 0.2), (EDGE_E - 0.2, HALF_W - 0.2), (0.2, HALF_W - 0.2)]: ch.Append(mm_(px), mm_(py))
    brd.Add(z)
pcbnew.ZONE_FILLER(brd).Fill(brd.Zones())

# silkscreen label
t = pcbnew.PCB_TEXT(brd); t.SetText(CFG["label"]); t.SetLayer(pcbnew.F_SilkS)
t.SetPosition(pcbnew.VECTOR2I(mm_(EDGE_E / 2), mm_(-4.0))); t.SetTextSize(pcbnew.VECTOR2I(mm_(1.0), mm_(1.0))); t.SetTextThickness(mm_(0.15)); brd.Add(t)
for txt, tx in (("RADIO", 11.5), ("ANTENNA", EDGE_E - 11.0)):      # which end goes where
    t2 = pcbnew.PCB_TEXT(brd); t2.SetText(txt); t2.SetLayer(pcbnew.F_SilkS)
    t2.SetPosition(pcbnew.VECTOR2I(mm_(tx), mm_(4.3))); t2.SetTextSize(pcbnew.VECTOR2I(mm_(0.9), mm_(0.9))); t2.SetTextThickness(mm_(0.15)); brd.Add(t2)
for f in brd.GetFootprints():
    if f.GetReference() not in ("J1", "J2"): f.Value().SetVisible(False)

out = os.path.join(DIR, NAME + ".kicad_pcb")
brd.Save(out)
print("saved", out, "board %.1f x %.1f mm" % (EDGE_E, 2 * HALF_W))
