---
name: time-resolved
description: >
  Time-resolved neutron reflectometry with EIS correlation — extract timing
  intervals from EIS data, reduce neutron events by time slice, and process
  time-resolved measurements. Covers eis-intervals, simple-reduction, and
  eis-reduce-events tools.
  USE FOR: extracting EIS timing, reducing neutron event data, time-resolved
  analysis workflows.
  DO NOT USE FOR: fitting reduced data (see fitting skill) or data packaging
  (see data-packaging skill).
---

# Time-Resolved EIS/Neutron Workflow

## Overview

This workflow correlates Electrochemical Impedance Spectroscopy (EIS) timing
with neutron reflectometry event data to produce time-resolved reflectivity
curves. It runs in stages:

1. **Extract EIS intervals** → JSON timing file (runs anywhere)
2. **Reduce neutron events** → reflectivity curves per time slice (requires Mantid)

## Stage 1: Extract EIS Intervals

### What it does

Parses EC-Lab `.mpt` files to extract timing boundaries for each EIS measurement,
producing a JSON file that maps wall-clock times to measurement intervals.

### Usage

```bash
eis-intervals --data-dir /path/to/eis/data -o intervals.json
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--data-dir` | (required) | Directory containing `.mpt` files |
| `--pattern` | `*C02_[0-9]*.mpt` | Glob pattern to match EIS files |
| `--exclude` | `fit` | Exclude files containing this string |
| `--resolution` | `per-file` | `per-file` (one interval per file) or `per-frequency` (one per measurement) |
| `--hold-interval` | — | Generate hold intervals of this duration (seconds) between EIS files |
| `-o, --output` | stdout | Output JSON file path |
| `-q, --quiet` | — | Suppress progress messages |

### Resolution modes

- **`per-file`** (default): One interval per EIS file — use for reduction workflows
- **`per-frequency`**: One interval per frequency measurement — for detailed analysis

### Hold intervals

Use `--hold-interval` to create intervals during gaps between EIS measurements
(e.g., during potentiostatic hold periods):

```bash
eis-intervals --data-dir ./eis-data --hold-interval 30 -o intervals.json
```

### Output JSON structure

```json
{
  "source_directory": "/path/to/eis/data",
  "pattern": "*C02_[0-9]*.mpt",
  "resolution": "per-file",
  "n_intervals": 12,
  "intervals": [
    {
      "label": "eis_1",
      "filename": "sequence_1_..._PEIS_C02_1.mpt",
      "interval_type": "eis",
      "start": "2025-04-20T10:55:16.521000",
      "end": "2025-04-20T11:05:06.361862",
      "duration_seconds": 589.84,
      "n_frequencies": 51
    },
    {
      "label": "hold_gap_1_0",
      "interval_type": "hold",
      "start": "2025-04-20T11:05:06.361862",
      "end": "2025-04-20T11:05:36.361862",
      "duration_seconds": 30.0
    }
  ]
}
```

## Stage 2: Reduce Neutron Events

Two reduction approaches are available, both requiring Mantid (typically via Docker):

### Option A: Simple reduction (full duration)

Reduces the entire event file without time-slicing:

```bash
simple-reduction \
  --event-file REF_L_218386.nxs.h5 \
  --template template.xml \
  --output-dir ./reduced
```

Uses `lr_reduction.workflow.reduce()` to produce combined reflectivity.

**Output files:**
- `REFL_{run}_combined_data_auto.txt` — combined reflectivity
- `reflectivity.txt` — copy of combined file
- `.last_reduced_set` — metadata (run number)

### Option B: EIS time-resolved reduction

Splits events by EIS interval boundaries and reduces each slice:

```bash
eis-reduce-events \
  --intervals intervals.json \
  --event-file REF_L_218389.nxs.h5 \
  --template template.xml \
  --output-dir ./reduced_data
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--intervals` | (required) | JSON file from `eis-intervals` |
| `--event-file` | (required) | NeXus/HDF5 event data file |
| `--template` | (required) | Reduction template XML |
| `--output-dir` | `./reduced_data` | Output directory |
| `--scan-index` | `1` | Scan index within the template |
| `--theta-offset` | `0.0` | Theta offset for reduction |
| `--tz-offset` | `5.0` | Timezone offset (hours from UTC, e.g., 5.0 for EST) |
| `-v, --verbose` | — | Debug logging |

**Output files:**
- `r{RUN}_{LABEL}.txt` — reflectivity per interval (4 columns: Q, R, dR, dQ)
- `r{RUN}_eis_reduction.json` — reduction metadata with interval details
- `reduction_options.json` — all parameters for reproducibility

## Docker Usage

Reduction tools require Mantid. Use Docker:

```bash
# Simple reduction
docker compose run analyzer simple-reduction \
  --event-file /app/data/REF_L_218386.nxs.h5 \
  --template /app/data/template.xml

# Time-resolved reduction
docker compose run analyzer eis-reduce-events \
  --intervals /app/data/intervals.json \
  --event-file /app/data/REF_L_218389.nxs.h5 \
  --template /app/data/template.xml \
  --output-dir /app/results/tnr
```

## Complete Example

```bash
# 1. Extract EIS intervals (local machine)
eis-intervals \
  --data-dir /Users/m2d/data/expt11/ec-data \
  --hold-interval 30 \
  -o intervals.json

# 2. Reduce events by time slice (Docker/Mantid cluster)
docker compose run analyzer eis-reduce-events \
  --intervals /app/data/intervals.json \
  --event-file /app/data/REF_L_218389.nxs.h5 \
  --template /app/data/template.xml \
  --output-dir /app/results/tnr

# 3. Fit individual time slices (local machine)
run-fit 218389 cu_thf
```

## Reference

See [docs/time-resolved-eis.md](docs/time-resolved-eis.md) for detailed EIS data format documentation and cluster workflow examples.
