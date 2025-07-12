# Neutron Reflectometry Analysis Tools

[![Python Tests](https://github.com/mdoucet/analyzer/actions/workflows/python-test.yml/badge.svg)](https://github.com/mdoucet/analyzer/actions/workflows/python-test.yml)
[![codecov](https://codecov.io/gh/mdoucet/analyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/mdoucet/analyzer)
[![DOI](https://zenodo.org/badge/1013265177.svg)](https://doi.org/10.5281/zenodo.15870378)

This repository is a demonstration project to show how LLMs can be used to help scattering facility users 
analyze data. It was created out of the need to analyze a large number of data sets for a real experiment.
It is based on the idea that a list of properly named, well defined, and well documented tools can easily be
interpreted by an LLM, which can then call them according to a user's input. This version has LLM instructions
for both GitHub Copilot and GEMINI. This project is still in the prototype phase. Much remains to be done in terms of flexibility and reporting. Please feel free to contribute your own tools.


## 🚀 Quick Start

**New to this repository?** Start here:

The easiest way to get started and use this project, follow these steps:

1. Install VS Code
2. In VS Code, enable GitHub Copilot by logging in to your GitHub account
3. Follow the installation steps below
4. Make sure your data is available on the computer you are working on
5. Modify the `config.ini` file and make sure the `combined_data_dir` and `partial_data_dir` point to your data (they can be in the same directory).
6. Make sure the `results_dir` in the `config.ini` file is somewhere you like
7. If you are from another facility or you data files have a different naming convention (and if you are brave), you can change the `combined_data_template` in `config.ini` to define how your data files are named.



**From the command line**

```python
# In Python or Jupyter
from analyzer_tools.welcome import welcome
welcome()

# Or from command line
python analyzer_tools/cli.py
```

This will show you all available tools and help you get started!

## 📊 What This Package Does

- **🔍 Data Quality Assessment**: Check partial data consistency before combining
- **📈 Model Fitting**: Fit reflectivity data to theoretical models 
- **📋 Automated Reporting**: Generate comprehensive analysis reports
- **🛠️ Model Management**: Create and modify fitting models
- **📈 Result Analysis**: Evaluate fit quality and parameter uncertainties

## 🏗️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd analyzer
   ```

2. **Set up Python environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Install the package (optional):**
   ```bash
   pip install -e .  # Installs CLI commands: run-fit, assess-partial, create-model
   ```

## 🔧 Available Tools

| Tool | Purpose | Example Usage |
|------|---------|---------------|
| **Partial Data Assessor** | Check quality of partial data | `python analyzer_tools/partial_data_assessor.py 218281` |
| **Fit Runner** | Fit data to models | `python analyzer_tools/run_fit.py 218281 cu_thf` |
| **Result Assessor** | Evaluate fit quality | `python analyzer_tools/result_assessor.py 218281 cu_thf` |
| **Model Creator** | Generate fit scripts | `python analyzer_tools/create_model_script.py cu_thf data.txt` |
| **Temporary Models** | Adjust model parameters | `python analyzer_tools/create_temporary_model.py cu_thf cu_thf_temp --adjust Cu thickness 500,800` |

### 💡 Get Help Anytime

```bash
# List all tools
python analyzer_tools/cli.py --list-tools

# Get help for specific tool  
python analyzer_tools/cli.py --help-tool partial

# Show analysis workflows
python analyzer_tools/cli.py --workflows

# Interactive tool selection
python -c "from analyzer_tools.welcome import help_me_choose; help_me_choose()"
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

## 📁 Data Organization

Data locations are configured in `config.ini`. Default structure:

### Combined Data
- **Default Location**: `data/combined/`
- **Configurable**: Set `combined_data_dir` in config.ini
- **Template**: Configurable via `combined_data_template` (default: `REFL_{set_id}_combined_data_auto.txt`)
- **Use**: Final reduced data ready for fitting

### Partial Data  
- **Default Location**: `data/partial/`
- **Configurable**: Set `partial_data_dir` in config.ini
- **Format**: `REFL_<set_ID>_<part_ID>_<run_ID>_partial.txt`
- **Use**: Individual data parts before combining (for quality assessment)
- **Structure**: Usually 3 parts per set, all with same `set_ID` belong together

### File Format
All data files contain 4 columns: Q, R, dR, dQ
- **Q**: Momentum transfer (1/Å)
- **R**: Reflectivity 
- **dR**: Reflectivity uncertainty
- **dQ**: Q resolution

## 🔄 Analysis Workflows

### 1. Partial Data Quality Check
```bash
# Assess overlap quality between data parts
python analyzer_tools/partial_data_assessor.py 218281

# Check the report
open reports/report_218281.md
```

### 2. Standard Fitting Workflow
```bash
# 1. Run the fit
python analyzer_tools/run_fit.py 218281 cu_thf

# 2. Assess results
python analyzer_tools/result_assessor.py 218281 cu_thf

# 3. Check reports directory for results
ls reports/
```

### 3. Parameter Exploration
```bash
# 1. Create model variant
python analyzer_tools/create_temporary_model.py cu_thf cu_thf_wide --adjust Cu thickness 300,1000

# 2. Test with new parameters
python analyzer_tools/run_fit.py 218281 cu_thf_wide

# 3. Compare results
python analyzer_tools/result_assessor.py 218281 cu_thf_wide
```

## ⚙️ Configuration

Edit `config.ini` to customize paths and settings:

```ini
[paths]
# Fit results storage
results_dir = /tmp/fits                    

# Data directories (customize for your setup)
combined_data_dir = data/combined          # Final reduced data
partial_data_dir = data/partial           # Individual data parts  

# Output directories
reports_dir = reports                     # Analysis reports

# File naming template for combined data
combined_data_template = REFL_{set_id}_combined_data_auto.txt
```

**🔧 Customizing Data Locations:**
- Set `combined_data_dir` to point to your reduced data location
- Set `partial_data_dir` to point to your partial data location  
- Modify `combined_data_template` if your files use different naming
- All tools automatically use these configured paths

## 🏗️ Models

Models are Python files in the `models/` directory. Each must contain a `create_fit_experiment` function returning a `refl1d.experiment.Experiment` object.

**Available models:**
- `cu_thf`: Copper thin film model

**Create new models:**
```bash
# Copy existing model as template
cp models/cu_thf.py models/my_model.py

** Create a model file that can be loaded in the refl1d interface **
python analyzer_tools/create_model_script.py my_model data.txt
```

## 🤖 AI Assistant Integration  

This repository is designed to work seamlessly with AI assistants. The tool registry system allows AI assistants to:

- Automatically discover available tools
- Understand tool capabilities and usage
- Guide users through appropriate workflows
- Provide contextual help and examples

**For AI assistants:** Import the registry to access tool information:
```python
from analyzer_tools.registry import get_all_tools, get_workflows, print_tool_overview
```

## 🆘 Getting Help

- **Tool overview**: `python analyzer_tools/cli.py`
- **Specific tool help**: `python analyzer_tools/cli.py --help-tool <tool_name>`
- **Workflows**: `python analyzer_tools/cli.py --workflows`
- **Interactive selection**: `python -c "from analyzer_tools.welcome import help_me_choose; help_me_choose()"`
- **Developer notes**: See `docs/developer_notes.md`

## 🤝 Contributing

1. Follow the test-driven development approach outlined in `docs/developer_notes.md`
2. Update the tool registry when adding new tools
3. Run tests: `pytest`
4. Update documentation


## 🚀 Next Steps

- Add more flexibility for modifying existing models
- Add co-refinement
- Add nested sampling analysis to compare models
- Add the ability to call time-resolved reduction
- Add the ability to fit and report on time-resolved data
