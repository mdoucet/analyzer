import pytest
import numpy as np
import tempfile
import os
from analyzer_tools.planner.instrument import InstrumentSimulator, load_measurement


@pytest.fixture
def simulator():
    """Default simulator with standard parameters."""
    return InstrumentSimulator()


@pytest.fixture
def custom_simulator():
    """Simulator with custom Q values."""
    q_values = np.linspace(0.01, 0.5, 50)
    return InstrumentSimulator(q_values=q_values, relative_error=0.05)


@pytest.fixture
def sample_data_file():
    """Create a temporary data file for testing."""
    # Create test data: Q, R, dR, dQ
    q = np.linspace(0.01, 0.2, 20)
    r = np.exp(-q * 10)
    dr = 0.1 * r
    dq = 0.025 * q
    
    data = np.column_stack([q, r, dr, dq])
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.dat') as f:
        np.savetxt(f, data)
        temp_filename = f.name
    
    yield temp_filename
    
    # Cleanup
    os.unlink(temp_filename)


class TestInstrumentSimulator:
    """Test the InstrumentSimulator class."""
    
    def test_default_initialization(self):
        """Test default initialization of InstrumentSimulator."""
        simulator = InstrumentSimulator()
        
        assert simulator.q_values is not None
        assert len(simulator.q_values) == 50  # Default size
        assert simulator.q_values[0] == pytest.approx(0.008, rel=1e-3)
        assert simulator.q_values[-1] == pytest.approx(0.2, rel=1e-3)
        assert len(simulator.dq_values) == len(simulator.q_values)
        assert len(simulator.relative_errors) == len(simulator.q_values)
        assert np.all(simulator.relative_errors == 0.10)  # Default relative error
    
    def test_custom_q_values_initialization(self):
        """Test initialization with custom Q values."""
        q_values = np.linspace(0.01, 0.5, 30)
        relative_error = 0.05
        dq = 0.03
        
        simulator = InstrumentSimulator(
            q_values=q_values, 
            dq_values=dq, 
            relative_error=relative_error
        )
        
        assert len(simulator.q_values) == 30
        assert np.array_equal(simulator.q_values, q_values)
        assert np.all(simulator.dq_values == dq)
        assert np.all(simulator.relative_errors == relative_error)
    
    def test_array_dq_values_initialization(self):
        """Test initialization with array of dQ values."""
        q_values = np.linspace(0.01, 0.5, 10)
        dq_values = np.linspace(0.01, 0.05, 10)
        
        simulator = InstrumentSimulator(q_values=q_values, dq_values=dq_values)
        
        assert np.array_equal(simulator.dq_values, dq_values)
    
    def test_invalid_dq_array_length(self):
        """Test that mismatched dQ array length raises error."""
        q_values = np.linspace(0.01, 0.5, 10)
        dq_values = np.linspace(0.01, 0.05, 5)  # Wrong length
        
        with pytest.raises(ValueError, match="operands could not be broadcast together"):
            InstrumentSimulator(q_values=q_values, dq_values=dq_values)
    
    def test_default_initialization_with_array_dq(self):
        """Test default initialization with array dQ values."""
        # Test with valid array dQ values (should work)
        dq_values = np.linspace(0.001, 0.005, 50)  # 50 values to match default q_values
        simulator = InstrumentSimulator(dq_values=dq_values)
        
        assert len(simulator.q_values) == 50
        assert np.array_equal(simulator.dq_values, dq_values)
        
        # Test with invalid array dQ values (wrong length)
        dq_values_wrong = np.linspace(0.001, 0.005, 30)  # Wrong length
        with pytest.raises(ValueError, match="dq_values array must match length of q_values"):
            InstrumentSimulator(dq_values=dq_values_wrong)
    
    def test_data_file_initialization(self, sample_data_file):
        """Test initialization from data file."""
        simulator = InstrumentSimulator(data_file=sample_data_file)
        
        assert simulator.q_values is not None
        assert len(simulator.q_values) == 20  # Number of points in test data
        assert simulator.relative_errors is not None
        assert len(simulator.relative_errors) == len(simulator.q_values)
    
    def test_add_noise_basic(self, simulator):
        """Test basic noise addition functionality."""
        reflectivity = np.ones(50) * 0.5  # Constant reflectivity
        
        noisy_reflectivity, errors = simulator.add_noise(reflectivity)
        
        assert len(noisy_reflectivity) == len(reflectivity)
        assert len(errors) == len(reflectivity)
        assert np.all(errors > 0), "Errors should be positive"
        
        # Check that errors are proportional to reflectivity
        expected_errors = simulator.relative_errors * reflectivity
        np.testing.assert_array_almost_equal(errors, expected_errors)
    
    def test_add_noise_creates_variation(self, simulator):
        """Test that noise addition creates variation in data."""
        reflectivity = np.ones(50) * 0.1
        
        # Run multiple times to check randomness
        results = []
        for _ in range(10):
            noisy_reflectivity, _ = simulator.add_noise(reflectivity)
            results.append(noisy_reflectivity)
        
        # Check that results are different (with high probability)
        results = np.array(results)
        assert np.std(results) > 0, "Noise should create variation between runs"
    
    def test_add_noise_different_error_levels(self):
        """Test that different relative errors produce different noise levels."""
        q_values = np.linspace(0.01, 0.2, 20)
        reflectivity = np.ones(20) * 0.1
        
        # Low noise simulator
        sim_low = InstrumentSimulator(q_values=q_values, relative_error=0.01)
        noisy_low, errors_low = sim_low.add_noise(reflectivity)
        
        # High noise simulator
        sim_high = InstrumentSimulator(q_values=q_values, relative_error=0.20)
        noisy_high, errors_high = sim_high.add_noise(reflectivity)
        
        assert np.mean(errors_high) > np.mean(errors_low), "Higher relative error should give larger errors"
    
    def test_add_noise_zero_reflectivity(self, simulator):
        """Test noise addition with zero reflectivity values."""
        reflectivity = np.zeros(50)
        
        noisy_reflectivity, errors = simulator.add_noise(reflectivity)
        
        assert len(noisy_reflectivity) == len(reflectivity)
        assert len(errors) == len(reflectivity)
        assert np.all(errors == 0), "Errors should be zero when reflectivity is zero"


class TestLoadMeasurement:
    """Test the load_measurement function."""
    
    def test_load_measurement_valid_file(self, sample_data_file):
        """Test loading a valid measurement file."""
        data = load_measurement(sample_data_file)
        
        assert "q" in data
        assert "R" in data
        assert "dR" in data
        assert "dq" in data
        
        assert len(data["q"]) == 20
        assert len(data["R"]) == 20
        assert len(data["dR"]) == 20
        assert len(data["dq"]) == 20
    
    def test_load_measurement_invalid_columns(self):
        """Test loading file with insufficient columns."""
        # Create file with only 2 columns
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.dat') as f:
            data = np.column_stack([np.linspace(0.01, 0.2, 10), np.ones(10)])
            np.savetxt(f, data)
            temp_filename = f.name
        
        try:
            with pytest.raises(ValueError, match="Data file must have at least 4 columns"):
                load_measurement(temp_filename)
        finally:
            os.unlink(temp_filename)
    
    def test_load_measurement_nonexistent_file(self):
        """Test loading a nonexistent file."""
        with pytest.raises(OSError):
            load_measurement("nonexistent_file.dat")


# Test edge cases and error conditions
class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_simulator_consistency(self):
        """Test that simulator properties are consistent."""
        simulator = InstrumentSimulator()
        
        assert len(simulator.q_values) == len(simulator.dq_values)
        assert len(simulator.q_values) == len(simulator.relative_errors)
    
    def test_reproducible_noise_with_seed(self):
        """Test that noise is reproducible with fixed random seed."""
        simulator = InstrumentSimulator()
        reflectivity = np.ones(50) * 0.1
        
        # Set seed and generate noise
        np.random.seed(42)
        noisy1, errors1 = simulator.add_noise(reflectivity)
        
        # Reset seed and generate again
        np.random.seed(42)
        noisy2, errors2 = simulator.add_noise(reflectivity)
        
        np.testing.assert_array_equal(noisy1, noisy2)
        np.testing.assert_array_equal(errors1, errors2)