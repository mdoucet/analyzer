# Mantid Scripts for EIS-Correlated Neutron Data

These scripts are designed to run on a Mantid cluster or MantidWorkbench to filter
and reduce neutron scattering data based on EIS (Electrochemical Impedance Spectroscopy)
measurement intervals.

## Prerequisites

- Mantid Framework
- `lr_reduction` package (for reduction scripts)
- NumPy, Matplotlib

## Workflow

### Step 1: Extract EIS Intervals (on any machine)

Use the `eis-measurement-splitter` tool to extract timing intervals from EIS files:

```bash
eis-measurement-splitter --data-dir /path/to/eis/data --output intervals.json
```

This produces a JSON file like:

```json
{
  "source_directory": "/path/to/eis/data",
  "pattern": "*C02_?.mpt",
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

### Step 2: Filter Events (on Mantid cluster)

Copy `intervals.json` and the scripts to the Mantid cluster, then run:

```bash
python eis_filter_events.py \
    --intervals intervals.json \
    --event-file /SNS/REF_L/IPTS-XXXXX/nexus/REF_L_12345.nxs.h5 \
    --output-dir ./filtered_events
```

This will:
- Load the neutron event data
- Filter events by EIS measurement intervals
- Save each filtered workspace as a NeXus file

### Step 3: Filter + Reduce Events (on Mantid cluster)

For full reduction using LiquidsReflectometer templates:

```bash
python eis_reduce_events.py \
    --intervals intervals.json \
    --event-file /SNS/REF_L/IPTS-XXXXX/nexus/REF_L_12345.nxs.h5 \
    --template /SNS/REF_L/IPTS-XXXXX/shared/templates/template.xml \
    --output-dir ./reduced_data
```

This will:
- Load and filter neutron events
- Apply dead time correction
- Reduce each slice using the template
- Save reflectivity data as text files (Q, R, dR, dQ)
- Create a summary plot

## Script Options

### eis_filter_events.py

| Option | Description |
|--------|-------------|
| `--intervals` | Path to JSON file with EIS measurement intervals (required) |
| `--event-file` | Path to neutron event data file (required) |
| `--output-dir` | Directory for output files (default: `./filtered_events`) |
| `--prefix` | Prefix for output workspace names (default: `eis_measurement`) |

### eis_reduce_events.py

| Option | Description |
|--------|-------------|
| `--intervals` | Path to JSON file with EIS measurement intervals (required) |
| `--event-file` | Path to neutron event data file (required) |
| `--template` | Path to reduction template file (required) |
| `--output-dir` | Directory for output files (default: `./reduced_data`) |
| `--scan-index` | Scan index within the template (default: 1) |
| `--theta-offset` | Theta offset for reduction (default: 0.0) |
| `--no-plot` | Skip creating summary plot |
