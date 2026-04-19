---
name: neutron-reflectometry-analyzer
description: >
  Neutron reflectometry analysis using the analyzer-tools package (refl1d/bumps).
  USE FOR: fitting reflectivity data, assessing fit quality, evaluating partial data
  overlap, computing theta offsets, creating or adjusting models, time-resolved
  neutron reflectometry, data packaging.
  DO NOT USE FOR: general Python questions unrelated to reflectometry.
argument-hint: 'Describe what you want to analyze (e.g., "fit set 218281 with cu_thf model")'
---

# Neutron Reflectometry Analyzer

Provides CLI tools for neutron reflectometry data analysis built on
[refl1d](https://refl1d.readthedocs.io) and
[bumps](https://bumps.readthedocs.io). Install with:

```bash
pip install -e /path/to/analyzer
```

Verify installation:

```bash
analyzer-tools --help
```

---

## Data Conventions

### Directory layout (configured in `config.ini`)

| Directory | Default | Contents |
|-----------|---------|----------|
| Combined data | `data/combined/` | Final reflectivity curves |
| Partial data | `data/partial/` | Individual partial curves (3 per set) |
| Models | `models/` | Python model files for refl1d |
| Results | `results/` | Fit outputs |
| Reports | `reports/` | Markdown reports with plots |

### File naming

- **Combined**: `REFL_{set_id}_combined_data_auto.txt`
- **Partial**: `REFL_{set_id}_{part_id}_{run_id}_partial.txt` (part_id = 1–3)

### Column format (all data files)

| Column | Symbol | Description |
|--------|--------|-------------|
| 1 | Q | Momentum transfer (1/Å) |
| 2 | R | Reflectivity |
| 3 | dR | Uncertainty on R |
| 4 | dQ | Q resolution (FWHM, 1/Å) |

---

## CLI Tools Reference

### Fitting workflow

#### 1. `run-fit` — Fit combined data to a model

```bash
run-fit <SET_ID> <MODEL_NAME>
```

Loads `REFL_{SET_ID}_combined_data_auto.txt`, runs DREAM MCMC (10k samples,
5k burn-in), saves results to `results/{SET_ID}_{MODEL_NAME}/`.

#### 2. `assess-result` — Evaluate fit quality

```bash
assess-result <RESULTS_DIR> <SET_ID> <MODEL_NAME>
```

Generates reflectivity plot, SLD profile with 90% CL uncertainty bands,
parameter table, and markdown report in `reports/`.

**Chi-squared quality thresholds:**

| χ² | Quality | Action |
|----|---------|--------|
| < 2 | Excellent | Review uncertainties |
| 2–3 | Good | Check residual patterns |
| 3–5 | Acceptable | Consider adjusting model |
| > 5 | Poor | Revise model |

#### 3. `create-model` — Generate standalone fit script

```bash
create-model <MODEL_NAME> <DATA_FILE>
```

### Model adjustment

#### `create-temporary-model` — Adjust parameter ranges

```bash
create-temporary-model <BASE_MODEL> <NEW_MODEL> --adjust '<LAYER> <PARAM> <MIN>,<MAX>'
```

Example:
```bash
create-temporary-model cu_thf cu_thf_wide --adjust 'Cu thickness 300,1200'
```

### Partial data

#### `assess-partial` — Check overlap quality before combining

```bash
assess-partial <SET_ID>
```

Calculates overlap χ² between adjacent parts. Thresholds: < 1.5 good,
1.5–3.0 acceptable, > 3.0 investigate.

### Theta offsets

#### `theta-offset` — Compute angular offsets from NeXus event files

```bash
theta-offset <NEXUS_FILE> --db <DIRECT_BEAM_FILE>
```

Also computes the gravity-induced angular offset at the mean neutron wavelength.

### Time-resolved / EIS

#### `eis-intervals` — Extract EIS step intervals

```bash
eis-intervals <EIS_DATA_FILE>
```

#### `eis-reduce-events` — Reduce neutron events for time-resolved analysis

```bash
eis-reduce-events <EVENT_FILE> --intervals <INTERVALS_JSON>
```

### Data packaging

#### `iceberg-packager` — Package time-resolved data as Iceberg/Parquet

```bash
iceberg-packager <DATA_DIR> --output <OUTPUT_DIR>
```

### Batch processing

#### `analyzer-batch` — Run multiple operations from a manifest

```bash
analyzer-batch <MANIFEST_FILE>
```

---

## Standard Fitting Workflow

```
run-fit <SET_ID> <MODEL>
    │
    ▼
assess-result results/<SET_ID>_<MODEL> <SET_ID> <MODEL>
    │  → plots, parameter table, markdown report
    ▼
┌─ χ² acceptable? ─────────────────────┐
│  Yes → record in analysis notes       │
│  No  → adjust model and re-fit:       │
│        create-temporary-model + run-fit│
└───────────────────────────────────────┘
```

### Complete example

```bash
# 1. Fit
run-fit 218281 cu_thf

# 2. Assess
assess-result results/218281_cu_thf 218281 cu_thf
# → reports/report_218281.md shows χ² = 6.2 (poor)

# 3. Widen parameter range
create-temporary-model cu_thf cu_thf_wide --adjust 'material thickness 10,300'

# 4. Re-fit and re-assess
run-fit 218281 cu_thf_wide
assess-result results/218281_cu_thf_wide 218281 cu_thf_wide
# → χ² = 1.8 (excellent)
```

---

## Model Files

Model files live in `models/` and define a `create_fit_experiment(q, dq, data, errors)` function
that returns a `refl1d.experiment.Experiment`. Layers are stacked top-to-bottom:

```python
sample = THF(0, 11.4) | material(58, 13) | Cu(505, 4.6) | Ti(39.5, 9.1) | Si
#        ambient         layers...                                          substrate
```

Parameters are constrained with `.range(min, max)`.

---

## LLM-Powered Evaluation (optional)

If [AuRE](https://github.com/neutrons-ai/aure) is installed (`pip install -e /path/to/aure`),
run `aure evaluate` after `assess-result` for intelligent assessment:

```bash
aure evaluate results/<SET_ID>_<MODEL> \
  --context "<sample description>" --json
```

Returns structured verdict with `acceptable`, `issues`, `suggestions`, and
`physical_concerns`. See AuRE documentation for LLM configuration.

---

## Notes

- All analysis results should be recorded in `docs/analysis_notes.md`
- The fitting algorithm is bumps DREAM (Differential Evolution Adaptive Metropolis)
- SLD profile uncertainty bands represent 90% confidence intervals
- Data column order is Q, R, dR, dQ but model function signature is `(q, dq, data, errors)`
