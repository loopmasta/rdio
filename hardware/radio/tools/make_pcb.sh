#!/bin/bash
# Rebuilds the PCB from hardware/radio/rdio.kicad_sch:
#   netlist -> placed board (build_pcb.py) -> Specctra DSN (patch_dsn.py) -> Freerouting -> SES import -> antenna trace + GND pours
#   + stitching vias
#   (post_pcb.py) -> drop dangling vias -> KiCad DRC.
# Usage: [LAYERS=4] hardware/radio/tools/make_pcb.sh [--install]       (default: 2 layers; LAYERS=4 adds a solid GND plane on In1.Cu)     (--install copies the result to hardware/radio/rdio.kicad_pcb)
# Needs KiCad 10 (kicad-cli and its bundled python), Java and the Freerouting jar. Override the paths with KICAD, JAVA, FREEROUTING, WORK.
set -e
HERE=$(cd "$(dirname "$0")" && pwd); HW="$HERE/.."
KICAD=${KICAD:-/Applications/KiCad/KiCad.app/Contents}
PY=$KICAD/Frameworks/Python.framework/Versions/Current/bin/python3
KCLI=${KCLI:-kicad-cli}
JAVA=${JAVA:-/opt/homebrew/opt/openjdk/bin/java}
FREEROUTING=${FREEROUTING:-$HOME/Documents/Projects/Tools/freerouting/freerouting-2.5.0.jar}
WORK=${WORK:-/tmp/rdio_pcb_work}
mkdir -p "$WORK"; cd "$WORK"
# the DRC limits live in the project file; give the work copies the same name
for n in final final2; do cp "$HW/rdio.kicad_pro" "$n.kicad_pro"; done
$KCLI sch export netlist --format kicadsexpr -o rdio.net "$HW/rdio.kicad_sch" >/dev/null
rm -f work.kicad_pcb; $PY "$HERE/build_pcb.py" rdio.net work.kicad_pcb > build.log 2>&1
grep -q "^saved" build.log || { echo "BUILD FAILED"; grep -v assert build.log | tail -8; exit 1; }
route() {   # route <board.kicad_pcb> <name> [patch_dsn options...]  ->  <name>.ses
  local board=$1 name=$2; shift 2
  $PY "$HERE/export_dsn.py" "$board" "$name.dsn" 2>&1 | grep "dsn export"
  python3 -I "$HERE/patch_dsn.py" "$name.dsn" "$name.p.dsn" --clearance 230 "$@"
  rm -f "$name.ses"
  timeout 280 "$JAVA" -Djava.awt.headless=true -jar "$FREEROUTING" -de "$name.p.dsn" -do "$name.ses" -mp 60 2>&1 \
    | grep -E "Auto-routing stage completed" | sed 's/^20[^ ]* [^ ]* //' | sed 's/ using .*//'
}
export LAYERS=${LAYERS:-2}
if [ "$LAYERS" = "4" ]; then
  # 4 layers: In1.Cu is a solid GND plane. Stage A routes the two long power nets alone (Freerouting leaves them open otherwise),
  # stage B routes everything else around them.
  route work.kicad_pcb stageA --plane In1.Cu --only-nets "${POWER_NETS:-VBAT,/VIN_ESP}"
  $PY "$HERE/import_ses.py" work.kicad_pcb stageA.ses stageA.kicad_pcb 2>&1 | grep "ses import"
  route stageA.kicad_pcb stageB --plane In1.Cu
  $PY "$HERE/import_ses.py" stageA.kicad_pcb stageB.ses routed.kicad_pcb 2>&1 | grep "ses import"
else
  route work.kicad_pcb stage1
  $PY "$HERE/import_ses.py" work.kicad_pcb stage1.ses routed.kicad_pcb 2>&1 | grep "ses import"
fi
$PY "$HERE/post_pcb.py" routed.kicad_pcb final.kicad_pcb 2>&1 | grep -v -E "assert|leak"
$KCLI pcb drc --severity-all --format json -o drc.json final.kicad_pcb >/dev/null 2>&1
$PY "$HERE/remove_dangling_vias.py" final.kicad_pcb drc.json final2.kicad_pcb 2>&1 | grep -v -E "assert|leak"
$KCLI pcb drc --severity-all --format report -o drc.txt final2.kicad_pcb >/dev/null
grep -E "^\[" drc.txt | sed 's/ (.*//' | sort | uniq -c | sort -rn
grep "Found" drc.txt
echo "result: $WORK/final2.kicad_pcb"
if [ "$1" = "--install" ]; then cp final2.kicad_pcb "$HW/rdio.kicad_pcb"; echo "installed into hardware/radio/rdio.kicad_pcb"; fi
