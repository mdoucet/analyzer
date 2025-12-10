#!/usr/bin/env python3
"""
Tests for the EIS Measurement Splitter module.
"""

import os
import pytest
import tempfile
from pathlib import Path


class TestEISMeasurementSplitter:
    """Tests for EIS measurement-based event splitter."""
    
    def test_imports(self):
        """Test that the module can be imported."""
        from analyzer_tools import eis_measurement_splitter
        assert eis_measurement_splitter is not None
    
    def test_parse_mpt_header(self):
        """Test parsing MPT header."""
        from analyzer_tools.eis_measurement_splitter import parse_mpt_header
        
        # This would need a fixture file to test properly
        # For now, just ensure the function exists
        assert callable(parse_mpt_header)
    
    def test_generate_mantid_script(self):
        """Test script generation."""
        from analyzer_tools.eis_measurement_splitter import generate_mantid_script
        from datetime import datetime
        
        intervals = [
            ('test1.mpt', datetime(2025, 4, 20, 10, 0, 0), datetime(2025, 4, 20, 10, 5, 0)),
            ('test2.mpt', datetime(2025, 4, 20, 10, 10, 0), datetime(2025, 4, 20, 10, 15, 0)),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            output_script = f.name
        
        try:
            generate_mantid_script(
                intervals,
                '/path/to/event.nxs',
                output_script,
                './output',
                'test_ws'
            )
            
            # Check that script was created
            assert os.path.exists(output_script)
            
            # Check script contains expected content
            with open(output_script, 'r') as f:
                content = f.read()
                assert 'FilterEvents' in content
                assert 'test1.mpt' in content
                assert 'test2.mpt' in content
                
        finally:
            if os.path.exists(output_script):
                os.unlink(output_script)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
