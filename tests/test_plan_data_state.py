"""Tests for ``plan-data``'s --state-in / --state-out flags.

We don't exercise the LLM here; we focus on argument resolution from
state-in. The full plan-data flow needs network/LLM and is covered by
integration tests.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from analyzer_tools.analysis.plan_data import main as plan_data
from analyzer_tools.state import empty_state, load_state, save_state, update_stage


def test_no_args_errors():
    runner = CliRunner()
    result = runner.invoke(plan_data, [])
    assert result.exit_code != 0
    assert "DATA_FILE" in result.output or "data_file" in result.output.lower()


def test_state_in_fills_data_and_context(tmp_path, monkeypatch):
    """state-in supplies reduction.partial_file / paths.context_file / paths.output_directory."""
    data_file = tmp_path / "REFL_226642_3_226644_partial.txt"
    data_file.write_text("# q i di\n0.01 1.0 0.01\n")
    context_file = tmp_path / "context.md"
    context_file.write_text("sample stack")
    output_root = tmp_path / "out"

    wstate = empty_state()
    update_stage(wstate, "reduction", partial_file=str(data_file))
    wstate["paths"]["context_file"] = str(context_file)
    wstate["paths"]["output_directory"] = str(output_root)
    state_path = tmp_path / "state.json"
    save_state(wstate, str(state_path))

    # Short-circuit the LLM: have call_planner_llm raise a known error so we
    # confirm argument resolution succeeded before reaching the LLM.
    import analyzer_tools.analysis.plan_data as mod

    def _boom(_):
        raise RuntimeError("LLM_SHORTCIRCUIT")

    monkeypatch.setattr(mod, "call_planner_llm", _boom)
    monkeypatch.setattr(mod, "read_header_lines", lambda p: "")
    monkeypatch.setattr(mod, "list_sibling_files", lambda p: [])
    monkeypatch.setattr(mod, "load_skills", lambda names: {})

    runner = CliRunner()
    result = runner.invoke(plan_data, ["--state-in", str(state_path)])
    # We expect to reach the LLM call (i.e. arg resolution worked) and see
    # the shortcut error bubble up via click's ClickException.
    assert "LLM_SHORTCIRCUIT" in result.output
    assert "DATA_FILE is required" not in result.output
    assert "CONTEXT_FILE is required" not in result.output


def test_state_in_missing_paths_errors(tmp_path):
    """state-in without reduction.partial_file -> clean UsageError."""
    wstate = empty_state()
    wstate["paths"]["output_directory"] = str(tmp_path / "out")
    state_path = tmp_path / "state.json"
    save_state(wstate, str(state_path))

    runner = CliRunner()
    result = runner.invoke(plan_data, ["--state-in", str(state_path)])
    assert result.exit_code != 0
    assert "DATA_FILE" in result.output or "data_file" in result.output.lower()


def test_state_out_writes_v1_state(tmp_path, monkeypatch):
    data_file = tmp_path / "data.txt"
    data_file.write_text("# q i di\n0.01 1.0 0.01\n")
    context_file = tmp_path / "context.md"
    context_file.write_text("sample")
    output_dir = tmp_path / "plan"

    import analyzer_tools.analysis.plan_data as mod

    fake_result = {
        "sequence_id": "Cu-D2O-226642",
        "sequence_number": 3,
        "sequence_complete": True,
        "create_model_ready": True,
        "config": {
            "model_name": "Cu-D2O-226642",
            "describe": "Cu on Ti on Si",
            "states": [{"name": "s1", "data": ["a.txt"]}],
            "metadata": {"perform_assembly": True},
        },
    }
    monkeypatch.setattr(mod, "call_planner_llm", lambda _: fake_result)
    monkeypatch.setattr(mod, "read_header_lines", lambda p: "")
    monkeypatch.setattr(mod, "list_sibling_files", lambda p: [])
    monkeypatch.setattr(mod, "load_skills", lambda names: {})
    monkeypatch.setattr(mod, "build_user_message", lambda **kw: "msg")

    state_out = tmp_path / "out.json"
    runner = CliRunner()
    result = runner.invoke(
        plan_data,
        [
            str(data_file),
            str(context_file),
            "--output-dir", str(output_dir),
            "--state-out", str(state_out),
        ],
    )
    assert result.exit_code == 0, result.output
    s = load_state(str(state_out))
    assert s["schema_version"] == "1"
    assert s["analysis"]["model_name"] == "Cu-D2O-226642"
    assert s["analysis"]["perform_assembly"] is True
    assert s["analysis"]["metadata"]["job_yaml"].endswith("job_Cu-D2O-226642.yaml")
    assert s["analysis"]["metadata"]["sequence_id"] == "Cu-D2O-226642"
