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
        name="Model Script Creator (AuRE)",
        module="analyzer_tools.analysis.model_from_aure",
        description="Generate an analyzer-convention refl1d model script from an AuRE ModelDefinition JSON (preferred) or a plain-English sample description (calls `aure analyze -m 0`).",
        usage="create-model <definition.json|sample_description> [DATA_FILE] [--out models/<name>.py]",
        examples=[
            "create-model path/to/model_initial.json --out models/cu_thf.py",
            "create-model 'Cu/Ti on Si in dTHF' data/combined/REFL_218281_combined_data_auto.txt --out models/cu_thf.py",
        ],
        data_type="combined"
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
    ),

    "theta_offset": ToolInfo(
        name="Theta Offset Calculator",
        module="analyzer_tools.analysis.theta_offset",
        description="Compute the theta offset for a Liquids Reflectometer (BL-4B) run by fitting the specular peak on the detector and comparing with the motor-log angle. Requires a NeXus event file and a pre-processed direct-beam file.",
        usage="theta-offset <nexus_file> --db <db_file>",
        examples=[
            "theta-offset REF_L_226642.nxs.h5 --db DB_226559.dat",
            "theta-offset REF_L_226642.nxs.h5 --db DB_226559.dat --ymin 135 --ymax 170",
            "theta-offset REF_L_226642.nxs.h5 --db DB_226559.dat --log offsets.csv"
        ],
        data_type="both"
    ),

    "analyze_sample": ToolInfo(
        name="Sample Pipeline Orchestrator",
        module="analyzer_tools.pipeline",
        description="End-to-end pipeline for one sample: partial assessment → reduction-issue gate → AuRE model generation → AuRE fit → result assessment + AuRE evaluation. Emits a reduction_batch.yaml manifest when re-reduction is required, but never re-runs reduction automatically.",
        usage="analyze-sample <sample.md|set_id> [--dry-run] [--no-reduction-gate]",
        examples=[
            "analyze-sample sample_218281.md",
            "analyze-sample 218281 --dry-run",
            "analyze-sample sample_218281.md --skip-aure-eval"
        ],
        data_type="both"
    ),

    "check_llm": ToolInfo(
        name="LLM Health Check",
        module="analyzer_tools.analysis.check_llm",
        description="Verify that the analyzer's LLM integration is ready: the aure CLI is installed, aure.llm is importable, and aure check-llm reports a working endpoint. Run this at the start of an analysis session.",
        usage="check-llm [--json] [--no-test]",
        examples=[
            "check-llm",
            "check-llm --json",
            "check-llm --no-test"
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
            "1. Use create_model_script to generate a refl1d model (AuRE)",
            "2. Use run_fit to perform fitting",
            "3. Use result_assessor to evaluate fit quality and get an LLM verdict"
        ],
        "tools": ["create_model_script", "run_fit", "result_assessor"]
    },

    "full_pipeline": {
        "name": "End-to-end Sample Pipeline",
        "description": "Single-command pipeline from partial data to final report with reduction-issue gate.",
        "steps": [
            "1. Write a sample_<id>.md with YAML frontmatter describing the sample",
            "2. Run analyze-sample sample_<id>.md",
            "3. If status is needs-reprocessing, edit and run reduction_batch.yaml with analyzer-batch, then re-run analyze-sample"
        ],
        "tools": ["analyze_sample"]
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
