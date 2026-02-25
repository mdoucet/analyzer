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
    
    # Parse potential steps from header if present (multi-step files)
    header_info['potential_steps'] = parse_potential_steps_from_header(lines, header_info['num_header_lines'])
    
    return header_info


def parse_potential_steps_from_header(lines: List[str], num_header_lines: int) -> Optional[Dict]:
    """
    Parse potential step definitions from EC-Lab header for multi-step PEIS files.
    
    Multi-step files have tabular header lines like:
        Ns                  0                   1                   2   ...
        E (V)               0.0000              -0.1000             -0.1000 ...
        vs.                 Eoc                 Ref                 Ref ...
    
    Note: These lines use fixed-width spacing (not tabs) between values.
    
    Args:
        lines: All lines from the file
        num_header_lines: Number of header lines
        
    Returns:
        Dictionary mapping step number to potential info, or None if not a multi-step file.
        Example: {0: {'E_V': 0.0, 'vs': 'Eoc'}, 1: {'E_V': -0.1, 'vs': 'Ref'}, ...}
    """
    ns_line = None
    e_line = None
    vs_line = None
    
    # Search for the potential step definition lines in the header
    # These lines use fixed-width spacing, so we split on whitespace
    for line in lines[:num_header_lines]:
        stripped = line.strip()
        # Check for Ns line (starts with 'Ns' followed by whitespace and numbers)
        if stripped.startswith('Ns') and not stripped.startswith('Ns\''):
            # Split on whitespace and check for numeric values
            parts = stripped.split()
            if len(parts) > 1 and parts[1].isdigit():
                ns_line = stripped
        elif stripped.startswith('E (V)'):
            parts = stripped.split()
            # Should have label and then numeric values
            if len(parts) > 2:
                e_line = stripped
        elif stripped.startswith('vs.'):
            parts = stripped.split()
            if len(parts) > 1:
                vs_line = stripped
    
    # If we don't have all three lines, this isn't a multi-step file
    if not (ns_line and e_line and vs_line):
        return None
    
    # Parse the lines by splitting on whitespace
    ns_parts = ns_line.split()
    e_parts = e_line.split()
    vs_parts = vs_line.split()
    
    # Skip the label in each line
    # Ns line: ['Ns', '0', '1', '2', ...]
    # E (V) line: ['E', '(V)', '0.0000', '-0.1000', ...]
    # vs. line: ['vs.', 'Eoc', 'Ref', ...]
    ns_values = ns_parts[1:]  # Skip 'Ns'
    e_values = e_parts[2:]    # Skip 'E' and '(V)'
    vs_values = vs_parts[1:]  # Skip 'vs.'
    
    # Build the result dictionary
    potential_steps = {}
    for i, ns_str in enumerate(ns_values):
        try:
            ns = int(ns_str)
            e_v = float(e_values[i]) if i < len(e_values) else None
            vs = vs_values[i] if i < len(vs_values) else None
            potential_steps[ns] = {
                'E_V': e_v,
                'vs': vs
            }
        except (ValueError, IndexError):
            continue
    
    return potential_steps if potential_steps else None


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
    ns_idx = find_column('Ns')  # Step number for multi-step files
    
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
            
            # Get step number if available (for multi-step files)
            ns_value = None
            if ns_idx is not None and ns_idx < len(parts):
                try:
                    ns_value = int(float(parts[ns_idx]))
                except ValueError:
                    pass
            
            measurements.append({
                'frequency_hz': freq_hz,
                'time_seconds': time_s,
                'wall_clock': wall_clock,
                'ewe_v': safe_float(parts, ewe_idx),
                'z_ohm': safe_float(parts, z_idx),
                'im_z_ohm': safe_float(parts, im_z_idx),
                'phase_deg': safe_float(parts, phase_idx),
                'ns': ns_value
            })
        except (ValueError, IndexError):
            continue
    
    return measurements


def split_measurements_by_step(measurements: List[Dict]) -> Dict[int, List[Dict]]:
    """
    Split measurements into groups by step number (Ns).
    
    Args:
        measurements: List of measurement dictionaries with 'ns' field
        
    Returns:
        Dictionary mapping step number to list of measurements for that step.
        Returns empty dict if no step numbers are present.
    """
    by_step = {}
    for m in measurements:
        ns = m.get('ns')
        if ns is not None:
            if ns not in by_step:
                by_step[ns] = []
            by_step[ns].append(m)
    return by_step


def has_multiple_steps(measurements: List[Dict]) -> bool:
    """Check if measurements contain multiple potential steps."""
    steps = set(m.get('ns') for m in measurements if m.get('ns') is not None)
    return len(steps) > 1


def extract_label_for_step(
    filename: str,
    step_number: int,
    potential_info: Optional[Dict] = None
) -> str:
    """
    Generate a label for a specific potential step.
    
    Args:
        filename: Source filename
        step_number: Step number (Ns value)
        potential_info: Optional dict with 'E_V' and 'vs' keys
        
    Returns:
        Label string like "Sample9_step0_0.0V_Eoc" or "Sample9_step1_-0.1V_Ref"
    """
    # Extract base name without extension
    base = filename.replace('.mpt', '').replace(',', '_')
    
    # Truncate if too long
    if len(base) > 40:
        base = base[:40]
    
    # Build label with step info
    if potential_info and potential_info.get('E_V') is not None:
        e_v = potential_info['E_V']
        vs = potential_info.get('vs', '')
        # Format potential with sign
        e_str = f"{e_v:+.2f}V".replace('+', 'p').replace('-', 'm').replace('.', 'p')
        label = f"{base}_step{step_number}_{e_str}"
        if vs:
            label = f"{label}_{vs}"
    else:
        label = f"{base}_step{step_number}"
    
    return label


def extract_label_from_filename(filename: str, pattern: str = None) -> str:
    """
    Extract a short label from an EIS filename.
    
    Looks for patterns like "sequence_N" or similar prefixes.
    Falls back to a cleaned version of the filename if no pattern found.
    
    Args:
        filename: The full filename (e.g., "sequence_1_CuPt_..._C02_1.mpt")
        pattern: Optional glob pattern used to match files (for extracting suffix)
        
    Returns:
        A short label suitable for output naming
    """
    import re
    
    # Try to extract "sequence_N" pattern
    seq_match = re.match(r'(sequence_\d+)', filename)
    if seq_match:
        label = seq_match.group(1)
        
        # Try to extract the file number from pattern match (e.g., C02_1 from *C02_?.mpt)
        if pattern:
            # Extract the variable part from the pattern (e.g., "?" or "*")
            # Look for pattern like C02_N at the end
            suffix_match = re.search(r'_C\d+_(\d+)\.mpt$', filename)
            if suffix_match:
                label = f"{label}_eis_{suffix_match.group(1)}"
        
        return label
    
    # Fallback: use filename without extension, truncated
    clean = filename.replace('.mpt', '').replace(',', '_')
    if len(clean) > 30:
        clean = clean[:30]
    return clean


def generate_hold_intervals(
    start_time: datetime,
    end_time: datetime,
    interval_seconds: float,
    label_prefix: str = "hold"
) -> List[Dict]:
    """
    Generate fixed-duration intervals for a hold period.
    
    Args:
        start_time: Start of the hold period
        end_time: End of the hold period
        interval_seconds: Duration of each interval in seconds
        label_prefix: Prefix for the interval label
        
    Returns:
        List of interval dictionaries
    """
    intervals = []
    current_time = start_time
    idx = 0
    
    while current_time < end_time:
        next_time = current_time + timedelta(seconds=interval_seconds)
        # Don't exceed the end time
        if next_time > end_time:
            next_time = end_time
        
        duration = (next_time - current_time).total_seconds()
        # Only add if duration is meaningful (at least 1 second)
        if duration >= 1.0:
            intervals.append({
                'label': f"{label_prefix}_{idx}",
                'interval_type': 'hold',
                'start': current_time.isoformat(),
                'end': next_time.isoformat(),
                'duration_seconds': duration
            })
            idx += 1
        
        current_time = next_time
    
    return intervals


def extract_per_file_intervals(
    data_dir: str,
    pattern: str = '*C02_?.mpt',
    exclude: str = 'fit',
    hold_interval: Optional[float] = None,
    verbose: bool = True
) -> List[Dict]:
    """
    Extract one interval per EIS file (coarse resolution).
    
    Each interval spans from acquisition start to end of last measurement.
    
    Args:
        data_dir: Directory containing .mpt files
        pattern: Glob pattern to match files
        exclude: Exclude files containing this string
        hold_interval: If specified, generate hold intervals (in seconds) for gaps
        verbose: Print progress messages
        
    Returns:
        List of interval dictionaries
    """
    data_dir = Path(data_dir)
    all_files = glob.glob(str(data_dir / pattern))
    
    # Sort numerically by extracting number from C02_N pattern
    def extract_number(filepath: str) -> int:
        match = re.search(r'_(\d+)\.mpt$', filepath)
        return int(match.group(1)) if match else 0
    
    files = sorted([f for f in all_files if exclude not in Path(f).name], key=extract_number)
    
    if not files:
        raise ValueError(f"No files found matching pattern {pattern} in {data_dir}")
    
    intervals = []
    prev_end_time = None
    acquisition_start = None
    hold_count = 0
    
    for file_idx, filepath in enumerate(files):
        filename = Path(filepath).name
        if verbose:
            print(f"Processing: {filename}")
        
        try:
            # Get header info for acquisition start time (needed for hold intervals)
            header_info = parse_mpt_header(filepath)
            if acquisition_start is None and header_info['acquisition_start'] is not None:
                acquisition_start = header_info['acquisition_start']
            
            measurements = read_frequency_measurements(filepath)
            if not measurements:
                if verbose:
                    print("  Warning: No measurements found, skipping")
                continue
            
            # Check if this is a multi-step file
            potential_steps = header_info.get('potential_steps')
            if has_multiple_steps(measurements) and potential_steps:
                # Handle multi-step file: create one interval per potential step
                if verbose:
                    print(f"  Multi-step file detected: {len(potential_steps)} steps")
                
                by_step = split_measurements_by_step(measurements)
                
                for step_num in sorted(by_step.keys()):
                    step_measurements = by_step[step_num]
                    step_info = potential_steps.get(step_num, {})
                    
                    step_start = step_measurements[0]['wall_clock']
                    step_end = step_measurements[-1]['wall_clock']
                    step_duration = (step_end - step_start).total_seconds()
                    
                    # Calculate average Ewe for this step
                    step_ewe_values = [m['ewe_v'] for m in step_measurements if m['ewe_v'] is not None]
                    step_avg_ewe = sum(step_ewe_values) / len(step_ewe_values) if step_ewe_values else None
                    
                    # Generate hold intervals between steps if requested
                    if hold_interval is not None and prev_end_time is not None:
                        gap_duration = (step_start - prev_end_time).total_seconds()
                        if gap_duration > 1.0:
                            if verbose:
                                print(f"    Inter-step hold: {gap_duration:.1f}s")
                            hold_intervals = generate_hold_intervals(
                                prev_end_time, step_start, hold_interval,
                                label_prefix=f"hold_step{step_num}"
                            )
                            for hi in hold_intervals:
                                hi['hold_index'] = hold_count
                                hold_count += 1
                            intervals.extend(hold_intervals)
                    
                    # Create label for this step
                    label = extract_label_for_step(filename, step_num, step_info)
                    
                    if verbose:
                        e_v = step_info.get('E_V')
                        vs = step_info.get('vs', '')
                        e_str = f"{e_v:.3f}V vs {vs}" if e_v is not None else "unknown"
                        print(f"    Step {step_num}: {e_str}, {len(step_measurements)} freq, {step_duration:.1f}s")
                    
                    interval_data = {
                        'label': label,
                        'filename': filename,
                        'interval_type': 'eis',
                        'start': step_start.isoformat(),
                        'end': step_end.isoformat(),
                        'duration_seconds': step_duration,
                        'n_frequencies': len(step_measurements),
                        'first_time_s': step_measurements[0]['time_seconds'],
                        'last_time_s': step_measurements[-1]['time_seconds'],
                        'step_number': step_num,
                    }
                    
                    # Add potential info
                    if step_info.get('E_V') is not None:
                        interval_data['potential_V'] = step_info['E_V']
                    if step_info.get('vs'):
                        interval_data['potential_vs'] = step_info['vs']
                    if step_avg_ewe is not None:
                        interval_data['avg_ewe_v'] = step_avg_ewe
                    
                    intervals.append(interval_data)
                    prev_end_time = step_end
                
                continue  # Done with this multi-step file
            
            # Single-step file: use original logic
            # Use first and last measurement times as the actual file interval
            # (header acquisition_start is global experiment start, same for all files)
            start_time = measurements[0]['wall_clock']
            end_time = measurements[-1]['wall_clock']
            duration = (end_time - start_time).total_seconds()
            
            # Generate hold intervals if requested
            if hold_interval is not None:
                # For the first file, generate hold intervals from acquisition start
                if file_idx == 0 and acquisition_start is not None:
                    gap_duration = (start_time - acquisition_start).total_seconds()
                    if gap_duration > 1.0:  # Only if there's a meaningful gap
                        if verbose:
                            print(f"  Initial hold period: {gap_duration:.1f}s")
                        hold_intervals = generate_hold_intervals(
                            acquisition_start, start_time, hold_interval,
                            label_prefix=f"hold_initial"
                        )
                        for hi in hold_intervals:
                            hi['hold_index'] = hold_count
                            hold_count += 1
                        intervals.extend(hold_intervals)
                
                # Generate hold intervals for gap between previous file and this one
                elif prev_end_time is not None:
                    gap_duration = (start_time - prev_end_time).total_seconds()
                    if gap_duration > 1.0:  # Only if there's a meaningful gap
                        if verbose:
                            print(f"  Inter-file hold period: {gap_duration:.1f}s")
                        hold_intervals = generate_hold_intervals(
                            prev_end_time, start_time, hold_interval,
                            label_prefix=f"hold_gap_{file_idx}"
                        )
                        for hi in hold_intervals:
                            hi['hold_index'] = hold_count
                            hold_count += 1
                        intervals.extend(hold_intervals)
            
            # Calculate average Ewe from all measurements
            ewe_values = [m['ewe_v'] for m in measurements if m['ewe_v'] is not None]
            avg_ewe = sum(ewe_values) / len(ewe_values) if ewe_values else None
            
            if verbose:
                print(f"  Start: {start_time.isoformat()}")
                print(f"  End: {end_time.isoformat()}")
                print(f"  Duration: {duration:.2f}s, {len(measurements)} frequencies")
                if avg_ewe is not None:
                    print(f"  Avg <Ewe>: {avg_ewe:.4f} V")
            
            # Extract a short label for this interval
            label = extract_label_from_filename(filename, pattern)
            
            interval_data = {
                'label': label,
                'filename': filename,
                'interval_type': 'eis',
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'duration_seconds': duration,
                'n_frequencies': len(measurements),
                'first_time_s': measurements[0]['time_seconds'],
                'last_time_s': measurements[-1]['time_seconds'],
            }
            if avg_ewe is not None:
                interval_data['avg_ewe_v'] = avg_ewe
            
            intervals.append(interval_data)
            prev_end_time = end_time
            
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
    
    # Sort numerically by extracting number from C02_N pattern
    def extract_number(filepath: str) -> int:
        match = re.search(r'_(\d+)\.mpt$', filepath)
        return int(match.group(1)) if match else 0
    
    files = sorted([f for f in all_files if exclude not in Path(f).name], key=extract_number)
    
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
    default='*C02_[0-9]*.mpt',
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
    '--hold-interval',
    type=float,
    default=None,
    help='Split hold periods (gaps before/between EIS) into intervals of this duration (seconds). '
         'E.g., --hold-interval 30 creates 30-second slices during hold periods.'
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
         hold_interval: Optional[float], output: Optional[str], quiet: bool) -> int:
    """Extract EIS timing intervals and output as JSON.

    Resolution modes:

    \b
      per-file       One interval per EIS file (default, good for reduction)
                     Auto-detects multi-step files and creates one interval per
                     potential step.
      per-frequency  One interval per frequency measurement (detailed analysis)

    Multi-step PEIS files:

    \b
      When a single .mpt file contains multiple potential steps (detected via
      the Ns column and header step definitions), per-file mode automatically
      splits the file into separate intervals for each step. Each interval
      includes step_number, potential_V, and potential_vs fields.

    Examples:

    \b
      # Extract per-file intervals (default)
      eis-interval-extractor --data-dir /path/to/eis/data --output intervals.json

    \b
      # Extract intervals from multi-step PEIS file
      eis-interval-extractor --data-dir /path/to/aqueous/data --pattern '*PEIS*.mpt' -o intervals.json

    \b
      # Extract per-file intervals with 30-second hold period slices
      eis-interval-extractor --data-dir /path/to/eis/data --hold-interval 30 -o intervals.json

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
        if hold_interval is not None:
            print(f"Hold interval: {hold_interval}s")
        print()
    
    # Extract intervals based on resolution
    if resolution == 'per-file':
        intervals = extract_per_file_intervals(
            data_dir, pattern, exclude, hold_interval=hold_interval, verbose=not quiet
        )
    else:
        if hold_interval is not None and not quiet:
            print("Note: --hold-interval is only supported with per-file resolution")
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
    
    # Add hold_interval info if specified
    if hold_interval is not None:
        result['hold_interval_seconds'] = hold_interval
        # Count hold vs EIS intervals
        n_hold = sum(1 for i in intervals if i.get('interval_type') == 'hold')
        n_eis = sum(1 for i in intervals if i.get('interval_type') == 'eis')
        result['n_hold_intervals'] = n_hold
        result['n_eis_intervals'] = n_eis
    
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
