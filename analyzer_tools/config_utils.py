"""
Configuration utilities for analyzer tools.

Settings are read from environment variables, optionally loaded from a .env
file in the working directory (via python-dotenv).

Variable names
--------------
ANALYZER_RESULTS_DIR          Path for fit output directories       (default: results)
ANALYZER_COMBINED_DATA_DIR    Path to combined reflectivity files   (default: data/combined)
ANALYZER_PARTIAL_DATA_DIR     Path to partial reflectivity files    (default: data/partial)
ANALYZER_REPORTS_DIR          Path for generated reports            (default: reports)
ANALYZER_COMBINED_DATA_TEMPLATE  File-name template                 (default: REFL_{set_id}_combined_data_auto.txt)
ANALYZER_MODELS_DIR           Path to model Python files            (default: models)
"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
    _DOTENV_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DOTENV_AVAILABLE = False


_DEFAULTS: dict[str, str] = {
    "ANALYZER_RESULTS_DIR":             "results",
    "ANALYZER_COMBINED_DATA_DIR":       "data/combined",
    "ANALYZER_PARTIAL_DATA_DIR":        "data/partial",
    "ANALYZER_REPORTS_DIR":             "reports",
    "ANALYZER_COMBINED_DATA_TEMPLATE":  "REFL_{set_id}_combined_data_auto.txt",
    "ANALYZER_MODELS_DIR":              "models",
}


def _load_env(dotenv_path: Optional[str] = None) -> None:
    """Load a .env file if dotenv is available.

    If *dotenv_path* is not given, looks for ``.env`` in the current working
    directory. Does nothing when python-dotenv is not installed.
    """
    if not _DOTENV_AVAILABLE:
        return
    path = Path(dotenv_path) if dotenv_path else Path(".env")
    if path.exists():
        _load_dotenv(path, override=False)


class Config:
    """Centralized configuration manager backed by environment variables."""

    def __init__(self, dotenv_path: Optional[str] = None):
        """Load configuration.

        Parameters
        ----------
        dotenv_path:
            Optional path to a ``.env`` file. When omitted, ``.env`` in the
            current working directory is tried. Environment variables that are
            already set are **not** overridden by the file (``override=False``).
        """
        _load_env(dotenv_path)

    def _get(self, key: str) -> str:
        return os.environ.get(key, _DEFAULTS[key])

    def get_results_dir(self) -> str:
        return self._get("ANALYZER_RESULTS_DIR")

    def get_combined_data_dir(self) -> str:
        return self._get("ANALYZER_COMBINED_DATA_DIR")

    def get_partial_data_dir(self) -> str:
        return self._get("ANALYZER_PARTIAL_DATA_DIR")

    def get_reports_dir(self) -> str:
        return self._get("ANALYZER_REPORTS_DIR")

    def get_combined_data_template(self) -> str:
        return self._get("ANALYZER_COMBINED_DATA_TEMPLATE")

    def get_models_dir(self) -> str:
        return self._get("ANALYZER_MODELS_DIR")

    # Keep a generic accessor for forward compatibility.
    def get_path(self, key: str) -> str:
        """Return the value of an arbitrary ANALYZER_* environment variable."""
        env_key = key if key.startswith("ANALYZER_") else f"ANALYZER_{key.upper()}"
        if env_key in _DEFAULTS:
            return self._get(env_key)
        return os.environ[env_key]


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_config_instance: Optional[Config] = None


def get_config(dotenv_path: Optional[str] = None) -> Config:
    """Return the global :class:`Config` instance (created on first call)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(dotenv_path)
    return _config_instance


def get_data_organization_info() -> dict:
    """Return current data-directory layout as a plain dict."""
    config = get_config()
    return {
        "combined_data_dir":        config.get_combined_data_dir(),
        "partial_data_dir":         config.get_partial_data_dir(),
        "reports_dir":              config.get_reports_dir(),
        "results_dir":              config.get_results_dir(),
        "combined_data_template":   config.get_combined_data_template(),
        "models_dir":               config.get_models_dir(),
    }
