"""Tests for the analyzer pipeline orchestrator."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from analyzer_tools import pipeline as pl


SAMPLE_MD = """---
set_id: "218281"
hypothesis: "Copper layer thins over time."
---

Copper film on silicon, 100 mM LiTFSI in THF. Expected 50 Å Cu on 20 Å CuOx.
"""


def test_parse_sample_file(tmp_path: Path) -> None:
    sample = tmp_path / "sample.md"
    sample.write_text(SAMPLE_MD)
    spec = pl.parse_sample_file(sample)
    assert spec.set_id == "218281"
    assert spec.hypothesis and "thins" in spec.hypothesis
    assert "Copper film" in spec.description


def test_parse_sample_file_missing_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "bad.md"
    p.write_text("no frontmatter here")
    with pytest.raises(Exception):
        pl.parse_sample_file(p)


def test_detect_reduction_issues_partial_chi2() -> None:
    metrics = {
        "overlaps": [
            {"parts": [1, 2], "chi2": 1.1, "classification": "good"},
            {"parts": [2, 3], "chi2": 10.0, "classification": "poor"},
        ]
    }
    issues = pl.detect_reduction_issues(
        metrics, None, chi2_threshold=3.0, offset_threshold_deg=0.01
    )
    assert len(issues) == 1
    assert issues[0]["type"] == "partial_overlap_chi2"
    assert issues[0]["severity"] == "block"
    assert pl.should_halt(issues)


def test_detect_reduction_issues_theta_offset() -> None:
    theta = [{"run": "218281", "offset": 0.05}, {"run": "218282", "offset": 0.001}]
    issues = pl.detect_reduction_issues(
        None, theta, chi2_threshold=3.0, offset_threshold_deg=0.01
    )
    assert len(issues) == 1
    assert issues[0]["run"] == "218281"


def test_detect_reduction_issues_none() -> None:
    assert pl.detect_reduction_issues(None, None, chi2_threshold=3.0, offset_threshold_deg=0.01) == []


def test_write_reduction_batch_yaml(tmp_path: Path) -> None:
    path = tmp_path / "reduction_batch.yaml"
    pl.write_reduction_batch_yaml(
        path,
        "218281",
        [{"run": "218281", "offset": 0.05}, {"run": "218282", "offset": 0.02}],
    )
    data = yaml.safe_load(path.read_text())
    assert "jobs" in data
    assert len(data["jobs"]) == 2
    assert data["jobs"][0]["tool"] == "simple-reduction"
    # Must be dispatchable by analyzer-batch
    from analyzer_tools.batch import TOOL_COMMANDS

    assert "simple-reduction" in TOOL_COMMANDS


def test_write_reduction_issues_md(tmp_path: Path) -> None:
    path = tmp_path / "issues.md"
    issues = [
        {
            "type": "partial_overlap_chi2",
            "segments": [1, 2],
            "severity": "block",
            "chi2": 7.5,
            "threshold": 3.0,
            "detail": "Overlap between parts 1 and 2 has chi^2=7.50 (> 3.0).",
        }
    ]
    metrics = {"overlaps": [{"parts": [1, 2], "chi2": 7.5, "classification": "poor"}]}
    pl.write_reduction_issues_md(path, "218281", issues, metrics, None)
    content = path.read_text()
    assert "Reprocessing required" in content
    assert "218281" in content
    assert "reduction_batch.yaml" in content


def test_pipeline_state_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = pl.PipelineState(set_id="218281", completed_stages=["partial"])
    state.save(path)
    loaded = pl.PipelineState.load(path)
    assert loaded is not None
    assert loaded.set_id == "218281"
    assert loaded.completed_stages == ["partial"]


def test_cli_dry_run(tmp_path: Path) -> None:
    sample = tmp_path / "sample.md"
    sample.write_text(SAMPLE_MD)
    runner = CliRunner()
    result = runner.invoke(
        pl.main,
        [
            str(sample),
            "--data-dir", str(tmp_path),
            "--partial-dir", str(tmp_path),
            "--results-dir", str(tmp_path / "results"),
            "--reports-dir", str(tmp_path / "reports"),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Planned pipeline" in result.output
    assert "218281" in result.output


def test_pipeline_halts_on_reduction_issue(tmp_path: Path, monkeypatch) -> None:
    """Pipeline halts, writes reduction_issues.md + reduction_batch.yaml."""
    reports = tmp_path / "reports"
    results = tmp_path / "results"

    # Stub out partial assessment to return bad overlap.
    def fake_partial(spec, partial_dir, reports_dir, **kwargs):
        return {
            "set_id": spec.set_id,
            "chi2_threshold": 3.0,
            "overlaps": [{"parts": [1, 2], "chi2": 99.0, "classification": "poor"}],
            "worst_chi2": 99.0,
            "status": "poor",
        }

    monkeypatch.setattr(pl, "_run_partial_assessment", fake_partial)

    spec = pl.SampleSpec(set_id="218281", description="test")
    state = pl.run_pipeline(
        spec,
        data_dir=str(tmp_path),
        partial_dir=str(tmp_path),
        results_root=str(results),
        reports_root=str(reports),
    )
    assert state.status == "needs-reprocessing"
    report_dir = reports / "sample_218281"
    assert (report_dir / "reduction_issues.md").exists()
    assert (report_dir / "reduction_batch.yaml").exists()
    assert (report_dir / "sample_218281.md").exists()
    sample_json = json.loads((report_dir / "sample_218281.json").read_text())
    assert sample_json["state"]["status"] == "needs-reprocessing"


def test_pipeline_proceeds_when_gate_disabled(tmp_path: Path, monkeypatch) -> None:
    """With --no-reduction-gate, bad overlap doesn't halt; fit stage is attempted."""
    reports = tmp_path / "reports"
    results = tmp_path / "results"

    def fake_partial(spec, partial_dir, reports_dir, **kwargs):
        return {
            "set_id": spec.set_id,
            "overlaps": [{"parts": [1, 2], "chi2": 99.0, "classification": "poor"}],
            "worst_chi2": 99.0,
            "status": "poor",
        }

    called = {}

    def fake_aure(spec, data_file, results_dir, **kwargs):
        called["aure"] = True
        os.makedirs(results_dir, exist_ok=True)
        return 0

    def fake_assess(spec, results_dir, reports_dir, **kwargs):
        called["assess"] = True
        return {"results_dir": results_dir, "report": "r.md", "aure_evaluation": None}

    monkeypatch.setattr(pl, "_run_partial_assessment", fake_partial)
    monkeypatch.setattr(pl, "_run_aure_analyze", fake_aure)
    monkeypatch.setattr(pl, "_run_result_assessment", fake_assess)
    monkeypatch.setattr(pl.shutil, "which", lambda _: "/usr/bin/aure")

    spec = pl.SampleSpec(set_id="218281")
    state = pl.run_pipeline(
        spec,
        data_dir=str(tmp_path),
        partial_dir=str(tmp_path),
        results_root=str(results),
        reports_root=str(reports),
        reduction_gate=False,
    )
    assert state.status == "ok"
    assert called.get("aure") is True
    assert called.get("assess") is True


def test_pipeline_failed_when_aure_missing(tmp_path: Path, monkeypatch) -> None:
    reports = tmp_path / "reports"
    results = tmp_path / "results"
    monkeypatch.setattr(pl, "_run_partial_assessment", lambda *a, **k: None)
    monkeypatch.setattr(pl.shutil, "which", lambda _: None)

    spec = pl.SampleSpec(set_id="218281")
    state = pl.run_pipeline(
        spec,
        data_dir=str(tmp_path),
        partial_dir=str(tmp_path),
        results_root=str(results),
        reports_root=str(reports),
    )
    assert state.status == "failed"
    assert "error" in state.stage_outputs.get("fit", {})
