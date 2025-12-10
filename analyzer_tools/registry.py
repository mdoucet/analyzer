"""
Tool Registry for Neutron Reflectometry Data Analysis

This module provides a centralized registry of all available analysis tools
with descriptions, usage examples, and workflows.
"""

from typing import Dict, List

class ToolInfo:
    """Information about an analysis tool."""
    
    def __init__(self, name: str, module: str, description: str, 
                 usage: str, examples: List[str], data_type: str = "both"):
        self.name = name
        self.module = module
        self.description = description
        self.usage = usage
        self.examples = examples
        self.data_type = data_type  # "partial", "combined", or "both"

# Registry of all available tools
TOOLS = {
    "partial_data_assessor": ToolInfo(
        name="Partial Data Assessor",
        module="analyzer_tools.partial_data_assessor",
        description="Assess quality of partial reflectometry data by analyzing overlap regions between data parts. Calculates chi-squared metrics and generates visualization reports.",
        usage="python analyzer_tools/partial_data_assessor.py <set_id>",
        examples=[
            "python analyzer_tools/partial_data_assessor.py 218281",
            "python analyzer_tools/partial_data_assessor.py 218328"
        ],
        data_type="partial"
    ),
    
    "run_fit": ToolInfo(
        name="Reflectivity Fit Runner",
        module="analyzer_tools.run_fit",
        description="Run reflectivity fits on combined data using specified models. Performs least-squares fitting and generates fit reports with uncertainty analysis.",
        usage="python analyzer_tools/run_fit.py <data_id> <model_name>",
        examples=[
            "python analyzer_tools/run_fit.py 218281 cu_thf",
            "python analyzer_tools/run_fit.py 218328 cu_thf_temp"
        ],
        data_type="combined"
    ),
    
    "result_assessor": ToolInfo(
        name="Fit Result Assessor",
        module="analyzer_tools.result_assessor",
        description="Assess quality of fitting results by analyzing chi-squared values, parameter uncertainties, and generating comparison plots.",
        usage="python analyzer_tools/result_assessor.py <data_id> <model_name>",
        examples=[
            "python analyzer_tools/result_assessor.py 218281 cu_thf",
            "python analyzer_tools/result_assessor.py 218328 cu_thf_temp"
        ],
        data_type="combined"
    ),
    
    "create_model_script": ToolInfo(
        name="Model Script Creator",
        module="analyzer_tools.create_model_script",
        description="Generate fitting scripts by combining model definitions with fitting commands. Useful for batch processing and reproducible analysis.",
        usage="python analyzer_tools/create_model_script.py <model_name> <data_file> [--model_dir DIR] [--output_dir DIR]",
        examples=[
            "python analyzer_tools/create_model_script.py cu_thf data.txt",
            "python analyzer_tools/create_model_script.py cu_thf data.txt --output_dir custom_output"
        ],
        data_type="combined"
    ),
    
    "create_temporary_model": ToolInfo(
        name="Temporary Model Creator",
        module="analyzer_tools.create_temporary_model",
        description="Create temporary models with adjusted parameter ranges for sensitivity analysis and parameter exploration.",
        usage="python analyzer_tools/create_temporary_model.py <base_model> <new_model> --adjust <param> <min>,<max>",
        examples=[
            "python analyzer_tools/create_temporary_model.py cu_thf cu_thf_temp --adjust Cu thickness 500,800",
            "python analyzer_tools/create_temporary_model.py cu_thf cu_thf_wide --adjust Cu thickness 300,1000"
        ],
        data_type="both"
    ),
    
    "experiment_optimizer": ToolInfo(
        name="Experimental Design Optimizer",
        module="analyzer_tools.experiment_optimizer",
        description="Optimize neutron reflectometry experimental parameters by maximizing expected Shannon information gain using Bayesian analysis. Based on Treece et al., J. Appl. Cryst. (2019).",
        usage="python analyzer_tools/experiment_optimizer.py <model_name> --param <parameter> --values <val1,val2,val3>",
        examples=[
            "python analyzer_tools/experiment_optimizer.py cu_thf --param sld_solvent --values -0.5,0,2,4,6.5",
            "python analyzer_tools/experiment_optimizer.py cu_thf --param Cu thickness --values 400,500,600,700,800 --method mvn",
            "python analyzer_tools/experiment_optimizer.py cu_thf --param counting_time --values 0.5,1,2,4,8 --realizations 5"
        ],
        data_type="combined"
    ),
    
    "eis_interval_extractor": ToolInfo(
        name="EIS Interval Extractor",
        module="analyzer_tools.eis_interval_extractor",
        description="Extract timing intervals from EIS .mpt files and output as JSON. Supports per-file (coarse) or per-frequency (fine) resolution. Use with Mantid scripts for event filtering.",
        usage="python analyzer_tools/eis_interval_extractor.py --data-dir <path> --output <path>",
        examples=[
            "eis-interval-extractor --data-dir /path/to/eis --output intervals.json",
            "eis-interval-extractor --data-dir /path/to/eis --resolution per-frequency -o intervals.json",
            "eis-interval-extractor --data-dir /path/to/eis --pattern '*C02_*.mpt' -o intervals.json"
        ],
        data_type="both"
    )
}

# Workflow definitions
WORKFLOWS = {
    "partial_data_quality": {
        "name": "Partial Data Quality Assessment",
        "description": "Assess the quality of partial reflectometry data before combining",
        "steps": [
            "1. Use partial_data_assessor to check overlap quality",
            "2. Review chi-squared metrics (< 2.0 is typically good)",
            "3. Examine overlap plots for systematic deviations",
            "4. Identify problematic datasets for further investigation"
        ],
        "tools": ["partial_data_assessor"]
    },
    
    "standard_fitting": {
        "name": "Standard Reflectivity Fitting",
        "description": "Complete workflow for fitting reflectivity data",
        "steps": [
            "1. Use run_fit to perform initial fitting",
            "2. Use result_assessor to evaluate fit quality",
            "3. If poor fit, use create_temporary_model to adjust parameters",
            "4. Re-run fitting with adjusted model",
            "5. Generate final reports"
        ],
        "tools": ["run_fit", "result_assessor", "create_temporary_model"]
    },
    
    "parameter_exploration": {
        "name": "Parameter Sensitivity Analysis",
        "description": "Explore parameter sensitivity and uncertainty",
        "steps": [
            "1. Start with standard fitting workflow",
            "2. Use create_temporary_model to create variants with different parameter ranges",
            "3. Run fits on multiple parameter sets",
            "4. Use result_assessor to compare results",
            "5. Identify sensitive parameters and optimal ranges"
        ],
        "tools": ["run_fit", "result_assessor", "create_temporary_model"]
    },
    
    "experimental_optimization": {
        "name": "Experimental Design Optimization",
        "description": "Optimize experimental parameters using information theory",
        "steps": [
            "1. Define your model and reasonable parameter priors",
            "2. Use experiment_optimizer to test different experimental conditions",
            "3. Analyze information gain vs. parameter plots",
            "4. Identify optimal experimental conditions",
            "5. Plan real experiments using optimized parameters"
        ],
        "tools": ["experiment_optimizer"]
    },
    
    "time_resolved_eis": {
        "name": "Time-Resolved EIS/Neutron Correlation",
        "description": "Correlate EIS measurements with neutron scattering events for time-resolved analysis",
        "steps": [
            "1. Use eis_timing_extractor to extract timing from EIS .mpt files",
            "2. Review timing boundaries and verify data quality",
            "3. Option A: Use mantid_event_splitter to split by individual frequency measurements",
            "4. Option B: Use eis_measurement_splitter to split by complete EIS measurement intervals",
            "5. Execute the generated script in a Mantid environment",
            "6. Analyze time-sliced neutron data corresponding to EIS measurements"
        ],
        "tools": ["eis_timing_extractor", "mantid_event_splitter", "eis_measurement_splitter"]
    }
}

def get_all_tools() -> Dict[str, ToolInfo]:
    """Get all available tools."""
    return TOOLS

def get_tool(tool_name: str) -> ToolInfo:
    """Get information about a specific tool."""
    return TOOLS.get(tool_name)

def get_tools_by_data_type(data_type: str) -> Dict[str, ToolInfo]:
    """Get tools that work with a specific data type."""
    return {name: tool for name, tool in TOOLS.items() 
            if tool.data_type == data_type or tool.data_type == "both"}

def get_workflows() -> Dict[str, Dict]:
    """Get all available workflows."""
    return WORKFLOWS

def print_tool_overview():
    """Print a comprehensive overview of all tools."""
    # Try to get config-based data organization, fall back to defaults
    try:
        import sys
        import os
        # Add parent directory to path for standalone execution
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from analyzer_tools.config_utils import get_data_organization_info
        data_org = get_data_organization_info()
    except ImportError:
        # Fallback to defaults if config_utils can't be imported
        data_org = {
            'combined_data_dir': 'data/combined',
            'partial_data_dir': 'data/partial',
            'reports_dir': 'reports',
            'combined_data_template': 'REFL_{set_id}_combined_data_auto.txt',
            'models_dir': 'models'
        }
    
    print("=" * 70)
    print("NEUTRON REFLECTOMETRY DATA ANALYSIS TOOLS")
    print("=" * 70)
    print()
    
    print("📊 AVAILABLE ANALYSIS TOOLS:")
    print("-" * 40)
    
    for tool_name, tool in TOOLS.items():
        print(f"\n🔧 {tool.name}")
        print(f"   {tool.description}")
        print(f"   Data type: {tool.data_type}")
        print(f"   Usage: {tool.usage}")
        if tool.examples:
            print(f"   Example: {tool.examples[0]}")
    
    print("\n📋 ANALYSIS WORKFLOWS:")
    print("-" * 40)
    
    for workflow_name, workflow in WORKFLOWS.items():
        print(f"\n🔄 {workflow['name']}")
        print(f"   {workflow['description']}")
        print(f"   Tools used: {', '.join(workflow['tools'])}")
    
    print("\n📁 DATA ORGANIZATION:")
    print("-" * 40)
    print(f"   • Partial data: {data_org['partial_data_dir']}/ (REFL_<set_ID>_<part_ID>_<run_ID>_partial.txt)")
    print(f"   • Combined data: {data_org['combined_data_dir']}/ ({data_org['combined_data_template']})")
    print(f"   • Models: {data_org['models_dir']}/ (Python files with reflectivity models)")
    print(f"   • Reports: {data_org['reports_dir']}/ (Generated analysis reports and plots)")
    
    print("\n🚀 QUICK START:")
    print("-" * 40)
    print("   1. For partial data quality: python analyzer_tools/partial_data_assessor.py 218281")
    print("   2. For reflectivity fitting: python analyzer_tools/run_fit.py 218281 cu_thf")
    print("   3. For result assessment: python analyzer_tools/result_assessor.py 218281 cu_thf")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    print_tool_overview()
