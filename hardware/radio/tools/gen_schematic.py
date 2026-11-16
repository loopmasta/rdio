import re, uuid, sys
"""Generates hardware/radio/rdio.kicad_sch (direct pin-to-pin schematic of the rdio ESP32 + SA818S carrier).

Usage:  python3 -I hardware/radio/tools/gen_schematic.py [output.kicad_sch]     (default: hardware/radio/rdio.kicad_sch)

Reads tools/base_lib_symbols.txt (the NodeMCU symbol plus the Device/power symbols) and KiCad's Connector.kicad_sym (SMA symbol).
All ids are deterministic, so running it twice gives the same file. Regenerating changes every id once compared with an older file:
rebuild the PCB afterwards with tools/make_pcb.sh (it works from the netlist of the schematic).
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
DST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "rdio.kicad_sch")
lib = open(os.path.join(HERE, "base_lib_symbols.txt")).read().rstrip('\n')
ROOT = "4521836c-930b-48e6-8608-6d97a97cafe1"
_n = [0]
def U():
    _n[0] += 1
    return str(uuid.uuid5(uuid.UUID(ROOT), "rdio-sch-%d" % _n[0]))
FONT = '(effects (font (size 1.27 1.27)))'
HID = '(effects (font (size 1.27 1.27)) (hide yes))'

# ---- VBAT rail symbol cloned from +3V3
i = lib.index('(symbol "power:+3V3"'); d = 0; j = i
while True:
    c = lib[j]
    if c == '(': d += 1
    elif c == ')':
        d -= 1
        if d == 0: break
    j += 1
vbat_sym = '\t\t' + lib[i:j+1].replace('+3V3', 'VBAT')

def two_pin(name, ref, pins=2):
    p2 = f'\n\t\t\t\t(pin passive line (at 0 -3.81 90) (length 1.27) (name "2" {FONT}) (number "2" {FONT}))' if pins == 2 else ''
    return f'''\t\t(symbol "Board:{name}" (exclude_from_sim no) (in_bom yes) (on_board yes)
\t\t\t(property "Reference" "{ref}" (at 2.54 0 0) {FONT})
\t\t\t(property "Value" "{name}" (at 0 0 0) {FONT})
\t\t\t(property "Footprint" "" (at 0 0 0) {HID})
\t\t\t(property "Datasheet" "" (at 0 0 0) {HID})
\t\t\t(symbol "{name}_0_1" (rectangle (start -1.27 -2.54) (end 1.27 2.54) (stroke (width 0.254) (type default)) (fill (type none))))
\t\t\t(symbol "{name}_1_1"
\t\t\t\t(pin passive line (at 0 3.81 270) (length 1.27) (name "1" {FONT}) (number "1" {FONT})){p2}
\t\t\t)
\t\t)'''

# ---- SA818S with the module's physical pin layout (datasheet pinout, top view)
SX, SY0 = 269.24, 168.91
TOPX = {"7":-15.24,"6":-10.16,"5":-5.08,"4":0,"3":5.08,"2":10.16,"1":15.24}
BOTX = {"12":-15.24,"13":-10.16,"14":-5.08,"15":0,"16":5.08,"17":10.16,"18":15.24}
LEFTY = {"8":7.62,"9":2.54,"10":-2.54,"11":-7.62}
PIN = {"1":("SQ (Audio ON)","output"),"2":("NC","no_connect"),"3":("AF_OUT","output"),"4":("NC","no_connect"),
       "5":("PTT","input"),"6":("PD","input"),"7":("H/L","input"),"8":("VBAT","power_in"),"9":("GND","power_in"),
       "10":("GND","power_in"),"11":("NC","no_connect"),"12":("ANT","passive"),"13":("NC","no_connect"),
       "14":("NC","no_connect"),"15":("NC","no_connect"),"16":("RXD","input"),"17":("TXD","output"),"18":("MIC_IN","input")}
def sa_pos(n):
    if n in TOPX: return (SX+TOPX[n], SY0-16.51)
    if n in BOTX: return (SX+BOTX[n], SY0+16.51)
    return (SX-22.86, SY0-LEFTY[n])
def sa_symbol():
    s = f'''\t\t(symbol "Board:SA818S" (exclude_from_sim no) (in_bom yes) (on_board yes)
\t\t\t(property "Reference" "U" (at 0 19.05 0) {FONT})
\t\t\t(property "Value" "SA818S" (at 0 -19.05 0) {FONT})
\t\t\t(property "Footprint" "rdio:DRA818_SA818" (at 0 0 0) {HID})
\t\t\t(property "Datasheet" "" (at 0 0 0) {HID})
\t\t\t(symbol "SA818S_0_1" (rectangle (start -20.32 13.97) (end 20.32 -13.97) (stroke (width 0.254) (type default)) (fill (type background))))
\t\t\t(symbol "SA818S_1_1"\n'''
    for n in [str(k) for k in range(1,19)]:
        nm,t = PIN[n]
        if n in TOPX: at = f"{TOPX[n]:.2f} 16.51 270"
        elif n in BOTX: at = f"{BOTX[n]:.2f} -16.51 90"
        else: at = f"-22.86 {LEFTY[n]:.2f} 0"
        s += f'\t\t\t\t(pin {t} line (at {at}) (length 2.54) (name "{nm}" {FONT}) (number "{n}" {FONT}))\n'
    return s + '\t\t\t)\n\t\t)'
def kicad_sym(name, new):
    t = open("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Connector.kicad_sym").read()
    i = t.index(f'(symbol "{name}"'); d = 0; j = i
    while True:
        c = t[j]
        if c == '(': d += 1
        elif c == ')':
            d -= 1
            if d == 0: break
        j += 1
    return '\t\t' + t[i:j+1].replace(f'(symbol "{name}"', f'(symbol "{new}"', 1)
def trim3():
    return f'''\t\t(symbol "Board:R_Trim3" (exclude_from_sim no) (in_bom yes) (on_board yes)
\t\t\t(property "Reference" "R" (at 2.54 0 0) {FONT})
\t\t\t(property "Value" "R_Trim3" (at 0 0 0) {FONT})
\t\t\t(property "Footprint" "" (at 0 0 0) {HID})
\t\t\t(property "Datasheet" "" (at 0 0 0) {HID})
\t\t\t(symbol "R_Trim3_0_1" (rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none))))
\t\t\t(symbol "R_Trim3_1_1"
\t\t\t\t(pin passive line (at 0 3.81 270) (length 1.27) (name "1" {FONT}) (number "1" {FONT}))
\t\t\t\t(pin passive line (at 0 -3.81 90) (length 1.27) (name "3" {FONT}) (number "3" {FONT}))
\t\t\t\t(pin passive line (at 3.81 0 180) (length 2.54) (name "2" {FONT}) (number "2" {FONT}))
\t\t\t)
\t\t)'''
lib_all = lib + '\n' + '\n'.join([vbat_sym, two_pin("FerriteBead","FB"), kicad_sym("Conn_Coaxial","Connector:Conn_Coaxial"), sa_symbol()]) + '\n\t)'

esp = {}
for m in re.finditer(r'\(pin \w+ line \(at ([-\d.]+) ([-\d.]+) \d+\) \(length [\d.]+\) \(name "([^"]*)".*?\(number "(\d+)"', lib):
    esp[m.group(4)] = (float(m.group(1)), float(m.group(2)), m.group(3))
assert len(esp) == 38

body = []; pwr = [0]
f = lambda v: f'{v:.2f}'.rstrip('0').rstrip('.')
def wire(x1,y1,x2,y2): body.append(f'\t(wire (pts (xy {f(x1)} {f(y1)}) (xy {f(x2)} {f(y2)})) (stroke (width 0) (type default)) (uuid "{U()}"))')
def poly(*pts):
    for a,b in zip(pts, pts[1:]): wire(a[0],a[1],b[0],b[1])
def junc(x,y): body.append(f'\t(junction (at {f(x)} {f(y)}) (diameter 0) (color 0 0 0 0) (uuid "{U()}"))')
def label(net,x,y,a=0):
    body.append(f'\t(label "{net}" (at {f(x)} {f(y)} {a}) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{U()}"))')
def text(t,x,y): body.append(f'\t(text "{t}" (exclude_from_sim no) (at {f(x)} {f(y)} 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{U()}"))')
def nc(x,y): body.append(f'\t(no_connect (at {f(x)} {f(y)}) (uuid "{U()}"))')
def symbol(lib_id,ref,val,x,y,pins,rot=0,hide=False,hideval=False,vat=None,fp=None,dnp=False):
    h = ' (hide yes)' if hide else ''
    hv = ' (hide yes)' if hideval else ''
    vx,vy = vat if vat else (x+2.54, y+1.27)
    s = f'\t(symbol (lib_id "{lib_id}") (at {f(x)} {f(y)} {rot}) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp {"yes" if dnp else "no"}) (uuid "{U()}")\n'
    if rot == 90 and not hide:
        s += f'\t\t(property "Reference" "{ref}" (at {f(x)} {f(y-3.81)} 0) (effects (font (size 1.27 1.27)){h}))\n'
        s += f'\t\t(property "Value" "{val}" (at {f(x)} {f(y+3.81)} 0) (effects (font (size 1.27 1.27)){hv}))\n'
    else:
        s += f'\t\t(property "Reference" "{ref}" (at {f(x+2.54)} {f(y-1.27)} 0) (effects (font (size 1.27 1.27)) (justify left){h}))\n'
        s += f'\t\t(property "Value" "{val}" (at {f(vx)} {f(vy)} 0) (effects (font (size 1.27 1.27)) (justify left){hv}))\n'
    s += f'\t\t(property "Footprint" "{fp or ""}" (at {f(x)} {f(y)} 0) {HID})\n\t\t(property "Datasheet" "" (at {f(x)} {f(y)} 0) {HID})\n'
    for p in pins: s += f'\t\t(pin "{p}" (uuid "{U()}"))\n'
    s += f'\t\t(instances (project "rdio" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n\t)'
    body.append(s)
def power(kind,x,y,rot=0):
    pwr[0]+=1
    ref = f'#FLG{pwr[0]:02d}' if kind=='PWR_FLAG' else f'#PWR{pwr[0]:02d}'
    symbol(f'power:{kind}', ref, kind, x, y, ["1"], rot=rot, hide=True, hideval=(kind in ('PWR_FLAG','GND')))
FPMAP = {r:"Resistor_SMD:R_0603_1608Metric" for r in ("R1","R2","R3","R4","R5","R9")}
FPMAP.update({r:"Capacitor_SMD:C_0603_1608Metric" for r in ("C1","C3","C4","C5","C7")})
FPMAP.update({"C2":"Capacitor_SMD:CP_Elec_6.3x5.4","C8":"Capacitor_SMD:CP_Elec_6.3x5.4","C6":"Capacitor_SMD:CP_Elec_6.3x5.8",
              "FB1":"Inductor_SMD:L_0805_2012Metric"})
def part(lib_id,ref,val,x,y,rot=0,dnp=False):
    symbol(lib_id,ref,val,x,y,["1","2"],rot,dnp=dnp,fp=FPMAP.get(ref))

# ================= ESP32
EX,EY = 152.4,152.4
symbol("Board:NodeMCU-32S-38pin","U1","NodeMCU ESP32S 38pin",EX,EY,[str(n) for n in range(1,39)],vat=(EX,EY+29.21),fp="rdio:ESP32_DevKit_38pin_PinHoles")
P = lambda n: (EX+esp[n][0], EY-esp[n][1])
used = {"1","5","9","14","19","32","38","36","33","31","28","27"}
for n in esp:
    if n not in used: nc(*P(n))

# ================= SA818S (physical layout)
symbol("Board:SA818S","U2","SA818S",SX,SY0,[str(k) for k in range(1,19)],vat=(SX,SY0+22.86),fp="rdio:DRA818_SA818")
sa_used = {"1","3","5","6","7","8","9","10","12","16","17","18"}
for n in PIN:
    if n not in sa_used: nc(*sa_pos(n))

# ---- ESP left side
x,y = P("1");  wire(x,y,127,y); power("+3V3",127,y)
x,y = P("14"); wire(x,y,127,y); power("GND",127,y); power("PWR_FLAG",127,y)
x,y = P("19")
wire(110.49,y,x,y); junc(121.92,y)
part("Board:FerriteBead","FB1","ferrite 2A DNP",106.68,y,90,dnp=True); wire(102.87,y,99.06,y); power("VBAT",99.06,y); power("PWR_FLAG",99.06,y)
part("Device:C_Polarized","C8","100uF DNP",121.92,182.88,dnp=True); wire(121.92,y,121.92,179.07); wire(121.92,186.69,121.92,191.77); power("GND",121.92,191.77)
label("VIN_ESP",124.46,y)
power("PWR_FLAG",121.92,y)
# 0 ohm link in parallel with FB1: fitted while FB1/C8 are not populated
junc(101.6,y); junc(113.03,y)
poly((101.6,y),(101.6,165.1),(102.87,165.1)); part("Device:R","R9","0R link",106.68,165.1,90); poly((110.49,165.1),(113.03,165.1),(113.03,y))

# analog in: AF_OUT (top pin 3) -> C1 -> node B -> GPIO34
XA = 120.65; AFY = 106.68
ax,ay = sa_pos("3")
x,y = P("5");  poly((x,y),(XA,y),(XA,AFY),(240.03,AFY))
part("Device:C","C1","1uF",243.84,AFY,90); poly((247.65,AFY),(ax,AFY),(ax,ay))
junc(160.02,AFY); junc(215.9,AFY)
part("Device:R","R2","100k",160.02,114.3); wire(160.02,AFY,160.02,110.49); wire(160.02,118.11,160.02,120.65); power("GND",160.02,120.65)
part("Device:R","R1","100k",215.9,96.52);  wire(215.9,AFY,215.9,100.33); wire(215.9,92.71,215.9,88.9); power("+3V3",215.9,88.9)

# analog out: GPIO25 -> C4 -> R3 -> MIC_IN (bottom pin 18, reached on the right side of the module)
XB = 111.76; MICY = 81.28; XR = 292.1
mx,my = sa_pos("18")
x,y = P("9");  poly((x,y),(XB,y),(XB,MICY),(123.19,MICY))
part("Device:C","C4","1uF",127,MICY,90); wire(130.81,MICY,148.59,MICY)
part("Device:R","R3","100k",152.4,MICY,90); poly((156.21,MICY),(XR,MICY),(XR,190.5),(mx,190.5),(mx,my))
junc(185.42,MICY); junc(198.12,MICY)
part("Device:R","R4","1k",185.42,91.44)
wire(185.42,MICY,185.42,87.63); wire(185.42,95.25,185.42,99.06); power("GND",185.42,99.06)
part("Device:C","C5","33nF",198.12,91.44);    wire(198.12,MICY,198.12,87.63); wire(198.12,95.25,198.12,99.06); power("GND",198.12,99.06)

# ---- ESP right side
x,y = P("38"); wire(x,y,x+2.54,y); power("GND",x+2.54,y,90)
x,y = P("32"); wire(x,y,x+2.54,y); power("GND",x+2.54,y,90)
# SQ: GPIO22 -> top pin 1
sx,sy = sa_pos("1"); x,y = P("36")
poly((x,y),(190.5,y),(190.5,114.3),(sx,114.3),(sx,sy))
# PTT: GPIO21 -> top pin 5 (straight row), R5 pull-up
px,py = sa_pos("5"); x,y = P("33")
poly((x,y),(px,y),(px,py))
junc(231.14,y); wire(231.14,y,231.14,y-3.81); part("Device:R","R5","10k",231.14,y-7.62); wire(231.14,y-11.43,231.14,y-13.97); power("+3V3",231.14,y-13.97)
# H/L: GPIO19 -> top pin 7 (straight row)
hx,hy = sa_pos("7"); x,y = P("31")
poly((x,y),(hx,y),(hx,hy))
# PD: top pin 6 tied to 3V3
dx,dy = sa_pos("6"); wire(dx,dy,dx,dy-2.54); power("+3V3",dx,dy-2.54)
# UART: GPIO17 TX -> RXD (bottom 16); TXD (bottom 17) -> GPIO16 RX
rx,ry = sa_pos("16"); tx,ty = sa_pos("17")
x,y = P("28"); poly((x,y),(190.5,y),(190.5,200.66),(rx,200.66),(rx,ry))
x,y = P("27"); poly((x,y),(185.42,y),(185.42,205.74),(tx,205.74),(tx,ty))

# ---- SA818S left side: power
vx,vy = sa_pos("8"); wire(vx,vy,vx-5.08,vy); power("VBAT",vx-5.08,vy)
g9x,g9y = sa_pos("9"); g10x,g10y = sa_pos("10")
poly((g9x,g9y),(g9x-5.08,g9y),(g9x-5.08,g10y)); wire(g10x,g10y,g10x-5.08,g10y); power("GND",g10x-5.08,g10y)
for ref,val,cx in (("C6","220uF",213.36),("C7","100nF",226.06)):
    part("Device:C_Polarized" if ref=="C6" else "Device:C",ref,val,cx,170.18)
    wire(cx,166.37,cx,161.29); power("VBAT",cx,161.29)
    wire(cx,173.99,cx,179.07); power("GND",cx,179.07)
# ---- antenna (bottom pin 12)
ax2,ay2 = sa_pos("12"); wire(ax2,ay2,ax2,190.5)
symbol("Connector:Conn_Coaxial","J2","SMA edge",ax2+5.08,190.5,["1","2"],fp="rdio:SMA_KooingTech_SMA-KE_EdgeMount")
power("GND",ax2+5.08,195.58)

# ---- 3V3 decoupling
for ref,val,cx,lid in (("C2","100uF",25.4,"Device:C_Polarized"),("C3","100nF",38.1,"Device:C")):
    part(lid,ref,val,cx,203.2); wire(cx,199.39,cx,194.31); power("+3V3",cx,194.31); wire(cx,207.01,cx,212.09); power("GND",cx,212.09)

# ---- net names
for net,x,y,a in (("NODE_B",127,AFY,0),("AF_OUT",258,AFY,0),("DAC_OUT",116.84,149.86,0),("MIC_A",134.62,MICY,0),("MIC_B",226.06,MICY,0),
                  ("SQ",178,134.62,0),("PTT",200,142.24,0),("HL",200,147.32,0),("SA_RXD",210,200.66,0),("SA_TXD",210,205.74,0)):
    label(net,x,y,a)

notes = [
 "rdio: SA818S radio interface (hardware only). Direct pin-to-pin wiring; only +3V3, VBAT and GND use rail symbols. Pin numbers = NodeMCU ESP32S 38pin header.",
 "U2 is drawn in the module's real pin layout (datasheet pinout, top view): pins 7..1 top, 12..18 bottom, 8..11 left. Footprint rdio:DRA818_SA818 (pad pattern taken from the rdio project, check against the module). Two unnumbered right-side pads are not in the symbol.",
 "AF_OUT (700mV, 200 ohm) -> C1 -> node B (R1||R2 = 1.65V bias) -> GPIO34 (ADC1_CH6). GPIO25 DAC -> C4 -> R3 100k / R4 1k -> MIC_IN (about -40 dB), C5 33nF low-pass. MIC_IN impedance unknown: verify at bench.",
 "PTT (GPIO21, open-drain): R5 pull-up -> reset/crash = receive. PD (pin 6) tied to 3V3: module always on. H/L (GPIO19, software controlled): output low = low power, release = high power. NEVER drive high.",
 "SQ (SA818S pin 1 'Audio ON', low while receiving) -> GPIO22 direct. UART2: GPIO17 TX -> RXD pin 16; TXD pin 17 -> GPIO16 RX, direct. 9600 8N1.",
 "Power: 5V comes from the NodeMCU own USB-C through its VIN pin (pin 19, net VIN_ESP). The module VBAT hangs off it through R9 (0R link); FB1 + C8 are DO NOT POPULATE (fit FB1 + C8 and remove R9 to try the filter). The radio draws up to 0.75A in TX: use a USB source rated >= 1A. Do not power the module from the NodeMCU 3V3 pin. Fit antenna or dummy load before transmitting.",
]
for k,t in enumerate(notes): text(t,20,258+4.5*k)

out = f'''(kicad_sch
\t(version 20250114)
\t(generator "eeschema")
\t(generator_version "9.0")
\t(uuid "{ROOT}")
\t(paper "A3")
\t(title_block
\t\t(title "rdio: ESP32 to SA818S radio interface")
\t\t(rev "4")
\t)
{lib_all}
''' + '\n'.join(body) + '\n\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n'
open(DST,'w').write(out); print("ok",len(body))
