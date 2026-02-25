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
2. Follow the [Installation](#installation) steps below
3. Make sure your data is available locally
4. Edit `config.ini` to point `combined_data_dir` and `partial_data_dir` at your data
5. Start analyzing:

```bash
# See all available tools
analyzer-tools --list-tools

# Assess partial data quality
assess-partial 218281

# Fit combined data
run-fit 218281 cu_thf

# Show available data files
analyzer-tools --show-data
```

## What This Package Does

- **Data Quality Assessment** — Check partial data consistency before combining
- **Model Fitting** — Fit reflectivity data to theoretical models with uncertainty analysis
- **Automated Reporting** — Generate Markdown reports with plots
- **Model Management** — Create and modify fitting models
- **Experiment Planning** — Optimize experimental parameters using information theory
- **Time-Resolved Reduction** — EIS interval extraction and Mantid event filtering (via Docker)
- **Data Packaging** — Export time-resolved datasets to Parquet/Iceberg format
- **MCP Server** — Expose all tools to LLMs via the Model Context Protocol


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

### Docker (full stack, including Mantid)

The Docker image uses [pixi](https://pixi.sh) to install Mantid and
[lr_reduction](https://github.com/neutrons/LiquidsReflectometer) from conda
channels, then installs analyzer-tools via pip.

```bash
docker compose build
docker compose run analyzer bash          # interactive shell
docker compose run analyzer run-fit 218281 cu_thf
docker compose up mcp                     # start MCP server
docker compose run test                   # run tests
```

Output files are available on your host via volume mounts (`data/`, `models/`,
`reports/`, `results/`).


## Project Structure

```
analyzer_tools/
├── cli.py                  # Click CLI and entry point wrappers
├── mcp_server.py           # FastMCP server (LLM tool integration)
├── config_utils.py         # Centralized config.ini reader
├── registry.py             # Tool catalog for CLI discovery
├── schemas.py              # Pydantic output schemas for MCP
├── analysis/               # Core analysis tools
│   ├── partial_data_assessor.py
│   ├── run_fit.py
│   ├── result_assessor.py
│   ├── create_model_script.py
│   ├── create_temporary_model.py
│   ├── eis_interval_extractor.py
│   └── plot_time_series.py
├── reduction/              # Mantid-based reduction (optional)
│   ├── core.py             # Shared reduction engine
│   ├── event_filter.py     # EIS event filtering
│   ├── simple_reduction.py # Single-run reduction CLI
│   └── eis_reduce_events.py# Time-resolved reduction CLI
├── planner/                # Experiment design optimization
│   ├── cli.py
│   ├── experiment_design.py
│   ├── optimizer.py
│   └── report.py
└── utils/
    ├── iceberg_packager.py # Parquet/Iceberg export
    ├── model_utils.py
    └── summary_plots.py
```


## CLI Commands

All commands are installed as entry points via `pip install -e .`:

| Command | Purpose |
|---------|---------|
| `analyzer-tools` | Main CLI — list tools, workflows, data, get help |
| `run-fit` | Fit combined data to a model |
| `assess-partial` | Assess partial data overlap quality |
| `assess-result` | Evaluate fit quality and uncertainties |
| `create-model` | Generate a fit script from a model |
| `eis-intervals` | Extract EIS timing intervals to JSON |
| `iceberg-packager` | Package tNR data into Parquet files |
| `analyzer-planner` | Experiment design optimization |
| `analyzer-mcp` | Start the MCP server |
| `simple-reduction` | Mantid single-run reduction (Docker) |
| `eis-reduce-events` | Mantid time-resolved reduction (Docker) |

```bash
# Discovery
analyzer-tools --list-tools        # all tools with descriptions
analyzer-tools --help-tool partial # detailed help for a tool
analyzer-tools --workflows         # analysis workflow guides
analyzer-tools --show-data         # available data files
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
run-fit 218281 cu_thf                     # fit the data
assess-result 218281 cu_thf               # evaluate fit quality
```

### 3. Parameter Exploration
```bash
create-temporary-model cu_thf cu_thf_wide --adjust 'Cu thickness 300,1000'
run-fit 218281 cu_thf_wide
assess-result 218281 cu_thf_wide
```

### 4. Experiment Planning
```bash
analyzer-planner optimize \
  --data-file data/combined/REFL_218386_combined_data_auto.txt \
  --model-file models/cu_thf_planner \
  --param "THF rho" --param-values "4.0,5.0,6.0" \
  --output-dir results/planning
```

### 5. Time-Resolved Reduction (Docker)
```bash
docker compose run analyzer eis-intervals --data-dir /app/data/eis -o intervals.json
docker compose run analyzer eis-reduce-events \
  --event-file /app/data/events.h5 \
  --template /app/data/template.xml \
  --intervals intervals.json \
  --output-dir /app/results/tnr
```


## Models

Models are Python files in `models/` that define a `create_fit_experiment()` function
returning a `refl1d.experiment.Experiment`.

Available models: `cu_thf`, `cu_thf_no_oxide`, `cu_thf_tiny`, `cu_thf_planner`,
`ionomer_sld_1`, `ionomer_sld_2`, `ionomer_sld_3`.

```bash
# Create a refl1d-compatible fit script
create-model cu_thf data.txt

# Copy an existing model as a starting point
cp models/cu_thf.py models/my_model.py
```


## MCP Server (AI Assistant Integration)

The MCP server exposes analysis tools to LLMs via the
[Model Context Protocol](https://modelcontextprotocol.io/).

### Claude Desktop / VS Code Copilot

Add to your MCP configuration (e.g. `mcp.json` or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "analyzer-tools": {
      "command": "fastmcp",
      "args": ["run", "analyzer_tools/mcp_server.py"],
      "cwd": "/path/to/analyzer",
      "env": {
        "PYTHONPATH": "/path/to/analyzer"
      }
    }
  }
}
```

Replace `/path/to/analyzer` with the absolute path to this repository.

Available MCP tools: `run_fit`, `assess_partial_data`, `extract_eis_intervals`,
`list_available_data`, `list_available_models`.

```bash
# Run the server manually for testing
analyzer-mcp
```


## Getting Help

```bash
analyzer-tools --list-tools            # all tools
analyzer-tools --help-tool <name>      # detailed help for one tool
analyzer-tools --workflows             # step-by-step workflow guides
analyzer-tools --show-data             # available data files
```

See [docs/developer_notes.md](docs/developer_notes.md) for development guidelines.


## Contributing

1. Follow the test-driven development approach in `docs/developer_notes.md`
2. Update the tool registry (`registry.py`) when adding new tools
3. Run tests: `pytest`
4. Keep CLI entry points in sync in `pyproject.toml`
