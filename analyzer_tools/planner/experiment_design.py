"""
Experimental Design Optimization Tool for Neutron Reflectometry

This tool implements the Bayesian framework for optimizing neutron reflectometry
experiments by maximizing expected Shannon information gain, following the methodology
of Treece et al., J. Appl. Cryst. (2019), 52, 47-59.
"""

import numpy as np
import copy
from typing import Dict, List, Tuple, Optional
import logging
from pydantic import BaseModel
from scipy.stats import gaussian_kde, multivariate_normal

from bumps import dream
from bumps.fitters import fit
from refl1d.names import Experiment, FitProblem, Parameter, QProbe
from tqdm import tqdm

logger = logging.getLogger(__name__)

from .instrument import add_instrumental_noise
from ..utils.model_utils import get_sld_contour


# Type definitions
class SampleParameter(BaseModel):
    name: str
    value: float
    bounds: Tuple[float, float]
    is_of_interest: bool = True
    h_prior: float = 0
    h_posterior: float = 0


class ExperimentRealization(BaseModel):
    q_values: List[float]
    reflectivity: List[float]
    noisy_reflectivity: List[float]
    errors: List[float]
    z: List[float]
    sld_best: List[float]
    # 90% CL
    sld_low: List[float]
    sld_high: List[float]
    posterior_entropy: float = 0
    # Entropy of the marginal distribution of each parameter
    marginal_entropy: List[float] = None


class ExperimentDesigner:
    """
    An agent to suggest optimal experimental protocols for neutron reflectometry
    by maximizing the expected Shannon information gain, following the methodology
    of Treece et al., J. Appl. Cryst. (2019), 52, 47-59.
    """

    def __init__(
        self, experiment: Experiment, parameters_of_interest: Optional[List[str]] = None
    ):
        self.experiment = experiment
        self.problem = FitProblem(experiment)
        self.parameters_of_interest: Optional[List[str]] = parameters_of_interest
        if len(parameters_of_interest or []) == 0:
            self.parameters_of_interest = None

        # The list of variable parameters
        self.parameters = self.get_parameters()

        # The list of all parameters in the model, including fixed parameters
        self.all_model_parameters = self._model_parameters_to_dict()

    def __repr__(self):
        summary = f"\nExperimentDesigner with {len(self.problem.parameters)} parameters"
        summary += f"\n    {'name':<20} {'value':<10} {'bounds':<20} {'*':<5} {'H_prior':<10} {'H_posterior':<12}"
        for k, v in self.parameters.items():
            # Format columns: name (20), value (10), bounds (20), interest (5)
            summary += (
                f"\n  - {k:<20} {v.value:<10.4g} {str(v.bounds):<20} "
                f"{'*' if v.is_of_interest else '':<5} {v.h_prior:<10.4g} {v.h_posterior:<12.4g}"
            )
        return summary

    def _model_parameters_to_dict(self) -> Dict[str, Parameter]:
        """
        Convert the model parameters to a dictionary of parameter names and their values.

        Returns
        -------
        Dict[str, Parameter]
            A dictionary of parameter names and their values.
        """
        param_dict = {}
        models = self.problem._models
        if len(models) == 0 or len(models) > 1:
            raise ValueError(
                f"Expected exactly one model in the problem, found {len(models)}"
            )
        # Structured dict of parameters. The structure is nested according to the model structure.
        # The structured dict below is a list of layers, each layer is a dict for 'thickness', 'interface', 'material'.
        # The 'material' is itself a dict of 'rho' and 'irho'.
        # Here we want to flatten this structure to a single dict of parameter names and values.
        struct_dict = models[0].parameters()["sample"]["layers"]

        for layer in struct_dict:
            for _, param in layer.items():
                if isinstance(param, dict):
                    for _, sub_value in param.items():
                        param_dict[sub_value.name] = sub_value
                else:
                    param_dict[param.name] = param

        return param_dict

    def set_parameter_to_optimize(self, param_name: str, value: float):
        """
        Set the value of a parameter in the model.

        This parameter is not one of the free parameters, but a fixed parameter.
        We will go back to the Experiment object and set the parameter value directly.

        Parameters
        ----------
        param_name : str
            The name of the parameter to set.
        value : float
            The value to set the parameter to.
        """
        if param_name not in self.all_model_parameters:
            raise ValueError(f"Parameter {param_name} not found in model parameters")
        param = self.all_model_parameters[param_name]
        param.value = value
        self.problem.model_update()

    def get_parameters(self):
        """
        Get the variable parameters and their prior.
        """
        # Extract parameters from the problem
        parameters: Dict[str, SampleParameter] = {}

        for param in self.problem.parameters:
            is_of_interest = (
                self.parameters_of_interest is None
                or param.name in self.parameters_of_interest
            )
            p = SampleParameter(
                name=param.name,
                value=param.value,
                bounds=param.bounds,
                is_of_interest=is_of_interest,
            )
            parameters[param.name] = p

        # Warn if parameters of interest not found
        if self.parameters_of_interest:
            if (missing_params := [
                param
                for param in self.parameters_of_interest
                if param not in self.all_model_parameters
            ]):
                logger.warning(f"Parameters {missing_params} not found in model")
                logger.info(f"Available parameters: {list(self.all_model_parameters.keys())}")
        return parameters

    def prior_entropy(self) -> float:
        """
        Calculate the prior entropy of the parameters.

        Returns
        -------
        float
            The Shannon entropy of the prior distribution in bits.
        """
        H_prior = 0.0

        for key, p in self.parameters.items():
            # Only include parameters of interest, which may be all parameters if none were specified
            if not p.is_of_interest:
                continue
            pmin, pmax = p.bounds
            if pmin is None or pmax is None:
                raise ValueError(f"Parameter {key} has `undefined bounds")
            if pmax <= pmin:
                raise ValueError(
                    f"Parameter {key} has invalid bounds: {pmin} >= {pmax}"
                )
            p.h_prior = np.log2(pmax - pmin)
            H_prior += p.h_prior
        return H_prior

    def perform_mcmc(
        self,
        q_values: np.ndarray,
        noisy_reflectivity: np.ndarray,
        errors: np.ndarray,
        mcmc_steps: int = 1000,
        burn_steps: int = 1000,
        q_resolution_scale: float = 0.025,
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Perform MCMC analysis using refl1d/bumps.

        Args:
            q_values: Q values
            noisy_reflectivity: Noisy reflectivity data
            errors: Error bars
            mcmc_steps: Number of MCMC steps
            burn_steps: Number of burn-in steps
            q_resolution_scale: Scaling factor for Q resolution (default: 0.025)

        Returns:
            Tuple of (2D numpy array of MCMC samples, list of parameter names)
        """
        # Prepare FitProblem

        probe = QProbe(q_values, q_values * q_resolution_scale, R=noisy_reflectivity, dR=errors)
        expt = Experiment(sample=self.experiment.sample, probe=probe)
        problem = FitProblem(expt)
        problem.model_update()

        # Run DREAM sampler
        result = fit(
            problem, method="dream", samples=mcmc_steps, burn=burn_steps, verbose=0
        )

        # Extract samples from the result
        # if hasattr(result, 'state') and hasattr(result.state, 'draw'):
        _, chains, _ = result.state.chains()

        # Analyze the fit state and save values
        result.state.keep_best()
        result.state.mark_outliers()

        # step = self.steps[-1]
        # step.chain_pop = chains[-1, :, :]
        # step.draw = result.state.draw(thin=self.thinning)
        # step.best_logp = result.state.best()[1]
        # self.problem.setp(result.state.best()[0])
        # step.final_chisq = self.result.chisq_str()
        # step.H, _, _ = calc_entropy(step.draw.points, select_pars=None, options=self.entropy_options)
        # step.dH = self.init_entropy - step.H
        # step.H_marg, _, _ = calc_entropy(step.draw.points, select_pars=self.sel, options=self.entropy_options)
        # step.dH_marg = self.init_entropy_marg - step.H_marg

        return result
    
        #samples = result.state.draw()
        #return samples.points

    def _extract_marginal_samples(
        self,
        mcmc_samples: np.ndarray,
    ) -> np.ndarray:
        """
        Extract marginal samples for parameters of interest.

        Args:
            mcmc_samples: Full MCMC samples array
            all_param_names: Names of all parameters in order
            parameters_of_interest: Names of parameters to extract

        Returns:
            Marginal samples array with only parameters of interest
        """
        if not self.parameters_of_interest:
            return mcmc_samples

        all_param_names = [p.name for p in self.problem.parameters]

        # Find indices of parameters of interest
        indices = []
        for param_name in self.parameters_of_interest:
            if param_name in all_param_names:
                indices.append(all_param_names.index(param_name))
            else:
                logger.warning(f"Warning: Parameter '{param_name}' not found in MCMC samples")

        if not indices:
            logger.debug("Warning: No parameters of interest found, using all parameters")
            return mcmc_samples

        return mcmc_samples[:, indices]

    def _calculate_posterior_entropy_mvn(self, mcmc_samples: np.ndarray) -> float:
        """
        Calculate posterior entropy using multivariate normal approximation.

        Args:
            mcmc_samples: 2D array of MCMC samples (rows=samples, cols=parameters)

        Returns:
            Posterior entropy in bits
        """
        if mcmc_samples.ndim != 2 or mcmc_samples.shape[0] < 2:
            raise ValueError("MCMC samples must be a 2D array with at least 2 samples.")

        try:
            # Use scipy's multivariate_normal.entropy (returns in nats)
            cov_matrix = np.cov(mcmc_samples, rowvar=False)
            entropy_nats = multivariate_normal.entropy(cov=cov_matrix)
            return entropy_nats / np.log(2)  # Convert to bits
        except np.linalg.LinAlgError:
            # Handle singular covariance matrix
            logger.error("Warning: Singular covariance matrix, using regularized version")
            cov_matrix = np.cov(mcmc_samples, rowvar=False)
            cov_matrix += 1e-10 * np.eye(cov_matrix.shape[0])  # Regularize
            entropy_nats = multivariate_normal.entropy(cov=cov_matrix)
            return entropy_nats / np.log(2)

    def _calculate_posterior_entropy_kdn(self, mcmc_samples: np.ndarray) -> float:
        """
        Calculate posterior entropy using kernel density estimation.

        Args:
            mcmc_samples: 2D array of MCMC samples

        Returns:
            Posterior entropy in bits
        """
        if mcmc_samples.ndim != 2 or mcmc_samples.shape[0] < 2:
            raise ValueError("MCMC samples must be a 2D array with at least 2 samples.")

        try:
            kde = gaussian_kde(mcmc_samples.T)
            log_probs = kde.logpdf(mcmc_samples.T)
            entropy_nats = -np.mean(log_probs)
            return entropy_nats / np.log(2)
        except Exception as e:
            # Fallback to multivariate normal entropy if KDE fails
            logger.error("Warning: KDE failed, falling back to MVN entropy. Exception: {}".format(e))
            cov_matrix = np.cov(mcmc_samples, rowvar=False)
            cov_matrix += 1e-10 * np.eye(cov_matrix.shape[0])  # Regularize
            entropy_nats = multivariate_normal.entropy(cov=cov_matrix)
            return entropy_nats / np.log(2)

    def _calculate_posterior_entropy(
        self, mcmc_samples: np.ndarray, method: str
    ) -> float:
        """
        Dispatcher for posterior entropy calculation.

        Args:
            mcmc_samples: 2D array of MCMC samples
            method: Method to use ('mvn' or 'kdn')

        Returns:
            Posterior entropy in bits
        """
        if method.lower() == "mvn":
            return self._calculate_posterior_entropy_mvn(mcmc_samples)
        elif method.lower() == "kdn":
            return self._calculate_posterior_entropy_kdn(mcmc_samples)
        else:
            raise ValueError("Invalid entropy method. Choose 'mvn' or 'kdn'.")

    def optimize(
        self,
        param_to_optimize: str,
        param_values: list,
        realizations: int = 3,
        mcmc_steps: int = 2000,
        entropy_method: str = "kdn",
        counting_time: float = 1.0,
    ):
        """
        Optimize the experimental design by evaluating the expected information gain
        for different parameter values.

        # TODO: capture reflectivity and SLD curves so we can plot them

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
        counting_time : float, optional
            Relative counting time for the experiment (default is 1.0).
            This parameter affects the noise level in the simulations.
        Returns:
            List of (parameter_value, information_gain) tuples
        """
        results = []
        simulated_data = []

        # Compute prior entropy
        prior_entropy = self.prior_entropy()

        logger.info(f"Starting optimization for parameter: {param_to_optimize}")
        logger.info(f"Prior Entropy: {prior_entropy:.4f} bits")
        logger.info(
            f"Testing {len(param_values)} values with {realizations} realizations each"
        )
        logger.info(f"Method: {entropy_method}, MCMC steps: {mcmc_steps}")

        # Iterate over parameter values
        # Use tqdm to wrap the parameter values for a progress bar
        for i, value in enumerate(tqdm(param_values, desc="Optimizing", unit="val")):
            logger.info(
                f"\n  Testing value {i + 1}/{len(param_values)}: {param_to_optimize} = {value}"
            )

            self.set_parameter_to_optimize(param_to_optimize, value)

            self.problem.summarize()

            z, sld, _ = self.experiment.smooth_profile()

            # Calculate noise-free reflectivity
            q_values, r_calc = self.experiment.reflectivity()

            realization_gains = []
            realization_data = []
            for j in range(realizations):
                try:
                    # Add noise
                    noisy_reflectivity, errors = add_instrumental_noise(
                        q_values, r_calc, counting_time
                    )

                    # Perform MCMC
                    mcmc_result = self.perform_mcmc(
                        q_values,
                        noisy_reflectivity,
                        errors,
                    )
                    mcmc_samples = mcmc_result.state.draw().points

                    # Extract marginal samples if parameters of interest specified
                    marginal_samples = self._extract_marginal_samples(mcmc_samples)

                    # Calculate posterior entropy
                    posterior_entropy = self._calculate_posterior_entropy(
                        marginal_samples, method=entropy_method
                    )

                    # Information gain
                    info_gain = prior_entropy - posterior_entropy
                    realization_gains.append(info_gain)
                    logger.info(f"ΔH = {info_gain:.3f} bits")

                    # %90 confidence interval for SLD
                    z, best, low, high = get_sld_contour(
                        self.problem,
                        mcmc_result.state,
                        cl=90,
                        npoints=200,
                        index=1,
                        align=-1,
                    )[0]

                    realization = ExperimentRealization(
                        q_values=q_values,
                        reflectivity=r_calc,
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
                    raise
                    realization_gains.append(0.0)

            # Average information gain
            avg_info_gain = np.mean(realization_gains)
            std_info_gain = np.std(realization_gains)
            logger.info(
                f"    -> Average Information Gain: {avg_info_gain:.4f} ± {std_info_gain:.4f} bits"
            )

            results.append((value, avg_info_gain))
            simulated_data.append(realization_data)

        return results, simulated_data
