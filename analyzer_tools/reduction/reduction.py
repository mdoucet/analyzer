#!/usr/bin/env python3
"""
CLI entry point for neutron event reduction.

Usage::

    simple-reduction --event-file REF_L_12345.nxs.h5 --template template.xml

Requires ``mantid`` and ``lr_reduction``::

    pip install analyzer-tools[reduction]
"""

from __future__ import annotations

import csv
import glob
import json
import logging
import os
import shutil
import sys

import click

logger = logging.getLogger(__name__)


def _read_offset_from_csv(csv_path: str, run_id: str) -> float:
    """Read the theta offset for *run_id* from a theta-offset CSV file.

    Looks for a row whose ``nexus`` column contains *run_id*.
    """
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if run_id in row["nexus"]:
                return float(row["offset"])
    raise click.ClickException(
        f"Run {run_id} not found in offset CSV: {csv_path}"
    )


@click.command()
@click.option(
    "--event-file", default=None, type=click.Path(exists=True),
    help="Path to neutron event data file (HDF5/NeXus). "
         "Required unless supplied via --state-in.",
)
@click.option(
    "--template", default=None, type=click.Path(exists=True),
    help="Path to reduction template file (.xml). "
         "Required unless supplied via --state-in.",
)
@click.option(
    "--output-dir", default=None, type=click.Path(file_okay=False),
    help="Directory for output files. "
         "Defaults to './reduced_data' or to paths.output_directory from --state-in.",
)
@click.option(
    "--theta-offset", default=None, type=float,
    help="Theta offset to apply during reduction (mutually exclusive with --offset-csv).",
)
@click.option(
    "--offset-csv", default=None, type=click.Path(exists=True),
    help="CSV file produced by theta-offset batch (requires --offset-run).",
)
@click.option(
    "--offset-run", default=None, type=str,
    help="Run ID to look up in the offset CSV (e.g. '226642').",
)
@click.option(
    "--json", "json_file", default=None, type=click.Path(dir_okay=False),
    help="Write a JSON summary (e.g. results.json) with paths to the partial "
         "and combined output files.",
)
@click.option(
    "--state-in", "state_in", default=None, type=click.Path(exists=True, dir_okay=False),
    help="Read a v1 workflow-state JSON. Missing --event-file / --template / "
         "--output-dir options are filled from paths.event_file / "
         "paths.template_file / paths.output_directory in the state.",
)
@click.option(
    "--state-out", "state_out", default=None, type=click.Path(dir_okay=False),
    help="Write a v1 workflow-state JSON with the reduction block populated.",
)
@click.option(
    "-v", "--verbose", is_flag=True,
    help="Enable debug-level logging.",
)
def main(
    event_file: str | None,
    template: str | None,
    output_dir: str | None,
    theta_offset: float | None,
    offset_csv: str | None,
    offset_run: str | None,
    json_file: str | None,
    state_in: str | None,
    state_out: str | None,
    verbose: bool,
) -> None:
    """Reduce neutron events using a reduction template.

    Provide theta offset as either a literal value (--theta-offset) or
    looked up from a CSV file (--offset-csv + --offset-run).
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Resolve missing path inputs from --state-in (v1 workflow state).
    from ..state import empty_state, load_state, save_state, update_stage, _path

    state: dict = load_state(state_in) if state_in else empty_state()
    if state_in:
        if event_file is None:
            event_file = (
                _path(state, "event_file")
                or _path(state, "input_file")
                or None
            )
        if template is None:
            template = _path(state, "template_file") or None
        if output_dir is None:
            output_dir = _path(state, "output_directory") or None

    if output_dir is None:
        output_dir = "./reduced_data"

    if event_file is None:
        raise click.UsageError(
            "--event-file is required (or supply paths.event_file via --state-in)."
        )
    if template is None:
        raise click.UsageError(
            "--template is required (or supply paths.template_file via --state-in)."
        )
    if not os.path.isfile(event_file):
        raise click.UsageError(f"--event-file does not exist: {event_file}")
    if not os.path.isfile(template):
        raise click.UsageError(f"--template does not exist: {template}")

    # Resolve theta offset
    if offset_csv is not None:
        if theta_offset is not None:
            raise click.UsageError(
                "--theta-offset and --offset-csv are mutually exclusive."
            )
        if offset_run is None:
            raise click.UsageError(
                "--offset-csv requires --offset-run."
            )
        theta_offset = _read_offset_from_csv(offset_csv, offset_run)
        logger.info("Offset from CSV: run %s → %+.4f°", offset_run, theta_offset)
    elif theta_offset is None:
        theta_offset = 0.0

    from . import MantidNotAvailableError
    try:
        from . import require_mantid
    except MantidNotAvailableError as exc:
        raise click.ClickException(str(exc)) from exc

    require_mantid()

    import mantid
    import mantid.simpleapi as api

    # lr_reduction imports plot_publisher at module level (output.py and
    # web_report.py), but we don't need it.  Provide a stub that accepts
    # any attribute access so all ``from plot_publisher import X`` succeed.
    import types
    if "plot_publisher" not in sys.modules:
        _stub = types.ModuleType("plot_publisher")
        _stub.__getattr__ = lambda name: lambda *a, **kw: None  # type: ignore[attr-defined]
        sys.modules["plot_publisher"] = _stub

    from lr_reduction import workflow

    mantid.kernel.config.setLogLevel(3)

    # Tell Mantid where to find data files by run number.  In production
    # the facility's data catalog handles this; here we point at the
    # directory containing the event files.
    data_dir = os.path.dirname(os.path.abspath(event_file))
    mantid.config.appendDataSearchDir(data_dir)
    mantid.config["default.facility"] = "SNS"
    mantid.config["default.instrument"] = "REF_L"

    logger.info("Loading event data: %s", event_file)
    ws = api.LoadEventNexus(event_file)
    logger.info("Workspace: %d events", ws.getNumberEvents())

    os.makedirs(output_dir, exist_ok=True)

    logger.info("Reducing with template: %s", template)
    first_run_of_set = workflow.reduce(
        ws, template, output_dir,
        average_overlap=False,
        theta_offset=theta_offset,
        q_summing=False,
        bck_in_q=False,
    )

    # Write metadata so downstream tools know which set was reduced
    metadata_file = os.path.join(output_dir, ".last_reduced_set")
    with open(metadata_file, "w") as f:
        f.write(str(first_run_of_set))
    logger.info("Metadata saved: %s", metadata_file)

    # Copy the combined file to a well-known name for convenience
    combined_file = os.path.join(
        output_dir, f"REFL_{first_run_of_set}_combined_data_auto.txt",
    )
    output_file = os.path.join(output_dir, "reflectivity.txt")
    if os.path.exists(combined_file):
        shutil.copy(combined_file, output_file)
        logger.info("Combined reflectivity: %s", output_file)
    else:
        logger.warning("Combined file not found: %s", combined_file)

    # Locate the partial file for the run we just reduced. Files are named
    # REFL_{first_run}_{id}_{run_number}_partial.txt; match by the current
    # event file's run number (e.g. REF_L_218282.nxs.h5 -> 218282).
    partial_file = None
    if json_file is not None or state_out is not None:
        run_number = "".join(c for c in os.path.basename(event_file).split(".")[0] if c.isdigit())
        pattern = os.path.join(
            output_dir, f"REFL_{first_run_of_set}_*_{run_number}_partial.txt",
        )
        matches = glob.glob(pattern)
        partial_file = os.path.abspath(matches[0]) if matches else None
        if partial_file is None:
            logger.warning("Partial file not found for pattern: %s", pattern)

    combined_file_abs = (
        os.path.abspath(combined_file) if os.path.exists(combined_file) else None
    )

    if json_file is not None:
        result = {
            "partial_file": partial_file,
            "combined_file": combined_file_abs,
        }
        with open(json_file, "w") as f:
            json.dump(result, f, indent=2)
        logger.info("JSON summary written: %s", os.path.abspath(json_file))

    if state_out is not None:
        state.setdefault("paths", {})
        state["paths"]["event_file"] = os.path.abspath(event_file)
        state["paths"]["raw_data"] = os.path.abspath(event_file)
        state["paths"]["template_file"] = os.path.abspath(template)
        state["paths"]["output_directory"] = os.path.abspath(output_dir)
        update_stage(
            state,
            "reduction",
            success=True,
            partial_file=partial_file,
            combined_file=combined_file_abs,
        )
        save_state(state, state_out)
        logger.info("State written: %s", os.path.abspath(state_out))

    logger.info("Reduction complete - output dir: %s", os.path.abspath(output_dir))


if __name__ == "__main__":
    main()
