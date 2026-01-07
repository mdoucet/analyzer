# Packaging EIS and tNR data for a data lakehouse
We want to package AI-ready data from EIS and time-resolved neutron reflectometry (tNR). Neutron reflectometry is a neutron scattering technique to study interfacial structure. This data come from impedance spectroscopy (EIS) taken while measuring neutron reflectometry. The neutron data is stored in a single data file. The information about each scattered neutron event (position on the detector, time of acquisition, etc...) is stored in this file. One of our tools in this project allows us to extract time splits (sometimes called slices) from the EIS data. This is stored in a split file. We then use this split file as input to what we call the "data reduction" process. This is a two-part process done in the scripts/eis_reduce_events.py script. We first sort all the neutron events according to the splits, then use the standard data reduction process to extract the reflectivity data from the neutron events. That process requires so-called reduction parameters, which are captured in a "reduction template" file.

What we need here is to package the output data for ingestion in a data lakehouse.


## Available data:
- location: $USER/git/experiments-2025/jen-apr2025/data/tNR
- The example json file expt11-splits-per-file-w-hold.json gives an example of time splits derived from EIS data (see data/tNR/README.md file for the call used to produce it).
- The data in the data/tNR/reduced folder are the corresponding reflectivity files, one for each split.
- The reflectivity data was produced using the parameters in REF_L_sample_6_tNR.xml (see command in the data/tNR/README.md file).

## Naming convention:
- *Split file* is the json file produced by our `eis_interval_extractor.py` tool. In this example it is expt11-splits-per-file-w-hold.json.
- *reduced files* are the reflectivity files, which are 4-column ASCII files: Q, R, dR, dQ
- *reduction template* is the xml file that contains all the information needed to reduce/process the raw data for each split. In this example it is REF_L_sample_6_tNR.xml.


## Requirements:
- Extract metadata from the expt11-splits-per-file-w-hold.json
- In the data/tNR/reduced folder, there is a json file named r218389_eis_reduction.json. One of the outputs of the data reduction is a file that ends in _eis_reduction.json, it contains important metadata that also needs to be extracted.
- Package the reduced data in the .txt files. All these files have 4 columns: Q, R, dR, dQ. You cannot assume that all these files have the same number if rows.
- Store the packaged reduced data, the meta data, the raw xml file into a parquet file for Iceberg.

---

## Implementation: Iceberg Packager Tool

The `iceberg_packager.py` tool packages tNR data with EIS timing information into Parquet files for Apache Iceberg.

### Installation

```bash
pip install -e .
```

This installs the `iceberg-packager` command-line tool.

### Usage

```bash
iceberg-packager <split_file> <reduced_dir> <template_file> [-o output.parquet]
```

**Arguments:**
- `split_file` - Path to the split JSON file (e.g., `expt11-splits-per-file-w-hold.json`)
- `reduced_dir` - Path to directory containing reduced `.txt` files
- `template_file` - Path to the reduction template XML file

**Options:**
- `-o, --output` - Output Parquet file path (defaults to `<reduced_dir>/tnr_data.parquet`)
- `--validate-only` - Only validate inputs, do not create output

### Example

```bash
# Package the example data
iceberg-packager \
    data/tNR/expt11-splits-per-file-w-hold.json \
    data/tNR/reduced \
    data/tNR/REF_L_sample_6_tNR.xml \
    -o output/tnr_dataset.parquet
```

### Output Files

The tool generates two Parquet files:

#### 1. Main Data File (`tnr_data.parquet`)

Contains one row per reflectivity file with columns:

| Column | Type | Description |
|--------|------|-------------|
| `run_number` | int | Neutron run number |
| `filename` | string | Name of the reduced file |
| `filepath` | string | Full path to the reduced file |
| `n_points` | int | Number of data points in this file |
| `Q` | array[float] | Momentum transfer values |
| `R` | array[float] | Reflectivity values |
| `dR` | array[float] | Reflectivity uncertainties |
| `dQ` | array[float] | Q resolution values |
| `Q_min`, `Q_max` | float | Q range |
| `R_min`, `R_max` | float | R range |
| `interval_label` | string | EIS interval label (e.g., "hold_gap_1_0") |
| `interval_type` | string | Type: "hold" or "eis" |
| `interval_start` | string | ISO timestamp of interval start |
| `interval_end` | string | ISO timestamp of interval end |
| `duration_seconds` | float | Interval duration |
| `hold_index` | int | Hold index (for hold intervals) |

#### 2. Metadata File (`tnr_data_metadata.parquet`)

Contains experiment-level metadata:

| Column | Type | Description |
|--------|------|-------------|
| `run_number` | int | Neutron run number |
| `total_duration` | float | Total experiment duration (seconds) |
| `n_intervals` | int | Number of time intervals |
| `n_reduced_files` | int | Number of reduced reflectivity files |
| `source_directory` | string | Original EIS data location |
| `eis_pattern` | string | File pattern used for EIS files |
| `resolution` | string | Time resolution mode |
| `reduction_template_xml` | string | Full XML content of reduction template |
| `packaged_timestamp` | string | ISO timestamp of packaging |
| `packager_version` | string | Tool version |
| `intervals_json` | string | JSON array of all intervals |
| `split_metadata_json` | string | Full split file as JSON |
| `reduction_metadata_json` | string | Full reduction metadata as JSON |

### Iceberg Integration

The Parquet files are compatible with Apache Iceberg tables. Example schema registration:

```python
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, IntegerType, FloatType, ListType

catalog = load_catalog("my_catalog")

# Create table from parquet
catalog.create_table_from_parquet(
    identifier="neutron.tnr_reflectivity",
    parquet_path="output/tnr_dataset.parquet"
)
```