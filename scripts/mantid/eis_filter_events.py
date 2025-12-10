#!/usr/bin/env python3
"""
Mantid Event Filtering Script - EIS Measurement Intervals

Filter neutron scattering events based on EIS measurement intervals.
Reads interval data from a JSON file produced by eis-measurement-splitter.

Usage:
    python eis_filter_events.py --intervals intervals.json --event-file REF_L_12345.nxs.h5

This script requires Mantid to be available in the Python environment.
"""

import argparse
import json
import os
from datetime import datetime

from numpy import datetime64, timedelta64

# Import Mantid algorithms
from mantid.simpleapi import (
    CreateEmptyTableWorkspace,
    FilterEvents,
    Load,
    SaveNexus,
    mtd,
)


def create_table_workspace(table_ws_name, column_def_list):
    """Create an empty table workspace with specified columns."""
    CreateEmptyTableWorkspace(OutputWorkspace=table_ws_name)
    table_ws = mtd[table_ws_name]
    for col_tup in column_def_list:
        data_type = col_tup[0]
        col_name = col_tup[1]
        table_ws.addColumn(data_type, col_name)
    return table_ws


def parse_iso_datetime(iso_string):
    """Parse ISO datetime string to datetime object."""
    formats = [
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(iso_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse datetime: {iso_string}")


def convert_to_absolute_seconds(dt):
    """
    Convert datetime to seconds relative to GPS epoch (1990-01-01).
    
    This is the format expected by Mantid's FilterEvents algorithm
    when using absolute time filtering.
    """
    gps_epoch = datetime64('1990-01-01T00:00:00')
    dt64 = datetime64(dt.isoformat())
    delta = dt64 - gps_epoch
    return float(delta / timedelta64(1, 's'))


def main():
    parser = argparse.ArgumentParser(
        description='Filter neutron events by EIS measurement intervals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python eis_filter_events.py \\
        --intervals /path/to/intervals.json \\
        --event-file /SNS/REF_L/IPTS-XXXXX/nexus/REF_L_12345.nxs.h5 \\
        --output-dir ./filtered_events
"""
    )
    
    parser.add_argument(
        '--intervals',
        type=str,
        required=True,
        help='Path to JSON file with EIS measurement intervals'
    )
    parser.add_argument(
        '--event-file',
        type=str,
        required=True,
        help='Path to neutron event data file (HDF5/NeXus)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./filtered_events',
        help='Directory for output files (default: ./filtered_events)'
    )
    parser.add_argument(
        '--prefix',
        type=str,
        default='eis_measurement',
        help='Prefix for output workspace names (default: eis_measurement)'
    )
    
    args = parser.parse_args()
    
    print("EIS Measurement Event Filter")
    print("=" * 60)
    print(f"Intervals file: {args.intervals}")
    print(f"Event file: {args.event_file}")
    print(f"Output directory: {args.output_dir}")
    print()
    
    # Load intervals from JSON
    with open(args.intervals, 'r') as f:
        data = json.load(f)
    
    intervals = data['intervals']
    print(f"Loaded {len(intervals)} measurement intervals")
    
    # Create output directory
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Convert to absolute seconds (GPS epoch)
    print("\nConverting times to absolute seconds...")
    intervals_abs = []
    for interval in intervals:
        filename = interval['filename']
        start_dt = parse_iso_datetime(interval['start'])
        end_dt = parse_iso_datetime(interval['end'])
        start_abs = convert_to_absolute_seconds(start_dt)
        end_abs = convert_to_absolute_seconds(end_dt)
        intervals_abs.append((filename, start_abs, end_abs))
        print(f"  {filename}")
        print(f"    Start: {interval['start']} -> {start_abs:.2f} s")
        print(f"    End: {interval['end']} -> {end_abs:.2f} s")
    
    # Create filter table workspace
    print("\nCreating filter table workspace...")
    filter_table = create_table_workspace(
        'eis_measurement_filter',
        [('float', 'start'), ('float', 'stop'), ('str', 'target')]
    )
    
    for i, (filename, start_abs, end_abs) in enumerate(intervals_abs):
        target = str(i)
        filter_table.addRow((start_abs, end_abs, target))
    
    # Load event data
    print(f"\nLoading event data from: {args.event_file}")
    event_ws = Load(Filename=args.event_file, OutputWorkspace='event_data')
    
    # Filter events
    print("\nFiltering events...")
    FilterEvents(
        InputWorkspace='event_data',
        SplitterWorkspace='eis_measurement_filter',
        GroupWorkspaces=True,
        OutputWorkspaceBaseName=args.prefix,
        FilterByPulseTime=True,
        OutputWorkspaceIndexedFrom1=False,
        CorrectionToSample='None',
        SpectrumWithoutDetector='Skip',
        SplitSampleLogs=False,
        OutputTOFCorrectionWorkspace='mock',
        RelativeTime=False,
    )
    
    # Save filtered workspaces
    print("\nSaving filtered workspaces...")
    for i, interval in enumerate(intervals):
        ws_name = f"{args.prefix}_{i}"
        if ws_name in mtd:
            filename = interval['filename']
            clean_name = filename.replace('.mpt', '').replace(',', '_')
            output_file = os.path.join(args.output_dir, f"{clean_name}_filtered.nxs")
            SaveNexus(InputWorkspace=ws_name, Filename=output_file)
            print(f"  Saved: {output_file}")
        else:
            print(f"  Warning: Workspace {ws_name} not found")
    
    print("\nFiltering complete!")
    print(f"Output directory: {args.output_dir}")


if __name__ == '__main__':
    main()
