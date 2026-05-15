"""Tests for ``simple-reduction``'s --state-in / --state-out flags.

The full reduction requires mantid + lr_reduction, which aren't always
available in the test environment. These tests focus on the CLI plumbing
around the state: argument resolution and error messages. They stop
short of running mantid by validating the CLI surface up to (and
including) the path-existence checks.
"""

from __future__ import annotations

from click.testing import CliRunner

from analyzer_tools.reduction.reduction import main as simple_reduction


def test_no_event_file_no_state_in_errors():
    runner = CliRunner()
    result = runner.invoke(simple_reduction, [])
    assert result.exit_code != 0
    assert "event-file" in result.output.lower()


def test_state_in_supplies_event_file_and_template(tmp_path):
    from analyzer_tools.state import empty_state, save_state

    event = tmp_path / "REF_L_226644.nxs.h5"
    event.write_bytes(b"")  # existence is what we check
    template = tmp_path / "template.xml"
    template.write_text("<template/>")

    state = empty_state()
    state["paths"]["event_file"] = str(event)
    state["paths"]["template_file"] = str(template)
    state["paths"]["output_directory"] = str(tmp_path / "out")
    state_path = tmp_path / "state.json"
    save_state(state, str(state_path))

    runner = CliRunner()
    result = runner.invoke(simple_reduction, ["--state-in", str(state_path)])

    # We don't expect to reach the actual reduction here (mantid may not be
    # installed). What we DO require is that argument resolution succeeded
    # — i.e. the CLI didn't bail with a "missing --event-file / --template"
    # UsageError.
    assert "event-file is required" not in result.output
    assert "template is required" not in result.output


def test_state_in_with_missing_event_file_path_errors(tmp_path):
    from analyzer_tools.state import empty_state, save_state

    state = empty_state()
    state["paths"]["event_file"] = str(tmp_path / "does-not-exist.h5")
    state["paths"]["template_file"] = str(tmp_path / "also-missing.xml")
    state_path = tmp_path / "state.json"
    save_state(state, str(state_path))

    runner = CliRunner()
    result = runner.invoke(simple_reduction, ["--state-in", str(state_path)])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_state_in_input_file_fallback(tmp_path):
    """If state has paths.input_file but no paths.event_file, use it."""
    from analyzer_tools.state import empty_state, save_state

    event = tmp_path / "REF_L_226644.nxs.h5"
    event.write_bytes(b"")
    template = tmp_path / "template.xml"
    template.write_text("<template/>")

    state = empty_state()
    state["paths"]["input_file"] = str(event)  # event_file deliberately absent
    state["paths"]["template_file"] = str(template)
    state_path = tmp_path / "state.json"
    save_state(state, str(state_path))

    runner = CliRunner()
    result = runner.invoke(simple_reduction, ["--state-in", str(state_path)])
    assert "event-file is required" not in result.output


def test_cli_event_file_overrides_state_in(tmp_path):
    """An explicit --event-file wins over --state-in."""
    from analyzer_tools.state import empty_state, save_state

    explicit = tmp_path / "explicit.h5"
    explicit.write_bytes(b"")
    template = tmp_path / "template.xml"
    template.write_text("<template/>")

    state = empty_state()
    state["paths"]["event_file"] = str(tmp_path / "different.h5")
    state["paths"]["template_file"] = str(template)
    state_path = tmp_path / "state.json"
    save_state(state, str(state_path))

    runner = CliRunner()
    result = runner.invoke(
        simple_reduction,
        ["--event-file", str(explicit), "--state-in", str(state_path)],
    )
    # CLI value wins; we don't get a "does not exist" error for either path.
    assert "does not exist" not in result.output
