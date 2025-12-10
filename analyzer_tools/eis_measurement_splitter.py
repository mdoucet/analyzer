#!/usr/bin/env python3
"""
EIS Measurement-Based Event Splitter

Generate Mantid event filtering scripts based on complete EIS measurement intervals.
Each EIS file (.mpt) becomes one time interval, from acquisition start to end of last measurement.
"""

import argparse
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Dict
import re


def parse_mpt_header(filepath: str) -> Dict[str, any]:
    """
    Parse the header of an EC-Lab .mpt file.
    
    Args:
        filepath: Path to the .mpt file
        
    Returns:
        Dictionary containing:
        - 'num_header_lines': Number of header lines
        - 'acquisition_start': Datetime of acquisition start
        - 'column_names': List of column names
    """
    header_info = {
        'num_header_lines': 0,
        'acquisition_start': None,
        'column_names': []
    }
    
    with open(filepath, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    # Find number of header lines
    for line in lines[:10]:
        if line.startswith('Nb header lines'):
            match = re.search(r':\s*(\d+)', line)
            if match:
                header_info['num_header_lines'] = int(match.group(1))
            break
    
    # Find acquisition start time
    for line in lines[:header_info['num_header_lines']]:
        if 'Acquisition started on' in line:
            # Format: "Acquisition started on : 04/20/2025 10:55:16.521"
            match = re.search(r':\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+)', line)
            if match:
                time_str = match.group(1)
                header_info['acquisition_start'] = datetime.strptime(
                    time_str, '%m/%d/%Y %H:%M:%S.%f'
                )
            break
    
    # Get column names from the last header line
    if header_info['num_header_lines'] > 0:
        header_line = lines[header_info['num_header_lines'] - 1].strip()
        header_info['column_names'] = header_line.split('\t')
    
    return header_info


def get_last_measurement_time(filepath: str) -> datetime:
    """
    Get the wall clock time of the last measurement in an EIS file.
    
    Args:
        filepath: Path to the .mpt file
        
    Returns:
        Datetime of the last measurement completion
    """
    header_info = parse_mpt_header(filepath)
    
    if header_info['acquisition_start'] is None:
        raise ValueError(f"Could not find acquisition start time in {filepath}")
    
    with open(filepath, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    # Find the time column index
    column_names = header_info['column_names']
    time_idx = column_names.index('time/s') if 'time/s' in column_names else 5
    
    # Read data lines and find the last valid time entry
    data_lines = lines[header_info['num_header_lines']:]
    last_time = 0.0
    
    for line in reversed(data_lines):
        line = line.strip()
        if not line:
            continue
            
        parts = line.split('\t')
        if len(parts) > time_idx:
            try:
                last_time = float(parts[time_idx])
                break
            except ValueError:
                continue
    
    # Calculate end time
    end_time = header_info['acquisition_start'] + timedelta(seconds=last_time)
    return end_time


def extract_measurement_intervals(data_dir: str, pattern: str = '*C02_?.mpt', 
                                  exclude_pattern: str = 'fit') -> List[Tuple[str, datetime, datetime]]:
    """
    Extract time intervals for each EIS measurement file.
    
    Args:
        data_dir: Directory containing .mpt files
        pattern: Glob pattern to match files
        exclude_pattern: Pattern to exclude from filenames
        
    Returns:
        List of (filename, start_time, end_time) tuples
    """
    data_dir = Path(data_dir)
    
    # Find all matching files
    all_files = glob.glob(str(data_dir / pattern))
    
    # Filter out files containing exclude_pattern
    files = [f for f in all_files if exclude_pattern not in Path(f).name]
    
    if not files:
        raise ValueError(f"No files found matching pattern {pattern} in {data_dir}")
    
    # Sort files for consistent ordering
    files.sort()
    
    intervals = []
    
    for filepath in files:
        filename = Path(filepath).name
        print(f"Processing: {filename}")
        
        try:
            header_info = parse_mpt_header(filepath)
            start_time = header_info['acquisition_start']
            
            if start_time is None:
                print(f"  Warning: Could not find acquisition start time, skipping")
                continue
            
            end_time = get_last_measurement_time(filepath)
            
            duration = (end_time - start_time).total_seconds()
            print(f"  Start: {start_time.isoformat()}")
            print(f"  End: {end_time.isoformat()}")
            print(f"  Duration: {duration:.2f} seconds")
            
            intervals.append((filename, start_time, end_time))
            
        except Exception as e:
            print(f"  Error processing {filename}: {e}")
    
    return intervals


def generate_mantid_script(intervals: List[Tuple[str, datetime, datetime]], 
                          event_file: str,
                          output_script: str,
                          output_dir: str = './filtered_events',
                          workspace_prefix: str = 'eis_measurement',
                          relative: bool = False,
                          run_start: str = None) -> None:
    """
    Generate a Mantid Python script for event filtering.
    
    Args:
        intervals: List of (filename, start_time, end_time) tuples
        event_file: Path to the neutron event data file (HDF5/NeXus)
        output_script: Path for the generated Python script
        output_dir: Directory where filtered workspaces will be saved
        workspace_prefix: Prefix for output workspace names
        relative: If True, use relative time filtering instead of absolute
        run_start: Optional run start time for relative filtering
    """
    script_lines = [
        '#!/usr/bin/env python3',
        '"""',
        'Mantid Event Filtering Script - EIS Measurement Intervals',
        '',
        'This script was auto-generated by eis_measurement_splitter.py',
        'It filters neutron scattering events based on complete EIS measurement intervals.',
        'Each EIS measurement file corresponds to one time interval.',
        '',
        'To run this script, execute it in a Mantid Python environment:',
        f'    python {Path(output_script).name}',
        '',
        'Or run it within MantidWorkbench.',
        '"""',
        '',
        'from datetime import datetime, timedelta',
        'from numpy import datetime64, timedelta64',
        'import os',
        '',
        '# Import Mantid algorithms',
        'from mantid.simpleapi import (',
        '    Load, ',
        '    FilterEvents, ',
        '    CreateEmptyTableWorkspace,',
        '    SaveNexus,',
        '    mtd',
        ')',
        '',
        '',
        'def create_table_workspace(table_ws_name, column_def_list):',
        '    """',
        '    Create an empty table workspace with specified columns.',
        '    ',
        '    Args:',
        '        table_ws_name: Name for the table workspace',
        '        column_def_list: List of (data_type, column_name) tuples',
        '        ',
        '    Returns:',
        '        Table workspace object',
        '    """',
        '    CreateEmptyTableWorkspace(OutputWorkspace=table_ws_name)',
        '    table_ws = mtd[table_ws_name]',
        '    for col_tup in column_def_list:',
        '        data_type = col_tup[0]',
        '        col_name = col_tup[1]',
        '        table_ws.addColumn(data_type, col_name)',
        '    return table_ws',
        '',
        '',
    ]
    
    if not relative:
        script_lines.extend([
            'def parse_iso_datetime(iso_string):',
            '    """Parse ISO datetime string to datetime object."""',
            '    formats = [',
            "        '%Y-%m-%dT%H:%M:%S.%f',",
            "        '%Y-%m-%dT%H:%M:%S',",
            '    ]',
            '    for fmt in formats:',
            '        try:',
            '            return datetime.strptime(iso_string, fmt)',
            '        except ValueError:',
            '            continue',
            '    raise ValueError(f"Could not parse datetime: {iso_string}")',
            '',
            '',
            'def convert_to_absolute_seconds(dt):',
            '    """',
            '    Convert datetime to seconds relative to GPS epoch (1990-01-01).',
            '    ',
            '    This is the format expected by Mantid\'s FilterEvents algorithm',
            '    when using absolute time filtering.',
            '    """',
            "    gps_epoch = datetime64('1990-01-01T00:00:00')",
            '    dt64 = datetime64(dt.isoformat())',
            '    delta = dt64 - gps_epoch',
            "    return float(delta / timedelta64(1, 's'))",
            '',
            '',
        ])
    
    script_lines.extend([
        'def main():',
        '    # Configuration',
        f"    event_file = r'{event_file}'",
        f"    output_dir = r'{output_dir}'",
        f"    workspace_prefix = '{workspace_prefix}'",
        '',
        '    # Create output directory if it doesn\'t exist',
        '    if not os.path.exists(output_dir):',
        '        os.makedirs(output_dir)',
        '',
    ])
    
    if relative:
        script_lines.extend([
            '    # EIS measurement intervals (relative time in seconds)',
            '    # Format: (filename, start_seconds, end_seconds)',
            '    measurement_intervals = [',
        ])
        
        if run_start:
            run_start_dt = datetime.fromisoformat(run_start)
            for filename, start_time, end_time in intervals:
                start_rel = (start_time - run_start_dt).total_seconds()
                end_rel = (end_time - run_start_dt).total_seconds()
                script_lines.append(f"        ('{filename}', {start_rel:.6f}, {end_rel:.6f}),")
        else:
            # Use first interval start as reference
            ref_time = intervals[0][1]
            for filename, start_time, end_time in intervals:
                start_rel = (start_time - ref_time).total_seconds()
                end_rel = (end_time - ref_time).total_seconds()
                script_lines.append(f"        ('{filename}', {start_rel:.6f}, {end_rel:.6f}),")
        
        script_lines.extend([
            '    ]',
            '',
            '    # Create filter table workspace with relative times',
            '    print("Creating filter table workspace...")',
            "    filter_table = create_table_workspace('eis_measurement_filter', ",
            "                                          [('float', 'start'), ",
            "                                           ('float', 'stop'), ",
            "                                           ('str', 'target')])",
            '',
            '    # Add intervals to filter table',
            '    for i, (filename, start_sec, end_sec) in enumerate(measurement_intervals):',
            '        target = str(i)',
            '        filter_table.addRow((start_sec, end_sec, target))',
            '        print(f"  Interval {i}: {filename}")',
            '        print(f"    Start: {start_sec:.2f} s")',
            '        print(f"    End: {end_sec:.2f} s")',
            '',
            '    # Load event data',
            '    print(f"\\nLoading event data from: {event_file}")',
            "    event_ws = Load(Filename=event_file, OutputWorkspace='event_data')",
            '',
            '    # Filter events',
            '    print("\\nFiltering events...")',
            '    FilterEvents(',
            "        InputWorkspace='event_data',",
            "        SplitterWorkspace='eis_measurement_filter',",
            '        GroupWorkspaces=True,',
            f"        OutputWorkspaceBaseName='{workspace_prefix}',",
            '        RelativeTime=True',
            '    )',
            '',
        ])
    else:
        script_lines.extend([
            '    # EIS measurement intervals (ISO format datetime strings)',
            '    # Format: (filename, start_time, end_time)',
            '    measurement_intervals = [',
        ])
        
        for filename, start_time, end_time in intervals:
            script_lines.append(
                f"        ('{filename}', '{start_time.isoformat()}', '{end_time.isoformat()}'),"
            )
        
        script_lines.extend([
            '    ]',
            '',
            '    # Convert to absolute seconds (GPS epoch)',
            '    print("Converting times to absolute seconds...")',
            '    intervals_abs = []',
            '    for filename, start_iso, end_iso in measurement_intervals:',
            '        start_dt = parse_iso_datetime(start_iso)',
            '        end_dt = parse_iso_datetime(end_iso)',
            '        start_abs = convert_to_absolute_seconds(start_dt)',
            '        end_abs = convert_to_absolute_seconds(end_dt)',
            '        intervals_abs.append((filename, start_abs, end_abs))',
            '        print(f"  {filename}")',
            '        print(f"    Start: {start_iso} -> {start_abs:.2f} s")',
            '        print(f"    End: {end_iso} -> {end_abs:.2f} s")',
            '',
            '    # Create filter table workspace with absolute times',
            '    print("\\nCreating filter table workspace...")',
            "    filter_table = create_table_workspace('eis_measurement_filter', ",
            "                                          [('float', 'start'), ",
            "                                           ('float', 'stop'), ",
            "                                           ('str', 'target')])",
            '',
            '    # Add intervals to filter table',
            '    for i, (filename, start_abs, end_abs) in enumerate(intervals_abs):',
            '        target = str(i)',
            '        filter_table.addRow((start_abs, end_abs, target))',
            '',
            '    # Load event data',
            '    print(f"\\nLoading event data from: {event_file}")',
            "    event_ws = Load(Filename=event_file, OutputWorkspace='event_data')",
            '',
            '    # Filter events',
            '    print("\\nFiltering events...")',
            '    FilterEvents(',
            "        InputWorkspace='event_data',",
            "        SplitterWorkspace='eis_measurement_filter',",
            '        GroupWorkspaces=True,',
            f"        OutputWorkspaceBaseName='{workspace_prefix}',",
            '        RelativeTime=False',
            '    )',
            '',
        ])
    
    script_lines.extend([
        '    # Save filtered workspaces',
        '    print("\\nSaving filtered workspaces...")',
        '    for i, (filename, _, _) in enumerate(measurement_intervals):',
        f"        ws_name = f'{workspace_prefix}_{{i}}'",
        '        if ws_name in mtd:',
        '            # Create a clean filename from the EIS filename',
        '            clean_name = filename.replace(".mpt", "").replace(",", "_")',
        '            output_file = os.path.join(output_dir, f"{clean_name}_filtered.nxs")',
        '            SaveNexus(InputWorkspace=ws_name, Filename=output_file)',
        '            print(f"  Saved: {output_file}")',
        '        else:',
        '            print(f"  Warning: Workspace {ws_name} not found")',
        '',
        '    print("\\nFiltering complete!")',
        '',
        '',
        'if __name__ == "__main__":',
        '    main()',
        ''
    ])
    
    # Write the script
    with open(output_script, 'w') as f:
        f.write('\n'.join(script_lines))
    
    print(f"\nGenerated Mantid script: {output_script}")
    print(f"  Event file: {event_file}")
    print(f"  Output directory: {output_dir}")
    print(f"  Workspace prefix: {workspace_prefix}")
    print(f"  Measurement intervals: {len(intervals)}")
    print(f"  Time mode: {'Relative' if relative else 'Absolute'}")


def generate_mantid_reduction_script(intervals: List[Tuple[str, datetime, datetime]], 
                                     event_file: str,
                                     output_script: str,
                                     template_file: str,
                                     output_dir: str = './reduced_data',
                                     workspace_prefix: str = 'eis_measurement',
                                     scan_index: int = 1,
                                     theta_offset: float = 0.0,
                                     create_plot: bool = True) -> None:
    """
    Generate a Mantid Python script for event filtering AND reduction.
    
    This generates a script similar to reduce_slices_ws from LiquidsReflectometer,
    which filters events and then reduces each slice using a template.
    
    Args:
        intervals: List of (filename, start_time, end_time) tuples
        event_file: Path to the neutron event data file (HDF5/NeXus)
        output_script: Path for the generated Python script
        template_file: Path to the reduction template file (.xml)
        output_dir: Directory where reduced data will be saved
        workspace_prefix: Prefix for output workspace names
        scan_index: Scan index to use within the template
        theta_offset: Theta offset to apply during reduction
        create_plot: Whether to create summary plots
    """
    script_lines = [
        '#!/usr/bin/env python3',
        '"""',
        'Mantid Event Filtering and Reduction Script - EIS Measurement Intervals',
        '',
        'This script was auto-generated by eis_measurement_splitter.py',
        'It filters neutron scattering events based on EIS measurement intervals',
        'and then reduces each slice using the LiquidsReflectometer workflow.',
        '',
        'This follows the same approach as reduce_slices_ws from:',
        'https://github.com/neutrons/LiquidsReflectometer/blob/main/src/lr_reduction/time_resolved.py',
        '',
        'To run this script, execute it in a Mantid Python environment with lr_reduction:',
        f'    python {Path(output_script).name}',
        '',
        'Or run it within MantidWorkbench.',
        '"""',
        '',
        'import json',
        'import os',
        'import sys',
        '',
        'import numpy as np',
        'from datetime import datetime, timedelta',
        'from numpy import datetime64, timedelta64',
        '',
        '# Import Mantid',
        'import mantid',
        'import mantid.simpleapi as api',
        'from mantid.api import mtd',
        '',
        'mantid.kernel.config.setLogLevel(3)',
        '',
        '# Import LiquidsReflectometer reduction modules',
        'from lr_reduction import template',
        'from lr_reduction.event_reduction import apply_dead_time_correction, compute_resolution',
        '',
        '',
        'def create_table_workspace(table_ws_name, column_def_list):',
        '    """Create an empty table workspace with specified columns."""',
        '    api.CreateEmptyTableWorkspace(OutputWorkspace=table_ws_name)',
        '    table_ws = mtd[table_ws_name]',
        '    for col_tup in column_def_list:',
        '        data_type = col_tup[0]',
        '        col_name = col_tup[1]',
        '        table_ws.addColumn(data_type, col_name)',
        '    return table_ws',
        '',
        '',
        'def parse_iso_datetime(iso_string):',
        '    """Parse ISO datetime string to datetime object."""',
        '    formats = [',
        "        '%Y-%m-%dT%H:%M:%S.%f',",
        "        '%Y-%m-%dT%H:%M:%S',",
        '    ]',
        '    for fmt in formats:',
        '        try:',
        '            return datetime.strptime(iso_string, fmt)',
        '        except ValueError:',
        '            continue',
        '    raise ValueError(f"Could not parse datetime: {iso_string}")',
        '',
        '',
        'def convert_to_absolute_seconds(dt):',
        '    """',
        '    Convert datetime to seconds relative to GPS epoch (1990-01-01).',
        '    """',
        "    gps_epoch = datetime64('1990-01-01T00:00:00')",
        '    dt64 = datetime64(dt.isoformat())',
        '    delta = dt64 - gps_epoch',
        "    return float(delta / timedelta64(1, 's'))",
        '',
        '',
        'def reduce_and_save(ws, template_data, output_path, ws_db=None, theta_value=None):',
        '    """',
        '    Reduce a single workspace and save the result.',
        '    ',
        '    This follows the same approach as reduce_slices_ws from LiquidsReflectometer.',
        '    """',
        '    try:',
        '        # Process using template',
        '        _reduced = template.process_from_template_ws(',
        '            ws, template_data, theta_value=theta_value, ws_db=ws_db',
        '        )',
        '        ',
        '        # Compute Q resolution',
        '        dq0 = 0',
        '        dq_slope = compute_resolution(ws)',
        '        dq = dq0 + dq_slope * _reduced[0]',
        '        ',
        '        # Create output array: [Q, R, dR, dQ]',
        '        _reduced = np.asarray([_reduced[0], _reduced[1], _reduced[2], dq])',
        '        ',
        '        # Save to file',
        '        np.savetxt(output_path, _reduced.T)',
        '        print(f"  Saved: {output_path}")',
        '        ',
        '        return _reduced',
        '    except Exception as e:',
        '        print(f"  Error reducing workspace: {e}")',
        '        return None',
        '',
        '',
        'def plot_slices(reduced_list, eis_names, output_path, offset=10):',
        '    """',
        '    Create a summary plot of all reduced slices.',
        '    """',
        '    try:',
        '        from matplotlib import pyplot as plt',
        '        ',
        '        fig, ax = plt.subplots(figsize=(8, 8))',
        '        ',
        '        _running_offset = 1.0',
        '        for i, (_data, name) in enumerate(zip(reduced_list, eis_names)):',
        '            if _data is None:',
        '                continue',
        '            qz, refl, d_refl, _ = _data',
        '            plt.errorbar(qz, refl * _running_offset, yerr=d_refl * _running_offset,',
        '                        markersize=4, marker="o", label=f"{i}: {name[:30]}...")',
        '            _running_offset *= offset',
        '        ',
        '        plt.legend(fontsize=8)',
        '        plt.xlabel(r"Q [$1/\\AA$]")',
        '        plt.ylabel("R(Q)")',
        '        ax.set_yscale("log")',
        '        ax.set_xscale("log")',
        '        plt.title("Time-Resolved Reflectivity (EIS Intervals)")',
        '        plt.tight_layout()',
        '        plt.savefig(output_path, dpi=150)',
        '        print(f"  Saved plot: {output_path}")',
        '    except Exception as e:',
        '        print(f"  Error creating plot: {e}")',
        '',
        '',
        'def main():',
        '    # Configuration',
        f"    event_file = r'{event_file}'",
        f"    template_file = r'{template_file}'",
        f"    output_dir = r'{output_dir}'",
        f"    workspace_prefix = '{workspace_prefix}'",
        f"    scan_index = {scan_index}",
        f"    theta_offset = {theta_offset}",
        f"    create_plot = {create_plot}",
        '',
        '    # Create output directory if it doesn\'t exist',
        '    if not os.path.exists(output_dir):',
        '        os.makedirs(output_dir)',
        '',
        '    # EIS measurement intervals (ISO format datetime strings)',
        '    # Format: (filename, start_time, end_time)',
        '    measurement_intervals = [',
    ]
    
    for filename, start_time, end_time in intervals:
        script_lines.append(
            f"        ('{filename}', '{start_time.isoformat()}', '{end_time.isoformat()}'),"
        )
    
    script_lines.extend([
        '    ]',
        '',
        '    # Save options for reproducibility',
        '    options = dict(',
        '        event_file=event_file,',
        '        template_file=template_file,',
        '        output_dir=output_dir,',
        '        scan_index=scan_index,',
        '        theta_offset=theta_offset,',
        '        n_intervals=len(measurement_intervals),',
        '    )',
        '    with open(os.path.join(output_dir, "reduction_options.json"), "w") as fp:',
        '        json.dump(options, fp, indent=2)',
        '',
        '    # Load the reduction template',
        '    print(f"Loading template: {template_file}")',
        '    template_data = template.read_template(template_file, scan_index)',
        '',
        '    # Apply theta offset',
        '    if theta_offset:',
        '        print(f"Theta offset: {theta_offset}")',
        '        template_data.angle_offset = theta_offset',
        '',
        '    # Load event data',
        '    print(f"\\nLoading event data: {event_file}")',
        '    meas_ws = api.LoadEventNexus(event_file)',
        '',
        '    # Get run metadata',
        '    try:',
        '        duration = meas_ws.getRun()["duration"].value',
        '    except:',
        '        duration = 0',
        '    try:',
        '        meas_run = meas_ws.getRun()["run_number"].value',
        '    except:',
        '        meas_run = 0',
        '',
        '    # Apply dead time correction up front (error events not filtered)',
        '    if template_data.dead_time:',
        '        print("Applying dead time correction to sample data...")',
        '        apply_dead_time_correction(meas_ws, template_data)',
        '',
        '    # Convert intervals to absolute seconds for filtering',
        '    print("\\nConverting time intervals...")',
        '    intervals_abs = []',
        '    for filename, start_iso, end_iso in measurement_intervals:',
        '        start_dt = parse_iso_datetime(start_iso)',
        '        end_dt = parse_iso_datetime(end_iso)',
        '        start_abs = convert_to_absolute_seconds(start_dt)',
        '        end_abs = convert_to_absolute_seconds(end_dt)',
        '        intervals_abs.append((filename, start_abs, end_abs))',
        '        duration_s = end_abs - start_abs',
        '        print(f"  {filename[:50]}... ({duration_s:.1f}s)")',
        '',
        '    # Create filter table workspace',
        '    print("\\nCreating filter table...")',
        "    filter_table = create_table_workspace('eis_filter',",
        "                                          [('float', 'start'),",
        "                                           ('float', 'stop'),",
        "                                           ('str', 'target')])",
        '',
        '    for i, (filename, start_abs, end_abs) in enumerate(intervals_abs):',
        '        filter_table.addRow((start_abs, end_abs, str(i)))',
        '',
        '    # Filter events by EIS measurement intervals',
        '    print("\\nFiltering events by EIS intervals...")',
        '    api.FilterEvents(',
        '        InputWorkspace=meas_ws,',
        "        SplitterWorkspace='eis_filter',",
        '        GroupWorkspaces=True,',
        f"        OutputWorkspaceBaseName='{workspace_prefix}',",
        '        FilterByPulseTime=True,',
        '        OutputWorkspaceIndexedFrom1=False,',
        "        CorrectionToSample='None',",
        "        SpectrumWithoutDetector='Skip',",
        '        SplitSampleLogs=False,',
        "        OutputTOFCorrectionWorkspace='mock',",
        '        RelativeTime=False,',
        '    )',
        '',
        f"    wsgroup = mtd['{workspace_prefix}']",
        '    wsnames = wsgroup.getNames()',
        '    print(f"Created {len(wsnames)} filtered workspaces")',
        '',
        '    # Load direct beam workspace (do this once for efficiency)',
        '    print(f"\\nLoading direct beam: REF_L_{template_data.norm_file}")',
        '    ws_db = api.LoadEventNexus(f"REF_L_{template_data.norm_file}")',
        '',
        '    # Apply dead time correction to direct beam',
        '    if template_data.dead_time:',
        '        print("Applying dead time correction to direct beam...")',
        '        apply_dead_time_correction(ws_db, template_data)',
        '',
        '    # Turn off dead time in template (already applied)',
        '    template_data.dead_time = False',
        '',
        '    # Reduce each filtered workspace',
        '    print("\\nReducing filtered workspaces...")',
        '    reduced_list = []',
        '    eis_names = []',
        '',
        '    for i, name in enumerate(wsnames):',
        '        tmpws = mtd[name]',
        '        n_events = tmpws.getNumberEvents()',
        '        eis_filename = measurement_intervals[i][0]',
        '        print(f"\\nWorkspace {name}: {n_events} events")',
        '        print(f"  EIS file: {eis_filename}")',
        '',
        '        # Create output filename',
        '        clean_name = eis_filename.replace(".mpt", "").replace(",", "_")',
        '        output_file = os.path.join(output_dir, f"r{meas_run}_{clean_name}.txt")',
        '',
        '        # Reduce and save',
        '        _reduced = reduce_and_save(tmpws, template_data, output_file, ws_db=ws_db)',
        '        reduced_list.append(_reduced)',
        '        eis_names.append(eis_filename)',
        '',
        '    # Create summary plot',
        '    if create_plot:',
        '        print("\\nCreating summary plot...")',
        '        plot_file = os.path.join(output_dir, f"r{meas_run}_eis_summary.png")',
        '        plot_slices(reduced_list, eis_names, plot_file)',
        '',
        '    # Save reduction summary as JSON',
        '    print("\\nSaving reduction summary...")',
        '    summary = {',
        '        "run_number": int(meas_run),',
        '        "duration": float(duration),',
        '        "n_intervals": len(measurement_intervals),',
        '        "intervals": [',
        '            {"eis_file": f, "start": s, "end": e}',
        '            for f, s, e in measurement_intervals',
        '        ],',
        '        "reduced_files": [',
        '            os.path.join(output_dir, f"r{meas_run}_{f.replace(\'.mpt\', \'\').replace(\',\', \'_\')}.txt")',
        '            for f, _, _ in measurement_intervals',
        '        ],',
        '    }',
        '    with open(os.path.join(output_dir, f"r{meas_run}_eis_reduction.json"), "w") as fp:',
        '        json.dump(summary, fp, indent=2)',
        '',
        '    print("\\n" + "=" * 60)',
        '    print("Reduction complete!")',
        '    print(f"  Output directory: {output_dir}")',
        '    print(f"  Reduced files: {len([r for r in reduced_list if r is not None])}")',
        '    print("=" * 60)',
        '',
        '',
        'if __name__ == "__main__":',
        '    main()',
        ''
    ])
    
    # Write the script
    with open(output_script, 'w') as f:
        f.write('\n'.join(script_lines))
    
    print(f"\nGenerated Mantid reduction script: {output_script}")
    print(f"  Event file: {event_file}")
    print(f"  Template file: {template_file}")
    print(f"  Output directory: {output_dir}")
    print(f"  Measurement intervals: {len(intervals)}")
    print(f"  Scan index: {scan_index}")
    print(f"  Theta offset: {theta_offset}")


def main():
    """Command-line interface for EIS measurement-based event splitter."""
    parser = argparse.ArgumentParser(
        description='Generate Mantid event filtering based on complete EIS measurement intervals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate script for filtering only (save workspaces)
  eis-measurement-splitter --data-dir /path/to/eis/data \\
      --event-file /path/to/events.nxs.h5 \\
      --output-script mantid_filter.py
  
  # Generate script for filtering AND reduction (like reduce_slices_ws)
  eis-measurement-splitter --data-dir /path/to/eis/data \\
      --event-file /path/to/events.nxs.h5 \\
      --output-script mantid_reduce.py \\
      --reduce --template /path/to/template.xml
  
  # With additional reduction options
  eis-measurement-splitter --data-dir /path/to/eis/data \\
      --event-file /path/to/events.nxs.h5 \\
      --output-script mantid_reduce.py \\
      --reduce --template /path/to/template.xml \\
      --scan-index 5 --theta-offset 0.01
"""
    )
    
    parser.add_argument(
        '--data-dir',
        type=str,
        required=True,
        help='Directory containing EIS .mpt files'
    )
    parser.add_argument(
        '--pattern',
        type=str,
        default='*C02_?.mpt',
        help='Glob pattern to match files (default: *C02_?.mpt)'
    )
    parser.add_argument(
        '--exclude',
        type=str,
        default='fit',
        help='Exclude files containing this string (default: fit)'
    )
    parser.add_argument(
        '--event-file',
        type=str,
        required=True,
        help='Path to neutron event data file (HDF5/NeXus)'
    )
    parser.add_argument(
        '--output-script',
        type=str,
        required=True,
        help='Output path for generated Mantid Python script'
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
    parser.add_argument(
        '--relative',
        action='store_true',
        help='Use relative time filtering instead of absolute'
    )
    parser.add_argument(
        '--run-start',
        type=str,
        help='Run start time for relative filtering (ISO format: 2025-04-20T10:00:00)'
    )
    
    # Reduction options
    parser.add_argument(
        '--reduce',
        action='store_true',
        help='Generate a reduction script instead of just filtering. '
             'This follows the same approach as reduce_slices_ws from LiquidsReflectometer.'
    )
    parser.add_argument(
        '--template',
        type=str,
        help='Path to reduction template file (.xml). Required when --reduce is used.'
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
        help='Skip creating summary plot when reducing'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.reduce and not args.template:
        parser.error("--template is required when using --reduce")
    
    print("EIS Measurement-Based Event Splitter")
    print("=" * 60)
    print(f"Data directory: {args.data_dir}")
    print(f"File pattern: {args.pattern}")
    print(f"Mode: {'Reduction' if args.reduce else 'Filtering only'}")
    print()
    
    # Extract measurement intervals
    intervals = extract_measurement_intervals(
        args.data_dir,
        args.pattern,
        args.exclude
    )
    
    if not intervals:
        print("\nError: No valid measurement intervals found")
        return 1
    
    print(f"\nFound {len(intervals)} measurement intervals")
    print()
    
    if args.reduce:
        # Generate reduction script
        generate_mantid_reduction_script(
            intervals,
            args.event_file,
            args.output_script,
            args.template,
            args.output_dir,
            args.prefix,
            args.scan_index,
            args.theta_offset,
            not args.no_plot
        )
    else:
        # Generate filtering-only script
        generate_mantid_script(
            intervals,
            args.event_file,
            args.output_script,
            args.output_dir,
            args.prefix,
            args.relative,
            args.run_start
        )
    
    print("\nTo run the script, execute it in a Mantid Python environment.")
    
    return 0


if __name__ == '__main__':
    exit(main())
