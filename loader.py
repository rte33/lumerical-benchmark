"""Dataset loader for the Lumerical Scripting Language (.lsf) Benchmark."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
EXT_DIR = os.path.join(DATA_DIR, "extended")

_FILES = {
    "core": {"train": "lumerical_train.jsonl", "test": "lumerical_test.jsonl", "all": "lumerical.jsonl"},
    "extended": {"train": os.path.join("extended", "lumerical_ext_train.jsonl"),
                 "test": os.path.join("extended", "lumerical_ext_test.jsonl"),
                 "all": os.path.join("extended", "lumerical_ext.jsonl")},
}


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def load_dataset(split: str = "all", dataset: str = "core", tier: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load benchmark tasks.

    Args:
        split: 'train', 'test', or 'all'.
        dataset: 'core' (the original 160 tasks), 'extended' (generated tiers 1-3), or
            'combined' (both).
        tier: optional difficulty tier filter for extended tasks (1, 2 or 3). Core tasks
            count as tier 0.

    Returns:
        List of task dictionaries containing question, gold_code, test_assertions, etc.
    """
    split = split.lower().strip()
    if split == "both":
        split = "all"
    if split not in ("train", "test", "all"):
        raise ValueError(f"Unknown split '{split}'. Expected 'train', 'test', or 'all'.")
    dataset = dataset.lower().strip()
    if dataset == "combined":
        items = load_dataset(split, "core") + load_dataset(split, "extended")
    elif dataset in _FILES:
        path = os.path.join(DATA_DIR, _FILES[dataset][split])
        if os.path.exists(path):
            items = _read_jsonl(path)
        else:
            # Fall back to filtering the combined file of this dataset
            items = [t for t in _read_jsonl(os.path.join(DATA_DIR, _FILES[dataset]["all"]))
                     if split == "all" or t.get("split") == split]
    else:
        raise ValueError(f"Unknown dataset '{dataset}'. Expected 'core', 'extended', or 'combined'.")

    if tier is not None:
        items = [t for t in items if t.get("tier", 0) == tier]
    return items


def load_dataframe(split: str = "all", dataset: str = "core"):
    """Load benchmark tasks as a pandas DataFrame (requires pandas)."""
    import pandas as pd
    return pd.DataFrame(load_dataset(split, dataset))


if __name__ == "__main__":
    train_tasks = load_dataset("train")
    test_tasks = load_dataset("test")
    all_tasks = load_dataset("all")
    print(f"Loaded Lumerical Benchmark:")
    print(f"  Train tasks: {len(train_tasks)}")
    print(f"  Test tasks:  {len(test_tasks)}")
    print(f"  Total tasks: {len(all_tasks)}")
    if os.path.exists(os.path.join(EXT_DIR, "lumerical_ext.jsonl")):
        ext = load_dataset("all", "extended")
        print(f"  Extended tasks: {len(ext)} "
              f"(tier 1: {sum(t['tier'] == 1 for t in ext)}, tier 2: {sum(t['tier'] == 2 for t in ext)}, "
              f"tier 3: {sum(t['tier'] == 3 for t in ext)})")
    print(f"\nSample task (ID: {all_tasks[0]['id']}):")
    print(f"  Category: {all_tasks[0]['category']}")
    print(f"  Question: {all_tasks[0]['question']}")
