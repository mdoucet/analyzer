"""
Tests for analyzer_tools.planner module.

Addresses PR review comments 6-9 with proper test structure, assertions,
and comprehensive error handling tests.
"""

import numpy as np
import pytest
from unittest.mock import patch

from analyzer_tools.utils.model_utils import expt_from_model_file
from analyzer_tools.planner.experiment_design import ExperimentDesigner
from analyzer_tools.planner import instrument, optimizer


class TestExperimentDesigner:
    """Test the ExperimentDesigner class."""

    @pytest.fixture
    def basic_experiment(self):
        """Create a basic experiment for testing."""
        # Create Q values - deterministic for reproducible tests
        q_values = np.logspace(np.log10(0.008), np.log10(0.2), 10)
        dq_values = q_values * 0.025

        model_name = "models/cu_thf_planner"
        experiment = expt_from_model_file(model_name, q_values, dq_values)
        return experiment

    @pytest.fixture
    def designer(self, basic_experiment):
        """Create an ExperimentDesigner instance."""
        simulator = instrument.InstrumentSimulator(
            q_values=np.logspace(np.log10(0.008), np.log10(0.2), 10)
        )
        return ExperimentDesigner(basic_experiment, simulator=simulator)

    def test_experiment_designer_initialization(self, designer):
        """Test that ExperimentDesigner initializes correctly."""
        assert designer is not None
        assert len(designer.parameters) > 0
        assert designer.all_model_parameters is not None

    def test_get_parameters(self, designer):
        """Test that get_parameters returns valid parameter dict."""
        params = designer.get_parameters()
        assert isinstance(params, dict)
        assert len(params) > 0

        # Check that all parameters have required attributes
        for name, param in params.items():
            assert hasattr(param, "name")
            assert hasattr(param, "value")
            assert hasattr(param, "bounds")
            assert hasattr(param, "is_of_interest")

    def test_prior_entropy_calculation(self, designer):
        """Test that prior entropy calculation works and returns positive value."""
        h_prior = designer.prior_entropy()
        assert isinstance(h_prior, float)
        assert h_prior > 0  # Entropy should be positive

    def test_model_parameters_to_dict(self, designer):
        """Test that model parameters dictionary is created correctly."""
        model_params = designer._model_parameters_to_dict()
        assert isinstance(model_params, dict)
        assert len(model_params) > 0

        # Should contain the THF rho parameter we'll use in tests
        assert "THF rho" in model_params

    def test_set_parameter_to_optimize_valid(self, designer):
        """Test setting a valid parameter for optimization."""
        # THF rho is a known parameter in the cu_thf_planner model
        original_value = designer.all_model_parameters["THF rho"].value
        new_value = 5.0

        designer.set_parameter_to_optimize("THF rho", new_value)

        # Check that the parameter value was updated
        assert designer.all_model_parameters["THF rho"].value == new_value
        assert designer.all_model_parameters["THF rho"].value != original_value

    def test_set_parameter_to_optimize_invalid_parameter(self, designer):
        """Test error handling for invalid parameter names."""
        with pytest.raises(
            ValueError,
            match="Parameter nonexistent_param not found in model parameters",
        ):
            designer.set_parameter_to_optimize("nonexistent_param", 1.0)

    def test_optimize_edge_case_empty_param_values(self, designer):
        """Test optimize method with empty parameter values list."""
        designer.set_parameter_to_optimize("THF rho", 5.0)

        # With empty param_values, should return empty results
        results, _ = optimizer.optimize(
            designer, param_to_optimize="THF rho", param_values=[], realizations=1
        )

        # Should return empty list
        assert results == []

    def test_optimize_edge_case_invalid_parameter(self, designer):
        """Test optimize method with invalid parameter to optimize."""
        with pytest.raises(ValueError):
            optimizer.optimize(
                designer,
                param_to_optimize="INVALID_PARAM",
                param_values=[1.0, 2.0],
                realizations=1,
            )

    def test_optimize_edge_case_zero_realizations(self, designer):
        """Test optimize method with zero realizations."""
        designer.set_parameter_to_optimize("THF rho", 5.0)

        # With zero realizations, should complete but return NaN values
        results, simulated_data = optimizer.optimize(
            designer,
            param_to_optimize="THF rho",
            param_values=[1.0, 2.0],
            realizations=0,
        )

        # Should return results but with NaN information gain
        assert len(results) == 2
        for param_val, info_gain, std_info_gain in results:
            assert isinstance(param_val, (int, float))
            assert np.isnan(info_gain)  # Should be NaN due to mean of empty list

    @patch("numpy.random.normal")  # Mock random to make test deterministic
    def test_optimize_basic_functionality(self, mock_random, designer):
        """Test basic optimize functionality with mocked randomness."""
        # Set up deterministic random behavior
        mock_random.return_value = np.zeros(len(designer.simulator.q_values))

        designer.set_parameter_to_optimize("THF rho", 5.0)

        # Run optimization with minimal parameters for speed
        results, simulated_data = optimizer.optimize(
            designer,
            param_to_optimize="THF rho",
            param_values=[4.5, 5.0],
            realizations=1,  # Minimal realizations for test speed
        )

        # Check that results are returned in expected format
        assert isinstance(results, list)
        assert isinstance(simulated_data, list)
        assert len(results) == 2  # Should have results for both values

        for param_val, info_gain, std_info_gain in results:
            assert isinstance(param_val, (int, float))
            assert isinstance(info_gain, (int, float))
            assert isinstance(std_info_gain, (int, float))


class TestExptFromModelFile:
    """Test the expt_from_model_file function for error handling."""

    def test_expt_from_model_file_valid_input(self):
        """Test that expt_from_model_file works with valid input."""
        q_values = np.array([0.01, 0.05, 0.1])
        dq_values = q_values * 0.025
        model_name = "models/cu_thf_tiny"

        experiment = expt_from_model_file(model_name, q_values, dq_values)
        assert experiment is not None
        assert hasattr(experiment, "sample")
        assert hasattr(experiment, "probe")

    def test_expt_from_model_file_nonexistent_file(self):
        """Test error handling for non-existent model files."""
        q_values = np.array([0.01, 0.05, 0.1])
        dq_values = q_values * 0.025

        with pytest.raises((FileNotFoundError, ImportError)):
            expt_from_model_file("models/non_existent_model", q_values, dq_values)

    def test_expt_from_model_file_empty_q_values(self):
        """Test error handling for empty q_values array."""
        q_values = np.array([])
        dq_values = np.array([])
        model_name = "models/cu_thf_tiny"

        # This should raise an error or handle gracefully
        # The exact error depends on the downstream refl1d implementation
        with pytest.raises((ValueError, IndexError)):
            expt_from_model_file(model_name, q_values, dq_values)

    def test_expt_from_model_file_mismatched_arrays(self):
        """Test error handling for q_values and dq_values of different lengths."""
        q_values = np.array([0.01, 0.05])
        dq_values = np.array([0.001])  # Different length
        model_name = "models/cu_thf_tiny"

        # The current implementation may handle this gracefully by broadcasting
        # or it may raise an error - test what actually happens
        try:
            experiment = expt_from_model_file(model_name, q_values, dq_values)
            # If it succeeds, verify the arrays were handled somehow
            assert experiment is not None
            print("✓ Mismatched arrays handled gracefully")
        except (ValueError, IndexError, TypeError) as e:
            # If it raises an error, that's also acceptable behavior
            print(f"✓ Mismatched arrays properly rejected: {type(e).__name__}")
            raise

    def test_expt_from_model_file_with_reflectivity_data(self):
        """Test expt_from_model_file with optional reflectivity and errors."""
        q_values = np.array([0.01, 0.05, 0.1])
        dq_values = q_values * 0.025
        reflectivity = np.array([1.0, 0.5, 0.1])
        errors = np.array([0.01, 0.01, 0.01])
        model_name = "models/cu_thf_tiny"

        experiment = expt_from_model_file(
            model_name, q_values, dq_values, reflectivity, errors
        )
        assert experiment is not None
        assert hasattr(experiment.probe, "R")
        assert hasattr(experiment.probe, "dR")
        np.testing.assert_array_equal(experiment.probe.R, reflectivity)
        np.testing.assert_array_equal(experiment.probe.dR, errors)


class TestPlannerIntegration:
    """Integration tests to ensure planner components work together."""

    def test_full_workflow_minimal(self):
        """Test a minimal complete workflow to ensure no breaking changes."""
        # Create a minimal experiment
        q_values = np.logspace(np.log10(0.008), np.log10(0.2), 5)  # Smaller for speed
        dq_values = q_values * 0.025

        model_name = "models/cu_thf_tiny"
        experiment = expt_from_model_file(model_name, q_values, dq_values)

        # Create designer
        simulator = instrument.InstrumentSimulator()
        designer = ExperimentDesigner(experiment, simulator=simulator)

        # Test basic operations
        assert designer.prior_entropy() > 0

        # Test parameter setting
        designer.set_parameter_to_optimize("THF rho", 5.0)

        # Verify the parameter was set
        assert designer.all_model_parameters["THF rho"].value == 5.0

        print("✓ Full workflow test completed successfully")
