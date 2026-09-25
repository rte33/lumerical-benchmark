"""Verification script: run every gold solution and check its assertions.

Supports:
1. Fast offline verification via headless simulator:
   python verify.py
2. Live verification in real Ansys Lumerical FDTD software:
   python verify.py --engine real
3. The extended (generated) dataset, optionally one tier at a time:
   python verify.py --engine real --dataset extended --tier 2

Extended tasks marked `requires_real_engine` are skipped by the sandbox engine.
"""
from __future__ import annotations

import argparse
import sys
import time

from executor import run_lumerical, run_real_lumerical
from loader import load_dataset


def main():
    parser = argparse.ArgumentParser(description="Verify Lumerical Benchmark tasks.")
    parser.add_argument(
        "--engine",
        choices=["sandbox", "real"],
        default="sandbox",
        help="Execution engine: 'sandbox' (default, offline AST) or 'real' (live Ansys Lumerical FDTD).",
    )
    parser.add_argument(
        "--split",
        choices=["train", "test", "all"],
        default="all",
        help="Dataset split to evaluate (default: 'all').",
    )
    parser.add_argument(
        "--dataset",
        choices=["core", "extended", "combined"],
        default="core",
        help="'core' (original 160 tasks, default), 'extended' (generated tiers 1-3) or 'combined'.",
    )
    parser.add_argument("--tier", type=int, choices=[0, 1, 2, 3], default=None,
                        help="Only verify tasks of this tier (core tasks are tier 0).")
    args = parser.parse_args()

    tasks = load_dataset(args.split, args.dataset, args.tier)
    print(f"=== Lumerical Benchmark Verification ===")
    print(f"Dataset: {args.dataset}  Split: {args.split}  ({len(tasks)} tasks)")
    print(f"Engine:  {args.engine}\n")

    passed = 0
    failed = 0
    skipped = 0
    t0 = time.time()

    for idx, t in enumerate(tasks, start=1):
        task_id = t["id"]
        cat = t["category"]
        gold = t["gold_code"]
        assertions = t.get("test_assertions", [])

        if args.engine == "real":
            res = run_real_lumerical(gold, assertions, timeout=t.get("timeout", 30))
        elif t.get("requires_real_engine"):
            skipped += 1
            res = None
        else:
            res = run_lumerical(gold, assertions)

        if res is None:
            pass
        elif res.ok:
            passed += 1
        else:
            failed += 1
            print(f"  [FAIL] {task_id} ({cat}): {res.error}")

        if idx % 50 == 0 or idx == len(tasks):
            print(f"  Progress: {idx}/{len(tasks)} (Passed: {passed}, Failed: {failed}, Skipped: {skipped})",
                  flush=True)

    elapsed = time.time() - t0
    print(f"\n==========================================")
    print(f"Results: {passed} passed, {failed} failed" + (f", {skipped} skipped (need real engine)" if skipped else "")
          + f" in {elapsed:.2f}s")
    print(f"Engine:  {args.engine}")
    print(f"==========================================")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
