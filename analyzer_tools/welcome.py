"""
Welcome module for new users to discover analysis tools.

This module provides easy-to-use functions that help users get started
with neutron reflectometry data analysis.
"""

def welcome():
    """
    Display a welcome message with tool overview.
    
    This function is designed to be called at the start of analysis sessions
    to help users discover available tools and workflows.
    """
    from .registry import print_tool_overview
    print("🎉 Welcome to Neutron Reflectometry Data Analysis!")
    print("This repository provides tools for analyzing neutron reflectometry data.\n")
    print_tool_overview()

def show_available_data():
    """Show what data is available for analysis."""
    import os
    import glob
    try:
        from .config_utils import get_config
    except ImportError:
        # Fallback for standalone execution
        from analyzer_tools.config_utils import get_config
    
    config = get_config()
    
    print("📊 AVAILABLE DATA:")
    print("=" * 50)
    
    # Check combined data
    combined_dir = config.get_combined_data_dir()
    if os.path.exists(combined_dir):
        combined_files = glob.glob(os.path.join(combined_dir, "*.txt"))
        print(f"\n📈 Combined Data ({len(combined_files)} datasets):")
        print(f"   Location: {combined_dir}/")
        print(f"   Template: {config.get_combined_data_template()}")
        if combined_files:
            # Show first few and last few
            sample_files = combined_files[:3] + (["..."] if len(combined_files) > 6 else []) + combined_files[-3:]
            for file in sample_files:
                if file == "...":
                    print(f"   {file}")
                else:
                    print(f"   {os.path.basename(file)}")
    else:
        print(f"\n📈 Combined Data: Directory not found ({combined_dir})")
    
    # Check partial data
    partial_dir = config.get_partial_data_dir()
    if os.path.exists(partial_dir):
        partial_files = glob.glob(os.path.join(partial_dir, "*_partial.txt"))
        # Group by set_id
        set_ids = set()
        for file in partial_files:
            basename = os.path.basename(file)
            # Extract set_id from REFL_<set_id>_<part>_<run>_partial.txt
            parts = basename.split('_')
            if len(parts) >= 2:
                set_ids.add(parts[1])
        
        print(f"\n📊 Partial Data ({len(set_ids)} data sets with {len(partial_files)} parts):")
        print(f"   Location: {partial_dir}/")
        if set_ids:
            sorted_ids = sorted(list(set_ids))
            sample_ids = sorted_ids[:5] + (["..."] if len(sorted_ids) > 10 else []) + sorted_ids[-5:]
            print("   Available set IDs:")
            for set_id in sample_ids:
                if set_id == "...":
                    print(f"     {set_id}")
                else:
                    print(f"     {set_id}")
    else:
        print(f"\n📊 Partial Data: Directory not found ({partial_dir})")
    
    print("\n" + "=" * 50)

def quick_start(data_type="combined"):
    """
    Provide a quick start guide for analysis.
    
    Args:
        data_type: "combined", "partial", or "both"
    """
    print(f"🚀 QUICK START GUIDE - {data_type.upper()} DATA")
    print("=" * 50)
    
    if data_type in ["partial", "both"]:
        print("\n📊 For Partial Data Analysis:")
        print("   1. Assess data quality:")
        print("      python analyzer_tools/partial_data_assessor.py 218281")
        print("   2. Check the generated report in reports/report_218281.md")
        print("   3. Look for chi-squared values < 2.0 (good overlap)")
    
    if data_type in ["combined", "both"]:
        print("\n📈 For Combined Data Fitting:")
        print("   1. Run a fit:")
        print("      python analyzer_tools/run_fit.py 218281 cu_thf")
        print("   2. Assess the fit quality:")
        print("      python analyzer_tools/result_assessor.py 218281 cu_thf")
        print("   3. Check reports/ directory for results")
    
    print("\n💡 Tips:")
    print("   • Use 'python analyzer_tools/cli.py --list-tools' to see all tools")
    print("   • Use 'python analyzer_tools/cli.py --workflows' to see analysis workflows")
    print("   • Check docs/developer_notes.md for detailed information")
    
    print("\n" + "=" * 50)

def help_me_choose():
    """Interactive helper to choose the right tool."""
    print("🤔 TOOL SELECTION HELPER")
    print("=" * 30)
    print("What type of analysis do you want to perform?")
    print()
    print("1. Check quality of partial data (before combining)")
    print("   → Use: partial_data_assessor")
    print("   → Example: python analyzer_tools/partial_data_assessor.py 218281")
    print()
    print("2. Fit reflectivity data with a model")
    print("   → Use: run_fit")
    print("   → Example: python analyzer_tools/run_fit.py 218281 cu_thf")
    print()
    print("3. Evaluate quality of existing fit results")
    print("   → Use: result_assessor") 
    print("   → Example: python analyzer_tools/result_assessor.py 218281 cu_thf")
    print()
    print("4. Create or modify fitting models")
    print("   → Use: create_model_script or create_temporary_model")
    print("   → Example: python analyzer_tools/create_temporary_model.py cu_thf cu_thf_temp --adjust Cu thickness 500,800")
    print()
    print("For complete workflows, run: python analyzer_tools/cli.py --workflows")
    print("=" * 30)

if __name__ == "__main__":
    welcome()
