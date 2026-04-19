---
name: fit-evaluation
description: >
  LLM-powered fit quality evaluation using AuRE, augmenting the standard
  assess-result workflow with intelligent analysis.
  USE FOR: evaluating fit quality after run-fit, getting actionable suggestions
  for model improvement, assessing physical plausibility of fitted parameters.
  DO NOT USE FOR: running fits (see fitting skill), partial data checks
  (see partial-assessment skill), or generating plots alone (use assess-result directly).
---

# LLM-Powered Fit Evaluation with AuRE

## Overview

This skill augments the existing `assess-result` tool with `aure evaluate` from
the [AuRE](https://github.com/neutrons-ai/aure) package. The two tools are
complementary:

| Tool | Provides |
|------|----------|
| `assess-result` | Reflectivity & SLD plots (SVG), parameter table, markdown report, SLD uncertainty bands |
| `aure evaluate` | LLM-driven quality verdict, residual structure analysis, boundary-hit detection, physical plausibility checks, actionable suggestions |

**Always run both.** `assess-result` produces the visual artifacts;
`aure evaluate` provides the intelligent assessment.

## Prerequisites

### 1. Install AuRE in the analyzer environment

```bash
pip install -e ~/git/aure
```

### 2. Configure LLM access

AuRE needs a working LLM connection. Set one of:

- **Environment variable**: `export OPENAI_API_KEY=sk-...`
- **Config file**: `~/git/aure/aure_config.yaml` (copy from `aure_config.example.yaml`)

Verify with:

```bash
aure check-llm
```

### 3. Verify `problem.json` exists

The `run-fit` tool (bumps DREAM with `export=`) writes `problem.json` to the
results directory automatically. Confirm it exists before running `aure evaluate`:

```bash
ls results/<SET_ID>_<MODEL>/problem.json
```

## Augmented Workflow

The standard fitting loop becomes:

```
run-fit <SET_ID> <MODEL>
    │
    ▼
assess-result results/<SET_ID>_<MODEL> <SET_ID> <MODEL>
    │  → plots, parameter table, markdown report
    ▼
aure evaluate results/<SET_ID>_<MODEL> --context "<sample description>" --json
    │  → quality verdict, issues, suggestions
    ▼
┌─ acceptable? ─────────────────────────┐
│  Yes → record in analysis notes       │
│  No  → act on suggestions, then:      │
│        create-temporary-model + re-fit │
└───────────────────────────────────────┘
```

## Step-by-Step Usage

### Step 1: Run the fit (unchanged)

```bash
run-fit 218281 cu_thf
```

### Step 2: Generate plots and report

```bash
assess-result results/218281_cu_thf 218281 cu_thf
```

This produces the usual artifacts:

| File | Contents |
|------|----------|
| `reports/report_218281.md` | Markdown report with parameter table |
| `reports/fit_result_218281_cu_thf_reflectivity.svg` | R vs Q plot |
| `reports/fit_result_218281_cu_thf_profile.svg` | SLD profile with 90% CL bands |
| `reports/sld_uncertainty_218281_cu_thf.txt` | SLD uncertainty data |

### Step 3: Run AuRE evaluation

```bash
aure evaluate results/218281_cu_thf \
  --context "Cu/Ti bilayer on Si in deuterated THF" \
  --json
```

#### Options

| Option | Description |
|--------|-------------|
| `REFL1D_DIR` | (required) Path to fit results directory containing `problem.json` |
| `--context`, `-c` | Natural-language sample description for physical plausibility checks |
| `--hypothesis`, `-h` | Hypothesis being tested (e.g., "single-layer model suffices") |
| `--json` | Machine-readable JSON output (recommended for automation) |
| `--verbose`, `-v` | Verbose logging |

#### JSON output structure

```json
{
  "directory": "results/218281_cu_thf",
  "iteration": 0,
  "method": "dream",
  "chi_squared": 1.83,
  "parameters": { "Cu thickness": 505.2, "material rho": 5.8 },
  "uncertainties": { "Cu thickness": 3.1, "material rho": 0.04 },
  "acceptable": true,
  "quality_assessment": "Good",
  "issues": [],
  "suggestions": ["Check dQ calibration in high-Q region"],
  "physical_concerns": []
}
```

#### Human-readable output (without `--json`)

```
═══════════════════════════════════════════
  Evaluate Refl1D Fit Result
═══════════════════════════════════════════

  Directory: results/218281_cu_thf
  χ² = 1.8300

  Fit Quality: Good (χ² = 1.830)

  ✓ Fit ACCEPTABLE
```

## Interpreting Results and Acting on Them

### Decision rules

| Field | Value | Action |
|-------|-------|--------|
| `acceptable` | `true` | Record result in `docs/analysis_notes.md`. Done. |
| `acceptable` | `false` | Read `issues` and `suggestions`, then adjust model and re-fit. |
| `physical_concerns` | non-empty | Review flagged parameters — may indicate wrong model or bad data. |

### Acting on suggestions

Common suggestions and how to respond:

| Suggestion | Action |
|------------|--------|
| "Parameter X at upper bound" | `create-temporary-model <base> <new> --adjust '<layer> <param> <wider_min>,<wider_max>'` |
| "Consider adding interface roughness" | Edit model to add `interface.range(...)` on the relevant layer |
| "Residual fringes suggest unmodeled layer" | Create a new model with an additional layer |
| "High-Q residual structure" | Check dQ resolution in the data; consider background parameter |

### Example: responding to boundary hit

```bash
# AuRE reports: "Cu thickness at upper bound (800 Å)"
create-temporary-model cu_thf cu_thf_wide --adjust 'Cu thickness 300,1200'
run-fit 218281 cu_thf_wide
assess-result results/218281_cu_thf_wide 218281 cu_thf_wide
aure evaluate results/218281_cu_thf_wide \
  --context "Cu/Ti bilayer on Si in deuterated THF" --json
```

## Complete Workflow Example

```bash
# 1. Fit
run-fit 218281 cu_thf

# 2. Plots & report
assess-result results/218281_cu_thf 218281 cu_thf

# 3. Intelligent evaluation
aure evaluate results/218281_cu_thf \
  -c "Cu/Ti bilayer on Si in deuterated THF" --json
# → { "acceptable": false,
#     "issues": ["Cu thickness near upper bound"],
#     "suggestions": ["Widen Cu thickness range to 1200 Å"] }

# 4. Act on suggestion
create-temporary-model cu_thf cu_thf_wide --adjust 'Cu thickness 300,1200'

# 5. Re-fit and re-evaluate
run-fit 218281 cu_thf_wide
assess-result results/218281_cu_thf_wide 218281 cu_thf_wide
aure evaluate results/218281_cu_thf_wide \
  -c "Cu/Ti bilayer on Si in deuterated THF" --json
# → { "acceptable": true, "quality_assessment": "Good" }

# 6. Record in analysis notes
```

## Fallback: When AuRE Is Unavailable

If the LLM is not configured or `aure` is not installed, fall back to using
`assess-result` alone. The chi-squared thresholds from the fitting skill still
apply:

| χ² range | Assessment |
|----------|------------|
| < 2.0 | Excellent |
| 2.0 – 3.0 | Good |
| 3.0 – 5.0 | Acceptable |
| > 5.0 | Poor — revise model |

## Notes

- `aure evaluate` reads `problem.json` (bumps serialized FitProblem). This file
  is written automatically by `run-fit` via bumps `fit(..., export=...)`.
- The `--context` flag significantly improves evaluation quality — always provide
  a sample description when available.
- All evaluation results should be recorded in `docs/analysis_notes.md`.
- `aure evaluate` does **not** generate plots — that is still handled by `assess-result`.
