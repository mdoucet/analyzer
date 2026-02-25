#!/usr/bin/env python3
"""
Command-line interfaces for analyzer tools.
"""

import sys
import os
import glob

import click

# Add the project root to the path for backward compatibility
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# ============================================================================
# Presentation helpers (moved from registry / welcome)
# ============================================================================


def print_tool_overview():
    """Print a comprehensive overview of all available tools."""
    from .registry import TOOLS, WORKFLOWS
    from .config_utils import get_data_organization_info

    try:
        data_org = get_data_organization_info()
    except Exception:
        data_org = {
            "combined_data_dir": "data/combined",
            "partial_data_dir": "data/partial",
            "reports_dir": "reports",
            "combined_data_template": "REFL_{set_id}_combined_data_auto.txt",
            "models_dir": "models",
        }

    print("=" * 70)
    print("NEUTRON REFLECTOMETRY DATA ANALYSIS TOOLS")
    print("=" * 70)
    print()

    print("\U0001f4ca AVAILABLE ANALYSIS TOOLS:")
    print("-" * 40)

    for _name, tool in TOOLS.items():
        print(f"\n\U0001f527 {tool.name}")
        print(f"   {tool.description}")
        print(f"   Data type: {tool.data_type}")
        print(f"   Usage: {tool.usage}")
        if tool.examples:
            print(f"   Example: {tool.examples[0]}")

    print("\n\U0001f4cb ANALYSIS WORKFLOWS:")
    print("-" * 40)

    for _wf_name, workflow in WORKFLOWS.items():
        print(f"\n\U0001f504 {workflow['name']}")
        print(f"   {workflow['description']}")
        print(f"   Tools used: {', '.join(workflow['tools'])}")

    print("\n\U0001f4c1 DATA ORGANIZATION:")
    print("-" * 40)
    print(
        f"   \u2022 Partial data: {data_org['partial_data_dir']}/"
        " (REFL_<set_ID>_<part_ID>_<run_ID>_partial.txt)"
    )
    print(
        f"   \u2022 Combined data: {data_org['combined_data_dir']}/"
        f" ({data_org['combined_data_template']})"
    )
    print(
        f"   \u2022 Models: {data_org['models_dir']}/"
        " (Python files with reflectivity models)"
    )
    print(
        f"   \u2022 Reports: {data_org['reports_dir']}/"
        " (Generated analysis reports and plots)"
    )

    print("\n\U0001f680 QUICK START:")
    print("-" * 40)
    print("   1. For partial data quality: assess-partial 218281")
    print("   2. For reflectivity fitting: run-fit 218281 cu_thf")
    print("   3. For result assessment: assess-result 218281 cu_thf")

    print("\n" + "=" * 70)


def _show_available_data():
    """Show what data is available for analysis."""
    from .config_utils import get_config

    config = get_config()

    print("\U0001f4ca AVAILABLE DATA:")
    print("=" * 50)

    # Combined data
    combined_dir = config.get_combined_data_dir()
    if os.path.exists(combined_dir):
        combined_files = glob.glob(os.path.join(combined_dir, "*.txt"))
        print(f"\n\U0001f4c8 Combined Data ({len(combined_files)} datasets):")
        print(f"   Location: {combined_dir}/")
        print(f"   Template: {config.get_combined_data_template()}")
        for f in sorted(combined_files)[:5]:
            print(f"   {os.path.basename(f)}")
        if len(combined_files) > 5:
            print(f"   ... and {len(combined_files) - 5} more")
    else:
        print(f"\n\U0001f4c8 Combined Data: Directory not found ({combined_dir})")

    # Partial data
    partial_dir = config.get_partial_data_dir()
    if os.path.exists(partial_dir):
        partial_files = glob.glob(os.path.join(partial_dir, "*_partial.txt"))
        set_ids: set[str] = set()
        for f in partial_files:
            parts = os.path.basename(f).split("_")
            if len(parts) >= 2:
                set_ids.add(parts[1])
        print(
            f"\n\U0001f4ca Partial Data ({len(set_ids)} data sets"
            f" with {len(partial_files)} parts):"
        )
        print(f"   Location: {partial_dir}/")
        if set_ids:
            print("   Available set IDs:")
            for sid in sorted(set_ids)[:10]:
                print(f"     {sid}")
            if len(set_ids) > 10:
                print(f"     ... and {len(set_ids) - 10} more")
    else:
        print(f"\n\U0001f4ca Partial Data: Directory not found ({partial_dir})")

    print("\n" + "=" * 50)


# ============================================================================
# CLI entry point wrappers
# ============================================================================


def run_fit_cli():
    """Command-line interface for run_fit."""
    from .analysis.run_fit import main
    main()


def assess_partial_cli():
    """Command-line interface for partial data assessor."""
    from .analysis.partial_data_assessor import main
    main()


def create_model_cli():
    """Command-line interface for create_model_script."""
    from .analysis.create_model_script import main
    main()


def result_assessor_cli():
    """Command-line interface for result assessor."""
    from .analysis.result_assessor import main
    main()


def eis_interval_extractor_cli():
    """Command-line interface for EIS interval extractor."""
    from .analysis.eis_interval_extractor import main
    main()


def iceberg_packager_cli():
    """Command-line interface for Iceberg packager."""
    from .utils.iceberg_packager import main
    main()


def eis_reduce_events_cli():
    """Command-line interface for Mantid EIS event reduction."""
    from .reduction.eis_reduce_events import main
    main()


def simple_reduction_cli():
    """Command-line interface for Mantid simple reduction."""
    from .reduction.simple_reduction import main
    main()


# ============================================================================
# Main CLI command
# ============================================================================


@click.command()
@click.option('--list-tools', 'list_tools', is_flag=True,
              help='List all available analysis tools')
@click.option('--help-tool', 'help_tool', type=str, metavar='TOOL',
              help='Get detailed help for a specific tool')
@click.option('--workflows', is_flag=True,
              help='Show available analysis workflows')
@click.option('--show-data', 'show_data', is_flag=True,
              help='Show available data files')
def main(list_tools: bool, help_tool: str, workflows: bool, show_data: bool):
    """Neutron Reflectometry Data Analysis Tools.

    \b
    Examples:
      analyzer-tools --list-tools              # Show all available tools
      analyzer-tools --help-tool partial       # Get help for partial data assessor
      analyzer-tools --workflows               # Show analysis workflows
      analyzer-tools --show-data               # Show available data files
    """
    if list_tools:
        print_tool_overview()
        return

    if show_data:
        _show_available_data()
        return

    if workflows:
        try:
            from .registry import get_workflows
        except ImportError:
            from analyzer_tools.registry import get_workflows

        workflow_dict = get_workflows()
        print("\n\U0001f504 ANALYSIS WORKFLOWS:")
        print("=" * 50)
        for name, workflow in workflow_dict.items():
            print(f"\n\U0001f4cb {workflow['name']}")
            print(f"   {workflow['description']}")
            print("   Steps:")
            for step in workflow['steps']:
                print(f"     {step}")
            print(f"   Tools: {', '.join(workflow['tools'])}")
        print("\n" + "=" * 50)
        return

    if help_tool:
        try:
            from .registry import get_all_tools
        except ImportError:
            from analyzer_tools.registry import get_all_tools

        tools = get_all_tools()
        tool_key = None

        # Find tool by partial name match
        for key, tool in tools.items():
            if help_tool.lower() in key.lower() or help_tool.lower() in tool.name.lower():
                tool_key = key
                break

        if tool_key:
            tool = tools[tool_key]
            print(f"\n\U0001f527 {tool.name}")
            print("=" * (len(tool.name) + 3))
            print(f"Description: {tool.description}")
            print(f"Data type: {tool.data_type}")
            print(f"Usage: {tool.usage}")
            print("\nExamples:")
            for example in tool.examples:
                print(f"  {example}")
            print()
        else:
            print(f"Tool '{help_tool}' not found.")
            print("Available tools:")
            for key, tool in tools.items():
                print(f"  {key}: {tool.name}")
        return

    # If no arguments provided, show overview
    print_tool_overview()


if __name__ == "__main__":
    main()
