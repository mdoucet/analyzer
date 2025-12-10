#!/usr/bin/env python3
"""
Tests for the Mantid Event Splitter module.
"""

import os
import pytest
import tempfile
from datetime import datetime


class TestLoadTimingData:
    """Tests for load_timing_data function."""
    
    def test_load_timing_data_returns_list(self, sample_timing_csv):
        """Test that load_timing_data returns a list of dictionaries."""
        from analyzer_tools.mantid_event_splitter import load_timing_data
        
        data = load_timing_data(sample_timing_csv)
        assert isinstance(data, list)
        assert len(data) > 0
        assert isinstance(data[0], dict)
    
    def test_load_timing_data_has_wall_clock_time(self, sample_timing_csv):
        """Test that loaded data has wall_clock_time field."""
        from analyzer_tools.mantid_event_splitter import load_timing_data
        
        data = load_timing_data(sample_timing_csv)
        assert 'wall_clock_time' in data[0]


class TestParseIsoDatetime:
    """Tests for parse_iso_datetime function."""
    
    def test_parse_iso_datetime_with_microseconds(self):
        """Test parsing ISO datetime with microseconds."""
        from analyzer_tools.mantid_event_splitter import parse_iso_datetime
        
        dt = parse_iso_datetime('2025-04-20T10:55:16.521000')
        assert dt.year == 2025
        assert dt.month == 4
        assert dt.day == 20
        assert dt.hour == 10
        assert dt.minute == 55
    
    def test_parse_iso_datetime_without_microseconds(self):
        """Test parsing ISO datetime without microseconds."""
        from analyzer_tools.mantid_event_splitter import parse_iso_datetime
        
        dt = parse_iso_datetime('2025-04-20T10:55:16')
        assert dt.year == 2025
        assert dt.hour == 10
    
    def test_parse_iso_datetime_invalid_format(self):
        """Test that invalid format raises ValueError."""
        from analyzer_tools.mantid_event_splitter import parse_iso_datetime
        
        with pytest.raises(ValueError):
            parse_iso_datetime('invalid-date-format')


class TestGetTimingIntervals:
    """Tests for get_timing_intervals function."""
    
    def test_get_timing_intervals_returns_list(self, sample_timing_csv):
        """Test that get_timing_intervals returns a list."""
        from analyzer_tools.mantid_event_splitter import load_timing_data, get_timing_intervals
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        assert isinstance(intervals, list)
    
    def test_get_timing_intervals_correct_count(self, sample_timing_csv):
        """Test that interval count is one less than data points."""
        from analyzer_tools.mantid_event_splitter import load_timing_data, get_timing_intervals
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        if len(data) >= 2:
            assert len(intervals) == len(data) - 1
    
    def test_get_timing_intervals_tuple_format(self, sample_timing_csv):
        """Test that intervals are tuples with (start, end, index)."""
        from analyzer_tools.mantid_event_splitter import load_timing_data, get_timing_intervals
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        if intervals:
            assert len(intervals[0]) == 3
            start, end, idx = intervals[0]
            assert isinstance(start, str)
            assert isinstance(end, str)
            assert isinstance(idx, int)


class TestGenerateMantidScript:
    """Tests for generate_mantid_script function."""
    
    def test_generate_mantid_script_returns_string(self, sample_timing_csv):
        """Test that generate_mantid_script returns a string."""
        from analyzer_tools.mantid_event_splitter import (
            load_timing_data, get_timing_intervals, generate_mantid_script
        )
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        script = generate_mantid_script(
            intervals,
            '/path/to/events.h5',
            './output',
            'test_prefix'
        )
        
        assert isinstance(script, str)
        assert len(script) > 0
    
    def test_generate_mantid_script_contains_imports(self, sample_timing_csv):
        """Test that generated script contains necessary imports."""
        from analyzer_tools.mantid_event_splitter import (
            load_timing_data, get_timing_intervals, generate_mantid_script
        )
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        script = generate_mantid_script(
            intervals,
            '/path/to/events.h5',
            './output',
            'test_prefix'
        )
        
        assert 'from mantid.simpleapi import' in script
        assert 'FilterEvents' in script
        assert 'Load' in script
    
    def test_generate_mantid_script_contains_event_file(self, sample_timing_csv):
        """Test that generated script contains the event file path."""
        from analyzer_tools.mantid_event_splitter import (
            load_timing_data, get_timing_intervals, generate_mantid_script
        )
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        event_file = '/my/custom/events.h5'
        script = generate_mantid_script(
            intervals,
            event_file,
            './output',
            'test_prefix'
        )
        
        assert event_file in script
    
    def test_generate_mantid_script_contains_timing_data(self, sample_timing_csv):
        """Test that generated script contains timing intervals."""
        from analyzer_tools.mantid_event_splitter import (
            load_timing_data, get_timing_intervals, generate_mantid_script
        )
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        script = generate_mantid_script(
            intervals,
            '/path/to/events.h5',
            './output',
            'test_prefix'
        )
        
        # Check that at least one timing value is in the script
        assert '2025-04-20T' in script
    
    def test_generate_mantid_script_is_valid_python(self, sample_timing_csv):
        """Test that generated script is syntactically valid Python."""
        from analyzer_tools.mantid_event_splitter import (
            load_timing_data, get_timing_intervals, generate_mantid_script
        )
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        script = generate_mantid_script(
            intervals,
            '/path/to/events.h5',
            './output',
            'test_prefix'
        )
        
        # This should not raise a SyntaxError
        compile(script, '<string>', 'exec')


class TestGenerateRelativeTimeScript:
    """Tests for generate_relative_time_script function."""
    
    def test_generate_relative_time_script_returns_string(self, sample_timing_csv):
        """Test that generate_relative_time_script returns a string."""
        from analyzer_tools.mantid_event_splitter import (
            load_timing_data, get_timing_intervals, generate_relative_time_script
        )
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        script = generate_relative_time_script(
            intervals,
            '/path/to/events.h5',
            './output',
            '2025-04-20T10:55:16.521000',
            'test_prefix'
        )
        
        assert isinstance(script, str)
        assert 'RelativeTime=True' in script
    
    def test_generate_relative_time_script_is_valid_python(self, sample_timing_csv):
        """Test that generated relative time script is valid Python."""
        from analyzer_tools.mantid_event_splitter import (
            load_timing_data, get_timing_intervals, generate_relative_time_script
        )
        
        data = load_timing_data(sample_timing_csv)
        intervals = get_timing_intervals(data)
        
        script = generate_relative_time_script(
            intervals,
            '/path/to/events.h5',
            './output',
            '2025-04-20T10:55:16.521000',
            'test_prefix'
        )
        
        # This should not raise a SyntaxError
        compile(script, '<string>', 'exec')


@pytest.fixture
def sample_timing_csv():
    """Create a sample timing CSV file for testing."""
    content = """freq_hz,re_z,neg_im_z,abs_z,time_s,cumulative_time_s,wall_clock_time
1000186.0,5.185,5.116,7.284,507.96,507.96,2025-04-20T10:55:16.521000
681292.69,4.552,3.444,5.708,508.38,508.38,2025-04-20T10:55:17.521000
464157.16,4.324,2.611,5.051,508.80,508.80,2025-04-20T10:55:18.521000
316229.97,3.842,1.851,4.264,509.22,509.22,2025-04-20T10:55:19.521000
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(content)
        filepath = f.name
    
    yield filepath
    
    # Cleanup
    if os.path.exists(filepath):
        os.unlink(filepath)
