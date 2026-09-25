"""Dataset loader for the Lumerical Scripting Language (.lsf) Benchmark."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_dataset(split: str = "all") -> List[Dict[str, Any]]:
    """Load benchmark tasks for a given split ('train', 'test', or 'all').
    
    Args:
        split: 'train' (80 tasks), 'test' (80 tasks), or 'all' (160 tasks).
        
    Returns:
        List of task dictionaries containing question, gold_code, test_assertions, etc.
    """
    split = split.lower().strip()
    if split == "train":
        filename = "lumerical_train.jsonl"
    elif split == "test":
        filename = "lumerical_test.jsonl"
    elif split in ("all", "both"):
        filename = "lumerical.jsonl"
    else:
        raise ValueError(f"Unknown split '{split}'. Expected 'train', 'test', or 'all'.")

    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        # Fallback to loading and filtering lumerical.jsonl
        path = os.path.join(DATA_DIR, "lumerical.jsonl")
        items = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    if split == "all" or item.get("split") == split:
                        items.append(item)
        return items

    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def load_dataframe(split: str = "all"):
    """Load benchmark tasks as a pandas DataFrame (requires pandas)."""
    import pandas as pd
    return pd.DataFrame(load_dataset(split))


if __name__ == "__main__":
    train_tasks = load_dataset("train")
    test_tasks = load_dataset("test")
    all_tasks = load_dataset("all")
    print(f"Loaded Lumerical Benchmark:")
    print(f"  Train tasks: {len(train_tasks)}")
    print(f"  Test tasks:  {len(test_tasks)}")
    print(f"  Total tasks: {len(all_tasks)}")
    print(f"\nSample task (ID: {all_tasks[0]['id']}):")
    print(f"  Category: {all_tasks[0]['category']}")
    print(f"  Question: {all_tasks[0]['question']}")
