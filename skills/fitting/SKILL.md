---
name: fitting
description: >
  Reflectivity fitting workflow — generate a model, run fits, and evaluate
  the result (assess-result + AuRE LLM evaluation).
  USE FOR: fitting combined data, evaluating fit quality, iterating on a model.
  DO NOT USE FOR: partial data quality checks (see partial-assessment skill),
  data reduction (see time-resolved skill), or end-to-end pipelines for a
  single sample (see pipeline skill — `analyze-sample`).
---

# Reflectivity Fitting Workflow

## Overview

The standard single-fit workflow is:

1. **`create-model`** — Generate an analyzer-convention refl1d script from an
   AuRE `ModelDefinition` JSON **or** from a plain-English sample description.
2. **`run-fit`** — Fit combined data to the model (wraps `aure analyze`).
3. **`assess-result`** — Generate plots, parameter tables, and a markdown
   report; automatically appends an `## LLM Evaluation (AuRE)` section when
   AuRE is installed.

For an end-to-end single-sample pipeline (partial checks → reduction gate →
fit → evaluate), use **`analyze-sample`** instead. See the `pipeline` skill.

## Step 1: Create a Model

### From a sample description (preferred)

```bash
create-model "Cu/Ti bilayer on Si in deuterated THF. Expected 50 Å Cu on 20 Å CuOx." \
             data/combined/REFL_218281_combined_data_auto.txt \
             --out models/cu_thf.py
```

Shells out to `aure analyze -m 0` to produce a `ModelDefinition` and converts
it to an analyzer-convention script with
`create_fit_experiment(q, dq, data, errors)`.

### From an existing `ModelDefinition` JSON

```bash
create-model path/to/NNN_model_initial.json --out models/cu_thf.py
```

## Step 2: Run a Fit

```bash
run-fit <SET_ID> [MODEL_NAME] [options]
```

By default this calls `aure analyze` with the configured sample description.
Use `--legacy` to run the old analyzer fitter.

**Examples:**

```bash
# Preferred: AuRE-driven fit from a sample description
run-fit 218281 -d sample_218281.md

# Legacy: fit a fixed model script
run-fit 218281 cu_thf --legacy
```

### What it does (AuRE mode)

1. Reads the sample description (YAML frontmatter + markdown body, or plain text).
2. Invokes `aure analyze <data_file> -o <results_dir> -m <max-refinements>`.
3. Writes results to `results/<SET_ID>_<MODEL>/` including `problem.json`
   (used by `aure evaluate`).

### Important: data column convention

The data file columns are `Q, R, dR, dQ`; model functions take
`create_fit_experiment(q, dq, data, errors)`. Generated scripts handle the
mapping — no manual swap needed.

### Output files

| File | Contents |
|------|----------|
| `problem.par` | Fitted parameter values |
| `problem-err.json` | Parameter uncertainties |
| `problem.json` | FitProblem definition (required by `aure evaluate`) |
| `problem.out` | Overall fit statistics |
| `*-refl.dat` | Reflectivity data with calculated fit values |

## Step 3: Assess the Result

```bash
assess-result <RESULTS_DIR> <SET_ID> <MODEL_NAME> [options]
```

**Example:**
```bash
assess-result results/218281_cu_thf 218281 cu_thf \
  --context "Cu/Ti bilayer on Si in deuterated THF"
```

### What it does

1. Reads fit output files.
2. Extracts χ², parameter values, and uncertainties.
3. Generates reflectivity plot (data vs fit) and SLD profile with 90% CL bands.
4. Writes the markdown report.
5. **Automatically runs `aure evaluate` when available** and appends an
   `## LLM Evaluation (AuRE)` section with verdict, issues, suggestions, and
   physical-plausibility concerns. Pass `--skip-aure-eval` to disable.

### Output files

| File | Contents |
|------|----------|
| `report_{SET_ID}.md` | Markdown report with fit quality, parameter table, plots, and LLM evaluation |
| `fit_result_{SET_ID}_{MODEL}_reflectivity.svg` | R vs Q plot |
| `fit_result_{SET_ID}_{MODEL}_profile.svg` | SLD profile with uncertainty band |
| `sld_uncertainty_{SET_ID}_{MODEL}.txt` | SLD profile numerical data |

### Chi-squared quality thresholds

| χ² range | Assessment | Recommended action |
|----------|------------|-------------------|
| < 2.0 | Excellent | Review parameter uncertainties |
| 2.0 – 3.0 | Good | Check for systematic residual patterns |
| 3.0 – 5.0 | Acceptable | Consider adjusting model |
| > 5.0 | Poor | Model likely needs revision |

### AuRE LLM evaluation fields

The appended `## LLM Evaluation (AuRE)` section contains:

| Field | Meaning |
|-------|---------|
| `verdict` / `acceptable` | Overall assessment |
| `issues` | Concrete problems (boundary hits, residual structure, …) |
| `suggestions` | Actionable next steps |
| `physical_concerns` | Parameters that are physically implausible |

To run the evaluation manually:

```bash
aure evaluate results/218281_cu_thf \
  --context "Cu/Ti bilayer on Si in deuterated THF" --json
```

LLM configuration for AuRE: set `OPENAI_API_KEY` or configure
`aure_config.yaml`; verify with `aure check-llm`.

## Step 4: Iterate if Needed

If the fit is poor or the AuRE evaluation is negative:

- **Edit the model description** and re-run `create-model` → `run-fit` → `assess-result`.
- Or edit `models/<name>.py` directly (change layer structure or parameter
  `.range(...)` bounds) and re-fit.

Common adjustments suggested by AuRE:

| Suggestion | Response |
|------------|----------|
| "Parameter X at upper bound" | Widen that parameter's range in the model file |
| "Consider adding interface roughness" | Add an `interface.range(...)` call on the layer |
| "Residual fringes suggest unmodeled layer" | Add a layer to the model |
| "High-Q residual structure" | Check `dQ` resolution and background |

## Complete Workflow Example

```bash
# 1. Generate a model from a description
create-model "Cu/Ti bilayer on Si in deuterated THF" \
             data/combined/REFL_218281_combined_data_auto.txt \
             --out models/cu_thf.py

# 2. Fit
run-fit 218281 cu_thf

# 3. Assess (also runs aure evaluate)
assess-result results/218281_cu_thf 218281 cu_thf \
  --context "Cu/Ti bilayer on Si in deuterated THF"
# → reports/report_218281.md with χ², plots, parameter table, LLM verdict
```

## Notes

- All analysis results should be recorded in `docs/analysis_notes.md`.
- The fitting algorithm is Bumps DREAM (Differential Evolution Adaptive Metropolis).
- MCMC samples provide parameter uncertainty estimates.
- SLD profile uncertainty bands represent 90% confidence intervals.
- For end-to-end sample analysis with reduction-issue gating, use
  **`analyze-sample`** (see the `pipeline` skill).
