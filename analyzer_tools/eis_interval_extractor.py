#!/usr/bin/env python3
"""
EIS Interval Extractor

Extract timing intervals from EIS (Electrochemical Impedance Spectroscopy)
.mpt files and output as JSON for use with Mantid event filtering scripts.

Supports two resolution modes:
- Per-file: One interval per EIS file (coarse, good for reduction)
- Per-frequency: One interval per frequency measurement (fine, for detailed analysis)
"""

import glob
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import click


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
        List of dictionaries with timing, Ewe, and impedance data for each frequency measurement
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
    
    # Helper function to find column index by name
    def find_column(name: str) -> Optional[int]:
        for i, col in enumerate(column_names):
            if col.strip() == name:
                return i
        return None
    
    # Find column indices for EIS data
    ewe_idx = find_column('<Ewe>/V')
    z_idx = find_column('|Z|/Ohm')
    im_z_idx = find_column('Im(Z)/Ohm')
    phase_idx = find_column('Phase(Z)/deg')
    
    measurements = []
    data_lines = lines[header_info['num_header_lines']:]
    
    def safe_float(parts: List[str], idx: Optional[int]) -> Optional[float]:
        """Safely extract a float value from parts list."""
        if idx is None or idx >= len(parts):
            return None
        try:
            return float(parts[idx])
        except ValueError:
            return None
    
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
                'wall_clock': wall_clock,
                'ewe_v': safe_float(parts, ewe_idx),
                'z_ohm': safe_float(parts, z_idx),
                'im_z_ohm': safe_float(parts, im_z_idx),
                'phase_deg': safe_float(parts, phase_idx)
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
            
            # Calculate average Ewe from all measurements
            ewe_values = [m['ewe_v'] for m in measurements if m['ewe_v'] is not None]
            avg_ewe = sum(ewe_values) / len(ewe_values) if ewe_values else None
            
            if verbose:
                print(f"  Start: {start_time.isoformat()}")
                print(f"  End: {end_time.isoformat()}")
                print(f"  Duration: {duration:.2f}s, {len(measurements)} frequencies")
                if avg_ewe is not None:
                    print(f"  Avg <Ewe>: {avg_ewe:.4f} V")
            
            interval_data = {
                'filename': filename,
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'duration_seconds': duration,
                'n_frequencies': len(measurements)
            }
            if avg_ewe is not None:
                interval_data['avg_ewe_v'] = avg_ewe
            
            intervals.append(interval_data)
            
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
                
                interval_data = {
                    'filename': filename,
                    'frequency_hz': measurements[i]['frequency_hz'],
                    'measurement_index': i,
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                    'duration_seconds': duration
                }
                
                # Add EIS data if available
                m = measurements[i]
                if m['ewe_v'] is not None:
                    interval_data['ewe_v'] = m['ewe_v']
                if m['z_ohm'] is not None:
                    interval_data['z_ohm'] = m['z_ohm']
                if m['im_z_ohm'] is not None:
                    interval_data['im_z_ohm'] = m['im_z_ohm']
                if m['phase_deg'] is not None:
                    interval_data['phase_deg'] = m['phase_deg']
                
                intervals.append(interval_data)
            
        except Exception as e:
            if verbose:
                print(f"  Error: {e}")
    
    if verbose:
        print(f"\nTotal intervals: {len(intervals)}")
    
    return intervals


@click.command()
@click.option(
    '--data-dir',
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help='Directory containing EIS .mpt files'
)
@click.option(
    '--pattern',
    type=str,
    default='*C02_?.mpt',
    show_default=True,
    help='Glob pattern to match files'
)
@click.option(
    '--exclude',
    type=str,
    default='fit',
    show_default=True,
    help='Exclude files containing this string'
)
@click.option(
    '--resolution',
    type=click.Choice(['per-file', 'per-frequency'], case_sensitive=False),
    default='per-file',
    show_default=True,
    help='Interval resolution mode'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    default=None,
    help='Output JSON file path. If not specified, prints to stdout.'
)
@click.option(
    '--quiet', '-q',
    is_flag=True,
    help='Suppress progress messages'
)
def main(data_dir: str, pattern: str, exclude: str, resolution: str,
         output: Optional[str], quiet: bool) -> int:
    """Extract EIS timing intervals and output as JSON.

    Resolution modes:

    \b
      per-file       One interval per EIS file (default, good for reduction)
      per-frequency  One interval per frequency measurement (detailed analysis)

    Examples:

    \b
      # Extract per-file intervals (default)
      eis-interval-extractor --data-dir /path/to/eis/data --output intervals.json

    \b
      # Extract per-frequency intervals
      eis-interval-extractor --data-dir /path/to/eis/data --resolution per-frequency -o intervals.json

    \b
      # Print to stdout
      eis-interval-extractor --data-dir /path/to/eis/data --quiet

    The output JSON can be used with Mantid scripts in scripts/mantid/ for
    event filtering and reduction.
    """
    if not quiet:
        print("EIS Interval Extractor")
        print("=" * 60)
        print(f"Data directory: {data_dir}")
        print(f"File pattern: {pattern}")
        print(f"Resolution: {resolution}")
        print()
    
    # Extract intervals based on resolution
    if resolution == 'per-file':
        intervals = extract_per_file_intervals(
            data_dir, pattern, exclude, verbose=not quiet
        )
    else:
        intervals = extract_per_frequency_intervals(
            data_dir, pattern, exclude, verbose=not quiet
        )
    
    if not intervals:
        print("\nError: No valid intervals found")
        return 1
    
    # Create output structure
    result = {
        'source_directory': str(Path(data_dir).resolve()),
        'pattern': pattern,
        'resolution': resolution,
        'n_intervals': len(intervals),
        'intervals': intervals
    }
    
    # Output
    if output:
        with open(output, 'w') as f:
            json.dump(result, f, indent=2)
        if not quiet:
            print(f"\nSaved {len(intervals)} intervals to: {output}")
    else:
        print(json.dumps(result, indent=2))
    
    return 0


if __name__ == '__main__':
    exit(main())
