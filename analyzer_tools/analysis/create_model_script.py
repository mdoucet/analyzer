#!/usr/bin/env python3
import os
import re
import sys

import click


def create_fit_script(model_name: str, data_file: str) -> None:
    """
    This script generates a fit script by combining a model file
    with fitting commands.
    """
    try:
        with open(f"models/{model_name}.py", 'r') as f:
            model_content = f.read()
    except FileNotFoundError:
        print(f"Error: Model file 'models/{model_name}.py' not found.")
        sys.exit(1)

    # Extract set_id from data_file name
    match = re.search(r'REFL_(\d+)_', data_file)
    if not match:
        print(f"Error: Could not extract set_id from data file name: {data_file}")
        sys.exit(1)
    set_id = match.group(1)

    script_name = f"model_{set_id}_{model_name}.py"

    fit_commands = f'''
_refl = np.loadtxt("{data_file}").T
experiment = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])
problem = FitProblem(experiment)
'''

    with open(script_name, 'w') as f:
        f.write("import numpy as np\n\n")
        f.write(model_content)
        f.write(fit_commands)

    print(f"Successfully created fit script: {script_name}")


@click.command()
@click.argument("model_name", type=str)
@click.argument("data_file", type=str)
def main(model_name: str, data_file: str):
    """
    Create a model script that can be loaded in refl1d.
    
    MODEL_NAME: Name of the model module in the models directory (e.g., 'cu_thf').
    
    DATA_FILE: Path to the data file (or just filename if in configured combined data directory).
    """
    create_fit_script(model_name, data_file)


if __name__ == '__main__':
    main()
