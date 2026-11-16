# hardware/radio/tools: regenerate the schematic and the PCB

These scripts produce `hardware/radio/rdio.kicad_sch` and `hardware/radio/rdio.kicad_pcb`. Run them from the repository root.

| file | what it does |
|---|---|
| `gen_schematic.py` | writes the schematic (direct pin-to-pin wiring, net names on the wires). Reads `base_lib_symbols.txt` (NodeMCU symbol, Device and power symbols) and KiCad's `Connector.kicad_sym` (SMA). Deterministic ids. |
| `gen_3d_placeholders.py` | writes the simple 3D placeholder models in `hardware/radio/rdio.3dshapes/` (DevKit on its two 5 mm headers and its own 2.5 mm sockets, SA818S, SMA jack). Edit `HEADER_H`, `SOCKET_H` etc. there, then rebuild with `make_pcb.sh --install`. |
| `make_pcb.sh` | the whole PCB pipeline, see below. `--install` copies the result to `hardware/radio/rdio.kicad_pcb`. Default is the 2-layer board; `LAYERS=4` builds a 4-layer variant with a solid GND plane on In1.Cu. |
| `patch_dsn.py` | patches the Specctra DSN before Freerouting: In1.Cu as GND plane, route only some nets (stage A: the long power nets), router clearance margin. |
| `build_pcb.py` | netlist -> placed board. **Part placement is the `place` table** (DevKit frame: x right towards the USB end, y down, mm). |
| `export_dsn.py`, `import_ses.py` | Specctra DSN export and SES import (KiCad python). |
| `post_pcb.py` | after routing: hand-drawn antenna trace (0.8 mm on 2 layers, 0.4 mm on 4), GND pours on every layer (0.25 mm clearance), GND stitching vias (grid, a fence beside the audio chain, one via per pour piece), no top pour under the SA818S, solid GND pad connections. |
| `flip_pcb.py` | the very last step: turns the whole board over (mirror about the vertical centre line, every item changes side) so that the DevKit and the small parts end up on the top and the radio module and the SMA on the bottom. The other scripts work with the module on the top side; do not run them on the finished board. Refuses to run twice. |
| `tidy_pcb.py` | last step: removes the antenna corridor rule area (it only keeps the autorouter out; the hand-drawn antenna trace lies inside it), places the reference designators that overlapped something, trims the USB-C outline on the bottom silkscreen around C8. Idempotent. |
| `remove_dangling_vias.py` | drops vias that touch only one layer (from the KiCad DRC json). |

Typical flow after a schematic change:

    python3 -I hardware/radio/tools/gen_schematic.py      # only if you edit the generator
    hardware/radio/tools/make_pcb.sh                      # builds in /tmp/rdio_pcb_work, prints the KiCad DRC summary
    hardware/radio/tools/make_pcb.sh --install            # same, then copies the board into hardware/radio/

Requirements (paths from this Mac, override with the environment variables KICAD, JAVA, FREEROUTING, WORK):
KiCad 10.0.6 (`kicad-cli`, bundled python with `pcbnew`), Java (`/opt/homebrew/opt/openjdk/bin/java`; the `java` on PATH is only a stub)
and Freerouting 2.5.0 (`~/Documents/Projects/Tools/freerouting/freerouting-2.5.0.jar`).

Things to know:
* With `LAYERS=4` the board is routed in two stages: stage A routes VBAT and VIN_ESP alone (Freerouting leaves the long power runs open otherwise), stage B everything else.
* The autorouter cannot route the 433 MHz antenna net (it sits in a reserved corridor); `post_pcb.py` draws it by hand.
* Regenerating the PCB discards manual edits (silkscreen touch-ups, moved parts). Put such changes into `build_pcb.py` instead.
* Routing is not guaranteed to complete after you move parts: check the "unrouted" count in the summary (1 is expected: the antenna net).
* The right-angle SMA footprint J3 is KiCad's own (copied into `rdio.pretty`); its position and the extra board edge on the antenna-track side are `J3_X` and `HALF_N` in `build_pcb.py`. `rdio.kicad_dru` (next to the project) makes the DRC accept that J2 and J3 overlap.
* Footprints come from `hardware/radio/rdio.pretty` (the SA818S pad pattern and the DevKit header holes are those of the earlier rdio carrier board, which was built and probed; the KooingTech SMA-KE footprint was built from the generic SMA-KE drawing, with a 3D model in `hardware/radio/rdio.3dshapes/`) and KiCad's libraries.
* KiCad 10 rewrites files it opens; close KiCad before running `--install`.

## The pictures in `hardware/radio/`

`rdio-pcb-3d.png` (top side, with the DevKit placeholder and the SMA connector; the small parts are hidden under the DevKit) and `rdio-pcb-bottom.png` (bottom side, with the radio module, the SMA connector and the DevKit stack below) are KiCad renders:

    cd hardware/radio
    export KICAD_CONFIG_HOME=<dir with a copy of your KiCad 10.0 settings in which show_footprints_insert, show_footprints_normal and show_footprints_not_in_posfile are true and show_footprints_dnp is false in 3d_viewer.json>
    kicad-cli pcb render --side top --quality high --preset follow_pcb_editor --width 2000 --height 1250 --rotate '-50,0,-20' -o rdio-pcb-3d.png rdio.kicad_pcb
    kicad-cli pcb render --side bottom --quality high --preset follow_pcb_editor --width 2000 --height 1250 --rotate '-50,0,-20' -o rdio-pcb-bottom.png rdio.kicad_pcb

`kicad-cli` takes the 3D viewer's settings from the user configuration, and by default the parts are switched off there, so both pictures need the copy with them switched on. With `show_footprints_dnp` false the parts that are not fitted (J2, FB1, C8) are left out, so the pictures show the build with the right-angle SMA J3 only. The models are the placeholders from `gen_3d_placeholders.py` and KiCad's own capacitor, resistor and inductor models.
