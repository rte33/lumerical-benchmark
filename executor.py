"""Execution harness and grading engines for Lumerical Scripting Language (.lsf).

Supports two execution backends:
1. Fast Headless Simulator (LumericalSimulator):
   - Zero-dependency, offline state-machine CAD sandbox.
   - Accurately tracks geometry hierarchy, property validation, and reports authentic error messages.
2. Real Ansys Lumerical Engine (run_real_lumerical):
   - Automates actual Ansys Lumerical FDTD software via lumapi.
"""
from __future__ import annotations

import atexit
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class ExecResult:
    ok: bool
    result: Optional[List[Any]] = None
    error: Optional[str] = None


# Canonical Lumerical error categories
_LUM_SIG_RULES = [
    (re.compile(r"syntax error", re.I), "syntax_error"),
    (re.compile(r"property '.*?' not recognized|unknown property", re.I), "unknown_property"),
    (re.compile(r"command '.*?' is unknown|unknown command|not recognized", re.I), "unknown_command"),
    (re.compile(r"object '.*?' does not exist|no object currently selected", re.I), "object_not_found"),
    (re.compile(r"invalid material|material '.*?' not found", re.I), "invalid_material"),
    (re.compile(r"dimension mismatch|out of bounds", re.I), "dimension_mismatch"),
    (re.compile(r"wrong number of arguments|invalid number of arguments", re.I), "wrong_arg_count"),
    (re.compile(r"type mismatch|invalid argument type", re.I), "type_error"),
    (re.compile(r"variable '.*?' is undefined", re.I), "undefined_variable"),
    (re.compile(r"assertion failed", re.I), "assertion_error"),
]


def lumerical_error_signature(error: str | None) -> str:
    """Classify Lumerical CAD runtime tracebacks and errors into canonical categories."""
    if not error:
        return "ok"
    for pat, name in _LUM_SIG_RULES:
        if pat.search(error):
            return name
    return "runtime_error"


_LUM_VALID_PROPS: Dict[str, Set[str]] = {
    "rect": {
        "name", "x", "y", "z", "x span", "y span", "z span",
        "x min", "x max", "y min", "y max", "z min", "z max",
        "material", "index", "override mesh order from material database",
        "mesh order", "grid attribute name", "enabled",
    },
    "circle": {
        "name", "x", "y", "z", "radius", "z span", "material", "index",
        "mesh order", "enabled",
    },
    "ring": {
        "name", "x", "y", "z", "inner radius", "outer radius", "z span",
        "theta start", "theta stop", "material", "index", "mesh order", "enabled",
    },
    "poly": {
        "name", "x", "y", "z", "z span", "vertices", "material", "index",
        "mesh order", "enabled",
    },
    "pyramid": {
        "name", "x", "y", "z", "x span", "y span", "z span",
        "x top span", "y top span", "material", "index", "mesh order", "enabled",
    },
    "fdtd": {
        "name", "dimension", "x", "y", "z", "x span", "y span", "z span",
        "x min", "x max", "y min", "y max", "z min", "z max",
        "mesh accuracy", "mesh refinement", "simulation time",
        "auto shutoff min", "x min bc", "x max bc", "y min bc", "y max bc",
        "z min bc", "z max bc", "pml layers", "enabled",
    },
    "varfdtd": {
        "name", "x", "y", "z", "x span", "y span", "simulation time",
        "mesh accuracy", "x min bc", "x max bc", "y min bc", "y max bc", "enabled",
    },
    "mesh": {
        "name", "x", "y", "z", "x span", "y span", "z span",
        "dx", "dy", "dz", "set maximum mesh step", "override x mesh",
        "override y mesh", "override z mesh", "enabled",
    },
    "monitor": {
        "name", "monitor type", "spatial type", "x", "y", "z",
        "x span", "y span", "z span", "x min", "x max", "y min", "y max",
        "z min", "z max", "override global monitor settings",
        "frequency points", "output power", "output ex", "output ey",
        "output ez", "output hx", "output hy", "output hz",
        "output px", "output py", "output pz", "enabled",
    },
    "source": {
        "name", "injection axis", "direction", "x", "y", "z",
        "x span", "y span", "z span", "wavelength start", "wavelength stop",
        "center wavelength", "wavelength span", "frequency",
        "mode selection", "theta", "phi", "polarization angle", "enabled",
    },
    "port": {
        "name", "direction", "injection axis", "mode selection",
        "x", "y", "z", "y span", "z span", "enabled",
    },
}
_LUM_VALID_PROPS = {k: {p.lower() for p in v} for k, v in _LUM_VALID_PROPS.items()}


class LumericalSimulator:
    """High-fidelity headless Lumerical CAD parser and state machine.

    Maintains simulation object hierarchy, variable bindings, and strictly
    validates property assignments, emitting authentic Lumerical interpreter
    error messages.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.objects: Dict[str, Dict[str, Any]] = {}
        self.variables: Dict[str, Any] = {}
        self.selected: Optional[str] = None
        self.layout_mode: bool = True

    def _eval_expr(self, expr_str: str) -> Any:
        expr_str = expr_str.strip()
        if not expr_str:
            return None

        # String literals
        if (expr_str.startswith('"') and expr_str.endswith('"')) or (
            expr_str.startswith("'") and expr_str.endswith("'")
        ):
            return expr_str[1:-1]

        # Numeric and variable evaluation
        safe_dict = {
            "pi": 3.141592653589793,
            "c": 299792458.0,
            "eps0": 8.854187817e-12,
            "mu0": 1.2566370614e-6,
        }
        safe_dict.update(self.variables)

        try:
            py_expr = expr_str.replace("^", "**")
            return eval(py_expr, {"__builtins__": None}, safe_dict)
        except Exception:
            if expr_str in self.variables:
                return self.variables[expr_str]
            raise NameError(f"variable '{expr_str}' is undefined")

    def run_script(self, script: str) -> ExecResult:
        self.reset()
        lines = script.splitlines()

        for line_idx, line in enumerate(lines, start=1):
            raw_line = line.strip()
            if "#" in raw_line:
                raw_line = raw_line.split("#", 1)[0].strip()
            if not raw_line:
                continue

            if raw_line.startswith(("def ", "class ", "import ", "from ", "print ")):
                return ExecResult(
                    False,
                    None,
                    f"Error: line {line_idx}: syntax error near '{raw_line.split()[0]}'. Lumerical script syntax required, not Python.",
                )

            statements = [s.strip() for s in raw_line.split(";") if s.strip()]
            for stmt in statements:
                try:
                    err = self._exec_stmt(stmt, line_idx)
                    if err:
                        return ExecResult(False, None, err)
                except Exception as ex:
                    return ExecResult(False, None, f"Error: line {line_idx}: {ex}")

        return ExecResult(True, [("ok",)], None)

    def _exec_stmt(self, stmt: str, line_idx: int) -> Optional[str]:
        call_match = re.match(r"^([a-zA-Z0-9_]+)(?:\((.*)\))?$", stmt)
        assign_match = re.match(r"^([a-zA-Z0-9_]+)\s*=\s*(.+)$", stmt)

        if assign_match:
            var_name, expr = assign_match.group(1), assign_match.group(2)
            try:
                val = self._eval_expr(expr)
                self.variables[var_name] = val
                return None
            except Exception as e:
                return f"Error: line {line_idx}: {e}"

        if not call_match:
            parts = stmt.split()
            cmd = parts[0]
            args_str = " ".join(parts[1:])
        else:
            cmd = call_match.group(1).lower()
            args_str = call_match.group(2) or ""

        args = []
        if args_str:
            cur_arg = []
            in_q = False
            q_char = ""
            for ch in args_str:
                if ch in ('"', "'") and not in_q:
                    in_q = True
                    q_char = ch
                    cur_arg.append(ch)
                elif ch == q_char and in_q:
                    in_q = False
                    cur_arg.append(ch)
                elif ch == "," and not in_q:
                    args.append("".join(cur_arg).strip())
                    cur_arg = []
                else:
                    cur_arg.append(ch)
            if cur_arg:
                args.append("".join(cur_arg).strip())

        eval_args = []
        for a in args:
            try:
                eval_args.append(self._eval_expr(a))
            except Exception as e:
                return f"Error: line {line_idx}: {e}"

        # Command Dispatch
        if cmd in ("newproject", "deleteall", "switchtolayout"):
            if cmd == "newproject":
                self.reset()
            elif cmd == "deleteall":
                self.objects.clear()
                self.selected = None
            elif cmd == "switchtolayout":
                self.layout_mode = True
            return None

        # Add Object Primitives
        add_primitives = {
            "addrect": ("rect", "rect"),
            "addcircle": ("circle", "circle"),
            "addring": ("ring", "ring"),
            "addpoly": ("poly", "poly"),
            "addpyramid": ("pyramid", "pyramid"),
            "addfdtd": ("fdtd", "FDTD"),
            "addvarfdtd": ("varfdtd", "varFDTD"),
            "addmesh": ("mesh", "mesh"),
            "addpower": ("monitor", "monitor"),
            "addprofile": ("monitor", "profile"),
            "addindex": ("monitor", "index"),
            "addtime": ("monitor", "time"),
            "addplane": ("source", "source"),
            "addgaussian": ("source", "source"),
            "addmodesource": ("source", "source"),
            "addmode": ("source", "source"),
            "adddipole": ("source", "source"),
            "addtfsf": ("source", "source"),
            "addport": ("port", "port"),
        }

        if cmd in add_primitives:
            obj_type, default_name = add_primitives[cmd]
            base_name = default_name
            name = base_name
            idx = 1
            while name in self.objects:
                name = f"{base_name}_{idx}"
                idx += 1
            new_obj = {"_type": obj_type, "name": name, "enabled": 1}
            self.objects[name] = new_obj
            self.selected = name
            return None

        if cmd == "select":
            if not eval_args:
                return f"Error: line {line_idx}: select requires 1 argument."
            target = str(eval_args[0])
            if target not in self.objects:
                return f"Error: line {line_idx}: object '{target}' does not exist."
            self.selected = target
            return None

        if cmd == "selectall":
            return None

        if cmd == "set":
            if len(eval_args) != 2:
                return f"Error: line {line_idx}: set requires 2 arguments: (property, value)."
            if not self.selected or self.selected not in self.objects:
                return f"Error: line {line_idx}: set - no object currently selected."

            prop_name = str(eval_args[0]).lower().strip()
            val = eval_args[1]
            obj = self.objects[self.selected]
            obj_type = obj.get("_type", "rect")

            valid_props = _LUM_VALID_PROPS.get(obj_type, _LUM_VALID_PROPS["rect"])
            if prop_name not in valid_props:
                return (
                    f"Error: line {line_idx}: set - property '{prop_name}' not recognized "
                    f"for object '{obj_type}'."
                )

            if prop_name == "name":
                new_name = str(val)
                old_name = self.selected
                self.objects[new_name] = self.objects.pop(old_name)
                self.objects[new_name]["name"] = new_name
                self.selected = new_name
            else:
                if prop_name == "injection axis" and str(val).lower() in ("x", "y", "z"):
                    val = f"{str(val).lower()}-axis"
                obj[prop_name] = val
            return None

        if cmd == "setnamed":
            if len(eval_args) != 3:
                return f"Error: line {line_idx}: setnamed requires 3 arguments: (name, property, value)."
            target_name = str(eval_args[0])
            if target_name not in self.objects:
                return f"Error: line {line_idx}: setnamed - object '{target_name}' does not exist."

            prop_name = str(eval_args[1]).lower().strip()
            val = eval_args[2]
            obj = self.objects[target_name]
            obj_type = obj.get("_type", "rect")

            valid_props = _LUM_VALID_PROPS.get(obj_type, _LUM_VALID_PROPS["rect"])
            if prop_name not in valid_props:
                return (
                    f"Error: line {line_idx}: setnamed - property '{prop_name}' not recognized "
                    f"for object '{obj_type}'."
                )

            if prop_name == "name":
                new_name = str(val)
                self.objects[new_name] = self.objects.pop(target_name)
                self.objects[new_name]["name"] = new_name
                if self.selected == target_name:
                    self.selected = new_name
            else:
                if prop_name == "injection axis" and str(val).lower() in ("x", "y", "z"):
                    val = f"{str(val).lower()}-axis"
                obj[prop_name] = val
            return None

        if cmd in ("run", "runanalysis", "save", "load", "closeall", "cleardataset"):
            return None

        return f"Error: line {line_idx}: command '{cmd}' is unknown or not recognized."


# ---------------------------------------------------------------------------
# Real Ansys Lumerical engine
#
# lumapi is driven from a dedicated worker process (`python executor.py
# --lumerical-worker`). A blocked lumapi call cannot be interrupted, and once
# one hangs no new session can be opened in the same process, so on timeout
# the harness kills the worker (and its Lumerical child) and starts a new one.
# ---------------------------------------------------------------------------

# Name of the harness-internal LSF variable used to evaluate "expr" assertions.
# (LSF identifiers may not begin with an underscore.)
_BENCH_VAR = "benchzzval"

# `run;` / `run("FDTD");` / `runsweep;` statements. Lumerical opens a modal "Save as"
# dialog when an unsaved project is run -- even in hidden mode -- which blocks the API
# indefinitely, so a save guard is injected in front of every run statement.
_RUN_STMT = re.compile(r"(?<![\w\"'.])(run|runsweep)\b(\s*\([^;\n]*\))?\s*(;|$)", re.I | re.M)

_STARTUP_TIMEOUT = 180.0


def get_real_lumerical_session():
    """Open an in-process headless Ansys Lumerical FDTD session (used by the worker)."""
    bin_path = os.environ.get("LUMERICAL_BIN", r"G:\Users\fardo\Lumerical_main_inst_26\bin")
    api_path = os.environ.get("LUMERICAL_API", r"G:\Users\fardo\Lumerical_main_inst_26\api\python")

    if bin_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")
    if api_path not in sys.path:
        sys.path.insert(0, api_path)

    import lumapi
    return lumapi.FDTD(hide=True)


def _last_lumerical_error(fdtd) -> str:
    """Fetch the interpreter's own error text; lumapi only raises 'Failed to evaluate code'."""
    try:
        e = fdtd.handle.iapi.appGetLastError()
        return e.contents.str[: e.contents.len].decode("utf-8", "replace").strip()
    except Exception:
        return ""


def _inject_save_guard(code: str, save_path: str) -> str:
    guard = f'if(currentfilename==""){{save("{save_path}");}} '
    return _RUN_STMT.sub(lambda m: guard + m.group(0), code)


def _to_plain(value: Any) -> Any:
    """Convert lumapi return values (numpy arrays/scalars) into plain Python objects."""
    if hasattr(value, "tolist"):
        if getattr(value, "size", 2) == 1:
            return value.flatten()[0].item() if hasattr(value, "flatten") else value.item()
        return value.tolist()
    return value


def _worker_main() -> None:
    """Entry point of the Lumerical worker process."""
    from multiprocessing.connection import Listener

    authkey = bytes.fromhex(sys.stdin.readline().strip())
    listener = Listener(("127.0.0.1", 0), authkey=authkey)
    print(listener.address[1], flush=True)
    # Keep stray Lumerical console output from filling the parent's pipe.
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    conn = listener.accept()

    tmpdir = tempfile.mkdtemp(prefix="lumbench_")
    save_path = os.path.join(tmpdir, "bench_task.fsp").replace("\\", "/")
    try:
        fdtd = get_real_lumerical_session()
    except Exception as e:
        conn.send(("err", f"could not start Lumerical: {e}"))
        return
    conn.send(("ok", "ready"))

    def failure(e: Exception) -> tuple:
        detail = _last_lumerical_error(fdtd) if "Failed to evaluate" in str(e) else ""
        return ("err", detail or str(e))

    try:
        while True:
            try:
                op, arg = conn.recv()
            except (EOFError, OSError):
                break
            try:
                if op == "exec":
                    fdtd.newproject()
                    fdtd.eval(_inject_save_guard(arg, save_path))
                    reply = ("ok", None)
                elif op == "getnamed":
                    reply = ("ok", _to_plain(fdtd.getnamed(*arg)))
                elif op == "expr":
                    fdtd.eval(f"{_BENCH_VAR} = {arg};")
                    reply = ("ok", _to_plain(fdtd.getv(_BENCH_VAR)))
                elif op == "eval":
                    fdtd.eval(arg)
                    reply = ("ok", None)
                elif op == "getv":
                    reply = ("ok", _to_plain(fdtd.getv(arg)))
                else:
                    reply = ("err", f"unknown worker op '{op}'")
            except Exception as e:
                reply = failure(e)
            conn.send(reply)
    finally:
        try:
            fdtd.close()
        except Exception:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)


class _LumericalWorker:
    """Parent-side handle of a Lumerical worker process."""

    def __init__(self):
        import secrets
        import subprocess
        from multiprocessing.connection import Client

        authkey = secrets.token_bytes(16)
        self.proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--lumerical-worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.proc.stdin.write(authkey.hex() + "\n")
        self.proc.stdin.flush()
        port = self.proc.stdout.readline().strip()
        if not port:
            self.kill()
            raise RuntimeError("Lumerical worker failed to start")
        self.conn = Client(("127.0.0.1", int(port)), authkey=authkey)
        status, info = self._recv(_STARTUP_TIMEOUT)
        if status != "ok":
            self.kill()
            raise RuntimeError(info)

    def _recv(self, timeout: Optional[float]):
        if not self.conn.poll(timeout):
            self.kill()
            raise TimeoutError(f"Lumerical did not finish within {timeout:g}s (session restarted)")
        try:
            return self.conn.recv()
        except (EOFError, OSError):
            self.kill()
            raise RuntimeError("Lumerical worker exited unexpectedly (session restarted)")

    def request(self, op: str, arg: Any, timeout: Optional[float]):
        self.conn.send((op, arg))
        return self._recv(timeout)

    def close(self) -> None:
        """Let the worker close Lumerical cleanly (releases the license); kill if it lingers."""
        try:
            self.conn.close()
            self.proc.wait(15)
        except Exception:
            self.kill()

    def kill(self) -> None:
        global _WORKER
        try:
            import psutil
            procs = psutil.Process(self.proc.pid).children(recursive=True)
        except Exception:
            procs = []
        for p in procs:
            try:
                p.kill()
            except Exception:
                pass
        try:
            self.proc.kill()
        except Exception:
            pass
        if _WORKER is self:
            _WORKER = None


_WORKER: Optional[_LumericalWorker] = None


def _worker() -> _LumericalWorker:
    global _WORKER
    if _WORKER is None:
        _WORKER = _LumericalWorker()
        atexit.register(_WORKER.close)
    return _WORKER


def real_lumerical_request(op: str, arg: Any, timeout: Optional[float] = 10.0):
    """Send one operation to the live session: 'exec', 'getnamed', 'expr', 'eval', 'getv'.

    Returns (status, value) where status is 'ok' or 'err'. Raises TimeoutError /
    RuntimeError if the session had to be restarted.
    """
    return _worker().request(op, arg, timeout)


def _flatten(values: Any) -> List[Any]:
    if isinstance(values, (list, tuple)):
        out: List[Any] = []
        for v in values:
            out.extend(_flatten(v))
        return out
    return [values]


def _compare(label: str, expected: Any, actual: Any, ass: dict) -> Optional[str]:
    """Return an error message if `actual` does not match the assertion, else None."""
    rtol = float(ass.get("rtol", 0.0))
    tol = float(ass.get("tol", 0.0 if "rtol" in ass else 1e-6))

    if isinstance(expected, list):
        flat_exp, flat_act = _flatten(expected), _flatten(actual)
        if len(flat_act) != len(flat_exp):
            return f"assertion failed: '{label}' expected {len(flat_exp)} values, got {len(flat_act)}"
        for e_v, a_v in zip(flat_exp, flat_act):
            try:
                if abs(float(a_v) - e_v) > tol + rtol * abs(e_v):
                    return f"assertion failed: '{label}' expected {expected}, got {actual}"
            except (TypeError, ValueError):
                return f"assertion failed: '{label}' expected {expected}, got {actual}"
        return None

    if isinstance(expected, (int, float)):
        try:
            act_num = float(actual)
        except (TypeError, ValueError):
            return f"assertion failed: '{label}' expected {expected}, got {actual!r}"
        if abs(act_num - expected) > tol + rtol * abs(expected):
            bound = f"+/- {tol:g}" + (f" + {rtol:g} rel" if rtol else "")
            return f"assertion failed: '{label}' expected {expected} ({bound}), got {actual}"
        return None

    if isinstance(expected, str) and isinstance(actual, str):
        if actual.strip().lower() != expected.strip().lower():
            return f"assertion failed: '{label}' expected '{expected}', got '{actual}'"
        return None

    if actual != expected:
        return f"assertion failed: '{label}' expected {expected}, got {actual}"
    return None


def check_real_assertions(test_assertions: list[dict] | None, timeout: float = 10.0) -> Optional[str]:
    """Check assertions against the current state of the live session.

    Assertion kinds:
      {"target": obj, "prop": p, "val": v}             -- getnamed(obj, p) == v
      {"type": "expr", "expr": "<lsf expr>", "val": v}  -- value of an LSF expression, e.g.
          'getnamednumber("hole")' or a result variable left by the script ('T1550').
    Numeric checks accept "tol" (absolute, default 1e-6) and/or "rtol" (relative).
    """
    for ass in test_assertions or []:
        expected = ass.get("val")
        try:
            if ass.get("type") == "expr":
                label = ass["expr"]
                status, actual = real_lumerical_request("expr", ass["expr"], timeout)
                if status != "ok":
                    return f"assertion failed: could not evaluate '{label}': {actual}"
            else:
                target = ass.get("target")
                prop = ass.get("prop", "").lower().strip()
                label = f"{target}.{prop}"
                status, actual = real_lumerical_request("getnamed", (target, prop), timeout)
                if status != "ok":
                    return f"assertion failed: could not query '{label}': {actual}"
        except (TimeoutError, RuntimeError) as e:
            return f"RuntimeError: {e}"
        err = _compare(label, expected, actual, ass)
        if err:
            return err
    return None


def execute_real_lumerical(code: str, timeout: float = 10.0) -> Optional[str]:
    """Run a script in a fresh project of the live session. Returns an error string or None."""
    code = (code or "").strip()
    if not code:
        return "Error: empty Lumerical script submission"
    try:
        status, info = real_lumerical_request("exec", code, timeout)
    except (TimeoutError, RuntimeError) as e:
        return f"RuntimeError: {e}"
    return None if status == "ok" else f"RuntimeError: {info}"


def run_real_lumerical(
    code: str,
    test_assertions: list[dict] | None = None,
    timeout: float = 10.0,
) -> ExecResult:
    """Execute Lumerical .lsf code directly in installed Ansys Lumerical FDTD software."""
    err = execute_real_lumerical(code, timeout)
    if err:
        return ExecResult(False, None, err)
    err = check_real_assertions(test_assertions, timeout)
    if err:
        return ExecResult(False, None, err)
    return ExecResult(True, [("ok",)], None)


def run_lumerical(
    code: str,
    test_assertions: list[dict] | None = None,
    timeout: float = 3.0,
    use_real: bool = False,
) -> ExecResult:
    """Execute Lumerical .lsf code in a CAD state machine or real Ansys Lumerical FDTD.

    Grades correctness against specified test assertions on object properties.
    """
    if use_real or os.environ.get("LUMERICAL_ENGINE", "").lower() == "real":
        return run_real_lumerical(code, test_assertions, timeout)

    code = (code or "").strip()
    if not code:
        return ExecResult(False, None, "Error: empty Lumerical script submission")

    sim = LumericalSimulator()
    res = sim.run_script(code)
    if not res.ok:
        return res

    # Check test assertions
    assertions = test_assertions or []
    for ass in assertions:
        if ass.get("type") == "expr":
            return ExecResult(
                False,
                None,
                f"assertion failed: expression assertion '{ass.get('expr')}' requires the real Lumerical engine",
            )
        target = ass.get("target")
        prop = ass.get("prop", "").lower().strip()
        expected = ass.get("val")

        if target not in sim.objects:
            return ExecResult(
                False,
                None,
                f"assertion failed: expected object '{target}' was not created in simulation",
            )

        obj = sim.objects[target]
        if prop not in obj:
            return ExecResult(
                False,
                None,
                f"assertion failed: property '{prop}' was not set on object '{target}'",
            )

        err = _compare(f"{target}.{prop}", expected, obj[prop], ass)
        if err:
            return ExecResult(False, None, err)

    return ExecResult(True, [(len(sim.objects),)], None)


if __name__ == "__main__" and sys.argv[1:] == ["--lumerical-worker"]:
    _worker_main()
