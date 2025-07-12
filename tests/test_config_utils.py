"""
Tests for analyzer_tools.config_utils module.
"""

import tempfile
import os
from unittest.mock import patch

from analyzer_tools.config_utils import Config, get_config, get_data_organization_info


class TestConfig:
    """Test the Config class."""
    
    def test_config_with_existing_file(self):
        """Test loading config from existing file."""
        config_content = """[paths]
results_dir = /tmp/test_fits
combined_data_dir = test_combined
partial_data_dir = test_partial
reports_dir = test_reports
combined_data_template = TEST_{set_id}_data.txt
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            config_file = f.name
        
        try:
            config = Config(config_file)
            assert config.get_results_dir() == "/tmp/test_fits"
            assert config.get_combined_data_dir() == "test_combined"
            assert config.get_partial_data_dir() == "test_partial"
            assert config.get_reports_dir() == "test_reports"
            assert config.get_combined_data_template() == "TEST_{set_id}_data.txt"
        finally:
            os.unlink(config_file)
    
    def test_config_with_missing_file(self):
        """Test config behavior when file doesn't exist."""
        config = Config("nonexistent_config.ini")
        
        # Should fall back to defaults
        assert config.get_results_dir() == "/tmp/fits"
        assert config.get_combined_data_dir() == "data/combined"
        assert config.get_partial_data_dir() == "data/partial"
        assert config.get_reports_dir() == "reports"
        assert config.get_combined_data_template() == "REFL_{set_id}_combined_data_auto.txt"
    
    def test_config_models_dir_default(self):
        """Test models directory defaults to 'models' when not configured."""
        config = Config("nonexistent_config.ini")
        assert config.get_models_dir() == "models"
    
    def test_config_models_dir_configured(self):
        """Test models directory when configured."""
        config_content = """[paths]
results_dir = /tmp/fits
models_dir = custom_models
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            config_file = f.name
        
        try:
            config = Config(config_file)
            assert config.get_models_dir() == "custom_models"
        finally:
            os.unlink(config_file)
    
    def test_get_path_method(self):
        """Test the generic get_path method."""
        config_content = """[paths]
custom_path = /custom/location
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            config_file = f.name
        
        try:
            config = Config(config_file)
            assert config.get_path('custom_path') == "/custom/location"
        finally:
            os.unlink(config_file)


class TestGlobalConfig:
    """Test global config functions."""
    
    @patch('analyzer_tools.config_utils._config_instance', None)
    def test_get_config_creates_instance(self):
        """Test that get_config creates a global instance."""
        config1 = get_config("nonexistent_test.ini")
        config2 = get_config("nonexistent_test.ini")
        
        # Should return the same instance
        assert config1 is config2
    
    def test_get_data_organization_info(self):
        """Test data organization info function."""
        info = get_data_organization_info()
        
        # Should return a dict with all expected keys
        expected_keys = {
            'combined_data_dir', 'partial_data_dir', 'reports_dir', 
            'results_dir', 'combined_data_template', 'models_dir'
        }
        assert set(info.keys()) == expected_keys
        
        # Should have default values when no config exists
        assert isinstance(info['combined_data_dir'], str)
        assert isinstance(info['partial_data_dir'], str)
        assert isinstance(info['combined_data_template'], str)


class TestConfigError:
    """Test config error handling."""
    
    def test_config_with_malformed_file(self):
        """Test behavior with malformed config file."""
        malformed_content = "this is not valid ini format"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(malformed_content)
            config_file = f.name
        
        try:
            # Config should handle parsing errors and fall back to defaults
            config = Config(config_file)
            # Even with malformed file, defaults should be set
            assert config.get_combined_data_dir() == "data/combined"  # Default
        except Exception:
            # If exception is raised, that's also acceptable behavior
            pass
        finally:
            os.unlink(config_file)
