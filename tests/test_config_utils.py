"""
Tests for analyzer_tools.config_utils module.

Configuration is now read from environment variables (optionally loaded from
a .env file via python-dotenv).  Tests use `monkeypatch` to set env vars and
reset the global singleton between tests.
"""

import os

import pytest

import analyzer_tools.config_utils as config_mod
from analyzer_tools.config_utils import Config, get_config, get_data_organization_info

# Captured before any autouse fixture can stub it.
_real_load_env = config_mod._load_env


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch):
    """Reset the global _config_instance and disable the .env cascade so
    tests aren't contaminated by a project or user-global .env file."""
    monkeypatch.setattr(config_mod, "_config_instance", None)
    # Clear every known ANALYZER_* default so cascade loads can be observed.
    for key in config_mod._DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    # Stub the cascade: tests that want .env loading call `_load_env` directly
    # or construct `Config(dotenv_path=...)` after re-enabling the real impl.
    monkeypatch.setattr(config_mod, "_load_env", lambda dotenv_path=None: [])
    yield


class TestConfig:
    """Test the Config class."""

    def test_defaults_when_no_env_vars(self, monkeypatch):
        """With no env vars the built-in defaults are returned."""
        for key in config_mod._DEFAULTS:
            monkeypatch.delenv(key, raising=False)

        config = Config()
        assert config.get_results_dir() == "results"
        assert config.get_combined_data_dir() == "data/combined"
        assert config.get_partial_data_dir() == "data/partial"
        assert config.get_reports_dir() == "reports"
        assert config.get_combined_data_template() == "REFL_{set_id}_combined_data_auto.txt"
        assert config.get_models_dir() == "models"

    def test_env_vars_override_defaults(self, monkeypatch):
        """Environment variables take precedence over built-in defaults."""
        monkeypatch.setenv("ANALYZER_RESULTS_DIR", "/tmp/test_fits")
        monkeypatch.setenv("ANALYZER_COMBINED_DATA_DIR", "test_combined")
        monkeypatch.setenv("ANALYZER_PARTIAL_DATA_DIR", "test_partial")
        monkeypatch.setenv("ANALYZER_REPORTS_DIR", "test_reports")
        monkeypatch.setenv("ANALYZER_COMBINED_DATA_TEMPLATE", "TEST_{set_id}_data.txt")

        config = Config()
        assert config.get_results_dir() == "/tmp/test_fits"
        assert config.get_combined_data_dir() == "test_combined"
        assert config.get_partial_data_dir() == "test_partial"
        assert config.get_reports_dir() == "test_reports"
        assert config.get_combined_data_template() == "TEST_{set_id}_data.txt"

    def test_models_dir_default(self, monkeypatch):
        """models_dir defaults to 'models' when env var is absent."""
        monkeypatch.delenv("ANALYZER_MODELS_DIR", raising=False)
        config = Config()
        assert config.get_models_dir() == "models"

    def test_models_dir_from_env(self, monkeypatch):
        """models_dir reads ANALYZER_MODELS_DIR."""
        monkeypatch.setenv("ANALYZER_MODELS_DIR", "custom_models")
        config = Config()
        assert config.get_models_dir() == "custom_models"

    def test_results_dir_env(self, monkeypatch):
        """get_results_dir returns ANALYZER_RESULTS_DIR."""
        monkeypatch.setenv("ANALYZER_RESULTS_DIR", "/some/results")
        assert Config().get_results_dir() == "/some/results"

    def test_independent_instances_see_same_env(self, monkeypatch):
        """Two Config() objects created with the same env return the same values."""
        monkeypatch.setenv("ANALYZER_RESULTS_DIR", "/shared")
        c1 = Config()
        c2 = Config()
        assert c1.get_results_dir() == c2.get_results_dir() == "/shared"

    def test_dotenv_file_is_loaded(self, monkeypatch, tmp_path):
        """Config loads values from a dotenv file when dotenv_path is given."""
        # Restore the real cascade loader for this test.
        monkeypatch.setattr(config_mod, "_load_env", _real_load_env)
        env_file = tmp_path / ".env"
        env_file.write_text("ANALYZER_RESULTS_DIR=/from/dotenv\n")
        # Make sure the env var is not already set so dotenv value is picked up.
        monkeypatch.delenv("ANALYZER_RESULTS_DIR", raising=False)

        config = Config(dotenv_path=str(env_file))
        assert config.get_results_dir() == "/from/dotenv"

    def test_env_var_wins_over_dotenv(self, monkeypatch, tmp_path):
        """An existing env var is NOT overridden by the .env file (override=False)."""
        monkeypatch.setattr(config_mod, "_load_env", _real_load_env)
        env_file = tmp_path / ".env"
        env_file.write_text("ANALYZER_RESULTS_DIR=/from/dotenv\n")
        monkeypatch.setenv("ANALYZER_RESULTS_DIR", "/from/shell")

        config = Config(dotenv_path=str(env_file))
        assert config.get_results_dir() == "/from/shell"

    def test_get_path_known_key(self, monkeypatch):
        """get_path accepts an ANALYZER_-prefixed key."""
        monkeypatch.setenv("ANALYZER_REPORTS_DIR", "my_reports")
        config = Config()
        assert config.get_path("ANALYZER_REPORTS_DIR") == "my_reports"

    def test_get_path_auto_prefix(self, monkeypatch):
        """get_path auto-prefixes a bare key with ANALYZER_."""
        monkeypatch.setenv("ANALYZER_REPORTS_DIR", "auto_reports")
        config = Config()
        assert config.get_path("reports_dir") == "auto_reports"


class TestGlobalConfig:
    """Test global config functions."""

    def test_get_config_returns_singleton(self):
        """get_config() returns the same object on repeated calls."""
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_get_config_creates_from_defaults(self, monkeypatch):
        """get_config() returns a Config with default values."""
        for key in config_mod._DEFAULTS:
            monkeypatch.delenv(key, raising=False)

        config = get_config()
        assert config.get_combined_data_dir() == "data/combined"

    def test_get_data_organization_info_keys(self):
        """get_data_organization_info() returns dict with all expected keys."""
        info = get_data_organization_info()
        expected = {
            "combined_data_dir", "partial_data_dir", "reports_dir",
            "results_dir", "combined_data_template", "models_dir",
        }
        assert set(info.keys()) == expected

    def test_get_data_organization_info_values_are_strings(self):
        """All values in data organization info are strings."""
        info = get_data_organization_info()
        for k, v in info.items():
            assert isinstance(v, str), f"Expected str for {k}, got {type(v)}"
