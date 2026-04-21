import os
import sys
import importlib
import configparser
import shlex
import shutil
import subprocess
from typing import List, Optional

import click
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


def _get_config():
    """Load configuration from config.ini."""
    config = configparser.ConfigParser()
    config.read("config.ini")
    return config


# ---------------------------------------------------------------------------
# AuRE wrapper
# ---------------------------------------------------------------------------


def build_aure_command(
    data_file: str,
    sample_description: str,
    output_dir: str,
    *,
    max_refinements: int = 5,
    extra_data: Optional[List[str]] = None,
    aure_executable: str = "aure",
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    """Build an ``aure analyze`` command line as a list of args."""
    cmd: List[str] = [
        aure_executable,
        "analyze",
        str(data_file),
        sample_description,
        "-o",
        str(output_dir),
        "-m",
        str(int(max_refinements)),
    ]
    for extra in extra_data or []:
        cmd.extend(["-d", str(extra)])
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def _read_sample_description(source: str) -> str:
    """If *source* is a file path, return its contents; else return *source* verbatim."""
    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as f:
            return f.read().strip()
    return source


@click.command()
@click.argument("set_id", type=str)
@click.argument("model_name", type=str, required=False)
@click.option(
    "--data-dir",
    type=click.Path(exists=True, file_okay=False),
    default=None,
    help="Directory containing the combined data files.",
)
@click.option(
    "--results-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Top level directory to store results.",
)
@click.option(
    "--reports-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Top level directory to store reports.",
)
@click.option(
    "--use-aure/--legacy",
    default=None,
    help="Force AuRE or legacy path. Auto-detects from --sample-description/-d if omitted.",
)
@click.option(
    "-d",
    "--sample-description",
    "sample_description",
    type=str,
    default=None,
    help="Sample description text or path to a markdown file. Enables AuRE mode.",
)
@click.option(
    "-m",
    "--max-refinements",
    type=int,
    default=5,
    show_default=True,
    help="AuRE refinement iterations (only used in --use-aure mode).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="In AuRE mode, print the command instead of running it.",
)
def main(
    set_id: str,
    model_name: Optional[str],
    data_dir: Optional[str],
    results_dir: Optional[str],
    reports_dir: Optional[str],
    use_aure: Optional[bool],
    sample_description: Optional[str],
    max_refinements: int,
    dry_run: bool,
):
    """
    Execute a reflectivity fit.

    \b
    Legacy mode (default when MODEL_NAME is a file in models/):
        run-fit 218281 cu_thf
    AuRE mode (when -d/--sample-description is given, or --use-aure is set):
        run-fit 218281 cu_thf -d "Cu/Ti on Si in dTHF"
        run-fit 218281 cu_thf -d sample.md --dry-run
    """
    config = _get_config()

    if data_dir is None:
        data_dir = config.get("paths", "combined_data_dir")
    if results_dir is None:
        results_dir = config.get("paths", "results_dir")
    if reports_dir is None:
        reports_dir = config.get("paths", "reports_dir")

    data_file_template = config.get("paths", "combined_data_template")
    data_file = os.path.join(data_dir, data_file_template.format(set_id=set_id))
    model_suffix = model_name or "aure"
    output_dir = os.path.join(results_dir, f"{set_id}_{model_suffix}")
    os.makedirs(output_dir, exist_ok=True)

    # Decide mode.
    if use_aure is None:
        use_aure = sample_description is not None

    if use_aure:
        if sample_description is None:
            raise click.BadParameter(
                "--use-aure requires -d/--sample-description (text or markdown path)."
            )
        description = _read_sample_description(sample_description)
        cmd = build_aure_command(
            data_file=data_file,
            sample_description=description,
            output_dir=output_dir,
            max_refinements=max_refinements,
        )
        printable = " ".join(shlex.quote(c) for c in cmd)
        if dry_run:
            click.echo(printable)
            return
        if shutil.which(cmd[0]) is None:
            click.echo(
                f"AuRE CLI '{cmd[0]}' not found on PATH. Install AuRE or re-run with --dry-run.",
                err=True,
            )
            click.echo(f"Would run: {printable}", err=True)
            sys.exit(2)
        click.echo(f"Running: {printable}", err=True)
        subprocess.run(cmd, check=True)
        return

    # Legacy path
    if model_name is None:
        raise click.BadParameter(
            "MODEL_NAME is required in legacy mode. "
            "Provide a models/<name>.py or use -d/--sample-description for AuRE mode."
        )
    click.echo(
        "Note: legacy run-fit path is deprecated. Pass -d/--sample-description to use AuRE.",
        err=True,
    )

    try:
        from .result_assessor import assess_result
    except ImportError:
        from analyzer_tools.analysis.result_assessor import assess_result

    execute_fit(model_name, data_file, output_dir)
    assess_result(output_dir, set_id, model_name, reports_dir)


if __name__ == "__main__":
    main()
