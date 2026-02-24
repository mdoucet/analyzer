#!/usr/bin/env python3
"""
CLI entry point for EIS time-resolved event reduction.

Splits neutron events by EIS measurement intervals and reduces each
slice independently.

Usage::

    eis-reduce-events \\
        --intervals intervals.json \\
        --event-file REF_L_12345.nxs.h5 \\
        --template template.xml

Requires ``mantid`` and ``lr_reduction``::

    pip install analyzer-tools[reduction]
"""

from __future__ import annotations

import json
import logging
import os

import click

logger = logging.getLogger(__name__)


def _save_options(
    *,
    intervals_file: str,
    event_file: str,
    template_file: str,
    output_dir: str,
    scan_index: int,
    theta_offset: float,
    tz_offset: float,
    n_intervals: int,
) -> None:
    """Persist reduction parameters for reproducibility."""
    options = {
        "intervals_file": intervals_file,
        "event_file": event_file,
        "template_file": template_file,
        "output_dir": output_dir,
        "scan_index": scan_index,
        "theta_offset": theta_offset,
        "tz_offset": tz_offset,
        "n_intervals": n_intervals,
    }
    path = os.path.join(output_dir, "reduction_options.json")
    with open(path, "w") as fp:
        json.dump(options, fp, indent=2)
    logger.info("Saved reduction options: %s", path)


def _save_summary(
    run_number: int,
    duration: float,
    intervals: list[dict],
    output_dir: str,
    reduced_files: list[str],
) -> None:
    """Write a JSON summary of the reduction run."""
    summary = {
        "run_number": run_number,
        "duration": duration,
        "n_intervals": len(intervals),
        "intervals": [
            {
                "label": iv.get("label", iv.get("filename", f"interval_{i}")),
                "interval_type": iv.get("interval_type", "eis"),
                "start": iv["start"],
                "end": iv["end"],
            }
            for i, iv in enumerate(intervals)
        ],
        "reduced_files": reduced_files,
    }
    path = os.path.join(output_dir, f"r{run_number}_eis_reduction.json")
    with open(path, "w") as fp:
        json.dump(summary, fp, indent=2)
    logger.info("Saved reduction summary: %s", path)


@click.command()
@click.option(
    "--intervals", required=True, type=click.Path(exists=True),
    help="Path to JSON file with EIS measurement intervals.",
)
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
    "--tz-offset", default=5.0, show_default=True, type=float,
    help="Timezone offset in hours from UTC for EIS timestamps (EST = 5.0).",
)
@click.option(
    "-v", "--verbose", is_flag=True,
    help="Enable debug-level logging.",
)
def main(
    intervals: str,
    event_file: str,
    template: str,
    output_dir: str,
    scan_index: int,
    theta_offset: float,
    tz_offset: float,
    verbose: bool,
) -> None:
    """Filter and reduce neutron events by EIS measurement intervals.

    \b
    Example:
        eis-reduce-events \\
            --intervals intervals.json \\
            --event-file REF_L_12345.nxs.h5 \\
            --template template.xml
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    from . import MantidNotAvailableError
    try:
        from .core import load_reduction, reduce_workspace, save_reduction
        from .event_filter import convert_intervals, filter_events_by_intervals
    except MantidNotAvailableError as exc:
        raise click.ClickException(str(exc)) from exc

    # Load intervals
    with open(intervals) as f:
        interval_list = json.load(f)["intervals"]
    logger.info("Loaded %d measurement intervals from %s", len(interval_list), intervals)

    os.makedirs(output_dir, exist_ok=True)
    _save_options(
        intervals_file=intervals,
        event_file=event_file,
        template_file=template,
        output_dir=output_dir,
        scan_index=scan_index,
        theta_offset=theta_offset,
        tz_offset=tz_offset,
        n_intervals=len(interval_list),
    )

    # Common setup
    setup = load_reduction(
        template,
        event_file,
        scan_index=scan_index,
        theta_offset=theta_offset,
    )

    # Convert and filter
    intervals_abs = convert_intervals(interval_list, tz_offset_hours=tz_offset)
    filtered = filter_events_by_intervals(setup.sample_ws, intervals_abs)

    # Reduce each slice
    reduced_files: list[str] = []
    for label, ws in filtered:
        n_events = ws.getNumberEvents()
        logger.info("Reducing %s (%d events)", label, n_events)

        clean_name = label.replace(",", "_").replace(" ", "_")
        output_file = os.path.join(output_dir, f"r{setup.run_number}_{clean_name}.txt")

        result = reduce_workspace(ws, setup.template_data, ws_db=setup.direct_beam_ws)
        save_reduction(result, output_file)
        reduced_files.append(output_file)

    _save_summary(setup.run_number, setup.duration, interval_list, output_dir, reduced_files)
    logger.info("Reduction complete — %d files in %s", len(reduced_files), output_dir)


if __name__ == "__main__":
    main()

