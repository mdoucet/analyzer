#!/usr/bin/env python3
"""
EIS Timing Extractor

Extract timing information from EIS (Electrochemical Impedance Spectroscopy) 
.mpt files and compute wall clock times for each measurement.

This tool reads EC-Lab ASCII files (.mpt) and extracts:
- The first four data columns (freq/Hz, Re(Z)/Ohm, -Im(Z)/Ohm, |Z|/Ohm)
- Cumulative time from the beginning of the measurement
- Wall clock time in ISO 8601 format

The wall clock time is calculated by adding the cumulative measurement time
to the acquisition start time found in the file header.
"""

import argparse
import os
import re
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import csv


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


def read_eis_data(filepath: str) -> List[Dict]:
    """
    Read EIS data from an .mpt file.
    
    Args:
        filepath: Path to the .mpt file
        
    Returns:
        List of dictionaries containing the extracted data with columns:
        - freq_hz: Frequency in Hz
        - re_z: Real part of impedance (Ohm)
        - neg_im_z: Negative imaginary part of impedance (Ohm)
        - abs_z: Absolute value of impedance (Ohm)
        - time_s: Original time column (seconds)
        - cumulative_time_s: Cumulative time from start (seconds)
        - wall_clock_time: Wall clock time (ISO 8601)
    """
    header_info = parse_mpt_header(filepath)
    
    if header_info['acquisition_start'] is None:
        raise ValueError(f"Could not find acquisition start time in {filepath}")
    
    data = []
    cumulative_time = 0.0
    
    with open(filepath, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    # Skip header lines and process data
    data_lines = lines[header_info['num_header_lines']:]
    
    # Find column indices
    column_names = header_info['column_names']
    try:
        freq_idx = 0  # freq/Hz is first column
        re_z_idx = 1  # Re(Z)/Ohm
        neg_im_z_idx = 2  # -Im(Z)/Ohm
        abs_z_idx = 3  # |Z|/Ohm
        time_idx = column_names.index('time/s') if 'time/s' in column_names else 5
    except (ValueError, IndexError):
        # Default indices if columns not found
        time_idx = 5
    
    prev_time = 0.0
    
    for line in data_lines:
        line = line.strip()
        if not line:
            continue
            
        parts = line.split('\t')
        if len(parts) < 6:
            continue
        
        try:
            freq_hz = float(parts[freq_idx])
            re_z = float(parts[re_z_idx])
            neg_im_z = float(parts[neg_im_z_idx])
            abs_z = float(parts[abs_z_idx])
            time_s = float(parts[time_idx])
            
            # Calculate cumulative time
            # The time column appears to be cumulative already
            cumulative_time = time_s
            
            # Calculate wall clock time
            wall_clock = header_info['acquisition_start'] + timedelta(seconds=cumulative_time)
            
            data.append({
                'freq_hz': freq_hz,
                're_z': re_z,
                'neg_im_z': neg_im_z,
                'abs_z': abs_z,
                'time_s': time_s,
                'cumulative_time_s': cumulative_time,
                'wall_clock_time': wall_clock.isoformat()
            })
            
            prev_time = time_s
            
        except (ValueError, IndexError) as e:
            # Skip lines that can't be parsed
            continue
    
    return data


def process_eis_file(filepath: str, output_path: Optional[str] = None) -> List[Dict]:
    """
    Process a single EIS .mpt file and optionally save to CSV.
    
    Args:
        filepath: Path to the .mpt file
        output_path: Optional path for output CSV file
        
    Returns:
        List of dictionaries with extracted data
    """
    print(f"Processing: {filepath}")
    
    data = read_eis_data(filepath)
    
    if output_path:
        save_to_csv(data, output_path)
        print(f"  Saved to: {output_path}")
    
    print(f"  Extracted {len(data)} data points")
    if data:
        print(f"  Time range: {data[0]['wall_clock_time']} to {data[-1]['wall_clock_time']}")
    
    return data


def process_eis_directory(data_dir: str, pattern: str = '*C02_?.mpt',
                          output_dir: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Process all matching EIS files in a directory.
    
    Args:
        data_dir: Directory containing EIS .mpt files
        pattern: Glob pattern for matching files (excludes files with 'fit')
        output_dir: Optional directory for output CSV files
        
    Returns:
        Dictionary mapping filenames to their extracted data
    """
    # Find matching files
    search_pattern = os.path.join(data_dir, pattern)
    files = glob.glob(search_pattern)
    
    # Exclude files with 'fit' in the name
    files = [f for f in files if 'fit' not in os.path.basename(f).lower()]
    
    # Sort files naturally (by sequence number)
    def extract_sequence_num(filepath):
        basename = os.path.basename(filepath)
        match = re.search(r'sequence_(\d+)', basename)
        if match:
            return int(match.group(1))
        match = re.search(r'C02_(\d+)', basename)
        if match:
            return int(match.group(1))
        return 0
    
    files.sort(key=extract_sequence_num)
    
    if not files:
        print(f"No files found matching pattern: {search_pattern}")
        return {}
    
    print(f"Found {len(files)} files to process")
    
    results = {}
    
    for filepath in files:
        basename = os.path.basename(filepath)
        
        # Determine output path
        output_path = None
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_name = os.path.splitext(basename)[0] + '_timing.csv'
            output_path = os.path.join(output_dir, output_name)
        
        try:
            data = process_eis_file(filepath, output_path)
            results[basename] = data
        except Exception as e:
            print(f"  Error processing {basename}: {e}")
            continue
    
    return results


def save_to_csv(data: List[Dict], output_path: str):
    """
    Save extracted data to a CSV file.
    
    Args:
        data: List of dictionaries with extracted data
        output_path: Path to output CSV file
    """
    if not data:
        return
    
    fieldnames = ['freq_hz', 're_z', 'neg_im_z', 'abs_z', 'time_s', 
                  'cumulative_time_s', 'wall_clock_time']
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def get_timing_boundaries(data: List[Dict]) -> List[Tuple[str, str]]:
    """
    Extract timing boundaries from EIS data for event splitting.
    
    This creates time intervals where each interval corresponds to
    the time between consecutive EIS measurements.
    
    Args:
        data: List of dictionaries with extracted data
        
    Returns:
        List of (start_time, end_time) tuples in ISO 8601 format
    """
    if len(data) < 2:
        return []
    
    boundaries = []
    for i in range(len(data) - 1):
        start_time = data[i]['wall_clock_time']
        end_time = data[i + 1]['wall_clock_time']
        boundaries.append((start_time, end_time))
    
    return boundaries


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Extract timing information from EIS .mpt files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single file
  python eis_timing_extractor.py --file data.mpt --output timing.csv
  
  # Process all files in a directory
  python eis_timing_extractor.py --data-dir /path/to/ec-data --output-dir ./output
  
  # Use custom file pattern
  python eis_timing_extractor.py --data-dir /path/to/ec-data --pattern "*C02_*.mpt"
"""
    )
    
    parser.add_argument('--file', '-f', type=str,
                        help='Path to a single .mpt file to process')
    parser.add_argument('--data-dir', '-d', type=str,
                        help='Directory containing EIS .mpt files')
    parser.add_argument('--pattern', '-p', type=str, default='*C02_?.mpt',
                        help='Glob pattern for matching files (default: *C02_?.mpt)')
    parser.add_argument('--output', '-o', type=str,
                        help='Output file path (for single file mode)')
    parser.add_argument('--output-dir', type=str,
                        help='Output directory for processed files')
    parser.add_argument('--boundaries', '-b', action='store_true',
                        help='Print timing boundaries for event splitting')
    
    args = parser.parse_args()
    
    if args.file:
        # Process single file
        data = process_eis_file(args.file, args.output)
        
        if args.boundaries:
            print("\nTiming boundaries for event splitting:")
            boundaries = get_timing_boundaries(data)
            for i, (start, end) in enumerate(boundaries):
                print(f"  {i}: {start} -> {end}")
                
    elif args.data_dir:
        # Process directory
        results = process_eis_directory(args.data_dir, args.pattern, args.output_dir)
        
        if args.boundaries and results:
            print("\nTiming boundaries summary:")
            for filename, data in results.items():
                if data:
                    print(f"\n{filename}:")
                    print(f"  Start: {data[0]['wall_clock_time']}")
                    print(f"  End: {data[-1]['wall_clock_time']}")
                    print(f"  Points: {len(data)}")
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
