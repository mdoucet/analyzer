import argparse
import os
import re


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
            f'(sample\["{layer}"\]\\.{parameter}\\.range\\()\\s*\\d+\\.?\\d*\\s*,\\s*\\d+\\.?\\d*\\s*(\\))'
        )
        replacement = f"\\g<1>{value[0]}, {value[1]}\\g<2>"
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a temporary model with adjusted parameter ranges."
    )
    parser.add_argument("base_model", type=str, help="The base model to use.")
    parser.add_argument("new_model", type=str, help="The name of the new model.")
    parser.add_argument(
        "--adjust",
        nargs=3,
        action="append",
        metavar=("LAYER", "PARAM", "MIN,MAX"),
        help="Adjust a parameter range. Example: --adjust Cu thickness 500,800",
    )
    args = parser.parse_args()

    adjustments = {}
    if args.adjust:
        for layer, param, values in args.adjust:
            min_val, max_val = values.split(",")
            adjustments[f"{layer}.{param}"] = (float(min_val), float(max_val))

    create_temporary_model(args.base_model, args.new_model, adjustments)
