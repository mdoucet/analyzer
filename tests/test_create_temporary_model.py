import os
import subprocess
import pytest

from models import cu_thf

@pytest.fixture
def cleanup_files():
    """Clean up generated files after the test."""
    yield
    if os.path.exists("models/cu_thf_test.py"):
        os.remove("models/cu_thf_test.py")

def test_create_temporary_model(cleanup_files):
    """
    Test the create_temporary_model.py script.
    """
    base_model = "cu_thf"
    new_model = "cu_thf_test"
    adjustments = ["Cu", "thickness", "500,800"]

    # Run the script
    subprocess.run(
        [
            "python3",
            "tools/create_temporary_model.py",
            base_model,
            new_model,
            "--adjust",
        ]
        + adjustments,
        check=True,
    )

    # Check that the new model file was created
    assert os.path.exists(f"models/{new_model}.py")

    # Check that the parameter was changed
    with open(f"models/{new_model}.py", "r") as f:
        content = f.read()
        assert 'sample["Cu"].thickness.range(500.0, 800.0)' in content
