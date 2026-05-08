---
name: data-packaging
description: >
  Package time-resolved neutron reflectometry (tNR) data with EIS timing
  into Parquet files for Apache Iceberg data lakehouse. Covers the
  iceberg-packager tool.
  USE FOR: creating analysis-ready Parquet datasets from reduced tNR data,
  combining reflectivity data with EIS metadata, preparing data for downstream
  analytics.
  DO NOT USE FOR: reducing raw data (see time-resolved skill) or fitting
  (see fitting skill).
---

# Data Packaging for Iceberg

## When to Use

After completing time-resolved reduction (see the time-resolved skill), use the
Iceberg packager to combine reduced reflectivity files with EIS timing metadata
into a structured Parquet dataset suitable for a data lakehouse.

## Prerequisites

You need three inputs, all produced by earlier workflow stages:

1. **Split file** — JSON from `eis-intervals` (with `--hold-interval` for hold periods)
2. **Reduced directory** — folder of `.txt` reflectivity files from `eis-reduce-events`
3. **Reduction template** — the XML file used during reduction

## Usage

```bash
iceberg-packager <SPLIT_FILE> <REDUCED_DIR> <TEMPLATE_FILE> [-o output.parquet]
```

**Example:**
```bash
iceberg-packager \
  intervals.json \
  results/tnr/reduced \
  template.xml \
  -o results/tnr/tnr_dataset.parquet
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `SPLIT_FILE` | (required) | Path to intervals JSON file |
| `REDUCED_DIR` | (required) | Directory containing reduced `.txt` files |
| `TEMPLATE_FILE` | (required) | Path to reduction template XML |
| `-o, --output` | `{REDUCED_DIR}/tnr_data.parquet` | Output Parquet file path |
| `--validate-only` | — | Only validate inputs, skip packaging |

## Output Files

### Main data file (`tnr_data.parquet`)

One row per reflectivity file:

| Column | Type | Description |
|--------|------|-------------|
| `run_number` | int | Neutron run number |
| `filename` | string | Reduced file name |
| `n_points` | int | Number of data points |
| `Q`, `R`, `dR`, `dQ` | array[float] | Reflectivity data columns |
| `Q_min`, `Q_max` | float | Q range |
| `R_min`, `R_max` | float | R range |
| `interval_label` | string | EIS interval label |
| `interval_type` | string | `"eis"` or `"hold"` |
| `interval_start`, `interval_end` | string | ISO 8601 timestamps |
| `duration_seconds` | float | Interval duration |
| `hold_index` | int | Index for hold intervals |

### Metadata file (`tnr_data_metadata.parquet`)

Experiment-level metadata including run number, total duration, number of
intervals, source directory, reduction template (raw XML), and the full
intervals JSON.

## Validation

Use `--validate-only` to check that all inputs exist and are readable
without creating output:

```bash
iceberg-packager intervals.json reduced/ template.xml --validate-only
```

## Complete Pipeline Example

```bash
# 1. Extract EIS intervals with hold periods
eis-intervals --data-dir ./eis-data --hold-interval 30 -o intervals.json

# 2. Reduce events (Docker)
docker compose run analyzer eis-reduce-events \
  --intervals /app/data/intervals.json \
  --event-file /app/data/REF_L_218389.nxs.h5 \
  --template /app/data/template.xml \
  --output-dir /app/results/tnr

# 3. Package for Iceberg
iceberg-packager \
  intervals.json \
  results/tnr \
  template.xml \
  -o results/tnr/tnr_dataset.parquet
```

## Reference

See [docs/iceberg.md](docs/iceberg.md) for detailed requirements, naming
conventions, and the full Parquet schema specification.
