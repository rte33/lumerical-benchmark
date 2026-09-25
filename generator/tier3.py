"""Tier 3: simulate-and-extract tasks (real engine + FDTD solver license).

The script must build a small 2D thin-film FDTD simulation, run it, and leave a
named scalar result in the workspace. The expected value is taken from running
the gold script; the build additionally requires it to agree with the exact
transfer-matrix (analytic) result, so every reference value is physically
validated. All simulation settings are fully specified in the question so the
result is reproducible.
"""
from __future__ import annotations

import cmath
import math
import random

from .util import EXACT_NOTE, NM, OPENERS, UM, E, grid, hl, lit, num, pick, task

CAT_FILM = "simulation_thin_films"
CAT_SPEC = "simulation_spectra"
TIMEOUT = 240

SETUP_TXT = (
    "Simulation setup: a 2D FDTD region (default name 'FDTD') centered at the origin, x span 100 nm with "
    "periodic boundaries in x, y span {ys}, PML in y, mesh accuracy 6 and simulation time {tsim} fs. Light "
    "is a plane-wave source 'source' injected along +y (injection axis 'y-axis', direction 'Forward') at "
    "y = {ysrc}, spanning 1 um in x, with wavelength range {l1} to {l2}. Power monitors are 'Linear X' "
    "monitors spanning 1 um in x that override the global monitor settings with {npts} frequency points."
)


def tmm(layers, lam, n0=1.0, ns=1.0):
    """Normal-incidence (R, T) of lossless layers [(n, d), ...] between media n0 and ns."""
    m00, m01, m10, m11 = 1, 0, 0, 1
    for n, d in layers:
        dl = 2 * math.pi * n * d / lam
        a, b, c_, dd = cmath.cos(dl), 1j * cmath.sin(dl) / n, 1j * n * cmath.sin(dl), cmath.cos(dl)
        m00, m01, m10, m11 = m00 * a + m01 * c_, m00 * b + m01 * dd, m10 * a + m11 * c_, m10 * b + m11 * dd
    B, C = m00 + m01 * ns, m10 + m11 * ns
    r = (n0 * B - C) / (n0 * B + C)
    t = 2 * n0 / (n0 * B + C)
    return abs(r) ** 2, (ns / n0) * abs(t) ** 2


def _fdtd(ys: float, tsim: int) -> str:
    return (f'addfdtd;\nset("dimension", "2D");\nset("x", 0); set("x span", 100e-9);\nset("y", 0); set("y span", {lit(ys)});\n'
            f'set("x min bc", "Periodic");\nset("mesh accuracy", 6);\nset("simulation time", {tsim}e-15);\n')


def _source(ysrc: float, l1: float, l2: float) -> str:
    return ('addplane;\nset("name", "source");\nset("injection axis", "y-axis");\nset("direction", "Forward");\n'
            f'set("x", 0); set("x span", 1e-6);\nset("y", {lit(ysrc)});\n'
            f'set("wavelength start", {lit(l1)});\nset("wavelength stop", {lit(l2)});\n')


def _monitor(name: str, y: float, npts: int) -> str:
    return (f'addpower;\nset("name", "{name}");\nset("monitor type", "Linear X");\nset("x", 0); set("x span", 1e-6);\n'
            f'set("y", {lit(y)});\nset("override global monitor settings", 1);\nset("frequency points", {npts});\n')


def _layer(name: str, y0: float, y1, n: float) -> str:
    return (f'addrect;\nset("name", "{name}");\nset("x", 0); set("x span", 1e-6);\n'
            f'set("y min", {lit(y0) if isinstance(y0, float) else y0}); set("y max", {lit(y1) if isinstance(y1, float) else y1});\n'
            f'set("index", {n});\n')


def _setup_txt(ys, tsim, ysrc, l1, l2, npts):
    return SETUP_TXT.format(ys=hl(ys), tsim=tsim, ysrc=hl(ysrc), l1=hl(l1), l2=hl(l2), npts=npts)


# ---------------------------------------------------------------------------
# simulation_thin_films  (train)
# ---------------------------------------------------------------------------

def slab_T(rng: random.Random):
    n = pick(rng, [1.45, 2.0, 2.5, 3.0, 3.48])
    t = grid(rng, 100, 600, 10) * NM
    lam = pick(rng, [1310, 1550]) * NM
    Ra, Ta = tmm([(n, t)], lam)
    qn = (f"{pick(rng, OPENERS)} compute the normal-incidence power transmission of a free-standing dielectric "
          f"film at {hl(lam)}. The film 'film' (index {n}, set via 'index') occupies y = 0 to y = {hl(t)} and "
          f"spans 1 um in x. " + _setup_txt(4 * UM, 500, -1.2 * UM, lam - 50 * NM, lam + 50 * NM, 101)
          + f" Place the transmission monitor 'T' at y = 1.2 um. Run the simulation and store the transmission "
          f"at exactly {hl(lam)} (interpolated from the monitor spectrum) in a variable named 'T_film'.")
    code = (_fdtd(4 * UM, 500) + _layer("film", 0.0, t, n) + _source(-1.2 * UM, lam - 50 * NM, lam + 50 * NM)
            + _monitor("T", 1.2 * UM, 101)
            + f'run;\nf = getdata("T", "f");\nT_film = interp(transmission("T"), f, c/{lit(lam)});\n')
    return task(CAT_FILM, "slab_T", 3, qn, code, [E("T_film", round(Ta, 6), tol=0.01)],
                timeout=TIMEOUT, reference={"analytic": Ta, "quantity": "T", "sanity_tol": 0.02})


def slab_R(rng: random.Random):
    n = pick(rng, [1.45, 2.0, 2.5, 3.0, 3.48])
    t = grid(rng, 100, 600, 10) * NM
    lam = pick(rng, [1310, 1550]) * NM
    Ra, Ta = tmm([(n, t)], lam)
    qn = (f"{pick(rng, OPENERS)} compute the normal-incidence power reflectance of a free-standing dielectric "
          f"film at {hl(lam)}. The film 'film' (index {n}, set via 'index') occupies y = 0 to y = {hl(t)} and "
          f"spans 1 um in x. " + _setup_txt(4 * UM, 500, -1.2 * UM, lam - 50 * NM, lam + 50 * NM, 101)
          + f" Place a reflection monitor 'R' behind the source at y = -1.6 um. Run the simulation and store the "
          f"reflectance at exactly {hl(lam)} (interpolated, as a positive number) in a variable named 'R_film'.")
    code = (_fdtd(4 * UM, 500) + _layer("film", 0.0, t, n) + _source(-1.2 * UM, lam - 50 * NM, lam + 50 * NM)
            + _monitor("R", -1.6 * UM, 101)
            + f'run;\nf = getdata("R", "f");\nR_film = -interp(transmission("R"), f, c/{lit(lam)});\n')
    return task(CAT_FILM, "slab_R", 3, qn, code, [E("R_film", round(Ra, 6), tol=0.01)],
                timeout=TIMEOUT, reference={"analytic": Ra, "quantity": "R", "sanity_tol": 0.02})


def ar_R(rng: random.Random):
    ns = pick(rng, [1.5, 2.0, 2.5, 3.0, 3.48])
    nc = pick(rng, [1.2, 1.3, 1.38, 1.45, 1.6, 1.8, 1.9])
    lam = pick(rng, [1310, 1550]) * NM
    tc = grid(rng, 100, 400, 10) * NM
    Ra, _ = tmm([(nc, tc)], lam, 1.0, ns)
    qn = (f"{pick(rng, OPENERS)} compute the reflectance of a coated substrate at {hl(lam)}. A coating 'coating' "
          f"(index {nc}) occupies y = 0 to y = {hl(tc)}; the substrate 'substrate' (index {ns}) fills y = {hl(tc)} "
          f"to y = 5 um so that it extends through the upper PML (both span 1 um in x, indices set via 'index'). "
          + _setup_txt(4 * UM, 500, -1.2 * UM, lam - 50 * NM, lam + 50 * NM, 101)
          + f" Place a reflection monitor 'R' at y = -1.6 um. Run the simulation and store the reflectance at "
          f"exactly {hl(lam)} (interpolated, positive) in a variable named 'R_ar'.")
    code = (_fdtd(4 * UM, 500) + _layer("coating", 0.0, tc, nc) + _layer("substrate", tc, 5 * UM, ns)
            + _source(-1.2 * UM, lam - 50 * NM, lam + 50 * NM) + _monitor("R", -1.6 * UM, 101)
            + f'run;\nf = getdata("R", "f");\nR_ar = -interp(transmission("R"), f, c/{lit(lam)});\n')
    return task(CAT_FILM, "ar_R", 3, qn, code, [E("R_ar", round(Ra, 6), tol=0.01)],
                timeout=TIMEOUT, reference={"analytic": Ra, "quantity": "R", "sanity_tol": 0.02})


# ---------------------------------------------------------------------------
# simulation_spectra  (test)
# ---------------------------------------------------------------------------

def dbr_peak(rng: random.Random):
    N = rng.randint(2, 6)
    nh, nl = pick(rng, [(2.0, 1.45), (2.2, 1.46), (2.5, 1.5), (3.0, 1.45), (3.48, 1.45)])
    lam = pick(rng, [1310, 1550]) * NM
    th, tl = lam / (4 * nh), lam / (4 * nl)
    stack = N * (th + tl)
    layers = [(nh, th), (nl, tl)] * N
    Ra, _ = tmm(layers, lam)
    qn = (f"{pick(rng, OPENERS)} compute the peak reflectance of a free-standing {N}-pair quarter-wave Bragg "
          f"mirror designed for {hl(lam)}. Along +y, alternate layers 'hi_k' (index {nh}) and 'lo_k' (index "
          f"{nl}), k = 1..{N}, beginning with hi_1, each a quarter wavelength thick in its own material, with no "
          f"gaps (indices via 'index', 1 um wide in x). The whole stack is centered on y = 0. "
          + _setup_txt(6 * UM, 1000, -2.2 * UM, lam - 50 * NM, lam + 50 * NM, 101)
          + f" Place a reflection monitor 'R' at y = -2.6 um. Run the simulation and store the reflectance at "
          f"{hl(lam)} (interpolated, positive) in a variable named 'R_peak'." + EXACT_NOTE)
    code = (f"N = {N}; lam = {lit(lam)}; nh = {nh}; nl = {nl}; th = lam/(4*nh); tl = lam/(4*nl);\n"
            + _fdtd(6 * UM, 1000)
            + "y0 = -N*(th+tl)/2;\nfor(k=1:N){\n  yb = y0 + (k-1)*(th+tl);\n"
              '  addrect; set("name", "hi_" + num2str(k)); set("x", 0); set("x span", 1e-6); set("y min", yb); set("y max", yb + th); set("index", nh);\n'
              '  addrect; set("name", "lo_" + num2str(k)); set("x", 0); set("x span", 1e-6); set("y min", yb + th); set("y max", yb + th + tl); set("index", nl);\n}\n'
            + _source(-2.2 * UM, lam - 50 * NM, lam + 50 * NM) + _monitor("R", -2.6 * UM, 101)
            + 'run;\nf = getdata("R", "f");\nR_peak = -interp(transmission("R"), f, c/lam);\n')
    return task(CAT_SPEC, "dbr_peak", 3, qn, code, [E("R_peak", round(Ra, 6), tol=0.01)],
                timeout=TIMEOUT, reference={"analytic": Ra, "quantity": "R", "sanity_tol": 0.02,
                                            "stack_thickness": stack})


def fp_peak(rng: random.Random):
    n = pick(rng, [2.0, 2.5, 3.0, 3.48])
    t = grid(rng, 500, 1500, 50) * NM
    # choose a transmission resonance lambda_m = 2 n t / m inside 1.2-1.7 um
    ms = [m for m in range(1, 30) if 1.25 * UM <= 2 * n * t / m <= 1.65 * UM]
    if not ms:
        return fp_peak(rng)
    m = pick(rng, ms)
    lp = 2 * n * t / m
    fsr = lp ** 2 / (2 * n * t)
    half = round(0.3 * fsr / NM) * NM
    l1, l2 = round((lp - half) / NM) * NM, round((lp + half) / NM) * NM
    qn = (f"{pick(rng, OPENERS)} find the Fabry-Perot transmission peak of a free-standing film. The film 'film' "
          f"(index {n}, set via 'index') occupies y = 0 to y = {hl(t)} and spans 1 um in x. "
          + _setup_txt(6 * UM, 1500, -1.2 * UM, l1, l2, 501)
          + f" Place the transmission monitor 'T' at y = {hl(t + 1.0 * UM)}. Run the simulation, locate the "
          f"transmission maximum within the source band, and store its wavelength (in meters) in a variable "
          f"named 'lambda_peak'.")
    code = (_fdtd(6 * UM, 1500) + _layer("film", 0.0, t, n) + _source(-1.2 * UM, l1, l2)
            + _monitor("T", t + 1.0 * UM, 501)
            + 'run;\nf = getdata("T", "f");\nTs = transmission("T");\n'
              "imax = find(Ts == max(Ts));\nlambda_peak = c/f(imax(1));\n")
    return task(CAT_SPEC, "fp_peak", 3, qn, code, [E("lambda_peak", lp, rtol=0.003)],
                timeout=TIMEOUT, reference={"analytic": lp, "quantity": "lambda_peak", "sanity_rtol": 0.005})


for _f in (slab_T, slab_R, ar_R, dbr_peak, fp_peak):
    _f.count = 12

FAMILIES = [(slab_T, "train"), (slab_R, "train"), (ar_R, "train"), (dbr_peak, "test"), (fp_peak, "test")]
