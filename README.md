# Neutron Reflectometry Analysis

This package provides a suite of tools for analyzing neutron reflectometry data. It is designed to help scientists fit experimental data to theoretical models and assess the quality of the data.

## Overview

Neutron reflectometry is a powerful technique for studying the structure of thin films and surfaces. This package provides the tools to:

*   **Assess the quality of partial data sets:** Before combining partial reflectivity curves, it's important to ensure they are consistent with each other. The `partial_data_assessor.py` tool helps with this by analyzing the overlap regions between partial data sets.
*   **Fit reflectivity data to models:** The `run_fit.py` tool allows you to fit your experimental data to a variety of theoretical models. The models are defined in the `models` directory.
*   **Generate reports:** The tools automatically generate markdown reports with plots and analysis results.

## Getting Started

### Prerequisites

*   Python 3
*   See `requirements.txt` for a list of required Python packages.

### Installation

1.  Clone this repository:
    ```bash
    git clone <repository-url>
    ```
2.  Install the required packages:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

## Configuration

The `config.ini` file is used to configure the paths for the data and results directories.

```ini
[paths]
# This is the top-level directory where the fit results will be stored
results_dir = /tmp/fits
# This is the directory containing your final reduced data
combined_data_dir = data/combined
# This is the directory containing the partial data, one file for each run
partial_data_dir = data/partial
# This is the directory where we will write the reports for each data set
reports_dir = reports
```
You can edit this file to change the default locations for your data and results.

## Data files
This package is currently geared towards using automatically reduced data from the
Liquids Reflectometer at SNS. By default, it will assume that fully reduced reflectivity
data are stored in files named `REFL_<set_ID>_combined_data_auto.txt`, where `set_ID`
is the first run number of a set.

## Partial data files
These are the reduced data files before they are combined into the combined reduced file.
This is useful to assess data quality and see if the normalization was done properly.
It can also be used to fit data with an angle offset.

- The file names are `REFL_<set_ID>_<part_ID>_<run_ID>_partial.txt`
- `part_ID` usually runs from 1 to 3. All the parts with the same `set_ID` belong together.
- The `set_ID` is usually the first `run_ID` of the set.



## Usage

### Assessing Partial Data

To assess the quality of a set of partial data files, use the `partial_data_assessor.py` tool. You need to provide the `set_id` of the data you want to analyze.

```bash
python3 tools/partial_data_assessor.py <set_id>
```

This will generate a report in the `reports` directory with a plot of the reflectivity curves and a metric for how well they match in the overlap regions.

### Running a Fit

To fit a reflectivity curve to a model, use the `run_fit.py` tool. You need to provide the `set_id` of the data and the name of the model you want to use.

```bash
python3 tools/run_fit.py <set_id> <model_name>
```

This will perform the fit and generate a report in the `reports` directory with plots of the fit and the resulting scattering length density (SLD) profile.

## Models

The theoretical models are defined as Python modules in the `models` directory. You can create your own models by adding a new Python file to this directory. Each model file must contain a `create_fit_experiment` function that returns a `refl1d.experiment.Experiment` object.

## Working with the Gemini CLI

You can also use the Gemini CLI to interact with this package. The Gemini CLI can help you with:

*   Answering questions about reflectometry data analysis.
*   Writing new analysis code and tools.
*   Running the existing tools to analyze data.

### Examples

Here are some examples of how you can use the Gemini CLI:

*   **Assess partial data:**
    > please run the partial data assessment tool for 218292

*   **Run a fit:**
    > run the fit for 218292 with model cu_thf

*   **Ask a question:**
    > what is the difference between `partial_data_assessor.py` and `result_assessor.py`?
