import os
import re
from typing import Dict, Tuple, List

import click


def adjust_model_parameters(model_content, adjustments):
    """
    Adjusts the parameter ranges in a model file.

    Parameters
    ----------
    model_content : str
        The content of the model file.
    adjustments : dict
        A dictionary of adjustments to make. The keys should be in the
        format "layer.parameter" (e.g., "Cu.thickness"), and the values
        should be tuples with the new min and max values.
    """
    for key, value in adjustments.items():
        layer, parameter = key.split(".")
        pattern = re.compile(
            rf'(sample\["{layer}"\]\.{parameter}\.range\()\s*\d+\.?\d*\s*,\s*\d+\.?\d*\s*(\))'
        )
        replacement = rf"\g<1>{value[0]}, {value[1]}\g<2>"
        model_content = pattern.sub(replacement, model_content)
    return model_content


def create_temporary_model(base_model_name, new_model_name, adjustments):
    """
    Creates a new model file with adjusted parameter ranges.

    Parameters
    ----------
    base_model_name : str
        The name of the base model to use.
    new_model_name : str
        The name of the new model to create.
    adjustments : dict
        A dictionary of adjustments to make.
    """
    base_model_path = os.path.join("models", f"{base_model_name}.py")
    if not os.path.exists(base_model_path):
        print(f"Error: Base model '{base_model_name}' not found.")
        return

    with open(base_model_path, "r") as f:
        model_content = f.read()

    model_content = adjust_model_parameters(model_content, adjustments)

    new_model_path = os.path.join("models", f"{new_model_name}.py")
    with open(new_model_path, "w") as f:
        f.write(model_content)

    print(f"Temporary model '{new_model_name}' created successfully.")


def parse_adjustment(ctx, param, value) -> Dict[str, Tuple[float, float]]:
    """Parse adjustment strings into a dictionary."""
    adjustments = {}
    if value:
        for adjustment in value:
            parts = adjustment.split()
            if len(parts) != 3:
                raise click.BadParameter(
                    f"Invalid adjustment format: '{adjustment}'. "
                    "Expected: 'LAYER PARAM MIN,MAX'"
                )
            layer, param_name, values = parts
            try:
                min_val, max_val = values.split(",")
                adjustments[f"{layer}.{param_name}"] = (float(min_val), float(max_val))
            except ValueError:
                raise click.BadParameter(
                    f"Invalid range format: '{values}'. Expected: 'MIN,MAX'"
                )
    return adjustments


@click.command()
@click.argument("base_model", type=str)
@click.argument("new_model", type=str)
@click.option(
    "--adjust", "-a",
    multiple=True,
    help="Adjust a parameter range. Format: 'LAYER PARAM MIN,MAX'. Example: --adjust 'Cu thickness 500,800'",
)
def main(base_model: str, new_model: str, adjust: tuple):
    """
    Create a temporary model with adjusted parameter ranges.
    
    BASE_MODEL: The base model to copy from (e.g., 'cu_thf').
    
    NEW_MODEL: The name for the new model (e.g., 'cu_thf_temp').
    
    Examples:
    
        create-model cu_thf cu_thf_temp --adjust 'Cu thickness 500,800'
        
        create-model cu_thf cu_thf_wide -a 'Cu thickness 300,1000' -a 'THF rho -0.5,2.0'
    """
    adjustments = parse_adjustment(None, None, adjust)
    create_temporary_model(base_model, new_model, adjustments)


if __name__ == "__main__":
    main()
