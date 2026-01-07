"""
Tests for the Iceberg Packager module.
"""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analyzer_tools.iceberg_packager import (
    create_reflectivity_records,
    extract_interval_for_file,
    find_reduction_json,
    find_reflectivity_files,
    load_reduction_metadata,
    load_reduction_template,
    load_reflectivity_file,
    load_split_file,
    package_to_parquet,
    validate_inputs,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_split_file(temp_dir):
    """Create a sample split file."""
    split_data = {
        "source_directory": "/path/to/eis/data",
        "pattern": "*C02_?.mpt",
        "resolution": "per-file",
        "n_intervals": 3,
        "intervals": [
            {
                "label": "hold_initial_0",
                "interval_type": "hold",
                "start": "2025-04-20T10:55:16.521000",
                "end": "2025-04-20T10:55:46.521000",
                "duration_seconds": 30.0,
                "hold_index": 0
            },
            {
                "label": "hold_initial_1",
                "interval_type": "hold",
                "start": "2025-04-20T10:55:46.521000",
                "end": "2025-04-20T10:56:16.521000",
                "duration_seconds": 30.0,
                "hold_index": 1
            },
            {
                "label": "sequence_1_eis_1",
                "interval_type": "eis",
                "start": "2025-04-20T10:56:16.521000",
                "end": "2025-04-20T10:57:16.521000",
                "duration_seconds": 60.0
            }
        ]
    }
    
    filepath = os.path.join(temp_dir, "splits.json")
    with open(filepath, 'w') as f:
        json.dump(split_data, f)
    
    return filepath


@pytest.fixture
def sample_reduction_json(temp_dir):
    """Create a sample reduction metadata JSON file."""
    reduction_data = {
        "run_number": 218389,
        "duration": 6546.09,
        "n_intervals": 3,
        "intervals": [
            {
                "label": "hold_initial_0",
                "interval_type": "hold",
                "start": "2025-04-20T10:55:16.521000",
                "end": "2025-04-20T10:55:46.521000"
            },
            {
                "label": "hold_initial_1",
                "interval_type": "hold",
                "start": "2025-04-20T10:55:46.521000",
                "end": "2025-04-20T10:56:16.521000"
            },
            {
                "label": "sequence_1_eis_1",
                "interval_type": "eis",
                "start": "2025-04-20T10:56:16.521000",
                "end": "2025-04-20T10:57:16.521000"
            }
        ],
        "reduced_files": [
            "/path/to/r218389_hold_initial_0.txt",
            "/path/to/r218389_hold_initial_1.txt",
            "/path/to/r218389_sequence_1_eis_1.txt"
        ]
    }
    
    reduced_dir = os.path.join(temp_dir, "reduced")
    os.makedirs(reduced_dir, exist_ok=True)
    
    filepath = os.path.join(reduced_dir, "r218389_eis_reduction.json")
    with open(filepath, 'w') as f:
        json.dump(reduction_data, f)
    
    return reduced_dir, filepath


@pytest.fixture
def sample_reflectivity_files(temp_dir):
    """Create sample reflectivity data files."""
    reduced_dir = os.path.join(temp_dir, "reduced")
    os.makedirs(reduced_dir, exist_ok=True)
    
    # Create sample 4-column data files
    files = []
    for label in ["hold_initial_0", "hold_initial_1", "sequence_1_eis_1"]:
        filename = f"r218389_{label}.txt"
        filepath = os.path.join(reduced_dir, filename)
        
        # Generate sample data with different number of points
        n_points = np.random.randint(50, 100)
        Q = np.linspace(0.01, 0.05, n_points)
        R = np.exp(-Q * 100) + np.random.normal(0, 0.01, n_points)
        dR = np.abs(R) * 0.05
        dQ = Q * 0.01
        
        data = np.column_stack([Q, R, dR, dQ])
        np.savetxt(filepath, data)
        files.append(filepath)
    
    return reduced_dir, files


@pytest.fixture
def sample_template_file(temp_dir):
    """Create a sample reduction template XML file."""
    template_content = """<Reduction>
 <instrument_name>REFL</instrument_name>
 <timestamp>Tuesday, 26. August 2025 03:40PM</timestamp>
 <version>2.2.0</version>
 <DataSeries>
  <RefLData>
   <peak_selection_type>narrow</peak_selection_type>
   <from_peak_pixels>146</from_peak_pixels>
   <to_peak_pixels>161</to_peak_pixels>
  </RefLData>
 </DataSeries>
</Reduction>"""
    
    filepath = os.path.join(temp_dir, "template.xml")
    with open(filepath, 'w') as f:
        f.write(template_content)
    
    return filepath


class TestLoadSplitFile:
    """Tests for load_split_file function."""
    
    def test_load_split_file_basic(self, sample_split_file):
        """Test loading a basic split file."""
        result = load_split_file(sample_split_file)
        
        assert result['source_directory'] == "/path/to/eis/data"
        assert result['pattern'] == "*C02_?.mpt"
        assert result['resolution'] == "per-file"
        assert result['n_intervals'] == 3
        assert len(result['intervals']) == 3
    
    def test_load_split_file_intervals(self, sample_split_file):
        """Test that intervals are loaded correctly."""
        result = load_split_file(sample_split_file)
        
        first_interval = result['intervals'][0]
        assert first_interval['label'] == "hold_initial_0"
        assert first_interval['interval_type'] == "hold"
        assert first_interval['duration_seconds'] == 30.0


class TestLoadReductionMetadata:
    """Tests for load_reduction_metadata function."""
    
    def test_load_reduction_metadata_basic(self, sample_reduction_json):
        """Test loading reduction metadata."""
        reduced_dir, filepath = sample_reduction_json
        result = load_reduction_metadata(filepath)
        
        assert result['run_number'] == 218389
        assert result['duration'] == 6546.09
        assert result['n_intervals'] == 3
        assert len(result['intervals']) == 3
        assert len(result['reduced_files']) == 3


class TestLoadReductionTemplate:
    """Tests for load_reduction_template function."""
    
    def test_load_template(self, sample_template_file):
        """Test loading a template XML file."""
        result = load_reduction_template(sample_template_file)
        
        assert "<Reduction>" in result
        assert "<instrument_name>REFL</instrument_name>" in result
        assert "</Reduction>" in result


class TestLoadReflectivityFile:
    """Tests for load_reflectivity_file function."""
    
    def test_load_reflectivity_file(self, sample_reflectivity_files):
        """Test loading a reflectivity data file."""
        reduced_dir, files = sample_reflectivity_files
        
        Q, R, dR, dQ = load_reflectivity_file(files[0])
        
        assert len(Q) > 0
        assert len(Q) == len(R) == len(dR) == len(dQ)
        assert Q.min() > 0
        assert Q.max() < 0.1


class TestFindReflectivityFiles:
    """Tests for find_reflectivity_files function."""
    
    def test_find_reflectivity_files(self, sample_reflectivity_files):
        """Test finding reflectivity files in a directory."""
        reduced_dir, expected_files = sample_reflectivity_files
        
        found_files = find_reflectivity_files(reduced_dir)
        
        assert len(found_files) == len(expected_files)
        for f in expected_files:
            assert f in found_files


class TestFindReductionJson:
    """Tests for find_reduction_json function."""
    
    def test_find_reduction_json(self, sample_reduction_json):
        """Test finding the reduction JSON file."""
        reduced_dir, expected_file = sample_reduction_json
        
        found_file = find_reduction_json(reduced_dir)
        
        assert found_file == expected_file
    
    def test_find_reduction_json_not_found(self, temp_dir):
        """Test when no reduction JSON exists."""
        result = find_reduction_json(temp_dir)
        assert result is None


class TestExtractIntervalForFile:
    """Tests for extract_interval_for_file function."""
    
    def test_extract_interval_match(self):
        """Test matching a file to its interval."""
        intervals = [
            {"label": "hold_initial_0", "interval_type": "hold"},
            {"label": "hold_initial_1", "interval_type": "hold"},
            {"label": "sequence_1_eis_1", "interval_type": "eis"}
        ]
        
        result = extract_interval_for_file("r218389_hold_initial_0.txt", intervals)
        
        assert result is not None
        assert result['label'] == "hold_initial_0"
        assert result['interval_type'] == "hold"
    
    def test_extract_interval_no_match(self):
        """Test when no matching interval exists."""
        intervals = [
            {"label": "hold_initial_0", "interval_type": "hold"}
        ]
        
        result = extract_interval_for_file("r218389_unknown_label.txt", intervals)
        
        assert result is None


class TestCreateReflectivityRecords:
    """Tests for create_reflectivity_records function."""
    
    def test_create_records(self, sample_reflectivity_files):
        """Test creating records from reflectivity files."""
        reduced_dir, files = sample_reflectivity_files
        
        intervals = [
            {"label": "hold_initial_0", "interval_type": "hold", 
             "start": "2025-04-20T10:55:16.521000", "end": "2025-04-20T10:55:46.521000",
             "duration_seconds": 30.0, "hold_index": 0},
            {"label": "hold_initial_1", "interval_type": "hold",
             "start": "2025-04-20T10:55:46.521000", "end": "2025-04-20T10:56:16.521000",
             "duration_seconds": 30.0, "hold_index": 1},
            {"label": "sequence_1_eis_1", "interval_type": "eis",
             "start": "2025-04-20T10:56:16.521000", "end": "2025-04-20T10:57:16.521000"}
        ]
        
        records = create_reflectivity_records(files, intervals, 218389)
        
        assert len(records) == len(files)
        for record in records:
            assert 'run_number' in record
            assert 'filename' in record
            assert 'Q' in record
            assert 'R' in record
            assert 'dR' in record
            assert 'dQ' in record
            assert record['run_number'] == 218389


class TestValidateInputs:
    """Tests for validate_inputs function."""
    
    def test_validate_valid_inputs(self, sample_split_file, sample_reflectivity_files, sample_template_file):
        """Test validation with valid inputs."""
        reduced_dir, _ = sample_reflectivity_files
        
        result = validate_inputs(sample_split_file, reduced_dir, sample_template_file)
        
        assert result is True
    
    def test_validate_missing_split(self, sample_reflectivity_files, sample_template_file):
        """Test validation with missing split file."""
        reduced_dir, _ = sample_reflectivity_files
        
        result = validate_inputs("/nonexistent/file.json", reduced_dir, sample_template_file)
        
        assert result is False
    
    def test_validate_missing_reduced_dir(self, sample_split_file, sample_template_file):
        """Test validation with missing reduced directory."""
        result = validate_inputs(sample_split_file, "/nonexistent/dir", sample_template_file)
        
        assert result is False


class TestPackageToParquet:
    """Tests for the full packaging workflow."""
    
    def test_package_to_parquet(self, temp_dir):
        """Test the complete packaging workflow."""
        # Create all required files
        reduced_dir = os.path.join(temp_dir, "reduced")
        os.makedirs(reduced_dir, exist_ok=True)
        
        # Create split file
        split_data = {
            "source_directory": "/path/to/eis/data",
            "pattern": "*C02_?.mpt",
            "resolution": "per-file",
            "n_intervals": 2,
            "intervals": [
                {"label": "hold_initial_0", "interval_type": "hold",
                 "start": "2025-04-20T10:55:16.521000", "end": "2025-04-20T10:55:46.521000",
                 "duration_seconds": 30.0, "hold_index": 0},
                {"label": "hold_initial_1", "interval_type": "hold",
                 "start": "2025-04-20T10:55:46.521000", "end": "2025-04-20T10:56:16.521000",
                 "duration_seconds": 30.0, "hold_index": 1}
            ]
        }
        split_file = os.path.join(temp_dir, "splits.json")
        with open(split_file, 'w') as f:
            json.dump(split_data, f)
        
        # Create reduction JSON
        reduction_data = {
            "run_number": 218389,
            "duration": 60.0,
            "n_intervals": 2,
            "intervals": split_data["intervals"],
            "reduced_files": []
        }
        reduction_json = os.path.join(reduced_dir, "r218389_eis_reduction.json")
        with open(reduction_json, 'w') as f:
            json.dump(reduction_data, f)
        
        # Create reflectivity files
        for label in ["hold_initial_0", "hold_initial_1"]:
            filepath = os.path.join(reduced_dir, f"r218389_{label}.txt")
            data = np.column_stack([
                np.linspace(0.01, 0.05, 50),  # Q
                np.random.rand(50),            # R
                np.random.rand(50) * 0.05,     # dR
                np.ones(50) * 0.0004           # dQ
            ])
            np.savetxt(filepath, data)
        
        # Create template file
        template_content = "<Reduction><instrument_name>REFL</instrument_name></Reduction>"
        template_file = os.path.join(temp_dir, "template.xml")
        with open(template_file, 'w') as f:
            f.write(template_content)
        
        # Run packaging
        output_file = os.path.join(temp_dir, "output.parquet")
        result = package_to_parquet(split_file, reduced_dir, template_file, output_file)
        
        # Verify output
        assert os.path.exists(result)
        
        # Read and verify parquet file
        df = pd.read_parquet(result)
        assert len(df) == 2  # Two reflectivity files
        assert 'Q' in df.columns
        assert 'R' in df.columns
        assert 'run_number' in df.columns
        assert df['run_number'].iloc[0] == 218389
        
        # Verify metadata file
        metadata_file = result.replace('.parquet', '_metadata.parquet')
        assert os.path.exists(metadata_file)
        
        metadata_df = pd.read_parquet(metadata_file)
        assert len(metadata_df) == 1
        assert metadata_df['run_number'].iloc[0] == 218389
        assert 'reduction_template_xml' in metadata_df.columns
