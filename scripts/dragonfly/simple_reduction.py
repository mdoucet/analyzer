#!/usr/bin/env python3
"""
Dragonfly Event Reduction Script

This is the dragonfly equivalent of the Mantid simple_reduction.py script.
It uses parquet files instead of HDF5/NeXus files.

Usage:
    python simple_reduction.py \\
        --data-dir /path/to/parquet/data \\
        --run-number 218389 \\
        --template template.xml

This script requires dragonfly and lr_reduction to be available.
"""

import argparse
import os

import numpy as np

# Use dragonfly's mantid shim for transparent lr_reduction compatibility
import dragonfly.mantid_shim  # noqa: F401 - must be imported before mantid

# Now import mantid modules (they will use dragonfly transparently)
import mantid.simpleapi as api
from mantid.simpleapi import mtd

# Import dragonfly directly for configuration
from dragonfly import simpleapi as dragonfly_api

# Import LiquidsReflectometer reduction modules
from lr_reduction import template
from lr_reduction.event_reduction import apply_dead_time_correction, compute_resolution


def reduce_and_save(ws, template_data, output_path, ws_db=None):
    """
    Reduce a single workspace and save the result.

    This follows the same approach as reduce_slices_ws from LiquidsReflectometer.
    """
    try:
        # Process using template
        _reduced = template.process_from_template_ws(ws, template_data, ws_db=ws_db)

        # Compute Q resolution
        dq0 = 0
        dq_slope = compute_resolution(ws)
        dq = dq0 + dq_slope * _reduced[0]

        # Create output array: [Q, R, dR, dQ]
        _reduced = np.asarray([_reduced[0], _reduced[1], _reduced[2], dq])

        # Save to file
        np.savetxt(output_path, _reduced.T)
        print(f"  Saved: {output_path}")

        return _reduced
    except Exception as e:
        print(f"  Error reducing workspace: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Reduce neutron events using dragonfly (parquet data)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Path to parquet data directory",
    )
    parser.add_argument(
        "--run-number",
        type=int,
        required=True,
        help="Run number to reduce (e.g., 218389)",
    )
    parser.add_argument(
        "--template",
        type=str,
        required=True,
        help="Path to reduction template file (.xml)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reduced_data",
        help="Directory for output files (default: ./reduced_data)",
    )
    parser.add_argument(
        "--scan-index",
        type=int,
        default=1,
        help="Scan index to use within the template (default: 1)",
    )
    parser.add_argument(
        "--theta-offset",
        type=float,
        default=0.0,
        help="Theta offset to apply during reduction (default: 0.0)",
    )

    args = parser.parse_args()

    print("Dragonfly Event Reduction")
    print("=" * 60)
    print(f"Data directory: {args.data_dir}")
    print(f"Run number: {args.run_number}")
    print(f"Template: {args.template}")
    print(f"Output directory: {args.output_dir}")
    print()

    # Configure dragonfly data path
    dragonfly_api.config.set_data_path(args.data_dir)

    # Create output directory
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # Load the reduction template
    print(f"\nLoading template: {args.template}")
    template_data = template.read_template(args.template, args.scan_index)

    # Apply theta offset
    if args.theta_offset:
        print(f"Theta offset: {args.theta_offset}")
        template_data.angle_offset = args.theta_offset

    # Load event data using dragonfly
    run_id = f"REF_L_{args.run_number}"
    print(f"\nLoading event data: {run_id}")
    meas_ws = api.LoadEventNexus(run_id, OutputWorkspace="meas_data")

    # Get run metadata
    try:
        meas_run = meas_ws.getRun()["run_number"].value
    except Exception:
        meas_run = args.run_number

    # Apply dead time correction up front
    if template_data.dead_time:
        print("Applying dead time correction to sample data...")
        apply_dead_time_correction(meas_ws, template_data)

    # Load direct beam workspace (do this once for efficiency)
    db_run_id = f"REF_L_{template_data.norm_file}"
    print(f"\nLoading direct beam: {db_run_id}")
    ws_db = api.LoadEventNexus(db_run_id, OutputWorkspace="direct_beam")

    # Apply dead time correction to direct beam
    if template_data.dead_time:
        print("Applying dead time correction to direct beam...")
        apply_dead_time_correction(ws_db, template_data)

    # Turn off dead time in template (already applied)
    template_data.dead_time = False

    # Reduce each filtered workspace
    print("\nReducing workspace...")

    # Get event count if available (not all workspace types support this)
    try:
        n_events = meas_ws.getNumberEvents()
        print(f"\nWorkspace with {n_events} events")
    except AttributeError:
        print("\nWorkspace loaded (event count not available)")

    output_file = os.path.join(args.output_dir, f"r{meas_run}_dragonfly.txt")

    # Reduce and save
    _reduced = reduce_and_save(meas_ws, template_data, output_file, ws_db=ws_db)

    print("\n" + "=" * 60)
    print("Reduction complete!")
    print(f"  Output file: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
