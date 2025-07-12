#!/usr/bin/env python3
"""
Command-line interfaces for analyzer tools.
"""

import sys
import os
import argparse

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
    # Since partial_data_assessor doesn't have a main(), we'll use the script directly
    import configparser
    import argparse
    from .partial_data_assessor import assess_data_set
    
    config = configparser.ConfigParser()
    config.read('config.ini')

    parser = argparse.ArgumentParser(description='Assess partial data sets.')
    parser.add_argument('set_id', type=str, help='Set ID to assess.')
    args = parser.parse_args()

    data_dir = config.get('paths', 'partial_data_dir')
    output_dir = config.get('paths', 'reports_dir')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    assess_data_set(args.set_id, data_dir, output_dir)


def create_model_cli():
    """Command-line interface for create_model_script."""
    from .create_model_script import main
    main()


def result_assessor_cli():
    """Command-line interface for result assessor."""
    from .result_assessor import main
    main()


def main():
    """Main CLI entry point with tool discovery."""
    # Import here to avoid circular imports and allow standalone execution
    try:
        from .registry import print_tool_overview, get_all_tools, get_workflows
    except ImportError:
        # Fallback for standalone execution
        from analyzer_tools.registry import print_tool_overview, get_all_tools, get_workflows
    
    parser = argparse.ArgumentParser(
        description='Neutron Reflectometry Data Analysis Tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  analyzer-tools --list-tools              # Show all available tools
  analyzer-tools --help-tool partial       # Get help for partial data assessor
  analyzer-tools --workflows              # Show analysis workflows
""")
    
    parser.add_argument('--list-tools', action='store_true',
                        help='List all available analysis tools')
    parser.add_argument('--help-tool', type=str, metavar='TOOL',
                        help='Get detailed help for a specific tool')
    parser.add_argument('--workflows', action='store_true',
                        help='Show available analysis workflows')
    
    args = parser.parse_args()
    
    if args.list_tools:
        print_tool_overview()
        return
        
    if args.workflows:
        workflows = get_workflows()
        print("\n🔄 ANALYSIS WORKFLOWS:")
        print("=" * 50)
        for name, workflow in workflows.items():
            print(f"\n📋 {workflow['name']}")
            print(f"   {workflow['description']}")
            print("   Steps:")
            for step in workflow['steps']:
                print(f"     {step}")
            print(f"   Tools: {', '.join(workflow['tools'])}")
        print("\n" + "=" * 50)
        return
        
    if args.help_tool:
        tools = get_all_tools()
        tool_key = None
        
        # Find tool by partial name match
        for key, tool in tools.items():
            if args.help_tool.lower() in key.lower() or args.help_tool.lower() in tool.name.lower():
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
            print(f"Tool '{args.help_tool}' not found.")
            print("Available tools:")
            for key, tool in tools.items():
                print(f"  {key}: {tool.name}")
        return
    
    # If no arguments provided, show overview
    print_tool_overview()


if __name__ == "__main__":
    main()
