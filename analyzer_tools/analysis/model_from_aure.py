"""
Bridge between AuRE ModelDefinition JSON and analyzer-convention refl1d scripts.

The analyzer convention is a Python module in ``models/`` that defines::

    def create_fit_experiment(q, dq, data, errors) -> refl1d.Experiment

This module converts an AuRE ``ModelDefinition`` dict
(see ``aure.nodes.model_builder``) into such a script, so that AuRE-generated
models fit seamlessly into the existing analyzer fitting/assessment tools.

It also provides a best-effort helper that invokes ``aure analyze`` as a
subprocess with ``--max-refinements 0`` to obtain a ModelDefinition from a
plain-English sample description (until AuRE ships a dedicated
model-generation CLI).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import click


# ---------------------------------------------------------------------------
# ModelDefinition → analyzer-convention script
# ---------------------------------------------------------------------------


def _safe_identifier(name: str, fallback: str) -> str:
    """Convert *name* into a valid Python identifier suitable for dict keys."""
    ident = "".join(c if c.isalnum() or c == "_" else "_" for c in name.strip())
    if not ident or not (ident[0].isalpha() or ident[0] == "_"):
        ident = fallback
    return ident


def _range_pair(layer: Dict[str, Any], key: str, default_min: float, default_max: float) -> tuple[float, float]:
    """Return (min, max) range for *key* (thickness/sld/roughness) with fallbacks."""
    lo = layer.get(f"{key}_min", default_min)
    hi = layer.get(f"{key}_max", default_max)
    return float(lo), float(hi)


def definition_to_script(definition: Dict[str, Any], *, model_name: str = "model") -> str:
    """Convert an AuRE ModelDefinition to an analyzer-convention refl1d script.

    The returned string is a valid Python module that exposes
    ``create_fit_experiment(q, dq, data, errors)`` and can be dropped into
    the ``models/`` directory.

    Parameters
    ----------
    definition
        ModelDefinition dict with keys: ``substrate``, ``layers``, ``ambient``,
        optional ``intensity``, ``back_reflection``, ``dq_is_fwhm``.
    model_name
        Used only in the module docstring.
    """
    substrate = definition["substrate"]
    ambient = definition["ambient"]
    layers = definition.get("layers", [])
    back_reflection = bool(definition.get("back_reflection", False))
    intensity = definition.get("intensity", {}) or {}
    dq_is_fwhm = bool(definition.get("dq_is_fwhm", True))

    sub_name = _safe_identifier(substrate["name"], "substrate")
    amb_name = _safe_identifier(ambient["name"], "ambient")

    # Build unique layer identifiers (avoid collisions with substrate/ambient).
    used = {sub_name, amb_name}
    layer_names: list[str] = []
    for i, layer in enumerate(layers):
        base = _safe_identifier(layer["name"], f"layer{i + 1}")
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        layer_names.append(candidate)

    lines: list[str] = []
    lines.append(f'"""Auto-generated analyzer model ({model_name}) from AuRE ModelDefinition."""')
    lines.append("")
    lines.append("from refl1d.names import *")
    lines.append("")
    lines.append("")
    lines.append("def create_fit_experiment(q, dq, data, errors):")
    lines.append('    """Build an analyzer-convention refl1d Experiment.')
    lines.append("")
    lines.append("    Parameters")
    lines.append("    ----------")
    lines.append("    q, dq, data, errors : array-like")
    lines.append("        Columns Q, dQ, R, dR from the data file. dq is assumed to be FWHM;")
    lines.append("        it is converted to 1-sigma internally.")
    lines.append('    """')
    if dq_is_fwhm:
        lines.append("    # Go from FWHM to 1-sigma")
        lines.append("    dq = dq / 2.355")
    lines.append("    probe = QProbe(q, dq, R=data, dR=errors)")

    # Probe intensity
    if intensity.get("fixed", False):
        lines.append(f"    probe.intensity = Parameter(value={float(intensity.get('value', 1.0))!r}, name=\"intensity\")")
    else:
        int_val = float(intensity.get("value", 1.0))
        int_min = float(intensity.get("min", 0.7))
        int_max = float(intensity.get("max", 1.1))
        lines.append(f"    probe.intensity = Parameter(value={int_val!r}, name=\"intensity\")")
        lines.append(f"    probe.intensity.range({int_min!r}, {int_max!r})")

    lines.append("")
    lines.append("    # Materials")
    lines.append(f"    {sub_name} = SLD(name={substrate['name']!r}, rho={float(substrate['sld'])!r})")
    lines.append(f"    {amb_name} = SLD(name={ambient['name']!r}, rho={float(ambient['sld'])!r})")
    for ident, layer in zip(layer_names, layers):
        lines.append(f"    {ident} = SLD(name={layer['name']!r}, rho={float(layer['sld'])!r})")

    lines.append("")
    lines.append("    # Sample stack")
    # Stack order: refl1d convention is "top | ... | substrate".
    # For back-reflection AuRE stacks neutrons coming from the substrate side
    # (ambient | layers(reverse) | substrate). For standard geometry it's
    # (ambient | layers | substrate). In both cases layer0 is the bottom
    # layer closest to the substrate when back_reflection=False.
    sub_rough = float(substrate.get("roughness", 3.0))
    if back_reflection:
        parts = [f"{amb_name}(0, 5.0)"]
        for ident, layer in zip(reversed(layer_names), reversed(layers)):
            parts.append(f"{ident}({float(layer['thickness'])!r}, {float(layer.get('roughness', 5.0))!r})")
        parts.append(sub_name)
    else:
        parts = [f"{amb_name}(0, 5.0)"]
        for ident, layer in zip(reversed(layer_names), reversed(layers)):
            parts.append(f"{ident}({float(layer['thickness'])!r}, {float(layer.get('roughness', 5.0))!r})")
        parts.append(f"{sub_name}(0, {sub_rough!r})")
    lines.append("    sample = " + " | ".join(parts))

    lines.append("")
    lines.append("    experiment = Experiment(probe=probe, sample=sample)")
    lines.append("")
    lines.append("    # Parameter ranges")

    # Ambient SLD (if not air and an sld_min/max is given)
    if (
        ambient.get("name", "").lower() != "air"
        and ambient.get("sld", 0) != 0
        and ("sld_min" in ambient or "sld_max" in ambient)
    ):
        amb_min = float(ambient.get("sld_min", ambient["sld"] * 0.8))
        amb_max = float(ambient.get("sld_max", ambient["sld"] * 1.2))
        lines.append(f"    sample[{ambient['name']!r}].material.rho.range({amb_min!r}, {amb_max!r})")

    # Substrate interface (only meaningful in non-back-reflection geometry)
    if not back_reflection:
        sub_rough_max = float(substrate.get("roughness_max", 15.0))
        lines.append(f"    sample[{substrate['name']!r}].interface.range(0.0, {sub_rough_max!r})")

    for layer in layers:
        t_min, t_max = _range_pair(layer, "thickness", float(layer["thickness"]) * 0.5, float(layer["thickness"]) * 2.0)
        s_min, s_max = _range_pair(layer, "sld", float(layer["sld"]) - 2.5, float(layer["sld"]) + 2.5)
        r_min, r_max = _range_pair(layer, "roughness", 5.0, 30.0)
        key = layer["name"]
        lines.append(f"    sample[{key!r}].thickness.range({t_min!r}, {t_max!r})")
        lines.append(f"    sample[{key!r}].material.rho.range({s_min!r}, {s_max!r})")
        lines.append(f"    sample[{key!r}].interface.range({r_min!r}, {r_max!r})")

    lines.append("")
    lines.append("    return experiment")
    lines.append("")

    return "\n".join(lines)


def load_definition(path: str | os.PathLike) -> Dict[str, Any]:
    """Load a ModelDefinition JSON from *path*."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_model_script(definition: Dict[str, Any], out_path: str | os.PathLike, *, model_name: Optional[str] = None) -> str:
    """Write *definition* as an analyzer-convention script to *out_path*.

    Returns the absolute output path.
    """
    out = os.path.abspath(str(out_path))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    name = model_name or Path(out).stem
    script = definition_to_script(definition, model_name=name)
    with open(out, "w", encoding="utf-8") as f:
        f.write(script)
    return out


# ---------------------------------------------------------------------------
# AuRE subprocess wrapper (generate-only)
# ---------------------------------------------------------------------------


def _find_initial_definition(output_dir: str | os.PathLike) -> Optional[str]:
    """Find the latest ``*_model_initial.json`` in an AuRE output directory."""
    models_dir = Path(output_dir) / "models"
    if not models_dir.is_dir():
        return None
    candidates = sorted(models_dir.glob("*_model_initial.json"))
    if not candidates:
        return None
    return str(candidates[-1])


def invoke_aure_modeling(
    sample_description: str,
    data_file: str,
    *,
    output_dir: str | os.PathLike,
    aure_executable: str = "aure",
    extra_args: Optional[list[str]] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Run ``aure analyze`` with ``--max-refinements 0`` to get a ModelDefinition.

    Until AuRE ships a dedicated model-generation CLI, this is the supported
    way to obtain a ModelDefinition without running a full fit.

    Parameters
    ----------
    sample_description
        Plain-English description of the sample (e.g. "Cu/Ti on Si in dTHF").
    data_file
        Path to a reflectivity data file.
    output_dir
        Directory where AuRE will write checkpoints and model JSON files.
    aure_executable
        Name or path of the ``aure`` CLI.
    extra_args
        Additional arguments forwarded to ``aure analyze``.
    timeout
        Optional subprocess timeout in seconds.

    Returns
    -------
    dict
        The ModelDefinition loaded from the generated
        ``*_model_initial.json`` file.
    """
    output_dir = os.path.abspath(str(output_dir))
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        aure_executable,
        "analyze",
        str(data_file),
        sample_description,
        "-o",
        output_dir,
        "-m",
        "0",
    ]
    if extra_args:
        cmd.extend(extra_args)

    subprocess.run(cmd, check=True, timeout=timeout)

    initial = _find_initial_definition(output_dir)
    if initial is None:
        raise RuntimeError(
            f"AuRE did not produce a '*_model_initial.json' in {output_dir}/models. "
            "Check the AuRE output for errors."
        )
    return load_definition(initial)


# ---------------------------------------------------------------------------
# Legacy helper: wrap an existing model.py + data file into a fit script
# ---------------------------------------------------------------------------


def create_fit_script(model_name: str, data_file: str, *, models_dir: str = "models") -> str:
    """Legacy wrapper: combine ``models/<model_name>.py`` with a tiny runner.

    This mirrors the original ``create_model_script.create_fit_script`` but is
    kept here so the new CLI can expose it as a deprecated subcommand.
    Returns the path of the generated script.
    """
    import re
    import sys

    model_path = os.path.join(models_dir, f"{model_name}.py")
    try:
        with open(model_path, "r", encoding="utf-8") as f:
            model_content = f.read()
    except FileNotFoundError:
        print(f"Error: Model file '{model_path}' not found.", file=sys.stderr)
        sys.exit(1)

    match = re.search(r"REFL_(\d+)_", os.path.basename(data_file))
    if not match:
        print(f"Error: Could not extract set_id from data file name: {data_file}", file=sys.stderr)
        sys.exit(1)
    set_id = match.group(1)

    script_name = f"model_{set_id}_{model_name}.py"
    fit_commands = (
        f'\n_refl = np.loadtxt("{data_file}").T\n'
        f"experiment = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])\n"
        f"problem = FitProblem(experiment)\n"
    )
    with open(script_name, "w", encoding="utf-8") as f:
        f.write("import numpy as np\n\n")
        f.write(model_content)
        f.write(fit_commands)
    return script_name


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.argument("source", type=str)
@click.argument("data_file", type=str, required=False)
@click.option(
    "--out",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output path for the generated model script (default: models/<name>.py).",
)
@click.option(
    "--from-json/--from-description",
    default=None,
    help="Force the input mode. Auto-detected from SOURCE if omitted.",
)
@click.option(
    "--model-name",
    type=str,
    default=None,
    help="Name to use in the generated script's docstring and default filename.",
)
@click.option(
    "--aure-output",
    type=click.Path(file_okay=False),
    default=None,
    help="Working directory for AuRE (defaults to a temp dir when using --from-description).",
)
@click.option(
    "--legacy",
    is_flag=True,
    default=False,
    help="Legacy mode: wrap an existing models/<SOURCE>.py + DATA_FILE into a fit script.",
)
def main(
    source: str,
    data_file: Optional[str],
    out: Optional[str],
    from_json: Optional[bool],
    model_name: Optional[str],
    aure_output: Optional[str],
    legacy: bool,
) -> None:
    """Generate a refl1d model script.

    Three modes:

    \b
    1. From an AuRE ModelDefinition JSON file:
         create-model path/to/model_initial.json --out models/cu_thf.py
    2. From a sample description (calls ``aure analyze -m 0``):
         create-model "Cu/Ti on Si in dTHF" data/combined/REFL_123_combined_data_auto.txt \\
             --out models/cu_thf.py
    3. Legacy: wrap existing models/<name>.py + data file into a fit script
       (deprecated; use AuRE-generated models going forward):
         create-model cu_thf data/combined/REFL_123_combined_data_auto.txt --legacy
    """
    # Legacy path: wrap models/<name>.py with the original helper.
    if legacy:
        if not data_file:
            raise click.BadParameter("DATA_FILE is required in --legacy mode")
        click.echo(
            "Warning: --legacy mode is deprecated. Use AuRE-generated ModelDefinition JSON instead.",
            err=True,
        )
        path = create_fit_script(source, data_file)
        click.echo(f"Successfully created fit script: {path}")
        return

    # Auto-detect input mode
    if from_json is None:
        from_json = os.path.isfile(source) and source.lower().endswith(".json")

    if from_json:
        if not os.path.isfile(source):
            raise click.BadParameter(f"ModelDefinition JSON not found: {source}")
        definition = load_definition(source)
        default_name = model_name or Path(source).stem
    else:
        # Description mode: SOURCE is the sample description text.
        if not data_file:
            raise click.BadParameter(
                "DATA_FILE is required when generating from a sample description"
            )
        default_name = model_name or "model"
        work_dir = aure_output or os.path.join(".aure_work", default_name)
        click.echo(f"Invoking AuRE to generate model in {work_dir} …", err=True)
        definition = invoke_aure_modeling(
            source, data_file, output_dir=work_dir
        )

    if out is None:
        out = os.path.join("models", f"{default_name}.py")

    path = write_model_script(definition, out, model_name=default_name)
    click.echo(f"Wrote analyzer model script: {path}")


if __name__ == "__main__":
    main()
