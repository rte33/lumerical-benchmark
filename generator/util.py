"""Shared helpers for procedural generation of Lumerical benchmark tasks.

Every family function takes a `random.Random` and returns one task dict with
`question`, `gold_code` and `test_assertions`. Values are drawn from integer
grids (nm / um) so the numbers printed in questions are exact and match the
assertions without floating-point artefacts.
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

C0 = 299792458.0  # same value as Lumerical's built-in constant `c`
NM, UM, FS, THZ = 1e-9, 1e-6, 1e-15, 1e12

# Tolerances: values stated in the question are checked to 1 pm; values the model
# must derive allow 0.1 nm so an honest rounding to one decimal in nm still passes.
TOL_GIVEN = 1e-12
TOL_DERIVED = 1e-10

MATERIALS = {
    "si": "Si (Silicon) - Palik",
    "sio2": "SiO2 (Glass) - Palik",
    "sin": "Si3N4 (Silicon Nitride) - Phillip",
    "au": "Au (Gold) - Palik",
    "ag": "Ag (Silver) - Johnson and Christy",
    "al": "Al (Aluminium) - Palik",
    "inp": "InP - Palik",
    "gaas": "GaAs - Palik",
}

OPENERS = [
    "Write a Lumerical script to",
    "Write an Ansys Lumerical (.lsf) script that will",
    "Using the Lumerical scripting language,",
    "Create a Lumerical FDTD script to",
]

EXACT_NOTE = " Compute derived quantities exactly in the script rather than rounding them."


def grid(rng: random.Random, lo: float, hi: float, step: float) -> float:
    """Pick a value on lo:step:hi (inclusive) without float drift."""
    n = int(round((hi - lo) / step))
    return round(lo + step * rng.randint(0, n), 10)


def num(x: float, nd: int = 4) -> str:
    s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def hl(v: float) -> str:
    """Human-readable length: '450 nm', '2.5 um'."""
    if abs(v) < 1e-15:
        return "0"
    if abs(v) >= 1e-6 - 1e-15:
        return f"{num(v / UM)} um"
    return f"{num(v / NM, 3)} nm"


def ht(v: float) -> str:
    return f"{num(v / FS, 3)} fs"


def lit(v: float) -> str:
    """LSF literal for an SI length/time value: 450e-9, 2.5e-6."""
    if v == 0:
        return "0"
    a = abs(v)
    if 1e-6 - 1e-15 <= a < 1:
        return f"{num(v / UM, 6)}e-6"
    if 1e-9 - 1e-18 <= a < 1e-6:
        return f"{num(v / NM, 6)}e-9"
    if a < 1e-9:
        return repr(float(v))
    return num(v, 9)


def q(s: str) -> str:
    """Mark a Python string as an LSF string literal."""
    return '"' + s + '"'


def fmt(v: Any) -> str:
    """Format a property value for gold code: floats -> SI literal, str -> raw expression."""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return lit(v)
    return str(v)


def obj(add: str, name: Optional[str], props: Sequence[Tuple[str, Any]]) -> str:
    lines = [f"{add};"]
    if name is not None:
        lines.append(f'set("name", "{name}");')
    for p, v in props:
        lines.append(f'set("{p}", {fmt(v)});')
    return "\n".join(lines) + "\n"


def A(target: str, prop: str, val: Any, derived: bool = False, tol: Optional[float] = None,
      rtol: Optional[float] = None) -> Dict[str, Any]:
    """Property assertion; numeric lengths get tight/loose tolerance depending on `derived`."""
    a: Dict[str, Any] = {"target": target, "prop": prop, "val": val}
    if isinstance(val, float) and tol is None and rtol is None:
        tol = TOL_DERIVED if derived else TOL_GIVEN
    if isinstance(val, list) and tol is None and rtol is None:
        tol = TOL_DERIVED if derived else TOL_GIVEN
    if tol is not None:
        a["tol"] = tol
    if rtol is not None:
        a["rtol"] = rtol
    if derived:
        a["derived"] = True
    return a


def E(expr: str, val: Any, setup: str = "", derived: bool = False, tol: Optional[float] = None,
      rtol: Optional[float] = None) -> Dict[str, Any]:
    """Expression assertion (real engine only)."""
    a: Dict[str, Any] = {"type": "expr", "expr": expr, "val": val}
    if setup:
        a["setup"] = setup
    if tol is not None:
        a["tol"] = tol
    elif isinstance(val, float) and rtol is None:
        a["tol"] = TOL_DERIVED if derived else TOL_GIVEN
    if rtol is not None:
        a["rtol"] = rtol
    if derived:
        a["derived"] = True
    return a


def count_setup(name: str, cond: str) -> Tuple[str, str]:
    """Order-independent count of objects named `name` satisfying `cond` (uses benchzzx/y/z/r)."""
    setup = (
        "benchzzn=0; "
        f'for(benchzzi=1:getnamednumber("{name}")){{ '
        f'benchzzx=getnamed("{name}","x",benchzzi); benchzzy=getnamed("{name}","y",benchzzi); '
        f"if({cond}){{ benchzzn=benchzzn+1; }} }}"
    )
    return setup, "benchzzn"


def extreme_setup(name: str, prop: str, mode: str) -> Tuple[str, str]:
    """Order-independent max/min of a property over all objects named `name`."""
    init = "-1e300" if mode == "max" else "1e300"
    op = ">" if mode == "max" else "<"
    setup = (
        f"benchzzm={init}; "
        f'for(benchzzi=1:getnamednumber("{name}")){{ '
        f'benchzzv=getnamed("{name}","{prop}",benchzzi); '
        f"if(benchzzv {op} benchzzm){{ benchzzm=benchzzv; }} }}"
    )
    return setup, "benchzzm"


def task(category: str, family: str, tier: int, question: str, code: str,
         asserts: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
    t = {
        "category": category,
        "family": family,
        "tier": tier,
        "question": question.strip(),
        "gold_code": "newproject;\n" + code.strip() + "\n",
        "test_assertions": asserts,
    }
    t.update(extra)
    return t


def pick(rng: random.Random, seq: Iterable[Any]) -> Any:
    seq = list(seq)
    return seq[rng.randrange(len(seq))]
