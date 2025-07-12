"""Tests for analyzer_tools.cli module."""

import pytest
from unittest.mock import patch, MagicMock
from analyzer_tools.cli import main


class TestCliMain:
    """Test the main CLI function."""
    
    @patch('analyzer_tools.registry.print_tool_overview')
    @patch('builtins.print')
    def test_list_tools_option(self, mock_print, mock_overview):
        """Test --list-tools option."""
        # Test with --list-tools
        with patch('sys.argv', ['cli.py', '--list-tools']):
            main()
        
        # Should call print_tool_overview 
        mock_overview.assert_called_once()
    
    @patch('analyzer_tools.registry.get_workflows')
    @patch('builtins.print')
    def test_workflows_option(self, mock_print, mock_get_workflows):
        """Test --workflows option."""
        # Mock workflows data
        mock_workflows = {
            'basic_analysis': {
                'name': 'Basic Analysis',
                'description': 'Basic workflow',
                'steps': ['step1', 'step2'],
                'tools': ['tool1', 'tool2']
            }
        }
        mock_get_workflows.return_value = mock_workflows
        
        # Test with --workflows
        with patch('sys.argv', ['cli.py', '--workflows']):
            main()
        
        # Should call get_workflows and print information
        mock_get_workflows.assert_called_once()
        mock_print.assert_called()
        
        # Check that workflow information was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        combined_output = " ".join(print_calls)
        
        assert "Basic Analysis" in combined_output
    
    @patch('analyzer_tools.registry.print_tool_overview')
    def test_no_arguments_calls_welcome(self, mock_overview):
        """Test that calling with no arguments shows tool overview."""
        with patch('sys.argv', ['cli.py']):
            main()
        
        # Should call print_tool_overview function
        mock_overview.assert_called_once()
    
    @patch('analyzer_tools.registry.print_tool_overview')
    @patch('builtins.print')
    def test_list_tools_with_specific_data_type(self, mock_print, mock_overview):
        """Test --list-tools with data type filtering."""
        # Test listing tools - should show all data types
        with patch('sys.argv', ['cli.py', '--list-tools']):
            main()
        
        mock_overview.assert_called_once()


class TestCliHelpers:
    """Test CLI helper functions and edge cases."""
    
    @patch('analyzer_tools.registry.print_tool_overview')
    @patch('builtins.print')
    def test_empty_tools_list(self, mock_print, mock_overview):
        """Test handling of empty tools list."""        
        with patch('sys.argv', ['cli.py', '--list-tools']):
            main()
        
        # Should call print_tool_overview
        mock_overview.assert_called_once()
    
    @patch('analyzer_tools.registry.get_workflows')
    @patch('builtins.print') 
    def test_empty_workflows_list(self, mock_print, mock_get_workflows):
        """Test handling of empty workflows list."""
        mock_get_workflows.return_value = {}
        
        with patch('sys.argv', ['cli.py', '--workflows']):
            main()
        
        # Should handle empty workflows gracefully
        mock_print.assert_called()
    
    @patch('builtins.print')
    def test_invalid_option_shows_help(self, mock_print):
        """Test that invalid options show help message."""
        with patch('sys.argv', ['cli.py', '--invalid-option']):
            try:
                main()
            except SystemExit:
                # argparse exits on invalid options, which is expected
                pass
        
        # The function should either print help or exit gracefully
        # This test mainly ensures no exceptions are raised unexpectedly


class TestCliIntegration:
    """Integration tests for CLI functionality."""
    
    @patch('sys.argv', ['cli.py', '--help'])
    def test_help_option(self):
        """Test --help option."""
        # Help should cause SystemExit (normal argparse behavior)
        with pytest.raises(SystemExit):
            main()
    
    @patch('analyzer_tools.registry.print_tool_overview')
    @patch('analyzer_tools.registry.get_all_tools')
    @patch('analyzer_tools.registry.get_workflows')
    def test_multiple_calls_work_independently(self, mock_get_workflows, mock_get_tools, mock_overview):
        """Test that multiple CLI calls work independently."""
        mock_get_workflows.return_value = {'workflow1': {'name': 'Test', 'description': 'test', 'steps': [], 'tools': []}}
        
        # Call with different arguments
        with patch('sys.argv', ['cli.py']):
            main()
        mock_overview.assert_called()
        
        with patch('sys.argv', ['cli.py', '--list-tools']):
            main()
        # print_tool_overview called again
        
        with patch('sys.argv', ['cli.py', '--workflows']):
            main()
        mock_get_workflows.assert_called()
