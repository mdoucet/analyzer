import numpy as np
from typing import Dict, List, Tuple, Optional
import logging


def add_instrumental_noise(
    q_values: np.ndarray,
    reflectivity_curve: np.ndarray,
    counting_time: float = 1.0,
    min_relative_error: float = 0.01,
    base_relative_error: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Add realistic instrumental noise to reflectivity data.

    Args:
        q_values: Q values
        reflectivity_curve: Noise-free reflectivity
        counting_time: Relative counting time (affects noise level)
        min_relative_error: Minimum relative error (default 0.01)
        base_relative_error: Base relative error (default 0.05)

    Returns:
        Tuple of (noisy_reflectivity, errors)
    """
    # Simple noise model: relative error inversely proportional to sqrt(R * counting_time)

    # Calculate relative errors - more realistic model
    relative_errors = np.maximum(
        min_relative_error,
        base_relative_error
        / np.sqrt(np.maximum(reflectivity_curve * counting_time, 1e-10)),
    )

    # Add Q-dependent component (higher Q = higher relative error)
    q_max = np.max(q_values)
    if q_max > 0:
        q_factor = 1 + 0.5 * (q_values / q_max) ** 2
        relative_errors *= q_factor

    # Absolute errors
    errors = relative_errors * reflectivity_curve

    # Add Gaussian noise
    noise = np.random.normal(0, errors)
    noisy_reflectivity = reflectivity_curve + noise

    # Ensure positive reflectivity
    noisy_reflectivity = np.maximum(noisy_reflectivity, 1e-12)

    return noisy_reflectivity, errors
