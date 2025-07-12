import pytest
import os
import tempfile
import shutil
import numpy as np
from unittest.mock import patch, MagicMock, call
from analyzer_tools import run_fit

class TestRunFit:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.test_dir, 'test_data.txt')
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.output_dir)
        
        # Create test data file
        test_data = np.array([
            [0.01, 0.02, 0.03, 0.04],  # Q
            [1.0, 0.9, 0.8, 0.7],     # R
            [0.1, 0.08, 0.06, 0.05],  # dR
            [0.001, 0.002, 0.003, 0.004]  # dQ
        ]).T
        np.savetxt(self.data_file, test_data)

    def teardown_method(self):
        shutil.rmtree(self.test_dir)

    @patch('importlib.import_module')
    @patch('numpy.loadtxt')
    @patch('bumps.fitters.fit')
    @patch('os.chdir')
    def test_execute_fit_success(self, mock_chdir, mock_fit, mock_loadtxt, mock_import):
        # Setup mocks
        mock_model = MagicMock()
        mock_experiment = MagicMock()
        mock_model.create_fit_experiment.return_value = mock_experiment
        mock_import.return_value = mock_model
        
        mock_loadtxt.return_value = np.array([
            [0.01, 1.0, 0.1, 0.001],
            [0.02, 0.9, 0.08, 0.002]
        ])
        
        # Test execution
        run_fit.execute_fit('test_model', self.data_file, self.output_dir)
        
        # Verify calls
        mock_import.assert_called_once_with('models.test_model')
        mock_loadtxt.assert_called_once_with(self.data_file)
        mock_chdir.assert_called_once_with(self.output_dir)
        mock_fit.assert_called_once()

    @patch('importlib.import_module')
    @patch('builtins.print')
    def test_execute_fit_import_error(self, mock_print, mock_import):
        # Setup mock to raise ImportError
        mock_import.side_effect = ImportError("Module not found")
        
        # Test execution
        run_fit.execute_fit('nonexistent_model', self.data_file, self.output_dir)
        
        # Verify error message was printed
        mock_print.assert_called_with(
            "Error: Could not import model 'nonexistent_model' from 'models' directory: Module not found"
        )

    @patch('importlib.import_module')
    @patch('builtins.print')
    def test_execute_fit_missing_function(self, mock_print, mock_import):
        # Setup mock module without create_fit_experiment function
        mock_model = MagicMock()
        del mock_model.create_fit_experiment
        mock_import.return_value = mock_model
        
        # Test execution
        run_fit.execute_fit('test_model', self.data_file, self.output_dir)
        
        # Verify error message was printed
        mock_print.assert_called_with(
            "Error: 'create_fit_experiment' function not found in 'test_model' module."
        )

    @patch('builtins.print')
    def test_execute_fit_missing_data_file(self, mock_print):
        # Test with non-existent data file
        nonexistent_file = os.path.join(self.test_dir, 'nonexistent.txt')
        
        run_fit.execute_fit('test_model', nonexistent_file, self.output_dir)
        
        # Verify error message was printed
        mock_print.assert_called_with(f"Error: Data file not found at {nonexistent_file}")

    @patch('analyzer_tools.run_fit.execute_fit')
    @patch('configparser.ConfigParser')
    def test_main_function(self, mock_config_parser, mock_execute_fit):
        # Setup mock config
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda section, key: {
            ('paths', 'combined_data_dir'): '/test/data',
            ('paths', 'results_dir'): '/test/results'
        }.get((section, key), '/default')
        mock_config_parser.return_value = mock_config
        
        # Test with command line arguments
        test_args = ['run_fit.py', 'test_model', '123']
        with patch('sys.argv', test_args):
            run_fit.main()
        
        # Verify execute_fit was called
        mock_execute_fit.assert_called_once()

    @patch('os.path.exists')
    @patch('builtins.print')
    def test_main_function_missing_config(self, mock_print, mock_exists):
        # Test with missing config file
        mock_exists.return_value = False
        
        test_args = ['run_fit.py', 'test_model', '123']
        with patch('sys.argv', test_args):
            run_fit.main()
        
        # Should print error about missing config
        error_calls = [call for call in mock_print.call_args_list 
                      if 'config.ini not found' in str(call)]
        assert len(error_calls) > 0

if __name__ == "__main__":
    pytest.main()
