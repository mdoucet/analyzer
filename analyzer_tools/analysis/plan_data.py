"""
``plan-data`` CLI — generate a job YAML for a newly arriving data file.

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
5. The LLM returns a single JSON object that IS the job YAML.

This module performs no filename parsing, no header regex, and no
sequence-completeness heuristics. All such logic lives in the prompt and
the skill files passed to the LLM.

Usage::

    plan-data DATA_FILE CONTEXT_FILE --output-dir DIR [--sequence-total N]
"""

from __future__ import annotations

import json
import logging
import re
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
    """Locate the analyzer's ``skills/`` directory by walking upward."""
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        candidate = parent / "skills"
        if candidate.is_dir():
            return candidate
    return None


def load_skills(skill_names: List[str]) -> Dict[str, str]:
    """Return ``{skill_name: file_text}`` for every skill found on disk."""
    skills_dir = _find_skills_dir()
    if skills_dir is None:
        return {}
    out: Dict[str, str] = {}
    for name in skill_names:
        path = skills_dir / name / "SKILL.md"
        if path.is_file():
            try:
                out[name] = path.read_text(encoding="utf-8")
            except OSError:
                continue
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
        return sorted(
            p.name for p in data_file.parent.iterdir() if p.is_file()
        )
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Prompt construction and LLM call
# ---------------------------------------------------------------------------


_SYSTEM_INSTRUCTIONS = """\
You are the data-arrival planner for a neutron reflectometry analysis
pipeline. A new data file has just arrived. Your job is to produce a
complete job YAML (returned as JSON) that downstream tools will act on.

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
3. Set ``perform_assembly: true`` if and only if this data file is the
   last part of the sequence AND every part is present in the sibling
   listing.
4. If — and only if — ``perform_assembly`` is true AND the context file
   is rich enough to draft a refl1d model (substrate, layer stack, and
   ambient medium are identifiable), produce a ``create_model`` block
   that conforms to the create-model skill's states-driven config schema.
   Use sibling file paths (basenames) as they appear in the listing.
5. Always write a clear summary into ``metadata.notes``.

Reply with a single JSON object and nothing else (no prose, no code
fences). The JSON must conform to:

{
  "job": {
    "perform_analysis": true,
    "perform_assembly": bool,
    "create_model": { ... },     // OPTIONAL — include only when warranted
    "metadata": {"notes": "..."}
  },
  "sequence_id": str,            // used to name the output file
  "sequence_number": int,
  "sequence_complete": bool,
  "create_model_included": bool
}

The "create_model" block, when included, must follow the create-model
skill's states-driven schema exactly: top-level "describe", "states"
(list with "name" + "data" + optional "theta_offset" /
"sample_broadening" / "back_reflection" / "extra_description"),
"model_name", and any other documented keys. Do NOT add fields outside
the schema. Do NOT invent files that are not in the sibling listing.
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
    parts.append(
        "\n".join(sibling_files) if sibling_files else "(directory is empty)"
    )

    parts.append("\n--- Scientist's context file ---")
    parts.append(context_text.strip() or "(empty)")

    parts.append(
        "\nProduce the JSON object now. Reply with JSON only, no commentary."
    )
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
    )


# ---------------------------------------------------------------------------
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
    + ", ".join(_DEFAULT_SKILL_NAMES) + ".",
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
    skill_names = list(skill_overrides) if skill_overrides else list(
        _DEFAULT_SKILL_NAMES
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
    click.echo(
        f"Data file: {data_file.name}  (sibling files: {len(sibling_files)})"
    )

    try:
        result = call_planner_llm(user_message)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise click.ClickException(f"LLM planner failed: {exc}") from exc

    job = result.get("job") or {}
    if not isinstance(job, dict) or not job:
        raise click.ClickException(
            f"LLM did not return a 'job' object. Reply was: {result!r}"
        )

    sequence_id = result.get("sequence_id") or "unknown"
    sequence_number = result.get("sequence_number")
    sequence_complete = result.get("sequence_complete", False)
    create_model_included = result.get("create_model_included") or (
        "create_model" in job
    )

    click.echo(
        f"sequence_id={sequence_id}  sequence_number={sequence_number}  "
        f"complete={sequence_complete}"
    )
    click.echo(f"perform_assembly: {job.get('perform_assembly')}")
    click.echo(
        "create_model section: "
        + ("included." if create_model_included else "omitted.")
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"job_{sequence_id}.yaml"
    out_path.write_text(dump_job_yaml(job), encoding="utf-8")
    click.echo(f"Job YAML written to: {out_path}")
