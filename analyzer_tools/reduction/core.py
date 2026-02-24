"""
Core reduction engine for neutron event data.

Provides reusable functions for loading data, reducing workspaces,
and saving results.  All Mantid / lr_reduction imports are deferred
to function bodies so that importing this module never triggers a
heavy Mantid initialisation.

Typical usage::

    from analyzer_tools.reduction.core import load_reduction, reduce_workspace, save_reduction

    setup = load_reduction("template.xml", "REF_L_12345.nxs.h5")
    result = reduce_workspace(setup.sample_ws, setup.template_data, ws_db=setup.direct_beam_ws)
    save_reduction(result, "output.txt")
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class ReductionSetup:
    """Holds the loaded artefacts needed for a reduction.

    Attributes
    ----------
    template_data : object
        The parsed lr_reduction template.
    sample_ws : object
        Mantid workspace with the sample event data.
    direct_beam_ws : object
        Mantid workspace with the direct beam data.
    run_number : int
        Run number extracted from the sample workspace metadata.
    duration : float
        Run duration in seconds (0 if unavailable).
    """

    template_data: Any
    sample_ws: Any
    direct_beam_ws: Any
    run_number: int = 0
    duration: float = 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_reduction(
    template_path: str,
    event_file: str,
    *,
    scan_index: int = 1,
    theta_offset: float = 0.0,
) -> ReductionSetup:
    """Load a reduction template, sample events, and direct beam.

    This is the common setup shared by every reduction workflow.
    Dead-time corrections are applied to both the sample and direct beam
    workspaces if the template requests them, then disabled in the
    template so downstream code does not re-apply them.

    Parameters
    ----------
    template_path : str
        Path to the lr_reduction template XML file.
    event_file : str
        Path to the neutron event NeXus/HDF5 file.
    scan_index : int
        Scan index within the template (default 1).
    theta_offset : float
        Theta offset to apply (default 0.0).

    Returns
    -------
    ReductionSetup
        Container with every artefact needed for reduction.
    """
    from . import require_mantid
    require_mantid()

    import mantid
    import mantid.simpleapi as api
    from lr_reduction import template
    from lr_reduction.event_reduction import apply_dead_time_correction

    mantid.kernel.config.setLogLevel(3)

    # Template
    logger.info("Loading template: %s (scan_index=%d)", template_path, scan_index)
    template_data = template.read_template(template_path, scan_index)

    if theta_offset:
        logger.info("Applying theta offset: %s", theta_offset)
        template_data.angle_offset = theta_offset

    # Sample events
    logger.info("Loading event data: %s", event_file)
    sample_ws = api.LoadEventNexus(event_file)

    run_number = _get_run_property(sample_ws, "run_number", default=0)
    duration = _get_run_property(sample_ws, "duration", default=0.0)

    if template_data.dead_time:
        logger.info("Applying dead-time correction to sample data")
        apply_dead_time_correction(sample_ws, template_data)

    # Direct beam
    logger.info("Loading direct beam: REF_L_%s", template_data.norm_file)
    direct_beam_ws = api.LoadEventNexus(f"REF_L_{template_data.norm_file}")

    if template_data.dead_time:
        logger.info("Applying dead-time correction to direct beam")
        apply_dead_time_correction(direct_beam_ws, template_data)

    # Disable dead-time in template so it is not re-applied during reduction
    template_data.dead_time = False

    return ReductionSetup(
        template_data=template_data,
        sample_ws=sample_ws,
        direct_beam_ws=direct_beam_ws,
        run_number=int(run_number),
        duration=float(duration),
    )


def reduce_workspace(ws, template_data, *, ws_db=None) -> np.ndarray:
    """Reduce a single Mantid workspace to reflectivity data.

    Parameters
    ----------
    ws : mantid EventWorkspace
        The workspace to reduce.
    template_data : lr_reduction template
        Parsed reduction template.
    ws_db : mantid EventWorkspace, optional
        Direct beam workspace for normalisation.

    Returns
    -------
    numpy.ndarray
        Shape ``(4, N)`` array of ``[Q, R, dR, dQ]``.

    Raises
    ------
    RuntimeError
        If the lr_reduction processing fails.
    """
    from lr_reduction import template
    from lr_reduction.event_reduction import compute_resolution

    raw = template.process_from_template_ws(ws, template_data, ws_db=ws_db)

    dq_slope = compute_resolution(ws)
    dq = dq_slope * raw[0]

    return np.asarray([raw[0], raw[1], raw[2], dq])


def save_reduction(data: np.ndarray, output_path: str) -> str:
    """Write a reduced ``[Q, R, dR, dQ]`` array to a text file.

    Parameters
    ----------
    data : numpy.ndarray
        Shape ``(4, N)`` array as returned by :func:`reduce_workspace`.
    output_path : str
        Destination file path.  Parent directories are created if needed.

    Returns
    -------
    str
        The absolute path of the written file.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    np.savetxt(output_path, data.T)
    logger.info("Saved reduced data: %s", output_path)
    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_run_property(ws, name: str, *, default=None):
    """Safely extract a scalar property from a workspace run log."""
    try:
        return ws.getRun()[name].value
    except Exception:
        logger.debug("Could not read run property %r, using default %r", name, default)
        return default
