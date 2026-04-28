---
name: fitting
description: >
  Reflectivity fitting workflow — generate a model script, run a fit, and
  evaluate the result.
  USE FOR: fitting reflectivity data, evaluating fit quality, iterating on a model.
  DO NOT USE FOR: partial data quality checks (see partial-assessment skill),
  data reduction (see time-resolved skill), or end-to-end pipelines for a
  single sample (see pipeline skill — `analyze-sample`).
---

# Reflectivity Fitting Workflow

## Overview

The standard single-fit workflow is:

1. **`create-model`** — Generate a complete refl1d-ready Python script from
   either an AuRE `ModelDefinition` JSON (Mode A) or a YAML/JSON config
   describing each physical state (Mode B). The script defines a module-level
   `problem = FitProblem(...)` and loads its own data.
2. **`run-fit`** — Execute that script with `bumps.fitters.fit` and write fit
   output to `<results-dir>/<name>/`.
3. **`assess-result`** — Generate plots, parameter tables, and a markdown
   report; automatically appends an `## LLM Evaluation (AuRE)` section when
   AuRE is installed. (`run-fit` calls this automatically unless
   `--no-assess` is given.)

For an end-to-end single-sample pipeline (partial checks → reduction gate →
fit → evaluate), use **`analyze-sample`** instead. See the `pipeline` skill.

## Step 1: Create a Model Script

See the [create-model skill](../create-model/SKILL.md) for the full reference.
The output is always a self-contained script that can be passed straight to
`run-fit` (or executed directly with the `refl1d` CLI).

```bash
# Mode A — from an AuRE problem JSON
create-model path/to/NNN_model_initial.json --out models/cu_thf.py

# Mode B — from a YAML config that describes one or more states
create-model --config model-creation.yaml
```

## Step 2: Run a Fit

```bash
run-fit SCRIPT [options]
```

`SCRIPT` is the complete model script produced by `create-model` (or any
refl1d script that exposes `problem` at module level).

### Options

| Option | Default | Notes |
|---|---|---|
| `--results-dir DIR` | `$ANALYZER_RESULTS_DIR` | Parent dir for fit output. |
| `--reports-dir DIR` | `$ANALYZER_REPORTS_DIR` | Where the assessment report is written. |
| `--name NAME` | script stem | Output subfolder name and report tag. |
| `--fit FITTER` | `dream` | Bumps fitter (`dream`, `amoeba`, `lm`, `de`, `newton`). |
| `--samples N` | `10000` | DREAM samples (only with `--fit dream`). |
| `--burn N` | `5000` | DREAM burn-in (only with `--fit dream`). |
| `--steps N` | fitter default | Optional fitter-specific step count. |
| `--pop N` | fitter default | Optional population size. |
| `--init STR` | — | DREAM init strategy. |
| `--alpha F` | `1.0` | DREAM outlier alpha. |
| `--seed N` | — | Random seed. |
| `--no-assess` | off | Skip the post-fit `assess-result` call. |

**Examples:**

```bash
# Fit a generated script with defaults; output goes to $ANALYZER_RESULTS_DIR/<stem>/
run-fit Models/cu_thf.py

# Override results location and use a denser DREAM run
run-fit Models/corefine-226667-226670.py \
  --results-dir Results --samples 20000 --burn 10000

# Fit only, no assessment
run-fit Models/quick.py --no-assess
```

### What it does

1. Executes the script (`runpy`) and grabs its module-level `problem`.
2. Calls `bumps.fitters.fit(problem, method=..., export=<results-dir>/<name>)`.
3. Unless `--no-assess`, calls `assess-result` on the output directory.

### Output files (in `<results-dir>/<name>/`)

| File | Contents |
|------|----------|
| `problem.par` | Fitted parameter values |
| `problem-err.json` | Parameter uncertainties |
| `problem-1-expt.json` | FitProblem definition |
| `problem.out` | Overall fit statistics |
| `*-refl.dat` | Reflectivity data + calculated fit |
| `problem-1-profile.dat` | SLD profile |

## Step 3: Assess the Result

`run-fit` calls `assess-result` automatically. To run it manually:

```bash
assess-result <RESULTS_DIR> [options]
```

The basename of `RESULTS_DIR` becomes the report tag, so e.g.
`assess-result results/cu_thf` writes `report_cu_thf.md`. Use
`--output-dir DIR` to override `$ANALYZER_REPORTS_DIR`.

### Chi-squared quality thresholds

| χ² range | Assessment | Recommended action |
|----------|------------|-------------------|
| < 2.0 | Excellent | Review parameter uncertainties |
| 2.0 – 3.0 | Good | Check for systematic residual patterns |
| 3.0 – 5.0 | Acceptable | Consider adjusting model |
| > 5.0 | Poor | Model likely needs revision |

### AuRE LLM evaluation fields

| Field | Meaning |
|-------|---------|
| `verdict` / `acceptable` | Overall assessment |
| `issues` | Concrete problems (boundary hits, residual structure, …) |
| `suggestions` | Actionable next steps |
| `physical_concerns` | Parameters that are physically implausible |

## Complete Workflow Example

```bash
# 1. Generate a model script from a config
create-model --config model-creation.yaml      # → Models/cu_thf.py

# 2. Fit (auto-runs assess-result afterwards)
run-fit Models/cu_thf.py

# Result lands in $ANALYZER_RESULTS_DIR/cu_thf/
# Report lands in $ANALYZER_REPORTS_DIR/report_cu_thf.md
```

## Notes

- All analysis results should be recorded in `docs/analysis_notes.md`.
- The default fitter is Bumps DREAM (Differential Evolution Adaptive Metropolis).
- MCMC samples provide parameter uncertainty estimates.
- SLD profile uncertainty bands represent 90% confidence intervals.
- For end-to-end sample analysis with reduction-issue gating, use
  **`analyze-sample`** (see the `pipeline` skill).
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

`create-model` has two modes. Pick one depending on your input.

### Mode B — from a description + data files (most common)

```bash
# Case 1 — one combined file (QProbe)
create-model --describe "50 nm Cu / 3 nm Ti on Si in D2O" \
             --data data/combined/REFL_226642_combined_data_auto.txt \
             --out models/cu_d2o.py

# Case 3 — co-refine two combined files with shared structural parameters
create-model --describe "2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O" \
             --data data/combined/REFL_226642_combined_data_auto.txt \
             --data data/combined/REFL_226652_combined_data_auto.txt \
             --out models/Cu-D2O-corefine.py

# Any mode — read options from a YAML/JSON config
create-model --config model-creation.yaml
```

The case (1, 2, or 3) is auto-detected from the data file names. Case 2 is
the multi-segment fit (`REFL_{set}_{part}_{run}_partial.txt` files sharing
one `set_id`). See the [create-model skill](../create-model/SKILL.md) for
the full reference and the case-3 `shared_parameters` rules.

### Mode A — from an AuRE problem JSON

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
create-model --describe "Cu/Ti bilayer on Si in deuterated THF" \
             --data data/combined/REFL_218281_combined_data_auto.txt \
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
