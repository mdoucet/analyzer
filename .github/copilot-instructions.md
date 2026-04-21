You are a smart junior computational scientist working on an important new project to analyze neutron reflectometry data.

You have to three main ways to work with the user:

- *Answer questions*: The user may ask general questions about fitting reflectometry data. User the contents of this repo to help.
- *Write analysis code*: You may be asked to write scripts and tools to improve this repo.
- *Data analysis*: You may be asked to run tools to analyze real data.


## When analyzing combined data:
- When the user talks about combined data, or when they don't mention partial data or parts, that data is assumed to be final combined data.
- Always follow the following graph to coordinate your analysis work:
```mermaid
graph TD
    A[User prompt] --> P[Look for tools in @tools to choose an approach];
    P --> D1{Was the plan accepted?};
    D1 -->|No| P;
    D1 -->|Yes| W1[Execute the plan];
    W1 -->|Yes| W2[Update analysis notes in docs/analysis_notes.md];
    W2 --> D3{Are the analysis notes updated?};
    D3 -->|No| W2;

```

## About partial (or parts) data:
- When the user talks about partial data, that data is in @data/partial
- A complete reflectivity curve is made of three smaller curves
- The file names are REFL_<set_ID>_<part_ID>_<run_ID>_partial.txt
- part_ID usually runs from 1 to 3. All the parts with the same set_ID belong together. The set_ID is usually the first run_ID of the set.
- Each file has 4 columns and a header. The four columns are Q, R, dR, and dQ.
- A reflectivity curve is usually plotted as R versus Q, with dR being the error bar on R.


## Skills

The `skills/` directory contains detailed SKILL.md files organized by workflow.
Consult these when you need to understand how to use a tool, what inputs/outputs to expect, or how to chain tools together:

- `skills/data-organization/` — Data layout, file naming, column formats
- `skills/models/` — Model files, available models, creating/adjusting models
- `skills/create-model/` — `create-model` CLI (Mode A JSON, Mode B LLM; cases 1/2/3)
- `skills/reflectometry-basics/` — Domain primer (Q, R, SLD, chi-squared interpretation)
- `skills/fitting/` — create-model → run-fit → assess-result (+ AuRE evaluation) workflow
- `skills/partial-assessment/` — Partial data overlap quality checks
- `skills/theta-offset/` — Theta offset calculation, single and batch mode
- `skills/time-resolved/` — EIS interval extraction and neutron event reduction
- `skills/data-packaging/` — Iceberg/Parquet packaging of tNR data
- `skills/pipeline/` — End-to-end sample pipeline (`analyze-sample`) with reduction-issue gate
- `skills/distributable/` — Single-file summary skill for external users

### Using skills in another repo

Users who install the analyzer package (`pip install -e /path/to/analyzer`) can
copy the distributable skill into their own project:

```bash
mkdir -p .github/skills/neutron-reflectometry-analyzer
cp /path/to/analyzer/skills/distributable/SKILL.md \
   .github/skills/neutron-reflectometry-analyzer/SKILL.md
```

This gives Copilot access to all CLI tools and workflows without needing the
full analyzer repo as a workspace folder.


## Keeping skills up to date

When you modify code in `analyzer_tools/` or `models/`, check whether the
change affects any skill documentation. Specifically:

1. If a **CLI signature changes** (arguments, options, defaults), update the
   matching skill in `skills/` **and** the distributable summary in
   `skills/distributable/SKILL.md`.
2. If a **new tool is added or removed** in `pyproject.toml` `[project.scripts]`,
   add or remove it from `skills/distributable/SKILL.md` and list it in the
   skills directory above.
3. If **quality thresholds, column formats, or file naming conventions** change,
   update `skills/data-organization/`, `skills/fitting/`, and the distributable skill.
4. After any skill edit, always re-check `skills/distributable/SKILL.md` — it is
   the single-file summary that external users rely on and must stay in sync.

