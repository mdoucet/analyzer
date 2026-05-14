"""Tests for ``analyze-sample``'s --state-in / --state-out flags.

We avoid running the actual pipeline (which needs Mantid/refl1d/lr_reduction).
The tests target the argument resolution layer and the v1 state emission
by stubbing ``run_pipeline``.
"""

from __future__ import annotations

import os

import pytest
from click.testing import CliRunner

from analyzer_tools.pipeline import main as analyze_sample
from analyzer_tools.state import empty_state, load_state, save_state, update_stage


_MINIMAL_JOB_YAML = """\
model_name: test_model
describe: synthetic
states:
  - name: state_0
    data: ["data_a.txt"]
"""


def _patch_pipeline_runtime(monkeypatch, status: str = "ok"):
    """Stub out everything past argument resolution.

    Returns the fake PipelineState that ``run_pipeline`` will yield.
    """
    import analyzer_tools.pipeline as mod

    class _FakeState:
        def __init__(self):
            self.status = status
            self.completed_stages = ["partial", "fit"]

    fake = _FakeState()
    monkeypatch.setattr(mod, "run_pipeline", lambda *a, **kw: fake)
    return fake


def test_no_config_no_state_in_errors():
    runner = CliRunner()
    result = runner.invoke(analyze_sample, [])
    assert result.exit_code != 0
    assert "CONFIG" in result.output


def test_state_in_supplies_config(tmp_path, monkeypatch):
    job_yaml = tmp_path / "job_test.yaml"
    job_yaml.write_text(_MINIMAL_JOB_YAML)
    output_root = tmp_path / "out"

    wstate = empty_state()
    wstate["paths"]["output_directory"] = str(output_root)
    update_stage(wstate, "analysis", metadata={"job_yaml": str(job_yaml)})
    state_path = tmp_path / "state.json"
    save_state(wstate, str(state_path))

    _patch_pipeline_runtime(monkeypatch, status="ok")

    runner = CliRunner()
    result = runner.invoke(analyze_sample, ["--state-in", str(state_path)])
    assert result.exit_code == 0, result.output
    assert "Pipeline status: ok" in result.output


def test_state_out_records_success(tmp_path, monkeypatch):
    job_yaml = tmp_path / "job_test.yaml"
    job_yaml.write_text(_MINIMAL_JOB_YAML)
    results_dir = tmp_path / "results"
    (results_dir / "test_model").mkdir(parents=True)
    problem_json = results_dir / "test_model" / "problem.json"
    problem_json.write_text("{}")

    _patch_pipeline_runtime(monkeypatch, status="ok")

    state_out = tmp_path / "out.json"
    runner = CliRunner()
    result = runner.invoke(
        analyze_sample,
        [
            str(job_yaml),
            "--results-dir", str(results_dir),
            "--reports-dir", str(tmp_path / "reports"),
            "--state-out", str(state_out),
        ],
    )
    assert result.exit_code == 0, result.output

    s = load_state(str(state_out))
    assert s["analysis"]["success"] is True
    assert s["analysis"]["model_name"] == "test_model"
    assert s["analysis"]["problem_json"] == str(problem_json.resolve())
    assert s["analysis"]["metadata"]["pipeline_status"] == "ok"
    assert s["errors"] == []


def test_state_out_records_failure(tmp_path, monkeypatch):
    job_yaml = tmp_path / "job_test.yaml"
    job_yaml.write_text(_MINIMAL_JOB_YAML)

    _patch_pipeline_runtime(monkeypatch, status="failed")

    state_out = tmp_path / "out.json"
    runner = CliRunner()
    result = runner.invoke(
        analyze_sample,
        [
            str(job_yaml),
            "--results-dir", str(tmp_path / "results"),
            "--reports-dir", str(tmp_path / "reports"),
            "--state-out", str(state_out),
        ],
    )
    # exit_code 2 on failure (per pipeline.main)
    assert result.exit_code == 2

    s = load_state(str(state_out))
    assert s["analysis"]["success"] is False
    assert s["analysis"]["metadata"]["pipeline_status"] == "failed"
    assert s["errors"][0]["stage"] == "analysis"


def test_state_in_fills_results_and_reports_dirs(tmp_path, monkeypatch):
    """state.paths.output_directory -> results=<od>/results, reports=<od>/reports."""
    job_yaml = tmp_path / "job_test.yaml"
    job_yaml.write_text(_MINIMAL_JOB_YAML)
    output_root = tmp_path / "out"

    wstate = empty_state()
    wstate["paths"]["output_directory"] = str(output_root)
    update_stage(wstate, "analysis", metadata={"job_yaml": str(job_yaml)})
    state_path = tmp_path / "state.json"
    save_state(wstate, str(state_path))

    captured = {}

    def _fake_run(spec, **kw):
        captured["results_root"] = kw.get("results_root")
        captured["reports_root"] = kw.get("reports_root")
        class _S:
            status = "ok"
            completed_stages = []
        return _S()

    import analyzer_tools.pipeline as mod
    monkeypatch.setattr(mod, "run_pipeline", _fake_run)

    runner = CliRunner()
    result = runner.invoke(analyze_sample, ["--state-in", str(state_path)])
    assert result.exit_code == 0, result.output
    assert captured["results_root"] == os.path.join(str(output_root), "results")
    assert captured["reports_root"] == os.path.join(str(output_root), "reports")
