---
name: fitting
description: >
  Reflectivity fitting workflow — run fits, assess results, adjust models, and iterate.
  Covers run-fit, assess-result, create-model, and create-temporary-model tools.
  USE FOR: fitting combined data to a model, evaluating fit quality, adjusting
  parameter ranges, generating fit reports.
  DO NOT USE FOR: partial data quality checks (see partial-assessment skill) or
  data reduction (see time-resolved skill).
---

# Reflectivity Fitting Workflow

## Overview

The standard fitting workflow is:

1. **`run-fit`** — Fit combined data to a model
2. **`assess-result`** — Evaluate fit quality and parameter uncertainties
3. If poor fit: **`create-temporary-model`** to adjust parameter ranges, then re-fit

## Step 1: Run a Fit

```bash
run-fit <SET_ID> <MODEL_NAME>
```

**Examples:**
```bash
run-fit 218281 cu_thf
run-fit 218386 cu_thf_no_oxide
```

### What it does

1. Loads combined data from `{combined_data_dir}/REFL_{SET_ID}_combined_data_auto.txt`
2. Creates the model experiment by calling `create_fit_experiment(Q, dQ, R, dR)`
3. Runs the DREAM MCMC algorithm (10,000 samples, 5,000 burn-in)
4. Saves results to `{results_dir}/{SET_ID}_{MODEL_NAME}/`

### Important: Column order

The data file columns are `Q, R, dR, dQ`, but the model function signature is `create_fit_experiment(q, dq, data, errors)`. The tool handles the mapping:

```python
_refl = np.loadtxt(data_file).T
experiment = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])
#                                  Q         dQ        R         dR
```

### Output files

| File | Contents |
|------|----------|
| `problem.par` | Fitted parameter values |
| `problem-err.json` | Parameter uncertainties (JSON) |
| `problem-1-expt.json` | Experiment definition with bounds |
| `problem.out` | Overall fit statistics |
| `*-refl.dat` | Reflectivity data with calculated fit values |

## Step 2: Assess the Result

```bash
assess-result <RESULTS_DIR> <SET_ID> <MODEL_NAME>
```

**Example:**
```bash
assess-result results/218281_cu_thf 218281 cu_thf
```

### What it does

1. Reads fit output files from the results directory
2. Extracts chi-squared, parameter values, and uncertainties
3. Generates reflectivity plot (data vs fit) and SLD profile with 90% confidence bands
4. Writes/appends to the markdown report

> **Tip:** For deeper, LLM-powered evaluation (residual structure analysis,
> physical plausibility, actionable suggestions), also run `aure evaluate`
> after `assess-result`. See the **fit-evaluation** skill for details.

### Output files

| File | Contents |
|------|----------|
| `report_{SET_ID}.md` | Markdown report with fit quality, parameter table, and plots |
| `fit_result_{SET_ID}_{MODEL}_reflectivity.svg` | R vs Q plot (log-log, data + fit) |
| `fit_result_{SET_ID}_{MODEL}_profile.svg` | SLD profile with uncertainty band |
| `sld_uncertainty_{SET_ID}_{MODEL}.txt` | SLD profile numerical data |

### Chi-squared quality thresholds

| χ² range | Assessment | Recommended action |
|----------|------------|-------------------|
| < 2.0 | Excellent | Review parameter uncertainties |
| 2.0 – 3.0 | Good | Check for systematic residual patterns |
| 3.0 – 5.0 | Acceptable | Consider adjusting model |
| > 5.0 | Poor | Model likely needs revision |

### Parameter table format

The report includes a table with columns:

| Layer | Parameter | Fitted Value | Uncertainty | Min | Max | Units |
|-------|-----------|--------------|-------------|-----|-----|-------|

Parameters are grouped by layer name.

## Step 3: Adjust and Re-fit (if needed)

If the fit quality is poor or parameters hit their bounds, create a modified model:

```bash
create-temporary-model <BASE_MODEL> <NEW_MODEL> --adjust 'LAYER PARAM MIN,MAX'
```

**Example:**
```bash
# Widen Cu thickness range
create-temporary-model cu_thf cu_thf_wide --adjust 'Cu thickness 300,1000'

# Then re-fit with the new model
run-fit 218281 cu_thf_wide
assess-result results/218281_cu_thf_wide 218281 cu_thf_wide
```

Multiple adjustments:
```bash
create-temporary-model cu_thf cu_thf_custom \
  --adjust 'Cu thickness 300,1000' \
  --adjust 'material rho 2,8'
```

## Complete Workflow Example

```bash
# 1. Initial fit
run-fit 218281 cu_thf

# 2. Check quality
assess-result results/218281_cu_thf 218281 cu_thf
# → reports/report_218281.md shows χ² = 6.2 (poor)

# 3. Adjust model — widen material thickness range
create-temporary-model cu_thf cu_thf_wide --adjust 'material thickness 10,300'

# 4. Re-fit
run-fit 218281 cu_thf_wide

# 5. Re-assess
assess-result results/218281_cu_thf_wide 218281 cu_thf_wide
# → χ² = 1.8 (excellent)
```

## Generating Standalone Scripts

To create a self-contained Python fit script (useful for debugging or running outside the framework):

```bash
create-model cu_thf REFL_218281_combined_data_auto.txt
# → model_218281_cu_thf.py
```

## Notes

- All analysis results should be recorded in `docs/analysis_notes.md`
- The fitting algorithm is Bumps DREAM (Differential Evolution Adaptive Metropolis)
- MCMC samples provide parameter uncertainty estimates
- SLD profile uncertainty bands represent 90% confidence intervals
