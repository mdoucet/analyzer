"""
``create-model`` CLI — dispatches between Mode A and Mode B.

Mode A — convert an existing AuRE problem JSON or ModelDefinition::

    create-model path/to/problem.json [-o models/<name>.py]

Mode B — generate a new script via LLM from a sample description and one or
more data files (auto-detecting which of cases 1/2/3 applies)::

    create-model --describe "..." --data file1.txt [--data file2.txt ...] \\
                 [-o models/<name>.py] [--model-name NAME]

Either mode also accepts a ``--config FILE`` (YAML or JSON) that provides the
same options as keys (``describe``, ``data``, ``out``, ``model_name``,
``source``). CLI flags override values loaded from the config file.

The config file may also use an AuRE-batch-manifest shape with a top-level
``jobs:`` list; each job is processed in turn. Per-job keys recognized:
``sample_description`` / ``description`` / ``describe``, ``data_file`` and
``data_files`` / ``data`` (merged), ``model_name`` / ``name``, ``source``,
``out``. A top-level ``defaults.output_root`` (or ``output_root``) is used as
the output directory when a job does not set ``out``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import yaml


def _load_config(path: Path) -> Dict[str, Any]:
    """Load a YAML or JSON config file into a plain dict."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise click.BadParameter(
            f"Config file {path} must contain a mapping at the top level."
        )
    return data


def _normalize_data(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (str, os.PathLike)):
        return [str(value)]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    raise click.BadParameter(f"Invalid 'data' value in config: {value!r}")


def _pick(d: Dict[str, Any], *keys: str) -> Any:
    """Return the first non-None value among ``keys`` in mapping ``d``."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _collect_data(d: Dict[str, Any]) -> List[str]:
    """Gather data files from a mapping, supporting multiple aliases."""
    files: List[str] = []
    single = _pick(d, "data_file")
    if single is not None:
        files.extend(_normalize_data(single))
    multi = _pick(d, "data", "data_files")
    if multi is not None:
        files.extend(_normalize_data(multi))
    return files


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("source", required=False, type=click.Path(dir_okay=False))
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="YAML or JSON file providing CLI options (describe, data, out, "
    "model_name, source). Flags on the command line override config values.",
)
@click.option(
    "--env",
    "env_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Extra .env file loaded at the top of the cascade (after the "
    "process environment, before project and user-global .env). Useful "
    "when running from a data directory that has no .env of its own.",
)
@click.option(
    "--describe",
    "describe",
    type=str,
    default=None,
    help="Mode B: natural-language description of the sample. Required with --data.",
)
@click.option(
    "--data",
    "data",
    type=click.Path(exists=True, dir_okay=False),
    multiple=True,
    help="Mode B: REF_L data file (repeatable). Auto-detects case 1 (one "
    "combined file), case 2 (partial files sharing a set_id), or case 3 "
    "(multiple combined files).",
)
@click.option(
    "-o",
    "--out",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output path for the generated model script. "
    "Default: <ANALYZER_MODELS_DIR>/<name>.py.",
)
@click.option(
    "--model-name",
    type=str,
    default=None,
    help="Name used in the script docstring and default output filename.",
)
def main(
    source: Optional[str],
    config_path: Optional[Path],
    env_path: Optional[Path],
    describe: Optional[str],
    data: Tuple[str, ...],
    out: Optional[str],
    model_name: Optional[str],
) -> None:
    """Generate a refl1d model script.

    \b
    Two modes:
      A) Convert an AuRE problem JSON — pass SOURCE.
      B) Generate via LLM from a description + data files —
         pass --describe and one or more --data.

    \b
    Case is auto-detected from the REF_L file names:
      case 1 — one combined file
      case 2 — N partial files sharing one set_id
      case 3 — N combined files co-refined (not supported by AuRE)

    \b
    --config FILE (YAML or JSON) supplies the same options as keys.
    Two shapes are accepted.

    \b
    Flat shape (one job). CLI flags override config.
    Paths resolve against the config file's directory.
    Top-level keys:
      describe: >-            # aliases: description, sample_description
        <sample description>
      data:                   # alias: data_files
        - path/to/file1.txt
        - path/to/file2.txt
      data_file: extra.txt    # optional; prepended to 'data'
      source:    problem.json # Mode A instead of describe/data
      out:       Models/foo.py
      model_name: foo         # alias: name

    \b
    Jobs-list shape (batch) — AuRE-manifest-compatible; each entry is
    one create-model call. AuRE-only keys (fit_method, fit_steps,
    llm_*, command, ...) are IGNORED. Only defaults.output_root is read.
      defaults:
        output_root: ./Models          # <root>/<name>.py if 'out' absent
      jobs:
        - name: copper_oxide
          sample_description: >-
            2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O.
          data_file:  Rawdata/REFL_226642_1_226642_partial.txt
          data_files:
            - Rawdata/REFL_226642_2_226643_partial.txt
            - Rawdata/REFL_226642_3_226644_partial.txt
        - name: corefine
          description: 2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O
          data:
            - Rawdata/REFL_226642_combined_data_auto.txt
            - Rawdata/REFL_226652_combined_data_auto.txt
          out: Models/Cu-D2O-corefine.py

    \b
    Each job must be Mode A (source) OR Mode B (describe + data),
    not both. When 'jobs:' is present, do not also pass
    SOURCE / --describe / --data on the command line.

    \b
    States shape (multi-state co-refinement). Use 'states:' instead of
    'data:' to group files by sample and control cross-state parameter
    tying.
      describe: ...
      states:
        - name: run_226642               # partials → one sample, 3 segments
          data:
            - Rawdata/REFL_226642_1_226642_partial.txt
            - Rawdata/REFL_226642_2_226643_partial.txt
            - Rawdata/REFL_226642_3_226644_partial.txt
          theta_offset:      {init: 0.0, min: -0.02, max: 0.02}
          sample_broadening: true        # defaults init=0, 0…0.01
        - name: run_226652               # combined file → single segment
          data: [Rawdata/REFL_226652_combined_data_auto.txt]
          back_reflection: true          # beam enters through substrate
      shared_parameters:                 # whitelist of tied attrs
        - Cu.thickness
        - Cu.material.rho
        - Ti.thickness
      # unshared_parameters: [CuOx.thickness]  # blacklist (mutex)
      out: Models/Cu-D2O-corefine.py

    \b
    States rules: within one state all files must be the same kind
    (all-partials-of-one-set OR one-combined) AND they share ONE Sample
    object, so every structural parameter is automatically tied across
    the state's files. theta_offset and sample_broadening are only
    allowed on partial-kind states; back_reflection is a per-state
    boolean (defaults to the LLM's answer); shared_parameters and
    unshared_parameters are mutually exclusive.

    \b
    Examples
    --------
    # Mode A: convert an AuRE problem JSON
    create-model path/to/problem.json -o models/cu_thf.py

    \b
    # Mode B: one combined file (case 1)
    create-model --describe "Cu/Ti on Si in D2O" \\
                 --data data/REFL_226642_combined_data_auto.txt \\
                 -o models/cu_thf.py

    \b
    # Mode B: co-refine two combined files (case 3)
    create-model --describe "CuOx/Cu/Ti on Si in D2O" \\
                 --data REFL_226642_combined_data_auto.txt \\
                 --data REFL_226652_combined_data_auto.txt \\
                 -o models/Cu-D2O-corefine.py

    \b
    # From a config file (flat or jobs-list)
    create-model --config model-creation.yaml
    """
    from analyzer_tools.config_utils import get_config

    cfg_obj = get_config(str(env_path) if env_path else None)
    models_dir = cfg_obj.get_models_dir()
    if env_path and cfg_obj.loaded_env_files:
        click.echo(
            "Loaded .env files: "
            + ", ".join(str(p) for p in cfg_obj.loaded_env_files),
            err=True,
        )

    # ── Jobs-style config: iterate and dispatch each job ────────────────
    if config_path is not None:
        cfg_raw = _load_config(config_path)
        if isinstance(cfg_raw.get("jobs"), list):
            if source or describe or data:
                raise click.BadParameter(
                    "When --config contains a 'jobs' list, do not also pass "
                    "SOURCE/--describe/--data on the command line."
                )
            cfg_dir = config_path.parent.resolve()
            defaults = cfg_raw.get("defaults") or {}
            default_out_root = _pick(defaults, "output_root") or _pick(
                cfg_raw, "output_root"
            )
            jobs = cfg_raw["jobs"]
            if not jobs:
                raise click.BadParameter("'jobs' list in config is empty.")
            for i, job in enumerate(jobs):
                if not isinstance(job, dict):
                    raise click.BadParameter(f"jobs[{i}] must be a mapping.")
                _dispatch_job(
                    job,
                    cfg_dir=cfg_dir,
                    default_out_root=default_out_root,
                    cli_out=out,
                    cli_model_name=model_name,
                    models_dir=models_dir,
                )
            return
        cfg: Dict[str, Any] = cfg_raw
    else:
        cfg = {}

    # ── Flat single-job merge: CLI wins over config ────────────────────
    if source is None:
        source = _pick(cfg, "source")
    if describe is None:
        describe = _pick(cfg, "describe", "description", "sample_description")
    data_list: List[str] = list(data) if data else _collect_data(cfg)
    if out is None:
        out = _pick(cfg, "out")
    if model_name is None:
        model_name = _pick(cfg, "model_name", "name")

    cfg_dir = config_path.parent.resolve() if config_path is not None else None

    # Multi-state path: "states:" takes precedence over flat "data:".
    states_raw = cfg.get("states") if isinstance(cfg.get("states"), list) else None
    if states_raw and data:
        raise click.BadParameter(
            "Config has a 'states:' list; do not also pass --data on the CLI."
        )
    if states_raw and source:
        raise click.BadParameter(
            "Mode A (SOURCE JSON) cannot be combined with a 'states:' list."
        )

    # Resolve relative paths against the config file's directory.
    if cfg_dir is not None:
        if source and not os.path.isabs(source):
            source = str(cfg_dir / source)
        data_list = [
            p if os.path.isabs(p) else str(cfg_dir / p) for p in data_list
        ]

    # Optional DATA_DIR variable emitted in the generated script so users
    # can redirect the script at a different data copy without editing any
    # other line. Relative values are resolved against the config file's
    # directory at generation time; the literal string is what ends up in
    # the script, so users should set this to the path they want to see
    # there (an absolute path, or a short relative like "data").
    data_dir_raw = _pick(cfg, "data_dir")
    data_dir: Optional[str] = None
    data_dir_abs: Optional[str] = None
    if data_dir_raw:
        data_dir = str(data_dir_raw)
        if os.path.isabs(data_dir):
            data_dir_abs = data_dir
        elif cfg_dir is not None:
            data_dir_abs = str((cfg_dir / data_dir).resolve())
        else:
            data_dir_abs = str(Path(data_dir).resolve())

    if states_raw is not None:
        if not describe:
            raise click.BadParameter(
                "Multi-state mode needs 'describe' / 'description' in the config."
            )
        _run_states_mode(
            describe=describe,
            states=states_raw,
            shared=cfg.get("shared_parameters"),
            unshared=cfg.get("unshared_parameters"),
            base_dir=cfg_dir,
            out=out,
            model_name=model_name,
            models_dir=models_dir,
            data_dir=data_dir,
            data_dir_abs=data_dir_abs,
        )
        return

    if source and (describe or data_list):
        raise click.BadParameter(
            "Mode A (SOURCE JSON) and Mode B (--describe / --data) are mutually "
            "exclusive. Pass either a JSON SOURCE or --describe + --data."
        )
    if not source and not (describe and data_list):
        raise click.BadParameter(
            "Provide either a JSON SOURCE (Mode A) or --describe and at least "
            "one --data file (Mode B). Use --config to read options from a file."
        )

    if source:
        _run_mode_a(source, out=out, model_name=model_name, models_dir=models_dir)
    else:
        assert describe is not None and data_list  # for type narrowing
        _run_mode_b(
            describe=describe,
            data_files=data_list,
            out=out,
            model_name=model_name,
            models_dir=models_dir,
            data_dir=data_dir,
            data_dir_abs=data_dir_abs,
        )


def _dispatch_job(
    job: Dict[str, Any],
    *,
    cfg_dir: Path,
    default_out_root: Optional[str],
    cli_out: Optional[str],
    cli_model_name: Optional[str],
    models_dir: str,
) -> None:
    """Run a single job from a ``jobs:`` list in the config file."""
    source = _pick(job, "source")
    describe = _pick(job, "describe", "description", "sample_description")
    data_list = _collect_data(job)
    model_name = cli_model_name or _pick(job, "model_name", "name")
    out = cli_out or _pick(job, "out")
    states_raw = job.get("states") if isinstance(job.get("states"), list) else None

    # Resolve relative paths against the config file's directory.
    if source and not os.path.isabs(source):
        source = str(cfg_dir / source)
    data_list = [p if os.path.isabs(p) else str(cfg_dir / p) for p in data_list]

    # If no explicit out, default to <output_root>/<model_name>.py (relative to cfg_dir).
    if out is None and default_out_root is not None:
        name = model_name or (
            Path(source).stem if source else "model"
        )
        root = default_out_root
        if not os.path.isabs(root):
            root = str(cfg_dir / root)
        out = os.path.join(root, f"{name}.py")
    elif out is not None and not os.path.isabs(out):
        out = str(cfg_dir / out)

    # Per-job data_dir takes precedence over the top-level one.
    data_dir_raw = _pick(job, "data_dir")
    data_dir = str(data_dir_raw) if data_dir_raw else None
    data_dir_abs: Optional[str] = None
    if data_dir is not None:
        if os.path.isabs(data_dir):
            data_dir_abs = data_dir
        else:
            data_dir_abs = str((cfg_dir / data_dir).resolve())

    if states_raw is not None:
        if source:
            raise click.BadParameter(
                f"Job {model_name or '?'}: 'source' (Mode A) cannot be "
                "combined with a 'states:' list."
            )
        if data_list:
            raise click.BadParameter(
                f"Job {model_name or '?'}: use either 'data'/'data_files' OR "
                "'states:', not both."
            )
        if not describe:
            raise click.BadParameter(
                f"Job {model_name or '?'}: multi-state mode needs "
                "'describe' / 'description'."
            )
        _run_states_mode(
            describe=describe,
            states=states_raw,
            shared=job.get("shared_parameters"),
            unshared=job.get("unshared_parameters"),
            base_dir=cfg_dir,
            out=out,
            model_name=model_name,
            models_dir=models_dir,
            data_dir=data_dir,
            data_dir_abs=data_dir_abs,
        )
        return

    if source and (describe or data_list):
        raise click.BadParameter(
            f"Job {model_name or '?'}: cannot mix 'source' with "
            "'describe'/'data' in the same entry."
        )
    if not source and not (describe and data_list):
        raise click.BadParameter(
            f"Job {model_name or '?'}: need either 'source' (Mode A) or "
            "'describe' + data files (Mode B)."
        )

    if source:
        _run_mode_a(source, out=out, model_name=model_name, models_dir=models_dir)
    else:
        assert describe is not None and data_list
        _run_mode_b(
            describe=describe,
            data_files=data_list,
            out=out,
            model_name=model_name,
            models_dir=models_dir,
            data_dir=data_dir,
            data_dir_abs=data_dir_abs,
        )


# ---------------------------------------------------------------------------
# Mode A — JSON → script
# ---------------------------------------------------------------------------


def _run_mode_a(
    source: str,
    *,
    out: Optional[str],
    model_name: Optional[str],
    models_dir: str,
) -> None:
    from .model_from_aure import load_definition, write_model_script

    if not os.path.isfile(source):
        raise click.BadParameter(f"SOURCE {source!r} does not exist.")

    definition = load_definition(source)
    data_files = definition.pop("_data_files", None)
    default_name = model_name or Path(source).stem
    if out is None:
        out = os.path.join(models_dir, f"{default_name}.py")
    path = write_model_script(
        definition, out, model_name=default_name, data_files=data_files
    )
    click.echo(f"Wrote analyzer model script: {path}")


# ---------------------------------------------------------------------------
# Mode B — description + data → LLM → script
# ---------------------------------------------------------------------------


def _write_script(out: str, script: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(script)
    click.echo(f"Wrote analyzer model script: {os.path.abspath(out)}")


def _handle_llm_failure(exc: Exception) -> None:
    """Re-raise as ClickException with guidance when LLM creds are missing."""
    msg = str(exc)
    if "API_KEY" in msg or "provider" in msg.lower():
        from analyzer_tools.config_utils import get_config

        cfg_obj = get_config()
        loaded = cfg_obj.loaded_env_files
        loaded_str = (
            "\n  ".join(str(p) for p in loaded) if loaded else "(none found)"
        )
        raise click.ClickException(
            f"LLM is not configured: {msg}\n\n"
            "Analyzer loads .env files in this order (highest priority first):\n"
            "  1. process environment\n"
            "  2. --env PATH / $ANALYZER_ENV_FILE\n"
            "  3. nearest .env walking up from the current directory\n"
            "  4. ~/.config/analyzer/.env  (or $ANALYZER_CONFIG_DIR/.env\n"
            "     or $XDG_CONFIG_HOME/analyzer/.env)\n\n"
            f"Files loaded this run:\n  {loaded_str}\n\n"
            "Add LLM_PROVIDER, LLM_MODEL, LLM_API_KEY (and LLM_BASE_URL if\n"
            "using a local endpoint) to one of those files, or pass\n"
            "--env PATH explicitly."
        ) from exc
    raise exc


def _run_mode_b(
    *,
    describe: str,
    data_files: List[str],
    out: Optional[str],
    model_name: Optional[str],
    models_dir: str,
    data_dir: Optional[str] = None,
    data_dir_abs: Optional[str] = None,
) -> None:
    from .model_generator import generate_model_script

    default_name = model_name or "model"
    if out is None:
        out = os.path.join(models_dir, f"{default_name}.py")

    click.echo(f"Generating model script via LLM for {len(data_files)} data file(s)…", err=True)
    try:
        script = generate_model_script(
            description=describe,
            data_files=data_files,
            model_name=default_name,
            data_dir=data_dir,
            data_dir_abs=data_dir_abs,
        )
    except ValueError as exc:
        _handle_llm_failure(exc)
        return  # unreachable

    _write_script(out, script)


# ---------------------------------------------------------------------------
# Mode B (multi-state) — YAML "states:" → LLM → script
# ---------------------------------------------------------------------------


def _run_states_mode(
    *,
    describe: str,
    states: List[Dict[str, Any]],
    shared: Any,
    unshared: Any,
    base_dir: Optional[Path],
    out: Optional[str],
    model_name: Optional[str],
    models_dir: str,
    data_dir: Optional[str] = None,
    data_dir_abs: Optional[str] = None,
) -> None:
    from .model_generator import (
        build_state_specs,
        generate_model_script_from_states,
    )

    default_name = model_name or "model"
    if out is None:
        out = os.path.join(models_dir, f"{default_name}.py")

    try:
        state_specs = build_state_specs(states, base_dir=base_dir)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    shared_list = _as_str_list("shared_parameters", shared)
    unshared_list = _as_str_list("unshared_parameters", unshared)
    if shared_list is not None and unshared_list is not None:
        raise click.BadParameter(
            "'shared_parameters' and 'unshared_parameters' are mutually exclusive."
        )

    click.echo(
        "Generating multi-state model script via LLM "
        f"({len(state_specs)} state(s), "
        f"{sum(len(s.data_files) for s in state_specs)} file(s))…",
        err=True,
    )
    try:
        script = generate_model_script_from_states(
            description=describe,
            states=state_specs,
            model_name=default_name,
            shared_parameters=shared_list,
            unshared_parameters=unshared_list,
            data_dir=data_dir,
            data_dir_abs=data_dir_abs,
        )
    except ValueError as exc:
        _handle_llm_failure(exc)
        return  # unreachable

    _write_script(out, script)


def _as_str_list(field_name: str, raw: Any) -> Optional[List[str]]:
    if raw is None:
        return None
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return [str(v) for v in raw]
    raise click.BadParameter(
        f"{field_name!r} must be a list of strings, got {type(raw).__name__}."
    )


if __name__ == "__main__":
    main()
