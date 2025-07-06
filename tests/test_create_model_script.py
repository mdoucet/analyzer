import pytest
import os
import tempfile
import shutil
from tools.create_model_script import create_fit_script

class TestCreateModelScript:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.test_dir)

    def test_create_fit_script(self):
        model_name = 'dummy_model'
        data_file = os.path.abspath('tests/sample_data/REFL_218281_combined_data_auto.txt')
        model_dir = os.path.abspath('tests/sample_models')
        set_id = '218281'
        
        create_fit_script(model_name, data_file, model_dir=model_dir, output_dir=self.test_dir)
        
        output_filename = f'model_{set_id}_{model_name}.py'
        output_path = os.path.join(self.test_dir, output_filename)
        
        assert os.path.exists(output_path)
        
        with open(output_path, 'r') as f:
            content = f.read()
        
        with open(os.path.join(model_dir, f'{model_name}.py'), 'r') as f:
            model_content = f.read()

        expected_content = f'''import numpy as np

{model_content}
_refl = np.loadtxt("{data_file}").T
experiment = create_fit_experiment(_refl[0], _refl[3], _refl[1], _refl[2])
problem = FitProblem(experiment)
'''
        assert content == expected_content

