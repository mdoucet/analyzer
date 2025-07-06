# Developer Notes

## Tools

### `create_model_script.py`

This tool generates a fit script by combining a model file with fitting commands. It now accepts optional arguments for the models directory, and output directory.

**Example:**

```bash
python3 tools/create_model_script.py my_model my_data.dat --model_dir /path/to/models --output_dir /path/to/output
```

### `create_temporary_model.py`

This tool allows for the creation of temporary models with adjusted parameter ranges. It takes a base model, a new model name, and a list of parameter adjustments as input. It then creates a new model file with the specified adjustments.

**Example:**

```bash
python3 tools/create_temporary_model.py cu_thf cu_thf_temp --adjust Cu thickness 500,800
```

## Configuration

The file naming convention for combined data files has been abstracted to a template in `config.ini`. The `run_fit.py` script now uses the `combined_data_template` from the config file to determine the data file name.

## Testing

The test suite has been updated to use pytest consistently. Tests now use standard `assert` statements and pytest fixtures for setup and teardown. A test for `create_temporary_model.py` has been added, and the test for `create_model_script.py` has been fixed to ensure it runs correctly and allows for coverage reporting.
