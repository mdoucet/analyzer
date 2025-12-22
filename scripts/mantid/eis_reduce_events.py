#!/usr/bin/env python3
"""
Mantid Event Reduction Script - EIS Measurement Intervals

Filter neutron scattering events based on EIS measurement intervals,
then reduce each slice using the LiquidsReflectometer workflow.

Usage:
    python eis_reduce_events.py \\
        --intervals intervals.json \\
        --event-file REF_L_12345.nxs.h5 \\
        --template template.xml

This script requires Mantid and lr_reduction to be available.
"""

import argparse
import json
import os
from datetime import datetime

import numpy as np
from numpy import datetime64, timedelta64

# Import Mantid
import mantid
import mantid.simpleapi as api
from mantid.api import mtd
import mantid.kernel as mk

mantid.kernel.config.setLogLevel(3)

# Import LiquidsReflectometer reduction modules
from lr_reduction import template
from lr_reduction.event_reduction import apply_dead_time_correction, compute_resolution


def parse_iso_datetime(iso_string):
    """Parse ISO datetime string to datetime object."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(iso_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse datetime: {iso_string}")


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
        description="Filter and reduce neutron events by EIS measurement intervals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python eis_reduce_events.py \\
        --intervals /path/to/intervals.json \\
        --event-file /SNS/REF_L/IPTS-XXXXX/nexus/REF_L_12345.nxs.h5 \\
        --template /SNS/REF_L/IPTS-XXXXX/shared/templates/template.xml \\
        --output-dir ./reduced_data
""",
    )

    parser.add_argument(
        "--intervals",
        type=str,
        required=True,
        help="Path to JSON file with EIS measurement intervals",
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
    parser.add_argument(
        "--tz-offset",
        type=float,
        default=5.0,
        help="Timezone offset in hours from UTC for EIS timestamps (default: 5.0 for EST)",
    )

    args = parser.parse_args()

    print("EIS Measurement Event Filter + Reduction")
    print("=" * 60)
    print(f"Intervals file: {args.intervals}")
    print(f"Event file: {args.event_file}")
    print(f"Template: {args.template}")
    print(f"Output directory: {args.output_dir}")
    print()

    # Load intervals from JSON
    with open(args.intervals, "r") as f:
        data = json.load(f)

    intervals = data["intervals"]
    print(f"Loaded {len(intervals)} measurement intervals")

    # Create output directory
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # Save options for reproducibility
    options = {
        "intervals_file": args.intervals,
        "event_file": args.event_file,
        "template_file": args.template,
        "output_dir": args.output_dir,
        "scan_index": args.scan_index,
        "theta_offset": args.theta_offset,
        "n_intervals": len(intervals),
    }
    with open(os.path.join(args.output_dir, "reduction_options.json"), "w") as fp:
        json.dump(options, fp, indent=2)

    # Load the reduction template
    print(f"\nLoading template: {args.template}")
    template_data = template.read_template(args.template, args.scan_index)

    # Apply theta offset
    if args.theta_offset:
        print(f"Theta offset: {args.theta_offset}")
        template_data.angle_offset = args.theta_offset

    # Load event data
    print(f"\nLoading event data: {args.event_file}")
    meas_ws = api.LoadEventNexus(args.event_file)

    # Get run metadata
    try:
        duration = meas_ws.getRun()["duration"].value
    except Exception:
        duration = 0
    try:
        meas_run = meas_ws.getRun()["run_number"].value
    except Exception:
        meas_run = 0

    # Apply dead time correction up front
    if template_data.dead_time:
        print("Applying dead time correction to sample data...")
        apply_dead_time_correction(meas_ws, template_data)

    # Convert intervals to absolute seconds for filtering
    print("\nConverting time intervals...")
    intervals_abs = []
    # Mantid Nexus times are in nanoseconds since 1970-01-01 UTC.
    # EIS files don't include timezone info, so we apply an offset.
    time_zone_delta = int(args.tz_offset * 60 * 60 * 1_000_000_000)  # hours -> nanoseconds
    print(f"  Timezone offset: {args.tz_offset:+.1f} hours")
    for interval in intervals:
        # Use label if available, fallback to filename
        label = interval.get("label", interval.get("filename", "unknown"))
        start_dt = parse_iso_datetime(interval["start"])
        end_dt = parse_iso_datetime(interval["end"])
        start_abs = (
            mk.DateAndTime(start_dt.isoformat()).totalNanoseconds() + time_zone_delta
        )
        end_abs = (
            mk.DateAndTime(end_dt.isoformat()).totalNanoseconds() + time_zone_delta
        )
        intervals_abs.append((label, start_abs, end_abs))
        duration_s = (end_abs - start_abs) / 1_000_000_000
        interval_type = interval.get("interval_type", "eis")
        print(f"  {label} ({interval_type}, {duration_s:.1f}s)")

    # Create filter table workspace
    print("\nCreating filter table...")
    filter_table, filter_info = api.GenerateEventsFilter(
        InputWorkspace="meas_ws",
        OutputWorkspace="eis_filter",
        InformationWorkspace="eis_info",
        TimeInterval=6000,
    )
    filter_table.setRowCount(0)

    for i, (filename, start_abs, end_abs) in enumerate(intervals_abs):
        filter_table.addRow((start_abs, end_abs, i))

    # Filter events by EIS measurement intervals
    print("\nFiltering events by EIS intervals...")
    api.FilterEvents(
        InputWorkspace=meas_ws,
        SplitterWorkspace="eis_filter",
        GroupWorkspaces=True,
        OutputWorkspaceBaseName="eis_measurement",
        FilterByPulseTime=True,
        OutputWorkspaceIndexedFrom1=False,
        CorrectionToSample="None",
        SpectrumWithoutDetector="Skip",
        SplitSampleLogs=False,
        OutputTOFCorrectionWorkspace="mock",
        RelativeTime=False,
    )

    wsgroup = mtd["eis_measurement"]
    wsnames = wsgroup.getNames()
    print(f"Created {len(wsnames)} filtered workspaces")
    print(", ".join(wsnames))

    # Load direct beam workspace (do this once for efficiency)
    print(f"\nLoading direct beam: REF_L_{template_data.norm_file}")
    ws_db = api.LoadEventNexus(f"REF_L_{template_data.norm_file}")

    # Apply dead time correction to direct beam
    if template_data.dead_time:
        print("Applying dead time correction to direct beam...")
        apply_dead_time_correction(ws_db, template_data)

    # Turn off dead time in template (already applied)
    template_data.dead_time = False

    # Reduce each filtered workspace
    print("\nReducing filtered workspaces...")
    reduced_list = []
    eis_names = []

    for i, name in enumerate(wsnames):
        tmpws = mtd[name]
        n_events = tmpws.getNumberEvents()
        # Use label if available, fallback to filename
        interval_label = intervals[i].get("label", intervals[i].get("filename", f"interval_{i}"))
        interval_type = intervals[i].get("interval_type", "eis")
        print(f"\nWorkspace {name}: {n_events} events")
        print(f"  Interval: {interval_label} ({interval_type})")

        # Create output filename using the label
        clean_name = interval_label.replace(",", "_").replace(" ", "_")
        output_file = os.path.join(args.output_dir, f"r{meas_run}_{clean_name}.txt")

        # Reduce and save
        _reduced = reduce_and_save(tmpws, template_data, output_file, ws_db=ws_db)
        reduced_list.append(_reduced)
        eis_names.append(interval_label)

    # Save reduction summary as JSON
    print("\nSaving reduction summary...")
    summary = {
        "run_number": int(meas_run),
        "duration": float(duration),
        "n_intervals": len(intervals),
        "intervals": [
            {
                "label": i.get("label", i.get("filename", f"interval_{idx}")),
                "interval_type": i.get("interval_type", "eis"),
                "start": i["start"],
                "end": i["end"],
            }
            for idx, i in enumerate(intervals)
        ],
        "reduced_files": [
            os.path.join(
                args.output_dir,
                f"r{meas_run}_{i.get('label', i.get('filename', f'interval_{idx}')).replace(',', '_').replace(' ', '_')}.txt",
            )
            for idx, i in enumerate(intervals)
        ],
    }
    with open(
        os.path.join(args.output_dir, f"r{meas_run}_eis_reduction.json"), "w"
    ) as fp:
        json.dump(summary, fp, indent=2)

    print("\n" + "=" * 60)
    print("Reduction complete!")
    print(f"  Output directory: {args.output_dir}")
    print(f"  Reduced files: {len([r for r in reduced_list if r is not None])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
