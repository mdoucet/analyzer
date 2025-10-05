import time
import numpy as np
from typing import Dict, Optional, Tuple


class InstrumentSimulator:
    """
    Class to simulate instrumental effects on reflectivity data.
    """

    def __init__(
        self,
        data_file: Optional[str] = None,
        q_values: Optional[np.ndarray] = None,
        dq_values: Optional[np.ndarray | float] = 0.025,
        relative_error: float = 0.10,
    ):
        self.q_values = q_values
        self.dq_values = dq_values

        if data_file:
            # Load example data to get Q values and errors
            data = load_measurement(data_file)
            self.q_values = data["q"]
            self.dq_values = data["dq"]
            print(type(data["R"]))
            self.relative_errors = np.where(
                data["R"] == 0, relative_error, data["dR"] / data["R"]
            )
            self.relative_errors[self.relative_errors <= 0] = relative_error
        elif q_values is not None:
            self.q_values = q_values
            self.dq_values = dq_values * np.ones(len(self.q_values))
            self.relative_errors = relative_error * np.ones(len(self.q_values))
        else:
            self.q_values = np.logspace(np.log10(0.008), np.log10(0.2), 50)

            if isinstance(self.dq_values, np.ndarray):
                if len(self.dq_values) != len(self.q_values):
                    raise ValueError("dq_values array must match length of q_values")
                self.dq_values = self.dq_values
            elif isinstance(self.dq_values, (int, float)):
                self.dq_values = self.dq_values * np.ones(len(self.q_values))

            self.relative_errors = relative_error * np.ones(len(self.q_values))

        assert len(self.q_values) == len(self.dq_values) == len(self.relative_errors), (
            "q_values, dq_values, and relative_errors must have the same length"
        )

    def add_noise(
        self,
        reflectivity: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        errors = self.relative_errors * reflectivity

        # Add Gaussian noise
        noise = np.random.normal(0, errors)
        noisy_reflectivity = reflectivity + noise

        return noisy_reflectivity, errors


def load_measurement(filename: str) -> Dict[str, np.ndarray]:
    """
    Load measurement data from a file.

    Args:
        filename: Path to the data file (expects 3 columns: Q, R, dR, dQ)
    Returns:
        Dictionary with keys 'q_values', 'reflectivity', 'errors'
    """
    data = np.loadtxt(filename)
    if data.shape[1] < 4:
        raise ValueError("Data file must have at least 4 columns: Q, R, dR, dQ")
    return {
        "q": data[:, 0],
        "R": data[:, 1],
        "dR": data[:, 2],
        "dq": data[:, 3],
    }
