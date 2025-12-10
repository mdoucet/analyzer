# Time-Resolved EIS Data Processing

We have developed tools to retrieve timing information from EIS impedance spectroscopy data and correlate it with neutron scattering event data.

## Data Location
- **EIS data directory**: `/Users/m2d/data/expt11/ec-data`
- **Relevant files**: `*C02_?.mpt` (excludes files containing "fit")

## Data Format
The EIS files are ASCII data with multiple columns. The first four columns are important:
- `freq/Hz`: Frequency in Hertz
- `Re(Z)/Ohm`: Real part of impedance
- `-Im(Z)/Ohm`: Negative imaginary part of impedance
- `|Z|/Ohm`: Absolute impedance

Each row represents a measurement at a different frequency. The `time/s` column contains the cumulative time it took to perform all measurements up to that row.

---

## Available Tools

### 1. EIS Timing Extractor (`eis_timing_extractor.py`)

Extracts timing information from EIS `.mpt` files and computes wall clock times for each measurement.

**Usage:**
```bash
# Process a single file
python analyzer_tools/eis_timing_extractor.py --file data.mpt --output timing.csv

# Process all files in a directory
python analyzer_tools/eis_timing_extractor.py --data-dir /path/to/eis/data --output-dir ./output

# Show timing boundaries
python analyzer_tools/eis_timing_extractor.py --data-dir /path/to/eis/data --boundaries
```

**Output:**
- CSV file with original columns plus:
  - `cumulative_time_s`: Cumulative time from start (seconds)
  - `wall_clock_time`: Wall clock time in ISO 8601 format

### 2. Mantid Event Splitter (`mantid_event_splitter.py`)

Generates Mantid scripts to split neutron event data based on **individual frequency measurements** from EIS files.

**Usage:**
```bash
# Generate filtering script (absolute time)
python analyzer_tools/mantid_event_splitter.py \
    --timing-file timing.csv \
    --event-file /path/to/events.nxs.h5 \
    --output-script mantid_filter.py

# Generate filtering script (relative time)
python analyzer_tools/mantid_event_splitter.py \
    --timing-file timing.csv \
    --event-file /path/to/events.nxs.h5 \
    --output-script mantid_filter.py \
    --relative
```

**Output:**
- Standalone Python script for Mantid
- Creates one time interval per frequency measurement
- For 10 files with 43 frequencies each → 430 intervals

### 3. EIS Measurement Splitter (`eis_measurement_splitter.py`)

Generates Mantid scripts to split neutron event data based on **complete EIS measurement intervals**. Supports two modes:
1. **Filtering mode** (default): Splits events and saves filtered workspaces
2. **Reduction mode** (`--reduce`): Splits events AND reduces each slice using the LiquidsReflectometer workflow

**Key Difference**: Each EIS file becomes ONE time interval (from acquisition start to end of last measurement), rather than splitting by individual frequencies.

**Usage - Filtering Only:**
```bash
# Generate filtering script (absolute time)
python analyzer_tools/eis_measurement_splitter.py \
    --data-dir /path/to/eis/data \
    --event-file /path/to/events.nxs.h5 \
    --output-script mantid_filter.py

# Generate filtering script (relative time)
python analyzer_tools/eis_measurement_splitter.py \
    --data-dir /path/to/eis/data \
    --event-file /path/to/events.nxs.h5 \
    --output-script mantid_filter.py \
    --relative
```

**Usage - Filtering + Reduction:**
```bash
# Generate reduction script (filter, reduce, and save reflectivity curves)
python analyzer_tools/eis_measurement_splitter.py \
    --data-dir /path/to/eis/data \
    --event-file /path/to/events.nxs.h5 \
    --output-script mantid_reduce.py \
    --reduce \
    --template /path/to/reduction_template.xml

# With additional options
python analyzer_tools/eis_measurement_splitter.py \
    --data-dir /path/to/eis/data \
    --event-file /path/to/events.nxs.h5 \
    --output-script mantid_reduce.py \
    --reduce \
    --template /path/to/template.xml \
    --scan-index 5 \
    --theta-offset 0.01 \
    --no-plot
```

**Output (Filtering mode):**
- Standalone Python script for Mantid
- Creates one time interval per EIS file
- Saves filtered workspaces as NeXus files

**Output (Reduction mode):**
- Standalone Python script for Mantid with lr_reduction dependency
- Creates one time interval per EIS file
- Reduces each filtered workspace using `template.process_from_template_ws()`
- Saves reflectivity data as text files (Q, R, dR, dQ)
- Creates a summary plot of all reduced curves
- Saves reduction metadata as JSON

---

## Workflow Comparison

### Option A: Frequency-Level Splitting (Fine-Grained)

1. Extract detailed timing data:
   ```bash
   python analyzer_tools/eis_timing_extractor.py \
       --data-dir /Users/m2d/data/expt11/ec-data \
       --output-dir ./eis_output
   ```

2. Generate Mantid script with frequency-level intervals:
   ```bash
   python analyzer_tools/mantid_event_splitter.py \
       --timing-file ./eis_output/sequence_1_..._timing.csv \
       --event-file /SNS/REF_L/IPTS-34347/nexus/REF_L_12345.nxs.h5 \
       --output-script mantid_frequency_filter.py
   ```

3. Execute in Mantid environment

**Result**: High temporal resolution, many output files

### Option B: Measurement-Level Splitting (Coarse-Grained)

1. Generate Mantid script directly from EIS files:
   ```bash
   python analyzer_tools/eis_measurement_splitter.py \
       --data-dir /Users/m2d/data/expt11/ec-data \
       --event-file /SNS/REF_L/IPTS-34347/nexus/REF_L_12345.nxs.h5 \
       --output-script mantid_measurement_filter.py
   ```

2. Execute in Mantid environment

**Result**: One filtered dataset per EIS measurement, easier to manage

---

## Implementation Notes

### Acquisition Start Time

The wall clock time is calculated using the header line:
```
Acquisition started on : 04/20/2025 10:55:16.521
```

### Time Intervals

- **Frequency-level**: Each interval corresponds to one row in the EIS file (one frequency measurement)
- **Measurement-level**: Each interval spans from acquisition start to the completion of the last frequency measurement

### Mantid Filtering

The generated scripts use Mantid's `FilterEvents` algorithm with:
- **Absolute time mode** (default): Times relative to GPS epoch (1990-01-01)
- **Relative time mode** (optional): Times relative to run start

### Output Files

Filtered workspaces are saved as NeXus files (`.nxs`) with descriptive names based on the source EIS files.

---

## Example: Processing expt11 Data

### Basic Workflow (Filter and Save Workspaces)

```bash
# Step 1: Extract timing boundaries to review
python analyzer_tools/eis_timing_extractor.py \
    --data-dir /Users/m2d/data/expt11/ec-data \
    --boundaries

# Step 2: Generate measurement-level filtering script
python analyzer_tools/eis_measurement_splitter.py \
    --data-dir /Users/m2d/data/expt11/ec-data \
    --event-file /SNS/REF_L/IPTS-34347/nexus/REF_L_12345.nxs.h5 \
    --output-script mantid_expt11_filter.py \
    --output-dir ./filtered_neutron_data

# Step 3: Execute in Mantid (on analysis cluster or MantidWorkbench)
python mantid_expt11_filter.py
```

This will create 9 filtered neutron datasets, one for each EIS measurement sequence.

### Full Reduction Workflow (Filter, Reduce, and Save Reflectivity)

```bash
# Step 1: Generate reduction script with reduction workflow
python analyzer_tools/eis_measurement_splitter.py \
    --data-dir /Users/m2d/data/expt11/ec-data \
    --event-file /SNS/REF_L/IPTS-34347/nexus/REF_L_12345.nxs.h5 \
    --output-script mantid_expt11_reduce.py \
    --reduce \
    --template /SNS/REF_L/IPTS-34347/shared/templates/expt11_template.xml \
    --output-dir ./reduced_reflectivity

# Step 2: Execute in Mantid environment with lr_reduction installed
python mantid_expt11_reduce.py
```

This will:
1. Load the neutron event data
2. Apply dead time correction
3. Filter events into 9 intervals (one per EIS measurement)
4. Reduce each interval using the LiquidsReflectometer workflow
5. Save each reflectivity curve as a text file (Q, R, dR, dQ)
6. Create a summary plot showing all 9 reflectivity curves
7. Save reduction metadata as JSON

**Output files:**
- `reduced_reflectivity/r12345_sequence_1_*.txt` - Reflectivity data
- `reduced_reflectivity/r12345_eis_summary.png` - Summary plot
- `reduced_reflectivity/r12345_eis_reduction.json` - Metadata
- `reduced_reflectivity/reduction_options.json` - Reproducibility info





