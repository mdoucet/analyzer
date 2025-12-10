#!/usr/bin/env python3
"""
Tests for the EIS Timing Extractor module.
"""

import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path


class TestParseHeader:
    """Tests for parse_mpt_header function."""
    
    def test_parse_header_extracts_num_header_lines(self, sample_mpt_file):
        """Test that header line count is extracted correctly."""
        from analyzer_tools.eis_timing_extractor import parse_mpt_header
        
        header_info = parse_mpt_header(sample_mpt_file)
        assert header_info['num_header_lines'] == 5
    
    def test_parse_header_extracts_acquisition_time(self, sample_mpt_file):
        """Test that acquisition start time is extracted correctly."""
        from analyzer_tools.eis_timing_extractor import parse_mpt_header
        
        header_info = parse_mpt_header(sample_mpt_file)
        assert header_info['acquisition_start'] is not None
        assert header_info['acquisition_start'].year == 2025
        assert header_info['acquisition_start'].month == 4
        assert header_info['acquisition_start'].day == 20
    
    def test_parse_header_extracts_column_names(self, sample_mpt_file):
        """Test that column names are extracted from the header."""
        from analyzer_tools.eis_timing_extractor import parse_mpt_header
        
        header_info = parse_mpt_header(sample_mpt_file)
        assert 'freq/Hz' in header_info['column_names']
        assert 'time/s' in header_info['column_names']


class TestReadEisData:
    """Tests for read_eis_data function."""
    
    def test_read_eis_data_returns_list(self, sample_mpt_file):
        """Test that read_eis_data returns a list of dictionaries."""
        from analyzer_tools.eis_timing_extractor import read_eis_data
        
        data = read_eis_data(sample_mpt_file)
        assert isinstance(data, list)
        assert len(data) > 0
        assert isinstance(data[0], dict)
    
    def test_read_eis_data_has_required_fields(self, sample_mpt_file):
        """Test that returned data has all required fields."""
        from analyzer_tools.eis_timing_extractor import read_eis_data
        
        data = read_eis_data(sample_mpt_file)
        required_fields = ['freq_hz', 're_z', 'neg_im_z', 'abs_z', 
                          'time_s', 'cumulative_time_s', 'wall_clock_time']
        
        for field in required_fields:
            assert field in data[0], f"Missing field: {field}"
    
    def test_read_eis_data_wall_clock_time_format(self, sample_mpt_file):
        """Test that wall clock time is in ISO 8601 format."""
        from analyzer_tools.eis_timing_extractor import read_eis_data
        
        data = read_eis_data(sample_mpt_file)
        wall_clock = data[0]['wall_clock_time']
        
        # Should be parseable as ISO format
        dt = datetime.fromisoformat(wall_clock)
        assert isinstance(dt, datetime)
    
    def test_read_eis_data_cumulative_time_increases(self, sample_mpt_file):
        """Test that cumulative time generally increases."""
        from analyzer_tools.eis_timing_extractor import read_eis_data
        
        data = read_eis_data(sample_mpt_file)
        if len(data) > 1:
            # Last time should be >= first time
            assert data[-1]['cumulative_time_s'] >= data[0]['cumulative_time_s']


class TestGetTimingBoundaries:
    """Tests for get_timing_boundaries function."""
    
    def test_get_timing_boundaries_returns_list(self, sample_mpt_file):
        """Test that get_timing_boundaries returns a list of tuples."""
        from analyzer_tools.eis_timing_extractor import read_eis_data, get_timing_boundaries
        
        data = read_eis_data(sample_mpt_file)
        boundaries = get_timing_boundaries(data)
        
        assert isinstance(boundaries, list)
        if len(data) >= 2:
            assert len(boundaries) == len(data) - 1
            assert isinstance(boundaries[0], tuple)
            assert len(boundaries[0]) == 2
    
    def test_get_timing_boundaries_empty_for_single_point(self):
        """Test that single data point returns empty boundaries."""
        from analyzer_tools.eis_timing_extractor import get_timing_boundaries
        
        data = [{'wall_clock_time': '2025-04-20T10:55:16.521'}]
        boundaries = get_timing_boundaries(data)
        
        assert boundaries == []


class TestSaveToCsv:
    """Tests for save_to_csv function."""
    
    def test_save_to_csv_creates_file(self, sample_mpt_file):
        """Test that save_to_csv creates a CSV file."""
        from analyzer_tools.eis_timing_extractor import read_eis_data, save_to_csv
        
        data = read_eis_data(sample_mpt_file)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        try:
            save_to_csv(data, output_path)
            assert os.path.exists(output_path)
            
            # Verify content
            with open(output_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) > 1  # Header + at least one data row
                assert 'freq_hz' in lines[0]
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


@pytest.fixture
def sample_mpt_file():
    """Create a sample .mpt file for testing."""
    content = """EC-Lab ASCII FILE
Nb header lines : 5
Acquisition started on : 04/20/2025 10:55:16.521
Some other header line
freq/Hz\tRe(Z)/Ohm\t-Im(Z)/Ohm\t|Z|/Ohm\tPhase(Z)/deg\ttime/s
1.0000186E+006\t5.1854591E+000\t-5.1158142E+000\t7.2842665E+000\t4.4612640E+001\t5.079621700546559E+002
6.8129269E+005\t4.5516105E+000\t-3.4436920E+000\t5.7075539E+000\t3.7110699E+001\t5.083791507944552E+002
4.6415716E+005\t4.3242121E+000\t-2.6111193E+000\t5.0514112E+000\t3.1125132E+001\t5.087971363343167E+002
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mpt', delete=False, 
                                      encoding='latin-1') as f:
        f.write(content)
        filepath = f.name
    
    yield filepath
    
    # Cleanup
    if os.path.exists(filepath):
        os.unlink(filepath)
