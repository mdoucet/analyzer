#!/usr/bin/env python3
"""
Command-line interfaces for analyzer tools.
"""

import sys
import os

import click

# Add the project root to the path for backward compatibility
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def run_fit_cli():
    """Command-line interface for run_fit."""
    from .run_fit import main
    main()


def assess_partial_cli():
    """Command-line interface for partial data assessor."""
    from .partial_data_assessor import main
    main()


def create_model_cli():
    """Command-line interface for create_model_script."""
    from .create_model_script import main
    main()


def result_assessor_cli():
    """Command-line interface for result assessor."""
    from .result_assessor import main
    main()


def eis_interval_extractor_cli():
    """Command-line interface for EIS interval extractor."""
    from .eis_interval_extractor import main
    main()


def iceberg_packager_cli():
    """Command-line interface for Iceberg packager."""
    from .iceberg_packager import main
    main()


def eis_reduce_events_cli():
    """Command-line interface for Mantid EIS event reduction."""
    from .reduction.eis_reduce_events import main
    main()


def simple_reduction_cli():
    """Command-line interface for Mantid simple reduction."""
    from .reduction.simple_reduction import main
    main()


@click.command()
@click.option('--list-tools', 'list_tools', is_flag=True,
              help='List all available analysis tools')
@click.option('--help-tool', 'help_tool', type=str, metavar='TOOL',
              help='Get detailed help for a specific tool')
@click.option('--workflows', is_flag=True,
              help='Show available analysis workflows')
def main(list_tools: bool, help_tool: str, workflows: bool):
    """Neutron Reflectometry Data Analysis Tools.

    \b
    Examples:
      analyzer-tools --list-tools              # Show all available tools
      analyzer-tools --help-tool partial       # Get help for partial data assessor
      analyzer-tools --workflows              # Show analysis workflows
    """
    # Import here to avoid circular imports and allow standalone execution
    try:
        from .registry import print_tool_overview, get_all_tools, get_workflows
    except ImportError:
        # Fallback for standalone execution
        from analyzer_tools.registry import print_tool_overview, get_all_tools, get_workflows
    
    if list_tools:
        print_tool_overview()
        return
        
    if workflows:
        workflow_dict = get_workflows()
        print("\n🔄 ANALYSIS WORKFLOWS:")
        print("=" * 50)
        for name, workflow in workflow_dict.items():
            print(f"\n📋 {workflow['name']}")
            print(f"   {workflow['description']}")
            print("   Steps:")
            for step in workflow['steps']:
                print(f"     {step}")
            print(f"   Tools: {', '.join(workflow['tools'])}")
        print("\n" + "=" * 50)
        return
        
    if help_tool:
        tools = get_all_tools()
        tool_key = None
        
        # Find tool by partial name match
        for key, tool in tools.items():
            if help_tool.lower() in key.lower() or help_tool.lower() in tool.name.lower():
                tool_key = key
                break
                
        if tool_key:
            tool = tools[tool_key]
            print(f"\n🔧 {tool.name}")
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
