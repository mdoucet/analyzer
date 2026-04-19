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
    "--event-file", required=True, type=click.Path(exists=True),
    help="Path to neutron event data file (HDF5/NeXus).",
)
@click.option(
    "--template", required=True, type=click.Path(exists=True),
    help="Path to reduction template file (.xml).",
)
@click.option(
    "--output-dir", default="./reduced_data", show_default=True,
    type=click.Path(file_okay=False),
    help="Directory for output files.",
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
    "-v", "--verbose", is_flag=True,
    help="Enable debug-level logging.",
)
def main(
    event_file: str,
    template: str,
    output_dir: str,
    theta_offset: float | None,
    offset_csv: str | None,
    offset_run: str | None,
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

    logger.info("Reduction complete — output dir: %s", os.path.abspath(output_dir))


if __name__ == "__main__":
    main()
