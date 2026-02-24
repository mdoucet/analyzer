#!/usr/bin/env python3
"""
CLI entry point for simple neutron event reduction.

Usage::

    simple-reduction --event-file REF_L_12345.nxs.h5 --template template.xml

Requires ``mantid`` and ``lr_reduction``::

    pip install analyzer-tools[reduction]
"""

from __future__ import annotations

import logging
import os

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
    "--scan-index", default=1, show_default=True, type=int,
    help="Scan index within the template.",
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
    scan_index: int,
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
        from .core import load_reduction, reduce_workspace, save_reduction
    except MantidNotAvailableError as exc:
        raise click.ClickException(str(exc)) from exc

    setup = load_reduction(
        template,
        event_file,
        scan_index=scan_index,
        theta_offset=theta_offset,
    )

    n_events = setup.sample_ws.getNumberEvents()
    logger.info("Sample workspace: %d events", n_events)

    output_file = os.path.join(output_dir, f"r{setup.run_number}_reduced.txt")
    result = reduce_workspace(
        setup.sample_ws, setup.template_data, ws_db=setup.direct_beam_ws,
    )
    save_reduction(result, output_file)

    logger.info("Reduction complete — %s", output_file)


if __name__ == "__main__":
    main()

