"""Tier 1: derived-value tasks.

The question states design intent (gaps, margins, stacking order, quarter-wave
conditions, frequency ranges ...) instead of raw coordinates, so the model has
to compute positions/spans itself. Assertions target the derived values.
"""
from __future__ import annotations

import math
import random

from .util import (C0, EXACT_NOTE, FS, MATERIALS, NM, THZ, UM, A, grid, hl, ht, lit, num, obj,
                   pick, q, task, OPENERS)

SI, SIO2 = MATERIALS["si"], MATERIALS["sio2"]

# ---------------------------------------------------------------------------
# derived_waveguide_geometry  (train)
# ---------------------------------------------------------------------------
CAT_WG = "derived_waveguide_geometry"


def soi_strip(rng: random.Random):
    if rng.random() < 0.6:
        core_key, t, w = "si", pick(rng, [220, 250, 300]) * NM, grid(rng, 400, 650, 10) * NM
    else:
        core_key, t, w = "sin", pick(rng, [300, 400, 600, 800]) * NM, grid(rng, 800, 1600, 50) * NM
    tb = pick(rng, [1, 2, 3]) * UM
    L = grid(rng, 5, 30, 1) * UM
    bx, by = L + pick(rng, [2, 4]) * UM, grid(rng, 4, 8, 1) * UM
    mat = MATERIALS[core_key]
    qn = (f"{pick(rng, OPENERS)} build a strip waveguide on a buried-oxide layer. The BOX, named 'box', "
          f"is {hl(tb)} thick (material '{SIO2}'), spans {hl(bx)} in x and {hl(by)} in y, is centered at "
          f"x = y = 0, and its top surface lies at z = 0. The waveguide core, named 'core' (material "
          f"'{mat}'), is {hl(w)} wide (y), {hl(t)} thick and {hl(L)} long along x, centered at x = y = 0 "
          f"and resting directly on top of the BOX.")
    code = (f"tbox = {lit(tb)}; t = {lit(t)};\n"
            + obj("addrect", "box", [("x", 0.0), ("x span", bx), ("y", 0.0), ("y span", by),
                                     ("z", "-tbox/2"), ("z span", "tbox"), ("material", q(SIO2))])
            + obj("addrect", "core", [("x", 0.0), ("x span", L), ("y", 0.0), ("y span", w),
                                      ("z", "t/2"), ("z span", "t"), ("material", q(mat))]))
    asserts = [A("box", "z", -tb / 2, True), A("core", "z", t / 2, True), A("core", "z span", t),
               A("core", "y span", w), A("core", "material", mat)]
    return task(CAT_WG, "soi_strip", 1, qn, code, asserts)


def rib(rng: random.Random):
    H = pick(rng, [220, 250, 300, 340, 400]) * NM
    e = grid(rng, 60, H / NM - 50, 10) * NM
    w = grid(rng, 400, 900, 50) * NM
    ws, L = grid(rng, 3, 10, 1) * UM, grid(rng, 5, 25, 1) * UM
    qn = (f"{pick(rng, OPENERS)} model a silicon rib waveguide along x on top of an oxide surface at z = 0. "
          f"The total silicon height at the rib is {hl(H)} and the etch depth is {hl(e)}. Model the "
          f"unetched slab as a rectangle named 'slab' ({hl(ws)} wide in y) and the raised part as a "
          f"separate rectangle named 'rib' ({hl(w)} wide in y) occupying only the region above the slab. "
          f"Both are {hl(L)} long, centered at x = y = 0, and use material '{SI}'.")
    code = (f"H = {lit(H)}; etch = {lit(e)}; tslab = H - etch;\n"
            + obj("addrect", "slab", [("x", 0.0), ("x span", L), ("y", 0.0), ("y span", ws),
                                      ("z", "tslab/2"), ("z span", "tslab"), ("material", q(SI))])
            + obj("addrect", "rib", [("x", 0.0), ("x span", L), ("y", 0.0), ("y span", w),
                                     ("z", "tslab + etch/2"), ("z span", "etch"), ("material", q(SI))]))
    asserts = [A("slab", "z span", H - e, True), A("slab", "z", (H - e) / 2, True),
               A("rib", "z span", e, True), A("rib", "z", H - e / 2, True), A("rib", "y span", w)]
    return task(CAT_WG, "rib", 1, qn, code, asserts)


def taper_poly(rng: random.Random):
    w1 = grid(rng, 400, 600, 50) * NM
    w2 = pick(rng, [grid(rng, 150, 300, 10) * NM, grid(rng, 2, 12, 1) * UM])
    Lt = grid(rng, 5, 60, 5) * UM
    Lin, Lout = grid(rng, 2, 10, 1) * UM, grid(rng, 2, 10, 1) * UM
    qn = (f"{pick(rng, OPENERS)} build a linear taper along x from width {hl(w1)} to {hl(w2)} over a length "
          f"of {hl(Lt)}. Model the taper as a polygon named 'taper' positioned at x = y = 0 whose "
          f"vertices (relative to its position) are, in order: (0, -w1/2), (L, -w2/2), (L, w2/2), "
          f"(0, w1/2). Add an input waveguide 'wg_in' ({hl(w1)} wide, {hl(Lin)} long) whose right end "
          f"touches the taper at x = 0, and an output waveguide 'wg_out' ({hl(w2)} wide, {hl(Lout)} long) "
          f"whose left end touches the taper's wide/narrow end at x = L. All three are centered on y = 0, "
          f"220 nm thick, centered at z = 110 nm, material '{SI}'.")
    code = (f"w1 = {lit(w1)}; w2 = {lit(w2)}; L = {lit(Lt)}; Lin = {lit(Lin)}; Lout = {lit(Lout)};\n"
            + obj("addpoly", "taper", [("x", 0.0), ("y", 0.0), ("z", 110 * NM), ("z span", 220 * NM),
                                       ("vertices", "[0,-w1/2; L,-w2/2; L,w2/2; 0,w1/2]"),
                                       ("material", q(SI))])
            + obj("addrect", "wg_in", [("x", "-Lin/2"), ("x span", "Lin"), ("y", 0.0), ("y span", "w1"),
                                       ("z", 110 * NM), ("z span", 220 * NM), ("material", q(SI))])
            + obj("addrect", "wg_out", [("x", "L + Lout/2"), ("x span", "Lout"), ("y", 0.0), ("y span", "w2"),
                                        ("z", 110 * NM), ("z span", 220 * NM), ("material", q(SI))]))
    verts = [[0.0, -w1 / 2], [Lt, -w2 / 2], [Lt, w2 / 2], [0.0, w1 / 2]]
    asserts = [A("taper", "vertices", verts, True), A("wg_in", "x", -Lin / 2, True),
               A("wg_out", "x", Lt + Lout / 2, True), A("wg_out", "y span", w2)]
    return task(CAT_WG, "taper_poly", 1, qn, code, asserts)


def extents(rng: random.Random):
    metal = pick(rng, ["au", "al", "ag"])
    x1 = grid(rng, -20, -2, 0.5) * UM
    x2 = x1 + grid(rng, 4, 40, 0.5) * UM
    hw = grid(rng, 1, 5, 0.5) * UM
    yc = grid(rng, -3, 3, 0.5) * UM
    z1 = grid(rng, 0.8, 2.0, 0.1) * UM
    th = grid(rng, 100, 300, 20) * NM
    pad = grid(rng, 20, 80, 10) * UM
    qn = (f"{pick(rng, OPENERS)} add a metal heater named 'heater' (material '{MATERIALS[metal]}') that "
          f"extends from x = {hl(x1)} to x = {hl(x2)}, from y = {hl(yc - hw)} to y = {hl(yc + hw)}, and "
          f"from z = {hl(z1)} to z = {hl(z1 + th)}. Then add a square contact pad named 'pad' (same "
          f"material and z-extent, {hl(pad)} x {hl(pad)}) whose left edge coincides with the heater's "
          f"right end and which is centered on the heater in y.")
    code = (obj("addrect", "heater", [("x min", x1), ("x max", x2), ("y min", yc - hw), ("y max", yc + hw),
                                      ("z min", z1), ("z max", z1 + th), ("material", q(MATERIALS[metal]))])
            + obj("addrect", "pad", [("x min", x2), ("x max", x2 + pad), ("y", yc), ("y span", pad),
                                     ("z min", z1), ("z max", z1 + th), ("material", q(MATERIALS[metal]))]))
    asserts = [A("heater", "x", (x1 + x2) / 2, True), A("heater", "x span", x2 - x1, True),
               A("heater", "z", z1 + th / 2, True), A("pad", "x", x2 + pad / 2, True), A("pad", "y", yc, True)]
    return task(CAT_WG, "extents", 1, qn, code, asserts)


def slot(rng: random.Random):
    s = grid(rng, 50, 200, 10) * NM
    wr = grid(rng, 180, 300, 10) * NM
    t = pick(rng, [220, 250, 300]) * NM
    L = grid(rng, 5, 20, 1) * UM
    qn = (f"{pick(rng, OPENERS)} build a silicon slot waveguide along x: two rails named 'rail_top' "
          f"(+y side) and 'rail_bottom' (-y side), each {hl(wr)} wide, separated by a {hl(s)} slot that is "
          f"centered on y = 0. The rails are {hl(t)} thick sitting on z = 0, {hl(L)} long, centered at x = 0, "
          f"material '{SI}'.")
    code = (f"s = {lit(s)}; wr = {lit(wr)}; t = {lit(t)};\n"
            + obj("addrect", "rail_top", [("x", 0.0), ("x span", L), ("y", "(s+wr)/2"), ("y span", "wr"),
                                          ("z", "t/2"), ("z span", "t"), ("material", q(SI))])
            + obj("addrect", "rail_bottom", [("x", 0.0), ("x span", L), ("y", "-(s+wr)/2"), ("y span", "wr"),
                                             ("z", "t/2"), ("z span", "t"), ("material", q(SI))]))
    asserts = [A("rail_top", "y", (s + wr) / 2, True), A("rail_bottom", "y", -(s + wr) / 2, True),
               A("rail_top", "y span", wr), A("rail_bottom", "z", t / 2, True)]
    return task(CAT_WG, "slot", 1, qn, code, asserts)


def bend(rng: random.Random):
    R = grid(rng, 3, 15, 0.5) * UM
    w = grid(rng, 400, 600, 10) * NM
    Lin, Lout = grid(rng, 2, 10, 1) * UM, grid(rng, 2, 10, 1) * UM
    sgn = pick(rng, [1, -1])
    turn, ydir = ("counter-clockwise toward +y", "+y") if sgn > 0 else ("clockwise toward -y", "-y")
    th0, th1 = (-90, 0) if sgn > 0 else (0, 90)
    qn = (f"{pick(rng, OPENERS)} build a 90-degree waveguide bend. An input waveguide 'wg_in' runs along x "
          f"from x = -{hl(Lin)} to x = 0 at y = 0. It connects to a circular bend named 'bend' (a ring "
          f"sector) of centerline radius {hl(R)} that turns {turn}. The bend ends in an output waveguide "
          f"'wg_out' of length {hl(Lout)} running in the {ydir} direction. All waveguides are {hl(w)} wide, "
          f"220 nm thick, centered at z = 110 nm, material '{SI}'. Use the ring's 'theta start'/'theta stop' "
          f"(degrees, measured counter-clockwise from +x) to define the sector.")
    code = (f"R = {lit(R)}; w = {lit(w)}; Lin = {lit(Lin)}; Lout = {lit(Lout)}; s = {sgn};\n"
            + obj("addrect", "wg_in", [("x", "-Lin/2"), ("x span", "Lin"), ("y", 0.0), ("y span", "w"),
                                       ("z", 110 * NM), ("z span", 220 * NM), ("material", q(SI))])
            + obj("addring", "bend", [("x", 0.0), ("y", "s*R"), ("inner radius", "R - w/2"),
                                      ("outer radius", "R + w/2"), ("theta start", th0), ("theta stop", th1),
                                      ("z", 110 * NM), ("z span", 220 * NM), ("material", q(SI))])
            + obj("addrect", "wg_out", [("x", "R"), ("x span", "w"), ("y", "s*(R + Lout/2)"), ("y span", "Lout"),
                                        ("z", 110 * NM), ("z span", 220 * NM), ("material", q(SI))]))
    asserts = [A("bend", "y", sgn * R, True), A("bend", "inner radius", R - w / 2, True),
               A("bend", "outer radius", R + w / 2, True),
               A("bend", "theta start", -90.0) if sgn > 0 else A("bend", "theta stop", 90.0),
               A("wg_out", "x", R, True), A("wg_out", "y", sgn * (R + Lout / 2), True)]
    return task(CAT_WG, "bend", 1, qn, code, asserts)


# ---------------------------------------------------------------------------
# derived_coupler_layout  (train)
# ---------------------------------------------------------------------------
CAT_CPL = "derived_coupler_layout"
WG_Z = [("z", 110 * NM), ("z span", 220 * NM), ("material", q(SI))]
WG_Z_TXT = f"220 nm thick, centered at z = 110 nm, material '{SI}'"


def dc(rng: random.Random):
    g, w = grid(rng, 100, 400, 10) * NM, grid(rng, 400, 600, 10) * NM
    Lc = grid(rng, 5, 40, 0.5) * UM
    x0, y0 = grid(rng, -5, 5, 0.5) * UM, grid(rng, -3, 3, 0.5) * UM
    qn = (f"{pick(rng, OPENERS)} build the coupling section of a directional coupler: two parallel "
          f"waveguides 'wg_top' (+y) and 'wg_bottom' (-y), each {hl(w)} wide and {hl(Lc)} long along x, with "
          f"an edge-to-edge gap of {hl(g)}. The pair is centered at x = {hl(x0)}, y = {hl(y0)}. "
          f"Both are {WG_Z_TXT}.")
    code = (f"g = {lit(g)}; w = {lit(w)}; x0 = {lit(x0)}; y0 = {lit(y0)};\n"
            + obj("addrect", "wg_top", [("x", "x0"), ("x span", Lc), ("y", "y0 + (g+w)/2"), ("y span", "w")] + WG_Z)
            + obj("addrect", "wg_bottom", [("x", "x0"), ("x span", Lc), ("y", "y0 - (g+w)/2"), ("y span", "w")] + WG_Z))
    asserts = [A("wg_top", "y", y0 + (g + w) / 2, True), A("wg_bottom", "y", y0 - (g + w) / 2, True),
               A("wg_top", "x", x0), A("wg_bottom", "x span", Lc)]
    return task(CAT_CPL, "dc", 1, qn, code, asserts)


def mmi12(rng: random.Random):
    W, L = grid(rng, 2.5, 8, 0.5) * UM, grid(rng, 5, 40, 0.5) * UM
    wi = grid(rng, 400, 1000, 50) * NM
    Li, Lo = grid(rng, 2, 10, 1) * UM, grid(rng, 2, 10, 1) * UM
    qn = (f"{pick(rng, OPENERS)} build a 1x2 MMI splitter. The multimode body 'mmi' is {hl(W)} wide (y) and "
          f"{hl(L)} long (x), centered at the origin. An input waveguide 'in' ({hl(wi)} wide, {hl(Li)} long) "
          f"is attached to the center of the left facet. Two output waveguides 'out1' (upper) and 'out2' "
          f"(lower), each {hl(wi)} wide and {hl(Lo)} long, are attached to the right facet at y = +W/4 and "
          f"y = -W/4. All parts are {WG_Z_TXT}.")
    code = (f"W = {lit(W)}; L = {lit(L)}; wi = {lit(wi)}; Li = {lit(Li)}; Lo = {lit(Lo)};\n"
            + obj("addrect", "mmi", [("x", 0.0), ("x span", "L"), ("y", 0.0), ("y span", "W")] + WG_Z)
            + obj("addrect", "in", [("x", "-(L+Li)/2"), ("x span", "Li"), ("y", 0.0), ("y span", "wi")] + WG_Z)
            + obj("addrect", "out1", [("x", "(L+Lo)/2"), ("x span", "Lo"), ("y", "W/4"), ("y span", "wi")] + WG_Z)
            + obj("addrect", "out2", [("x", "(L+Lo)/2"), ("x span", "Lo"), ("y", "-W/4"), ("y span", "wi")] + WG_Z))
    asserts = [A("in", "x", -(L + Li) / 2, True), A("out1", "x", (L + Lo) / 2, True),
               A("out1", "y", W / 4, True), A("out2", "y", -W / 4, True), A("mmi", "x span", L)]
    return task(CAT_CPL, "mmi12", 1, qn, code, asserts)


def mmi22(rng: random.Random):
    W, L = grid(rng, 3, 9, 0.5) * UM, grid(rng, 10, 80, 1) * UM
    wi = grid(rng, 400, 900, 50) * NM
    Lp = grid(rng, 2, 10, 1) * UM
    qn = (f"{pick(rng, OPENERS)} build a 2x2 MMI coupler. The body 'mmi' is {hl(W)} wide and {hl(L)} long, "
          f"centered at the origin. Input ports 'in1' (upper) and 'in2' (lower) are attached to the left "
          f"facet and output ports 'out1' (upper) and 'out2' (lower) to the right facet; all four ports are "
          f"{hl(wi)} wide, {hl(Lp)} long, and located at y = +/-W/6. All parts are {WG_Z_TXT}.")
    code = f"W = {lit(W)}; L = {lit(L)}; wi = {lit(wi)}; Lp = {lit(Lp)};\n"
    code += obj("addrect", "mmi", [("x", 0.0), ("x span", "L"), ("y", 0.0), ("y span", "W")] + WG_Z)
    for name, sx, sy in (("in1", "-", ""), ("in2", "-", "-"), ("out1", "", ""), ("out2", "", "-")):
        code += obj("addrect", name, [("x", f"{sx}(L+Lp)/2"), ("x span", "Lp"), ("y", f"{sy}W/6"),
                                      ("y span", "wi")] + WG_Z)
    asserts = [A("in2", "x", -(L + Lp) / 2, True), A("in2", "y", -W / 6, True),
               A("out1", "y", W / 6, True), A("out1", "x", (L + Lp) / 2, True)]
    return task(CAT_CPL, "mmi22", 1, qn, code, asserts)


def ring_bus(rng: random.Random):
    R, w = grid(rng, 3, 20, 0.5) * UM, grid(rng, 400, 600, 10) * NM
    g, wb = grid(rng, 100, 300, 10) * NM, grid(rng, 400, 600, 10) * NM
    Lb = 2 * R + grid(rng, 4, 10, 1) * UM
    qn = (f"{pick(rng, OPENERS)} build an all-pass ring resonator. The ring 'ring' has a centerline radius "
          f"of {hl(R)} and a waveguide width of {hl(w)}, centered at the origin. A straight bus waveguide "
          f"'bus' ({hl(wb)} wide, {hl(Lb)} long along x, centered at x = 0) runs below the ring with an "
          f"edge-to-edge gap of {hl(g)}. Both are {WG_Z_TXT}.")
    code = (f"R = {lit(R)}; w = {lit(w)}; g = {lit(g)}; wb = {lit(wb)};\n"
            + obj("addring", "ring", [("x", 0.0), ("y", 0.0), ("inner radius", "R - w/2"),
                                      ("outer radius", "R + w/2")] + WG_Z)
            + obj("addrect", "bus", [("x", 0.0), ("x span", Lb), ("y", "-(R + w/2 + g + wb/2)"),
                                     ("y span", "wb")] + WG_Z))
    asserts = [A("ring", "inner radius", R - w / 2, True), A("ring", "outer radius", R + w / 2, True),
               A("bus", "y", -(R + w / 2 + g + wb / 2), True), A("bus", "y span", wb)]
    return task(CAT_CPL, "ring_bus", 1, qn, code, asserts)


def add_drop(rng: random.Random):
    R, w = grid(rng, 3, 20, 0.5) * UM, grid(rng, 400, 600, 10) * NM
    g1, g2 = grid(rng, 100, 300, 10) * NM, grid(rng, 100, 300, 10) * NM
    wb = w
    Lb = 2 * R + grid(rng, 4, 10, 1) * UM
    qn = (f"{pick(rng, OPENERS)} build an add-drop ring filter. The ring 'ring' (centerline radius {hl(R)}, "
          f"width {hl(w)}) is centered at the origin. A 'through' bus runs below the ring with an "
          f"edge-to-edge gap of {hl(g1)} and a 'drop' bus runs above it with a gap of {hl(g2)}. Both buses "
          f"are {hl(wb)} wide and {hl(Lb)} long along x, centered at x = 0. All parts are {WG_Z_TXT}.")
    code = (f"R = {lit(R)}; w = {lit(w)}; g1 = {lit(g1)}; g2 = {lit(g2)};\n"
            + obj("addring", "ring", [("x", 0.0), ("y", 0.0), ("inner radius", "R - w/2"),
                                      ("outer radius", "R + w/2")] + WG_Z)
            + obj("addrect", "through", [("x", 0.0), ("x span", Lb), ("y", "-(R + w + g1)"), ("y span", "w")] + WG_Z)
            + obj("addrect", "drop", [("x", 0.0), ("x span", Lb), ("y", "R + w + g2"), ("y span", "w")] + WG_Z))
    asserts = [A("through", "y", -(R + w + g1), True), A("drop", "y", R + w + g2, True),
               A("ring", "outer radius", R + w / 2, True)]
    return task(CAT_CPL, "add_drop", 1, qn, code, asserts)


def double_ring(rng: random.Random):
    R, w = grid(rng, 3, 12, 0.5) * UM, grid(rng, 400, 600, 10) * NM
    gr, g = grid(rng, 100, 400, 10) * NM, grid(rng, 100, 300, 10) * NM
    Lb = 4 * R + grid(rng, 6, 12, 1) * UM
    qn = (f"{pick(rng, OPENERS)} build two identical side-coupled rings 'ring_left' and 'ring_right' "
          f"(centerline radius {hl(R)}, width {hl(w)}) placed along x, symmetric about the origin, with an "
          f"edge-to-edge gap of {hl(gr)} between the rings. A bus waveguide 'bus' ({hl(w)} wide, {hl(Lb)} "
          f"long, centered at x = 0) runs below both rings with an edge-to-edge gap of {hl(g)}. All parts "
          f"are {WG_Z_TXT}.")
    xo = R + w / 2 + gr / 2
    code = f"R = {lit(R)}; w = {lit(w)}; gr = {lit(gr)}; g = {lit(g)}; xo = R + w/2 + gr/2;\n"
    for name, sx in (("ring_left", "-xo"), ("ring_right", "xo")):
        code += obj("addring", name, [("x", sx), ("y", 0.0), ("inner radius", "R - w/2"),
                                      ("outer radius", "R + w/2")] + WG_Z)
    code += obj("addrect", "bus", [("x", 0.0), ("x span", Lb), ("y", "-(R + w + g)"), ("y span", "w")] + WG_Z)
    asserts = [A("ring_left", "x", -xo, True), A("ring_right", "x", xo, True),
               A("bus", "y", -(R + w + g), True), A("ring_right", "inner radius", R - w / 2, True)]
    return task(CAT_CPL, "double_ring", 1, qn, code, asserts)


# ---------------------------------------------------------------------------
# derived_stack_design  (train)
# ---------------------------------------------------------------------------
CAT_STK = "derived_stack_design"
WAVELENGTHS = [633, 850, 980, 1064, 1310, 1550]


def ar_coating(rng: random.Random):
    ns = pick(rng, [1.45, 1.5, 1.9, 2.0, 2.25, 2.4, 3.0, 3.48])
    lam = pick(rng, WAVELENGTHS) * NM
    Ts = grid(rng, 1, 5, 0.5) * UM
    S = grid(rng, 4, 20, 1) * UM
    nc, tc = math.sqrt(ns), lam / (4 * math.sqrt(ns))
    qn = (f"{pick(rng, OPENERS)} design a single-layer quarter-wave anti-reflection coating for "
          f"{hl(lam)}. The substrate 'substrate' (index {ns}, {hl(S)} x {hl(S)} in x and y, centered at "
          f"x = y = 0) is {hl(Ts)} thick with its top surface at z = 0. Add the coating 'arc' on top of it with "
          f"the same lateral size, using the ideal coating index (geometric mean of air and substrate) set "
          f"via the 'index' property, and the quarter-wave thickness at that index." + EXACT_NOTE)
    code = (f"ns = {ns}; lam = {lit(lam)}; Ts = {lit(Ts)}; nc = sqrt(ns); tc = lam/(4*nc);\n"
            + obj("addrect", "substrate", [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S),
                                           ("z", "-Ts/2"), ("z span", "Ts"), ("index", "ns")])
            + obj("addrect", "arc", [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S),
                                     ("z", "tc/2"), ("z span", "tc"), ("index", "nc")]))
    asserts = [A("arc", "index", nc, True, tol=1e-4), A("arc", "z span", tc, True),
               A("arc", "z", tc / 2, True), A("substrate", "z", -Ts / 2, True)]
    return task(CAT_STK, "ar_coating", 1, qn, code, asserts)


def stack(rng: random.Random):
    n = rng.randint(3, 5)
    keys = [pick(rng, ["si", "sio2", "sin", "au", "al", "inp", "gaas"]) for _ in range(n)]
    th = [grid(rng, 50, 1000, 10) * NM for _ in range(n)]
    z0 = pick(rng, [0.0, grid(rng, -3, 2, 0.5) * UM])
    S = grid(rng, 5, 20, 1) * UM
    names = [f"layer_{i + 1}" for i in range(n)]
    desc = "; ".join(f"'{names[i]}': {hl(th[i])} of '{MATERIALS[keys[i]]}'" for i in range(n))
    qn = (f"{pick(rng, OPENERS)} build a {n}-layer planar stack. The layers are listed from bottom to top and "
          f"are stacked without gaps, with the bottom of the first layer at z = {hl(z0)}: {desc}. Every layer "
          f"spans {hl(S)} in both x and y, centered at x = y = 0.")
    code = f"zb = {lit(z0)};\n"
    zc = []
    zb = z0
    for i in range(n):
        code += f"t{i + 1} = {lit(th[i])};\n"
        code += obj("addrect", names[i], [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S),
                                          ("z", f"zb + t{i + 1}/2"), ("z span", f"t{i + 1}"),
                                          ("material", q(MATERIALS[keys[i]]))])
        code += f"zb = zb + t{i + 1};\n"
        zc.append(zb + th[i] / 2)
        zb += th[i]
    idx = sorted(rng.sample(range(1, n), 2))
    asserts = [A(names[i], "z", zc[i], True) for i in idx]
    asserts += [A(names[-1], "z span", th[-1]), A(names[idx[0]], "material", MATERIALS[keys[idx[0]]])]
    return task(CAT_STK, "stack", 1, qn, code, asserts)


def qw_bilayer(rng: random.Random):
    nh, nl = pick(rng, [(3.48, 1.45), (2.0, 1.45), (2.2, 1.46), (2.35, 1.38), (2.6, 1.5), (1.9, 1.45)])
    lam = pick(rng, WAVELENGTHS) * NM
    S = grid(rng, 4, 20, 1) * UM
    th, tl = lam / (4 * nh), lam / (4 * nl)
    qn = (f"{pick(rng, OPENERS)} build one period of a quarter-wave Bragg mirror for a design wavelength of "
          f"{hl(lam)}: a high-index layer 'hi' (index {nh}) directly on z = 0 and a low-index layer 'lo' "
          f"(index {nl}) directly on top of it. Each layer is a quarter wavelength thick inside its own "
          f"material. Set indices with the 'index' property; both layers span {hl(S)} in x and y, centered "
          f"at x = y = 0." + EXACT_NOTE)
    code = (f"lam = {lit(lam)}; nh = {nh}; nl = {nl}; th = lam/(4*nh); tl = lam/(4*nl);\n"
            + obj("addrect", "hi", [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S),
                                    ("z", "th/2"), ("z span", "th"), ("index", "nh")])
            + obj("addrect", "lo", [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S),
                                    ("z", "th + tl/2"), ("z span", "tl"), ("index", "nl")]))
    asserts = [A("hi", "z span", th, True), A("hi", "z", th / 2, True), A("lo", "z span", tl, True),
               A("lo", "z", th + tl / 2, True), A("lo", "index", nl, tol=1e-6)]
    return task(CAT_STK, "qw_bilayer", 1, qn, code, asserts)


def fp_cavity(rng: random.Random):
    m = rng.randint(1, 3)
    n = pick(rng, [1.45, 1.5, 1.6, 2.0])
    lam = pick(rng, [532, 633, 780, 850, 980]) * NM
    mk = pick(rng, ["ag", "au", "al"])
    tm = grid(rng, 20, 60, 5) * NM
    S = grid(rng, 4, 20, 1) * UM
    tcav = m * lam / (2 * n)
    ordn = {1: "first", 2: "second", 3: "third"}[m]
    qn = (f"{pick(rng, OPENERS)} build a metal-dielectric-metal Fabry-Perot filter resonant at {hl(lam)} in "
          f"{ordn} order. From bottom to top: 'mirror_bottom' ({hl(tm)} of '{MATERIALS[mk]}') with its bottom "
          f"at z = 0, the spacer 'cavity' (index {n}, set via 'index') whose thickness is m*lambda/(2n) with "
          f"m = {m}, and 'mirror_top' (same metal and thickness), all stacked without gaps. Every layer spans "
          f"{hl(S)} in x and y, centered at x = y = 0." + EXACT_NOTE)
    code = (f"lam = {lit(lam)}; n = {n}; m = {m}; tm = {lit(tm)}; tc = m*lam/(2*n);\n"
            + obj("addrect", "mirror_bottom", [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S),
                                               ("z", "tm/2"), ("z span", "tm"), ("material", q(MATERIALS[mk]))])
            + obj("addrect", "cavity", [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S),
                                        ("z", "tm + tc/2"), ("z span", "tc"), ("index", "n")])
            + obj("addrect", "mirror_top", [("x", 0.0), ("x span", S), ("y", 0.0), ("y span", S),
                                            ("z", "tm + tc + tm/2"), ("z span", "tm"), ("material", q(MATERIALS[mk]))]))
    asserts = [A("cavity", "z span", tcav, True), A("cavity", "z", tm + tcav / 2, True),
               A("mirror_top", "z", tm + tcav + tm / 2, True), A("cavity", "index", n, tol=1e-6)]
    return task(CAT_STK, "fp_cavity", 1, qn, code, asserts)


# ---------------------------------------------------------------------------
# derived_sim_setup  (test)
# ---------------------------------------------------------------------------
CAT_SIM = "derived_sim_setup"


def fdtd_margins(rng: random.Random):
    R = grid(rng, 1, 10, 0.5) * UM
    t = pick(rng, [220, 250, 300, 400]) * NM
    m = grid(rng, 0.5, 3, 0.5) * UM
    mz = grid(rng, 0.5, 2, 0.5) * UM
    acc = rng.randint(3, 6)
    T = grid(rng, 500, 3000, 100) * FS
    qn = (f"{pick(rng, OPENERS)} set up a 3D simulation of a silicon disk. Add a disk 'disk' "
          f"(material '{SI}', radius {hl(R)}, {hl(t)} thick, resting on z = 0, centered at x = y = 0). Add an "
          f"FDTD region (keep the default name 'FDTD') that encloses the disk with a lateral margin of {hl(m)} "
          f"beyond its edge on every side and extends {hl(mz)} below the bottom and above the top of the "
          f"disk. Use mesh accuracy {acc} and a simulation time of {ht(T)}.")
    code = (f"R = {lit(R)}; t = {lit(t)}; m = {lit(m)}; mz = {lit(mz)};\n"
            + obj("addcircle", "disk", [("x", 0.0), ("y", 0.0), ("radius", "R"), ("z", "t/2"), ("z span", "t"),
                                        ("material", q(SI))])
            + obj("addfdtd", None, [("dimension", q("3D")), ("x", 0.0), ("x span", "2*(R+m)"), ("y", 0.0),
                                    ("y span", "2*(R+m)"), ("z", "t/2"), ("z span", "t + 2*mz"),
                                    ("mesh accuracy", acc), ("simulation time", f"{num(T / FS, 3)}e-15")]))
    asserts = [A("FDTD", "x span", 2 * (R + m), True), A("FDTD", "z span", t + 2 * mz, True),
               A("FDTD", "z", t / 2, True), A("FDTD", "mesh accuracy", acc),
               A("FDTD", "simulation time", T, tol=1e-19)]
    return task(CAT_SIM, "fdtd_margins", 1, qn, code, asserts)


def source_band(rng: random.Random):
    kind = pick(rng, ["freq", "center"])
    src = pick(rng, [("addplane", "plane-wave source", "z-axis"), ("addgaussian", "Gaussian beam source", "z-axis"),
                     ("addmode", "mode source", "x-axis")])
    default_axis = src[2]
    src = (src[0], src[1], pick(rng, ["x-axis", "y-axis", "z-axis"]))
    name = pick(rng, ["src", "source", "input"])
    if kind == "freq":
        f1 = grid(rng, 150, 230, 5) * THZ
        f2 = f1 + grid(rng, 10, 60, 5) * THZ
        l1, l2 = C0 / f2, C0 / f1
        band = f"cover the frequency range {num(f1 / THZ)} THz to {num(f2 / THZ)} THz"
        setl = f"f1 = {num(f1 / THZ)}e12; f2 = {num(f2 / THZ)}e12;\n"
        props = [("wavelength start", "c/f2"), ("wavelength stop", "c/f1")]
    else:
        lc = pick(rng, [780, 850, 980, 1060, 1310, 1550, 1600]) * NM
        span = grid(rng, 20, 200, 10) * NM
        l1, l2 = lc - span / 2, lc + span / 2
        band = f"be centered at {hl(lc)} with a total wavelength span of {hl(span)}"
        setl = f"lc = {lit(lc)}; span = {lit(span)};\n"
        props = [("wavelength start", "lc - span/2"), ("wavelength stop", "lc + span/2")]
    qn = (f"{pick(rng, OPENERS)} add a {src[1]} named '{name}' with injection axis '{src[2]}' at the origin. "
          f"Its spectrum should {band}; configure it through the 'wavelength start' and 'wavelength stop' "
          f"properties." + (EXACT_NOTE if kind == "freq" else ""))
    code = setl + ("addfdtd;\n" if src[0] == "addmode" else "") + obj(
        src[0], name, [("injection axis", q(src[2])), ("x", 0.0), ("y", 0.0), ("z", 0.0)] + props)
    asserts = [A(name, "wavelength start", l1, True), A(name, "wavelength stop", l2, True)]
    if src[2] != default_axis:
        asserts.append(A(name, "injection axis", src[2]))
    return task(CAT_SIM, "source_band", 1, qn, code, asserts)


def mesh_ppw(rng: random.Random):
    lam = pick(rng, [1260, 1310, 1500, 1550]) * NM
    n = pick(rng, [2.0, 3.48, 1.45, 2.4, 3.2])
    N = pick(rng, [10, 12, 15, 16, 20, 24, 25, 30])
    s = grid(rng, 50, 200, 10) * NM
    mg = grid(rng, 100, 500, 50) * NM
    L = grid(rng, 2, 10, 1) * UM
    d = lam / (n * N)
    qn = (f"{pick(rng, OPENERS)} add a mesh override region 'slot_mesh' around a {hl(s)} wide slot centered on "
          f"y = 0 that runs along x. The region should extend {hl(mg)} beyond each slot wall in y, span "
          f"{hl(L)} in x and 300 nm in z (centered at x = 0, z = 110 nm). The mesh step in x, y and z must give "
          f"{N} mesh cells per wavelength for {hl(lam)} light in a material of index {n} (use 'set maximum "
          f"mesh step' with 'dx', 'dy', 'dz')." + EXACT_NOTE)
    code = (f"lam = {lit(lam)}; n = {n}; N = {N}; s = {lit(s)}; mg = {lit(mg)}; d = lam/(n*N);\n"
            + obj("addmesh", "slot_mesh", [("x", 0.0), ("x span", L), ("y", 0.0), ("y span", "s + 2*mg"),
                                           ("z", 110 * NM), ("z span", 300 * NM),
                                           ("set maximum mesh step", 1), ("dx", "d"), ("dy", "d"), ("dz", "d")]))
    asserts = [A("slot_mesh", "dx", d, True), A("slot_mesh", "dz", d, True),
               A("slot_mesh", "y span", s + 2 * mg, True)]
    return task(CAT_SIM, "mesh_ppw", 1, qn, code, asserts)


def sim_time(rng: random.Random):
    L = grid(rng, 10, 200, 5) * UM
    ng = pick(rng, [1.5, 2.0, 3.0, 4.2, 4.3, 4.5])
    k = pick(rng, [2, 3, 4, 5])
    acc = rng.randint(1, 4)
    shut = pick(rng, [1e-4, 1e-5, 1e-6])
    T = k * L * ng / C0
    qn = (f"{pick(rng, OPENERS)} add a 2D FDTD region (default name 'FDTD') spanning {hl(L + 2 * UM)} in x and "
          f"{hl(4 * UM)} in y, centered at the origin, for a device of length {hl(L)} with group index {ng}. "
          f"Set the simulation time to {k} times the time a pulse needs to travel the device length at that "
          f"group index, mesh accuracy {acc}, and an auto shutoff minimum of {shut:g}." + EXACT_NOTE)
    code = (f"L = {lit(L)}; ng = {ng}; k = {k};\n"
            + obj("addfdtd", None, [("dimension", q("2D")), ("x", 0.0), ("x span", L + 2 * UM), ("y", 0.0),
                                    ("y span", 4 * UM), ("simulation time", "k*L*ng/c"), ("mesh accuracy", acc),
                                    ("auto shutoff min", repr(shut))]))
    asserts = [A("FDTD", "simulation time", T, True, rtol=1e-4), A("FDTD", "dimension", "2D"),
               A("FDTD", "auto shutoff min", shut, tol=shut * 1e-6), A("FDTD", "x span", L + 2 * UM)]
    return task(CAT_SIM, "sim_time", 1, qn, code, asserts)


# ---------------------------------------------------------------------------
# derived_monitor_placement  (test)
# ---------------------------------------------------------------------------
CAT_MON = "derived_monitor_placement"


def tr_monitors(rng: random.Random):
    L = grid(rng, 6, 40, 1) * UM
    w = grid(rng, 400, 600, 10) * NM
    t = 220 * NM
    ds, dr, dt = grid(rng, 0.5, 2, 0.5) * UM, grid(rng, 0.2, 1, 0.1) * UM, grid(rng, 0.5, 2, 0.5) * UM
    m = grid(rng, 0.5, 1.5, 0.5) * UM
    zs = 2 * UM
    qn = (f"{pick(rng, OPENERS)} instrument a straight waveguide that runs along x from x = -{hl(L / 2)} to "
          f"x = {hl(L / 2)} ({hl(w)} wide, {hl(t)} thick on z = 0; you do not need to create the waveguide). "
          f"Add a mode source 'source' (injection axis 'x-axis') located {hl(ds)} inside the input end. Add "
          f"a reflection monitor 'refl' {hl(dr)} behind the source (toward the input end) and a transmission "
          f"monitor 'trans' {hl(dt)} before the output end. Both monitors are '2D X-normal' power monitors "
          f"centered on the core (y = 0, vertical center of the core) whose y span equals the waveguide width "
          f"plus {hl(m)} on each side, and whose z span is {hl(zs)}.")
    xs = -L / 2 + ds
    code = f"L = {lit(L)}; w = {lit(w)}; t = {lit(t)}; ds = {lit(ds)}; dr = {lit(dr)}; dt = {lit(dt)}; m = {lit(m)};\n"
    code += "addfdtd;\n" + obj("addmode", "source", [("injection axis", q("x-axis")), ("x", "-L/2 + ds"), ("y", 0.0),
                                                      ("y span", "w + 2*m"), ("z", "t/2"), ("z span", zs)])
    for name, x in (("refl", "-L/2 + ds - dr"), ("trans", "L/2 - dt")):
        code += obj("addpower", name, [("monitor type", q("2D X-normal")), ("x", x), ("y", 0.0),
                                       ("y span", "w + 2*m"), ("z", "t/2"), ("z span", zs)])
    asserts = [A("source", "x", xs, True), A("refl", "x", xs - dr, True), A("trans", "x", L / 2 - dt, True),
               A("trans", "y span", w + 2 * m, True), A("trans", "z", t / 2, True)]
    return task(CAT_MON, "tr_monitors", 1, qn, code, asserts)


def box_monitors(rng: random.Random):
    r = grid(rng, 50, 500, 10) * NM
    mg = grid(rng, 50, 300, 10) * NM
    c = [grid(rng, -1, 1, 0.1) * UM for _ in range(3)]
    h = r + mg
    qn = (f"{pick(rng, OPENERS)} enclose a nanoparticle of radius {hl(r)} centered at "
          f"({hl(c[0])}, {hl(c[1])}, {hl(c[2])}) in a closed cube of six power monitors whose faces sit "
          f"{hl(mg)} outside the particle surface. Name them 'x1'/'x2' (the faces at lower/higher x, type "
          f"'2D X-normal'), 'y1'/'y2' ('2D Y-normal') and 'z1'/'z2' ('2D Z-normal'); each face spans the full "
          f"cube side in its two in-plane directions and is centered on the particle in those directions.")
    code = f"cx = {lit(c[0])}; cy = {lit(c[1])}; cz = {lit(c[2])}; hw = {lit(r)} + {lit(mg)};\n"
    spec = {"x": ("2D X-normal", ["y", "z"]), "y": ("2D Y-normal", ["x", "z"]), "z": ("2D Z-normal", ["x", "y"])}
    for ax, (mt, inplane) in spec.items():
        for i, sgn in ((1, "-"), (2, "+")):
            props = [("monitor type", q(mt)), (ax, f"c{ax} {sgn} hw")]
            for ip in inplane:
                props += [(ip, f"c{ip}"), (f"{ip} span", "2*hw")]
            code += obj("addpower", f"{ax}{i}", props)
    asserts = [A("x1", "x", c[0] - h, True), A("y2", "y", c[1] + h, True), A("z1", "z", c[2] - h, True),
               A("z2", "x span", 2 * h, True), A("x2", "z", c[2], True), A("y1", "monitor type", "2D Y-normal")]
    return task(CAT_MON, "box_monitors", 1, qn, code, asserts)


def profile_slice(rng: random.Random):
    tb = pick(rng, [0.0, 1 * UM, 2 * UM, 3 * UM])
    t = pick(rng, [220, 250, 300, 400, 600]) * NM
    X, Y, Z = grid(rng, 4, 30, 1) * UM, grid(rng, 2.5, 8, 0.5) * UM, pick(rng, [1.5, 2.5, 3, 3.5, 4]) * UM
    zf = tb + t / 2
    base = "z = 0" if tb == 0 else f"z = {hl(tb)}"
    qn = (f"{pick(rng, OPENERS)} add two frequency-domain field profile monitors for a waveguide whose "
          f"{hl(t)} thick core has its bottom surface at {base}. The FDTD region (already defined elsewhere) "
          f"spans {hl(X)} x {hl(Y)} x {hl(Z)} centered at (0, 0, {hl(zf)}). 'field_xy' is a '2D Z-normal' "
          f"monitor through the vertical middle of the core covering the full x and y extent of the region. "
          f"'field_xz' is a '2D Y-normal' monitor at y = 0 covering the full x and z extent of the region.")
    code = (f"tb = {lit(tb)}; t = {lit(t)}; zc = tb + t/2;\n"
            + obj("addprofile", "field_xy", [("monitor type", q("2D Z-normal")), ("x", 0.0), ("x span", X),
                                             ("y", 0.0), ("y span", Y), ("z", "zc")])
            + obj("addprofile", "field_xz", [("monitor type", q("2D Y-normal")), ("x", 0.0), ("x span", X),
                                             ("y", 0.0), ("z", "zc"), ("z span", Z)]))
    asserts = [A("field_xy", "z", zf, True), A("field_xy", "y span", Y), A("field_xz", "z", zf, True),
               A("field_xz", "z span", Z), A("field_xz", "monitor type", "2D Y-normal")]
    return task(CAT_MON, "profile_slice", 1, qn, code, asserts)


def freq_points(rng: random.Random):
    f1 = grid(rng, 180, 220, 5) * THZ
    df = pick(rng, [0.25, 0.5, 1.0, 2.0]) * THZ
    npts = rng.randint(11, 81)
    f2 = f1 + df * (npts - 1)
    qn = (f"{pick(rng, OPENERS)} add a plane-wave source 'src' (injection axis 'z-axis') whose spectrum spans "
          f"{num(f1 / THZ)} THz to {num(f2 / THZ)} THz (set via 'wavelength start'/'wavelength stop'), and a "
          f"'2D Z-normal' power monitor 'T' at z = 1 um that overrides the global monitor settings and samples "
          f"that band with a frequency spacing of exactly {num(df / THZ)} THz, including both end points."
          + EXACT_NOTE)
    code = (f"f1 = {num(f1 / THZ)}e12; f2 = {num(f2 / THZ)}e12; df = {num(df / THZ)}e12;\n"
            + obj("addplane", "src", [("injection axis", q("z-axis")), ("wavelength start", "c/f2"),
                                      ("wavelength stop", "c/f1")])
            + obj("addpower", "T", [("monitor type", q("2D Z-normal")), ("z", 1 * UM),
                                    ("override global monitor settings", 1),
                                    ("frequency points", "round((f2-f1)/df) + 1")]))
    asserts = [A("T", "frequency points", npts, True), A("T", "override global monitor settings", 1),
               A("src", "wavelength start", C0 / f2, True)]
    return task(CAT_MON, "freq_points", 1, qn, code, asserts)


def time_probe(rng: random.Random):
    ri = grid(rng, 2, 15, 0.5) * UM
    w = grid(rng, 400, 800, 10) * NM
    cx, cy = grid(rng, -5, 5, 0.5) * UM, grid(rng, -5, 5, 0.5) * UM
    ro = ri + w
    rc = (ri + ro) / 2
    qn = (f"{pick(rng, OPENERS)} add a ring 'ring' centered at ({hl(cx)}, {hl(cy)}) with inner radius {hl(ri)} "
          f"and outer radius {hl(ro)} (220 nm thick, centered at z = 110 nm, material '{SI}'). Then add two "
          f"point time-domain monitors inside the ring waveguide, on its centerline and at mid-height: "
          f"'probe_right' at the ring's largest-x point and 'probe_top' at its largest-y point.")
    code = (f"cx = {lit(cx)}; cy = {lit(cy)}; ri = {lit(ri)}; ro = {lit(ro)}; rc = (ri+ro)/2;\n"
            + obj("addring", "ring", [("x", "cx"), ("y", "cy"), ("inner radius", "ri"), ("outer radius", "ro"),
                                      ("z", 110 * NM), ("z span", 220 * NM), ("material", q(SI))])
            + obj("addtime", "probe_right", [("monitor type", q("Point")), ("x", "cx + rc"), ("y", "cy"),
                                             ("z", 110 * NM)])
            + obj("addtime", "probe_top", [("monitor type", q("Point")), ("x", "cx"), ("y", "cy + rc"),
                                           ("z", 110 * NM)]))
    asserts = [A("probe_right", "x", cx + rc, True), A("probe_right", "y", cy, True),
               A("probe_top", "y", cy + rc, True), A("probe_top", "z", 110 * NM, True)]
    return task(CAT_MON, "time_probe", 1, qn, code, asserts)


FAMILIES = [
    (soi_strip, "train"), (rib, "train"), (taper_poly, "train"), (extents, "train"), (slot, "train"), (bend, "train"),
    (dc, "train"), (mmi12, "train"), (mmi22, "train"), (ring_bus, "train"), (add_drop, "train"), (double_ring, "train"),
    (ar_coating, "train"), (stack, "train"), (qw_bilayer, "train"), (fp_cavity, "train"),
    (fdtd_margins, "test"), (source_band, "test"), (mesh_ppw, "test"), (sim_time, "test"),
    (tr_monitors, "test"), (box_monitors, "test"), (profile_slice, "test"), (freq_points, "test"), (time_probe, "test"),
]
