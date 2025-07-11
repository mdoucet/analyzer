import pytest
import os
import tempfile
import shutil
import numpy as np
from unittest.mock import patch, MagicMock
from analyzer_tools import result_assessor

class TestResultAssessor:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.reports_dir = os.path.join(self.test_dir, 'reports')
        os.makedirs(self.reports_dir)

    def teardown_method(self):
        shutil.rmtree(self.test_dir)

    @patch('matplotlib.pyplot.savefig')
    @patch('analyzer_tools.utils.summary_plots.plot_sld')
    def test_assess_result_creates_files_and_report(self, mock_plot_sld, mock_savefig):
        # Arrange
        set_id = '123'
        model_name = 'test_model'
        fit_results_dir = os.path.join(self.test_dir, 'fit_results')
        os.makedirs(fit_results_dir)

        # Create dummy data files
        refl_data = np.array([[1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [0.1, 0.1, 0.1, 0.1, 0.1], [1, 2, 3, 4, 5]]).T
        np.savetxt(os.path.join(fit_results_dir, 'test-refl.dat'), refl_data)
        profile_data = np.array([[1,2],[3,4]])
        np.savetxt(os.path.join(fit_results_dir, 'problem-1-profile.dat'), profile_data)

        # Act
        result_assessor.assess_result(fit_results_dir, set_id, model_name, self.reports_dir)

        # Assert
        report_path = os.path.join(self.reports_dir, f'report_{set_id}.md')
        assert os.path.exists(report_path)

        with open(report_path, 'r') as f:
            report_content = f.read()

        assert f'## Fit results for {model_name}' in report_content
        assert 'Chi-squared' in report_content
        assert f'![Fit result](fit_result_{set_id}_{model_name}_reflectivity.svg)' in report_content
        assert f'![SLD profile](fit_result_{set_id}_{model_name}_profile.svg)' in report_content

        assert mock_savefig.call_count == 2
        mock_plot_sld.assert_called_once()

if __name__ == "__main__":
    pytest.main()
