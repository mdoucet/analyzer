"""
Tool Registry for Neutron Reflectometry Data Analysis

Centralized catalog of available analysis tools with descriptions,
usage examples, and workflow definitions.
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
        module="analyzer_tools.analysis.partial_data_assessor",
        description="Assess quality of partial reflectometry data by analyzing overlap regions between data parts. Calculates chi-squared metrics and generates visualization reports.",
        usage="assess-partial <set_id>",
        examples=[
            "assess-partial 218281",
            "assess-partial 218328"
        ],
        data_type="partial"
    ),
    
    "run_fit": ToolInfo(
        name="Reflectivity Fit Runner",
        module="analyzer_tools.analysis.run_fit",
        description="Run reflectivity fits on combined data using specified models. Performs least-squares fitting and generates fit reports with uncertainty analysis.",
        usage="run-fit <data_id> <model_name>",
        examples=[
            "run-fit 218281 cu_thf",
            "run-fit 218328 cu_thf_temp"
        ],
        data_type="combined"
    ),
    
    "result_assessor": ToolInfo(
        name="Fit Result Assessor",
        module="analyzer_tools.analysis.result_assessor",
        description="Assess quality of fitting results by analyzing chi-squared values, parameter uncertainties, and generating comparison plots.",
        usage="assess-result <data_id> <model_name>",
        examples=[
            "assess-result 218281 cu_thf",
            "assess-result 218328 cu_thf_temp"
        ],
        data_type="combined"
    ),
    
    "create_model_script": ToolInfo(
        name="Model Script Creator",
        module="analyzer_tools.analysis.create_model_script",
        description="Generate fitting scripts by combining model definitions with fitting commands. Useful for batch processing and reproducible analysis.",
        usage="create-model <model_name> <data_file> [--model_dir DIR] [--output_dir DIR]",
        examples=[
            "create-model cu_thf data.txt",
            "create-model cu_thf data.txt --output_dir custom_output"
        ],
        data_type="combined"
    ),
    
    "create_temporary_model": ToolInfo(
        name="Temporary Model Creator",
        module="analyzer_tools.analysis.create_temporary_model",
        description="Create temporary models with adjusted parameter ranges for sensitivity analysis and parameter exploration.",
        usage="create-temporary-model <base_model> <new_model> --adjust <param> <min>,<max>",
        examples=[
            "create-temporary-model cu_thf cu_thf_temp --adjust Cu thickness 500,800",
            "create-temporary-model cu_thf cu_thf_wide --adjust Cu thickness 300,1000"
        ],
        data_type="both"
    ),
    
    "eis_interval_extractor": ToolInfo(
        name="EIS Interval Extractor",
        module="analyzer_tools.analysis.eis_interval_extractor",
        description="Extract timing intervals from EIS .mpt files and output as JSON. Supports per-file (coarse) or per-frequency (fine) resolution. Use with Mantid scripts for event filtering.",
        usage="eis-intervals --data-dir <path> --output <path>",
        examples=[
            "eis-interval-extractor --data-dir /path/to/eis --output intervals.json",
            "eis-interval-extractor --data-dir /path/to/eis --resolution per-frequency -o intervals.json",
            "eis-interval-extractor --data-dir /path/to/eis --pattern '*C02_*.mpt' -o intervals.json"
        ],
        data_type="both"
    ),
    
    "iceberg_packager": ToolInfo(
        name="Iceberg Packager",
        module="analyzer_tools.utils.iceberg_packager",
        description="Package tNR (time-resolved Neutron Reflectometry) data with EIS timing intervals into Parquet files for ingestion into a data lakehouse (Apache Iceberg). Combines reflectivity data, timing metadata, and reduction parameters.",
        usage="iceberg-packager <split_file> <reduced_dir> <template_file> [-o output.parquet]",
        examples=[
            "iceberg-packager data/tNR/splits.json data/tNR/reduced REF_L_sample_6_tNR.xml",
            "iceberg-packager splits.json ./reduced template.xml -o output/tnr_dataset.parquet",
            "iceberg-packager splits.json ./reduced template.xml --validate-only"
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
    
    "time_resolved_eis": {
        "name": "Time-Resolved EIS/Neutron Correlation",
        "description": "Correlate EIS measurements with neutron scattering events for time-resolved analysis",
        "steps": [
            "1. Use eis_interval_extractor to extract timing from EIS .mpt files",
            "2. Review timing boundaries and verify data quality",
            "3. Copy intervals JSON and Mantid scripts to cluster",
            "4. Execute eis_filter_events.py or eis_reduce_events.py in Mantid",
            "5. Analyze time-sliced neutron data corresponding to EIS measurements"
        ],
        "tools": ["eis_interval_extractor"]
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
