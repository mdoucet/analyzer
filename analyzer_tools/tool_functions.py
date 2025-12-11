"""
Pure Python tool functions for MCP integration.

These functions wrap existing tool logic with clean typed interfaces
suitable for MCP exposure. They do not use argparse or sys.argv.
"""

import os
import sys
import glob
import configparser
from typing import Optional, List, Dict, Any

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .schemas import (
    FitResult,
    AssessmentResult,
    PartialDataAssessmentResult,
    EISIntervalsResult,
    DataListResult,
    DataFileInfo,
    ModelListResult,
    ToolHelpResult,
    ToolListResult,
    ParameterInfo,
)


def _get_config() -> configparser.ConfigParser:
    """Load configuration from config.ini."""
    config = configparser.ConfigParser()
    config_path = os.path.join(project_root, "config.ini")
    if os.path.exists(config_path):
        config.read(config_path)
    return config


def run_fit(
    data_id: str,
    model_name: str,
    output_dir: Optional[str] = None,
    data_dir: Optional[str] = None,
) -> FitResult:
    """
    Run a reflectivity fit on combined data using a specified model.
    
    Args:
        data_id: Data set ID (e.g., '218281')
        model_name: Model name from models/ directory (e.g., 'cu_thf')
        output_dir: Override output directory (optional)
        data_dir: Override data directory (optional)
        
    Returns:
        FitResult with fit status and parameters
    """
    from .run_fit import execute_fit
    
    config = _get_config()
    
    # Resolve paths
    if data_dir is None:
        data_dir = config.get("paths", "combined_data_dir", fallback="data/combined")
    
    data_template = config.get(
        "paths", "combined_data_template", 
        fallback="REFL_{set_id}_combined_data_auto.txt"
    )
    data_file = os.path.join(data_dir, data_template.format(set_id=data_id))
    
    if output_dir is None:
        results_dir = config.get("paths", "results_dir", fallback="results")
        output_dir = os.path.join(results_dir, f"{data_id}_{model_name}")
    
    # Check data file exists
    if not os.path.exists(data_file):
        return FitResult(
            success=False,
            message=f"Data file not found: {data_file}"
        )
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        execute_fit(model_name, data_file, output_dir)
        
        # Parse results if available
        chi_squared = None
        parameters = []
        
        # Try to read chi-squared from output
        out_file = os.path.join(output_dir, "problem.out")
        if os.path.exists(out_file):
            with open(out_file, "r") as f:
                for line in f:
                    if "chisq=" in line:
                        try:
                            chi_part = line.split("chisq=")[1].split(",")[0]
                            chi_squared = float(chi_part.split("(")[0])
                        except (IndexError, ValueError):
                            pass
                        break
        
        # Try to read parameters
        par_file = os.path.join(output_dir, "problem.par")
        if os.path.exists(par_file):
            with open(par_file, "r") as f:
                for line in f:
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                param_name = " ".join(parts[:-1])
                                param_value = float(parts[-1])
                                parameters.append(ParameterInfo(
                                    name=param_name,
                                    value=param_value
                                ))
                            except ValueError:
                                pass
        
        return FitResult(
            success=True,
            chi_squared=chi_squared,
            parameters=parameters,
            output_dir=output_dir,
            message=f"Fit completed successfully. Results in {output_dir}"
        )
        
    except Exception as e:
        return FitResult(
            success=False,
            message=f"Fit failed: {str(e)}"
        )


def assess_partial_data(
    set_id: str,
    data_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> PartialDataAssessmentResult:
    """
    Assess the quality of partial reflectometry data.
    
    Args:
        set_id: Set ID to assess (e.g., '218281')
        data_dir: Override partial data directory (optional)
        output_dir: Override output directory (optional)
        
    Returns:
        PartialDataAssessmentResult with quality metrics
    """
    from .partial_data_assessor import (
        get_data_files,
        read_data,
        find_overlap_regions,
        calculate_match_metric,
        plot_overlap_regions,
        generate_markdown_report,
    )
    
    config = _get_config()
    
    if data_dir is None:
        data_dir = config.get("paths", "partial_data_dir", fallback="data/partial")
    
    if output_dir is None:
        output_dir = config.get("paths", "reports_dir", fallback="reports")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Get data files
    file_paths = get_data_files(set_id, data_dir)
    
    if len(file_paths) < 2:
        return PartialDataAssessmentResult(
            success=False,
            set_id=set_id,
            num_parts=len(file_paths),
            overall_quality="poor",
            message=f"Not enough data parts found for set_id {set_id} (found {len(file_paths)})"
        )
    
    try:
        # Read data
        data_parts = [read_data(fp) for fp in file_paths]
        
        # Find overlap regions
        overlap_regions = find_overlap_regions(data_parts)
        
        # Calculate metrics
        metrics = [calculate_match_metric(o1, o2) for o1, o2 in overlap_regions]
        
        # Generate plots and report
        plot_path = plot_overlap_regions(data_parts, set_id, output_dir)
        generate_markdown_report(set_id, metrics, plot_path, output_dir)
        
        # Determine overall quality
        avg_chi2 = sum(metrics) / len(metrics) if metrics else float('inf')
        if avg_chi2 < 1.5:
            quality = "good"
        elif avg_chi2 < 3.0:
            quality = "acceptable"
        else:
            quality = "poor"
        
        overlap_quality = [
            {"overlap_index": i + 1, "chi_squared": m}
            for i, m in enumerate(metrics)
        ]
        
        report_path = os.path.join(output_dir, f"report_{set_id}.md")
        
        return PartialDataAssessmentResult(
            success=True,
            set_id=set_id,
            num_parts=len(file_paths),
            overlap_quality=overlap_quality,
            overall_quality=quality,
            report_path=report_path,
            message=f"Assessment complete. Average chi-squared: {avg_chi2:.3f}"
        )
        
    except Exception as e:
        return PartialDataAssessmentResult(
            success=False,
            set_id=set_id,
            num_parts=len(file_paths),
            overall_quality="poor",
            message=f"Assessment failed: {str(e)}"
        )


def extract_eis_intervals(
    data_dir: str,
    resolution: str = "per-file",
    pattern: str = "*C02_?.mpt",
    exclude: str = "fit",
    output_file: Optional[str] = None,
) -> EISIntervalsResult:
    """
    Extract timing intervals from EIS .mpt files.
    
    Args:
        data_dir: Directory containing EIS .mpt files
        resolution: 'per-file' or 'per-frequency'
        pattern: Glob pattern to match files
        exclude: Exclude files containing this string
        output_file: Output JSON file path (optional)
        
    Returns:
        EISIntervalsResult with extracted intervals
    """
    from .eis_interval_extractor import (
        extract_per_file_intervals,
        extract_per_frequency_intervals,
    )
    
    if not os.path.isdir(data_dir):
        return EISIntervalsResult(
            success=False,
            source_directory=data_dir,
            resolution=resolution,
            n_files=0,
            n_intervals=0,
            message=f"Directory not found: {data_dir}"
        )
    
    try:
        if resolution == "per-file":
            intervals = extract_per_file_intervals(
                data_dir, pattern=pattern, exclude=exclude
            )
        else:
            intervals = extract_per_frequency_intervals(
                data_dir, pattern=pattern, exclude=exclude
            )
        
        # Count unique files
        n_files = len(set(i.get("filename", "") for i in intervals))
        
        # Save to file if requested
        if output_file:
            output_data = {
                "source_directory": data_dir,
                "resolution": resolution,
                "n_intervals": len(intervals),
                "intervals": intervals
            }
            with open(output_file, "w") as f:
                import json
                json.dump(output_data, f, indent=2, default=str)
        
        return EISIntervalsResult(
            success=True,
            source_directory=data_dir,
            resolution=resolution,
            n_files=n_files,
            n_intervals=len(intervals),
            intervals=intervals,
            output_file=output_file,
            message=f"Extracted {len(intervals)} intervals from {n_files} files"
        )
        
    except Exception as e:
        return EISIntervalsResult(
            success=False,
            source_directory=data_dir,
            resolution=resolution,
            n_files=0,
            n_intervals=0,
            message=f"Extraction failed: {str(e)}"
        )


def list_available_data(
    data_type: str = "all"
) -> DataListResult:
    """
    List available data files in the configured directories.
    
    Args:
        data_type: 'partial', 'combined', or 'all'
        
    Returns:
        DataListResult with available data files
    """
    config = _get_config()
    
    combined_files: List[DataFileInfo] = []
    partial_files: List[DataFileInfo] = []
    
    # List combined data
    if data_type in ("combined", "all"):
        combined_dir = config.get("paths", "combined_data_dir", fallback="data/combined")
        if os.path.isdir(combined_dir):
            for f in glob.glob(os.path.join(combined_dir, "REFL_*_combined*.txt")):
                # Extract set_id from filename
                basename = os.path.basename(f)
                match = basename.split("_")[1] if "_" in basename else basename
                combined_files.append(DataFileInfo(
                    path=f,
                    set_id=match,
                    file_type="combined"
                ))
    
    # List partial data
    if data_type in ("partial", "all"):
        partial_dir = config.get("paths", "partial_data_dir", fallback="data/partial")
        if os.path.isdir(partial_dir):
            for f in glob.glob(os.path.join(partial_dir, "REFL_*_partial.txt")):
                # Extract set_id from filename
                basename = os.path.basename(f)
                parts = basename.split("_")
                set_id = parts[1] if len(parts) > 1 else basename
                partial_files.append(DataFileInfo(
                    path=f,
                    set_id=set_id,
                    file_type="partial"
                ))
    
    return DataListResult(
        success=True,
        combined_data=combined_files,
        partial_data=partial_files,
        message=f"Found {len(combined_files)} combined and {len(partial_files)} partial files"
    )


def list_available_models() -> ModelListResult:
    """
    List available model files in the models/ directory.
    
    Returns:
        ModelListResult with available model names
    """
    models_dir = os.path.join(project_root, "models")
    
    if not os.path.isdir(models_dir):
        return ModelListResult(
            success=False,
            message=f"Models directory not found: {models_dir}"
        )
    
    models = []
    for f in glob.glob(os.path.join(models_dir, "*.py")):
        basename = os.path.basename(f)
        if not basename.startswith("_"):
            model_name = basename[:-3]  # Remove .py extension
            models.append(model_name)
    
    return ModelListResult(
        success=True,
        models=sorted(models),
        message=f"Found {len(models)} models"
    )


def get_tool_help(tool_name: str) -> ToolHelpResult:
    """
    Get detailed help for a specific tool.
    
    Args:
        tool_name: Name or partial name of the tool
        
    Returns:
        ToolHelpResult with tool documentation
    """
    from .registry import get_all_tools
    
    tools = get_all_tools()
    
    # Find tool by partial match
    matched_tool = None
    for key, tool in tools.items():
        if tool_name.lower() in key.lower() or tool_name.lower() in tool.name.lower():
            matched_tool = tool
            break
    
    if matched_tool is None:
        return ToolHelpResult(
            tool_name=tool_name,
            description=f"Tool '{tool_name}' not found",
            usage="",
            examples=[],
            data_type=""
        )
    
    return ToolHelpResult(
        tool_name=matched_tool.name,
        description=matched_tool.description,
        usage=matched_tool.usage,
        examples=matched_tool.examples,
        data_type=matched_tool.data_type
    )


def list_tools() -> ToolListResult:
    """
    List all available analysis tools.
    
    Returns:
        ToolListResult with tool names and descriptions
    """
    from .registry import get_all_tools
    
    tools = get_all_tools()
    
    tool_list = [
        {"name": tool.name, "key": key, "description": tool.description}
        for key, tool in tools.items()
    ]
    
    return ToolListResult(
        success=True,
        tools=tool_list,
        message=f"Found {len(tool_list)} tools"
    )
