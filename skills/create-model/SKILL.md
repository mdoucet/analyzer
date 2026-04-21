---
name: create-model
description: >
  Generate a refl1d analyzer-convention model script. Two modes:
  (A) convert an existing AuRE problem JSON, or
  (B) generate directly via LLM from a sample description and one or more
  REF_L data files. Mode B auto-detects which of the three fitting cases
  applies: single combined file (case 1), multiple partial files from one
  measurement (case 2), or multiple combined files co-refined (case 3 — not
  supported by AuRE, only by this tool).
  USE FOR: creating a new model file; adapting a hand-written model for
  co-refinement of multiple measurements.
  DO NOT USE FOR: running fits (see fitting skill) or adjusting an existing
  model's parameter ranges (edit the script directly).
---

# create-model

## When to use

- You have a **natural-language description** of a sample and one or more
  REF_L data files, and want a model script ready for `run-fit`.
- You already have an **AuRE problem JSON** (from `aure prepare` / `aure batch`)
  and want to convert it to an analyzer-convention script.

## The three cases

`create-model` in Mode B auto-detects the case from the data file names:

| Case | Input files | Probe | Output shape |
|------|-------------|-------|--------------|
| 1 | One `REFL_{set}_combined_data_auto.txt` | `QProbe` (Q, dQ) | `create_fit_experiment` + `FitProblem(experiment)` |
| 2 | N `REFL_{set}_{part}_{run}_partial.txt` files sharing one `set_id` | `make_probe` per segment (θ, dT, λ, dL) | `create_sample()` + `create_probe()` + single `FitProblem(experiment)` with shared sample across probes |
| 3 | N `REFL_{set_k}_combined_data_auto.txt` files with different `set_id`s | `QProbe` each | N experiments, constraint lines tying shared parameters, `FitProblem([experiment, experiment2, ...])` |

Case 3 is **not supported by AuRE** — only by `create-model` Mode B.

## Modes

### Mode A — convert an AuRE problem JSON

```bash
create-model path/to/problem.json --out models/cu_thf.py
```

Accepts either an AuRE `ModelDefinition` JSON (keys `substrate`/`ambient`/
`layers`/`intensity`/`dq_is_fwhm`) or a bumps `problem.json` (schema
`bumps-draft-03`). Only produces case-1 or case-2 scripts, depending on what
AuRE emitted.

### Mode B — generate via LLM

```bash
create-model \
  --describe "2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O" \
  --data data/REFL_226642_combined_data_auto.txt \
  --data data/REFL_226652_combined_data_auto.txt \
  --out models/Cu-D2O-corefine.py \
  --model-name corefine_226642_226652
```

`--data` is repeatable. The case is detected from the file names; you do not
need to specify it. The LLM provider and model come from `.env` (`LLM_PROVIDER`,
`LLM_MODEL`, `LLM_BASE_URL`, …) via `aure.llm`.

### Driving options from a file

Either mode accepts `--config FILE` (YAML or JSON). Two shapes are supported.

#### Flat (single job)

Top-level keys. Command-line flags override config values. Relative paths
are resolved against the **config file's directory**.

| Key | Aliases | Meaning |
|---|---|---|
| `describe` | `description`, `sample_description` | Mode B: sample description text |
| `data` | `data_files` | Mode B: list of REF_L data files |
| `data_file` | — | Mode B: single extra data file, prepended to `data` |
| `source` | — | Mode A: path to problem JSON |
| `out` | — | Output script path |
| `model_name` | `name` | Name used in docstring and default filename |

```yaml
# model-creation.yaml  (flat)
describe: |
  2 nm copper oxide on 50 nm copper on 3 nm Ti on silicon.
  The ambient medium is D2O (SLD about 6).
  Neutrons enter from the silicon substrate side.
data:
  - Rawdata/REFL_226642_combined_data_auto.txt
  - Rawdata/REFL_226652_combined_data_auto.txt
out: Models/Cu-D2O-corefine.py
model_name: corefine_226642_226652
```

```bash
create-model --config model-creation.yaml
```

#### Jobs list (batch)

To generate several scripts in one call, use a top-level `jobs:` list. Each
entry is one create-model invocation. This shape mirrors the AuRE
`aure batch` manifest so you can reuse an existing file, but **only the keys
listed above are read** — AuRE-specific settings (`fit_method`, `fit_steps`,
`llm_*`, `command`, …) are ignored.

```yaml
# model-creation.yaml  (jobs)
defaults:
  output_root: ./Models    # default directory for per-job output files

jobs:
  - name: copper_oxide     # → Models/copper_oxide.py
    sample_description: >-
      2 nm copper oxide on 50 nm copper on 3 nm Ti on silicon
      in D2O (SLD ~6). Neutrons enter from the silicon side.
    data_file: Rawdata/REFL_226642_1_226642_partial.txt
    data_files:
      - Rawdata/REFL_226642_2_226643_partial.txt
      - Rawdata/REFL_226642_3_226644_partial.txt

  - name: corefine_226642_226652
    description: 2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O
    data:
      - Rawdata/REFL_226642_combined_data_auto.txt
      - Rawdata/REFL_226652_combined_data_auto.txt
    out: Models/Cu-D2O-corefine.py   # overrides defaults.output_root
```

Rules for the jobs form:

- Each job must be **either** Mode A (`source:`) **or** Mode B
  (`describe` + data files); mixing the two in one entry is an error.
- Output path: explicit `out:` wins; otherwise `<defaults.output_root>/<name>.py`
  is used (resolved relative to the config file).
- Do not pass `SOURCE`/`--describe`/`--data`/`--out` on the command line when
  `--config` has a `jobs:` list.
- `defaults.output_root` is the only field read from `defaults:`. Everything
  else there is ignored.

## What the LLM must return

The LLM is constrained to reply with a single JSON object of this shape —
`create-model` converts it into the Python script itself, so free-form LLM
Python is never executed:

```json
{
  "ambient":   {"name": "D2O", "sld": 6.19,
                "sld_min": 5.19, "sld_max": 7.19,
                "roughness_min": 1.0, "roughness_max": 25.0},
  "substrate": {"name": "Si",  "sld": 2.07,
                "roughness_min": 0.0, "roughness_max": 15.0},
  "layers": [
    {"name": "CuOx", "sld": 5.0,  "thickness": 30.0,  "roughness": 10.0,
     "thickness_min": 5.0,   "thickness_max": 200.0,
     "sld_min": 3.0,         "sld_max": 7.0,
     "roughness_min": 5.0,   "roughness_max": 30.0},
    {"name": "Cu",   "sld": 6.4,  "thickness": 500.0, "roughness": 5.0, "...": "..."},
    {"name": "Ti",   "sld": -1.95,"thickness": 35.0,  "roughness": 5.0, "...": "..."}
  ],
  "intensity":        {"value": 1.0, "min": 0.95, "max": 1.05},
  "back_reflection":  false,
  "shared_parameters": [
    "Cu.material.rho", "Cu.interface",
    "Ti.thickness", "Ti.material.rho", "Ti.interface"
  ]
}
```

Key rules:

- `layers` goes **ambient-adjacent → substrate-adjacent** (top-to-bottom).
  Do **not** include the ambient or substrate inside `layers`.
- SLD bounds: at least ±2 × 10⁻⁶ Å⁻² around nominal. Adhesion layers (Ti):
  ±3 or wider.
- Roughness ≥ 5 Å and typically ≤ 30 Å; must be less than half the thinnest
  adjacent layer.
- Minimum layer thickness: 5 Å.
- Never vary the substrate SLD.
- Do **not** add a native SiO₂ on Si unless the user description says so.

On parse or validation failure, `create-model` retries the LLM once with the
error message appended, then aborts.

## Case-3 `shared_parameters`

Case 3 is the reason `create-model` exists: AuRE cannot co-refine multiple
combined files with flexible inter-experiment constraints. Provide the list
of dotted attribute paths to tie across all experiments. Sensible defaults:

- Share **structural** parameters of buried layers (Ti and Cu thickness / SLD
  / interface; adhesion layer roughness).
- Do **not** share `intensity` (each experiment has its own probe) or the
  ambient SLD (solvent can differ between runs).
- If a layer's properties genuinely differ between measurements (e.g. an
  oxide that grows), leave it **off** the shared list.

Each entry must match ``LayerName.{material.rho|thickness|interface}``.
The renderer emits one line per constraint per non-first experiment:

```python
experiment2.sample["Cu"].material.rho = experiment.sample["Cu"].material.rho
```

## Generated script templates (excerpt)

### Case 1

```python
def create_fit_experiment(q, dq, data, errors):
    dq = dq / 2.355
    probe = QProbe(q, dq, data=(data, errors))
    probe.intensity = Parameter(value=1.0, name="intensity")
    probe.intensity.range(0.95, 1.05)
    ...
    sample = D2O(0, 10) | CuOx(30, 10) | Cu(500, 5) | Ti(35, 5) | Si
    experiment = Experiment(probe=probe, sample=sample)
    sample["Cu"].thickness.range(250, 1000)
    ...
    return experiment

data_file = "…/REFL_226642_combined_data_auto.txt"
_refl = np.loadtxt(data_file).T
experiment = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])
problem = FitProblem(experiment)
```

### Case 2

```python
def create_probe(data_file, theta):
    q, data, errors, dq = np.loadtxt(data_file).T
    wl = 4*np.pi*np.sin(np.pi/180*theta)/q
    dT = dq/q * np.tan(np.pi/180*theta) * 180/np.pi
    probe = make_probe(T=theta, dT=dT, L=wl, dL=0*q,
                       data=(data, errors),
                       radiation="neutron", resolution="uniform")
    ...

def create_sample():
    ...

sample = create_sample()
probe1 = create_probe(data_file1, theta=0.45)
probe2 = create_probe(data_file2, theta=1.2)
probe3 = create_probe(data_file3, theta=3.5)

experiment = Experiment(probe=probe1, sample=sample)
experiment2 = Experiment(probe=probe2, sample=sample)
experiment3 = Experiment(probe=probe3, sample=sample)

problem = FitProblem(experiment)
```

### Case 3

```python
def create_fit_experiment(q, dq, data, errors):
    ...  # builds an INDEPENDENT sample for each call

_refl = np.loadtxt(data_file1).T
experiment  = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])
_refl = np.loadtxt(data_file2).T
experiment2 = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])

# Shared structural parameters
experiment2.sample["Cu"].material.rho = experiment.sample["Cu"].material.rho
experiment2.sample["Cu"].interface    = experiment.sample["Cu"].interface
experiment2.sample["Ti"].thickness    = experiment.sample["Ti"].thickness
experiment2.sample["Ti"].material.rho = experiment.sample["Ti"].material.rho
experiment2.sample["Ti"].interface    = experiment.sample["Ti"].interface

problem = FitProblem([experiment, experiment2])
```

## See also

- [models skill](../models/SKILL.md) — anatomy of a model file, adjusting
  parameter ranges.
- [reflectometry-basics skill](../reflectometry-basics/SKILL.md) — domain
  rules the LLM is instructed to follow.
- [fitting skill](../fitting/SKILL.md) — how to run the generated script.
