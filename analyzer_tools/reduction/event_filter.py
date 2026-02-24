"""
EIS interval parsing and Mantid event filtering.

Converts EIS measurement interval JSON data into Mantid filter tables
and splits an event workspace by those intervals.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interval parsing
# ---------------------------------------------------------------------------

def parse_iso_datetime(iso_string: str) -> datetime:
    """Parse an ISO-8601 datetime string.

    Supports formats with and without fractional seconds.

    Parameters
    ----------
    iso_string : str
        e.g. ``"2025-06-15T14:30:00.123"`` or ``"2025-06-15T14:30:00"``.

    Returns
    -------
    datetime.datetime

    Raises
    ------
    ValueError
        If the string does not match any known format.
    """
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(iso_string, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse datetime: {iso_string}")


def _interval_label(interval: dict, index: int) -> str:
    """Extract a human-readable label from an interval dict."""
    return interval.get("label", interval.get("filename", f"interval_{index}"))


def convert_intervals(intervals: list[dict], *, tz_offset_hours: float = 5.0) -> list[tuple[str, int, int]]:
    """Convert EIS interval dicts to ``(label, start_ns, end_ns)`` tuples.

    Parameters
    ----------
    intervals : list[dict]
        Each dict must contain ``"start"`` and ``"end"`` ISO-8601 strings.
        Optional ``"label"`` / ``"filename"`` keys are used for display.
    tz_offset_hours : float
        Timezone offset in hours from UTC for EIS timestamps
        (default 5.0 for EST, since EIS files omit timezone info).

    Returns
    -------
    list[tuple[str, int, int]]
        ``(label, start_nanoseconds, end_nanoseconds)`` in Mantid
        absolute time.
    """
    from . import require_mantid
    require_mantid()

    import mantid.kernel as mk

    tz_delta_ns = int(tz_offset_hours * 3_600 * 1_000_000_000)
    logger.info("Timezone offset: %+.1f h (%d ns)", tz_offset_hours, tz_delta_ns)

    result = []
    for i, interval in enumerate(intervals):
        label = _interval_label(interval, i)
        start_ns = mk.DateAndTime(parse_iso_datetime(interval["start"]).isoformat()).totalNanoseconds() + tz_delta_ns
        end_ns = mk.DateAndTime(parse_iso_datetime(interval["end"]).isoformat()).totalNanoseconds() + tz_delta_ns
        duration_s = (end_ns - start_ns) / 1_000_000_000
        interval_type = interval.get("interval_type", "eis")
        logger.info("  %s (%s, %.1fs)", label, interval_type, duration_s)
        result.append((label, start_ns, end_ns))

    return result


# ---------------------------------------------------------------------------
# Event filtering
# ---------------------------------------------------------------------------

def filter_events_by_intervals(
    sample_ws: Any,
    intervals_abs: list[tuple[str, int, int]],
) -> list[tuple[str, Any]]:
    """Filter events in *sample_ws* by absolute time intervals.

    Creates a Mantid ``SplitterWorkspace`` from *intervals_abs*, runs
    ``FilterEvents``, and returns the resulting workspaces paired with
    their labels.

    Parameters
    ----------
    sample_ws : mantid EventWorkspace
        The loaded sample event workspace.
    intervals_abs : list[tuple[str, int, int]]
        As returned by :func:`convert_intervals`.

    Returns
    -------
    list[tuple[str, mantid EventWorkspace]]
        ``(label, filtered_workspace)`` pairs, one per interval.
    """
    import mantid.simpleapi as api
    from mantid.api import mtd

    logger.info("Creating filter table for %d intervals", len(intervals_abs))

    filter_table, _info = api.GenerateEventsFilter(
        InputWorkspace=sample_ws,
        OutputWorkspace="eis_filter",
        InformationWorkspace="eis_info",
        TimeInterval=6000,
    )
    filter_table.setRowCount(0)

    for i, (_label, start_ns, end_ns) in enumerate(intervals_abs):
        filter_table.addRow((start_ns, end_ns, i))

    logger.info("Filtering events by EIS intervals")
    api.FilterEvents(
        InputWorkspace=sample_ws,
        SplitterWorkspace="eis_filter",
        GroupWorkspaces=True,
        OutputWorkspaceBaseName="eis_measurement",
        FilterByPulseTime=True,
        OutputWorkspaceIndexedFrom1=False,
        CorrectionToSample="None",
        SpectrumWithoutDetector="Skip",
        SplitSampleLogs=False,
        OutputTOFCorrectionWorkspace="mock",
        RelativeTime=False,
    )

    wsgroup = mtd["eis_measurement"]
    ws_names = wsgroup.getNames()
    logger.info("Created %d filtered workspaces: %s", len(ws_names), ", ".join(ws_names))

    return [(intervals_abs[i][0], mtd[name]) for i, name in enumerate(ws_names)]
