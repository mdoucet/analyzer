"""Tests for analyzer_tools.cli module."""

import pytest
from unittest.mock import patch
from click.testing import CliRunner

from analyzer_tools.cli import main


class TestCliMain:
    """Test the main CLI function."""
    
    @patch('analyzer_tools.cli.print_tool_overview')
    def test_list_tools_option(self, mock_overview):
        """Test --list-tools option."""
        runner = CliRunner()
        result = runner.invoke(main, ['--list-tools'])
        
        # Should call print_tool_overview
        assert result.exit_code == 0
        mock_overview.assert_called_once()
    
    @patch('analyzer_tools.registry.get_workflows')
    def test_workflows_option(self, mock_get_workflows):
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
        
        runner = CliRunner()
        result = runner.invoke(main, ['--workflows'])
        
        # Should call get_workflows and print information
        assert result.exit_code == 0
        mock_get_workflows.assert_called_once()
        
        # Check that workflow information was printed
        assert "Basic Analysis" in result.output



class TestCliHelpers:
    """Test CLI helper functions and edge cases."""
    
    @patch('analyzer_tools.registry.get_workflows')
    def test_empty_workflows_list(self, mock_get_workflows):
        """Test handling of empty workflows list."""
        mock_get_workflows.return_value = {}
        
        runner = CliRunner()
        result = runner.invoke(main, ['--workflows'])
        
        # Should handle empty workflows gracefully
        assert result.exit_code == 0


class TestCliIntegration:
    """Integration tests for CLI functionality."""
    
    def test_help_option(self):
        """Test --help option."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        assert result.exit_code == 0
        assert "Neutron Reflectometry Data Analysis Tools" in result.output
    
    @patch('analyzer_tools.cli.print_tool_overview')
    @patch('analyzer_tools.registry.get_all_tools')
    @patch('analyzer_tools.registry.get_workflows')
    def test_multiple_calls_work_independently(self, mock_get_workflows, mock_get_tools, mock_overview):
        """Test that multiple CLI calls work independently."""
        mock_get_workflows.return_value = {'workflow1': {'name': 'Test', 'description': 'test', 'steps': [], 'tools': []}}
        
        runner = CliRunner()
        
        # Call with different arguments
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_overview.assert_called()
        
        result = runner.invoke(main, ['--list-tools'])
        assert result.exit_code == 0
        
        result = runner.invoke(main, ['--workflows'])
        assert result.exit_code == 0
        mock_get_workflows.assert_called()



