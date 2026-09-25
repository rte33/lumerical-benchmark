"""Tier 2: programmatic-structure tasks (real engine only).

These need loops, string-built object names, computed polygon vertices,
structure/analysis groups with user properties and setup scripts, custom
materials and global settings. Many assertions are order-independent
aggregates (counts, extrema) evaluated with LSF `expr` assertions.
"""
from __future__ import annotations

import math
import random

from .util import (EXACT_NOTE, MATERIALS, NM, OPENERS, UM, A, E, count_setup, extreme_setup, grid, hl,
                   lit, num, obj, pick, q, task)

SI = MATERIALS["si"]
CAT_ARR = "arrays_and_lattices"
CAT_GRP = "groups_and_parametrization"
SLAB_Z = [("z", 110 * NM), ("z span", 220 * NM)]


def _none(name: str):
    """Assert that no object with this exact name exists (catches off-by-one loops)."""
    return E(f'getnamednumber("{name}")', 0)


# ---------------------------------------------------------------------------
# arrays_and_lattices  (train)
# ---------------------------------------------------------------------------

def square_lattice(rng: random.Random):
    nx, ny = rng.randint(3, 9), rng.randint(3, 9)
    a = grid(rng, 300, 600, 10) * NM
    r = round(a / NM * pick(rng, [0.2, 0.25, 0.3, 0.35])) * NM
    qn = (f"{pick(rng, OPENERS)} build a square-lattice photonic crystal of air holes in a silicon slab. The "
          f"slab 'slab' (material '{SI}', 220 nm thick, centered at z = 110 nm) spans {nx + 1} lattice periods "
          f"in x and {ny + 1} in y, centered at the origin. Add {nx} x {ny} circular holes (material 'etch', "
          f"radius {hl(r)}, same z extent) with lattice constant {hl(a)}, forming a grid centered at the "
          f"origin. Name each hole 'hole_i_j', where i = 1..{nx} counts columns from -x to +x and j = 1..{ny} "
          f"counts rows from -y to +y. Use loops.")
    code = (f"nx = {nx}; ny = {ny}; a = {lit(a)}; r = {lit(r)};\n"
            + obj("addrect", "slab", [("x", 0.0), ("x span", "(nx+1)*a"), ("y", 0.0), ("y span", "(ny+1)*a")]
                  + SLAB_Z + [("material", q(SI))])
            + "for(i=1:nx){\n  for(j=1:ny){\n    addcircle;\n"
              '    set("name", "hole_" + num2str(i) + "_" + num2str(j));\n'
              '    set("x", (i-(nx+1)/2)*a); set("y", (j-(ny+1)/2)*a);\n'
              '    set("radius", r); set("z", 110e-9); set("z span", 220e-9); set("material", "etch");\n'
              "  }\n}\n")
    asserts = [A("hole_1_1", "x", (1 - (nx + 1) / 2) * a, True), A("hole_1_1", "y", (1 - (ny + 1) / 2) * a, True),
               A(f"hole_{nx}_{ny}", "x", (nx - (nx + 1) / 2) * a, True),
               A(f"hole_1_{ny}", "radius", r), _none(f"hole_{nx + 1}_1"), _none(f"hole_1_{ny + 1}")]
    return task(CAT_ARR, "square_lattice", 2, qn, code, asserts)


def hex_w1(rng: random.Random):
    nx = rng.randint(8, 16)
    ny = pick(rng, [5, 7, 9, 11])
    a = grid(rng, 380, 500, 10) * NM
    r = round(a / NM * pick(rng, [0.25, 0.28, 0.3, 0.32])) * NM
    jc = (ny + 1) // 2
    qn = (f"{pick(rng, OPENERS)} build a W1 photonic-crystal waveguide in a triangular lattice. Rows are "
          f"indexed j = 1..{ny} from -y to +y and lie at y = (j - {jc}) * a * sqrt(3)/2 with a = {hl(a)}. Each "
          f"row holds {nx} holes indexed i = 1..{nx} at x = (i - {num((nx + 1) / 2, 1)}) * a, shifted by +a/2 "
          f"in every even row. Leave out the entire middle row (j = {jc}) to form the waveguide. All holes are "
          f"circles named 'hole' (radius {hl(r)}, material 'etch', 220 nm thick, centered at z = 110 nm)."
          + EXACT_NOTE)
    code = (f"nx = {nx}; ny = {ny}; a = {lit(a)}; r = {lit(r)}; jc = {jc};\n"
            "for(j=1:ny){\n  if(j != jc){\n    for(i=1:nx){\n      addcircle; set(\"name\", \"hole\");\n"
            "      set(\"x\", (i-(nx+1)/2)*a + (mod(j,2)==0)*a/2);\n"
            "      set(\"y\", (j-jc)*a*sqrt(3)/2);\n"
            "      set(\"radius\", r); set(\"z\", 110e-9); set(\"z span\", 220e-9); set(\"material\", \"etch\");\n"
            "    }\n  }\n}\n")
    s_row, e_row = count_setup("hole", f"abs(benchzzy) < {a / 4!r}")
    s_ymax, e_ymax = extreme_setup("hole", "y", "max")
    s_xmax, e_xmax = extreme_setup("hole", "x", "max")
    asserts = [E('getnamednumber("hole")', nx * (ny - 1)), E(e_row, 0, setup=s_row),
               E(e_ymax, (ny - jc) * a * math.sqrt(3) / 2, setup=s_ymax, derived=True),
               E(e_xmax, (nx - (nx + 1) / 2) * a + a / 2, setup=s_xmax, derived=True),
               A("hole", "radius", r)]
    return task(CAT_ARR, "hex_w1", 2, qn, code, asserts)


def grating_teeth(rng: random.Random):
    N = rng.randint(10, 30)
    P = grid(rng, 500, 700, 10) * NM
    ff = pick(rng, [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7])
    e = pick(rng, [70, 110, 150]) * NM
    x0 = grid(rng, -5, 5, 0.5) * UM
    W = grid(rng, 8, 15, 1) * UM
    tw = ff * P
    qn = (f"{pick(rng, OPENERS)} build a shallow-etched grating coupler on 220 nm silicon. A partially etched "
          f"slab 'slab' (material '{SI}', thickness 220 nm minus the {hl(e)} etch depth, bottom at z = 0, "
          f"{hl(W)} wide in y, spanning from x = {hl(x0 - P)} to x = {hl(x0 + N * P)}) carries {N} unetched "
          f"teeth named 'tooth_1' ... 'tooth_{N}' that fill the remaining {hl(e)} up to z = 220 nm. The grating "
          f"period is {hl(P)} and the fill factor (tooth width / period) is {ff}; tooth_1 is centered at "
          f"x = {hl(x0)} and the index increases toward +x. Teeth are {hl(W)} wide, centered on y = 0, same "
          f"material. Use a loop.")
    code = (f"N = {N}; P = {lit(P)}; ff = {ff}; etch = {lit(e)}; x0 = {lit(x0)}; W = {lit(W)};\n"
            + obj("addrect", "slab", [("x min", "x0 - P"), ("x max", "x0 + N*P"), ("y", 0.0), ("y span", "W"),
                                      ("z min", 0.0), ("z max", "220e-9 - etch"), ("material", q(SI))])
            + "for(k=1:N){\n  addrect; set(\"name\", \"tooth_\" + num2str(k));\n"
              "  set(\"x\", x0 + (k-1)*P); set(\"x span\", ff*P); set(\"y\", 0); set(\"y span\", W);\n"
              f"  set(\"z min\", 220e-9 - etch); set(\"z max\", 220e-9); set(\"material\", \"{SI}\");\n}}\n")
    k = rng.randint(2, N - 1)
    asserts = [A(f"tooth_{N}", "x", x0 + (N - 1) * P, True), A(f"tooth_{k}", "x span", tw, True),
               A("tooth_1", "z", 220 * NM - e / 2, True), A("slab", "z span", 220 * NM - e, True),
               _none(f"tooth_{N + 1}")]
    return task(CAT_ARR, "grating_teeth", 2, qn, code, asserts)


def apodized_grating(rng: random.Random):
    N = rng.randint(12, 30)
    P = grid(rng, 550, 750, 10) * NM
    ff1 = pick(rng, [0.8, 0.75, 0.7, 0.65])
    ffN = pick(rng, [0.3, 0.35, 0.4, 0.45])
    x0 = grid(rng, 0, 5, 0.5) * UM
    ffk = lambda k: ff1 + (ffN - ff1) * (k - 1) / (N - 1)
    qn = (f"{pick(rng, OPENERS)} build an apodized grating of {N} silicon teeth named 'tooth_1' ... "
          f"'tooth_{N}' (material '{SI}', 10 um wide in y centered on y = 0, 220 nm thick centered at "
          f"z = 110 nm). The period is {hl(P)}; period k (k = 1..{N}) begins at x = {hl(x0)} + (k-1) * period "
          f"and its tooth occupies the first ff_k * period of it, where the fill factor varies linearly from "
          f"{ff1} for k = 1 to {ffN} for k = {N}. Use a loop." + EXACT_NOTE)
    code = (f"N = {N}; P = {lit(P)}; ff1 = {ff1}; ffN = {ffN}; x0 = {lit(x0)};\n"
            "for(k=1:N){\n  ff = ff1 + (ffN-ff1)*(k-1)/(N-1);\n"
            "  addrect; set(\"name\", \"tooth_\" + num2str(k));\n"
            "  set(\"x min\", x0 + (k-1)*P); set(\"x max\", x0 + (k-1)*P + ff*P);\n"
            f"  set(\"y\", 0); set(\"y span\", 10e-6); set(\"z\", 110e-9); set(\"z span\", 220e-9); set(\"material\", \"{SI}\");\n}}\n")
    k = rng.randint(2, N - 1)
    asserts = [A("tooth_1", "x span", ff1 * P, True), A(f"tooth_{N}", "x span", ffN * P, True),
               A(f"tooth_{k}", "x span", ffk(k) * P, True),
               A(f"tooth_{k}", "x", x0 + (k - 1) * P + ffk(k) * P / 2, True), _none(f"tooth_{N + 1}")]
    return task(CAT_ARR, "apodized_grating", 2, qn, code, asserts)


def wg_array(rng: random.Random):
    N = rng.randint(3, 12)
    p = grid(rng, 1, 4, 0.1) * UM
    w1 = grid(rng, 400, 600, 10) * NM
    dw = pick(rng, [0.0, 10 * NM, 20 * NM, -10 * NM])
    L = grid(rng, 10, 50, 5) * UM
    wtxt = (f"all {hl(w1)} wide" if dw == 0 else
            f"with widths that start at {hl(w1)} for wg_1 and change by {hl(dw)} from one waveguide to the next")
    qn = (f"{pick(rng, OPENERS)} build an array of {N} parallel silicon waveguides named 'wg_1' ... 'wg_{N}' "
          f"(from -y to +y), {wtxt}. They are {hl(L)} long along x (centered at x = 0), 220 nm thick centered "
          f"at z = 110 nm, material '{SI}', with a center-to-center pitch of {hl(p)}, and the array is centered "
          f"on y = 0. Use a loop.")
    code = (f"N = {N}; p = {lit(p)}; w1 = {lit(w1)}; dw = {lit(dw)};\n"
            "for(k=1:N){\n  addrect; set(\"name\", \"wg_\" + num2str(k));\n"
            f"  set(\"x\", 0); set(\"x span\", {lit(L)}); set(\"y\", (k-(N+1)/2)*p); set(\"y span\", w1 + (k-1)*dw);\n"
            f"  set(\"z\", 110e-9); set(\"z span\", 220e-9); set(\"material\", \"{SI}\");\n}}\n")
    asserts = [A("wg_1", "y", (1 - (N + 1) / 2) * p, True), A(f"wg_{N}", "y", (N - (N + 1) / 2) * p, True),
               A(f"wg_{N}", "y span", w1 + (N - 1) * dw, True), _none(f"wg_{N + 1}")]
    return task(CAT_ARR, "wg_array", 2, qn, code, asserts)


def dbr_loop(rng: random.Random):
    N = rng.randint(3, 15)
    nh, nl = pick(rng, [(3.48, 1.45), (2.0, 1.45), (2.2, 1.46), (2.35, 1.38), (2.6, 1.5)])
    lam = pick(rng, [850, 980, 1064, 1310, 1550]) * NM
    z0 = pick(rng, [0.0, 0.5 * UM, 1 * UM, -1 * UM])
    th, tl = lam / (4 * nh), lam / (4 * nl)
    qn = (f"{pick(rng, OPENERS)} build a {N}-pair quarter-wave Bragg mirror for {hl(lam)}. Starting at "
          f"z = {hl(z0)} and going up, alternate high-index layers 'hi_k' (index {nh}) and low-index layers "
          f"'lo_k' (index {nl}), k = 1..{N}, beginning with hi_1, with no gaps. Each layer is a quarter "
          f"wavelength thick in its own material. Use the 'index' property; every layer spans 10 um x 10 um "
          f"centered at x = y = 0. Use a loop." + EXACT_NOTE)
    code = (f"N = {N}; lam = {lit(lam)}; nh = {nh}; nl = {nl}; z0 = {lit(z0)};\n"
            "th = lam/(4*nh); tl = lam/(4*nl);\n"
            "for(k=1:N){\n  zb = z0 + (k-1)*(th+tl);\n"
            "  addrect; set(\"name\", \"hi_\" + num2str(k)); set(\"index\", nh);\n"
            "  set(\"x\", 0); set(\"x span\", 10e-6); set(\"y\", 0); set(\"y span\", 10e-6); set(\"z min\", zb); set(\"z max\", zb + th);\n"
            "  addrect; set(\"name\", \"lo_\" + num2str(k)); set(\"index\", nl);\n"
            "  set(\"x\", 0); set(\"x span\", 10e-6); set(\"y\", 0); set(\"y span\", 10e-6); set(\"z min\", zb + th); set(\"z max\", zb + th + tl);\n}\n")
    asserts = [A("hi_1", "z", z0 + th / 2, True), A(f"lo_{N}", "z", z0 + (N - 1) * (th + tl) + th + tl / 2, True),
               A(f"hi_{N}", "z span", th, True), A(f"lo_{N}", "index", nl, tol=1e-6), _none(f"hi_{N + 1}")]
    return task(CAT_ARR, "dbr_loop", 2, qn, code, asserts)


def crow(rng: random.Random):
    N = rng.randint(3, 8)
    R = grid(rng, 2, 10, 0.5) * UM
    w = grid(rng, 400, 600, 10) * NM
    g = grid(rng, 100, 400, 10) * NM
    pitch = 2 * R + w + g
    qn = (f"{pick(rng, OPENERS)} build a coupled-resonator optical waveguide: {N} identical rings named "
          f"'ring_1' ... 'ring_{N}' (from -x to +x) with centerline radius {hl(R)} and width {hl(w)}, all "
          f"centered on y = 0, with an edge-to-edge gap of {hl(g)} between neighbouring rings, and the chain "
          f"centered on x = 0. Rings are 220 nm thick centered at z = 110 nm, material '{SI}'. Use a loop.")
    code = (f"N = {N}; R = {lit(R)}; w = {lit(w)}; g = {lit(g)}; pitch = 2*R + w + g;\n"
            "for(k=1:N){\n  addring; set(\"name\", \"ring_\" + num2str(k));\n"
            "  set(\"x\", (k-(N+1)/2)*pitch); set(\"y\", 0); set(\"inner radius\", R - w/2); set(\"outer radius\", R + w/2);\n"
            f"  set(\"z\", 110e-9); set(\"z span\", 220e-9); set(\"material\", \"{SI}\");\n}}\n")
    k = rng.randint(1, N)
    asserts = [A("ring_1", "x", (1 - (N + 1) / 2) * pitch, True), A(f"ring_{N}", "x", (N - (N + 1) / 2) * pitch, True),
               A(f"ring_{k}", "inner radius", R - w / 2, True), _none(f"ring_{N + 1}")]
    return task(CAT_ARR, "crow", 2, qn, code, asserts)


def bullseye(rng: random.Random):
    N = rng.randint(4, 15)
    r0 = grid(rng, 0.3, 2, 0.1) * UM
    P = grid(rng, 200, 800, 10) * NM
    ff = pick(rng, [0.3, 0.4, 0.5, 0.6])
    qn = (f"{pick(rng, OPENERS)} build a circular Bragg (bullseye) grating of {N} concentric rings named "
          f"'ring_1' ... 'ring_{N}' (innermost first) centered at the origin. Ring k has inner radius "
          f"{hl(r0)} + (k-1) * {hl(P)} and a radial width of {ff} times the {hl(P)} period. Rings are made of "
          f"'{MATERIALS['sin']}', 250 nm thick centered at z = 125 nm. Use a loop.")
    code = (f"N = {N}; r0 = {lit(r0)}; P = {lit(P)}; ff = {ff};\n"
            "for(k=1:N){\n  addring; set(\"name\", \"ring_\" + num2str(k)); set(\"x\", 0); set(\"y\", 0);\n"
            "  set(\"inner radius\", r0 + (k-1)*P); set(\"outer radius\", r0 + (k-1)*P + ff*P);\n"
            f"  set(\"z\", 125e-9); set(\"z span\", 250e-9); set(\"material\", \"{MATERIALS['sin']}\");\n}}\n")
    k = rng.randint(2, N - 1)
    asserts = [A("ring_1", "inner radius", r0), A(f"ring_{N}", "outer radius", r0 + (N - 1) * P + ff * P, True),
               A(f"ring_{k}", "inner radius", r0 + (k - 1) * P, True), _none(f"ring_{N + 1}")]
    return task(CAT_ARR, "bullseye", 2, qn, code, asserts)


def ngon_poly(rng: random.Random):
    star = rng.random() < 0.4
    Nv = rng.randint(5, 12)
    R1 = grid(rng, 0.5, 5, 0.25) * UM
    R2 = round(R1 / UM * pick(rng, [0.4, 0.5, 0.6]), 4) * UM
    phi = pick(rng, [0, 90])
    cx, cy = grid(rng, -3, 3, 0.5) * UM, grid(rng, -3, 3, 0.5) * UM
    if star:
        verts = []
        for k in range(2 * Nv):
            rr = R1 if k % 2 == 0 else R2
            ang = math.radians(phi) + math.pi * k / Nv
            verts.append([rr * math.cos(ang), rr * math.sin(ang)])
        shape = (f"a {Nv}-pointed star with {2 * Nv} vertices that alternate between radius {hl(R1)} (the tips, "
                 f"starting with the first vertex) and {hl(R2)}, equally spaced in angle")
        vcode = (f"M = 2*{Nv}; v = matrix(M, 2);\nfor(k=1:M){{\n  if(mod(k,2)==1){{ rr = {lit(R1)}; }} else {{ rr = {lit(R2)}; }}\n"
                 f"  ang = {phi}*pi/180 + pi*(k-1)/{Nv};\n  v(k,1) = rr*cos(ang); v(k,2) = rr*sin(ang);\n}}\n")
    else:
        verts = [[R1 * math.cos(math.radians(phi) + 2 * math.pi * k / Nv),
                  R1 * math.sin(math.radians(phi) + 2 * math.pi * k / Nv)] for k in range(Nv)]
        shape = f"a regular {Nv}-sided polygon with circumradius {hl(R1)}"
        vcode = (f"M = {Nv}; v = matrix(M, 2);\nfor(k=1:M){{\n  ang = {phi}*pi/180 + 2*pi*(k-1)/M;\n"
                 f"  v(k,1) = {lit(R1)}*cos(ang); v(k,2) = {lit(R1)}*sin(ang);\n}}\n")
    qn = (f"{pick(rng, OPENERS)} create a polygon named 'shape' positioned at ({hl(cx)}, {hl(cy)}) whose "
          f"vertices (relative to its position) describe {shape}. The first vertex lies at an angle of {phi} "
          f"degrees from the +x axis and the vertices proceed counter-clockwise. Compute the vertex matrix with "
          f"a loop. The polygon is 220 nm thick, centered at z = 110 nm, material '{SI}'." + EXACT_NOTE)
    code = vcode + obj("addpoly", "shape", [("x", cx), ("y", cy), ("vertices", "v")] + SLAB_Z + [("material", q(SI))])
    asserts = [A("shape", "vertices", verts, True), A("shape", "x", cx), E('size(getnamed("shape","vertices"))', [len(verts), 2])]
    if cx == 0:
        asserts[1] = A("shape", "y", cy) if cy != 0 else A("shape", "material", SI)
    return task(CAT_ARR, "ngon_poly", 2, qn, code, asserts)


def nanobeam(rng: random.Random):
    M = rng.randint(4, 12)
    a = grid(rng, 300, 450, 10) * NM
    rmin, rmax = grid(rng, 60, 90, 5) * NM, grid(rng, 100, 140, 5) * NM
    wb = grid(rng, 400, 700, 10) * NM
    xs = [(k - (2 * M + 1) / 2) * a for k in range(1, 2 * M + 1)]
    rk = lambda x: rmin + (rmax - rmin) * (abs(x) - a / 2) / ((M - 1) * a)
    qn = (f"{pick(rng, OPENERS)} build a tapered photonic-crystal nanobeam cavity. The beam 'beam' "
          f"(material '{SI}', {hl(wb)} wide in y, 220 nm thick centered at z = 110 nm, spanning "
          f"{hl((2 * M + 2) * a)} in x, centered at the origin) contains {2 * M} air holes named 'hole_1' ... "
          f"'hole_{2 * M}' from -x to +x, with period {hl(a)}, placed symmetrically about x = 0 so that no hole "
          f"sits at the center. The hole radius grows linearly with distance from the center: the two central "
          f"holes have radius {hl(rmin)} and the two outermost holes have radius {hl(rmax)}. Holes are material "
          f"'etch', same z extent, centered on y = 0. Use a loop." + EXACT_NOTE)
    code = (f"M = {M}; a = {lit(a)}; rmin = {lit(rmin)}; rmax = {lit(rmax)};\n"
            + obj("addrect", "beam", [("x", 0.0), ("x span", "(2*M+2)*a"), ("y", 0.0), ("y span", wb)]
                  + SLAB_Z + [("material", q(SI))])
            + "for(k=1:2*M){\n  x = (k-(2*M+1)/2)*a;\n  addcircle; set(\"name\", \"hole_\" + num2str(k));\n"
              "  set(\"x\", x); set(\"y\", 0); set(\"radius\", rmin + (rmax-rmin)*(abs(x)-a/2)/((M-1)*a));\n"
              "  set(\"z\", 110e-9); set(\"z span\", 220e-9); set(\"material\", \"etch\");\n}\n")
    k = rng.randint(2, M - 1)
    asserts = [A("hole_1", "radius", rmax), A(f"hole_{M}", "radius", rmin),
               A(f"hole_{k}", "radius", rk(xs[k - 1]), True), A(f"hole_{M + 1}", "x", a / 2, True),
               A(f"hole_{2 * M}", "x", xs[-1], True), _none(f"hole_{2 * M + 1}")]
    return task(CAT_ARR, "nanobeam", 2, qn, code, asserts)


# ---------------------------------------------------------------------------
# groups_and_parametrization  (test)
# ---------------------------------------------------------------------------

def group_script_pc(rng: random.Random):
    nx, ny = rng.randint(2, 8), rng.randint(2, 8)
    a = grid(rng, 300, 600, 10) * NM
    r = round(a / NM * pick(rng, [0.2, 0.25, 0.3])) * NM
    gx, gy = grid(rng, -5, 5, 0.5) * UM, grid(rng, -5, 5, 0.5) * UM
    qn = (f"{pick(rng, OPENERS)} create a parametrized structure group named 'pc' located at ({hl(gx)}, "
          f"{hl(gy)}). Give it user properties 'a' (length, {hl(a)}), 'r' (length, {hl(r)}), 'nx' (number, "
          f"{nx}) and 'ny' (number, {ny}). Its setup script must build an nx x ny square lattice of circles "
          f"named 'hole' with lattice constant a and radius r, centered on the group origin (220 nm thick, "
          f"centered at z = 110 nm, material 'etch'), so that editing the user properties regenerates the "
          f"lattice.")
    script = ('deleteall; for(i=1:nx){ for(j=1:ny){ addcircle; set(\\"name\\",\\"hole\\"); '
              'set(\\"x\\",(i-(nx+1)/2)*a); set(\\"y\\",(j-(ny+1)/2)*a); set(\\"radius\\",r); '
              'set(\\"z\\",110e-9); set(\\"z span\\",220e-9); set(\\"material\\",\\"etch\\"); } }')
    code = (f'addstructuregroup;\nset("name", "pc");\nset("x", {lit(gx)}); set("y", {lit(gy)});\n'
            f'adduserprop("a", 2, {lit(a)});\nadduserprop("r", 2, {lit(r)});\n'
            f'adduserprop("nx", 0, {nx});\nadduserprop("ny", 0, {ny});\n'
            f'set("script", "{script}");\n')
    s_x, e_x = extreme_setup("pc::hole", "x", "max")
    asserts = [A("pc", "a", a), A("pc", "nx", nx), A("pc", "x", gx) if gx != 0 else A("pc", "y", gy),
               E('getnamednumber("pc::hole")', nx * ny, setup="runsetup;"),
               E(e_x, (nx - 1) / 2 * a, setup="runsetup; " + s_x, derived=True),
               E('getnamed("pc::hole","radius")', r, setup="runsetup;")]
    return task(CAT_GRP, "group_script_pc", 2, qn, code, asserts)


def custom_material(rng: random.Random):
    nk = rng.random() < 0.4
    mname = pick(rng, ["polymer", "my_glass", "coating", "cladding_mat", "resist", "hydex"])
    n = pick(rng, [1.33, 1.38, 1.46, 1.52, 1.57, 1.6, 1.7, 1.85, 2.05])
    k = pick(rng, [0.001, 0.005, 0.01, 0.02, 0.05])
    oname = pick(rng, ["cladding", "film", "layer", "overlay"])
    T = grid(rng, 200, 3000, 50) * NM
    S = grid(rng, 5, 20, 1) * UM
    mo = pick(rng, [None, 1, 3])
    mtype = "(n,k) Material" if nk else "Dielectric"
    extra = (f" Give it a constant imaginary index (k) of {k}." if nk else "")
    mo_txt = (f" Override the material database mesh order and give '{oname}' mesh order {mo}." if mo else "")
    qn = (f"{pick(rng, OPENERS)} define a new material named '{mname}' of type '{mtype}' with a constant "
          f"refractive index of {n}.{extra} Then add a rectangle '{oname}' ({hl(S)} x {hl(S)} in x and y, "
          f"{hl(T)} thick, bottom at z = 0, centered at x = y = 0) that uses this material.{mo_txt}")
    code = (f'm = addmaterial("{mtype}");\nsetmaterial(m, "name", "{mname}");\n'
            f'setmaterial("{mname}", "Refractive Index", {n});\n'
            + (f'setmaterial("{mname}", "Imaginary Refractive Index", {k});\n' if nk else "")
            + obj("addrect", oname, [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S), ("z min", 0.0),
                                     ("z max", T), ("material", q(mname))]
                  + ([("override mesh order from material database", 1), ("mesh order", mo)] if mo else [])))
    asserts = [A(oname, "material", mname), E(f'getmaterial("{mname}","Refractive Index")', n, tol=1e-6),
               E(f'getmaterial("{mname}","type")', mtype), A(oname, "z", T / 2, True)]
    if nk:
        asserts.append(E(f'getmaterial("{mname}","Imaginary Refractive Index")', k, tol=1e-6))
    if mo:
        asserts.append(A(oname, "mesh order", mo))
    return task(CAT_GRP, "custom_material", 2, qn, code, asserts)


def analysis_box(rng: random.Random):
    cx, cy = grid(rng, -3, 3, 0.5) * UM, grid(rng, -3, 3, 0.5) * UM
    hw = pick(rng, [v / 10 for v in range(3, 21) if v != 10]) * UM  # 1 um -> 2 um span is the default
    gname = pick(rng, ["box", "scat_box", "flux_box", "power_box"])
    qn = (f"{pick(rng, OPENERS)} create an analysis group named '{gname}' centered at ({hl(cx)}, {hl(cy)}) and "
          f"place inside it four power monitors forming a closed square of side {hl(2 * hw)} around that "
          f"point (2D simulation): 'm_right' and 'm_left' ('2D X-normal', on the faces at larger and smaller x) "
          f"and 'm_top' and 'm_bottom' ('2D Y-normal', on the faces at larger and smaller y). Each monitor spans "
          f"the full side of the square and is centered on the square along its length.")
    code = f'addanalysisgroup;\nset("name", "{gname}");\nset("x", {lit(cx)}); set("y", {lit(cy)});\nhw = {lit(hw)};\n'
    for name, mt, props in (("m_right", "2D X-normal", [("x", "hw"), ("y", 0.0), ("y span", "2*hw")]),
                            ("m_left", "2D X-normal", [("x", "-hw"), ("y", 0.0), ("y span", "2*hw")]),
                            ("m_top", "2D Y-normal", [("y", "hw"), ("x", 0.0), ("x span", "2*hw")]),
                            ("m_bottom", "2D Y-normal", [("y", "-hw"), ("x", 0.0), ("x span", "2*hw")])):
        code += f'addpower;\nset("name", "{name}");\naddtogroup("{gname}");\n'
        code += "".join(f'set("{p}", {v if isinstance(v, str) else lit(v)});\n' for p, v in
                        [("monitor type", q(mt))] + props)
    asserts = [A(gname, "x", cx), A(f"{gname}::m_right", "x", hw, True), A(f"{gname}::m_bottom", "y", -hw, True),
               A(f"{gname}::m_top", "x span", 2 * hw), A(f"{gname}::m_left", "monitor type", "2D X-normal"),
               E(f'getnamednumber("{gname}::m_top")', 1)]
    if cx == 0:
        asserts[0] = A(gname, "y", cy) if cy != 0 else E(f'getnamednumber("{gname}")', 1)
    return task(CAT_GRP, "analysis_box", 2, qn, code, asserts)


def device_group(rng: random.Random):
    gx, gy = grid(rng, -10, 10, 0.5) * UM, grid(rng, -10, 10, 0.5) * UM
    ang = pick(rng, [15, 30, 45, 60, 90, 120, 135, -30, -45])
    w = grid(rng, 400, 600, 10) * NM
    L = grid(rng, 5, 20, 1) * UM
    tb = pick(rng, [1, 2, 3]) * UM
    qn = (f"{pick(rng, OPENERS)} create a structure group named 'device' whose origin is at ({hl(gx)}, "
          f"{hl(gy)}) and which is rotated by {ang} degrees about the z axis. Inside the group add a BOX layer "
          f"'box' ('{MATERIALS['sio2']}', {hl(L + 2 * UM)} x 4 um, {hl(tb)} thick, top surface at z = 0) and a "
          f"waveguide core 'core' ('{SI}', {hl(L)} long in the group's local x direction, {hl(w)} wide, 220 nm "
          f"thick, resting on the BOX). Both are centered on the group origin in x and y.")
    code = (f'addstructuregroup;\nset("name", "device");\nset("x", {lit(gx)}); set("y", {lit(gy)});\n'
            f'set("first axis", "z"); set("rotation 1", {ang});\ntb = {lit(tb)};\n'
            f'addrect;\nset("name", "box");\naddtogroup("device");\n'
            f'set("x", 0); set("x span", {lit(L + 2 * UM)}); set("y", 0); set("y span", 4e-6);\n'
            f'set("z", -tb/2); set("z span", tb); set("material", "{MATERIALS["sio2"]}");\n'
            f'addrect;\nset("name", "core");\naddtogroup("device");\n'
            f'set("x", 0); set("x span", {lit(L)}); set("y", 0); set("y span", {lit(w)});\n'
            f'set("z", 110e-9); set("z span", 220e-9); set("material", "{SI}");\n')
    asserts = [A("device", "rotation 1", float(ang)), A("device", "first axis", "z"),
               A("device::core", "y span", w), A("device::box", "z", -tb / 2, True),
               A("device::core", "z", 110 * NM, True), A("device::core", "x", 0.0, tol=1e-12)]
    asserts.insert(0, A("device", "x", gx) if gx != 0 else A("device", "y", gy))
    return task(CAT_GRP, "device_group", 2, qn, code, asserts)


def global_settings(rng: random.Random):
    lc = pick(rng, [780, 850, 980, 1060, 1310, 1550]) * NM
    span = grid(rng, 40, 300, 20) * NM
    npts = pick(rng, [21, 51, 101, 201, 301, 501])
    qn = (f"{pick(rng, OPENERS)} configure the global source settings so that sources default to a band "
          f"centered at {hl(lc)} with a total span of {hl(span)} (set 'wavelength start' and 'wavelength "
          f"stop'), and set the global monitor settings to use {npts} frequency points. Then add a plane-wave "
          f"source 'src' and a power monitor 'T' that both keep using these global settings.")
    code = (f"lc = {lit(lc)}; span = {lit(span)};\n"
            'setglobalsource("wavelength start", lc - span/2);\nsetglobalsource("wavelength stop", lc + span/2);\n'
            f'setglobalmonitor("frequency points", {npts});\n'
            'addplane;\nset("name", "src");\naddpower;\nset("name", "T");\n')
    asserts = [E('getglobalsource("wavelength start")', lc - span / 2, derived=True),
               E('getglobalsource("wavelength stop")', lc + span / 2, derived=True),
               E('getglobalmonitor("frequency points")', npts),
               A("src", "wavelength start", lc - span / 2, True),
               A("T", "override global monitor settings", 0)]
    return task(CAT_GRP, "global_settings", 2, qn, code, asserts)


def arc_poly(rng: random.Random):
    R = grid(rng, 2, 10, 0.5) * UM
    w = grid(rng, 400, 800, 50) * NM
    th1, th2 = pick(rng, [(0, 90), (0, 180), (-45, 45), (90, 180), (30, 150), (0, 270)])
    Np = pick(rng, [11, 21, 31, 41, 51])
    ro, ri = R + w / 2, R - w / 2
    verts = []
    for k in range(Np):
        t = math.radians(th1 + (th2 - th1) * k / (Np - 1))
        verts.append([ro * math.cos(t), ro * math.sin(t)])
    for k in range(Np):
        t = math.radians(th2 - (th2 - th1) * k / (Np - 1))
        verts.append([ri * math.cos(t), ri * math.sin(t)])
    qn = (f"{pick(rng, OPENERS)} build a curved waveguide section as a polygon named 'arc' positioned at the "
          f"origin: an annular sector of centerline radius {hl(R)} and width {hl(w)} from {th1} to {th2} degrees. "
          f"Generate the vertex matrix with a loop: first {Np} points along the outer edge from {th1} to {th2} "
          f"degrees (equally spaced, both ends included), then {Np} points along the inner edge from {th2} back "
          f"to {th1} degrees. The polygon is 220 nm thick, centered at z = 110 nm, material '{SI}'." + EXACT_NOTE)
    code = (f"R = {lit(R)}; w = {lit(w)}; t1 = {th1}*pi/180; t2 = {th2}*pi/180; Np = {Np};\n"
            "v = matrix(2*Np, 2);\nfor(k=1:Np){\n  t = t1 + (t2-t1)*(k-1)/(Np-1);\n"
            "  v(k,1) = (R+w/2)*cos(t); v(k,2) = (R+w/2)*sin(t);\n"
            "  t = t2 - (t2-t1)*(k-1)/(Np-1);\n"
            "  v(Np+k,1) = (R-w/2)*cos(t); v(Np+k,2) = (R-w/2)*sin(t);\n}\n"
            + obj("addpoly", "arc", [("x", 0.0), ("y", 0.0), ("vertices", "v")] + SLAB_Z + [("material", q(SI))]))
    asserts = [E('size(getnamed("arc","vertices"))', [2 * Np, 2]), A("arc", "vertices", verts, True),
               A("arc", "material", SI)]
    return task(CAT_GRP, "arc_poly", 2, qn, code, asserts)


FAMILIES = [
    (square_lattice, "train"), (hex_w1, "train"), (grating_teeth, "train"), (apodized_grating, "train"),
    (wg_array, "train"), (dbr_loop, "train"), (crow, "train"), (bullseye, "train"), (ngon_poly, "train"),
    (nanobeam, "train"),
    (group_script_pc, "test"), (custom_material, "test"), (analysis_box, "test"), (device_group, "test"),
    (global_settings, "test"), (arc_poly, "test"),
]
