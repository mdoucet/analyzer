"""Sanity + drift checks for the vendored v1 workflow-state module.

``analyzer_tools/state.py`` is a verbatim copy of
``src/ndip_state/state.py`` from the ``ndip-workflows`` repo. The two files
must stay in sync — Galaxy tool XMLs there inline the same source. This
test enforces that when both repos are checked out side-by-side.
"""

from __future__ import annotations

import pathlib

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
VENDORED = ROOT / "analyzer_tools" / "state.py"
UPSTREAM_CANDIDATES = [
    ROOT.parent / "ndip-workflows" / "src" / "ndip_state" / "state.py",
]


def _find_upstream() -> pathlib.Path | None:
    for p in UPSTREAM_CANDIDATES:
        if p.is_file():
            return p
    return None


def test_vendored_state_importable():
    from analyzer_tools.state import (
        SCHEMA_VERSION,
        empty_state,
        load_state,
        save_state,
        update_stage,
    )
    assert SCHEMA_VERSION == "1"
    s = empty_state()
    assert s["schema_version"] == "1"
    assert s["reduction"] == {"success": None, "metadata": {}}


def test_vendored_state_roundtrip(tmp_path):
    from analyzer_tools.state import empty_state, load_state, save_state, update_stage

    s = empty_state()
    s["paths"]["event_file"] = "/a.h5"
    update_stage(s, "reduction", success=True, partial_file="/p.txt")
    p = tmp_path / "state.json"
    save_state(s, str(p))
    s2 = load_state(str(p))
    assert s2["paths"]["event_file"] == "/a.h5"
    assert s2["reduction"]["success"] is True
    assert s2["reduction"]["partial_file"] == "/p.txt"


def test_vendored_state_migrates_v0(tmp_path):
    """Old flat-key state files still load."""
    import json

    from analyzer_tools.state import load_state

    p = tmp_path / "v0.json"
    p.write_text(json.dumps({
        "event_file": "/a.h5",
        "template_file": "/t.xml",
        "output_directory": "/out",
    }))
    s = load_state(str(p))
    assert s["schema_version"] == "1"
    assert s["paths"]["event_file"] == "/a.h5"
    assert s["paths"]["template_file"] == "/t.xml"
    assert s["paths"]["output_directory"] == "/out"


def test_no_drift_against_ndip_workflows():
    """When ndip-workflows is checked out as a sibling, the two copies match."""
    upstream = _find_upstream()
    if upstream is None:
        pytest.skip("ndip-workflows sibling repo not found; cannot check drift")
    assert VENDORED.read_text().rstrip() == upstream.read_text().rstrip(), (
        f"{VENDORED} has drifted from {upstream} — re-sync the vendored copy."
    )
