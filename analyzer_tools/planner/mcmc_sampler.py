import numpy as np
from typing import List, Tuple

from refl1d.names import Experiment, FitProblem, QProbe
from bumps.fitters import fit


def perform_mcmc(
    sample: object,
    q_values: np.ndarray,
    noisy_reflectivity: np.ndarray,
    errors: np.ndarray,
    dq_values: np.ndarray,
    mcmc_steps: int = 1000,
    burn_steps: int = 1000,
) -> Tuple[np.ndarray, List[str]]:
    """
    Perform MCMC analysis using refl1d/bumps.

    Args:
        sample: refl1d object representing the sample
        q_values: Q values
        noisy_reflectivity: Noisy reflectivity data
        errors: Error bars
        mcmc_steps: Number of MCMC steps
        burn_steps: Number of burn-in steps
        dq_values: Q resolution values
    Returns:
        Tuple of (2D numpy array of MCMC samples, list of parameter names)
    """
    # Prepare FitProblem

    probe = QProbe(q_values, dq_values, R=noisy_reflectivity, dR=errors)
    expt = Experiment(sample=sample, probe=probe)
    problem = FitProblem(expt)
    problem.model_update()

    # Run DREAM sampler
    result = fit(
        problem, method="dream", samples=mcmc_steps, burn=burn_steps, verbose=0
    )

    # Analyze the fit state and save values
    result.state.keep_best()
    result.state.mark_outliers()

    return result
