#!/usr/bin/env python3
"""
EIS Interval Extractor

Extract timing intervals from EIS (Electrochemical Impedance Spectroscopy)
.mpt files and output as JSON for use with Mantid event filtering scripts.

Supports two resolution modes:
- Per-file: One interval per EIS file (coarse, good for reduction)
- Per-frequency: One interval per frequency measurement (fine, for detailed analysis)
"""

import argparse
import glob
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


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


def read_frequency_measurements(filepath: str) -> List[Dict]:
    """
    Read individual frequency measurements from an EIS .mpt file.
    
    Args:
        filepath: Path to the .mpt file
        
    Returns:
        List of dictionaries with timing for each frequency measurement
    """
    header_info = parse_mpt_header(filepath)
    
    if header_info['acquisition_start'] is None:
        raise ValueError(f"Could not find acquisition start time in {filepath}")
    
    with open(filepath, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    # Find column indices
    column_names = header_info['column_names']
    time_idx = column_names.index('time/s') if 'time/s' in column_names else 5
    freq_idx = 0  # freq/Hz is typically first column
    
    measurements = []
    data_lines = lines[header_info['num_header_lines']:]
    
    for line in data_lines:
        line = line.strip()
        if not line:
            continue
            
        parts = line.split('\t')
        if len(parts) <= max(time_idx, freq_idx):
            continue
        
        try:
            time_s = float(parts[time_idx])
            freq_hz = float(parts[freq_idx])
            wall_clock = header_info['acquisition_start'] + timedelta(seconds=time_s)
            
            measurements.append({
                'frequency_hz': freq_hz,
                'time_seconds': time_s,
                'wall_clock': wall_clock
            })
        except (ValueError, IndexError):
            continue
    
    return measurements


def extract_per_file_intervals(
    data_dir: str,
    pattern: str = '*C02_?.mpt',
    exclude: str = 'fit',
    verbose: bool = True
) -> List[Dict]:
    """
    Extract one interval per EIS file (coarse resolution).
    
    Each interval spans from acquisition start to end of last measurement.
    
    Args:
        data_dir: Directory containing .mpt files
        pattern: Glob pattern to match files
        exclude: Exclude files containing this string
        verbose: Print progress messages
        
    Returns:
        List of interval dictionaries
    """
    data_dir = Path(data_dir)
    all_files = glob.glob(str(data_dir / pattern))
    files = sorted([f for f in all_files if exclude not in Path(f).name])
    
    if not files:
        raise ValueError(f"No files found matching pattern {pattern} in {data_dir}")
    
    intervals = []
    
    for filepath in files:
        filename = Path(filepath).name
        if verbose:
            print(f"Processing: {filename}")
        
        try:
            header_info = parse_mpt_header(filepath)
            start_time = header_info['acquisition_start']
            
            if start_time is None:
                if verbose:
                    print(f"  Warning: No acquisition start time, skipping")
                continue
            
            measurements = read_frequency_measurements(filepath)
            if not measurements:
                if verbose:
                    print(f"  Warning: No measurements found, skipping")
                continue
            
            end_time = measurements[-1]['wall_clock']
            duration = (end_time - start_time).total_seconds()
            
            if verbose:
                print(f"  Start: {start_time.isoformat()}")
                print(f"  End: {end_time.isoformat()}")
                print(f"  Duration: {duration:.2f}s, {len(measurements)} frequencies")
            
            intervals.append({
                'filename': filename,
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'duration_seconds': duration,
                'n_frequencies': len(measurements)
            })
            
        except Exception as e:
            if verbose:
                print(f"  Error: {e}")
    
    return intervals


def extract_per_frequency_intervals(
    data_dir: str,
    pattern: str = '*C02_?.mpt',
    exclude: str = 'fit',
    verbose: bool = True
) -> List[Dict]:
    """
    Extract one interval per frequency measurement (fine resolution).
    
    Each interval spans from one frequency measurement to the next.
    
    Args:
        data_dir: Directory containing .mpt files
        pattern: Glob pattern to match files
        exclude: Exclude files containing this string
        verbose: Print progress messages
        
    Returns:
        List of interval dictionaries
    """
    data_dir = Path(data_dir)
    all_files = glob.glob(str(data_dir / pattern))
    files = sorted([f for f in all_files if exclude not in Path(f).name])
    
    if not files:
        raise ValueError(f"No files found matching pattern {pattern} in {data_dir}")
    
    intervals = []
    
    for filepath in files:
        filename = Path(filepath).name
        if verbose:
            print(f"Processing: {filename}")
        
        try:
            measurements = read_frequency_measurements(filepath)
            
            if len(measurements) < 2:
                if verbose:
                    print(f"  Warning: Not enough measurements for intervals")
                continue
            
            if verbose:
                print(f"  Found {len(measurements)} frequency measurements")
            
            # Create intervals between consecutive measurements
            for i in range(len(measurements) - 1):
                start = measurements[i]['wall_clock']
                end = measurements[i + 1]['wall_clock']
                duration = (end - start).total_seconds()
                
                intervals.append({
                    'filename': filename,
                    'frequency_hz': measurements[i]['frequency_hz'],
                    'measurement_index': i,
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                    'duration_seconds': duration
                })
            
        except Exception as e:
            if verbose:
                print(f"  Error: {e}")
    
    if verbose:
        print(f"\nTotal intervals: {len(intervals)}")
    
    return intervals


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description='Extract EIS timing intervals and output as JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Resolution modes:
  per-file       One interval per EIS file (default, good for reduction)
  per-frequency  One interval per frequency measurement (detailed analysis)

Examples:
  # Extract per-file intervals (default)
  eis-interval-extractor --data-dir /path/to/eis/data --output intervals.json
  
  # Extract per-frequency intervals
  eis-interval-extractor --data-dir /path/to/eis/data --resolution per-frequency -o intervals.json
  
  # Print to stdout
  eis-interval-extractor --data-dir /path/to/eis/data --quiet

The output JSON can be used with Mantid scripts in scripts/mantid/ for
event filtering and reduction.
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
        '--resolution',
        type=str,
        choices=['per-file', 'per-frequency'],
        default='per-file',
        help='Interval resolution (default: per-file)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output JSON file path. If not specified, prints to stdout.'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress messages'
    )
    
    args = parser.parse_args()
    
    if not args.quiet:
        print("EIS Interval Extractor")
        print("=" * 60)
        print(f"Data directory: {args.data_dir}")
        print(f"File pattern: {args.pattern}")
        print(f"Resolution: {args.resolution}")
        print()
    
    # Extract intervals based on resolution
    if args.resolution == 'per-file':
        intervals = extract_per_file_intervals(
            args.data_dir, args.pattern, args.exclude, verbose=not args.quiet
        )
    else:
        intervals = extract_per_frequency_intervals(
            args.data_dir, args.pattern, args.exclude, verbose=not args.quiet
        )
    
    if not intervals:
        print("\nError: No valid intervals found")
        return 1
    
    # Create output structure
    output = {
        'source_directory': str(Path(args.data_dir).resolve()),
        'pattern': args.pattern,
        'resolution': args.resolution,
        'n_intervals': len(intervals),
        'intervals': intervals
    }
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        if not args.quiet:
            print(f"\nSaved {len(intervals)} intervals to: {args.output}")
    else:
        print(json.dumps(output, indent=2))
    
    return 0


if __name__ == '__main__':
    exit(main())
