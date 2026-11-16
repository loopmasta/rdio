"""Turns the finished board over, like the page of a book (mirror about its vertical centre line, as KiCad's own bottom view does, so the text of
the new bottom side reads correctly from below; the antenna end moves from the left to the right): every item changes side and is mirrored,
so it is the same physical board. The generators build it with the radio module and the SMA on the top side and the small parts on
the bottom; after this step the small parts, with the DevKit, are on the TOP and the radio module and the SMA are on the BOTTOM.
Not idempotent (a second run would turn it back), so it refuses to run on a board that carries the marker in the title block.
Usage: flip_pcb.py <in.kicad_pcb> <out.kicad_pcb>"""
import sys, pcbnew
from pcbnew import VECTOR2I
MARK = "turned over by flip_pcb.py"
b = pcbnew.LoadBoard(sys.argv[1])
tb = b.GetTitleBlock()
if MARK in [tb.GetComment(i) for i in range(9)]: sys.exit("already flipped: " + sys.argv[1])
C = VECTOR2I(b.GetBoardEdgesBoundingBox().GetCenter().x, 0)      # the board keeps its place
TB = pcbnew.FLIP_DIRECTION_LEFT_RIGHT
fps = list(b.GetFootprints()); tracks = list(b.GetTracks()); zones = list(b.Zones()); draws = list(b.GetDrawings())
for f in fps: f.Flip(C, TB)
for t in tracks: t.Flip(C, TB)
for z in zones: z.Flip(C, TB)
for d in draws:
    if d.GetParentFootprint() is None: d.Flip(C, TB)
tb.SetComment(0, MARK); b.SetTitleBlock(tb)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[2], b)
print("saved", sys.argv[2])
