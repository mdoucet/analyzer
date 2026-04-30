---
name: plan-data
description: >
  Generate a job YAML for a newly arriving partial reflectometry data file.
  The planner reads sequence_id / sequence_number from the file header or
  filename, scans the same directory for sibling parts, and — when the
  sequence is complete — uses an LLM to draft the create_model section from
  a scientist's Markdown context file.
  USE FOR: automating job-YAML creation the moment a new partial data file
  arrives at the instrument.
  DO NOT USE FOR: running fits, assessing results, or assembling combined
  curves (those steps follow from the generated job YAML).
---

# Skill: Data arrival planner (`plan-data`)

## Purpose

Every time a new partial data file (`REFL_{seq_id}_{seq_num}_{run_id}_partial.txt`)
arrives, `plan-data` decides whether the sequence is complete and produces a
**job YAML** that downstream tools (or a human) can act on.

```bash
plan-data DATA_FILE CONTEXT_FILE --output-dir DIR [--sequence-total N]
```

## How sequence identity is determined

1. The `Meta:` JSON line in the file header is parsed for `sequence_id` and
   `sequence_number`.
2. If either field is absent, the values are inferred from the filename:
   `REFL_{sequence_id}_{sequence_number}_{run_id}_partial.txt`.

## Assembly decision

`perform_assembly: true` is set **only** when **both** conditions hold:

- `sequence_number == sequence_total` (this is the last expected part), **and**
- all parts `1 … sequence_total` are found in the same directory as the input
  file.

If either condition fails, `perform_assembly: false` is emitted and no
`create_model` block is generated.

## LLM-drafted `create_model` section

When `perform_assembly` is true, the planner calls the configured LLM
(via `aure.llm`) to:

1. Assess whether the context file contains enough sample information to
   build a refl1d model.
2. If yes, draft a `create_model` YAML block with:
   - `describe`: sample description extracted/condensed from the context.
   - `states`: one state for the current sequence with `data:` file list,
     `theta_offset`, and `sample_broadening` flags.
   - `model_name`: short identifier.

If the LLM is not configured (`check-llm` returns an error) or judges the
context insufficient, the `create_model` key is omitted and a note is added
to `metadata.notes`.

Use `--no-llm` to skip LLM assessment entirely.

## Output

Written to `OUTPUT_DIR/job_<sequence_id>.yaml`:

```yaml
perform_analysis: true
perform_assembly: true   # or false

# Only present when perform_assembly=true and context is sufficient:
create_model:
  describe: |
    2 nm CuOx / 50 nm Cu / 3 nm Ti on Si in D2O (SLD ~6).
    Neutrons enter from the silicon side.
  states:
    - name: run_226642
      data:
        - REFL_226642_1_226642_partial.txt
        - REFL_226642_2_226643_partial.txt
        - REFL_226642_3_226644_partial.txt
      theta_offset: {init: 0.0, min: -0.02, max: 0.02}
      sample_broadening: true
  model_name: Cu-D2O-226642

metadata:
  notes: |
    Sequence 226642 is complete (3 parts present). <LLM summary…>
```

## Context file format

The context file (`context-sample5.md`) is a **free-form Markdown** note written
by the scientist. It should include at minimum:

- A sample description: substrate, layers (name + approximate thickness),
  ambient medium.
- Optionally: fitting approach notes, potential issues, questions.

Example:

```markdown
# Copper film

## Description
Deposited 50 nm copper on 3 nm titanium on silicon, in D2O.
Neutrons enter from the back of the sample.
Copper oxide likely present on the copper surface.

## Fitting approach
- Co-refine segments, not the combined data sets.
- Allow for sample broadening and angle offset.
```

The richer the description, the better the drafted `create_model` block.

## Using the output

The generated job YAML's `create_model` block is in the same shape accepted
by `create-model --config`. You can:

```bash
# Extract the create_model section and pass it to create-model:
create-model --config job_226642.yaml    # not directly — extract the block first

# Or pass the whole YAML to analyze-sample (if it also has states/describe):
analyze-sample job_226642.yaml
```

Alternatively, use the job YAML as a trigger record for a custom pipeline
that reads `perform_assembly` and conditionally calls `analyze-sample`.

## CLI reference

```
plan-data [OPTIONS] DATA_FILE CONTEXT_FILE

  DATA_FILE    — REFL_{seq_id}_{seq_num}_{run_id}_partial.txt
  CONTEXT_FILE — scientist's Markdown context note

Options:
  -o, --output-dir DIR        Output directory for the job YAML  [required]
  -n, --sequence-total N      Expected parts per complete sequence  [default: 3]
  --no-llm                    Skip LLM assessment step
  -h, --help                  Show this message and exit
```

## Sequence with a non-standard total

If your instrument produces 4-part sequences:

```bash
plan-data REFL_226642_4_226645_partial.txt context.md -o jobs/ --sequence-total 4
```
