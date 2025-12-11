#!/usr/bin/env python3
"""
MCP Server for Neutron Reflectometry Analysis Tools

This module provides an MCP (Model Context Protocol) server that exposes
the analyzer tools to LLMs like Claude. Tools can be called through the
MCP protocol while remaining independently callable via their original CLIs.

Usage:
    # Run the MCP server
    python -m analyzer_tools.mcp_server
    
    # Or via entry point (after pip install -e .)
    analyzer-mcp
    
    # Or using fastmcp CLI
    fastmcp run analyzer_tools/mcp_server.py
"""

import os
import sys
from typing import Optional, Literal

from fastmcp import FastMCP

# Add project root to path before importing analyzer_tools
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import after path setup
from analyzer_tools.tool_functions import (  # noqa: E402
    run_fit as _run_fit,
    assess_partial_data as _assess_partial_data,
    extract_eis_intervals as _extract_eis_intervals,
    list_available_data as _list_available_data,
    list_available_models as _list_available_models,
    get_tool_help as _get_tool_help,
    list_tools as _list_tools,
)

# Create the FastMCP server
mcp = FastMCP(
    "analyzer-tools",
    instructions="Neutron reflectometry data analysis tools for fitting, assessment, and experiment planning"
)


# ============================================================================
# Tool Definitions
# ============================================================================

@mcp.tool()
def run_fit(
    data_id: str,
    model_name: str,
    output_dir: Optional[str] = None
) -> dict:
    """
    Run a reflectivity fit on combined neutron data using a specified model.
    
    Performs MCMC fitting and generates fit reports with parameter uncertainties.
    
    Args:
        data_id: Data set ID (e.g., '218281')
        model_name: Model name from models/ directory (e.g., 'cu_thf')
        output_dir: Override output directory (optional)
        
    Returns:
        Fit results including chi-squared, parameters, and output paths
    """
    result = _run_fit(data_id=data_id, model_name=model_name, output_dir=output_dir)
    return result.model_dump()


@mcp.tool()
def assess_partial_data(
    set_id: str,
    data_dir: Optional[str] = None,
    output_dir: Optional[str] = None
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
    result = _assess_partial_data(set_id=set_id, data_dir=data_dir, output_dir=output_dir)
    return result.model_dump()


@mcp.tool()
def extract_eis_intervals(
    data_dir: str,
    resolution: Literal["per-file", "per-frequency"] = "per-file",
    pattern: str = "*C02_?.mpt",
    output_file: Optional[str] = None
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
    result = _extract_eis_intervals(
        data_dir=data_dir,
        resolution=resolution,
        pattern=pattern,
        output_file=output_file
    )
    return result.model_dump()


@mcp.tool()
def list_available_data(
    data_type: Literal["partial", "combined", "all"] = "all"
) -> dict:
    """
    List available reflectometry data files.
    
    Lists data files in the configured directories that can be used for analysis.
    
    Args:
        data_type: Type of data to list - 'partial', 'combined', or 'all'
        
    Returns:
        List of available data files with paths and set IDs
    """
    result = _list_available_data(data_type=data_type)
    return result.model_dump()


@mcp.tool()
def list_available_models() -> dict:
    """
    List available reflectivity model files.
    
    Lists model files in the models/ directory that can be used for fitting.
    
    Returns:
        List of available model names
    """
    result = _list_available_models()
    return result.model_dump()


@mcp.tool()
def get_tool_help(tool_name: str) -> dict:
    """
    Get detailed help for a specific analysis tool.
    
    Args:
        tool_name: Name or partial name of the tool to get help for
        
    Returns:
        Tool documentation including description, usage, and examples
    """
    result = _get_tool_help(tool_name=tool_name)
    return result.model_dump()


@mcp.tool()
def list_tools() -> dict:
    """
    List all available neutron reflectometry analysis tools.
    
    Returns:
        List of tools with names and descriptions
    """
    result = _list_tools()
    return result.model_dump()


# ============================================================================
# Server Entry Point
# ============================================================================

def main():
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
