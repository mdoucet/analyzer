# Time-Resolved EIS Data Processing

Tools to correlate EIS (Electrochemical Impedance Spectroscopy) timing with neutron scattering event data.

## Overview

The workflow is designed to be run in two stages:
1. **Extract EIS intervals** (can run on any machine)
2. **Filter/reduce neutron events** (must run on Mantid cluster)

## Data Format

EIS files (`.mpt`) are EC-Lab ASCII format with:
- Header containing `Acquisition started on : MM/DD/YYYY HH:MM:SS.fff`
- Tab-separated data with `time/s` column for elapsed time

---

## Step 1: Extract EIS Intervals

Use `eis-intervals` to extract timing from EIS files into JSON:

```bash
eis-intervals --data-dir /path/to/eis/data --output intervals.json
```

This produces:
```json
{
  "source_directory": "/path/to/eis/data",
  "n_intervals": 9,
  "intervals": [
    {
      "filename": "sequence_1_..._PEIS_C02_1.mpt",
      "start": "2025-04-20T10:55:16.521000",
      "end": "2025-04-20T11:05:06.361862",
      "duration_seconds": 589.84
    },
    ...
  ]
}
```

### Options

| Option | Description |
|--------|-------------|
| `--data-dir` | Directory containing EIS `.mpt` files (required) |
| `--pattern` | Glob pattern to match files (default: `*C02_?.mpt`) |
| `--exclude` | Exclude files containing this string (default: `fit`) |
| `--output` | Output JSON file path (prints to stdout if not specified) |
| `--quiet` | Suppress progress messages |

---

## Step 2: Process on Mantid Cluster

Copy `intervals.json` and the scripts from `scripts/mantid/` to the cluster.

### Option A: Filter Events Only

```bash
python eis_filter_events.py \
    --intervals intervals.json \
    --event-file /SNS/REF_L/IPTS-XXXXX/nexus/REF_L_12345.nxs.h5 \
    --output-dir ./filtered_events
```

Outputs:
- One NeXus file per EIS interval

### Option B: Filter + Reduce

```bash
python eis_reduce_events.py \
    --intervals intervals.json \
    --event-file /SNS/REF_L/IPTS-XXXXX/nexus/REF_L_12345.nxs.h5 \
    --template /SNS/REF_L/IPTS-XXXXX/shared/templates/template.xml \
    --output-dir ./reduced_data
```

Outputs:
- Reflectivity text files (Q, R, dR, dQ) per interval
- Summary plot (`*_eis_summary.png`)
- Reduction metadata JSON

---

## Complete Example

```bash
# On your local machine (with EIS data access)
eis-intervals \
    --data-dir /Users/m2d/data/expt11/ec-data \
    --output intervals.json

# Copy to Mantid cluster, then run:
python eis_reduce_events.py \
    --intervals intervals.json \
    --event-file /SNS/REF_L/IPTS-34347/nexus/REF_L_218281.nxs.h5 \
    --template /SNS/REF_L/IPTS-34347/shared/templates/expt11.xml \
    --output-dir ./expt11_reduced
```

---

## Files

| File | Location | Description |
|------|----------|-------------|
| `eis_interval_extractor.py` | `analyzer_tools/` | Extracts intervals → JSON |
| `eis_filter_events.py` | `scripts/mantid/` | Mantid script for filtering |
| `eis_reduce_events.py` | `scripts/mantid/` | Mantid script for reduction |

---

## Resolution Modes

The `eis-intervals` tool supports two resolution modes:

### Per-File (Default)
One interval per EIS file - good for reduction workflows:
```bash
eis-intervals --data-dir /path/to/eis/data --resolution per-file
```

### Per-Frequency
One interval per frequency measurement - for detailed analysis:
```bash
eis-intervals --data-dir /path/to/eis/data --resolution per-frequency
```





