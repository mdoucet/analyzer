"""
LLM-driven refl1d model script generator (``create-model`` Mode B).

Given a natural-language sample description and one or more REF_L data files,
this module:

1. Detects which fitting *case* applies (see below).
2. Calls the configured LLM (via ``aure.llm``) with a strict JSON-output prompt
   to obtain a :class:`ModelSpec` (materials, layer stack, bounds, optional
   case-3 shared-parameter list).
3. Renders an analyzer-convention refl1d script from that spec using a
   case-specific template — the Python is always produced by our code so the
   LLM cannot emit arbitrary code.

Cases
-----
* **case1** — one combined data file, Q-based ``QProbe``.
* **case2** — multiple ``REFL_{set}_{part}_{run}_partial.txt`` files sharing
  a single ``set_id``; angle-based probes built with ``make_probe``.
* **case3** — multiple combined data files representing distinct measurements
  to be co-refined with shared structural parameters (not supported by AuRE).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

CASE_1 = "case1"
CASE_2 = "case2"
CASE_3 = "case3"

_PARTIAL_RE = re.compile(r"REFL_(\d+)_(\d+)_(\d+)_partial\.txt$", re.IGNORECASE)
_COMBINED_RE = re.compile(r"REFL_(\d+)_combined_data_auto\.txt$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------


def _classify_file(path: Path) -> Tuple[str, Dict[str, str]]:
    """Return ("partial"|"combined", metadata) for a REF_L file path."""
    name = path.name
    m = _PARTIAL_RE.search(name)
    if m:
        return "partial", {
            "set_id": m.group(1),
            "part_id": m.group(2),
            "run_id": m.group(3),
        }
    m = _COMBINED_RE.search(name)
    if m:
        return "combined", {"set_id": m.group(1)}
    raise ValueError(
        f"Unrecognised REF_L filename: {name!r}. Expected "
        "'REFL_{set}_combined_data_auto.txt' or "
        "'REFL_{set}_{part}_{run}_partial.txt'."
    )


def detect_case(data_files: Sequence[Path | str]) -> str:
    """Choose case1 / case2 / case3 from *data_files*."""
    if not data_files:
        raise ValueError("At least one data file is required.")
    paths = [Path(f) for f in data_files]
    kinds = [_classify_file(p) for p in paths]

    kinds_only = {k for k, _ in kinds}
    if len(kinds_only) > 1:
        raise ValueError(
            "Mixing partial and combined data files is not supported. "
            "Provide either a single combined file, several partial files "
            "from the same set, or several combined files."
        )

    kind = next(iter(kinds_only))
    if kind == "combined":
        return CASE_1 if len(paths) == 1 else CASE_3

    # Partial files: must share a single set_id.
    set_ids = {meta["set_id"] for _, meta in kinds}
    if len(set_ids) > 1:
        raise ValueError(
            "Partial files span multiple set_ids: "
            f"{sorted(set_ids)}. All partial files must share the "
            "same set_id (the first run number)."
        )
    if len(paths) < 2:
        raise ValueError(
            "Case 2 (multi-segment co-refinement) needs at least two partial "
            "files from the same set; only one was given."
        )
    return CASE_2


# ---------------------------------------------------------------------------
# REF_L header parsing
# ---------------------------------------------------------------------------


_RUN_ROW_RE = re.compile(
    r"^#\s*(\d+)\s+(\d+)\s+([0-9.+\-eE]+)\s+"
    r"([0-9.+\-eE]+)\s+([0-9.+\-eE]+)"
)


def parse_refl_header(path: Path | str) -> Dict[str, Any]:
    """Extract experiment/run metadata from a REF_L data file header.

    Returns a dict with keys:

    * ``experiment`` — e.g. ``"IPTS-34347"``
    * ``run`` — top-level run number from the header line
    * ``theta_offset`` — float (degrees) if present, else ``0.0``
    * ``runs`` — list of ``{data_run, norm_run, two_theta, theta, lambda_min, lambda_max}``
      for every row of the header table (1 row for partials, N for combined).
    """
    path = Path(path)
    experiment: Optional[str] = None
    run: Optional[str] = None
    theta_offset = 0.0
    runs: List[Dict[str, Any]] = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.startswith("#"):
                break
            stripped = line.lstrip("# ").rstrip()
            if stripped.startswith("Experiment "):
                parts = stripped.split()
                # "Experiment IPTS-xxxx Run yyyy"
                if len(parts) >= 2:
                    experiment = parts[1]
                if len(parts) >= 4 and parts[2].lower() == "run":
                    run = parts[3]
            elif stripped.startswith("Theta offset"):
                _, _, val = stripped.partition(":")
                try:
                    theta_offset = float(val.strip())
                except ValueError:
                    theta_offset = 0.0
            else:
                m = _RUN_ROW_RE.match(line)
                if m:
                    two_theta = float(m.group(3))
                    runs.append(
                        {
                            "data_run": m.group(1),
                            "norm_run": m.group(2),
                            "two_theta": two_theta,
                            "theta": two_theta / 2.0,
                            "lambda_min": float(m.group(4)),
                            "lambda_max": float(m.group(5)),
                        }
                    )

    return {
        "experiment": experiment,
        "run": run,
        "theta_offset": theta_offset,
        "runs": runs,
    }


# ---------------------------------------------------------------------------
# Structured model specification (LLM output schema)
# ---------------------------------------------------------------------------


@dataclass
class LayerSpec:
    name: str
    sld: float
    thickness: float = 0.0
    roughness: float = 5.0
    thickness_min: Optional[float] = None
    thickness_max: Optional[float] = None
    sld_min: Optional[float] = None
    sld_max: Optional[float] = None
    roughness_min: Optional[float] = None
    roughness_max: Optional[float] = None


@dataclass
class ModelSpec:
    ambient: LayerSpec
    substrate: LayerSpec
    layers: List[LayerSpec]  # ambient-adjacent → substrate-adjacent (top-to-bottom)
    intensity: Dict[str, float] = field(
        default_factory=lambda: {"value": 1.0, "min": 0.95, "max": 1.05}
    )
    back_reflection: bool = False
    # Case-3 only: list of per-layer attribute paths to tie across experiments,
    # e.g. ["Cu.material.rho", "Cu.interface", "Ti.thickness"].
    shared_parameters: List[str] = field(default_factory=list)


def _layer_from_dict(d: Dict[str, Any]) -> LayerSpec:
    return LayerSpec(
        name=str(d["name"]),
        sld=float(d["sld"]),
        thickness=float(d.get("thickness", 0.0)),
        roughness=float(d.get("roughness", 5.0)),
        thickness_min=_opt_float(d.get("thickness_min")),
        thickness_max=_opt_float(d.get("thickness_max")),
        sld_min=_opt_float(d.get("sld_min")),
        sld_max=_opt_float(d.get("sld_max")),
        roughness_min=_opt_float(d.get("roughness_min")),
        roughness_max=_opt_float(d.get("roughness_max")),
    )


def _opt_float(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def model_spec_from_dict(d: Dict[str, Any]) -> ModelSpec:
    """Validate an LLM JSON response and coerce into a :class:`ModelSpec`.

    Raises ``ValueError`` on missing/invalid keys.
    """
    for key in ("ambient", "substrate", "layers"):
        if key not in d:
            raise ValueError(f"ModelSpec JSON is missing required key {key!r}.")
    if not isinstance(d["layers"], list) or len(d["layers"]) == 0:
        raise ValueError("ModelSpec 'layers' must be a non-empty list.")

    ambient = _layer_from_dict(d["ambient"])
    substrate = _layer_from_dict(d["substrate"])
    layers = [_layer_from_dict(layer) for layer in d["layers"]]

    intensity = d.get("intensity") or {}
    intensity_out = {
        "value": float(intensity.get("value", 1.0)),
        "min": float(intensity.get("min", 0.95)),
        "max": float(intensity.get("max", 1.05)),
    }

    return ModelSpec(
        ambient=ambient,
        substrate=substrate,
        layers=layers,
        intensity=intensity_out,
        back_reflection=bool(d.get("back_reflection", False)),
        shared_parameters=[str(p) for p in (d.get("shared_parameters") or [])],
    )


# ---------------------------------------------------------------------------
# LLM prompting
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You are a neutron reflectometry expert helping to construct refl1d model
specifications. You MUST reply with a single JSON object conforming to the
schema provided in the user message — no prose, no code fences, no commentary.

Domain rules (apply to every layer):
- Minimum roughness: 5 Å. Typical range: 5–30 Å.
- Roughness bounds must stay below half the thickness of adjacent layers.
- SLD bounds: at least ±2 × 10⁻⁶ Å⁻² around nominal. For adhesion layers
  (Ti etc.), use ±3 or wider.
- Never vary the substrate SLD. Its roughness sits on the last layer's
  interface; do not add a substrate-thickness parameter.
- Minimum layer thickness: 5 Å. Do NOT add SiO₂ on silicon unless the user
  explicitly mentions it.

Common SLD (×10⁻⁶ Å⁻²): Silicon 2.07, Gold 4.5, Copper 6.55, Titanium −1.95,
Platinum 6.288, D2O 6.19, THF 5.8, Air 0.0.
"""


_JSON_SCHEMA_DESCRIPTION = """\
Respond with a JSON object of shape:

{
  "ambient":   {"name": str, "sld": float,
                "sld_min": float?, "sld_max": float?,
                "roughness": float?, "roughness_min": float?, "roughness_max": float?},
  "substrate": {"name": str, "sld": float,
                "roughness_min": float?, "roughness_max": float?},
  "layers": [
    {"name": str, "sld": float, "thickness": float, "roughness": float,
     "thickness_min": float, "thickness_max": float,
     "sld_min": float, "sld_max": float,
     "roughness_min": float, "roughness_max": float}
  ],
  "intensity":       {"value": float, "min": float, "max": float},
  "back_reflection": bool,
  "shared_parameters": [str]   // case 3 only; ignored otherwise
}

Layer ordering: the "layers" list goes from the ambient-adjacent layer
(first) to the substrate-adjacent layer (last). Do NOT include the ambient
or the substrate inside "layers".
"""


def _case_instructions(case: str, n_files: int) -> str:
    if case == CASE_1:
        return (
            "Case 1: a single combined data file. Produce a layer stack for "
            "a standard Q-based QProbe fit. Leave 'shared_parameters' empty."
        )
    if case == CASE_2:
        return (
            f"Case 2: {n_files} partial (single-angle) files from the same "
            "measurement. All segments see the same sample, so produce one "
            "layer stack. Leave 'shared_parameters' empty — the renderer "
            "automatically shares the sample object across probes."
        )
    return (
        f"Case 3: {n_files} combined data files to be co-refined. Produce one "
        "shared layer stack, and in 'shared_parameters' list the dotted "
        "attribute paths that should be *tied* across all experiments, e.g. "
        '"Cu.material.rho", "Cu.interface", "Ti.thickness", "Ti.material.rho", '
        '"Ti.interface". Intensity and ambient SLD should normally be '
        "per-experiment (do NOT list them in shared_parameters)."
    )


def build_llm_prompt(
    case: str,
    description: str,
    data_files: Sequence[Path],
    headers: Sequence[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Build a (system, user) message pair for the LLM call."""
    header_blocks = []
    for path, header in zip(data_files, headers):
        runs = header.get("runs") or []
        run_lines = "\n".join(
            f"    - data_run={r['data_run']}, 2θ={r['two_theta']:.4f}°, θ={r['theta']:.4f}°"
            for r in runs
        )
        header_blocks.append(
            f"- {path.name} (experiment {header.get('experiment')}, "
            f"run {header.get('run')}, theta_offset={header.get('theta_offset')}):\n"
            f"{run_lines or '    (no run table rows)'}"
        )
    header_block = "\n".join(header_blocks)

    user = (
        f"Sample description (from the user):\n"
        f"{description.strip()}\n\n"
        f"Data files:\n{header_block}\n\n"
        f"{_case_instructions(case, len(data_files))}\n\n"
        f"{_JSON_SCHEMA_DESCRIPTION}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


class LLMResponseError(RuntimeError):
    """Raised when the LLM reply cannot be parsed into a ModelSpec."""


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(content: str) -> Dict[str, Any]:
    """Pull a JSON object out of the LLM response."""
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK_RE.search(content)
    if m:
        return json.loads(m.group(1))
    # Try bracket-balanced first-object extraction as a last resort.
    start = content.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(content[start : i + 1])
    raise LLMResponseError(f"No JSON object found in LLM response: {content[:200]!r}")


def call_llm_for_model_spec(
    messages: List[Dict[str, str]],
    *,
    llm: Any = None,
    max_retries: int = 1,
) -> ModelSpec:
    """Invoke the configured LLM and parse the reply into a :class:`ModelSpec`.

    On the first parse/validation failure, append the error to the
    conversation and retry once. Raises :class:`LLMResponseError` if the
    second attempt also fails.
    """
    if llm is None:  # pragma: no cover - real LLM is opt-in
        from aure.llm import get_llm

        llm = get_llm(temperature=0.0)

    history = list(messages)
    last_error: Optional[str] = None
    for attempt in range(max_retries + 1):
        reply = llm.invoke(history)
        content = getattr(reply, "content", reply)
        if isinstance(content, list):  # Some providers return segmented content.
            content = "".join(
                seg.get("text", "") if isinstance(seg, dict) else str(seg)
                for seg in content
            )
        try:
            data = _extract_json(str(content))
            return model_spec_from_dict(data)
        except (LLMResponseError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt >= max_retries:
                break
            history = history + [
                {"role": "assistant", "content": str(content)},
                {
                    "role": "user",
                    "content": (
                        "Your previous reply could not be parsed: "
                        f"{last_error}. Please respond with ONLY a valid JSON "
                        "object matching the schema. No prose, no code fences."
                    ),
                },
            ]
    raise LLMResponseError(
        f"LLM reply still invalid after {max_retries + 1} attempt(s): {last_error}"
    )


# ---------------------------------------------------------------------------
# Script rendering
# ---------------------------------------------------------------------------


def _format_float(value: float) -> str:
    """Compact float repr suitable for embedding in generated source."""
    return repr(float(value))


def _layer_var(layer: LayerSpec, used: set[str]) -> str:
    base = "".join(c if c.isalnum() or c == "_" else "_" for c in layer.name.strip())
    if not base or not (base[0].isalpha() or base[0] == "_"):
        base = f"layer_{len(used)}"
    candidate = base
    i = 2
    while candidate in used:
        candidate = f"{base}_{i}"
        i += 1
    used.add(candidate)
    return candidate


def _materials_lines(spec: ModelSpec, indent: str) -> List[str]:
    used: set[str] = set()
    lines: List[str] = []
    for layer in [spec.ambient] + spec.layers + [spec.substrate]:
        var = _layer_var(layer, used)
        lines.append(
            f"{indent}{var} = SLD(name={layer.name!r}, rho={_format_float(layer.sld)})"
        )
    return lines


def _stack_line(spec: ModelSpec, indent: str) -> str:
    # refl1d stack order: ambient → substrate (ambient first).
    parts: List[str] = [
        f"{spec.ambient.name}(0, {_format_float(spec.ambient.roughness)})"
    ]
    for layer in spec.layers:
        parts.append(
            f"{layer.name}({_format_float(layer.thickness)}, "
            f"{_format_float(layer.roughness)})"
        )
    parts.append(spec.substrate.name)
    return f"{indent}sample = " + " | ".join(parts)


def _range_lines(spec: ModelSpec, indent: str, *, sample_var: str = "sample") -> List[str]:
    out: List[str] = []
    amb = spec.ambient
    if amb.sld_min is not None and amb.sld_max is not None:
        out.append(
            f'{indent}{sample_var}[{amb.name!r}].material.rho.range('
            f"{_format_float(amb.sld_min)}, {_format_float(amb.sld_max)})"
        )
    if amb.roughness_min is not None and amb.roughness_max is not None:
        out.append(
            f'{indent}{sample_var}[{amb.name!r}].interface.range('
            f"{_format_float(amb.roughness_min)}, {_format_float(amb.roughness_max)})"
        )
    for layer in spec.layers:
        if layer.thickness_min is not None and layer.thickness_max is not None:
            out.append(
                f'{indent}{sample_var}[{layer.name!r}].thickness.range('
                f"{_format_float(layer.thickness_min)}, "
                f"{_format_float(layer.thickness_max)})"
            )
        if layer.sld_min is not None and layer.sld_max is not None:
            out.append(
                f'{indent}{sample_var}[{layer.name!r}].material.rho.range('
                f"{_format_float(layer.sld_min)}, "
                f"{_format_float(layer.sld_max)})"
            )
        if layer.roughness_min is not None and layer.roughness_max is not None:
            out.append(
                f'{indent}{sample_var}[{layer.name!r}].interface.range('
                f"{_format_float(layer.roughness_min)}, "
                f"{_format_float(layer.roughness_max)})"
            )
    sub = spec.substrate
    if sub.roughness_min is not None and sub.roughness_max is not None:
        out.append(
            f'{indent}{sample_var}[{sub.name!r}].interface.range('
            f"{_format_float(sub.roughness_min)}, "
            f"{_format_float(sub.roughness_max)})"
        )
    return out


_HEADER = """\
\"\"\"Auto-generated analyzer model ({model_name}) — created by create-model.\"\"\"

import os
import numpy as np
from bumps.fitters import fit
from refl1d.names import *
"""


def render_case1_script(
    spec: ModelSpec,
    data_file: Path | str,
    *,
    model_name: str = "model",
) -> str:
    """Render a case-1 (single combined file, QProbe) script."""
    lines: List[str] = [_HEADER.format(model_name=model_name), ""]
    lines.append("def create_fit_experiment(q, dq, data, errors):")
    lines.append('    """Build an analyzer-convention refl1d Experiment.')
    lines.append("")
    lines.append("    Parameters")
    lines.append("    ----------")
    lines.append("    q, dq, data, errors : array-like")
    lines.append("        Columns Q, dQ, R, dR from the data file. dq is assumed to be FWHM;")
    lines.append("        it is converted to 1-sigma internally.")
    lines.append('    """')
    lines.append("    # Go from FWHM to 1-sigma")
    lines.append("    dq = dq / 2.355")
    lines.append("    probe = QProbe(q, dq, data=(data, errors))")
    lines.append(
        f"    probe.intensity = Parameter(value={_format_float(spec.intensity['value'])}, "
        f'name="intensity")'
    )
    lines.append(
        f"    probe.intensity.range({_format_float(spec.intensity['min'])}, "
        f"{_format_float(spec.intensity['max'])})"
    )
    lines.append("")
    lines.extend(_materials_lines(spec, "    "))
    lines.append("")
    lines.append(_stack_line(spec, "    "))
    lines.append("")
    lines.append("    experiment = Experiment(probe=probe, sample=sample)")
    lines.append("")
    lines.append("    # Parameter ranges")
    lines.extend(_range_lines(spec, "    "))
    lines.append("")
    lines.append("    return experiment")
    lines.append("")
    lines.append("")
    lines.append(f"data_file = {str(data_file)!r}")
    lines.append("")
    lines.append("_refl = np.loadtxt(data_file).T")
    lines.append(
        "experiment = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])"
    )
    lines.append("")
    lines.append("problem = FitProblem(experiment)")
    lines.append("")
    return "\n".join(lines)


def render_case2_script(
    spec: ModelSpec,
    data_files: Sequence[Path | str],
    thetas: Sequence[float],
    *,
    model_name: str = "model",
) -> str:
    """Render a case-2 (multi-segment partials, make_probe) script."""
    if len(data_files) != len(thetas):
        raise ValueError("data_files and thetas must be the same length")

    lines: List[str] = [_HEADER.format(model_name=model_name)]
    lines.append("from refl1d.probe import make_probe")
    lines.append("")
    lines.append("")
    lines.append("def create_probe(data_file, theta):")
    lines.append('    """Build an angle-based probe from one REF_L partial file."""')
    lines.append("    q, data, errors, dq = np.loadtxt(data_file).T")
    lines.append("    wl = 4 * np.pi * np.sin(np.pi / 180 * theta) / q")
    lines.append("    dT = dq / q * np.tan(np.pi / 180 * theta) * 180 / np.pi")
    lines.append("    dL = 0 * q  # wavelength resolution placeholder")
    lines.append("    probe = make_probe(")
    lines.append("        T=theta, dT=dT, L=wl, dL=dL,")
    lines.append("        data=(data, errors),")
    lines.append('        radiation="neutron",')
    lines.append('        resolution="uniform",')
    lines.append("    )")
    lines.append(
        f"    probe.intensity = Parameter(value={_format_float(spec.intensity['value'])}, "
        f'name="intensity")'
    )
    lines.append(
        f"    probe.intensity.range({_format_float(spec.intensity['min'])}, "
        f"{_format_float(spec.intensity['max'])})"
    )
    lines.append("    return probe")
    lines.append("")
    lines.append("")
    lines.append("def create_sample():")
    lines.append('    """Build the shared sample stack (one stack, all probes)."""')
    lines.extend(_materials_lines(spec, "    "))
    lines.append("")
    lines.append(_stack_line(spec, "    "))
    lines.append("")
    lines.append("    # Parameter ranges")
    lines.extend(_range_lines(spec, "    "))
    lines.append("")
    lines.append("    return sample")
    lines.append("")
    lines.append("")
    for i, path in enumerate(data_files, start=1):
        lines.append(f"data_file{i} = {str(path)!r}")
    lines.append("")
    lines.append("sample = create_sample()")
    lines.append("")
    probe_names: List[str] = []
    for i, theta in enumerate(thetas, start=1):
        probe_names.append(f"probe{i}")
        lines.append(
            f"probe{i} = create_probe(data_file{i}, theta={_format_float(theta)})"
        )
    lines.append("")
    experiment_names: List[str] = []
    for i, pname in enumerate(probe_names, start=1):
        ename = "experiment" if i == 1 else f"experiment{i}"
        experiment_names.append(ename)
        lines.append(f"{ename} = Experiment(probe={pname}, sample=sample)")
    lines.append("")
    lines.append(
        "# To enable shared sample_broadening / theta_offset, uncomment:"
    )
    lines.append(f"# {probe_names[0]}.sample_broadening.range(0.0, 0.5)")
    for other in probe_names[1:]:
        lines.append(
            f"# {other}.sample_broadening = {probe_names[0]}.sample_broadening"
        )
    lines.append(f"# {probe_names[0]}.theta_offset.range(-0.02, 0.02)")
    for other in probe_names[1:]:
        lines.append(
            f"# {other}.theta_offset = {probe_names[0]}.theta_offset"
        )
    lines.append("")
    lines.append("problem = FitProblem(" + experiment_names[0] + ")")
    lines.append("")
    return "\n".join(lines)


_SHARED_PATH_RE = re.compile(
    r"^\s*(?P<layer>[^.\s]+)\.(?P<attr>material\.rho|thickness|interface)\s*$"
)


def _shared_constraint_line(i: int, path: str) -> Optional[str]:
    m = _SHARED_PATH_RE.match(path)
    if not m:
        return None
    layer = m.group("layer")
    attr = m.group("attr")
    expt_i = f"experiment{i}" if i > 1 else "experiment"  # not used for i==1
    return (
        f'{expt_i}.sample[{layer!r}].{attr} = '
        f'experiment.sample[{layer!r}].{attr}'
    )


def render_case3_script(
    spec: ModelSpec,
    data_files: Sequence[Path | str],
    *,
    model_name: str = "model",
) -> str:
    """Render a case-3 (multiple combined files, co-refined) script."""
    if len(data_files) < 2:
        raise ValueError("case 3 requires at least two data files")

    lines: List[str] = [_HEADER.format(model_name=model_name), ""]
    lines.append("def create_fit_experiment(q, dq, data, errors):")
    lines.append('    """Build a refl1d Experiment with an INDEPENDENT sample copy.')
    lines.append("")
    lines.append("    Each experiment gets its own sample stack; shared structural")
    lines.append("    parameters are tied explicitly below with assignments of the")
    lines.append("    form ``experimentN.sample[\"Layer\"].attr = experiment.sample[...]``.")
    lines.append('    """')
    lines.append("    dq = dq / 2.355  # FWHM → 1-sigma")
    lines.append("    probe = QProbe(q, dq, data=(data, errors))")
    lines.append(
        f"    probe.intensity = Parameter(value={_format_float(spec.intensity['value'])}, "
        f'name="intensity")'
    )
    lines.append(
        f"    probe.intensity.range({_format_float(spec.intensity['min'])}, "
        f"{_format_float(spec.intensity['max'])})"
    )
    lines.append("")
    lines.extend(_materials_lines(spec, "    "))
    lines.append("")
    lines.append(_stack_line(spec, "    "))
    lines.append("")
    lines.append("    experiment = Experiment(probe=probe, sample=sample)")
    lines.append("")
    lines.append("    # Parameter ranges")
    lines.extend(_range_lines(spec, "    "))
    lines.append("")
    lines.append("    return experiment")
    lines.append("")
    lines.append("")
    for i, path in enumerate(data_files, start=1):
        lines.append(f"data_file{i} = {str(path)!r}")
    lines.append("")
    experiment_names: List[str] = []
    for i in range(1, len(data_files) + 1):
        ename = "experiment" if i == 1 else f"experiment{i}"
        experiment_names.append(ename)
        lines.append(f"_refl = np.loadtxt(data_file{i}).T")
        lines.append(
            f"{ename} = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])"
        )
    lines.append("")
    if spec.shared_parameters:
        lines.append("# Shared structural parameters across experiments")
        for i in range(2, len(data_files) + 1):
            for path in spec.shared_parameters:
                constraint = _shared_constraint_line(i, path)
                if constraint is not None:
                    lines.append(constraint)
        lines.append("")
    lines.append(
        "problem = FitProblem([" + ", ".join(experiment_names) + "])"
    )
    lines.append("")
    return "\n".join(lines)


def render_script(
    case: str,
    spec: ModelSpec,
    data_files: Sequence[Path | str],
    *,
    thetas: Optional[Sequence[float]] = None,
    model_name: str = "model",
) -> str:
    if case == CASE_1:
        return render_case1_script(spec, data_files[0], model_name=model_name)
    if case == CASE_2:
        if thetas is None:
            raise ValueError("case 2 rendering requires thetas")
        return render_case2_script(spec, data_files, thetas, model_name=model_name)
    if case == CASE_3:
        return render_case3_script(spec, data_files, model_name=model_name)
    raise ValueError(f"Unknown case {case!r}")


# ---------------------------------------------------------------------------
# Top-level orchestration (used by CLI)
# ---------------------------------------------------------------------------


def generate_model_script(
    description: str,
    data_files: Sequence[Path | str],
    *,
    model_name: str = "model",
    llm: Any = None,
) -> str:
    """High-level entry point: files → header parsing → LLM → script."""
    paths = [Path(f) for f in data_files]
    case = detect_case(paths)
    headers = [parse_refl_header(p) for p in paths]
    messages = build_llm_prompt(case, description, paths, headers)
    spec = call_llm_for_model_spec(messages, llm=llm)

    thetas: Optional[List[float]] = None
    if case == CASE_2:
        # Pull theta from each partial file's single header row; fall back to
        # filename order if any row is missing.
        thetas = []
        for h in headers:
            runs = h.get("runs") or []
            if not runs:
                raise ValueError(
                    "Case 2 requires a 2θ entry in every partial file header; "
                    "one of the files has an empty header table."
                )
            thetas.append(float(runs[0]["theta"]))
    return render_script(case, spec, paths, thetas=thetas, model_name=model_name)
