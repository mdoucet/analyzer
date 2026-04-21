"""Tests for analyzer_tools.analysis.model_generator."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List

import pytest
from click.testing import CliRunner

from analyzer_tools.analysis import create_model as cm
from analyzer_tools.analysis import model_generator as mg


SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def model_spec_dict() -> Dict[str, Any]:
    """Stable spec for a Cu/Ti on Si in D2O sample."""
    return {
        "ambient": {
            "name": "D2O",
            "sld": 6.19,
            "sld_min": 5.69,
            "sld_max": 6.69,
            "roughness": 10.0,
            "roughness_min": 1.0,
            "roughness_max": 25.0,
        },
        "substrate": {
            "name": "Si",
            "sld": 2.07,
            "roughness_min": 0.0,
            "roughness_max": 15.0,
        },
        "layers": [
            {
                "name": "CuOx",
                "sld": 5.0,
                "thickness": 30.0,
                "roughness": 10.0,
                "thickness_min": 5.0,
                "thickness_max": 200.0,
                "sld_min": 3.0,
                "sld_max": 7.0,
                "roughness_min": 5.0,
                "roughness_max": 30.0,
            },
            {
                "name": "Cu",
                "sld": 6.4,
                "thickness": 500.0,
                "roughness": 5.0,
                "thickness_min": 250.0,
                "thickness_max": 1000.0,
                "sld_min": 5.0,
                "sld_max": 7.5,
                "roughness_min": 1.0,
                "roughness_max": 12.0,
            },
            {
                "name": "Ti",
                "sld": -1.95,
                "thickness": 35.0,
                "roughness": 5.0,
                "thickness_min": 15.0,
                "thickness_max": 60.0,
                "sld_min": -5.0,
                "sld_max": 1.0,
                "roughness_min": 5.0,
                "roughness_max": 30.0,
            },
        ],
        "intensity": {"value": 1.0, "min": 0.95, "max": 1.05},
        "back_reflection": False,
        "shared_parameters": [
            "Cu.material.rho",
            "Cu.interface",
            "Ti.thickness",
            "Ti.material.rho",
            "Ti.interface",
        ],
    }


@pytest.fixture
def model_spec(model_spec_dict: Dict[str, Any]) -> mg.ModelSpec:
    return mg.model_spec_from_dict(model_spec_dict)


# ---------------------------------------------------------------------------
# detect_case
# ---------------------------------------------------------------------------


def test_detect_case_single_combined(tmp_path: Path) -> None:
    f = tmp_path / "REFL_218281_combined_data_auto.txt"
    f.touch()
    assert mg.detect_case([f]) == mg.CASE_1


def test_detect_case_partial_set(tmp_path: Path) -> None:
    files = [
        tmp_path / "REFL_218281_1_218281_partial.txt",
        tmp_path / "REFL_218281_2_218282_partial.txt",
        tmp_path / "REFL_218281_3_218283_partial.txt",
    ]
    for f in files:
        f.touch()
    assert mg.detect_case(files) == mg.CASE_2


def test_detect_case_multiple_combined(tmp_path: Path) -> None:
    files = [
        tmp_path / "REFL_226642_combined_data_auto.txt",
        tmp_path / "REFL_226652_combined_data_auto.txt",
    ]
    for f in files:
        f.touch()
    assert mg.detect_case(files) == mg.CASE_3


def test_detect_case_rejects_mixed(tmp_path: Path) -> None:
    a = tmp_path / "REFL_218281_combined_data_auto.txt"
    b = tmp_path / "REFL_218281_1_218281_partial.txt"
    a.touch()
    b.touch()
    with pytest.raises(ValueError, match="Mixing"):
        mg.detect_case([a, b])


def test_detect_case_partial_multiple_sets_rejected(tmp_path: Path) -> None:
    a = tmp_path / "REFL_218281_1_218281_partial.txt"
    b = tmp_path / "REFL_218500_1_218500_partial.txt"
    a.touch()
    b.touch()
    with pytest.raises(ValueError, match="multiple set_ids"):
        mg.detect_case([a, b])


def test_detect_case_single_partial_rejected(tmp_path: Path) -> None:
    a = tmp_path / "REFL_218281_1_218281_partial.txt"
    a.touch()
    with pytest.raises(ValueError, match="at least two"):
        mg.detect_case([a])


# ---------------------------------------------------------------------------
# parse_refl_header
# ---------------------------------------------------------------------------


def test_parse_refl_header_combined_has_three_runs() -> None:
    header = mg.parse_refl_header(
        SAMPLE_DATA_DIR / "REFL_218281_combined_data_auto.txt"
    )
    assert header["experiment"] == "IPTS-34347"
    assert header["run"] == "218281"
    assert header["theta_offset"] == 0.0
    assert len(header["runs"]) == 3
    two_thetas = [r["two_theta"] for r in header["runs"]]
    assert two_thetas[0] == pytest.approx(0.899996)
    assert header["runs"][0]["theta"] == pytest.approx(0.899996 / 2)


def test_parse_refl_header_partial_has_one_run() -> None:
    header = mg.parse_refl_header(
        SAMPLE_DATA_DIR / "partial" / "REFL_218281_1_218281_partial.txt"
    )
    assert len(header["runs"]) == 1
    assert header["runs"][0]["two_theta"] == pytest.approx(0.899996)


# ---------------------------------------------------------------------------
# Rendering (parse as Python, inspect content)
# ---------------------------------------------------------------------------


def test_render_case1_is_valid_python_with_qprobe(
    model_spec: mg.ModelSpec, tmp_path: Path
) -> None:
    data_file = tmp_path / "REFL_218281_combined_data_auto.txt"
    script = mg.render_case1_script(model_spec, data_file, model_name="cu_thf")
    ast.parse(script)
    assert "QProbe" in script
    assert "create_fit_experiment" in script
    assert "FitProblem(experiment)" in script
    assert "make_probe" not in script


def test_render_case2_uses_make_probe(model_spec: mg.ModelSpec) -> None:
    files = [f"REFL_218281_{i}_21828{i}_partial.txt" for i in range(1, 4)]
    thetas = [0.45, 1.2, 3.5]
    script = mg.render_case2_script(
        model_spec, files, thetas, model_name="cu_thf_partial"
    )
    ast.parse(script)
    assert "from refl1d.probe import make_probe" in script
    assert "create_probe(data_file, theta)" in script
    assert "create_sample()" in script
    # Three probes / experiments, one shared sample
    assert "probe1 = create_probe(data_file1, theta=0.45)" in script
    assert "probe3 = create_probe(data_file3, theta=3.5)" in script
    assert "experiment3 = Experiment(probe=probe3, sample=sample)" in script


def test_render_case3_emits_constraints_and_list_fitproblem(
    model_spec: mg.ModelSpec,
) -> None:
    files = [
        "REFL_226642_combined_data_auto.txt",
        "REFL_226652_combined_data_auto.txt",
    ]
    script = mg.render_case3_script(model_spec, files, model_name="corefine")
    ast.parse(script)
    assert "FitProblem([experiment, experiment2])" in script
    # Constraints tie shared parameters from experiment2 to experiment
    assert (
        'experiment2.sample[\'Cu\'].material.rho = '
        'experiment.sample[\'Cu\'].material.rho' in script
    )
    assert (
        'experiment2.sample[\'Ti\'].thickness = '
        'experiment.sample[\'Ti\'].thickness' in script
    )
    # Cu.material.rho IS shared; it should NOT be freely re-ranged on experiment2.
    # Intensity should remain per-experiment (each experiment has its own probe).
    assert "create_fit_experiment" in script


# ---------------------------------------------------------------------------
# LLM JSON parsing / retry logic
# ---------------------------------------------------------------------------


class _FakeLLMReply:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    """Minimal LangChain-style chat model stub."""

    def __init__(self, replies: List[str]) -> None:
        self._replies = list(replies)
        self.calls: List[List[Dict[str, str]]] = []

    def invoke(self, messages: List[Dict[str, str]]):
        self.calls.append(list(messages))
        return _FakeLLMReply(self._replies.pop(0))


def test_call_llm_parses_plain_json(model_spec_dict: Dict[str, Any]) -> None:
    import json as _json

    llm = _FakeLLM([_json.dumps(model_spec_dict)])
    spec = mg.call_llm_for_model_spec([{"role": "user", "content": "x"}], llm=llm)
    assert spec.layers[0].name == "CuOx"
    assert spec.shared_parameters[0] == "Cu.material.rho"
    assert len(llm.calls) == 1


def test_call_llm_parses_fenced_json(model_spec_dict: Dict[str, Any]) -> None:
    import json as _json

    fenced = "```json\n" + _json.dumps(model_spec_dict) + "\n```"
    llm = _FakeLLM([fenced])
    spec = mg.call_llm_for_model_spec([{"role": "user", "content": "x"}], llm=llm)
    assert spec.ambient.name == "D2O"


def test_call_llm_retries_once_then_succeeds(
    model_spec_dict: Dict[str, Any],
) -> None:
    import json as _json

    llm = _FakeLLM(["not JSON at all", _json.dumps(model_spec_dict)])
    spec = mg.call_llm_for_model_spec([{"role": "user", "content": "x"}], llm=llm)
    assert spec.layers[0].name == "CuOx"
    # Two invocations — the second one carried the error-feedback message.
    assert len(llm.calls) == 2
    last_user = llm.calls[1][-1]
    assert last_user["role"] == "user"
    assert "could not be parsed" in last_user["content"]


def test_call_llm_gives_up_after_one_retry() -> None:
    llm = _FakeLLM(["not JSON", "still not JSON"])
    with pytest.raises(mg.LLMResponseError):
        mg.call_llm_for_model_spec([{"role": "user", "content": "x"}], llm=llm)
    assert len(llm.calls) == 2


# ---------------------------------------------------------------------------
# CLI (Mode B)
# ---------------------------------------------------------------------------


def test_cli_mode_b_calls_llm_and_writes_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_spec_dict: Dict[str, Any],
) -> None:
    """Mode B: --describe + --data → generate_model_script → file written."""
    # Copy a sample file into tmp so the CLI can read its header.
    src = SAMPLE_DATA_DIR / "REFL_218281_combined_data_auto.txt"
    data_path = tmp_path / "REFL_218281_combined_data_auto.txt"
    data_path.write_bytes(src.read_bytes())

    # Monkeypatch the LLM call so no network/auth is required.
    captured: Dict[str, Any] = {}

    def fake_call(messages, *, llm=None, max_retries=1):  # noqa: ARG001
        captured["messages"] = messages
        return mg.model_spec_from_dict(model_spec_dict)

    monkeypatch.setattr(mg, "call_llm_for_model_spec", fake_call)

    out_path = tmp_path / "models" / "generated.py"
    runner = CliRunner()
    result = runner.invoke(
        cm.main,
        [
            "--describe",
            "2 nm CuOx / 50 nm Cu / 3.5 nm Ti on Si in D2O",
            "--data",
            str(data_path),
            "--out",
            str(out_path),
            "--model-name",
            "gen_cu",
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    content = out_path.read_text()
    assert "create_fit_experiment" in content
    assert "QProbe" in content
    assert "FitProblem(experiment)" in content
    # LLM saw a user message with the description.
    assert any(
        "2 nm CuOx" in m.get("content", "") for m in captured["messages"]
    )


def test_cli_config_file_drives_mode_b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_spec_dict: Dict[str, Any],
) -> None:
    """A YAML config file can supply describe/data/out."""
    import yaml

    src = SAMPLE_DATA_DIR / "REFL_218281_combined_data_auto.txt"
    data_path = tmp_path / "REFL_218281_combined_data_auto.txt"
    data_path.write_bytes(src.read_bytes())

    out_path = tmp_path / "models" / "from_config.py"
    config = {
        "describe": "Cu/Ti on Si in D2O",
        "data": [str(data_path)],
        "out": str(out_path),
        "model_name": "from_cfg",
    }
    cfg_path = tmp_path / "model.yaml"
    cfg_path.write_text(yaml.safe_dump(config))

    monkeypatch.setattr(
        mg,
        "call_llm_for_model_spec",
        lambda messages, **kw: mg.model_spec_from_dict(model_spec_dict),
    )

    runner = CliRunner()
    result = runner.invoke(cm.main, ["--config", str(cfg_path)])
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    assert "create_fit_experiment" in out_path.read_text()


def test_cli_rejects_both_modes_simultaneously(tmp_path: Path) -> None:
    json_path = tmp_path / "x.json"
    json_path.write_text('{"substrate": {"name": "Si", "sld": 2.07}, '
                         '"ambient": {"name": "D2O", "sld": 6.19}, '
                         '"layers": []}')
    data_path = tmp_path / "REFL_218281_combined_data_auto.txt"
    data_path.touch()

    runner = CliRunner()
    result = runner.invoke(
        cm.main,
        [str(json_path), "--describe", "x", "--data", str(data_path)],
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output
