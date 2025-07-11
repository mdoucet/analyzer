import pytest
import os
import tempfile
import shutil
from unittest.mock import patch
from analyzer_tools import partial_data_assessor

class TestPartialDataAssessor:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.reports_dir = os.path.join(self.test_dir, 'reports')
        os.makedirs(self.reports_dir)

    def teardown_method(self):
        shutil.rmtree(self.test_dir)

    @patch('matplotlib.pyplot.savefig')
    def test_assess_data_set_creates_report_with_metrics(self, mock_savefig):
        # Arrange
        set_id = '218281'
        data_dir = os.path.abspath('tests/sample_data/partial')

        # Act
        partial_data_assessor.assess_data_set(set_id, data_dir, self.reports_dir)

        # Assert
        report_path = os.path.join(self.reports_dir, f'report_{set_id}.md')
        assert os.path.exists(report_path)

        with open(report_path, 'r') as f:
            report_content = f.read()

        assert "## Partial Data Assessment" in report_content
        assert "### Overlap Metrics (Chi-squared)" in report_content
        assert "Overlap 1" in report_content
        assert "Overlap 2" in report_content
        
        # Check that the plot was created
        mock_savefig.assert_called_once()

if __name__ == "__main__":
    pytest.main()
