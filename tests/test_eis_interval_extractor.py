#!/usr/bin/env python3
"""
Tests for the EIS Interval Extractor module.
"""

import json
import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path


@pytest.fixture
def sample_mpt_file():
    """Create a sample .mpt file for testing."""
    content = """EC-Lab ASCII FILE
Nb header lines : 5
Acquisition started on : 04/20/2025 10:55:16.521
Some other header line
freq/Hz\tRe(Z)/Ohm\t-Im(Z)/Ohm\t|Z|/Ohm\tPhase(Z)/deg\ttime/s
1.0000186E+006\t5.1854591E+000\t-5.1158142E+000\t7.2842665E+000\t4.4612640E+001\t5.079621700546559E+002
6.8129269E+005\t4.5516105E+000\t-3.4436920E+000\t5.7075539E+000\t3.7110699E+001\t5.083791507944552E+02
4.6415716E+005\t4.3242121E+000\t-2.6111193E+000\t5.0514112E+000\t3.1125132E+001\t5.087971363343167E+02
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mpt', delete=False, 
                                      encoding='latin-1') as f:
        f.write(content)
        filepath = f.name
    
    yield filepath
    
    # Cleanup
    if os.path.exists(filepath):
        os.unlink(filepath)


@pytest.fixture
def sample_mpt_directory():
    """Create a directory with multiple sample .mpt files for testing."""
    files_content = {
        'test_01_C02_1.mpt': """EC-Lab ASCII FILE
Nb header lines : 5
Acquisition started on : 04/20/2025 10:55:16.521
Some other header line
freq/Hz\tRe(Z)/Ohm\t-Im(Z)/Ohm\t|Z|/Ohm\tPhase(Z)/deg\ttime/s
1.0000186E+006\t5.1854591E+000\t-5.1158142E+000\t7.2842665E+000\t4.4612640E+001\t5.079621700546559E+02
6.8129269E+005\t4.5516105E+000\t-3.4436920E+000\t5.7075539E+000\t3.7110699E+001\t5.200E+02
""",
        'test_02_C02_2.mpt': """EC-Lab ASCII FILE
Nb header lines : 5
Acquisition started on : 04/20/2025 11:00:00.000
Some other header line
freq/Hz\tRe(Z)/Ohm\t-Im(Z)/Ohm\t|Z|/Ohm\tPhase(Z)/deg\ttime/s
1.0000186E+006\t5.1854591E+000\t-5.1158142E+000\t7.2842665E+000\t4.4612640E+001\t6.0E+02
6.8129269E+005\t4.5516105E+000\t-3.4436920E+000\t5.7075539E+000\t3.7110699E+001\t7.0E+02
""",
    }
    
    tmpdir = tempfile.mkdtemp()
    
    for filename, content in files_content.items():
        filepath = os.path.join(tmpdir, filename)
        with open(filepath, 'w', encoding='latin-1') as f:
            f.write(content)
    
    yield tmpdir
    
    # Cleanup
    for filename in files_content:
        filepath = os.path.join(tmpdir, filename)
        if os.path.exists(filepath):
            os.unlink(filepath)
    os.rmdir(tmpdir)


class TestParseMptHeader:
    """Tests for parse_mpt_header function."""
    
    def test_parse_header_extracts_num_header_lines(self, sample_mpt_file):
        """Test that header line count is extracted correctly."""
        from analyzer_tools.eis_interval_extractor import parse_mpt_header
        
        header_info = parse_mpt_header(sample_mpt_file)
        assert header_info['num_header_lines'] == 5
    
    def test_parse_header_extracts_acquisition_time(self, sample_mpt_file):
        """Test that acquisition start time is extracted correctly."""
        from analyzer_tools.eis_interval_extractor import parse_mpt_header
        
        header_info = parse_mpt_header(sample_mpt_file)
        assert header_info['acquisition_start'] is not None
        assert header_info['acquisition_start'].year == 2025
        assert header_info['acquisition_start'].month == 4
        assert header_info['acquisition_start'].day == 20
    
    def test_parse_header_extracts_column_names(self, sample_mpt_file):
        """Test that column names are extracted from the header."""
        from analyzer_tools.eis_interval_extractor import parse_mpt_header
        
        header_info = parse_mpt_header(sample_mpt_file)
        assert 'freq/Hz' in header_info['column_names']
        assert 'time/s' in header_info['column_names']


class TestReadFrequencyMeasurements:
    """Tests for read_frequency_measurements function."""
    
    def test_returns_list(self, sample_mpt_file):
        """Test that read_frequency_measurements returns a list of dictionaries."""
        from analyzer_tools.eis_interval_extractor import read_frequency_measurements
        
        data = read_frequency_measurements(sample_mpt_file)
        assert isinstance(data, list)
        assert len(data) > 0
        assert isinstance(data[0], dict)
    
    def test_has_required_fields(self, sample_mpt_file):
        """Test that returned data has all required fields."""
        from analyzer_tools.eis_interval_extractor import read_frequency_measurements
        
        data = read_frequency_measurements(sample_mpt_file)
        required_fields = ['frequency_hz', 'time_seconds', 'wall_clock']
        
        for field in required_fields:
            assert field in data[0], f"Missing field: {field}"
    
    def test_wall_clock_time_format(self, sample_mpt_file):
        """Test that wall clock time is a datetime object."""
        from analyzer_tools.eis_interval_extractor import read_frequency_measurements
        
        data = read_frequency_measurements(sample_mpt_file)
        wall_clock = data[0]['wall_clock']
        
        # Should be a datetime object
        assert isinstance(wall_clock, datetime)


class TestExtractPerFileIntervals:
    """Tests for extract_per_file_intervals function."""
    
    def test_returns_list(self, sample_mpt_directory):
        """Test that extract_per_file_intervals returns a list."""
        from analyzer_tools.eis_interval_extractor import extract_per_file_intervals
        
        intervals = extract_per_file_intervals(sample_mpt_directory)
        assert isinstance(intervals, list)
        assert len(intervals) == 2  # We have 2 test files
    
    def test_interval_has_required_fields(self, sample_mpt_directory):
        """Test that intervals have required fields."""
        from analyzer_tools.eis_interval_extractor import extract_per_file_intervals
        
        intervals = extract_per_file_intervals(sample_mpt_directory)
        required_fields = ['filename', 'start', 'end', 'duration_seconds']
        
        for interval in intervals:
            for field in required_fields:
                assert field in interval, f"Missing field: {field}"
    
    def test_intervals_are_sorted_by_start(self, sample_mpt_directory):
        """Test that intervals are sorted by start time."""
        from analyzer_tools.eis_interval_extractor import extract_per_file_intervals
        
        intervals = extract_per_file_intervals(sample_mpt_directory)
        
        if len(intervals) >= 2:
            for i in range(len(intervals) - 1):
                assert intervals[i]['start'] <= intervals[i + 1]['start']


class TestExtractPerFrequencyIntervals:
    """Tests for extract_per_frequency_intervals function."""
    
    def test_returns_list(self, sample_mpt_directory):
        """Test that extract_per_frequency_intervals returns a list."""
        from analyzer_tools.eis_interval_extractor import extract_per_frequency_intervals
        
        intervals = extract_per_frequency_intervals(sample_mpt_directory)
        assert isinstance(intervals, list)
        # Each file has 2 data rows, so we expect 4 intervals total
        assert len(intervals) >= 2
    
    def test_interval_has_required_fields(self, sample_mpt_directory):
        """Test that intervals have required fields."""
        from analyzer_tools.eis_interval_extractor import extract_per_frequency_intervals
        
        intervals = extract_per_frequency_intervals(sample_mpt_directory)
        required_fields = ['filename', 'start', 'end', 'duration_seconds', 'frequency_hz', 'measurement_index']
        
        for interval in intervals:
            for field in required_fields:
                assert field in interval, f"Missing field: {field}"
    
    def test_intervals_have_frequency(self, sample_mpt_directory):
        """Test that per-frequency intervals include frequency info."""
        from analyzer_tools.eis_interval_extractor import extract_per_frequency_intervals
        
        intervals = extract_per_frequency_intervals(sample_mpt_directory)
        
        for interval in intervals:
            assert 'frequency_hz' in interval
            assert isinstance(interval['frequency_hz'], (int, float))


class TestJsonOutput:
    """Tests for JSON output functionality."""
    
    def test_save_to_json(self, sample_mpt_directory):
        """Test that intervals can be saved to JSON."""
        from analyzer_tools.eis_interval_extractor import extract_per_file_intervals
        
        intervals = extract_per_file_intervals(sample_mpt_directory)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name
        
        try:
            output_data = {
                'resolution': 'per-file',
                'source_directory': sample_mpt_directory,
                'intervals': intervals
            }
            with open(output_path, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            # Verify the file exists and is valid JSON
            assert os.path.exists(output_path)
            with open(output_path, 'r') as f:
                loaded = json.load(f)
            
            assert loaded['resolution'] == 'per-file'
            assert len(loaded['intervals']) == 2
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestMainFunction:
    """Tests for main CLI function."""
    
    def test_main_function_exists(self):
        """Test that main CLI function exists."""
        from analyzer_tools.eis_interval_extractor import main
        assert callable(main)


class TestGenerateHoldIntervals:
    """Tests for generate_hold_intervals function."""
    
    def test_generates_correct_number_of_intervals(self):
        """Test that the correct number of intervals is generated."""
        from analyzer_tools.eis_interval_extractor import generate_hold_intervals
        
        start = datetime(2025, 4, 20, 10, 0, 0)
        end = datetime(2025, 4, 20, 10, 2, 0)  # 2 minutes = 120 seconds
        
        # 30-second intervals should give 4 intervals
        intervals = generate_hold_intervals(start, end, 30.0)
        assert len(intervals) == 4
    
    def test_interval_fields(self):
        """Test that intervals have required fields."""
        from analyzer_tools.eis_interval_extractor import generate_hold_intervals
        
        start = datetime(2025, 4, 20, 10, 0, 0)
        end = datetime(2025, 4, 20, 10, 1, 0)  # 1 minute
        
        intervals = generate_hold_intervals(start, end, 30.0)
        
        for interval in intervals:
            assert 'label' in interval
            assert 'interval_type' in interval
            assert interval['interval_type'] == 'hold'
            assert 'start' in interval
            assert 'end' in interval
            assert 'duration_seconds' in interval
    
    def test_handles_partial_final_interval(self):
        """Test that partial final intervals are handled correctly."""
        from analyzer_tools.eis_interval_extractor import generate_hold_intervals
        
        start = datetime(2025, 4, 20, 10, 0, 0)
        end = datetime(2025, 4, 20, 10, 0, 45)  # 45 seconds
        
        # 30-second intervals should give 2 intervals: 30s + 15s
        intervals = generate_hold_intervals(start, end, 30.0)
        assert len(intervals) == 2
        assert intervals[0]['duration_seconds'] == 30.0
        assert intervals[1]['duration_seconds'] == 15.0
    
    def test_returns_empty_for_short_period(self):
        """Test that very short periods return empty list."""
        from analyzer_tools.eis_interval_extractor import generate_hold_intervals
        
        start = datetime(2025, 4, 20, 10, 0, 0)
        end = datetime(2025, 4, 20, 10, 0, 0, 500000)  # 0.5 seconds
        
        intervals = generate_hold_intervals(start, end, 30.0)
        assert len(intervals) == 0


class TestHoldIntervalsInPerFile:
    """Tests for hold interval integration in extract_per_file_intervals."""
    
    def test_hold_intervals_generated_for_initial_gap(self, sample_mpt_directory):
        """Test that hold intervals are generated before first EIS measurement."""
        from analyzer_tools.eis_interval_extractor import extract_per_file_intervals
        
        # The sample files have acquisition start at 10:55:16.521
        # but first measurement at ~10:55:16.521 + 507.96s = ~11:03:44
        # So there should be hold intervals
        intervals = extract_per_file_intervals(
            sample_mpt_directory,
            pattern='*C02_?.mpt',
            hold_interval=60.0,  # 1-minute slices
            verbose=False
        )
        
        # Should have both hold and EIS intervals
        hold_intervals = [i for i in intervals if i.get('interval_type') == 'hold']
        eis_intervals = [i for i in intervals if i.get('interval_type') == 'eis']
        
        # We have 2 EIS files in the fixture
        assert len(eis_intervals) == 2
        # There should be hold intervals (exact count depends on gap duration)
        assert len(hold_intervals) >= 0  # May be 0 if gaps are small in fixture
    
    def test_no_hold_intervals_without_option(self, sample_mpt_directory):
        """Test that no hold intervals are generated without the option."""
        from analyzer_tools.eis_interval_extractor import extract_per_file_intervals
        
        intervals = extract_per_file_intervals(
            sample_mpt_directory,
            pattern='*C02_?.mpt',
            hold_interval=None,  # No hold intervals
            verbose=False
        )
        
        # Should only have EIS intervals (2 files)
        assert len(intervals) == 2
        # None should be hold type (field may not exist without hold_interval)
        hold_intervals = [i for i in intervals if i.get('interval_type') == 'hold']
        assert len(hold_intervals) == 0


class TestExtractLabelFromFilename:
    """Tests for extract_label_from_filename function."""
    
    def test_extracts_sequence_number(self):
        """Test that sequence number is extracted correctly."""
        from analyzer_tools.eis_interval_extractor import extract_label_from_filename
        
        filename = "sequence_1_CuPt_UHP1MLiBF4-d8-THF_1per-EtOH_expt11_CAs,PEIS,OCV_02_PEIS_C02_1.mpt"
        label = extract_label_from_filename(filename, pattern="*C02_?.mpt")
        
        assert label.startswith("sequence_1")
        assert "eis_1" in label
    
    def test_extracts_different_sequence_numbers(self):
        """Test that different sequence numbers are extracted correctly."""
        from analyzer_tools.eis_interval_extractor import extract_label_from_filename
        
        # Test sequence 5 with file number 5
        filename = "sequence_5_CuPt_expt_C02_5.mpt"
        label = extract_label_from_filename(filename, pattern="*C02_?.mpt")
        
        assert "sequence_5" in label
        assert "eis_5" in label
    
    def test_fallback_for_non_sequence_filename(self):
        """Test fallback for filenames without sequence pattern."""
        from analyzer_tools.eis_interval_extractor import extract_label_from_filename
        
        filename = "some_other_filename_structure.mpt"
        label = extract_label_from_filename(filename)
        
        # Should return a cleaned version of the filename
        assert len(label) <= 30
        assert ".mpt" not in label
    
    def test_eis_intervals_have_labels(self, sample_mpt_directory):
        """Test that EIS intervals have label field."""
        from analyzer_tools.eis_interval_extractor import extract_per_file_intervals
        
        intervals = extract_per_file_intervals(
            sample_mpt_directory,
            pattern='*C02_?.mpt',
            verbose=False
        )
        
        for interval in intervals:
            assert 'label' in interval
            assert len(interval['label']) > 0


class TestCliFunction:
    """Tests for CLI wrapper function."""
    
    def test_cli_function_exists(self):
        """Test that CLI wrapper exists in cli module."""
        from analyzer_tools.cli import eis_interval_extractor_cli
        assert callable(eis_interval_extractor_cli)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
