"""
Neutron event reduction modules.

These modules require Mantid and lr_reduction to be installed.
They are optional dependencies of analyzer-tools::

    pip install analyzer-tools[reduction]

Public API
----------
- :func:`load_reduction` — load template, event data, and direct beam
- :func:`reduce_workspace` — reduce a single Mantid workspace to [Q, R, dR, dQ]
- :func:`save_reduction` — write a reduced array to a text file
- :func:`filter_events_by_intervals` — split events by EIS time intervals
"""


class MantidNotAvailableError(ImportError):
    """Raised when mantid or lr_reduction cannot be imported."""


_REQUIRED_PACKAGES = ("mantid", "lr_reduction")


def require_mantid():
    """Verify that Mantid and lr_reduction are importable.

    Raises
    ------
    MantidNotAvailableError
        If any required package is missing, with installation instructions.
    """
    import importlib.util

    missing = [pkg for pkg in _REQUIRED_PACKAGES if importlib.util.find_spec(pkg) is None]
    if missing:
        raise MantidNotAvailableError(
            f"Required packages not installed: {', '.join(missing)}. "
            "Install with:  pip install analyzer-tools[reduction]  "
            "or see https://download.mantidproject.org/"
        )


# Re-export the main public functions so users can write:
#   from analyzer_tools.reduction import load_reduction, reduce_workspace
def __getattr__(name):
    """Lazy-load public symbols to avoid importing mantid at package level."""
    _public = {
        "load_reduction": ".core",
        "reduce_workspace": ".core",
        "save_reduction": ".core",
        "filter_events_by_intervals": ".event_filter",
        "parse_iso_datetime": ".event_filter",
    }
    if name in _public:
        import importlib

        mod = importlib.import_module(_public[name], __package__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
