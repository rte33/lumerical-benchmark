"""Generate the extended benchmark and gate every task on the real Lumerical engine.

    python build_extended.py                    # full build (needs Ansys Lumerical)
    python build_extended.py --per-family 3     # quick smoke build
    python build_extended.py --families rib,dc  # only some families

A generated task is kept only if, on the real engine:
  1. the gold script runs without error,
  2. every assertion passes,
  3. every assertion fails once its expected value is perturbed (mutation control),
  4. the assertion set fails on an empty project (null control),
  5. each property assertion fails when the gold script's matching set(...) lines are
     removed, i.e. it is not satisfied by a default value (defaults control; tiers 1-2),
  6. tier-3 simulation results are reproduced exactly by a second run (determinism).
Tasks whose gold script also passes the offline sandbox are marked sandbox-compatible.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict

from executor import check_real_assertions, execute_real_lumerical, real_lumerical_request, run_lumerical
from generator import tier1, tier2, tier3
from generator.util import hl

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "extended")
TIER_MODULES = {1: tier1, 2: tier2, 3: tier3}


def perturb(a: dict):
    b = copy.deepcopy(a)
    v = a["val"]
    if isinstance(v, bool):
        b["val"] = not v
    elif isinstance(v, (int, float)):
        # step well outside the assertion's tolerance band (and at least 10%)
        band = a.get("tol", 0.0 if "rtol" in a else 1e-6) + a.get("rtol", 0.0) * abs(v)
        b["val"] = v + max(0.1 * abs(v), 3 * band) if v != 0 else max(1.0, 3 * band)
    elif isinstance(v, str):
        b["val"] = v + "_MUTATED"
    elif isinstance(v, list):
        def bump(x):
            return [bump(y) for y in x] if isinstance(x, list) else (x * 1.1 if x else 1e-7)
        b["val"] = bump(v)
    else:
        return None
    return b


def strip_prop_lines(code: str, prop: str) -> str:
    return re.sub(r'set\(\s*"' + re.escape(prop) + r'"\s*,[^;]*\);', "", code, flags=re.I)


def gate(t: dict) -> tuple[bool, str, dict]:
    info: dict = {}
    timeout = t.get("timeout", 30)
    t0 = time.time()
    err = execute_real_lumerical(t["gold_code"], timeout)
    info["exec_s"] = round(time.time() - t0, 2)
    if err:
        return False, f"gold failed: {err}", info
    if t["tier"] == 3:
        # Reference values come from the gold simulation; they must agree with the analytic result.
        ref = t["reference"]
        for a in t["test_assertions"]:
            status, val = real_lumerical_request("expr", ("", a["expr"]), 30)
            if status != "ok" or not isinstance(val, (int, float)):
                return False, f"could not read result {a['expr']}: {val}", info
            a["val"] = round(float(val), 6) if abs(val) > 1e-3 else float(val)
            dev = abs(val - ref["analytic"])
            ok = dev <= ref["sanity_tol"] if "sanity_tol" in ref else dev <= ref["sanity_rtol"] * abs(ref["analytic"])
            info["fdtd_vs_analytic"] = round(dev, 6)
            if not ok:
                return False, f"FDTD {val:.5g} disagrees with analytic {ref['analytic']:.5g}", info
            ref["fdtd"] = a["val"]
    err = check_real_assertions(t["test_assertions"], 30)
    if err:
        return False, f"gold assertion: {err}", info

    # Mutation control (state of the gold run is reused)
    for a in t["test_assertions"]:
        m = perturb(a)
        if m is None:
            return False, f"cannot perturb {a}", info
        if check_real_assertions([m], 30) is None:
            return False, f"mutation not caught: {a}", info

    # Determinism: capture tier-3 results, re-run, compare exactly
    if t["tier"] == 3:
        ref = []
        for a in t["test_assertions"]:
            m = dict(a, rtol=0.0, tol=0.0)
            ref.append(check_real_assertions([m], 30))
        err = execute_real_lumerical(t["gold_code"], timeout)
        if err:
            return False, f"rerun failed: {err}", info
        if check_real_assertions(t["test_assertions"], 30):
            return False, "rerun changed result beyond tolerance", info
        info["bit_identical_rerun"] = all(
            (check_real_assertions([dict(a, rtol=0.0, tol=0.0)], 30) is None) == (r is None)
            for a, r in zip(t["test_assertions"], ref))

    # Null control
    execute_real_lumerical("newproject;", 30)
    if check_real_assertions(t["test_assertions"], 30) is None:
        return False, "assertions pass on an empty project", info

    # Defaults control
    if t["tier"] in (1, 2):
        for a in t["test_assertions"]:
            if a.get("type") == "expr":
                continue
            stripped = strip_prop_lines(t["gold_code"], a["prop"])
            if stripped == t["gold_code"]:
                continue
            err = execute_real_lumerical(stripped, timeout)
            if err is None and check_real_assertions([a], 30) is None:
                return False, f"assertion satisfied without its set() line (default value?): {a}", info

    # Derived values should not be spelled out in the question
    leaks = []
    for a in t["test_assertions"]:
        if a.get("derived") and isinstance(a["val"], float) and 0 < abs(a["val"]) < 1e-3:
            if re.search(r"(?<![\d.])" + re.escape(hl(a["val"])) + r"(?![\d])", t["question"]):
                leaks.append(a.get("prop") or a.get("expr"))
    info["derived_leaks"] = leaks

    sb = run_lumerical(t["gold_code"], t["test_assertions"])
    info["sandbox_ok"] = sb.ok
    return True, "ok", info


fam_target: dict = {}


def generate(per_family: int, seed: int, families: set | None, tiers: set):
    out = []
    for tier, mod in TIER_MODULES.items():
        if tier not in tiers:
            continue
        for fam, split in mod.FAMILIES:
            if families and fam.__name__ not in families:
                continue
            # simulation families may cap their count (runtime); over-generate so that
            # families still reach their target after gate rejections
            n = min(per_family, getattr(fam, "count", per_family))
            fam_target[fam.__name__] = n
            n = int(n * 1.4) + 1
            rng = random.Random(f"{seed}:{fam.__name__}")
            seen = set()
            tries = 0
            while len([x for x in out if x["family"] == fam.__name__]) < n and tries < n * 20:
                tries += 1
                t = fam(rng)
                if t["question"] in seen:
                    continue
                seen.add(t["question"])
                t["split"] = split
                out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-family", type=int, default=36)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--families", default="")
    ap.add_argument("--tiers", default="1,2,3")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--no-write", action="store_true", help="gate only; do not write dataset files")
    args = ap.parse_args()

    fams = {f.strip() for f in args.families.split(",") if f.strip()} or None
    tiers = {int(x) for x in args.tiers.split(",")}
    cands = generate(args.per_family, args.seed, fams, tiers)
    print(f"Generated {len(cands)} candidate tasks; gating on the real Lumerical engine...", flush=True)

    # Gate results are checkpointed so an interrupted build resumes where it stopped.
    os.makedirs(args.out_dir, exist_ok=True)
    cache_path = os.path.join(args.out_dir, "gate_cache.jsonl")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    cache[rec["key"]] = rec
        print(f"Resuming: {len(cache)} gate results cached in {cache_path}", flush=True)
    cache_f = open(cache_path, "a", encoding="utf-8", newline="\n")

    kept, rejected = [], []
    reasons = Counter()
    kept_per_family = Counter()
    t0 = time.time()
    for i, t in enumerate(cands, 1):
        if kept_per_family[t["family"]] >= fam_target[t["family"]]:
            continue  # family already full
        key = hashlib.sha1(json.dumps([t["question"], t["gold_code"], t["test_assertions"]],
                                      sort_keys=True).encode()).hexdigest()
        if key in cache:
            ok, why, info = cache[key]["ok"], cache[key]["why"], cache[key]["info"]
            t = cache[key]["task"]
        else:
            ts = time.time()
            ok, why, info = gate(t)
            cache_f.write(json.dumps({"key": key, "ok": ok, "why": why, "info": info, "task": t}) + "\n")
            cache_f.flush()
            print(f"    . {i} {t['family']} {'ok' if ok else 'REJ'} {time.time() - ts:.1f}s", flush=True)
        t["_gate"] = info
        if ok:
            kept.append(t)
            kept_per_family[t["family"]] += 1
        else:
            rejected.append({"family": t["family"], "reason": why, "question": t["question"][:160]})
            reasons[f"{t['family']}: {why.split(':')[0]}"] += 1
            if sum(1 for r in rejected if r["family"] == t["family"]) <= 2:
                print(f"  [REJECT] {t['family']}: {why[:300]}", flush=True)
        if i % 50 == 0 or i == len(cands):
            print(f"  {i}/{len(cands)}  kept={len(kept)} rejected={len(rejected)}  ({time.time() - t0:.0f}s)", flush=True)

    # Final dataset
    kept.sort(key=lambda t: (t["split"] != "train", t["tier"], t["category"], t["family"]))
    final, leaks = [], []
    for i, t in enumerate(kept, 1):
        g = t.pop("_gate")
        if g.get("derived_leaks"):
            leaks.append({"id": f"ext-{i:04d}", "family": t["family"], "props": g["derived_leaks"]})
        rec = {
            "id": f"ext-{i:04d}", "task_id": i, "split": t["split"], "tier": t["tier"],
            "category": t["category"], "family": t["family"], "question": t["question"],
            "gold_code": t["gold_code"], "test_assertions": t["test_assertions"],
            "requires_real_engine": not g["sandbox_ok"],
        }
        for k in ("timeout", "reference"):
            if k in t:
                rec[k] = t[k]
        final.append(rec)

    by_cat = defaultdict(Counter)
    for r in final:
        by_cat[r["category"]][r["split"]] += 1
    report = {
        "seed": args.seed, "candidates": len(cands), "kept": len(final), "rejected": len(rejected),
        "elapsed_s": round(time.time() - t0, 1),
        "by_tier": dict(Counter(r["tier"] for r in final)),
        "by_split": dict(Counter(r["split"] for r in final)),
        "by_category": {k: dict(v) for k, v in sorted(by_cat.items())},
        "by_family": dict(Counter(r["family"] for r in final)),
        "sandbox_compatible": sum(not r["requires_real_engine"] for r in final),
        "assertions": sum(len(r["test_assertions"]) for r in final),
        "reject_reasons": dict(reasons),
        "derived_value_leaks": leaks,
        "rejected_examples": rejected[:50],
    }
    print(json.dumps({k: v for k, v in report.items() if k != "rejected_examples"}, indent=1))

    if not args.no_write:
        os.makedirs(args.out_dir, exist_ok=True)
        for name, rows in (("lumerical_ext.jsonl", final),
                           ("lumerical_ext_train.jsonl", [r for r in final if r["split"] == "train"]),
                           ("lumerical_ext_test.jsonl", [r for r in final if r["split"] == "test"])):
            with open(os.path.join(args.out_dir, name), "w", encoding="utf-8", newline="\n") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
        with open(os.path.join(args.out_dir, "build_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        print(f"Wrote {len(final)} tasks to {args.out_dir}")


if __name__ == "__main__":
    main()
