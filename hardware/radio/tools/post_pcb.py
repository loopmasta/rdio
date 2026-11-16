"""After routing: hand-drawn antenna trace, GND pours on every copper layer, GND stitching vias (grid + islands + a via fence beside the audio
chain), solid GND pad connections, zone fill. Usage: post_pcb.py <routed.kicad_pcb> <out.kicad_pcb>   (run in the folder that holds anchors.json)
Environment: POUR_UNDER_MODULE=0 keeps the top layer free of copper under the whole SA818S body (default 1: only its two test-pad areas stay free)."""
import os, sys, json, math, pcbnew
from pcbnew import FromMM as MM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
A = json.load(open("anchors.json"))
E = A["edges"]; EDGE_W, EDGE_E, HALF, CX = E["w"], E["e"], E["half"], E["cx"]
byname = b.GetNetsByName()
gnd = [n for n in byname.values() if n.GetNetname() == "GND"][0]
ant = [n for n in byname.values() if n.GetNetname() == "Net-(J2-In)"][0]
# antenna: straight from the SMA pad to module pin 12 (0.4 mm = about 50 ohm over the inner plane on the 4-layer board, 0.8 mm on 2 layers)
pts = [(A["ant_sma"]["x"], A["ant_sma"]["y"]), (A["ant_module"]["x"], A["ant_sma"]["y"])]   # straight along the SMA pad level, ends inside module pin 12
for p, q in zip(pts, pts[1:]):
    t = pcbnew.PCB_TRACK(b); t.SetLayer(pcbnew.F_Cu); t.SetNet(ant); t.SetWidth(MM(A.get("ant_width", 0.8)))
    t.SetStart(VECTOR2I(MM(p[0]), MM(p[1]))); t.SetEnd(VECTOR2I(MM(q[0]), MM(q[1]))); b.Add(t)
def zone(layer):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(gnd)
    z.SetLocalClearance(MM(0.25))          # KiCad's default pour clearance is 0.5 mm: needlessly wide, the design rule is 0.2 mm
    z.SetMinThickness(MM(0.2)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)        # keep every piece for now: vias below save the useful ones
    o = z.Outline(); o.NewOutline()
    for x, y in ((EDGE_W+0.2,-HALF+0.2),(EDGE_E-0.2,-HALF+0.2),(EDGE_E-0.2,HALF-0.2),(EDGE_W+0.2,HALF-0.2)): o.Append(MM(x), MM(y))
    b.Add(z)
LAYERS = A.get("layers", 2)
LAY = [pcbnew.F_Cu] + ([pcbnew.In1_Cu, pcbnew.In2_Cu] if LAYERS == 4 else []) + [pcbnew.B_Cu]
for _l in LAY: zone(_l)
if os.environ.get("POUR_UNDER_MODULE", "1") == "0":
    # no top pour under the module body, tracks allowed
    k = pcbnew.ZONE(b); k.SetIsRuleArea(True); k.SetZoneName("sa818_body_nopour")
    k.SetDoNotAllowZoneFills(True); k.SetDoNotAllowTracks(False); k.SetDoNotAllowVias(False); k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); k.SetLayerSet(ls)
    o = k.Outline(); o.NewOutline()
    for x, y in ((CX-16.8,-9.5),(CX+17.8,-9.5),(CX+17.8,9.5),(CX-16.8,9.5)): o.Append(MM(x), MM(y))
    b.Add(k)
for f in b.GetFootprints():          # solid (no thermal spokes) connection of every GND pad to the pours
    for pad in f.Pads():
        if pad.GetNetname() == "GND": pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
for t in b.GetTracks():
    if t.GetClass() != "PCB_VIA" and t.GetWidth() < MM(0.2): t.SetWidth(MM(0.25))
FILL = pcbnew.ZONE_FILLER(b); FILL.Fill(b.Zones())

# ---- GND stitching vias. A via goes where its whole footprint lies inside filled GND copper on every layer (so it touches nothing else).
STITCH = 3.0 if LAYERS == 2 else 4.0
VIA_D, VIA_DR, MARGIN, R = 0.6, 0.3, 1.0, 0.55
zones = {z.GetFirstLayer(): z for z in b.Zones() if not z.GetIsRuleArea()}
holes = [(t.GetPosition().x, t.GetPosition().y) for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
holes += [(pad.GetPosition().x, pad.GetPosition().y) for f in b.GetFootprints() for pad in f.Pads() if pad.GetDrillSize().x > 0]
placed = []
def near(c, lst, d): return any((hx - c.x) ** 2 + (hy - c.y) ** 2 < MM(d) ** 2 for hx, hy in lst)
def solid(pos): return all(z.HitTestFilledArea(l, pos, 0) for l, z in zones.items())
RING = ((1,0),(-1,0),(0,1),(0,-1),(.7,.7),(-.7,.7),(.7,-.7),(-.7,-.7))
def try_via(x, y, hole_d=1.0, via_d=1.3):
    c = VECTOR2I(MM(x), MM(y))
    if not (EDGE_W + 0.8 < x < EDGE_E - 0.8 and -HALF + 0.8 < y < HALF - 0.8): return False
    if near(c, holes, hole_d) or near(c, placed, via_d): return False
    if not solid(c) or not all(solid(VECTOR2I(MM(x + R*dx), MM(y + R*dy))) for dx, dy in RING): return False
    v = pcbnew.PCB_VIA(b); v.SetPosition(c); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetNet(gnd)
    v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DR)); b.Add(v); placed.append((c.x, c.y)); return True
n_grid = n_fence = n_island = 0
x = EDGE_W + MARGIN
while x < EDGE_E - MARGIN:                                    # 1. regular grid
    y = -HALF + MARGIN
    while y < HALF - MARGIN:
        n_grid += try_via(x, y, 1.2, 1.5)
        y += STITCH
    x += STITCH
# 2. a fence of vias beside the audio chain (both sides of every audio track, every 2 mm): ground copper tied through on both sides
AUDIO = ("/DAC_OUT", "/MIC_A", "/MIC_B", "/NODE_B", "/AF_OUT")
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA" or t.GetNetname() not in AUDIO: continue
    s, e = t.GetStart(), t.GetEnd(); L = math.hypot(e.x - s.x, e.y - s.y) / 1e6
    if L < 0.01: continue
    ux, uy = (e.x - s.x) / 1e6 / L, (e.y - s.y) / 1e6 / L
    off = t.GetWidth() / 2e6 + 0.95
    for i in range(int(L / 2.0) + 2):
        d = min(i * 2.0, L)
        px, py = s.x / 1e6 + ux * d, s.y / 1e6 + uy * d
        for sgn in (1, -1):
            n_fence += try_via(px - uy * off * sgn, py + ux * off * sgn, 0.9, 1.6)
# 3. every separate piece of GND copper gets a via (an island without a via/pad of its net is removed in the last fill)
gnd_pads = [(pad.GetPosition().x, pad.GetPosition().y) for f in b.GetFootprints() for pad in f.Pads() if pad.GetNetname() == "GND"]
for l, z in zones.items():
    poly = z.GetFilledPolysList(l)
    for i in range(poly.OutlineCount()):
        if any(poly.Contains(VECTOR2I(px, py), i) for px, py in placed + gnd_pads + holes): continue
        bb = poly.Outline(i).BBox(); found = False
        yy = bb.GetTop()
        while yy < bb.GetBottom() and not found:
            xx = bb.GetLeft()
            while xx < bb.GetRight() and not found:
                if poly.Contains(VECTOR2I(xx, yy), i) and try_via(xx / 1e6, yy / 1e6, 0.9, 0.8):
                    found = True; n_island += 1
                xx += MM(0.4)
            yy += MM(0.4)
for z in zones.values(): z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
FILL.Fill(b.Zones())
print("stitching vias: grid %d, audio fence %d, island rescue %d" % (n_grid, n_fence, n_island))
pcbnew.SaveBoard(sys.argv[2], b)
print("post done")
