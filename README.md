# Lumerical Benchmark: Ansys Lumerical Scripting Language (.lsf) Benchmark for LLMs

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tasks: 160](https://img.shields.io/badge/tasks-160%20verified-green.svg)](data/lumerical.jsonl)
[![Ansys Lumerical](https://img.shields.io/badge/Ansys-Lumerical%20FDTD-orange.svg)](https://www.ansys.com/products/optics/fdtd)

An open benchmark dataset and execution harness for evaluating Large Language Models on **Ansys Lumerical Scripting Language (`.lsf`)** for Photonic Integrated Circuit (PIC) layout and FDTD simulation automation.

Every single task in this benchmark has been validated against both a **zero-dependency headless CAD simulator** and the **actual Ansys Lumerical FDTD software** via the official Python automation API (`lumapi`).

---

## 📌 Motivation

Standard code generation benchmarks (e.g., HumanEval/MBPP for Python, Spider for SQL) evaluate general-purpose programming languages where modern frontier models enjoy immense pre-training density. When models fail on those tasks, errors are overwhelmingly semantic/logical, where syntax error feedback has limited utility.

**Ansys Lumerical Scripting Language (`.lsf`)** represents a high-impact, low-resource domain-specific language (DSL) in computational electromagnetics and silicon photonics:
1. **Low Pre-training Density**: LLMs frequently hallucinate Python constructs (`def`, `import`), confuse spatial properties (`width` vs `y span`), or miss CAD object hierarchies.
2. **Sharp Diagnostic Feedback**: The CAD interpreter returns explicit, deterministic error signatures (e.g. unknown property, object not found, inactive property).
3. **Realistic Photonic Engineering**: Tasks cover the complete device development lifecycle—waveguides, couplers, resonators, material stacks, monitors, ports, and boundary conditions.

---

## 📊 Dataset Structure & Zero-Leakage Split

The benchmark contains **160 tasks** split strictly across device / functional categories into **80 Train** and **80 Test** tasks. 

To prevent cross-split contamination and prevent memorization of geometric dimensions, the functional categories are mutually exclusive:

| Split | Category | Tasks | Key Photonic Devices & Operations |
|---|---|---|---|
| **Train** | `waveguides_and_tapers` | 20 | Strip, rib, slot waveguides, linear tapers, substrate buffers (`addrect`, `set`) |
| **Train** | `splitters_and_couplers` | 20 | Directional couplers, Y-branches, MMI 1x2 couplers, waveguide crossings |
| **Train** | `monitors_and_detection` | 20 | Frequency-domain power monitors, refractive index monitors, time probes (`addpower`, `addindex`, `addtime`) |
| **Train** | `materials_and_stacks` | 20 | Dielectric bilayers, DBR stacks, anti-reflective coatings, metallic contacts |
| **Test** | `cavities_and_resonators` | 20 | Micro-ring resonators, disk resonators, Bragg grating corrugations (`addring`, `addcircle`) |
| **Test** | `sources_and_illumination` | 20 | Electric/magnetic dipoles, plane waves, mode sources (`adddipole`, `addplane`, `addmode`) |
| **Test** | `solver_and_meshing` | 20 | 2D/3D FDTD simulation regions, boundary conditions (PML, Periodic, Metal), mesh overrides (`addfdtd`, `addmesh`) |
| **Test** | `analysis_groups_and_metrics` | 20 | 4-monitor enclosing boxes, reflection/transmission pairs, 2D field profile slices (`addprofile`) |

- **Total Tasks**: 160
- **Train Split**: 80 tasks (in `data/lumerical_train.jsonl`)
- **Test Split**: 80 tasks (in `data/lumerical_test.jsonl`)
- **Combined**: 160 tasks (in `data/lumerical.jsonl`)
- **Category Overlap**: 0%

---

## 🔍 Task Schema

Each entry is formatted as a single JSON object per line (`.jsonl`):

```json
{
  "id": "lum-001",
  "task_id": 1,
  "split": "train",
  "category": "waveguides_and_tapers",
  "question": "Write a Lumerical script to create a silicon strip waveguide along the X-axis: add a substrate named 'substrate' (index 1.44, x-span 14 um, y-span 4 um, z-span 2 um centered at z = -1 um) and a core named 'core' (material 'Si (Silicon) - Palik', x-span 10 um, y-span 400 nm, z-span 220 nm centered at z = 110 nm).",
  "gold_code": "newproject;\naddrect;\nset(\"name\", \"substrate\");\nset(\"x\", 0); set(\"x span\", 14e-6);\nset(\"y\", 0); set(\"y span\", 4e-6);\nset(\"z\", -1e-6); set(\"z span\", 2e-6);\nset(\"index\", 1.44);\n\naddrect;\nset(\"name\", \"core\");\nset(\"x\", 0); set(\"x span\", 10e-6);\nset(\"y\", 0); set(\"y span\", 400e-9);\nset(\"z\", 110.0e-9); set(\"z span\", 220e-9);\nset(\"material\", \"Si (Silicon) - Palik\");\n",
  "test_assertions": [
    {"target": "substrate", "prop": "index", "val": 1.44},
    {"target": "core", "prop": "material", "val": "Si (Silicon) - Palik"},
    {"target": "core", "prop": "y span", "val": 4e-07, "tol": 1e-12},
    {"target": "core", "prop": "z span", "val": 2.2e-07, "tol": 1e-12}
  ]
}
```

---

## 🚀 Quickstart

### 1. Load the Dataset

No external dependencies are required to load the dataset:

```python
from loader import load_dataset

# Load test split (80 tasks)
test_tasks = load_dataset("test")

# Load train split (80 tasks)
train_tasks = load_dataset("train")

# Load all (160 tasks)
all_tasks = load_dataset("all")
```

If `pandas` is installed:
```python
from loader import load_dataframe

df = load_dataframe("test")
print(df[["id", "category", "question"]].head())
```

### 2. Verify and Grade Generated Scripts

Use the built-in grading harness to test model predictions or gold solutions:

```python
from executor import run_lumerical

script = """
newproject;
addrect;
set("name", "substrate");
set("x", 0); set("x span", 14e-6);
set("y", 0); set("y span", 4e-6);
set("z", -1e-6); set("z span", 2e-6);
set("index", 1.44);
"""

assertions = [
    {"target": "substrate", "prop": "index", "val": 1.44},
    {"target": "substrate", "prop": "x span", "val": 14e-6}
]

res = run_lumerical(script, test_assertions=assertions)
print("Passed?", res.ok)
if not res.ok:
    print("Error:", res.error)
```

---

## ⚡ Execution Engines

### A. Fast Headless Simulator (Default)
A lightweight, zero-dependency Python state machine that tracks CAD primitives, property mutations, materials, and active coordinate constraints.
- **Speed**: ~0.03 seconds for all 160 tasks.
- **License**: None required.
- **Use Case**: CI/CD testing, high-throughput LLM sampling, parallel evaluation.

```bash
python verify.py --engine sandbox
```

### B. Real Ansys Lumerical FDTD Engine
Automates an actual Ansys Lumerical installation via `lumapi`.
- **Accuracy**: 100% ground-truth CAD validation.
- **Requirements**: Installed Ansys Lumerical software (FDTD Solutions) and valid license.

```bash
python verify.py --engine real
```

*(Set `LUMERICAL_BIN` and `LUMERICAL_API` environment variables if installed in custom directories).*

---

## 📋 Citation & License

This dataset and benchmark code are released under the [MIT License](LICENSE).

```bibtex
@misc{lumerical_benchmark_2026,
  author = {Fardous Mahmud},
  title = {Lumerical Benchmark: Ansys Lumerical Scripting Language (.lsf) Benchmark for LLMs},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/rte33/lumerical-benchmark}}
}
```
