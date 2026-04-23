"""
Configuration utilities for analyzer tools.

``.env`` cascade
----------------
When the first :func:`get_config` call is made (from any CLI entry point),
``.env`` files are loaded in **decreasing priority** (earlier loads win
because ``override=False`` is used for every call):

1. **Process environment** — real shell ``export`` values always win.
2. **Explicit path** — passed as ``get_config(dotenv_path=...)`` or via
   the ``ANALYZER_ENV_FILE`` environment variable.
3. **Project ``.env``** — the nearest ``.env`` found by walking upward
   from the current working directory (``dotenv.find_dotenv``).
4. **User-global ``.env``** — ``$ANALYZER_CONFIG_DIR/.env`` if set,
   else ``$XDG_CONFIG_HOME/analyzer/.env`` if set,
   else ``~/.config/analyzer/.env``.

Typical layout:

- Put LLM secrets (``LLM_PROVIDER``, ``LLM_API_KEY``, ``LLM_MODEL``,
  ``LLM_BASE_URL``) in the **user-global** file once.
- Put per-sample overrides (``ANALYZER_MODELS_DIR``,
  ``ANALYZER_RESULTS_DIR`` …) in a **project** ``.env`` next to your data.

Variable names
--------------
ANALYZER_RESULTS_DIR          Path for fit output directories       (default: results)
ANALYZER_COMBINED_DATA_DIR    Path to combined reflectivity files   (default: data/combined)
ANALYZER_PARTIAL_DATA_DIR     Path to partial reflectivity files    (default: data/partial)
ANALYZER_REPORTS_DIR          Path for generated reports            (default: reports)
ANALYZER_COMBINED_DATA_TEMPLATE  File-name template                 (default: REFL_{set_id}_combined_data_auto.txt)
ANALYZER_MODELS_DIR           Path to model Python files            (default: models)
ANALYZER_ENV_FILE             Extra ``.env`` path loaded before project/global
ANALYZER_CONFIG_DIR           Override directory for the user-global ``.env``
"""

import os
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
    from dotenv import find_dotenv as _find_dotenv  # type: ignore
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


def _user_global_env_path() -> Path:
    """Return the path to the user-global ``.env``.

    Order: ``$ANALYZER_CONFIG_DIR`` → ``$XDG_CONFIG_HOME/analyzer`` →
    ``~/.config/analyzer``.
    """
    explicit = os.environ.get("ANALYZER_CONFIG_DIR")
    if explicit:
        return Path(explicit).expanduser() / ".env"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "analyzer" / ".env"


def _candidate_env_paths(dotenv_path: Optional[str]) -> List[Path]:
    """Return `.env` paths in the order they should be loaded.

    Earlier entries have higher priority because ``override=False``.
    The process environment is not returned here — it is already in
    ``os.environ`` and wins automatically.
    """
    paths: List[Path] = []

    # 1. Explicit caller-supplied path (or $ANALYZER_ENV_FILE).
    explicit = dotenv_path or os.environ.get("ANALYZER_ENV_FILE")
    if explicit:
        paths.append(Path(explicit).expanduser())

    # 2. Project .env — walk upward from CWD.
    if _DOTENV_AVAILABLE:
        found = _find_dotenv(usecwd=True)
        if found:
            paths.append(Path(found))

    # 3. User-global .env.
    paths.append(_user_global_env_path())

    # De-duplicate while preserving order; drop non-existent files.
    seen: set[str] = set()
    unique: List[Path] = []
    for p in paths:
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if p.is_file():
            unique.append(p)
    return unique


def _load_env(dotenv_path: Optional[str] = None) -> List[Path]:
    """Load analyzer ``.env`` cascade. Returns the list of files loaded.

    All layers are loaded with ``override=False`` so the process
    environment and earlier (higher-priority) files win.
    """
    if not _DOTENV_AVAILABLE:
        return []
    loaded: List[Path] = []
    for path in _candidate_env_paths(dotenv_path):
        _load_dotenv(path, override=False)
        loaded.append(path)
    return loaded


class Config:
    """Centralized configuration manager backed by environment variables."""

    def __init__(self, dotenv_path: Optional[str] = None):
        """Load the ``.env`` cascade and record which files were used.

        Parameters
        ----------
        dotenv_path:
            Optional extra ``.env`` path inserted at the top of the cascade
            (after the process environment but before project and user-global
            files). Environment variables already set are **not** overridden
            (``override=False``).
        """
        self.loaded_env_files: List[Path] = _load_env(dotenv_path)

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
