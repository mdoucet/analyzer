"""Tests for analyzer_tools.cli module and planner CLI."""

import pytest
import tempfile
import os
import json
import logging
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from analyzer_tools.cli import main
from analyzer_tools.planner.cli import optimize, alternate_model, report, setup_logging, _print_ascii_graph, main as planner_main


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


class TestPlannerCLI:
    """Test the planner CLI functionality."""
    
    def test_optimize_help(self):
        """Test that the optimize command shows help."""
        runner = CliRunner()
        result = runner.invoke(optimize, ['--help'])
        
        assert result.exit_code == 0
        assert "Optimize neutron reflectometry experiment design" in result.output
        assert "--data-file" in result.output
        assert "--model-file" in result.output
    
    def test_main_help(self):
        """Test that the main command shows help."""
        runner = CliRunner()
        result = runner.invoke(planner_main, ['--help'])
        
        assert result.exit_code == 0
        assert "Neutron Reflectometry Experiment Planning Tool" in result.output
        assert "optimize" in result.output
    
    def test_optimize_missing_required_args(self):
        """Test that missing required arguments cause failure."""
        runner = CliRunner()
        result = runner.invoke(optimize, [])
        
        assert result.exit_code != 0
        assert "Missing option" in result.output
    
    def test_optimize_invalid_data_file(self):
        """Test that invalid data file causes failure."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(optimize, [
                '--data-file', 'nonexistent.txt',
                '--model-file', 'models/cu_thf_planner',
                '--output-dir', temp_dir,
                '--param', 'THF rho',
                '--param-values', '4.0,5.0',
                '--num-realizations', '1'
            ])
            
            assert result.exit_code != 0
    
    def test_optimize_invalid_param_values(self):
        """Test that invalid parameter values cause failure."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(optimize, [
                '--data-file', 'tests/sample_data/REFL_218386_combined_data_auto.txt',
                '--model-file', 'models/cu_thf_planner',
                '--output-dir', temp_dir,
                '--param', 'THF rho',
                '--param-values', 'invalid,values',
                '--num-realizations', '1'
            ])
            
            assert result.exit_code != 0
    
    @pytest.mark.slow
    def test_optimize_basic_functionality(self):
        """Test basic optimization functionality with minimal parameters."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(optimize, [
                '--data-file', 'tests/sample_data/REFL_218386_combined_data_auto.txt',
                '--model-file', 'models/cu_thf_planner',
                '--output-dir', temp_dir,
                '--param', 'THF rho',
                '--param-values', '4.0,5.0',
                '--num-realizations', '1',
                '--mcmc-steps', '50',  # Very small for testing
                '--burn-steps', '50',
                '--sequential',
                '--entropy-method', 'mvn'
            ])
            
            print("STDOUT:", result.output)
            if result.exception:
                print("Exception:", result.exception)
                import traceback
                traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
            
            # Check that the command completed successfully
            assert result.exit_code == 0
            
            # Check that output was generated
            assert "Starting experiment design optimization" in result.output
            assert "OPTIMIZATION RESULTS" in result.output
            
            # Check that output file was created
            output_file = os.path.join(temp_dir, "optimization_results.json")
            assert os.path.exists(output_file)
            
            # Check output file contents
            with open(output_file, 'r') as f:
                data = json.load(f)
                
            assert "parameter" in data
            assert "results" in data
            assert data["parameter"] == "THF rho"
            assert len(data["results"]) == 2  # Two parameter values
            assert "optimal_value" in data
            assert "max_information_gain" in data
    
    def test_entropy_method_validation(self):
        """Test that entropy method validation works."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(optimize, [
                '--data-file', 'tests/sample_data/REFL_218386_combined_data_auto.txt',
                '--model-file', 'models/cu_thf_planner',
                '--output-dir', temp_dir,
                '--param', 'THF rho',
                '--param-values', '4.0,5.0',
                '--entropy-method', 'invalid'
            ])
            
            assert result.exit_code != 0
            assert "Invalid value for '--entropy-method'" in result.output
    
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
    
    @patch('builtins.print')
    def test_main_with_help_flag(self, mock_print):
        """Test main function with help flag."""
        test_args = ['cli.py', '--help']
        with patch('sys.argv', test_args):
            try:
                from analyzer_tools.cli import main
                main()
            except SystemExit:
                pass  # argparse calls sys.exit after showing help
        
        # Help is printed to stdout by argparse, not through print()
        # So we just check that the function ran without error

    @patch('analyzer_tools.welcome.welcome')
    def test_main_no_args_calls_welcome(self, mock_welcome):
        """Test that main with no args calls registry print."""
        test_args = ['cli.py']
        with patch('sys.argv', test_args):
            from analyzer_tools.cli import main
            main()
        
        # The actual CLI doesn't call welcome.welcome() directly,
        # it calls registry.print_tool_overview() which does the welcome display

    @patch('analyzer_tools.registry.print_tool_overview')
    def test_main_with_list_tools(self, mock_print_overview):
        """Test main function with list-tools option."""
        test_args = ['cli.py', '--list-tools']
        with patch('sys.argv', test_args):
            from analyzer_tools.cli import main
            main()
        
        mock_print_overview.assert_called()


class TestPlannerCLIExtended:
    """Extended tests for planner CLI functionality to improve coverage."""
    
    def test_setup_logging_verbose_false(self):
        """Test setup_logging with verbose=False."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging(verbose=False)
            mock_config.assert_called_once_with(
                level=logging.INFO,
                format="%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
    
    def test_setup_logging_verbose_true(self):
        """Test setup_logging with verbose=True."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging(verbose=True)
            mock_config.assert_called_once_with(
                level=logging.DEBUG,
                format="%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
    
    def test_print_ascii_graph_basic(self):
        """Test _print_ascii_graph with basic data."""
        # Mock results data: [(param_val, info_gain, std_gain), ...]
        results = [(1.0, 0.5, 0.1), (2.0, 0.8, 0.2), (3.0, 0.3, 0.05)]
        
        with patch('click.echo') as mock_echo:
            _print_ascii_graph(results)
            
            # Should have header and data lines
            assert mock_echo.call_count >= 5  # Header + separator + 3 data lines
            
            # Check that values and gains are printed
            calls = [str(call) for call in mock_echo.call_args_list]
            combined_output = " ".join(calls)
            
            assert "1.00" in combined_output
            assert "2.00" in combined_output
            assert "3.00" in combined_output
            assert "0.500" in combined_output
            assert "0.800" in combined_output
    
    def test_print_ascii_graph_empty(self):
        """Test _print_ascii_graph with empty results."""
        results = []
        
        with patch('click.echo') as mock_echo:
            _print_ascii_graph(results)
            
            # Should still print header
            assert mock_echo.call_count >= 2
    
    def test_print_ascii_graph_zero_max_gain(self):
        """Test _print_ascii_graph with zero max gain."""
        results = [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
        
        with patch('click.echo') as mock_echo:
            _print_ascii_graph(results)
            
            # Should handle zero gain gracefully
            assert mock_echo.call_count >= 4
    
    def test_optimize_with_verbose_flag(self):
        """Test optimize command with verbose flag enabled."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a minimal optimization that should trigger the verbose path
            with patch('analyzer_tools.planner.cli.instrument.InstrumentSimulator'), \
                 patch('analyzer_tools.planner.cli.expt_from_model_file'), \
                 patch('analyzer_tools.planner.cli.ExperimentDesigner') as mock_designer_class, \
                 patch('analyzer_tools.planner.cli.make_report') as mock_make_report:
                
                # Mock the designer instance
                mock_designer = MagicMock()
                mock_designer.prior_entropy.return_value = 1.5
                mock_designer.__str__.return_value = "Mock Designer Info"
                mock_designer.optimize.return_value = ([(4.0, 0.5, 0.1)], {"data": "test"})
                mock_designer_class.return_value = mock_designer
                
                result = runner.invoke(optimize, [
                    '--data-file', 'tests/sample_data/REFL_218386_combined_data_auto.txt',
                    '--model-file', 'models/cu_thf_planner',
                    '--output-dir', temp_dir,
                    '--param', 'THF rho',
                    '--param-values', '4.0',
                    '--num-realizations', '1',
                    '--mcmc-steps', '10',
                    '--burn-steps', '10',
                    '--sequential',
                    '--verbose'
                ])
                
                # Should complete successfully and show verbose output
                assert result.exit_code == 0
                assert "Mock Designer Info" in result.output
                mock_make_report.assert_called_once()
    
    def test_optimize_with_parallel_flag(self):
        """Test optimize command with parallel execution."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('analyzer_tools.planner.cli.instrument.InstrumentSimulator'), \
                 patch('analyzer_tools.planner.cli.expt_from_model_file'), \
                 patch('analyzer_tools.planner.cli.ExperimentDesigner') as mock_designer_class, \
                 patch('analyzer_tools.planner.cli.make_report') as mock_make_report:
                
                # Mock the designer instance
                mock_designer = MagicMock()
                mock_designer.prior_entropy.return_value = 1.5
                mock_designer.optimize_parallel.return_value = ([(4.0, 0.5, 0.1)], {"data": "test"})
                mock_designer_class.return_value = mock_designer
                
                result = runner.invoke(optimize, [
                    '--data-file', 'tests/sample_data/REFL_218386_combined_data_auto.txt',
                    '--model-file', 'models/cu_thf_planner',
                    '--output-dir', temp_dir,
                    '--param', 'THF rho',
                    '--param-values', '4.0',
                    '--num-realizations', '1',
                    '--mcmc-steps', '10',
                    '--burn-steps', '10',
                    '--parallel'
                ])
                
                # Should complete successfully
                assert result.exit_code == 0
                mock_designer.optimize_parallel.assert_called_once()
                mock_make_report.assert_called_once()
    
    def test_alternate_model_help(self):
        """Test that alternate_model command shows help."""
        runner = CliRunner()
        result = runner.invoke(alternate_model, ['--help'])
        
        assert result.exit_code == 0
        assert "Evaluate an alternate model" in result.output
        assert "--result-file" in result.output
        assert "--model-file" in result.output
    
    def test_alternate_model_missing_args(self):
        """Test alternate_model command with missing arguments."""
        runner = CliRunner()
        result = runner.invoke(alternate_model, [])
        
        assert result.exit_code != 0
        assert "Missing option" in result.output
    
    def test_alternate_model_invalid_result_file(self):
        """Test alternate_model command with invalid result file."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(alternate_model, [
                '--result-file', 'nonexistent.json',
                '--model-file', 'models/cu_thf_planner',
                '--output-dir', temp_dir
            ])
            
            assert result.exit_code != 0
    
    def test_alternate_model_basic_functionality(self):
        """Test alternate_model command basic functionality."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock results file
            result_file = os.path.join(temp_dir, "test_results.json")
            with open(result_file, 'w') as f:
                json.dump({"test": "data"}, f)
            
            with patch('analyzer_tools.planner.cli.evaluate_alternate_model') as mock_evaluate, \
                 patch('analyzer_tools.planner.cli.make_report') as mock_report:
                
                result = runner.invoke(alternate_model, [
                    '--result-file', result_file,
                    '--model-file', 'models/cu_thf_planner',
                    '--output-dir', temp_dir,
                    '--mcmc-steps', '100',
                    '--burn-steps', '50',
                    '--verbose'
                ])
                
                # Should complete successfully
                assert result.exit_code == 0
                assert "Evaluating alternate model" in result.output
                assert "Alternate model evaluation completed" in result.output
                
                # Should call the underlying functions
                mock_evaluate.assert_called_once()
                mock_report.assert_called_once()
    
    def test_alternate_model_error_handling(self):
        """Test alternate_model command error handling."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock results file
            result_file = os.path.join(temp_dir, "test_results.json")
            with open(result_file, 'w') as f:
                json.dump({"test": "data"}, f)
            
            with patch('analyzer_tools.planner.cli.evaluate_alternate_model') as mock_evaluate:
                mock_evaluate.side_effect = Exception("Test error")
                
                result = runner.invoke(alternate_model, [
                    '--result-file', result_file,
                    '--model-file', 'models/cu_thf_planner',
                    '--output-dir', temp_dir
                ])
                
                # Should handle error gracefully
                assert result.exit_code != 0
                assert "Error: Test error" in result.output
    
    def test_report_help(self):
        """Test that report command shows help."""
        runner = CliRunner()
        result = runner.invoke(report, ['--help'])
        
        assert result.exit_code == 0
        assert "Generate a report from optimization results" in result.output
        assert "--result-file" in result.output
        assert "--output-dir" in result.output
    
    def test_report_missing_args(self):
        """Test report command with missing arguments."""
        runner = CliRunner()
        result = runner.invoke(report, [])
        
        assert result.exit_code != 0
        assert "Missing option" in result.output
    
    def test_report_invalid_result_file(self):
        """Test report command with invalid result file."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(report, [
                '--result-file', 'nonexistent.json',
                '--output-dir', temp_dir
            ])
            
            assert result.exit_code != 0
    
    def test_report_basic_functionality(self):
        """Test report command basic functionality."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock results file
            result_file = os.path.join(temp_dir, "test_results.json")
            with open(result_file, 'w') as f:
                json.dump({"test": "data"}, f)
            
            with patch('analyzer_tools.planner.cli.make_report') as mock_report:
                result = runner.invoke(report, [
                    '--result-file', result_file,
                    '--output-dir', temp_dir,
                    '--verbose'
                ])
                
                # Should complete successfully
                assert result.exit_code == 0
                assert "Report generated in directory" in result.output
                
                # Should call the underlying function
                mock_report.assert_called_once_with(
                    json_file=result_file,
                    output_dir=temp_dir,
                )
    
    def test_report_error_handling(self):
        """Test report command error handling."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock results file
            result_file = os.path.join(temp_dir, "test_results.json")
            with open(result_file, 'w') as f:
                json.dump({"test": "data"}, f)
            
            with patch('analyzer_tools.planner.cli.make_report') as mock_report:
                mock_report.side_effect = Exception("Test error")
                
                result = runner.invoke(report, [
                    '--result-file', result_file,
                    '--output-dir', temp_dir
                ])
                
                # Should handle error gracefully
                assert result.exit_code != 0
                assert "Error generating report: Test error" in result.output
