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

## Package Structure (July 11, 2025)

The project has been restructured as a proper Python package named `analyzer_tools`:

### Key Changes:

- **New package structure**: All tools moved from `tools/` to `analyzer_tools/` package
- **Added `pyproject.toml`**: Modern Python packaging with proper metadata and dependencies
- **CLI commands**: Available via entry points: `run-fit`, `assess-partial`, `create-model`
- **Import paths**: Use `from analyzer_tools import ...` instead of `from tools import ...`
- **Installation**: Package can be installed with `pip install -e .` for development

### Usage Examples:

```python
# Import functions directly
from analyzer_tools import execute_fit, assess_result

# Import modules
from analyzer_tools import result_assessor
from analyzer_tools.utils import summary_plots
```

### CLI Usage:

```bash
# Run a fit (when CLI is properly installed)
run-fit 218386 cu_thf

# Or use Python modules directly
python analyzer_tools/run_fit.py 218386 cu_thf
```

## Configuration

The file naming convention for combined data files has been abstracted to a template in `config.ini`. The `run_fit.py` script now uses the `combined_data_template` from the config file to determine the data file name.

## Testing

The test suite has been updated to use pytest consistently. Tests now use standard `assert` statements and pytest fixtures for setup and teardown. A test for `create_temporary_model.py` has been added, and the test for `create_model_script.py` has been fixed to ensure it runs correctly and allows for coverage reporting.

### Recent Test Fixes (July 11, 2025)

Fixed import issues and Python 3.9 compatibility:

- Fixed relative import in `result_assessor.py` from `from utils import summary_plots` to `from .utils import summary_plots`
- Fixed Python 3.9 compatibility in `model_utils.py` by updating type hint from `QProbe | None` to `"QProbe | None"` (union syntax requires Python 3.10+)
- Fixed regex warning in `result_assessor.py` by using raw string for pattern with `\Z` escape sequence
- Fixed regex warnings in `summary_plots.py` and `partial_data_assessor.py` by using raw strings
- Updated test mocks to use correct `analyzer_tools` import paths
- All tests now pass without warnings

## Continuous Integration

A GitHub Actions workflow has been added to automatically run the test suite on every push and pull request to the `main` branch. The workflow is defined in `.github/workflows/python-test.yml`
