import os
import sys
import argparse
import importlib
import configparser
import numpy as np
from refl1d.names import *
from bumps.fitters import fit


# Add project root to path to allow importing from 'models'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def execute_fit(model_name, data_file, output_dir):
    """
    This script executes a fit using a predefined model and data.

    Parameters
    ----------
    model_name : str
        The name of the model module in the 'models' directory (e.g., 'cu_thf').
    data_file : str
        Path to the data file.
    output_dir : str
        The directory where fit results will be saved.
    """
    try:
        model_module = importlib.import_module(f"models.{model_name}")
        create_fit_experiment = model_module.create_fit_experiment
    except ImportError as e:
        print(
            f"Error: Could not import model '{model_name}' from 'models' directory: {e}"
        )
        return
    except AttributeError:
        print(
            f"Error: 'create_fit_experiment' function not found in '{model_name}' module."
        )
        return

    if not os.path.exists(data_file):
        print(f"Error: Data file not found at {data_file}")
        return

    _refl = np.loadtxt(data_file).T

    experiment = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])
    problem = FitProblem(experiment)

    fit(
        problem,
        method="dream",
        samples=10000,
        burn=5000,
        alpha=1,
        verbose=1,
        export=f"{output_dir}",
    )

    return output_dir


if __name__ == "__main__":
    from tools.result_assessor import assess_result

    config = configparser.ConfigParser()
    config.read("config.ini")

    parser = argparse.ArgumentParser(
        description="Execute a fit using a specified model."
    )
    parser.add_argument("set_id", type=str, help="The set ID of the data to fit.")
    parser.add_argument(
        "model_name",
        type=str,
        help="Name of the model module in the models directory (e.g., cu_thf).",
    )
    parser.add_argument(
        "--data_dir",
        type=str,
        default=config.get("paths", "combined_data_dir"),
        help="Directory containing the combined data files.",
    )
    parser.add_argument(
        "--results_dir",
        type=str,
        default=config.get("paths", "results_dir"),
        help="Top level directory to store results.",
    )
    parser.add_argument(
        "--reports_dir",
        type=str,
        default=config.get("paths", "reports_dir"),
        help="Top level directory to store reports.",
    )
    args = parser.parse_args()

    data_file_template = config.get("paths", "combined_data_template")
    data_file = os.path.join(
        args.data_dir, data_file_template.format(set_id=args.set_id)
    )
    output_dir = os.path.join(args.results_dir, f"{args.set_id}_{args.model_name}")

    os.makedirs(output_dir, exist_ok=True)

    execute_fit(args.model_name, data_file, output_dir)

    assess_result(output_dir, args.set_id, args.model_name, args.reports_dir)
