"""
Configuration utilities for analyzer tools.

Provides centralized access to configuration settings from config.ini
"""

import configparser
import os
from typing import Optional


class Config:
    """Centralized configuration manager."""
    
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file."""
        self._config = configparser.ConfigParser()
        if os.path.exists(self.config_file):
            self._config.read(self.config_file)
            # If file exists but has no paths section, add defaults
            if not self._config.has_section('paths'):
                self._set_defaults()
        else:
            # Provide defaults if config file doesn't exist
            self._set_defaults()
    
    def _set_defaults(self):
        """Set default configuration values."""
        self._config.add_section('paths')
        self._config.set('paths', 'results_dir', '/tmp/fits')
        self._config.set('paths', 'combined_data_dir', 'data/combined')
        self._config.set('paths', 'partial_data_dir', 'data/partial')
        self._config.set('paths', 'reports_dir', 'reports')
        self._config.set('paths', 'combined_data_template', 'REFL_{set_id}_combined_data_auto.txt')
    
    def get_path(self, path_name: str) -> str:
        """Get a path from configuration."""
        return self._config.get('paths', path_name)
    
    def get_combined_data_dir(self) -> str:
        """Get the combined data directory."""
        return self.get_path('combined_data_dir')
    
    def get_partial_data_dir(self) -> str:
        """Get the partial data directory."""
        return self.get_path('partial_data_dir')
    
    def get_reports_dir(self) -> str:
        """Get the reports directory."""
        return self.get_path('reports_dir')
    
    def get_results_dir(self) -> str:
        """Get the results directory."""
        return self.get_path('results_dir')
    
    def get_combined_data_template(self) -> str:
        """Get the combined data file template."""
        return self.get_path('combined_data_template')
    
    def get_models_dir(self) -> str:
        """Get the models directory (defaults to 'models')."""
        try:
            return self.get_path('models_dir')
        except (configparser.NoOptionError, configparser.NoSectionError):
            return 'models'


# Global config instance
_config_instance: Optional[Config] = None


def get_config(config_file: str = "config.ini") -> Config:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_file)
    return _config_instance


def get_data_organization_info() -> dict:
    """Get current data organization from config for display purposes."""
    config = get_config()
    return {
        'combined_data_dir': config.get_combined_data_dir(),
        'partial_data_dir': config.get_partial_data_dir(),
        'reports_dir': config.get_reports_dir(),
        'results_dir': config.get_results_dir(),
        'combined_data_template': config.get_combined_data_template(),
        'models_dir': config.get_models_dir()
    }
