"""Tests for the AuRE-wrapper behaviour of run-fit (Phase 3)."""

from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

from analyzer_tools.analysis import run_fit


def _write_config(tmp: Path) -> None:
    """Minimal config.ini for the CLI."""
    (tmp / "config.ini").write_text(
        "[paths]\n"
        "combined_data_dir = data/combined\n"
        "partial_data_dir = data/partial\n"
        "results_dir = results\n"
        "reports_dir = reports\n"
        "models_dir = models\n"
        "combined_data_template = REFL_{set_id}_combined_data_auto.txt\n"
    )


def test_build_aure_command_basic() -> None:
    cmd = run_fit.build_aure_command(
        data_file="/tmp/data.txt",
        sample_description="Cu on Si",
        output_dir="/tmp/out",
        max_refinements=3,
    )
    assert cmd[:2] == ["aure", "analyze"]
    assert "/tmp/data.txt" in cmd
    assert "Cu on Si" in cmd
    assert "-o" in cmd and "/tmp/out" in cmd
    assert "-m" in cmd and "3" in cmd


def test_build_aure_command_extra_data() -> None:
    cmd = run_fit.build_aure_command(
        data_file="a.dat",
        sample_description="desc",
        output_dir="out",
        extra_data=["b.dat", "c.dat"],
    )
    assert cmd.count("-d") == 2
    assert "b.dat" in cmd and "c.dat" in cmd


def test_run_fit_cli_dry_run_prints_aure_command(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path)
    data_dir = tmp_path / "data" / "combined"
    data_dir.mkdir(parents=True)
    data_file = data_dir / "REFL_218281_combined_data_auto.txt"
    data_file.write_text("# hdr\n0.01 0.1 0.01 0.001\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        run_fit.main,
        ["218281", "cu_thf", "-d", "Cu/Ti on Si in dTHF", "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "aure analyze" in result.output
    assert "Cu/Ti on Si in dTHF" in result.output
    # Output dir argument must mention set_id + model name
    assert "results/218281_cu_thf" in result.output or os.path.join("results", "218281_cu_thf") in result.output


def test_sample_description_from_file(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path)
    data_dir = tmp_path / "data" / "combined"
    data_dir.mkdir(parents=True)
    (data_dir / "REFL_1_combined_data_auto.txt").write_text("x\n")
    desc = tmp_path / "sample.md"
    desc.write_text("50 nm Cu on Si")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        run_fit.main,
        ["1", "dummy", "-d", str(desc), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "50 nm Cu on Si" in result.output
