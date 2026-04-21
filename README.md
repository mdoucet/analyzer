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
4. Edit `config.ini` to point `combined_data_dir` and `partial_data_dir` at your data
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
- **Model Generation** — `create-model` turns a sample description into a refl1d script via [AuRE](https://github.com/neutrons-ai/aure)
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
| `create-model` | Generate a refl1d script from a sample description or `ModelDefinition` JSON (via AuRE) |
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

Edit `config.ini` to customize paths:

```ini
[paths]
results_dir = results
combined_data_dir = data/combined
partial_data_dir = data/partial
reports_dir = reports
combined_data_template = REFL_{set_id}_combined_data_auto.txt
```


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
create-model "Cu/Ti on Si in dTHF" data/combined/REFL_218281_combined_data_auto.txt \
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

Models are Python files in `models/` that define a `create_fit_experiment(q, dq, data, errors)`
function returning a `refl1d.experiment.Experiment`.

Available models: `cu_thf`, `cu_thf_no_oxide`, `cu_thf_tiny`,
`ionomer_sld_1`, `ionomer_sld_2`, `ionomer_sld_3`.

```bash
# Generate a model from a plain-English description (via AuRE)
create-model "Cu/Ti on Si in dTHF" \
             data/combined/REFL_218281_combined_data_auto.txt \
             --out models/cu_thf.py

# Or from an existing AuRE ModelDefinition JSON
create-model path/to/NNN_model_initial.json --out models/cu_thf.py

# Copy an existing model as a starting point and edit bounds manually
cp models/cu_thf.py models/my_model.py
```

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
