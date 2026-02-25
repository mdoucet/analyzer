import pytest
import os
import tempfile
import shutil
from analyzer_tools.analysis.create_model_script import create_fit_script

class TestCreateModelScript:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_create_fit_script(self):
        model_name = 'cu_thf'
        data_file = os.path.abspath(os.path.join(self.original_dir, 'tests/sample_data/REFL_218281_combined_data_auto.txt'))
        model_file_source = os.path.abspath(os.path.join(self.original_dir, 'models', f'{model_name}.py'))
        
        os.mkdir('models')
        shutil.copy(model_file_source, 'models')

        create_fit_script(model_name, data_file)
        
        set_id = '218281'
        output_filename = f'model_{set_id}_{model_name}.py'
        
        assert os.path.exists(output_filename)
        
        with open(output_filename, 'r') as f:
            content = f.read()
        
        with open(os.path.join('models', f'{model_name}.py'), 'r') as f:
            model_content = f.read()

        expected_content = f'''import numpy as np

{model_content}
_refl = np.loadtxt("{data_file}").T
experiment = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])
problem = FitProblem(experiment)
'''
        assert content == expected_content

