"""Final clean-up of the board, so the KiCad DRC has nothing left but real findings. Idempotent. Usage: tidy_pcb.py <in.kicad_pcb> <out.kicad_pcb>
  * removes the "ant_corridor" rule area: it only kept the autorouter out of the antenna path, and the hand-drawn antenna trace lies inside it
  * SA818S (U2): the reference designator sits in the middle of the module (upright)
  * the USB-C outline on the bottom silkscreen leaves out the part C8 covers; its label moves clear of C8's pad
  * GND pads of every footprint get the solid zone connection again, and the zones are refilled
  * passive reference designators: moved next to their part where they overlapped something (see REF_MOVES)"""
import sys, pcbnew
from pcbnew import FromMM as MM, ToMM, VECTOR2I
b = pcbnew.LoadBoard(sys.argv[1])
CX = -7.5                                   # SA818S centre, as in build_pcb.py
def fp(ref): return [f for f in b.GetFootprints() if f.GetReference() == ref][0]

# --- U2: the reference designator sits in the middle of the module (upright); the footprint itself (rdio.pretty) has the outline in pieces
# that stop short of the pads
u2 = fp("U2")
f = u2.Reference(); f.SetTextAngle(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T)); f.SetPosition(VECTOR2I(MM(CX), MM(0)))

# --- USB-C outline of the DevKit (bottom silkscreen, drawn by build_pcb.py): the DNP electrolytic C8 stands over its top and left side, so
# those two sides are drawn only where C8 is not
X1, X2, YY = 16.7, 23.8, 4.5
for g in list(b.GetDrawings()):
    if isinstance(g, pcbnew.PCB_SHAPE) and g.GetLayer() == pcbnew.B_SilkS and g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        sx, sy, ex, ey = (ToMM(v) for v in (g.GetStart().x, g.GetStart().y, g.GetEnd().x, g.GetEnd().y))
        top = abs(sy + YY) < 1e-3 and abs(ey + YY) < 1e-3 and min(sx, ex) > X1 - 1e-3 and max(sx, ex) > X2 - 1e-3
        left = abs(sx - X1) < 1e-3 and abs(ex - X1) < 1e-3 and max(abs(sy), abs(ey)) <= YY + 1e-3 and min(sy, ey) < -1e-3
        if (abs(sy + YY) < 1e-3 and abs(ey + YY) < 1e-3 and abs(min(sx, ex) - X1) < 1e-3) or (left and abs(max(sy, ey) - YY) < 1e-3 and abs(min(sy, ey) + YY) < 1e-3):
            if abs(sy + YY) < 1e-3:        g.SetStart(VECTOR2I(MM(22.9), g.GetStart().y)); g.SetEnd(VECTOR2I(MM(X2), g.GetEnd().y))
            else:                          g.SetStart(VECTOR2I(MM(X1), MM(1.0))); g.SetEnd(VECTOR2I(MM(X1), MM(YY)))

for t in b.GetDrawings():
    if isinstance(t, pcbnew.PCB_TEXT) and t.GetText() == "USB-C" and t.GetLayer() == pcbnew.B_SilkS:     # horizontal, below C8
        t.SetTextAngle(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T)); t.SetPosition(VECTOR2I(MM(20.25), MM(2.5)))

# --- reference designators: ref -> (x, y) in board mm, upright
REF_MOVES = {"R1": (-9.0, -7.0), "R2": (-11.0, -3.0), "R9": (19.0, -9.6), "FB1": (14.5, -9.6), "C6": (-19.0, 6.6)}
for ref, (x, y) in REF_MOVES.items():
    t = fp(ref).Reference(); t.SetTextAngle(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T)); t.SetPosition(VECTOR2I(MM(x), MM(y)))
# last, because removing a zone invalidates the footprint wrappers of this KiCad version
for z in list(b.Zones()):
    if z.GetIsRuleArea() and z.GetZoneName() == "ant_corridor": b.Remove(z)

# solid (no thermal spokes) connection of every GND pad, as post_pcb.py sets it: a footprint swapped in later would have lost it
for f in b.GetFootprints():
    for pad in f.Pads():
        if pad.GetNetname() == "GND": pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[2], b)
print("saved", sys.argv[2])
