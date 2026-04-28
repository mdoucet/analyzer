# Neutron Reflectometry Analysis Tools

[![Python Tests](https://github.com/mdoucet/analyzer/actions/workflows/python-test.yml/badge.svg)](https://github.com/mdoucet/analyzer/actions/workflows/python-test.yml)
[![codecov](https://codecov.io/gh/mdoucet/analyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/mdoucet/analyzer)
[![DOI](https://zenodo.org/badge/1013265177.svg)](https://doi.org/10.5281/zenodo.15870378)

A toolbox of small, well-named CLI tools that an LLM agent (or a human) can
chain together to analyze neutron reflectometry data end-to-end: partial
data quality checks → model generation → refl1d fit → report. Built around
[refl1d](https://github.com/reflectometry/refl1d)/[bumps](https://github.com/bumps/bumps)
for the math, with optional [AuRE](https://github.com/neutrons-ai/aure) for
LLM-driven model creation and fit evaluation.

## Quick Start

1. Install with `pip install -e ".[dev]"` (see [Installation](#installation)).
2. *(Optional)* Set up a one-time user-global LLM config:

   ```bash
   mkdir -p ~/.config/analyzer
   cat > ~/.config/analyzer/.env <<'EOF'
   LLM_PROVIDER=openai
   LLM_MODEL=gpt-4o
   LLM_API_KEY=sk-...
   EOF
   check-llm
   ```

3. `cd` into a sample folder containing reduced data and run the pipeline:

   ```bash
   analyze-sample sample.yaml
   ```

   The YAML uses the same shape as `create-model --config` (a
   `describe:` + `states:` list). A minimal example:

   ```yaml
   describe: 50 nm Cu / 3 nm Ti on Si in D2O
   model_name: cu_d2o_218281
   states:
     - name: state_218281
       data:
         - rawdata/REFL_218281_1_218281_partial.txt
         - rawdata/REFL_218281_2_218282_partial.txt
         - rawdata/REFL_218281_3_218283_partial.txt
   ```

The pipeline runs partial-data checks, halts on bad reduction, then calls
`create-model` → `run-fit` → `assess-result`, writing a Markdown report
under `reports/`.

## What you get

- **`analyze-sample`** — One-shot pipeline for a single sample, with a
  reduction-issue gate that emits a `reduction_batch.yaml` manifest you
  review and dispatch yourself (reduction is never run automatically).
- **`create-model`** — Generate a refl1d-ready Python script from a sample
  description (LLM/AuRE) or convert an AuRE problem JSON. Multi-state
  co-refinement is supported.
- **`run-fit`** — Run a bumps DREAM fit on a refl1d script and produce
  parameter tables, plots, and a Markdown report.
- **`assess-result`** — Re-render the report from a fit-output directory:
  reflectivity overlay (multi-experiment), per-state SLD profiles with 90%
  CL bands. Optionally appends an `aure evaluate` LLM verdict.
- **`assess-partial`** — Overlap-χ² check on partial reflectivity files.
- **`theta-offset`** — Compute or batch-compute incident-angle offsets for
  a Liquids Reflectometer run.
- **`eis-intervals` / `eis-reduce-events`** — Time-resolved reduction
  helpers (Mantid-based; Docker recommended).
- **`iceberg-packager`** — Package time-resolved data into Parquet/Iceberg.
- **`analyzer-batch`** — Dispatch multiple analyzer-tool jobs from a YAML
  manifest.
- **`check-llm`** — Verify that AuRE and the configured LLM endpoint are
  reachable.

Run `analyzer-tools --list-tools` for the full registry, or
`analyzer-tools --help-tool <name>` for any single tool. Per-workflow
documentation lives under [`skills/`](skills/).

## Installation

```bash
git clone <repository-url>
cd analyzer
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

This gives you all analysis, fitting, and pipeline tools. The Mantid-based
reduction commands (`simple-reduction`, `eis-reduce-events`) require Mantid
and are skipped gracefully when it isn't installed; use Docker for the
full stack — see [docs/docker.md](docs/docker.md).

LLM features (`create-model` Mode B, `aure evaluate` augmentation) require
[AuRE](https://github.com/neutrons-ai/aure) installed in the same
environment and a configured LLM endpoint. They degrade gracefully when
unavailable.

## Configuration

The analyzer needs a project root and five role-based directories
(combined data, partial data, models, results, reports). The simplest
setup is to `cd` into a sample folder — everything resolves under `$PWD`
with lowercase defaults (`rawdata/`, `models/`, `results/`, `reports/`).
A repo-level `.env` *above* the sample folders can rename those
sub-folders without becoming the project root itself.

See [docs/configuration.md](docs/configuration.md) for the full
`.env`-cascade rules and variable reference.

## Documentation

| Topic | Where |
|---|---|
| End-to-end pipeline (`analyze-sample`) | [skills/pipeline/SKILL.md](skills/pipeline/SKILL.md) |
| `create-model` reference (Mode A & B) | [skills/create-model/SKILL.md](skills/create-model/SKILL.md) |
| Fitting workflow (`create-model` → `run-fit` → `assess-result`) | [skills/fitting/SKILL.md](skills/fitting/SKILL.md) |
| Partial-data overlap checks | [skills/partial-assessment/SKILL.md](skills/partial-assessment/SKILL.md) |
| Theta-offset calculation | [skills/theta-offset/SKILL.md](skills/theta-offset/SKILL.md) |
| Time-resolved reduction | [skills/time-resolved/SKILL.md](skills/time-resolved/SKILL.md), [docs/time-resolved-eis.md](docs/time-resolved-eis.md) |
| Data layout & file formats | [skills/data-organization/SKILL.md](skills/data-organization/SKILL.md) |
| Reflectometry primer | [skills/reflectometry-basics/SKILL.md](skills/reflectometry-basics/SKILL.md) |
| Configuration / `.env` cascade | [docs/configuration.md](docs/configuration.md) |
| Docker (full stack with Mantid) | [docs/docker.md](docs/docker.md) |
| Single-file skill summary (for downstream repos) | [skills/distributable/SKILL.md](skills/distributable/SKILL.md) |

## Citation

If this project helps your work, please cite via the
[Zenodo DOI](https://doi.org/10.5281/zenodo.15870378) (badge above) or the
metadata in [CITATION.cff](CITATION.cff).
