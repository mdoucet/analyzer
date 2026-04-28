---
name: analyze-sample
description: >
  End-to-end sample pipeline for neutron reflectometry analysis. Drives the full
  workflow for a single sample: partial-data assessment, reduction-issue gate,
  model generation (`create-model`), fitting (`run-fit`, which auto-runs
  `assess-result`), and an optional AuRE evaluation pass.
  USE FOR: automating analysis of a single sample from start to finish.
  DO NOT USE FOR: individual tool execution (see the respective skills) or
  batch-processing multiple samples (use `analyzer-batch`).
---

# Skill: Sample pipeline (`analyze-sample`)

One command drives the full analyzer workflow for a single sample:

```
analyze-sample path/to/sample_218281.yaml
```

The argument is a YAML file in the **same shape as `create-model --config`**.

## What it does

Stages, in order:

1. **assess-partial** — for each state whose data files are partials, compute
   overlap χ² between segments.
2. **theta-offset (record)** — if the YAML has a `theta_offset:` block, those
   offsets are recorded and fed to the gate. (The `theta-offset` tool itself
   is **not** invoked here; precompute offsets separately if you need them.)
3. **reduction-issue gate** — if any overlap χ² exceeds `--chi2-threshold`
   (default `3.0`) or any `|θ-offset|` exceeds `--offset-threshold-deg`
   (default `0.01`), the pipeline **halts** and writes:
   - `reports/sample_<tag>/reduction_issues.md`
   - `reports/sample_<tag>/reduction_batch.yaml` (an `analyzer-batch` manifest
     with one `simple-reduction` job per segment — review and run it manually;
     reduction is **never** auto-executed).
4. **create-model** — `create-model --config <yaml>` produces the refl1d
   script.
5. **run-fit** — `run-fit <script> --name <tag>` fits the script and runs
   `assess-result` automatically, writing `reports/report_<tag>.md` with
   reflectivity overlay + per-state SLD profiles with credible-interval bands.
6. **aure evaluate** *(optional, default on)* — appends an
   `## LLM Evaluation (AuRE)` section to the fit report. Skip with
   `--skip-aure-eval`.

The "tag" is the YAML's `model_name` field (alias `name`), defaulting to the
YAML stem.

Final per-sample summary is written to:

- `reports/sample_<tag>/sample_<tag>.md`
- `reports/sample_<tag>/sample_<tag>.json` (structured, for downstream tools)
- `reports/sample_<tag>/.pipeline_state.json` (resume cache)

## YAML config (same shape as `create-model --config`)

```yaml
# Required
describe: |
  Copper film on silicon in 100 mM LiTFSI/THF. Expected: Si substrate,
  ~20 Å native CuOx, ~50 Å Cu, THF electrolyte ambient.

model_name: cu_thf_218281        # used as the pipeline tag

states:
  - name: state_218281
    data:
      - REFL_218281_1_218281_partial.txt
      - REFL_218281_2_218282_partial.txt
      - REFL_218281_3_218283_partial.txt
    # optional per-state nuisance parameters:
    # theta_offset: true
    # sample_broadening: { init: 0.0, min: -0.005, max: 0.005 }
    # back_reflection: false

# Optional — if relative, resolved against this YAML's directory
# data_dir: ../reduced

# Optional — passed through to create-model
# shared_parameters: [...]
# unshared_parameters: [...]
# out: models/cu_thf_218281.py

# Pipeline-only optional fields
hypothesis: Copper layer thins over time.
theta_offset:
  - { run: "218281", offset: 0.003 }
  - { run: "218282", offset: 0.002 }
```

All keys accepted by `create-model --config` are forwarded verbatim. The
pipeline-only extras (`hypothesis`, top-level `theta_offset`) are read by
`analyze-sample` but ignored by `create-model`.

For multi-state co-refines, list multiple states in `states:`, each with its
own `data:` block. All files within one state must be the same kind (all
partial of one set_id, or all combined).

## Useful flags

| Flag | Purpose |
| --- | --- |
| `--dry-run` | Print the plan without executing. |
| `--force` | Ignore cached state and re-run all stages. |
| `--skip-partial` | Skip partial-data assessment. |
| `--skip-fit` | Stop after the reduction gate (useful for pre-checks). |
| `--no-reduction-gate` | Continue even if overlap χ² or θ-offset is bad. |
| `--chi2-threshold 3.0` | Overlap χ² threshold for "block". |
| `--offset-threshold-deg 0.01` | θ-offset threshold for "block". |
| `--skip-aure-eval` | Skip the `aure evaluate` LLM pass. |
| `--results-dir PATH` | Override `ANALYZER_RESULTS_DIR`. |
| `--reports-dir PATH` | Override `ANALYZER_REPORTS_DIR`. |

## Resuming

On re-run, completed stages are read from `.pipeline_state.json` and skipped.
Use `--force` to start over.

## Exit codes

- `0` — pipeline completed (`status: ok`).
- `2` — a stage failed (e.g., `create-model`/`run-fit` missing or non-zero).
- `3` — reduction-issue gate halted the pipeline (`status: needs-reprocessing`).
---
name: analyze-sample
description: >
  End-to-end sample pipeline for neutron reflectometry analysis. Drives the full
  workflow for a single sample, including partial-data assessment, theta-offset
  ingestion, model generation, fitting, and result assessment.
  USE FOR: automating the analysis of a single sample from start to finish.
  DO NOT USE FOR: individual tool execution (see respective skills for details).
  CSV logs, batch-processing multiple runs.
  DO NOT USE FOR: fitting reflectivity data (see fitting skill), reducing
  neutron events (see time-resolved skill).
---

# Skill: Sample pipeline (`analyze-sample`)

One command drives the full analyzer workflow for a single sample:

```
analyze-sample path/to/sample_218281.md
```

or, with defaults from the env vars (`.env` / `ANALYZER_*`):

```
analyze-sample 218281
```

## What it does

Runs, in order, for one `set_id`:

1. **Partial-data assessment** — χ² overlap between segments (if partial files exist).
2. **Theta-offset ingestion** — reads offsets from the sample YAML (if present).
3. **Reduction-issue gate** — if any overlap χ² exceeds `--chi2-threshold`
   (default `3.0`) or any |θ-offset| exceeds `--offset-threshold-deg`
   (default `0.01`), the pipeline **halts** and writes:
   - `reports/sample_<id>/reduction_issues.md`
   - `reports/sample_<id>/reduction_batch.yaml` (an `analyzer-batch` manifest
     with one `simple-reduction` job per segment that the user can review and
     run manually — reduction is **never** auto-executed)
4. **Model generation via AuRE** (`aure analyze -m 0`) — from the sample
   description in the markdown body.
5. **Fit via AuRE** (`aure analyze -m <max-refinements>`) — writes to
   `<results>/<set_id>_<model>/`.
6. **Result assessment + AuRE evaluation** — augments `report_<id>.md` with
   an `## LLM Evaluation (AuRE)` section (unless `--skip-aure-eval`).

Final sample summary is written to:

- `reports/sample_<id>/sample_<id>.md`
- `reports/sample_<id>/sample_<id>.json` (structured, for downstream tools)
- `reports/sample_<id>/.pipeline_state.json` (resume cache)

## Sample description format

```markdown
---
set_id: "218281"
hypothesis: "Copper layer thins over time."
# optional:
# data_file: /abs/path/to/REFL_218281_combined_data_auto.txt
# partial_dir: /abs/path/to/partials
# model: cu_thf              # tag appended to results dir
# theta_offset:
#   - {run: "218281", offset: 0.003}
#   - {run: "218282", offset: 0.002}
---

Copper film on silicon in 100 mM LiTFSI/THF electrolyte. Expected structure:
Si substrate, ~20 Å native CuOx, ~50 Å Cu, THF electrolyte ambient.
```

Everything below the `---` fences is passed verbatim to AuRE as the sample
description.

## Useful flags

| Flag | Purpose |
| --- | --- |
| `--dry-run` | Print the plan without executing. |
| `--force` | Ignore cached state and re-run all stages. |
| `--skip-partial` | Skip partial-data assessment. |
| `--skip-fit` | Stop after the reduction gate (useful for pre-checks). |
| `--no-reduction-gate` | Continue even if overlap χ² or θ-offset is bad. |
| `--chi2-threshold 3.0` | Overlap χ² threshold for "block". |
| `--offset-threshold-deg 0.01` | θ-offset threshold for "block". |
| `--skip-aure-eval` | Skip the `aure evaluate` LLM pass. |
| `-m 5` | AuRE max refinements. |

## Resuming

On re-run, completed stages are read from `.pipeline_state.json` and skipped.
Use `--force` to start over.

## Exit codes

- `0` — pipeline completed (`status: ok`).
- `2` — a stage failed (e.g., `aure` not installed, fit non-zero).
- `3` — reduction-issue gate halted the pipeline (`status: needs-reprocessing`).
