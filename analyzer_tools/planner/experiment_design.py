"""
Experimental Design Optimization Tool for Neutron Reflectometry

This tool implements the Bayesian framework for optimizing neutron reflectometry
experiments by maximizing expected Shannon information gain, following the methodology
of Treece et al., J. Appl. Cryst. (2019), 52, 47-59.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from pydantic import BaseModel
from scipy.stats import gaussian_kde, multivariate_normal

from refl1d.names import Experiment, FitProblem, Parameter

from . import instrument

logger = logging.getLogger(__name__)


# Type definitions
class SampleParameter(BaseModel):
    name: str
    value: float
    bounds: Tuple[float, float]
    is_of_interest: bool = True
    h_prior: float = 0
    h_posterior: float = 0


class ExperimentRealization(BaseModel):
    # Input parameters
    param_to_optimize: str = ""
    param_value: float = 0

    # Metrics
    chi2: float = 0
    posterior_entropy: float = 0
    # Entropy of the marginal distribution of each parameter
    marginal_entropy: List[float] = []
    evidence: float = 0

    # Distributions
    q_values: List[float]
    dq_values: List[float]
    reflectivity: List[float]
    noisy_reflectivity: List[float]
    errors: List[float]
    fit_reflectivity: Optional[List[float]] = None

    # SLD profile
    z: List[float]
    sld_best: List[float]
    # 90% CL
    sld_low: List[float]
    sld_high: List[float]


class ExperimentDesigner:
    """
    An agent to suggest optimal experimental protocols for neutron reflectometry
    by maximizing the expected Shannon information gain, following the methodology
    of Treece et al., J. Appl. Cryst. (2019), 52, 47-59.
    """

    def __init__(
        self,
        experiment: Experiment,
        simulator: instrument.InstrumentSimulator,
        parameters_of_interest: Optional[List[str]] = None,
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

        if simulator is None:
            simulator = instrument.InstrumentSimulator()
        self.simulator = simulator

    def __repr__(self):
        summary = f"\nExperimentDesigner with {len(self.problem.parameters)} parameters"
        summary += f"\n    {'name':<20} {'value':<10} {'bounds':<20} {'H_prior':<10} {'H_posterior':<12}"
        for k, v in self.parameters.items():
            # Format columns: name (20), value (10), bounds (20), interest (5)
            starred = "*" if v.is_of_interest else ""
            par = f"{k}{starred}"
            summary += (
                f"\n  - {par:<20} {v.value:<10.4g} {str(v.bounds):<20} "
                f"{v.h_prior:<10.4g} {v.h_posterior:<12.4g}"
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
            if missing_params := [
                param
                for param in self.parameters_of_interest
                if param not in self.all_model_parameters
            ]:
                logger.warning(f"Parameters {missing_params} not found in model")
                logger.info(
                    f"Available parameters: {list(self.all_model_parameters.keys())}"
                )
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
                logger.warning(
                    f"Warning: Parameter '{param_name}' not found in MCMC samples"
                )

        if not indices:
            logger.debug(
                "Warning: No parameters of interest found, using all parameters"
            )
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
            logger.error(
                "Warning: Singular covariance matrix, using regularized version"
            )
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
            logger.error(
                "Warning: KDE failed, falling back to MVN entropy. Exception: {}".format(
                    e
                )
            )
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
