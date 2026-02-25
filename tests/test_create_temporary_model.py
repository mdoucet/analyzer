import os
import pytest
from click.testing import CliRunner

from analyzer_tools.analysis.create_temporary_model import main


@pytest.fixture
def cleanup_files():
    """Clean up generated files after the test."""
    yield
    if os.path.exists("models/cu_thf_test.py"):
        os.remove("models/cu_thf_test.py")


def test_create_temporary_model(cleanup_files):
    """Test the create_temporary_model CLI using CliRunner."""
    runner = CliRunner()
    
    result = runner.invoke(main, [
        'cu_thf',
        'cu_thf_test',
        '--adjust',
        'Cu thickness 500,800',
    ])

    # Check command succeeded
    assert result.exit_code == 0, f"Command failed with output: {result.output}"
    
    # Check that the new model file was created
    assert os.path.exists("models/cu_thf_test.py")

    # Check that the parameter was changed
    with open("models/cu_thf_test.py", "r") as f:
        content = f.read()
        assert 'sample["Cu"].thickness.range(500.0, 800.0)' in content
