import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed

from . import mcmc_sampler
from .experiment_design import ExperimentRealization, ExperimentDesigner
from ..utils.model_utils import get_sld_contour

logger = logging.getLogger(__name__)


def evaluate_param(
    experiment_designer: "ExperimentDesigner",
    param_to_optimize: str,
    value: float,
    realizations: int,
    prior_entropy: float,
    mcmc_steps: int,
    entropy_method: str,
):
    experiment_designer.set_parameter_to_optimize(param_to_optimize, value)
    logger.info(f"{experiment_designer.problem.summarize()}")

    # z, sld, _ = experiment_designer.experiment.smooth_profile()
    q_values, r_calc = experiment_designer.experiment.reflectivity()

    realization_gains = []
    realization_data = []
    for _ in range(realizations):
        try:
            noisy_reflectivity, errors = experiment_designer.simulator.add_noise(r_calc)

            mcmc_result = mcmc_sampler.perform_mcmc(
                experiment_designer.experiment.sample,
                q_values,
                noisy_reflectivity,
                errors,
                dq_values=experiment_designer.simulator.dq_values,
                mcmc_steps=mcmc_steps,
            )
            mcmc_samples = mcmc_result.state.draw().points

            marginal_samples = experiment_designer._extract_marginal_samples(
                mcmc_samples
            )

            posterior_entropy = experiment_designer._calculate_posterior_entropy(
                marginal_samples, method=entropy_method
            )
            info_gain = prior_entropy - posterior_entropy
            realization_gains.append(info_gain)

            z, best, low, high = get_sld_contour(
                experiment_designer.problem,
                mcmc_result.state,
                cl=90,
                npoints=200,
                index=1,
                align=-1,
            )[0]

            best_p, _ = mcmc_result.state.best()
            experiment_designer.problem.setp(best_p)

            _, reflectivity = experiment_designer.experiment.reflectivity()

            realization = ExperimentRealization(
                q_values=q_values,
                dq_values=experiment_designer.simulator.dq_values,
                reflectivity=reflectivity,
                noisy_reflectivity=noisy_reflectivity,
                errors=errors,
                z=z,
                sld_best=best,
                sld_low=low,
                sld_high=high,
                posterior_entropy=posterior_entropy,
            )
            realization_data.append(realization.model_dump(mode="json"))

        except Exception as e:
            logger.error(f"Error: {e}")
            realization_gains.append(0.0)

    avg_info_gain = np.mean(realization_gains)
    std_info_gain = np.std(realization_gains)
    return value, avg_info_gain, std_info_gain, realization_data


def optimize(
    experiment_designer: "ExperimentDesigner",
    param_to_optimize: str,
    param_values: list,
    realizations: int = 3,
    mcmc_steps: int = 2000,
    entropy_method: str = "kdn",
) -> Tuple[List[Tuple[float, float, float]], List[List[Dict]]]:
    """
    Optimize the experimental design sequentially by evaluating the expected information gain
    for different parameter values.

    Parameters
    ----------
    param_to_optimize : str
        The name of the parameter to optimize.
    param_values : list
        A list of parameter values to evaluate.
    realizations : int, optional
        Number of noise realizations to simulate (default is 3).
    mcmc_steps : int, optional
        Number of MCMC steps for posterior sampling (default is 2000).
    entropy_method : str, optional
        Method for entropy calculation ('mvn' or 'kdn', default is 'mvn').

    Returns:
        List of (parameter_value, information_gain, std_info_gain) tuples and list of simulated data
    """
    results = []
    simulated_data = []
    prior_entropy = experiment_designer.prior_entropy()

    logger.info(f"Starting sequential optimization for parameter: {param_to_optimize}")
    logger.info(f"Prior Entropy: {prior_entropy:.4f} bits")
    logger.info(
        f"Testing {len(param_values)} values with {realizations} realizations each"
    )
    logger.info(f"Method: {entropy_method}, MCMC steps: {mcmc_steps}")

    if param_to_optimize not in experiment_designer.all_model_parameters:
        raise ValueError(f"Parameter {param_to_optimize} not found in model parameters")

    for value in tqdm(param_values, desc="Optimizing", unit="val"):
        try:
            result_value, avg_info_gain, std_info_gain, realization_data = (
                evaluate_param(
                    experiment_designer,
                    param_to_optimize,
                    value,
                    realizations,
                    prior_entropy,
                    mcmc_steps,
                    entropy_method,
                )
            )
            results.append((result_value, avg_info_gain, std_info_gain))
            simulated_data.append(realization_data)
            logger.info(
                f"Value {result_value}: ΔH = {avg_info_gain:.4f} ± {std_info_gain:.4f} bits"
            )
        except Exception as e:
            logger.error(f"Error evaluating value {value}: {e}")

    return results, simulated_data


def optimize_parallel(
    experiment_designer: "ExperimentDesigner",
    param_to_optimize: str,
    param_values: list,
    realizations: int = 3,
    mcmc_steps: int = 2000,
    entropy_method: str = "kdn",
) -> Tuple[List[Tuple[float, float, float]], List[List[Dict]]]:
    """
    Optimize the experimental design by evaluating the expected information gain
    for different parameter values.

    Parameters
    ----------
    param_to_optimize : str
        The name of the parameter to optimize.
    param_values : list
        A list of parameter values to evaluate.
    realizations : int, optional
        Number of noise realizations to simulate (default is 3).
    mcmc_steps : int, optional
        Number of MCMC steps for posterior sampling (default is 2000).
    entropy_method : str, optional
        Method for entropy calculation ('mvn' or 'kdn', default is 'mvn').

    Returns:
        List of (parameter_value, information_gain, std_info_gain) tuples and list of simulated data
    """
    results = []
    simulated_data = []
    prior_entropy = experiment_designer.prior_entropy()

    logger.info(f"Starting optimization for parameter: {param_to_optimize}")
    logger.info(f"Prior Entropy: {prior_entropy:.4f} bits")
    logger.info(
        f"Testing {len(param_values)} values with {realizations} realizations each"
    )
    logger.info(f"Method: {entropy_method}, MCMC steps: {mcmc_steps}")

    if param_to_optimize not in experiment_designer.all_model_parameters:
        raise ValueError(
            f"Parameter {param_to_optimize} not found in model parameters"
        )

    with ProcessPoolExecutor() as executor:
        future_to_value = {
            executor.submit(
                evaluate_param,
                experiment_designer,
                param_to_optimize,
                value,
                realizations,
                prior_entropy,
                mcmc_steps,
                entropy_method,
            ): value
            for value in param_values
        }

        for future in tqdm(
            as_completed(future_to_value),
            total=len(param_values),
            desc="Optimizing",
            unit="val",
        ):
            value = future_to_value[future]
            try:
                result_value, avg_info_gain, std_info_gain, realization_data = (
                    future.result()
                )
                results.append((result_value, avg_info_gain, std_info_gain))
                simulated_data.append(realization_data)
                logger.info(
                    f"Value {result_value}: ΔH = {avg_info_gain:.4f} ± {std_info_gain:.4f} bits"
                )
            except Exception as e:
                logger.error(f"Error evaluating value {value}: {e}")

    # Ensure ordered_results includes [value, avg_gain, std_gain]
    value_to_result = {result[0]: result for result in results}
    ordered_results = [
        [value, value_to_result[value][1], value_to_result[value][2]]
        for value in param_values
    ]

    # Sort simulated data to match the order of param_values
    value_to_data = {
        result[0]: data for result, data in zip(results, simulated_data)
    }
    ordered_simulated_data = [value_to_data[value] for value in param_values]

    return ordered_results, ordered_simulated_data
