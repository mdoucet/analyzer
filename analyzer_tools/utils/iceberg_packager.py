#!/usr/bin/env python3
"""
Iceberg Packager for EIS and tNR Data

This module packages time-resolved neutron reflectometry (tNR) data combined
with electrochemical impedance spectroscopy (EIS) timing information into
Parquet files suitable for ingestion into a data lakehouse (Apache Iceberg).

The tool extracts:
- Metadata from split files (timing intervals from EIS data)
- Metadata from reduction JSON files (processed data info)
- Reflectivity data from reduced .txt files (Q, R, dR, dQ columns)
- Reduction template XML content

All data is packaged into a Parquet file with proper schema for Iceberg.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def load_split_file(split_file: str) -> Dict[str, Any]:
    """
    Load and parse a split file (JSON with EIS timing intervals).
    
    Args:
        split_file: Path to the split JSON file
        
    Returns:
        Dictionary containing split metadata
    """
    with open(split_file, 'r') as f:
        data = json.load(f)
    
    return {
        'source_directory': data.get('source_directory', ''),
        'pattern': data.get('pattern', ''),
        'resolution': data.get('resolution', ''),
        'n_intervals': data.get('n_intervals', 0),
        'intervals': data.get('intervals', [])
    }


def load_reduction_metadata(reduction_json: str) -> Dict[str, Any]:
    """
    Load reduction metadata from the *_eis_reduction.json file.
    
    Args:
        reduction_json: Path to the reduction JSON file
        
    Returns:
        Dictionary containing reduction metadata
    """
    with open(reduction_json, 'r') as f:
        data = json.load(f)
    
    return {
        'run_number': data.get('run_number'),
        'duration': data.get('duration'),
        'n_intervals': data.get('n_intervals'),
        'intervals': data.get('intervals', []),
        'reduced_files': data.get('reduced_files', [])
    }


def load_reduction_template(template_file: str) -> str:
    """
    Load the reduction template XML file content.
    
    Args:
        template_file: Path to the XML template file
        
    Returns:
        Raw XML content as string
    """
    with open(template_file, 'r') as f:
        return f.read()


def load_reflectivity_file(filepath: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Load a reflectivity data file (4-column ASCII: Q, R, dR, dQ).
    
    Args:
        filepath: Path to the reflectivity .txt file
        
    Returns:
        Tuple of (Q, R, dR, dQ) arrays
    """
    data = np.loadtxt(filepath)
    if data.ndim == 1:
        # Single row case
        data = data.reshape(1, -1)
    
    return data[:, 0], data[:, 1], data[:, 2], data[:, 3]


def find_reflectivity_files(reduced_dir: str) -> List[str]:
    """
    Find all reflectivity .txt files in the reduced directory.
    
    Args:
        reduced_dir: Path to the directory with reduced files
        
    Returns:
        List of paths to reflectivity files (sorted)
    """
    reduced_path = Path(reduced_dir)
    txt_files = sorted([str(f) for f in reduced_path.glob('*.txt')])
    return txt_files


def find_reduction_json(reduced_dir: str) -> Optional[str]:
    """
    Find the *_eis_reduction.json file in the reduced directory.
    
    Args:
        reduced_dir: Path to the directory with reduced files
        
    Returns:
        Path to the reduction JSON file, or None if not found
    """
    reduced_path = Path(reduced_dir)
    json_files = list(reduced_path.glob('*_eis_reduction.json'))
    if json_files:
        return str(json_files[0])
    return None


def extract_interval_for_file(filename: str, intervals: List[Dict]) -> Optional[Dict]:
    """
    Match a reduced file to its corresponding interval metadata.
    
    Args:
        filename: Name of the reduced file (e.g., r218389_hold_gap_1_0.txt)
        intervals: List of interval dictionaries from metadata
        
    Returns:
        Matching interval dictionary, or None if not found
    """
    # Extract the label part from filename: r218389_hold_gap_1_0.txt -> hold_gap_1_0
    base = os.path.basename(filename)
    # Remove run number prefix (r######_) and extension
    parts = base.replace('.txt', '').split('_', 1)
    if len(parts) > 1:
        label = parts[1]
    else:
        label = base.replace('.txt', '')
    
    for interval in intervals:
        if interval.get('label') == label:
            return interval
    
    return None


def create_reflectivity_records(
    reflectivity_files: List[str],
    intervals: List[Dict],
    run_number: int
) -> List[Dict[str, Any]]:
    """
    Create records for each reflectivity file with associated metadata.
    
    Args:
        reflectivity_files: List of paths to reflectivity files
        intervals: List of interval metadata dictionaries
        run_number: Run number for this dataset
        
    Returns:
        List of record dictionaries ready for DataFrame conversion
    """
    records = []
    
    for filepath in reflectivity_files:
        filename = os.path.basename(filepath)
        
        # Load reflectivity data
        try:
            Q, R, dR, dQ = load_reflectivity_file(filepath)
        except Exception as e:
            click.echo(f"Warning: Failed to load {filepath}: {e}", err=True)
            continue
        
        # Match to interval metadata
        interval = extract_interval_for_file(filename, intervals)
        
        record = {
            'run_number': run_number,
            'filename': filename,
            'filepath': filepath,
            'n_points': len(Q),
            'Q': Q.tolist(),
            'R': R.tolist(),
            'dR': dR.tolist(),
            'dQ': dQ.tolist(),
            'Q_min': float(Q.min()),
            'Q_max': float(Q.max()),
            'R_min': float(R.min()),
            'R_max': float(R.max()),
        }
        
        # Add interval metadata if found
        if interval:
            record['interval_label'] = interval.get('label', '')
            record['interval_type'] = interval.get('interval_type', '')
            record['interval_start'] = interval.get('start', '')
            record['interval_end'] = interval.get('end', '')
            record['duration_seconds'] = interval.get('duration_seconds')
            record['hold_index'] = interval.get('hold_index')
        else:
            record['interval_label'] = ''
            record['interval_type'] = ''
            record['interval_start'] = ''
            record['interval_end'] = ''
            record['duration_seconds'] = None
            record['hold_index'] = None
        
        records.append(record)
    
    return records


def package_to_parquet(
    split_file: str,
    reduced_dir: str,
    template_file: str,
    output_file: str
) -> str:
    """
    Package all tNR data into a Parquet file for Iceberg.
    
    Args:
        split_file: Path to the split JSON file
        reduced_dir: Path to the directory with reduced files
        template_file: Path to the reduction template XML file
        output_file: Path for the output Parquet file
        
    Returns:
        Path to the created Parquet file
    """
    # Load all metadata
    click.echo(f"Loading split file: {split_file}")
    split_metadata = load_split_file(split_file)
    
    # Find and load reduction metadata
    reduction_json = find_reduction_json(reduced_dir)
    if reduction_json:
        click.echo(f"Loading reduction metadata: {reduction_json}")
        reduction_metadata = load_reduction_metadata(reduction_json)
    else:
        click.echo("Warning: No *_eis_reduction.json file found", err=True)
        reduction_metadata = {'run_number': 0, 'duration': 0, 'n_intervals': 0, 'intervals': [], 'reduced_files': []}
    
    # Load reduction template
    click.echo(f"Loading reduction template: {template_file}")
    template_xml = load_reduction_template(template_file)
    
    # Find and load reflectivity files
    reflectivity_files = find_reflectivity_files(reduced_dir)
    click.echo(f"Found {len(reflectivity_files)} reflectivity files")
    
    # Merge intervals from both sources (reduction metadata takes precedence)
    intervals = reduction_metadata.get('intervals', [])
    if not intervals:
        intervals = split_metadata.get('intervals', [])
    
    # Create records for each reflectivity file
    records = create_reflectivity_records(
        reflectivity_files,
        intervals,
        reduction_metadata.get('run_number', 0)
    )
    
    click.echo(f"Created {len(records)} records")
    
    # Create DataFrame for reflectivity data
    df = pd.DataFrame(records)
    
    # Create metadata table (single row with experiment-level info)
    metadata_record = {
        'run_number': reduction_metadata.get('run_number', 0),
        'total_duration': reduction_metadata.get('duration', 0.0),
        'n_intervals': reduction_metadata.get('n_intervals', 0),
        'n_reduced_files': len(reflectivity_files),
        'source_directory': split_metadata.get('source_directory', ''),
        'eis_pattern': split_metadata.get('pattern', ''),
        'resolution': split_metadata.get('resolution', ''),
        'reduction_template_xml': template_xml,
        'packaged_timestamp': datetime.now(timezone.utc).isoformat(),
        'packager_version': '1.0.0'
    }
    
    # Convert intervals to JSON for storage
    metadata_record['intervals_json'] = json.dumps(intervals)
    metadata_record['split_metadata_json'] = json.dumps(split_metadata)
    metadata_record['reduction_metadata_json'] = json.dumps(reduction_metadata)
    
    metadata_df = pd.DataFrame([metadata_record])
    
    # Create output directory if needed
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to Parquet with separate row groups for data and metadata
    # We'll create a combined output with two types of records
    
    # Option 1: Write reflectivity data to main parquet file
    data_output = str(output_path)
    df.to_parquet(data_output, engine='pyarrow', index=False)
    click.echo(f"Wrote reflectivity data to: {data_output}")
    
    # Option 2: Write metadata to a separate file
    metadata_output = str(output_path).replace('.parquet', '_metadata.parquet')
    metadata_df.to_parquet(metadata_output, engine='pyarrow', index=False)
    click.echo(f"Wrote experiment metadata to: {metadata_output}")
    
    return data_output


def validate_inputs(split_file: str, reduced_dir: str, template_file: str) -> bool:
    """
    Validate that all required input files/directories exist.
    
    Args:
        split_file: Path to split JSON file
        reduced_dir: Path to reduced data directory
        template_file: Path to XML template file
        
    Returns:
        True if all inputs are valid
    """
    valid = True
    
    if not os.path.exists(split_file):
        click.echo(f"Error: Split file not found: {split_file}", err=True)
        valid = False
    
    if not os.path.isdir(reduced_dir):
        click.echo(f"Error: Reduced directory not found: {reduced_dir}", err=True)
        valid = False
    
    if not os.path.exists(template_file):
        click.echo(f"Error: Template file not found: {template_file}", err=True)
        valid = False
    
    return valid


@click.command()
@click.argument('split_file', type=click.Path(exists=True))
@click.argument('reduced_dir', type=click.Path(exists=True))
@click.argument('template_file', type=click.Path(exists=True))
@click.option('--output', '-o', 'output_file', type=click.Path(),
              help='Output Parquet file path. Defaults to <reduced_dir>/tnr_data.parquet')
@click.option('--validate-only', is_flag=True,
              help='Only validate inputs, do not create output')
def main(split_file: str, reduced_dir: str, template_file: str, 
         output_file: Optional[str], validate_only: bool):
    """
    Package tNR (time-resolved Neutron Reflectometry) data for Iceberg.
    
    \b
    This tool combines:
    - Split file: JSON with EIS timing intervals (from eis_interval_extractor)
    - Reduced files: Reflectivity data files (Q, R, dR, dQ)
    - Template file: XML reduction parameters
    
    \b
    Arguments:
      SPLIT_FILE     Path to the split JSON file (e.g., expt11-splits-per-file-w-hold.json)
      REDUCED_DIR    Path to directory containing reduced .txt files
      TEMPLATE_FILE  Path to the reduction template XML file
    
    \b
    Example:
      iceberg-packager data/tNR/expt11-splits.json data/tNR/reduced REF_L_sample_6_tNR.xml
      iceberg-packager splits.json ./reduced template.xml -o output/tnr_dataset.parquet
    """
    click.echo("=" * 60)
    click.echo("Iceberg Packager for EIS and tNR Data")
    click.echo("=" * 60)
    
    if not validate_inputs(split_file, reduced_dir, template_file):
        raise click.Abort()
    
    if validate_only:
        click.echo("Validation passed!")
        return
    
    # Set default output file if not specified
    if output_file is None:
        output_file = os.path.join(reduced_dir, 'tnr_data.parquet')
    
    # Package the data
    output_path = package_to_parquet(split_file, reduced_dir, template_file, output_file)
    
    click.echo("=" * 60)
    click.echo(f"Successfully packaged data to: {output_path}")
    click.echo("=" * 60)


if __name__ == '__main__':
    main()
