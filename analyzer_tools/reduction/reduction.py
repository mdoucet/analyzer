#!/usr/bin/env python3
"""
CLI entry point for neutron event reduction.

Usage::

    simple-reduction --event-file REF_L_12345.nxs.h5 --template template.xml

Requires ``mantid`` and ``lr_reduction``::

    pip install analyzer-tools[reduction]
"""

from __future__ import annotations

import logging
import os
import shutil

import click

logger = logging.getLogger(__name__)


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
    "--theta-offset", default=0.0, show_default=True, type=float,
    help="Theta offset to apply during reduction.",
)
@click.option(
    "-v", "--verbose", is_flag=True,
    help="Enable debug-level logging.",
)
def main(
    event_file: str,
    template: str,
    output_dir: str,
    theta_offset: float,
    verbose: bool,
) -> None:
    """Reduce neutron events using a reduction template."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    from . import MantidNotAvailableError
    try:
        from . import require_mantid
    except MantidNotAvailableError as exc:
        raise click.ClickException(str(exc)) from exc

    require_mantid()

    import mantid
    import mantid.simpleapi as api
    from lr_reduction import workflow

    mantid.kernel.config.setLogLevel(3)

    logger.info("Loading event data: %s", event_file)
    ws = api.LoadEventNexus(event_file)
    logger.info("Workspace: %d events", ws.getNumberEvents())

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
