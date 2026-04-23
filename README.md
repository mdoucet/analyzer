# Neutron Reflectometry Analysis Tools

[![Python Tests](https://github.com/mdoucet/analyzer/actions/workflows/python-test.yml/badge.svg)](https://github.com/mdoucet/analyzer/actions/workflows/python-test.yml)
[![codecov](https://codecov.io/gh/mdoucet/analyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/mdoucet/analyzer)
[![DOI](https://zenodo.org/badge/1013265177.svg)](https://doi.org/10.5281/zenodo.15870378)

This repository is a demonstration project to show how LLMs can be used to help scattering facility users
analyze data. It was created out of the need to analyze a large number of data sets for a real experiment.
It is based on the idea that a list of properly named, well defined, and well documented tools can easily be
interpreted by an LLM, which can then call them according to a user's input. This version has LLM instructions
for both GitHub Copilot and GEMINI. This project is still in the prototype phase. Much remains to be done in terms of flexibility and reporting. Please feel free to contribute your own tools.


## Quick Start

1. Install VS Code and enable GitHub Copilot
2. Follow the [Installation](#installation) steps below (install [AuRE](https://github.com/neutrons-ai/aure) too if you want LLM features)
3. Make sure your data is available locally
4. Copy `.env.example` to `.env` and point `ANALYZER_COMBINED_DATA_DIR` and `ANALYZER_PARTIAL_DATA_DIR` at your data
5. Verify the LLM endpoint is reachable (optional but recommended):

```bash
check-llm
```

6. Start analyzing:

```bash
# See all available tools
analyzer-tools --list-tools

# End-to-end pipeline for one sample (recommended)
analyze-sample sample_218281.md

# Or run individual steps:
assess-partial 218281                 # partial-data quality
run-fit 218281 cu_thf                 # fit the combined data
assess-result results/218281_cu_thf 218281 cu_thf    # evaluate (+ AuRE)
```

## What This Package Does

- **End-to-end Pipeline** — `analyze-sample` runs the full workflow for one sample with a reduction-issue gate
- **Data Quality Assessment** — Check partial data consistency before combining
- **Model Generation** — `create-model` generates a refl1d script either by converting an AuRE problem JSON or directly via LLM from a sample description (including multi-file co-refinement, which AuRE does not support)
- **Model Fitting** — Wraps `aure analyze` to fit reflectivity data with uncertainty analysis
- **LLM-powered Evaluation** — `assess-result` appends an AuRE-driven fit verdict to the report
- **Automated Reporting** — Generate Markdown reports with plots
- **Time-Resolved Reduction** — EIS interval extraction and Mantid event filtering (via Docker)
- **Data Packaging** — Export time-resolved datasets to Parquet/Iceberg format
- **LLM Health Check** — `check-llm` verifies the AuRE/LLM chain at the start of a session


## Installation

### Local (without Mantid)

```bash
git clone <repository-url>
cd analyzer
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

This gives you all analysis, fitting, and planning tools. The reduction
commands (`simple-reduction`, `eis-reduce-events`) require Mantid and are
skipped gracefully when it is not installed.

### LLM features (optional)

The model-creation, fit-evaluation, and commentary features delegate to
[AuRE](https://github.com/neutrons-ai/aure). Install it in the same
environment and configure an LLM endpoint:

```bash
pip install -e /path/to/aure
export OPENAI_API_KEY=sk-...   # or configure aure_config.yaml
check-llm                      # verify the chain
```

When AuRE or the LLM is unavailable, all LLM-based steps degrade gracefully
(skipped with a warning); the rest of the pipeline continues to work.

### Docker (full stack, including Mantid)

The Docker image uses [pixi](https://pixi.sh) to install Mantid and
[lr_reduction](https://github.com/neutrons/LiquidsReflectometer) from conda
channels, then installs analyzer-tools via pip.

```bash
docker compose build
docker compose run analyzer bash          # interactive shell
docker compose run analyzer run-fit 218281 cu_thf
docker compose run test                   # run tests
```

Output files are available on your host via volume mounts (`data/`, `models/`,
`reports/`, `results/`).


## CLI Commands

All commands are installed as entry points via `pip install -e .`:

| Command | Purpose |
|---------|---------|
| `analyzer-tools` | Main CLI — list tools and get help |
| `analyze-sample` | End-to-end pipeline for one sample (partial → gate → fit → evaluate) |
| `check-llm` | Verify AuRE is installed and the LLM endpoint is reachable |
| `run-fit` | Fit combined data (wraps `aure analyze`; `--legacy` for the old fitter) |
| `assess-partial` | Assess partial-data overlap quality; `--llm-commentary` adds AuRE commentary |
| `assess-result` | Evaluate fit quality + append an AuRE LLM verdict to the report |
| `create-model` | Generate a refl1d script from a problem JSON (Mode A) or directly via LLM from a description + data files (Mode B) |
| `theta-offset` | Compute the theta offset for a Liquids Reflectometer run |
| `eis-intervals` | Extract EIS timing intervals to JSON |
| `iceberg-packager` | Package tNR data into Parquet files |
| `analyzer-batch` | Dispatch multiple jobs from a YAML manifest |
| `simple-reduction` | Mantid single-run reduction (Docker) |
| `eis-reduce-events` | Mantid time-resolved reduction (Docker) |

```bash
# Discovery
analyzer-tools --list-tools        # all tools with descriptions
analyzer-tools --help-tool partial # detailed help for a tool
```


## Configuration

Copy `.env.example` to `.env` in the project directory and edit the values:

```bash
cp .env.example .env
```

```dotenv
# Paths
ANALYZER_RESULTS_DIR=results
ANALYZER_COMBINED_DATA_DIR=data/combined
ANALYZER_PARTIAL_DATA_DIR=data/partial
ANALYZER_REPORTS_DIR=reports
ANALYZER_COMBINED_DATA_TEMPLATE=REFL_{set_id}_combined_data_auto.txt
ANALYZER_MODELS_DIR=models
```

### `.env` cascade

Analyzer CLIs can be invoked from **any** directory (e.g. a per-sample data
folder). On startup, `.env` files are loaded in decreasing priority — the
first setter wins:

1. **Process environment** — variables already `export`ed in your shell.
2. **`--env PATH`** (on supported commands) or **`$ANALYZER_ENV_FILE`**.
3. **Project `.env`** — the nearest `.env` walking up from the current
   working directory.
4. **User-global `.env`** — `~/.config/analyzer/.env`
   (override dir via `$ANALYZER_CONFIG_DIR` or `$XDG_CONFIG_HOME/analyzer`).

Recommended split:

- **User-global** `~/.config/analyzer/.env` → LLM credentials used by every
  project (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`).
- **Project / sample** `.env` in the data folder → path overrides
  (`ANALYZER_MODELS_DIR`, `ANALYZER_RESULTS_DIR`, …) and any per-sample
  LLM overrides.

```bash
# First-time setup of user-global credentials
mkdir -p ~/.config/analyzer
cat > ~/.config/analyzer/.env <<'EOF'
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...
EOF
```

With that in place, `create-model`, `assess-result`, and friends work from
any project directory without re-configuring the LLM.

### LLM / AuRE variables

Required for `create-model` Mode B and `assess-result`'s LLM evaluation:

| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `openai` \| `gemini` \| `alcf` \| `local` |
| `LLM_MODEL` | Model name (e.g. `gpt-4o`, `gpt-oss:120b`) |
| `LLM_API_KEY` | API key (or `OPENAI_API_KEY` / `GEMINI_API_KEY`) |
| `LLM_BASE_URL` | Base URL for local / OpenAI-compat endpoints |
| `LLM_TEMPERATURE` | Default `0.0` |
| `LLM_TIMEOUT` | Request timeout in seconds |


## Data Organization

| Directory | Contents | Format |
|-----------|----------|--------|
| `data/combined/` | Final reduced reflectivity curves | `REFL_{set_id}_combined_data_auto.txt` |
| `data/partial/` | Individual partial curves (usually 3 per set) | `REFL_<set_ID>_<part_ID>_<run_ID>_partial.txt` |
| `models/` | Python model files for refl1d | `*.py` with `create_fit_experiment()` |
| `results/` | Fit outputs (parameters, plots) | per-fit subdirectories |
| `reports/` | Markdown analysis reports | `report_<set_id>.md` |

All data files have 4 columns: **Q** (1/Å), **R** (reflectivity), **dR** (uncertainty), **dQ** (resolution).


## Analysis Workflows

### 1. Partial Data Quality Check
```bash
assess-partial 218281
# → reports/report_218281.md with overlap chi-squared metrics and plots
```

### 2. Standard Fitting
```bash
create-model --describe "Cu/Ti on Si in dTHF" \
             --data data/combined/REFL_218281_combined_data_auto.txt \
             --out models/cu_thf.py
run-fit 218281 cu_thf                     # fit the data
assess-result 218281 cu_thf               # evaluate fit quality (+ AuRE)
```

### 3. End-to-end Pipeline
```bash
analyze-sample sample_218281.md           # one command, full workflow
```

### 4. Time-Resolved Reduction (Docker)
```bash
docker compose run analyzer eis-intervals --data-dir /app/data/eis -o intervals.json
docker compose run analyzer eis-reduce-events \
  --event-file /app/data/events.h5 \
  --template /app/data/template.xml \
  --intervals intervals.json \
  --output-dir /app/results/tnr
```


## Models

Models are Python files in the directory set by `ANALYZER_MODELS_DIR`
(default `models/`) that define a `create_fit_experiment(q, dq, data, errors)`
function returning a `refl1d.experiment.Experiment`.

```bash
# Mode B — generate from a description + one combined file (case 1)
create-model --describe "Cu/Ti on Si in D2O" \
             --data data/combined/REFL_218281_combined_data_auto.txt \
             --out models/cu_thf.py

# Mode B — co-refine multiple combined files (case 3; not supported by AuRE)
create-model --describe "2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O" \
             --data data/combined/REFL_226642_combined_data_auto.txt \
             --data data/combined/REFL_226652_combined_data_auto.txt \
             --out models/Cu-D2O-corefine.py

# Mode A — from an existing AuRE problem JSON
create-model path/to/NNN_model_initial.json --out models/cu_thf.py

# Either mode — options from a YAML/JSON config
create-model --config model-creation.yaml

# Or start from an existing model and edit bounds manually
cp models/cu_thf.py models/my_model.py
```

### `--config` file format

`--config` accepts YAML or JSON in two shapes.

**Flat (one job).** Top-level keys (CLI flags override, relative paths
resolve against the config file's directory):

| Key | Aliases | Meaning |
|---|---|---|
| `describe` | `description`, `sample_description` | Mode B sample description |
| `data` | `data_files` | Mode B: list of REF_L data files |
| `data_file` | — | Mode B: single extra data file, prepended to `data` |
| `source` | — | Mode A: path to problem JSON |
| `out` | — | Output script path |
| `model_name` | `name` | Name in docstring / default filename |

```yaml
describe: |
  2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O (SLD ~6).
data:
  - Rawdata/REFL_226642_combined_data_auto.txt
  - Rawdata/REFL_226652_combined_data_auto.txt
out: Models/Cu-D2O-corefine.py
model_name: corefine_226642_226652
```

**Jobs list (batch).** AuRE-batch-manifest-compatible shape. Each entry is
one `create-model` invocation; AuRE-specific keys (`fit_method`, `fit_steps`,
`llm_*`, `command`, …) are **ignored**. Only `defaults.output_root` is read
from `defaults:`.

```yaml
defaults:
  output_root: ./Models          # fallback output directory

jobs:
  - name: copper_oxide           # → Models/copper_oxide.py
    sample_description: >-
      2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O.
    data_file: Rawdata/REFL_226642_1_226642_partial.txt
    data_files:
      - Rawdata/REFL_226642_2_226643_partial.txt
      - Rawdata/REFL_226642_3_226644_partial.txt

  - name: corefine_226642_226652
    description: 2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O
    data:
      - Rawdata/REFL_226642_combined_data_auto.txt
      - Rawdata/REFL_226652_combined_data_auto.txt
    out: Models/Cu-D2O-corefine.py    # overrides output_root
```

Rules: each job must be either Mode A (`source:`) **or** Mode B (`describe`
+ data files), not both; when `jobs:` is present do not also pass
`SOURCE`/`--describe`/`--data`/`--out` on the command line. See the
[create-model skill](skills/create-model/SKILL.md) for full details.

**States (multi-state co-refinement).** Use a top-level `states:` list when
you want to co-refine measurements of the same sample — a state groups
files that share one Sample stack, and across states you control which
structural parameters are tied with `shared_parameters` (whitelist) or
`unshared_parameters` (blacklist, mutually exclusive). Partial-kind states
can also float their own `theta_offset` / `sample_broadening`. Combined and
partial-kind states may be mixed in the same run. See
[skills/create-model/SKILL.md](skills/create-model/SKILL.md) for the full
example and rules.

To widen or tighten a parameter range, edit the model file's
`.range(min, max)` calls directly and re-fit. (The old
`create-temporary-model` CLI was retired in v0.2.0.)


## Getting Help

```bash
analyzer-tools --list-tools            # all tools
analyzer-tools --help-tool <name>      # detailed help for one tool
```

See [docs/developer_notes.md](docs/developer_notes.md) for development guidelines.


## Contributing

1. Follow the test-driven development approach in `docs/developer_notes.md`
2. Update the tool registry (`registry.py`) when adding new tools
3. Run tests: `pytest`
4. Keep CLI entry points in sync in `pyproject.toml`
