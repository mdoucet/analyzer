"""
``plan-data`` CLI — generate a config YAML for a newly arriving data file.

The output YAML conforms to the ``create-model --config`` / ``analyze-sample``
schema (top-level ``describe`` / ``states`` / ``model_name``) plus a
``metadata`` block that carries job-control information
(``perform_assembly`` and free-form ``notes``). The ``metadata`` block is
ignored by ``create-model`` and ``analyze-sample`` so the same file can be
passed directly to either tool.

The tool delegates the entire decision-making to the LLM:

1. The relevant skill files (data-organization, create-model, plan-data,
   reflectometry-basics) are loaded and passed to the LLM as authoritative
   reference material.
2. The data file's full header (all comment lines) is passed verbatim so
   the LLM can read whatever metadata the instrument wrote
   (``sequence_id``, ``sequence_number``, run number, etc.).
3. A listing of the data file's sibling files in the same directory is
   passed so the LLM can decide whether the sequence is complete.
4. The scientist's free-form context file is passed.
5. The LLM returns a single JSON object that IS the config YAML.

This module performs no filename parsing, no header regex, and no
sequence-completeness heuristics. All such logic lives in the prompt and
the skill files passed to the LLM.

Usage::

    plan-data DATA_FILE CONTEXT_FILE --output-dir DIR [--sequence-total N]
"""

from __future__ import annotations

import json
import logging
import os
import re
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill loading
# ---------------------------------------------------------------------------


_DEFAULT_SKILL_NAMES = (
    "data-organization",
    "create-model",
    "plan-data",
    "reflectometry-basics",
)


def _find_skills_dir() -> Optional[Path]:
    """Locate a writable ``skills/`` directory for development overrides.

    Checked in order:

    1. ``$ANALYZER_SKILLS_DIR`` if set and a directory.
    2. A ``skills/`` directory next to ``analyzer_tools/`` in a source
       checkout (walking upward from this file). Lets contributors edit
       SKILL.md files without reinstalling.

    Returns ``None`` when neither is found; callers should then fall back
    to packaged resources via :func:`load_skills`.
    """
    env_dir = os.environ.get("ANALYZER_SKILLS_DIR")
    if env_dir:
        candidate = Path(env_dir)
        if candidate.is_dir():
            return candidate
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "skills"
        if candidate.is_dir() and (candidate / "plan-data" / "SKILL.md").is_file():
            return candidate
    return None


def _load_packaged_skill(name: str) -> Optional[str]:
    """Return the SKILL.md text for *name* shipped inside the package."""
    try:
        skill_file = resources.files("analyzer_tools.skills") / name / "SKILL.md"
    except (ModuleNotFoundError, FileNotFoundError):
        return None
    try:
        return skill_file.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return None


def load_skills(skill_names: List[str]) -> Dict[str, str]:
    """Return ``{skill_name: file_text}`` for every skill that loads.

    Prefers a development override (``ANALYZER_SKILLS_DIR`` or a sibling
    ``skills/`` dir in a source checkout) so live edits are picked up;
    falls back per-skill to the copy bundled inside the installed
    ``analyzer_tools`` package.
    """
    skills_dir = _find_skills_dir()
    out: Dict[str, str] = {}
    for name in skill_names:
        if skills_dir is not None:
            override = skills_dir / name / "SKILL.md"
            if override.is_file():
                try:
                    out[name] = override.read_text(encoding="utf-8")
                    continue
                except OSError:
                    pass
        packaged = _load_packaged_skill(name)
        if packaged is not None:
            out[name] = packaged
    return out


# ---------------------------------------------------------------------------
# Data file inspection (no parsing — raw text is forwarded to the LLM)
# ---------------------------------------------------------------------------


def read_header_lines(path: Path, *, max_lines: int = 200) -> str:
    """Return the leading comment lines (``#`` prefix) of a text file."""
    out: List[str] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                if line.startswith("#"):
                    out.append(line.rstrip("\n"))
                else:
                    break
    except OSError:
        return ""
    return "\n".join(out)


def list_sibling_files(data_file: Path) -> List[str]:
    """Return the names of all regular files in ``data_file``'s directory."""
    try:
        return sorted(p.name for p in data_file.parent.iterdir() if p.is_file())
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Prompt construction and LLM call
# ---------------------------------------------------------------------------


_SYSTEM_INSTRUCTIONS = """\
You are the data-arrival planner for a neutron reflectometry analysis
pipeline. A new data file has just arrived. Your job is to produce a
config YAML (returned as JSON) that can be passed *directly* to the
``create-model --config`` and ``analyze-sample`` CLIs.

You will receive, in the user message:

* The full text of several SKILL.md files describing the analyzer's
  conventions and tools. Treat these as authoritative.
* The header (comment lines) of the newly arrived data file.
* A listing of all sibling files in the data file's directory.
* The scientist's free-form context file describing the sample.
* The expected total number of files per complete sequence.

You MUST:

1. Identify the sequence this data file belongs to. Prefer metadata in
   the file header (e.g. ``sequence_id``, ``sequence_number`` in a
   ``Meta:`` JSON line) over any inference from the filename.
2. Decide whether the sequence is complete: every part from 1 to the
   expected total must be represented by a sibling file (use the file
   naming conventions from the data-organization skill).
3. Set ``metadata.perform_assembly: true`` if and only if this data
   file is the last part of the sequence AND every part is present in
   the sibling listing.
4. If — and only if — ``perform_assembly`` is true AND the context
   file is rich enough to draft a refl1d model (substrate, layer
   stack, and ambient medium are identifiable), populate the
   create-model schema fields at the TOP LEVEL of the config:
   ``describe``, ``states`` (list with ``name`` + ``data`` + optional
   ``theta_offset`` / ``sample_broadening`` / ``back_reflection`` /
   ``extra_description``), and ``model_name``. Use sibling file paths
   (basenames) as they appear in the listing.
5. Always write a clear summary into ``metadata.notes``.

Reply with a single JSON object and nothing else (no prose, no code
fences). The JSON must conform to:

{
  "config": {
    // create-model schema fields at the top level — OPTIONAL,
    // include only when context is rich enough to draft a model:
    "describe": "...",
    "states": [ ... ],
    "model_name": "...",
    // Always present:
    "metadata": {
      "perform_assembly": bool,
      "notes": "..."
    }
  },
  "sequence_id": str,            // used to name the output file
  "sequence_number": int,
  "sequence_complete": bool,
  "create_model_ready": bool     // true iff describe+states populated
}

Do NOT wrap the create-model fields in a nested ``create_model`` key —
they must sit at the top level of ``config`` so the file can be passed
directly to ``create-model --config`` and ``analyze-sample``. Do NOT
add fields outside the documented create-model schema. Do NOT invent
files that are not in the sibling listing. The ``metadata`` block is
ignored by ``create-model`` and ``analyze-sample`` and carries only
job-control information.
"""


def build_user_message(
    *,
    skills: Dict[str, str],
    data_file: Path,
    header_text: str,
    sibling_files: List[str],
    context_text: str,
    sequence_total: int,
) -> str:
    """Assemble the user-message payload."""
    parts: List[str] = []
    parts.append("=== ANALYZER SKILLS (authoritative reference) ===")
    for name, body in skills.items():
        parts.append(f"\n--- skill: {name} ---\n{body.strip()}\n")
    parts.append("\n=== END SKILLS ===\n")

    parts.append(f"Data file path: {data_file}")
    parts.append(f"Data file directory: {data_file.parent}")
    parts.append(f"Expected files per complete sequence: {sequence_total}")

    parts.append("\n--- Data file header (comment lines only) ---")
    parts.append(header_text or "(no header lines found)")

    parts.append("\n--- Sibling files in the same directory ---")
    parts.append("\n".join(sibling_files) if sibling_files else "(directory is empty)")

    parts.append("\n--- Scientist's context file ---")
    parts.append(context_text.strip() or "(empty)")

    parts.append("\nProduce the JSON object now. Reply with JSON only, no commentary.")
    return "\n".join(parts)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _extract_json(text: str) -> Dict[str, Any]:
    """Pull the first JSON object out of an LLM reply."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_FENCE_RE.search(text)
    if m:
        return json.loads(m.group(1))
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    raise ValueError(f"No JSON object found in LLM reply: {text[:200]!r}")


def call_planner_llm(user_message: str) -> Dict[str, Any]:
    """Invoke the configured LLM with the planner prompt."""
    # Load the analyzer .env cascade (project .env walked up from CWD, then
    # ~/.config/analyzer/.env) into os.environ so that aure.llm.get_llm()
    # picks up LLM_PROVIDER / LLM_API_KEY / LLM_BASE_URL etc. even when they
    # are not exported in the shell.
    try:
        from analyzer_tools.config_utils import _load_env

        _load_env()
    except Exception:
        pass

    try:
        from aure.llm import get_llm, llm_available  # type: ignore
    except Exception as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "AuRE LLM module is not importable. Install AuRE and run "
            "`check-llm` to diagnose."
        ) from exc

    if not llm_available():
        raise RuntimeError(
            "AuRE LLM is not configured (set LLM_PROVIDER, LLM_API_KEY, "
            "etc.). Run `check-llm` for details."
        )

    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore

    llm = get_llm()
    response = llm.invoke(
        [
            SystemMessage(content=_SYSTEM_INSTRUCTIONS),
            HumanMessage(content=user_message),
        ]
    )
    text = getattr(response, "content", str(response))
    if isinstance(text, bytes):
        text = text.decode()
    return _extract_json(text)


# ---------------------------------------------------------------------------
# YAML serialisation helpers
# ---------------------------------------------------------------------------


class _LiteralStr(str):
    """str subclass rendered as a YAML literal block scalar."""


def _literal_representer(dumper: yaml.Dumper, data: _LiteralStr) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


def _literalise(obj: Any, keys: Tuple[str, ...]) -> Any:
    if isinstance(obj, dict):
        return {
            k: (
                _LiteralStr(v)
                if k in keys and isinstance(v, str) and "\n" in v
                else _literalise(v, keys)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_literalise(item, keys) for item in obj]
    return obj


def dump_job_yaml(job: Dict[str, Any]) -> str:
    """Serialise *job* to YAML with block scalars for prose fields."""
    processed = _literalise(job, keys=("notes", "describe"))
    dumper = yaml.Dumper
    dumper.add_representer(_LiteralStr, _literal_representer)
    return yaml.dump(
        processed,
        Dumper=dumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )  # ---------------------------------------------------------------------------


# CLI entry point
# ---------------------------------------------------------------------------


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "data_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "context_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
    help="Directory in which to write the job YAML file.",
)
@click.option(
    "--sequence-total",
    "-n",
    type=int,
    default=3,
    show_default=True,
    help="Expected total number of files in a complete sequence.",
)
@click.option(
    "--skill",
    "skill_overrides",
    multiple=True,
    help="Skill name to include (repeatable). Defaults to: "
    + ", ".join(_DEFAULT_SKILL_NAMES)
    + ".",
)
def main(
    data_file: Path,
    context_file: Path,
    output_dir: Path,
    sequence_total: int,
    skill_overrides: tuple,
) -> None:
    """Generate a job YAML for a newly arrived data file (LLM-driven).

    \b
    DATA_FILE    — the new data file from the instrument.
    CONTEXT_FILE — scientist's Markdown context note for the sample.

    The tool loads the analyzer's skill files, the data file's header,
    a listing of sibling files in the same directory, and the context
    file, then asks the configured LLM to produce a complete job YAML.
    All decisions about sequence identity, sequence completeness, and
    whether to draft a create_model block are made by the LLM. Run
    ``check-llm`` first if the LLM endpoint may be unreachable.
    """
    skill_names = (
        list(skill_overrides) if skill_overrides else list(_DEFAULT_SKILL_NAMES)
    )
    skills = load_skills(skill_names)
    if not skills:
        click.echo(
            "Warning: no skill files were loaded — LLM will plan blind.",
            err=True,
        )

    header_text = read_header_lines(data_file)
    sibling_files = list_sibling_files(data_file)
    try:
        context_text = context_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise click.FileError(str(context_file), hint=str(exc)) from exc

    user_message = build_user_message(
        skills=skills,
        data_file=data_file,
        header_text=header_text,
        sibling_files=sibling_files,
        context_text=context_text,
        sequence_total=sequence_total,
    )

    click.echo(f"Loaded skills: {', '.join(skills) or '(none)'}")
    click.echo(f"Data file: {data_file.name}  (sibling files: {len(sibling_files)})")

    try:
        result = call_planner_llm(user_message)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise click.ClickException(f"LLM planner failed: {exc}") from exc

    job = result.get("config") or result.get("job") or {}
    if not isinstance(job, dict) or not job:
        raise click.ClickException(
            f"LLM did not return a 'config' object. Reply was: {result!r}"
        )

    sequence_id = result.get("sequence_id") or "unknown"
    sequence_number = result.get("sequence_number")
    sequence_complete = result.get("sequence_complete", False)
    metadata = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
    perform_assembly = metadata.get("perform_assembly")
    create_model_ready = result.get("create_model_ready")
    if create_model_ready is None:
        create_model_ready = bool(job.get("states")) and bool(job.get("describe"))

    click.echo(
        f"sequence_id={sequence_id}  sequence_number={sequence_number}  "
        f"complete={sequence_complete}"
    )
    click.echo(f"metadata.perform_assembly: {perform_assembly}")
    click.echo(
        "create-model fields: "
        + (
            "present (config is ready for create-model / analyze-sample)."
            if create_model_ready
            else "omitted."
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"job_{sequence_id}.yaml"
    out_path.write_text(dump_job_yaml(job), encoding="utf-8")
    click.echo(f"Job YAML written to: {out_path}")
