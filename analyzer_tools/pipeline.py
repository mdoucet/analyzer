"""
Analyzer pipeline orchestrator — sequential workflow for a single sample.

Reads a sample description (YAML frontmatter + markdown body) and runs:

    1. assess-partial         (if partial data is available)
    2. theta-offset           (optional, if requested)
    3. reduction-issue gate   (halts if blocking issues are found)
    4. create-model (AuRE)    (skippable if model= is provided)
    5. run-fit (AuRE)
    6. assess-result (+ aure evaluate)

Reduction is NEVER run automatically: if the gate trips, the pipeline writes
``reduction_issues.md`` and a pre-filled ``reduction_batch.yaml`` manifest
into the per-sample report directory and exits with a non-zero code.

Design: plain Python sequential, no LangChain. A tiny JSON state cache under
``<report_dir>/<set_id>/.pipeline_state.json`` lets users resume.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sample description (YAML frontmatter + markdown body)
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


@dataclass
class SampleSpec:
    """Parsed sample description driving the pipeline."""

    set_id: str
    description: str = ""
    data_file: Optional[str] = None
    partial_dir: Optional[str] = None
    model: Optional[str] = None
    theta_offset: Optional[Dict[str, Any]] = None
    hypothesis: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)


def parse_sample_file(path: str | os.PathLike) -> SampleSpec:
    """Parse a markdown file with YAML frontmatter into a :class:`SampleSpec`."""
    text = Path(path).read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        raise click.ClickException(
            f"Sample file '{path}' has no YAML frontmatter. "
            "Expected '---\\n<yaml>\\n---\\n<markdown body>'."
        )
    front_raw, body = m.group(1), m.group(2)
    front = yaml.safe_load(front_raw) or {}
    if "set_id" not in front:
        raise click.ClickException(
            f"Sample file '{path}' is missing required 'set_id' in YAML frontmatter."
        )
    # Pull out the known fields; keep the rest under extras for forward compat.
    known = {"set_id", "data_file", "partial_dir", "model", "theta_offset", "hypothesis"}
    extras = {k: v for k, v in front.items() if k not in known}
    return SampleSpec(
        set_id=str(front["set_id"]),
        description=body.strip(),
        data_file=front.get("data_file"),
        partial_dir=front.get("partial_dir"),
        model=front.get("model"),
        theta_offset=front.get("theta_offset"),
        hypothesis=front.get("hypothesis"),
        extras=extras,
    )


# ---------------------------------------------------------------------------
# State cache
# ---------------------------------------------------------------------------


@dataclass
class PipelineState:
    """Pipeline execution state persisted to disk for resume support."""

    set_id: str
    status: str = "running"  # running | ok | needs-reprocessing | failed
    completed_stages: List[str] = field(default_factory=list)
    stage_outputs: Dict[str, Any] = field(default_factory=dict)
    reduction_issues: List[Dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def save(self, path: str | os.PathLike) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: str | os.PathLike) -> Optional["PipelineState"]:
        p = Path(path)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        return cls(**data)


# ---------------------------------------------------------------------------
# Reduction-issue gate
# ---------------------------------------------------------------------------


def detect_reduction_issues(
    partial_metrics: Optional[Dict[str, Any]],
    theta_offsets: Optional[List[Dict[str, Any]]],
    *,
    chi2_threshold: float,
    offset_threshold_deg: float,
) -> List[Dict[str, Any]]:
    """Build the structured ``reduction_issues`` list from prior step outputs.

    Parameters
    ----------
    partial_metrics
        Output of ``partial_data_assessor.compute_metrics`` (may be ``None``).
    theta_offsets
        List of per-segment theta-offset results, each a dict with at least
        ``run`` and ``offset`` keys (may be ``None``).
    chi2_threshold
        Overlap χ² above which an issue is ``block`` severity.
    offset_threshold_deg
        |theta_offset| above which an issue is ``block`` severity.
    """
    issues: List[Dict[str, Any]] = []

    if partial_metrics:
        for pair in partial_metrics.get("overlaps", []):
            chi2 = pair["chi2"]
            if chi2 >= chi2_threshold:
                issues.append(
                    {
                        "type": "partial_overlap_chi2",
                        "segments": pair["parts"],
                        "severity": "block",
                        "chi2": chi2,
                        "threshold": chi2_threshold,
                        "detail": (
                            f"Overlap between parts {pair['parts'][0]} and "
                            f"{pair['parts'][1]} has chi^2={chi2:.2f} "
                            f"(> {chi2_threshold}). Likely bad normalization, "
                            "wrong direct-beam run, or misaligned segments."
                        ),
                    }
                )

    if theta_offsets:
        for entry in theta_offsets:
            offset = float(entry.get("offset", 0.0))
            if abs(offset) > offset_threshold_deg:
                issues.append(
                    {
                        "type": "theta_offset",
                        "run": entry.get("run"),
                        "severity": "block",
                        "offset_deg": offset,
                        "threshold_deg": offset_threshold_deg,
                        "detail": (
                            f"Computed theta offset {offset:+.4f}° exceeds "
                            f"threshold ±{offset_threshold_deg}°. Reduction "
                            "should be re-run with this offset applied."
                        ),
                    }
                )

    return issues


def should_halt(issues: List[Dict[str, Any]]) -> bool:
    """Return True if any issue has ``severity == 'block'``."""
    return any(i.get("severity") == "block" for i in issues)


def write_reduction_issues_md(
    path: str | os.PathLike,
    set_id: str,
    issues: List[Dict[str, Any]],
    partial_metrics: Optional[Dict[str, Any]],
    theta_offsets: Optional[List[Dict[str, Any]]],
) -> None:
    """Write a human-readable issues report."""
    lines: List[str] = [
        f"# Reprocessing required — set {set_id}",
        "",
        "The analyzer detected issues in the reduced data that prevent a",
        "meaningful fit. Please re-reduce the raw data and re-run the",
        "pipeline.",
        "",
        "## Detected issues",
        "",
    ]
    for i, issue in enumerate(issues, start=1):
        lines.append(f"### {i}. {issue['type']} ({issue['severity']})")
        lines.append("")
        lines.append(issue["detail"])
        lines.append("")

    if partial_metrics:
        lines.append("## Partial overlap χ² summary")
        lines.append("")
        for pair in partial_metrics.get("overlaps", []):
            lines.append(
                f"- Parts {pair['parts'][0]}↔{pair['parts'][1]}: "
                f"χ² = {pair['chi2']:.3f} ({pair['classification']})"
            )
        lines.append("")

    if theta_offsets:
        lines.append("## Theta-offset summary")
        lines.append("")
        for entry in theta_offsets:
            lines.append(
                f"- Run {entry.get('run', '?')}: offset = "
                f"{float(entry.get('offset', 0.0)):+.4f}°"
            )
        lines.append("")

    lines.extend(
        [
            "## How to proceed",
            "",
            "1. Review `reduction_batch.yaml` in this directory. It is pre-filled",
            "   with one `simple-reduction` job per segment.",
            "2. Edit any paths or options you need to adjust.",
            "3. Run the reductions:",
            "",
            "   ```bash",
            "   analyzer-batch reduction_batch.yaml",
            "   ```",
            "",
            "4. Re-run `analyze-sample` on the re-reduced data.",
            "",
            "## References",
            "",
            "- Theta-offset skill: `skills/theta-offset/SKILL.md`",
            "- Partial-data skill: `skills/partial-assessment/SKILL.md`",
            "",
        ]
    )
    Path(path).write_text("\n".join(lines))


def _build_reduction_batch_manifest(
    set_id: str,
    theta_offsets: Optional[List[Dict[str, Any]]],
    offset_log: Optional[str],
    template_xml: Optional[str],
) -> Dict[str, Any]:
    """Build an analyzer-batch-compatible manifest for re-reducing segments."""
    jobs: List[Dict[str, Any]] = []
    entries = theta_offsets or []
    if not entries:
        # Best-effort single job referencing the set_id. User will edit paths.
        entries = [{"run": set_id}]
    for entry in entries:
        run = entry.get("run", set_id)
        args: List[Any] = [
            "--event-file",
            f"REF_L_{run}.nxs.h5",
        ]
        if template_xml:
            args.extend(["--template", str(template_xml)])
        else:
            args.extend(["--template", f"REF_L_{set_id}_auto_template.xml"])
        if offset_log:
            args.extend(["--offset-csv", str(offset_log)])
        jobs.append(
            {
                "name": f"reduce_{run}",
                "tool": "simple-reduction",
                "args": args,
            }
        )
    return {"defaults": {"output_root": "./reduced"}, "jobs": jobs}


def write_reduction_batch_yaml(
    path: str | os.PathLike,
    set_id: str,
    theta_offsets: Optional[List[Dict[str, Any]]],
    *,
    offset_log: Optional[str] = None,
    template_xml: Optional[str] = None,
) -> None:
    """Write a reduction_batch.yaml manifest that the user can review and run."""
    manifest = _build_reduction_batch_manifest(
        set_id, theta_offsets, offset_log, template_xml
    )
    Path(path).write_text(
        "# Auto-generated by analyze-sample. Review before running:\n"
        "#   analyzer-batch reduction_batch.yaml\n\n"
        + yaml.safe_dump(manifest, sort_keys=False)
    )


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------


def _run_partial_assessment(
    spec: SampleSpec,
    partial_dir: str,
    reports_dir: str,
    *,
    chi2_threshold: float,
    llm_commentary: Optional[bool],
) -> Optional[Dict[str, Any]]:
    """Run assess-partial in-process; return structured metrics dict or None."""
    from analyzer_tools.analysis import partial_data_assessor as pda

    if not os.path.isdir(partial_dir):
        logger.info("No partial_dir '%s'; skipping partial assessment", partial_dir)
        return None
    files = pda.get_data_files(spec.set_id, partial_dir)
    if len(files) < 2:
        logger.info("Only %d partial files for set %s; skipping", len(files), spec.set_id)
        return None
    return pda.assess_data_set(
        spec.set_id,
        partial_dir,
        reports_dir,
        llm_commentary=llm_commentary,
        chi2_threshold=chi2_threshold,
    )


def _run_aure_analyze(
    spec: SampleSpec,
    data_file: str,
    results_dir: str,
    *,
    max_refinements: int,
    aure_executable: str = "aure",
) -> int:
    """Run ``aure analyze`` as a subprocess. Returns the exit code."""
    from analyzer_tools.analysis.run_fit import build_aure_command

    cmd = build_aure_command(
        data_file=data_file,
        sample_description=spec.description or spec.set_id,
        output_dir=results_dir,
        max_refinements=max_refinements,
        aure_executable=aure_executable,
    )
    logger.info("Running: %s", " ".join(shlex.quote(c) for c in cmd))
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def _run_result_assessment(
    spec: SampleSpec,
    results_dir: str,
    reports_dir: str,
    *,
    skip_aure_eval: bool,
) -> Dict[str, Any]:
    """Run assess_result in-process and return a summary dict."""
    from analyzer_tools.analysis import result_assessor as ra

    model_tag = spec.model or "aure"
    ra.assess_result(results_dir, spec.set_id, model_tag, reports_dir)

    evaluation = None
    if not skip_aure_eval:
        evaluation = ra.run_aure_evaluate(
            results_dir, context=spec.description, hypothesis=spec.hypothesis
        )
        if evaluation is not None:
            report_path = os.path.join(reports_dir, f"report_{spec.set_id}.md")
            ra.append_aure_section_to_report(report_path, evaluation)

    return {
        "results_dir": os.path.abspath(results_dir),
        "report": os.path.join(reports_dir, f"report_{spec.set_id}.md"),
        "aure_evaluation": evaluation,
    }


# ---------------------------------------------------------------------------
# Consolidated sample report
# ---------------------------------------------------------------------------


def write_sample_reports(
    report_dir: str,
    state: PipelineState,
    spec: SampleSpec,
) -> None:
    """Write sample_<id>.md and sample_<id>.json."""
    md_path = os.path.join(report_dir, f"sample_{spec.set_id}.md")
    json_path = os.path.join(report_dir, f"sample_{spec.set_id}.json")

    lines: List[str] = [f"# Sample {spec.set_id}", ""]
    if state.status == "needs-reprocessing":
        lines.append("> ⚠ **Reprocessing required** — see `reduction_issues.md`.")
        lines.append("")
    if spec.description:
        lines.append("## Sample description")
        lines.append("")
        lines.append(spec.description)
        lines.append("")

    lines.append("## Pipeline status")
    lines.append("")
    lines.append(f"- Status: **{state.status}**")
    lines.append(f"- Completed stages: {', '.join(state.completed_stages) or '(none)'}")
    lines.append("")

    if state.reduction_issues:
        lines.append("## Reduction issues")
        lines.append("")
        for issue in state.reduction_issues:
            lines.append(f"- **{issue['type']}** ({issue['severity']}): {issue['detail']}")
        lines.append("")

    stage_outputs = state.stage_outputs
    if "partial" in stage_outputs:
        pm = stage_outputs["partial"]
        lines.append("## Partial assessment")
        lines.append("")
        lines.append(f"- Worst χ²: {pm.get('worst_chi2', 'n/a')}")
        lines.append(f"- Report: `report_{spec.set_id}.md`")
        lines.append("")
    if "fit" in stage_outputs:
        lines.append("## Fit")
        lines.append("")
        lines.append(f"- Results: `{stage_outputs['fit'].get('results_dir')}`")
        lines.append("")
    if "assess" in stage_outputs:
        lines.append("## Assessment")
        lines.append("")
        assess = stage_outputs["assess"]
        lines.append(f"- Report: `{assess.get('report')}`")
        if assess.get("aure_evaluation"):
            verdict = assess["aure_evaluation"].get("verdict", "n/a")
            lines.append(f"- AuRE verdict: {verdict}")
        lines.append("")

    Path(md_path).write_text("\n".join(lines))
    Path(json_path).write_text(json.dumps({"spec": asdict(spec), "state": asdict(state)}, indent=2))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_pipeline(
    spec: SampleSpec,
    *,
    data_dir: str,
    partial_dir: str,
    results_root: str,
    reports_root: str,
    chi2_threshold: float = 3.0,
    offset_threshold_deg: float = 0.01,
    reduction_gate: bool = True,
    llm_commentary: Optional[bool] = None,
    skip_aure_eval: bool = False,
    max_refinements: int = 5,
    dry_run: bool = False,
    force: bool = False,
    skip_partial: bool = False,
    skip_fit: bool = False,
) -> PipelineState:
    """Run the analyzer pipeline for one sample.

    Returns the final :class:`PipelineState`.
    """
    report_dir = os.path.join(reports_root, f"sample_{spec.set_id}")
    os.makedirs(report_dir, exist_ok=True)
    state_path = os.path.join(report_dir, ".pipeline_state.json")

    existing = None if force else PipelineState.load(state_path)
    state = existing or PipelineState(set_id=spec.set_id)

    def _mark(stage: str, output: Any = None) -> None:
        if stage not in state.completed_stages:
            state.completed_stages.append(stage)
        if output is not None:
            state.stage_outputs[stage] = output
        state.save(state_path)

    def _done_stage(stage: str) -> bool:
        return stage in state.completed_stages

    # Resolve data file
    data_file = spec.data_file or os.path.join(
        data_dir, f"REFL_{spec.set_id}_combined_data_auto.txt"
    )
    effective_partial_dir = spec.partial_dir or partial_dir

    if dry_run:
        click.echo("Planned pipeline:")
        click.echo(f"  1. assess-partial (set {spec.set_id}) in {effective_partial_dir}")
        click.echo(f"  2. theta-offset (if configured): {spec.theta_offset or 'none'}")
        click.echo(f"  3. reduction-gate (chi2>{chi2_threshold}, |offset|>{offset_threshold_deg}°)")
        click.echo(f"  4. aure analyze {data_file} -o {os.path.join(results_root, f'{spec.set_id}_aure')}")
        click.echo(f"  5. assess-result + aure evaluate")
        click.echo(f"  6. Write reports under {report_dir}")
        state.status = "dry-run"
        return state

    # --- Stage 1: partial assessment -------------------------------------
    partial_metrics: Optional[Dict[str, Any]] = state.stage_outputs.get("partial")
    if not skip_partial and not _done_stage("partial"):
        partial_metrics = _run_partial_assessment(
            spec,
            effective_partial_dir,
            reports_root,
            chi2_threshold=chi2_threshold,
            llm_commentary=llm_commentary,
        )
        _mark("partial", partial_metrics)

    # --- Stage 2: theta-offset (only if explicitly requested) ------------
    theta_offsets: Optional[List[Dict[str, Any]]] = state.stage_outputs.get("theta")
    if spec.theta_offset and not _done_stage("theta"):
        # We only *record* theta offsets passed in the YAML (or previously
        # computed). Invoking the theta-offset tool requires raw NeXus files
        # which are outside the pipeline's scope; the user is expected to run
        # it ahead of time and paste results into the sample YAML, or pass
        # a precomputed CSV.
        to = spec.theta_offset
        if isinstance(to, list):
            theta_offsets = to
        elif isinstance(to, dict):
            theta_offsets = [to]
        else:
            theta_offsets = None
        _mark("theta", theta_offsets)

    # --- Stage 3: reduction-issue gate -----------------------------------
    issues: List[Dict[str, Any]] = []
    if reduction_gate:
        issues = detect_reduction_issues(
            partial_metrics,
            theta_offsets,
            chi2_threshold=chi2_threshold,
            offset_threshold_deg=offset_threshold_deg,
        )
        state.reduction_issues = issues

    if issues and should_halt(issues):
        state.status = "needs-reprocessing"
        write_reduction_issues_md(
            os.path.join(report_dir, "reduction_issues.md"),
            spec.set_id,
            issues,
            partial_metrics,
            theta_offsets,
        )
        write_reduction_batch_yaml(
            os.path.join(report_dir, "reduction_batch.yaml"),
            spec.set_id,
            theta_offsets,
        )
        write_sample_reports(report_dir, state, spec)
        state.finished_at = time.time()
        state.save(state_path)
        return state

    # --- Stage 4 + 5: create-model + run-fit via AuRE --------------------
    results_dir = os.path.join(results_root, f"{spec.set_id}_{spec.model or 'aure'}")
    if not skip_fit and not _done_stage("fit"):
        if shutil.which("aure") is None:
            logger.warning("AuRE CLI not available — cannot run fit stage.")
            state.status = "failed"
            state.stage_outputs["fit"] = {"error": "aure executable not found"}
            write_sample_reports(report_dir, state, spec)
            state.save(state_path)
            return state
        rc = _run_aure_analyze(
            spec,
            data_file,
            results_dir,
            max_refinements=max_refinements,
        )
        if rc != 0:
            state.status = "failed"
            state.stage_outputs["fit"] = {"exit_code": rc, "results_dir": results_dir}
            write_sample_reports(report_dir, state, spec)
            state.save(state_path)
            return state
        _mark("fit", {"results_dir": os.path.abspath(results_dir)})

    # --- Stage 6: assess-result + aure evaluate --------------------------
    if not skip_fit and not _done_stage("assess"):
        assess_out = _run_result_assessment(
            spec,
            results_dir,
            reports_root,
            skip_aure_eval=skip_aure_eval,
        )
        _mark("assess", assess_out)

    state.status = "ok"
    state.finished_at = time.time()
    write_sample_reports(report_dir, state, spec)
    state.save(state_path)
    return state


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.argument("sample", type=str)
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Directory with combined data. Defaults to config.ini.",
)
@click.option(
    "--partial-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Directory with partial data. Defaults to config.ini.",
)
@click.option(
    "--results-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Top-level results directory. Defaults to config.ini.",
)
@click.option(
    "--reports-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Top-level reports directory. Defaults to config.ini.",
)
@click.option("--reduction-gate/--no-reduction-gate", default=True, show_default=True)
@click.option("--chi2-threshold", type=float, default=3.0, show_default=True)
@click.option("--offset-threshold-deg", type=float, default=0.01, show_default=True)
@click.option("--llm-commentary/--no-llm-commentary", default=None)
@click.option("--skip-aure-eval", is_flag=True, default=False)
@click.option("-m", "--max-refinements", type=int, default=5, show_default=True)
@click.option("--skip-partial", is_flag=True, default=False)
@click.option("--skip-fit", is_flag=True, default=False)
@click.option("--force", is_flag=True, default=False, help="Ignore cached pipeline state.")
@click.option("--dry-run", is_flag=True, default=False)
def main(
    sample: str,
    data_dir: Optional[str],
    partial_dir: Optional[str],
    results_dir: Optional[str],
    reports_dir: Optional[str],
    reduction_gate: bool,
    chi2_threshold: float,
    offset_threshold_deg: float,
    llm_commentary: Optional[bool],
    skip_aure_eval: bool,
    max_refinements: int,
    skip_partial: bool,
    skip_fit: bool,
    force: bool,
    dry_run: bool,
) -> None:
    """Run the analyzer pipeline for a single sample.

    SAMPLE is either a path to a markdown file (YAML frontmatter + body) or
    a bare set ID (auto-discovers data using config.ini defaults).
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from analyzer_tools.config_utils import get_config

    cfg = get_config()
    data_dir = data_dir or cfg.get_combined_data_dir()
    partial_dir = partial_dir or cfg.get_partial_data_dir()
    results_dir = results_dir or cfg.get_results_dir()
    reports_dir = reports_dir or cfg.get_reports_dir()

    if os.path.isfile(sample):
        spec = parse_sample_file(sample)
    else:
        spec = SampleSpec(set_id=str(sample))

    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    state = run_pipeline(
        spec,
        data_dir=data_dir,
        partial_dir=partial_dir,
        results_root=results_dir,
        reports_root=reports_dir,
        chi2_threshold=chi2_threshold,
        offset_threshold_deg=offset_threshold_deg,
        reduction_gate=reduction_gate,
        llm_commentary=llm_commentary,
        skip_aure_eval=skip_aure_eval,
        max_refinements=max_refinements,
        dry_run=dry_run,
        force=force,
        skip_partial=skip_partial,
        skip_fit=skip_fit,
    )

    click.echo(f"Pipeline status: {state.status}")
    if state.status == "needs-reprocessing":
        click.echo(
            f"See {os.path.join(reports_dir, f'sample_{spec.set_id}', 'reduction_issues.md')}",
            err=True,
        )
        sys.exit(3)
    if state.status == "failed":
        sys.exit(2)


if __name__ == "__main__":
    main()
