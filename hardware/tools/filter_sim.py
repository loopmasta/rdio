"""7th-order Chebyshev (0.1 dB) low-pass harmonic filters for the 2 m and 70 cm amateur bands.

Ideal values from the prototype g-values, then a simulation with real-part effects (inductor Q and parallel
capacitance, capacitor ESL and ESR) and a Monte-Carlo tolerance run, to choose standard (E24) values.
Run with KiCad's Python and numpy on the path:
  PYTHONPATH=/tmp/np39 /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 filter_sim.py
"""
import itertools, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "filter")
G = [1.1812, 1.4228, 2.0967, 1.5734, 2.0967, 1.4228, 1.1812]      # Chebyshev 0.1 dB ripple, n = 7
E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]

BANDS = {
    "vhf": dict(name="2 m", f_lo=144e6, f_hi=146e6, fc=155e6, QL=70, QC=400, ESL=0.8e-9, CP=0.06e-12),
    "uhf": dict(name="70 cm", f_lo=430e6, f_hi=440e6, fc=460e6, QL=90, QC=400, ESL=0.8e-9, CP=0.05e-12),
}

def ideal(fc):
    w = 2 * math.pi * fc
    return [G[i] / (50 * w) if i % 2 == 0 else G[i] * 50 / w for i in range(7)]    # C, L, C, L, C, L, C

def e24_near(v, unit):
    """the E24 values within about +-12 % of v (v in base units, unit = 1e-12 or 1e-9)"""
    x = v / unit
    dec = 10 ** math.floor(math.log10(x))
    cands = sorted({round(e * dec * m, 3) for e in E24 for m in (0.1, 1, 10)})
    return [c for c in cands if 0.88 * x <= c <= 1.12 * x]

def s_params(freq, vals, band, scale=None):
    """vals: 7 values in F/H. scale: optional per-element multipliers (tolerance). Returns S21, S11 (complex)."""
    w = 2 * np.pi * freq
    A = np.ones_like(w, dtype=complex); B = np.zeros_like(A); C_ = np.zeros_like(A); D = np.ones_like(A)
    for i, v in enumerate(vals):
        v = v * (scale[i] if scale is not None else 1.0)
        if i % 2 == 0:       # shunt capacitor: C in series with its ESL and ESR, to ground
            z = 1 / (1j * w * v) + 1j * w * band["ESL"] + 1 / (w * v * band["QC"])
            y = 1 / z
            M = (np.ones_like(w), np.zeros_like(w), y, np.ones_like(w))
        else:                # series inductor: (L + R) in parallel with its winding capacitance
            zl = 1j * w * v + w * v / band["QL"]
            z = 1 / (1 / zl + 1j * w * band["CP"])
            M = (np.ones_like(w), z, np.zeros_like(w), np.ones_like(w))
        A, B, C_, D = A * M[0] + B * M[2], A * M[1] + B * M[3], C_ * M[0] + D * M[2], C_ * M[1] + D * M[3]
    Z0 = 50.0
    den = A + B / Z0 + C_ * Z0 + D
    s21 = 2 / den
    s11 = (A + B / Z0 - C_ * Z0 - D) / den
    return s21, s11

def db(x): return 20 * np.log10(np.abs(x) + 1e-12)

def evaluate(vals, band, tol_c=0.05, tol_l=0.05, runs=300, seed=1):
    rng = np.random.default_rng(seed)
    f_band = np.linspace(band["f_lo"], band["f_hi"], 41)
    f_h2 = np.linspace(2 * band["f_lo"], 2 * band["f_hi"], 41)
    f_h3 = np.linspace(3 * band["f_lo"], 3 * band["f_hi"], 41)
    f_h5 = np.linspace(5 * band["f_lo"], 5 * band["f_hi"], 41)
    s21, s11 = s_params(f_band, vals, band)
    il, rl = -db(s21).max(), -db(s11).max()
    h2 = -db(s_params(f_h2, vals, band)[0]).min(); h3 = -db(s_params(f_h3, vals, band)[0]).min()
    h5 = -db(s_params(f_h5, vals, band)[0]).min()
    worst = dict(il=0.0, rl=99.0, h2=999.0)
    for _ in range(runs):
        sc = [1 + rng.uniform(-tol_c if i % 2 == 0 else -tol_l, tol_c if i % 2 == 0 else tol_l) for i in range(7)]
        a, b = s_params(f_band, vals, band, sc)
        worst["il"] = max(worst["il"], -db(a).max()); worst["rl"] = min(worst["rl"], -db(b).max())
        worst["h2"] = min(worst["h2"], -db(s_params(f_h2, vals, band, sc)[0]).min())
    return dict(il=il, rl=rl, h2=h2, h3=h3, h5=h5, worst=worst)

def design(key):
    band = BANDS[key]
    c1, l2, c3, l4, c5, l6, c7 = ideal(band["fc"])
    cs = [e * 1e-12 for e in e24_near(c1, 1e-12)]; ls2 = [e * 1e-9 for e in e24_near(l2, 1e-9)]
    cs3 = [e * 1e-12 for e in e24_near(c3, 1e-12)]; ls4 = [e * 1e-9 for e in e24_near(l4, 1e-9)]
    best = None
    for a, b, c, d in itertools.product(cs, ls2, cs3, ls4):
        vals = [a, b, c, d, c, b, a]                      # symmetric ladder
        r = evaluate(vals, band, runs=60)
        # score: low loss and good match in the band with tolerances, strong second-harmonic rejection
        score = r["worst"]["il"] * 3 + max(0, 18 - r["worst"]["rl"]) * 0.7 + max(0, 50 - r["worst"]["h2"]) * 0.2
        if best is None or score < best[0]: best = (score, vals)
    return band, [c1, l2, c3, l4], best[1]

def svg_plot(path, title, curves, xr, yr, marks=()):
    W, H, ml, mt, mr, mb = 900, 520, 70, 50, 20, 55
    def X(f): return ml + (f - xr[0]) / (xr[1] - xr[0]) * (W - ml - mr)
    def Y(v): return mt + (yr[1] - v) / (yr[1] - yr[0]) * (H - mt - mb)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Helvetica" font-size="13">',
         f'<rect width="{W}" height="{H}" fill="white"/>', f'<text x="{W / 2}" y="26" text-anchor="middle" font-size="17">{title}</text>']
    for v in range(int(yr[0]), int(yr[1]) + 1, 10):
        o.append(f'<line x1="{ml}" y1="{Y(v)}" x2="{W - mr}" y2="{Y(v)}" stroke="#ddd"/><text x="{ml - 8}" y="{Y(v) + 4}" text-anchor="end">{v}</text>')
    step = 100e6 if xr[1] - xr[0] > 400e6 else 50e6
    f = math.ceil(xr[0] / step) * step
    while f <= xr[1]:
        o.append(f'<line x1="{X(f)}" y1="{mt}" x2="{X(f)}" y2="{H - mb}" stroke="#ddd"/><text x="{X(f)}" y="{H - mb + 18}" text-anchor="middle">{f / 1e6:.0f}</text>')
        f += step
    for (f1, f2, col, lab) in marks:
        o.append(f'<rect x="{X(f1)}" y="{mt}" width="{max(X(f2) - X(f1), 2)}" height="{H - mt - mb}" fill="{col}" opacity="0.18"/>')
    for freq, vals, col, lab in curves:
        pts = " ".join(f"{X(a):.1f},{Y(min(max(b, yr[0]), yr[1])):.1f}" for a, b in zip(freq, vals))
        o.append(f'<polyline fill="none" stroke="{col}" stroke-width="2.2" points="{pts}"/>')
    o.append(f'<text x="{W / 2}" y="{H - 12}" text-anchor="middle">MHz</text><text x="18" y="{H / 2}" transform="rotate(-90 18 {H / 2})" text-anchor="middle">dB</text>')
    ly = mt + 18
    for freq, vals, col, lab in curves:
        o.append(f'<line x1="{W - 250}" y1="{ly}" x2="{W - 225}" y2="{ly}" stroke="{col}" stroke-width="3"/><text x="{W - 218}" y="{ly + 4}">{lab}</text>'); ly += 20
    o.append("</svg>")
    open(path, "w").write("\n".join(o))

if __name__ == "__main__":
    result = {}
    os.makedirs(OUT, exist_ok=True)
    for key in ("vhf", "uhf"):
        band, ideal_vals, vals = design(key)
        r = evaluate(vals, band, runs=500)
        result[key] = dict(ideal=[x for x in ideal_vals], values=vals, **{k: v for k, v in r.items()})
        print(f"{key.upper()} {band['name']}  fc {band['fc'] / 1e6:.0f} MHz")
        print("  ideal  C1 %.2f pF  L1 %.1f nH  C2 %.2f pF  L2 %.1f nH" % (ideal_vals[0] * 1e12, ideal_vals[1] * 1e9, ideal_vals[2] * 1e12, ideal_vals[3] * 1e9))
        print("  E24    C1 %.1f pF  L1 %.0f nH  C2 %.1f pF  L2 %.0f nH   (C4=C1, L3=L1, C3=C2)" % (vals[0] * 1e12, vals[1] * 1e9, vals[2] * 1e12, vals[3] * 1e9))
        print("  nominal: loss %.2f dB, return loss %.1f dB, 2nd harmonic %.0f dB, 3rd %.0f dB, 5th %.0f dB" % (r["il"], r["rl"], r["h2"], r["h3"], r["h5"]))
        print("  worst of 500 runs (C +-5 %%, L +-5 %%): loss %.2f dB, return loss %.1f dB, 2nd harmonic %.0f dB" % (r["worst"]["il"], r["worst"]["rl"], r["worst"]["h2"]))
        f = np.linspace(20e6, 6 * band["f_hi"], 900)
        s21, s11 = s_params(f, vals, band)
        d = os.path.join(OUT, key); os.makedirs(d, exist_ok=True)
        svg_plot(os.path.join(d, f"{key}-response.svg"), f"{band['name']} filter: simulated response (nominal values, real part losses)",
                 [(f, db(s21), "#1b5fb5", "S21 (transmission)"), (f, db(s11), "#c0392b", "S11 (reflection)")], (0, 6 * band["f_hi"]), (-90, 0),
                 [(band["f_lo"], band["f_hi"], "#2e9e4f", "band"), (2 * band["f_lo"], 2 * band["f_hi"], "#e67e22", "2nd"), (3 * band["f_lo"], 3 * band["f_hi"], "#e67e22", "3rd")])
    json.dump(result, open(os.path.join(OUT, "design.json"), "w"), indent=1)
