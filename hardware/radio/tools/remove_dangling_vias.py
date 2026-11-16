import sys, json, pcbnew
from pcbnew import FromMM as MM
src, drc, dst = sys.argv[1:4]
b = pcbnew.LoadBoard(src)
pos = []
for v in json.load(open(drc))["violations"]:
    if v["type"] == "via_dangling":
        it = v["items"][0]["pos"]; pos.append((it["x"], it["y"]))
n = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition()
        if any(abs(pcbnew.ToMM(p.x)-x) < 0.05 and abs(pcbnew.ToMM(p.y)-y) < 0.05 for x, y in pos):
            b.Remove(t); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(dst, b)
print("removed dangling vias:", n)
