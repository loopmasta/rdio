import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
ok = pcbnew.ImportSpecctraSES(b, sys.argv[2])
print("ses import", ok)
pcbnew.SaveBoard(sys.argv[3], b)
