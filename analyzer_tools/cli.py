#!/usr/bin/env python3
"""
Command-line interfaces for analyzer tools.
"""

import sys
import os

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


if __name__ == "__main__":
    print("Available commands:")
    print("  run-fit: Execute a fit using a specified model")
    print("  assess-partial: Assess partial data sets") 
    print("  create-model: Create model scripts")
