# Tools

This directory contains a suite of tools for analyzing neutron reflectometry data.

## `partial_data_assessor.py`

This tool is used to assess the quality of partial data sets. It takes a `set_id` as input and analyzes the overlap regions between the partial data files for that set.

### Usage

```bash
python3 tools/partial_data_assessor.py <set_id>
```

### Output

*   A plot of the reflectivity curves for the partial data sets, saved as `reflectivity_curve_<set_id>.svg` in the `reports` directory.
*   An updated report file, `report_<set_id>.md`, in the `reports` directory, containing the plot and a chi-squared metric for each overlap region.

## `run_fit.py`

This tool is used to fit a reflectivity curve to a model. It takes a `set_id` and a `model_name` as input.

### Usage

```bash
python3 tools/run_fit.py <set_id> <model_name>
```

### Output

*   A directory named `<set_id>_<model_name>` in the `results_dir` (defined in `config.ini`) containing the fit results.
*   Plots of the fit and the SLD profile, saved in the `reports` directory.
*   An updated report file, `report_<set_id>.md`, in the `reports` directory, with details of the fit.

## `create_temporary_model.py`

This tool allows you to create a new model with adjusted parameter ranges based on an existing model.

### Usage

```bash
python3 tools/create_temporary_model.py <base_model> <new_model> --adjust <layer> <parameter> <min,max>
```

### Example

```bash
python3 tools/create_temporary_model.py cu_thf cu_thf_temp --adjust Cu thickness 500,800
```

This will create a new model file named `cu_thf_temp.py` in the `models` directory, with the `Cu.thickness` parameter range set to (500, 800).

## `result_assessor.py`

This tool is used to assess the results of a fit. It is called automatically by `run_fit.py`, but can also be run manually.

### Usage

```bash
python3 tools/result_assessor.py <results_directory> <set_id> <model_name>
```

### Output

*   Plots of the fit and the SLD profile, saved in the `reports` directory.
*   An updated report file, `report_<set_id>.md`, in the `reports` directory, with details of the fit.
