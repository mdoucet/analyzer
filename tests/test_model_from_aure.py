"""Tests for analyzer_tools.analysis.model_from_aure."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from analyzer_tools.analysis import model_from_aure as mfa


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cu_thf_definition() -> dict:
    """A representative AuRE ModelDefinition (Cu/Ti on Si, back reflection)."""
    return {
        "substrate": {"name": "Silicon", "sld": 2.07, "roughness": 3.0},
        "ambient": {
            "name": "D2O",
            "sld": 6.36,
            "sld_min": 5.36,
            "sld_max": 7.36,
        },
        "layers": [
            {
                "name": "Titanium",
                "sld": -1.95,
                "sld_min": -5.0,
                "sld_max": 1.0,
                "thickness": 50.0,
                "thickness_min": 25.0,
                "thickness_max": 100.0,
                "roughness": 5.0,
                "roughness_min": 5.0,
                "roughness_max": 30.0,
            },
            {
                "name": "Copper",
                "sld": 6.55,
                "sld_min": 4.5,
                "sld_max": 8.5,
                "thickness": 500.0,
                "thickness_min": 250.0,
                "thickness_max": 1000.0,
                "roughness": 5.0,
                "roughness_min": 5.0,
                "roughness_max": 30.0,
            },
        ],
        "back_reflection": True,
        "intensity": {"value": 1.0, "min": 0.7, "max": 1.1, "fixed": False},
        "dq_is_fwhm": True,
    }


# ---------------------------------------------------------------------------
# definition_to_script
# ---------------------------------------------------------------------------


def test_script_is_valid_python(cu_thf_definition: dict) -> None:
    script = mfa.definition_to_script(cu_thf_definition, model_name="cu_thf")
    ast.parse(script)


def test_script_defines_create_fit_experiment(cu_thf_definition: dict) -> None:
    script = mfa.definition_to_script(cu_thf_definition)
    tree = ast.parse(script)
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "create_fit_experiment" in funcs

    # Signature must be (q, dq, data, errors)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    arg_names = [a.arg for a in fn.args.args]
    assert arg_names == ["q", "dq", "data", "errors"]


def test_script_contains_expected_materials(cu_thf_definition: dict) -> None:
    script = mfa.definition_to_script(cu_thf_definition)
    assert "'Silicon'" in script
    assert "'D2O'" in script
    assert "'Copper'" in script
    assert "'Titanium'" in script
    # FWHM → sigma conversion for dq
    assert "dq = dq / 2.355" in script
    # Ranges from the definition should appear
    assert "250.0, 1000.0" in script  # Copper thickness range
    assert "-5.0, 1.0" in script  # Titanium SLD range


def test_script_executes_and_builds_experiment(cu_thf_definition: dict) -> None:
    """Full round-trip: generate → exec → call create_fit_experiment → Experiment."""
    import numpy as np

    script = mfa.definition_to_script(cu_thf_definition)
    namespace: dict = {}
    exec(compile(script, "<generated>", "exec"), namespace)  # noqa: S102
    fn = namespace["create_fit_experiment"]

    n = 50
    q = np.linspace(0.008, 0.2, n)
    dq = q * 0.03
    r = np.exp(-q * 20.0)
    dr = r * 0.05

    experiment = fn(q.copy(), dq.copy(), r.copy(), dr.copy())
    # Should behave like a refl1d Experiment
    assert hasattr(experiment, "reflectivity")
    qout, rout = experiment.reflectivity()
    assert len(qout) == n
    assert len(rout) == n


# ---------------------------------------------------------------------------
# write_model_script / load_definition
# ---------------------------------------------------------------------------


def test_load_and_write_roundtrip(tmp_path: Path, cu_thf_definition: dict) -> None:
    json_path = tmp_path / "defn.json"
    json_path.write_text(json.dumps(cu_thf_definition))

    loaded = mfa.load_definition(json_path)
    assert loaded == cu_thf_definition

    out = tmp_path / "models" / "cu_thf.py"
    written = mfa.write_model_script(loaded, out, model_name="cu_thf")
    assert Path(written).exists()
    content = Path(written).read_text()
    assert "create_fit_experiment" in content


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_from_json(tmp_path: Path, cu_thf_definition: dict) -> None:
    json_path = tmp_path / "cu_thf.json"
    json_path.write_text(json.dumps(cu_thf_definition))
    out_path = tmp_path / "models" / "cu_thf.py"

    runner = CliRunner()
    result = runner.invoke(mfa.main, [str(json_path), "--out", str(out_path)])
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    assert "create_fit_experiment" in out_path.read_text()


def test_cli_description_mode_calls_aure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cu_thf_definition: dict) -> None:
    """CLI --from-description path invokes invoke_aure_modeling and writes a script."""

    def fake_invoke(
        sample_description: str,
        data_file: str,
        *,
        output_dir: str,
        **_: object,
    ) -> dict:
        assert "Cu" in sample_description
        assert os.path.exists(data_file)
        return cu_thf_definition

    monkeypatch.setattr(mfa, "invoke_aure_modeling", fake_invoke)

    data_file = tmp_path / "data.txt"
    data_file.write_text("0.01 0.1 0.01 0.001\n")
    out_path = tmp_path / "models" / "cu_thf.py"

    runner = CliRunner()
    result = runner.invoke(
        mfa.main,
        [
            "Cu/Ti on Si in dTHF",
            str(data_file),
            "--from-description",
            "--out",
            str(out_path),
            "--aure-output",
            str(tmp_path / "aure_work"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    assert "create_fit_experiment" in out_path.read_text()


# ---------------------------------------------------------------------------
# _find_initial_definition
# ---------------------------------------------------------------------------


def test_find_initial_definition(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    a = models / "003_model_initial.json"
    a.write_text("{}")
    b = models / "005_model_initial.json"
    b.write_text("{}")

    found = mfa._find_initial_definition(tmp_path)
    assert found == str(b)
