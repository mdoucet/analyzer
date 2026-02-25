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
        from . import require_mantid
    except MantidNotAvailableError as exc:
        raise click.ClickException(str(exc)) from exc

    require_mantid()

    import os

    import mantid
    import mantid.simpleapi as api
    from lr_reduction import output as lr_output
    from lr_reduction import template as lr_template

    mantid.kernel.config.setLogLevel(3)

    logger.info("Loading template: %s (scan_index=%d)", template, scan_index)
    template_data = lr_template.read_template(template, scan_index)

    if theta_offset:
        template_data.angle_offset = theta_offset

    logger.info("Loading event data: %s", event_file)
    ws = api.LoadEventNexus(event_file)
    logger.info("Sample workspace: %d events", ws.getNumberEvents())

    qz, refl, d_refl, meta_data = lr_template.process_from_template_ws(
        ws, template_data, info=True,
    )

    # Save using RunCollection (standard SNS auto-reduction format)
    os.makedirs(output_dir, exist_ok=True)
    reduced_file = os.path.join(
        output_dir,
        "REFL_%s_%s_%s_partial.txt"
        % (meta_data["sequence_id"], meta_data["sequence_number"], meta_data["run_number"]),
    )
    coll = lr_output.RunCollection()
    coll.add(qz, refl, d_refl, meta_data=meta_data)
    coll.save_ascii(reduced_file, meta_as_json=True)
    logger.info("Reduction complete — %s", os.path.abspath(reduced_file))


if __name__ == "__main__":
    main()

