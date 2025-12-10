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

mantid.kernel.config.setLogLevel(3)

# Import LiquidsReflectometer reduction modules
from lr_reduction import template
from lr_reduction.event_reduction import apply_dead_time_correction, compute_resolution


def create_table_workspace(table_ws_name, column_def_list):
    """Create an empty table workspace with specified columns."""
    api.CreateEmptyTableWorkspace(OutputWorkspace=table_ws_name)
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
    """Convert datetime to seconds relative to GPS epoch (1990-01-01)."""
    gps_epoch = datetime64('1990-01-01T00:00:00')
    dt64 = datetime64(dt.isoformat())
    delta = dt64 - gps_epoch
    return float(delta / timedelta64(1, 's'))


def reduce_and_save(ws, template_data, output_path, ws_db=None):
    """
    Reduce a single workspace and save the result.
    
    This follows the same approach as reduce_slices_ws from LiquidsReflectometer.
    """
    try:
        # Process using template
        _reduced = template.process_from_template_ws(
            ws, template_data, ws_db=ws_db
        )
        
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


def plot_slices(reduced_list, eis_names, output_path, offset=10):
    """Create a summary plot of all reduced slices."""
    try:
        from matplotlib import pyplot as plt
        
        fig, ax = plt.subplots(figsize=(8, 8))
        
        _running_offset = 1.0
        for i, (_data, name) in enumerate(zip(reduced_list, eis_names)):
            if _data is None:
                continue
            qz, refl, d_refl, _ = _data
            plt.errorbar(
                qz, refl * _running_offset, yerr=d_refl * _running_offset,
                markersize=4, marker='o', label=f"{i}: {name[:30]}..."
            )
            _running_offset *= offset
        
        plt.legend(fontsize=8)
        plt.xlabel(r"Q [$1/\AA$]")
        plt.ylabel("R(Q)")
        ax.set_yscale('log')
        ax.set_xscale('log')
        plt.title("Time-Resolved Reflectivity (EIS Intervals)")
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        print(f"  Saved plot: {output_path}")
    except Exception as e:
        print(f"  Error creating plot: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Filter and reduce neutron events by EIS measurement intervals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python eis_reduce_events.py \\
        --intervals /path/to/intervals.json \\
        --event-file /SNS/REF_L/IPTS-XXXXX/nexus/REF_L_12345.nxs.h5 \\
        --template /SNS/REF_L/IPTS-XXXXX/shared/templates/template.xml \\
        --output-dir ./reduced_data
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
        '--template',
        type=str,
        required=True,
        help='Path to reduction template file (.xml)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./reduced_data',
        help='Directory for output files (default: ./reduced_data)'
    )
    parser.add_argument(
        '--scan-index',
        type=int,
        default=1,
        help='Scan index to use within the template (default: 1)'
    )
    parser.add_argument(
        '--theta-offset',
        type=float,
        default=0.0,
        help='Theta offset to apply during reduction (default: 0.0)'
    )
    parser.add_argument(
        '--no-plot',
        action='store_true',
        help='Skip creating summary plot'
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
    with open(args.intervals, 'r') as f:
        data = json.load(f)
    
    intervals = data['intervals']
    print(f"Loaded {len(intervals)} measurement intervals")
    
    # Create output directory
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Save options for reproducibility
    options = {
        'intervals_file': args.intervals,
        'event_file': args.event_file,
        'template_file': args.template,
        'output_dir': args.output_dir,
        'scan_index': args.scan_index,
        'theta_offset': args.theta_offset,
        'n_intervals': len(intervals),
    }
    with open(os.path.join(args.output_dir, 'reduction_options.json'), 'w') as fp:
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
        duration = meas_ws.getRun()['duration'].value
    except:
        duration = 0
    try:
        meas_run = meas_ws.getRun()['run_number'].value
    except:
        meas_run = 0
    
    # Apply dead time correction up front
    if template_data.dead_time:
        print("Applying dead time correction to sample data...")
        apply_dead_time_correction(meas_ws, template_data)
    
    # Convert intervals to absolute seconds for filtering
    print("\nConverting time intervals...")
    intervals_abs = []
    for interval in intervals:
        filename = interval['filename']
        start_dt = parse_iso_datetime(interval['start'])
        end_dt = parse_iso_datetime(interval['end'])
        start_abs = convert_to_absolute_seconds(start_dt)
        end_abs = convert_to_absolute_seconds(end_dt)
        intervals_abs.append((filename, start_abs, end_abs))
        duration_s = end_abs - start_abs
        print(f"  {filename[:50]}... ({duration_s:.1f}s)")
    
    # Create filter table workspace
    print("\nCreating filter table...")
    filter_table = create_table_workspace(
        'eis_filter',
        [('float', 'start'), ('float', 'stop'), ('str', 'target')]
    )
    
    for i, (filename, start_abs, end_abs) in enumerate(intervals_abs):
        filter_table.addRow((start_abs, end_abs, str(i)))
    
    # Filter events by EIS measurement intervals
    print("\nFiltering events by EIS intervals...")
    api.FilterEvents(
        InputWorkspace=meas_ws,
        SplitterWorkspace='eis_filter',
        GroupWorkspaces=True,
        OutputWorkspaceBaseName='eis_measurement',
        FilterByPulseTime=True,
        OutputWorkspaceIndexedFrom1=False,
        CorrectionToSample='None',
        SpectrumWithoutDetector='Skip',
        SplitSampleLogs=False,
        OutputTOFCorrectionWorkspace='mock',
        RelativeTime=False,
    )
    
    wsgroup = mtd['eis_measurement']
    wsnames = wsgroup.getNames()
    print(f"Created {len(wsnames)} filtered workspaces")
    
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
        eis_filename = intervals[i]['filename']
        print(f"\nWorkspace {name}: {n_events} events")
        print(f"  EIS file: {eis_filename}")
        
        # Create output filename
        clean_name = eis_filename.replace('.mpt', '').replace(',', '_')
        output_file = os.path.join(args.output_dir, f"r{meas_run}_{clean_name}.txt")
        
        # Reduce and save
        _reduced = reduce_and_save(tmpws, template_data, output_file, ws_db=ws_db)
        reduced_list.append(_reduced)
        eis_names.append(eis_filename)
    
    # Create summary plot
    if not args.no_plot:
        print("\nCreating summary plot...")
        plot_file = os.path.join(args.output_dir, f"r{meas_run}_eis_summary.png")
        plot_slices(reduced_list, eis_names, plot_file)
    
    # Save reduction summary as JSON
    print("\nSaving reduction summary...")
    summary = {
        'run_number': int(meas_run),
        'duration': float(duration),
        'n_intervals': len(intervals),
        'intervals': [
            {'eis_file': i['filename'], 'start': i['start'], 'end': i['end']}
            for i in intervals
        ],
        'reduced_files': [
            os.path.join(
                args.output_dir,
                f"r{meas_run}_{i['filename'].replace('.mpt', '').replace(',', '_')}.txt"
            )
            for i in intervals
        ],
    }
    with open(os.path.join(args.output_dir, f"r{meas_run}_eis_reduction.json"), 'w') as fp:
        json.dump(summary, fp, indent=2)
    
    print("\n" + "=" * 60)
    print("Reduction complete!")
    print(f"  Output directory: {args.output_dir}")
    print(f"  Reduced files: {len([r for r in reduced_list if r is not None])}")
    print("=" * 60)


if __name__ == '__main__':
    main()
