"""
Tests for analyzer_tools.welcome module.
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

from analyzer_tools.welcome import welcome, show_available_data, quick_start, help_me_choose


class TestWelcome:
    """Test the welcome function."""
    
    @patch('analyzer_tools.registry.print_tool_overview')
    @patch('builtins.print')
    def test_welcome_prints_message_and_overview(self, mock_print, mock_overview):
        """Test that welcome prints welcome message and calls tool overview."""
        welcome()
        
        # Should print welcome message
        mock_print.assert_called()
        welcome_calls = [call for call in mock_print.call_args_list 
                        if 'Welcome to Neutron Reflectometry Data Analysis!' in str(call)]
        assert len(welcome_calls) > 0
        
        # Should call print_tool_overview
        mock_overview.assert_called_once()


class TestShowAvailableData:
    """Test the show_available_data function."""
    
    def test_show_available_data_with_existing_directories(self):
        """Test show_available_data when data directories exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directories and files
            combined_dir = os.path.join(temp_dir, "combined")
            partial_dir = os.path.join(temp_dir, "partial")
            os.makedirs(combined_dir)
            os.makedirs(partial_dir)
            
            # Create test files
            with open(os.path.join(combined_dir, "REFL_218281_combined_data_auto.txt"), 'w') as f:
                f.write("test data")
            with open(os.path.join(partial_dir, "REFL_218281_1_218281_partial.txt"), 'w') as f:
                f.write("test data")
            
            # Mock config to use our test directories
            mock_config = MagicMock()
            mock_config.get_combined_data_dir.return_value = combined_dir
            mock_config.get_partial_data_dir.return_value = partial_dir
            mock_config.get_combined_data_template.return_value = "REFL_{set_id}_combined_data_auto.txt"
            
            with patch('analyzer_tools.config_utils.get_config', return_value=mock_config):
                with patch('builtins.print') as mock_print:
                    show_available_data()
                    
                    # Check that output contains expected information
                    print_calls = [str(call) for call in mock_print.call_args_list]
                    combined_output = " ".join(print_calls)
                    
                    assert "Combined Data (1 datasets)" in combined_output
                    assert "Partial Data (1 data sets" in combined_output
                    assert "218281" in combined_output
    
    def test_show_available_data_with_missing_directories(self):
        """Test show_available_data when data directories don't exist."""
        mock_config = MagicMock()
        mock_config.get_combined_data_dir.return_value = "/nonexistent/combined"
        mock_config.get_partial_data_dir.return_value = "/nonexistent/partial"
        
        with patch('analyzer_tools.config_utils.get_config', return_value=mock_config):
            with patch('builtins.print') as mock_print:
                show_available_data()
                
                # Check that output indicates missing directories
                print_calls = [str(call) for call in mock_print.call_args_list]
                combined_output = " ".join(print_calls)
                
                assert "Directory not found" in combined_output

    @patch('analyzer_tools.config_utils.get_config')
    @patch('builtins.print')
    def test_show_available_data_with_files(self, mock_print, mock_get_config):
        """Test showing available data when files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock config
            mock_config = MagicMock()
            mock_config.get_combined_data_dir.return_value = temp_dir
            mock_config.get_partial_data_dir.return_value = temp_dir
            mock_get_config.return_value = mock_config
            
            # Create test data files
            test_files = [
                'REFL_123_combined_data_auto.txt',
                'REFL_456_combined_data_auto.txt',
                'REFL_123_1_001_partial.txt',
                'REFL_123_2_002_partial.txt'
            ]
            
            for filename in test_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    f.write("# Test data\n")
            
            # Test the function
            show_available_data()
            
            # Check that it printed information about available data
            assert mock_print.call_count > 0
            printed_text = ' '.join([str(call.args[0]) for call in mock_print.call_args_list])
            assert 'Combined' in printed_text or 'combined' in printed_text

    @patch('analyzer_tools.config_utils.get_config')
    @patch('builtins.print') 
    def test_show_available_data_no_files(self, mock_print, mock_get_config):
        """Test showing available data when no files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock config pointing to empty directory
            mock_config = MagicMock()
            mock_config.get_combined_data_dir.return_value = temp_dir
            mock_config.get_partial_data_dir.return_value = temp_dir
            mock_get_config.return_value = mock_config
            
            # Test with no data files
            show_available_data()
            
            # Should still print something (even if no data found)
            assert mock_print.call_count > 0


class TestQuickStart:
    """Test the quick_start function."""
    
    @patch('builtins.print')
    def test_quick_start_combined(self, mock_print):
        """Test quick_start for combined data."""
        quick_start("combined")
        
        print_calls = [str(call) for call in mock_print.call_args_list]
        combined_output = " ".join(print_calls)
        
        assert "COMBINED DATA" in combined_output
        assert "run_fit.py" in combined_output
        assert "result_assessor.py" in combined_output
    
    @patch('builtins.print')
    def test_quick_start_partial(self, mock_print):
        """Test quick_start for partial data."""
        quick_start("partial")
        
        print_calls = [str(call) for call in mock_print.call_args_list]
        combined_output = " ".join(print_calls)
        
        assert "PARTIAL DATA" in combined_output
        assert "partial_data_assessor.py" in combined_output
    
    @patch('builtins.print')
    def test_quick_start_both(self, mock_print):
        """Test quick_start for both data types."""
        quick_start("both")
        
        print_calls = [str(call) for call in mock_print.call_args_list]
        combined_output = " ".join(print_calls)
        
        assert "PARTIAL DATA" in combined_output.upper()
        assert "COMBINED DATA" in combined_output.upper()
        assert "partial_data_assessor.py" in combined_output
        assert "run_fit.py" in combined_output
    
    @patch('builtins.print')
    def test_quick_start_prints_instructions(self, mock_print):
        """Test that quick_start prints instructions."""
        quick_start()
        
        # Should print instructions
        assert mock_print.call_count > 0
        printed_text = ' '.join([str(call.args[0]) for call in mock_print.call_args_list])
        assert 'quick' in printed_text.lower() or 'start' in printed_text.lower()


class TestHelpMeChoose:
    """Test the help_me_choose function."""
    
    @patch('builtins.print')
    def test_help_me_choose_prints_options(self, mock_print):
        """Test that help_me_choose prints tool selection options."""
        help_me_choose()
        
        print_calls = [str(call) for call in mock_print.call_args_list]
        combined_output = " ".join(print_calls)
        
        # Should mention all main tools
        assert "partial_data_assessor" in combined_output
        assert "run_fit" in combined_output
        assert "result_assessor" in combined_output
        assert "create_model_script" in combined_output or "create_temporary_model" in combined_output
        
        # Should provide guidance
        assert "quality of partial data" in combined_output.lower()
        assert "fit reflectivity data" in combined_output.lower() or "reflectivity data" in combined_output.lower()
    
    @patch('builtins.print')
    def test_help_me_choose_prints_guidance(self, mock_print):
        """Test that help_me_choose prints guidance."""
        help_me_choose()
        
        # Should print guidance
        assert mock_print.call_count > 0
        # Check that something was printed - just verify the call happened
        if mock_print.call_args_list:
            printed_calls = [str(call) for call in mock_print.call_args_list]
            assert len(printed_calls) > 0
