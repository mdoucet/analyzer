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

### Configuration System Updates (July 12, 2025)

Fixed hard-coded path assumptions in the tool discovery system:

#### Problem Identified:
- New tool registry, welcome module, and documentation had hard-coded paths (`data/combined`, `data/partial`)
- This contradicted the configurable nature of the repository specified in `config.ini`
- Users with different data organization couldn't benefit from the discovery tools

#### Solution Implemented:

1. **Created `analyzer_tools/config_utils.py`**:
   - Centralized configuration management with `Config` class
   - Provides easy access to all configurable paths
   - Includes fallback defaults if config.ini doesn't exist
   - Thread-safe global config instance via `get_config()`

2. **Updated Tool Registry** (`registry.py`):
   - Now reads actual configured paths from `config.ini`
   - Shows real data locations and file templates in overview
   - Handles both package and standalone execution modes

3. **Updated Welcome Module** (`welcome.py`):
   - `show_available_data()` now uses configured paths
   - Displays actual data locations and templates
   - Gracefully handles missing directories

4. **Enhanced Documentation**:
   - README.md now emphasizes configurable nature
   - Shows how to customize data locations
   - Explains that all tools automatically use configured paths

#### Usage:

```python
# For tools and scripts
from analyzer_tools.config_utils import get_config
config = get_config()
combined_dir = config.get_combined_data_dir()

# For display/overview functions
from analyzer_tools.config_utils import get_data_organization_info
info = get_data_organization_info()
```

#### Verification:
- All discovery tools now properly reflect user's actual data organization
- Configuration changes are immediately reflected in tool overviews
- System works with any custom data directory structure
- Maintains backward compatibility with existing tools

This ensures the repository truly adapts to the user's data organization rather than assuming fixed paths.

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

## Code Coverage Integration (July 12, 2025)

Added code coverage reporting to the CI/CD pipeline and repository:

### Changes Made:

1. **Enhanced GitHub Actions Workflow** (`.github/workflows/python-test.yml`):
   - Added `pytest-cov` installation
   - Modified test command to include coverage reporting: `pytest --cov=analyzer_tools --cov-report=xml --cov-report=html --cov-report=term-missing`
   - Added Codecov integration with `codecov/codecov-action@v3`
   - Uploads coverage reports to Codecov automatically on every push/PR

2. **Added Coverage Configuration** (`.coveragerc`):
   - Configured to track `analyzer_tools` package
   - Excludes test files, cache, and hidden files from coverage
   - Generates both XML (for Codecov) and HTML (for local viewing) reports
   - Excludes common non-testable lines (like `if __name__ == '__main__':`)

3. **Updated README with Badges**:
   - Added GitHub Actions status badge
   - Added Codecov coverage badge
   - Badges provide quick visual status of build health and test coverage

### Current Coverage Status:
- **Baseline Coverage**: 20%
- **Well-tested modules**: `create_temporary_model.py` (91%), `partial_data_assessor.py` (85%)
- **Areas needing tests**: CLI interfaces, welcome module, config utilities

### Usage:

```bash
# Run tests with coverage locally
pytest --cov=analyzer_tools --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=analyzer_tools --cov-report=html
# View report: open htmlcov/index.html

# Generate XML for CI
pytest --cov=analyzer_tools --cov-report=xml
```

### Benefits:
- **Quality Assurance**: Tracks which code is tested
- **CI Integration**: Automatic coverage reporting on every commit
- **Progress Tracking**: Coverage badges show testing progress over time
- **Identifies Gaps**: Highlights untested code that may need attention

The coverage system helps maintain code quality and ensures new features include appropriate tests.

## Tool Discovery System (July 12, 2025)

### New User-Friendly Features

Added a comprehensive tool discovery system to make the repository accessible to new users and AI assistants:

#### Key Components:

1. **Tool Registry (`analyzer_tools/registry.py`)**:
   - Centralized catalog of all analysis tools with descriptions, usage examples, and data type requirements
   - Defines analysis workflows with step-by-step instructions
   - Provides programmatic access to tool information for AI assistants
   - Can be executed standalone to show tool overview

2. **Enhanced CLI (`analyzer_tools/cli.py`)**:
   - `--list-tools`: Shows comprehensive tool overview
   - `--help-tool <name>`: Detailed help for specific tools
   - `--workflows`: Displays analysis workflows
   - Handles both module and standalone execution

3. **Welcome Module (`analyzer_tools/welcome.py`)**:
   - `welcome()`: Displays welcome message and tool overview
   - `show_available_data()`: Shows what data is available for analysis
   - `quick_start()`: Provides quick start guides for different data types
   - `help_me_choose()`: Interactive tool selection helper

4. **Updated README.md**:
   - User-friendly quick start section
   - Comprehensive tool table with examples
   - Analysis workflow examples
   - AI assistant integration notes

#### Usage Examples:

```python
# For new users
from analyzer_tools.welcome import welcome
welcome()

# For AI assistants  
from analyzer_tools.registry import get_all_tools, get_workflows
tools = get_all_tools()
workflows = get_workflows()
```

```bash
# Command line discovery
python -m analyzer_tools.cli --list-tools
python -m analyzer_tools.cli --help-tool partial
python -m analyzer_tools.cli --workflows
```

#### Benefits:

- **User Onboarding**: New users can quickly discover available tools and workflows
- **AI Assistant Integration**: Provides structured tool information for AI assistants
- **Self-Documenting**: Repository becomes self-documenting with built-in help system
- **Maintainable**: Adding new tools only requires updating the registry

This system ensures both human users and AI assistants can easily discover and understand the available analysis capabilities.
