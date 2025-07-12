import pytest
import os
import tempfile
import shutil
import numpy as np
from unittest.mock import patch, MagicMock
from analyzer_tools.utils import model_utils

class TestModelUtils:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.test_dir)

    def test_list_available_models(self):
        """Test listing available models from models directory."""
        # Create test model files
        models_dir = os.path.join(self.test_dir, 'models')
        os.makedirs(models_dir)
        
        test_files = [
            'cu_thf.py',
            'test_model.py',
            '__init__.py',  # Should be excluded
            'not_a_python_file.txt'  # Should be excluded
        ]
        
        for filename in test_files:
            filepath = os.path.join(models_dir, filename)
            with open(filepath, 'w') as f:
                if filename.endswith('.py'):
                    f.write("# Test model\ndef create_fit_experiment():\n    pass\n")
                else:
                    f.write("# Not a Python file\n")
        
        with patch('analyzer_tools.config_utils.get_config') as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.get_models_dir.return_value = models_dir
            mock_config.return_value = mock_config_instance
            
            models = model_utils.list_available_models()
            
            # Should return Python files excluding __init__.py
            assert 'cu_thf' in models
            assert 'test_model' in models
            assert '__init__' not in models
            assert 'not_a_python_file' not in models

    def test_list_available_models_empty_dir(self):
        """Test listing models from empty directory."""
        models_dir = os.path.join(self.test_dir, 'empty_models')
        os.makedirs(models_dir)
        
        with patch('analyzer_tools.config_utils.get_config') as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.get_models_dir.return_value = models_dir
            mock_config.return_value = mock_config_instance
            
            models = model_utils.list_available_models()
            assert models == []

    @patch('importlib.import_module')
    def test_validate_model_valid(self, mock_import):
        """Test validating a valid model."""
        # Setup mock model with required function
        mock_model = MagicMock()
        mock_model.create_fit_experiment = MagicMock()
        mock_import.return_value = mock_model
        
        result = model_utils.validate_model('test_model')
        
        assert result is True
        mock_import.assert_called_once_with('models.test_model')

    @patch('importlib.import_module')
    def test_validate_model_import_error(self, mock_import):
        """Test validating model with import error."""
        mock_import.side_effect = ImportError("Module not found")
        
        result = model_utils.validate_model('nonexistent_model')
        
        assert result is False

    @patch('importlib.import_module')
    def test_validate_model_missing_function(self, mock_import):
        """Test validating model missing required function."""
        # Setup mock model without required function
        mock_model = MagicMock()
        del mock_model.create_fit_experiment
        mock_import.return_value = mock_model
        
        result = model_utils.validate_model('invalid_model')
        
        assert result is False

    @patch('importlib.import_module')
    def test_get_model_info_success(self, mock_import):
        """Test getting model information successfully."""
        # Setup mock model with docstring
        mock_model = MagicMock()
        mock_model.__doc__ = "Test model for neutron reflectometry"
        mock_model.create_fit_experiment = MagicMock()
        mock_import.return_value = mock_model
        
        info = model_utils.get_model_info('test_model')
        
        assert info['name'] == 'test_model'
        assert info['description'] == "Test model for neutron reflectometry"
        assert info['valid'] is True

    @patch('importlib.import_module')
    def test_get_model_info_no_docstring(self, mock_import):
        """Test getting model info when no docstring is available."""
        mock_model = MagicMock()
        mock_model.__doc__ = None
        mock_model.create_fit_experiment = MagicMock()
        mock_import.return_value = mock_model
        
        info = model_utils.get_model_info('test_model')
        
        assert info['description'] == "No description available"

    @patch('importlib.import_module')
    def test_get_model_info_invalid_model(self, mock_import):
        """Test getting info for invalid model."""
        mock_import.side_effect = ImportError("Module not found")
        
        info = model_utils.get_model_info('invalid_model')
        
        assert info['valid'] is False
        assert 'error' in info

    def test_model_name_from_path(self):
        """Test extracting model name from file path."""
        test_cases = [
            ('/path/to/models/cu_thf.py', 'cu_thf'),
            ('models/test_model.py', 'test_model'),
            ('simple_model.py', 'simple_model'),
            ('/absolute/path/complex_model.py', 'complex_model')
        ]
        
        for file_path, expected_name in test_cases:
            assert model_utils.model_name_from_path(file_path) == expected_name

    def test_is_valid_model_file(self):
        """Test checking if file is a valid model file."""
        test_cases = [
            ('cu_thf.py', True),
            ('test_model.py', True),
            ('__init__.py', False),
            ('not_python.txt', False),
            ('README.md', False),
            ('.hidden_file.py', False)
        ]
        
        for filename, expected in test_cases:
            assert model_utils.is_valid_model_file(filename) == expected

if __name__ == "__main__":
    pytest.main()
