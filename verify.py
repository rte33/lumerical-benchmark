"""Verification script to test all 160 benchmark tasks.

Supports:
1. Fast offline verification via headless simulator:
   python verify.py
2. Live verification in real Ansys Lumerical FDTD software:
   python verify.py --engine real
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
    args = parser.parse_args()

    tasks = load_dataset(args.split)
    print(f"=== Lumerical Benchmark Verification ===")
    print(f"Split:  {args.split} ({len(tasks)} tasks)")
    print(f"Engine: {args.engine}\n")

    passed = 0
    failed = 0
    t0 = time.time()

    for idx, t in enumerate(tasks, start=1):
        task_id = t["id"]
        cat = t["category"]
        gold = t["gold_code"]
        assertions = t.get("test_assertions", [])

        if args.engine == "real":
            res = run_real_lumerical(gold, assertions)
        else:
            res = run_lumerical(gold, assertions)

        if res.ok:
            passed += 1
        else:
            failed += 1
            print(f"  [FAIL] {task_id} ({cat}): {res.error}")

        if idx % 20 == 0 or idx == len(tasks):
            print(f"  Progress: {idx}/{len(tasks)} verified (Passed: {passed}, Failed: {failed})")

    elapsed = time.time() - t0
    print(f"\n==========================================")
    print(f"Results: {passed} passed, {failed} failed in {elapsed:.2f}s")
    print(f"Engine:  {args.engine}")
    print(f"==========================================")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
