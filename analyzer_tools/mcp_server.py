#!/usr/bin/env python3
"""
MCP Server for Neutron Reflectometry Analysis Tools

Exposes analyzer tools to LLMs via the MCP (Model Context Protocol).
Tools remain independently callable via their CLI entry points.

Usage:
    analyzer-mcp
    fastmcp run analyzer_tools/mcp_server.py
"""

import os
import sys
import glob
import logging
from typing import Optional, Literal

from fastmcp import FastMCP

# Add project root to path for standalone execution (e.g., fastmcp run)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from analyzer_tools.config_utils import get_config  # noqa: E402
from analyzer_tools.schemas import (  # noqa: E402
    FitResult,
    PartialDataAssessmentResult,
    EISIntervalsResult,
    DataListResult,
    DataFileInfo,
    ModelListResult,
    ParameterInfo,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "analyzer-tools",
    instructions="Neutron reflectometry data analysis tools for fitting, assessment, and experiment planning",
)


# ============================================================================
# MCP Tools
# ============================================================================


@mcp.tool()
def run_fit(
    data_id: str,
    model_name: str,
    output_dir: Optional[str] = None,
) -> dict:
    """
    Run a reflectivity fit on combined neutron data using a specified model.

    Performs least-squares fitting and generates reports with parameter uncertainties.

    Args:
        data_id: Data set ID (e.g., '218281')
        model_name: Model name from models/ directory (e.g., 'cu_thf')
        output_dir: Override output directory (optional)

    Returns:
        Fit results including chi-squared, parameters, and output paths
    """
    from analyzer_tools.analysis.run_fit import execute_fit

    config = get_config()
    data_file = os.path.join(
        config.get_combined_data_dir(),
        config.get_combined_data_template().format(set_id=data_id),
    )

    if output_dir is None:
        output_dir = os.path.join(config.get_results_dir(), f"{data_id}_{model_name}")

    if not os.path.exists(data_file):
        return FitResult(
            success=False, message=f"Data file not found: {data_file}"
        ).model_dump()

    os.makedirs(output_dir, exist_ok=True)

    try:
        execute_fit(model_name, data_file, output_dir)

        chi_squared = None
        parameters: list[ParameterInfo] = []

        out_file = os.path.join(output_dir, "problem.out")
        if os.path.exists(out_file):
            with open(out_file, "r") as f:
                for line in f:
                    if "chisq=" in line:
                        try:
                            chi_squared = float(
                                line.split("chisq=")[1].split(",")[0].split("(")[0]
                            )
                        except (IndexError, ValueError):
                            pass
                        break

        par_file = os.path.join(output_dir, "problem.par")
        if os.path.exists(par_file):
            with open(par_file, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            parameters.append(
                                ParameterInfo(
                                    name=" ".join(parts[:-1]),
                                    value=float(parts[-1]),
                                )
                            )
                        except ValueError:
                            pass

        return FitResult(
            success=True,
            chi_squared=chi_squared,
            parameters=parameters,
            output_dir=output_dir,
            message=f"Fit completed successfully. Results in {output_dir}",
        ).model_dump()

    except Exception as e:
        return FitResult(success=False, message=f"Fit failed: {e}").model_dump()


@mcp.tool()
def assess_partial_data(
    set_id: str,
    data_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """
    Assess the quality of partial reflectometry data.

    Analyzes overlap regions between data parts, calculates chi-squared metrics,
    and generates visualization reports.

    Args:
        set_id: Set ID to assess (e.g., '218281')
        data_dir: Override partial data directory (optional)
        output_dir: Override output directory (optional)

    Returns:
        Assessment results with quality metrics and report path
    """
    from analyzer_tools.analysis.partial_data_assessor import (
        get_data_files,
        read_data,
        find_overlap_regions,
        calculate_match_metric,
        plot_overlap_regions,
        generate_markdown_report,
    )

    config = get_config()
    if data_dir is None:
        data_dir = config.get_partial_data_dir()
    if output_dir is None:
        output_dir = config.get_reports_dir()

    os.makedirs(output_dir, exist_ok=True)
    file_paths = get_data_files(set_id, data_dir)

    if len(file_paths) < 2:
        return PartialDataAssessmentResult(
            success=False,
            set_id=set_id,
            num_parts=len(file_paths),
            overall_quality="poor",
            message=f"Not enough data parts for set_id {set_id} (found {len(file_paths)})",
        ).model_dump()

    try:
        data_parts = [read_data(fp) for fp in file_paths]
        overlap_regions = find_overlap_regions(data_parts)
        metrics = [calculate_match_metric(o1, o2) for o1, o2 in overlap_regions]

        plot_path = plot_overlap_regions(data_parts, set_id, output_dir)
        generate_markdown_report(set_id, metrics, plot_path, output_dir)

        avg_chi2 = sum(metrics) / len(metrics) if metrics else float("inf")
        if avg_chi2 < 1.5:
            quality = "good"
        elif avg_chi2 < 3.0:
            quality = "acceptable"
        else:
            quality = "poor"

        return PartialDataAssessmentResult(
            success=True,
            set_id=set_id,
            num_parts=len(file_paths),
            overlap_quality=[
                {"overlap_index": i + 1, "chi_squared": m}
                for i, m in enumerate(metrics)
            ],
            overall_quality=quality,
            report_path=os.path.join(output_dir, f"report_{set_id}.md"),
            message=f"Assessment complete. Average chi-squared: {avg_chi2:.3f}",
        ).model_dump()

    except Exception as e:
        return PartialDataAssessmentResult(
            success=False,
            set_id=set_id,
            num_parts=len(file_paths),
            overall_quality="poor",
            message=f"Assessment failed: {e}",
        ).model_dump()


@mcp.tool()
def extract_eis_intervals(
    data_dir: str,
    resolution: Literal["per-file", "per-frequency"] = "per-file",
    pattern: str = "*C02_?.mpt",
    output_file: Optional[str] = None,
) -> dict:
    """
    Extract timing intervals from EIS .mpt files.

    Extracts timing information from EIS (Electrochemical Impedance Spectroscopy)
    files for use with Mantid neutron event filtering scripts.

    Args:
        data_dir: Directory containing EIS .mpt files
        resolution: 'per-file' (coarse) or 'per-frequency' (fine)
        pattern: Glob pattern to match files (default: '*C02_?.mpt')
        output_file: Output JSON file path (optional)

    Returns:
        Extracted intervals with timing information
    """
    from analyzer_tools.analysis.eis_interval_extractor import (
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
            message=f"Directory not found: {data_dir}",
        ).model_dump()

    try:
        extractor = (
            extract_per_file_intervals
            if resolution == "per-file"
            else extract_per_frequency_intervals
        )
        intervals = extractor(data_dir, pattern=pattern, exclude="fit")
        n_files = len({i.get("filename", "") for i in intervals})

        if output_file:
            import json

            with open(output_file, "w") as f:
                json.dump(
                    {
                        "source_directory": data_dir,
                        "resolution": resolution,
                        "n_intervals": len(intervals),
                        "intervals": intervals,
                    },
                    f,
                    indent=2,
                    default=str,
                )

        return EISIntervalsResult(
            success=True,
            source_directory=data_dir,
            resolution=resolution,
            n_files=n_files,
            n_intervals=len(intervals),
            intervals=intervals,
            output_file=output_file,
            message=f"Extracted {len(intervals)} intervals from {n_files} files",
        ).model_dump()

    except Exception as e:
        return EISIntervalsResult(
            success=False,
            source_directory=data_dir,
            resolution=resolution,
            n_files=0,
            n_intervals=0,
            message=f"Extraction failed: {e}",
        ).model_dump()


@mcp.tool()
def list_available_data(
    data_type: Literal["partial", "combined", "all"] = "all",
) -> dict:
    """
    List available reflectometry data files.

    Args:
        data_type: Type of data to list - 'partial', 'combined', or 'all'

    Returns:
        List of available data files with paths and set IDs
    """
    config = get_config()
    combined_files: list[DataFileInfo] = []
    partial_files: list[DataFileInfo] = []

    if data_type in ("combined", "all"):
        combined_dir = config.get_combined_data_dir()
        if os.path.isdir(combined_dir):
            for f in glob.glob(os.path.join(combined_dir, "REFL_*_combined*.txt")):
                basename = os.path.basename(f)
                set_id = basename.split("_")[1] if "_" in basename else basename
                combined_files.append(
                    DataFileInfo(path=f, set_id=set_id, file_type="combined")
                )

    if data_type in ("partial", "all"):
        partial_dir = config.get_partial_data_dir()
        if os.path.isdir(partial_dir):
            for f in glob.glob(os.path.join(partial_dir, "REFL_*_partial.txt")):
                basename = os.path.basename(f)
                parts = basename.split("_")
                set_id = parts[1] if len(parts) > 1 else basename
                partial_files.append(
                    DataFileInfo(path=f, set_id=set_id, file_type="partial")
                )

    return DataListResult(
        success=True,
        combined_data=combined_files,
        partial_data=partial_files,
        message=f"Found {len(combined_files)} combined and {len(partial_files)} partial files",
    ).model_dump()


@mcp.tool()
def list_available_models() -> dict:
    """
    List available reflectivity model files from the models/ directory.

    Returns:
        List of available model names
    """
    models_dir = os.path.join(_PROJECT_ROOT, "models")

    if not os.path.isdir(models_dir):
        return ModelListResult(
            success=False, message=f"Models directory not found: {models_dir}"
        ).model_dump()

    models = sorted(
        os.path.basename(f)[:-3]
        for f in glob.glob(os.path.join(models_dir, "*.py"))
        if not os.path.basename(f).startswith("_")
    )

    return ModelListResult(
        success=True, models=models, message=f"Found {len(models)} models"
    ).model_dump()


# ============================================================================
# Server Entry Point
# ============================================================================


def main():
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
