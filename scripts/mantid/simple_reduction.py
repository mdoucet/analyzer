#!/usr/bin/env python3
"""
Mantid Event Reduction Script

Usage:
    python simple_reduction.py \\
        --event-file REF_L_12345.nxs.h5 \\
        --template template.xml

This script requires Mantid and lr_reduction to be available.
"""

import argparse
import json
import os

import numpy as np

# Import Mantid
import mantid
import mantid.simpleapi as api
from mantid.api import mtd
import mantid.kernel as mk

mantid.kernel.config.setLogLevel(3)

# Import LiquidsReflectometer reduction modules
from lr_reduction import template, workflow
from lr_reduction.event_reduction import apply_dead_time_correction, compute_resolution
import shutil



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
        description="Reduce neutron events using a reduction template",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--event-file",
        type=str,
        required=True,
        help="Path to neutron event data file (HDF5/NeXus)",
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

    print("Mantid Event Reduction")
    print("=" * 60)
    print(f"Event file: {args.event_file}")
    print(f"Template: {args.template}")
    print(f"Output directory: {args.output_dir}")
    print()

    # Create output directory
    #if not os.path.exists(args.output_dir):
    #    os.makedirs(args.output_dir, exist_ok=True)

    # Load event data
    print(f"\nLoading event data: {args.event_file}")
    meas_ws = api.LoadEventNexus(args.event_file)

    # Reduce each filtered workspace
    print("\nReducing workspace...")

    n_events = meas_ws.getNumberEvents()

    print(f"\nWorkspace with {n_events} events")

    # Reduce and save
    #_reduced = reduce_and_save(meas_ws, template_data, output_file, ws_db=ws_db)
    first_run_of_set = workflow.reduce(meas_ws, args.template, args.output_dir,
                                           average_overlap=False,
                                           theta_offset=args.theta_offset,
                                           q_summing=False, bck_in_q=False)

    # Save the first run of set to a metadata file
    metadata_file = os.path.join(args.output_dir, ".last_reduced_set")
    with open(metadata_file, "w") as f:
        f.write(str(first_run_of_set))
    combined_file = os.path.join(args.output_dir, f"REFL_{first_run_of_set}_combined_data_auto.txt")
    output_file = os.path.join(args.output_dir, "reflectivity.txt")
    if os.path.exists(combined_file):
        shutil.copy(combined_file, output_file)
        print(f"  Copied to: {output_file}")
    else:
        print(f"  Warning: Combined file not found: {combined_file}")
    print(f"  Metadata saved: {metadata_file}")
    print("\n" + "=" * 60)
    print("Reduction complete!")
    print(f"  Output dir: {args.output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
