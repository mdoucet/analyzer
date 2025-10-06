#!/usr/bin/env python3
"""
Command-line interfaces for experiment planner.
"""

import os
import json
import logging
import click
import numpy as np

from ..utils.model_utils import expt_from_model_file
from .experiment_design import ExperimentDesigner
from . import instrument


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.command()
@click.option(
    "--data-file",
    type=click.Path(exists=True, readable=True),
    required=True,
    help="Path to the measurement data file",
)
@click.option(
    "--model-file",
    type=str,
    required=True,
    help="Path to the model file (without .py extension)",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True),
    required=True,
    help="Directory to save output results",
)
@click.option(
    "--param",
    type=str,
    required=True,
    help="Parameter to optimize (e.g., 'THF rho')",
)
@click.option(
    "--param-values",
    type=str,
    required=True,
    help="Comma-separated values for the parameter to optimize (e.g., '1.5,2.5,3.5')",
)
@click.option(
    "--num-realizations",
    type=int,
    default=1,
    help="Number of realizations per parameter value",
)
@click.option(
    "--mcmc-steps",
    type=int,
    default=1000,
    help="Number of MCMC steps for fitting",
)
@click.option(
    "--burn-steps",
    type=int,
    default=1000,
    help="Number of burn-in steps for MCMC fitting",
)
@click.option(
    "--parallel/--sequential",
    default=True,
    help="Run optimization in parallel or sequential mode",
)
@click.option(
    "--entropy-method",
    type=click.Choice(["mvn", "kdn"]),
    default="kdn",
    help="Method for entropy calculation (mvn: multivariate normal, kdn: kernel density)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
def optimize(
    data_file: str,
    model_file: str,
    output_dir: str,
    param: str,
    param_values: str,
    num_realizations: int,
    mcmc_steps: int,
    burn_steps: int,
    parallel: bool,
    entropy_method: str,
    verbose: bool,
) -> None:
    """
    Optimize neutron reflectometry experiment design by maximizing information gain.
    
    This tool evaluates different parameter values to determine which experimental
    conditions provide the most information about the parameters of interest.
    """
    setup_logging(verbose)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Parse parameter values
        param_vals = [float(x.strip()) for x in param_values.split(",")]
        
        click.echo("Starting experiment design optimization...")
        click.echo(f"Model: {model_file}")
        click.echo(f"Data file: {data_file}")
        click.echo(f"Parameter to optimize: {param}")
        click.echo(f"Parameter values: {param_vals}")
        click.echo(f"Realizations: {num_realizations}")
        click.echo(f"MCMC steps: {mcmc_steps}")
        click.echo(f"Mode: {'Parallel' if parallel else 'Sequential'}")
        
        # Create instrument simulator from data file
        simulator = instrument.InstrumentSimulator(data_file=data_file)
        
        # Create experiment from model file
        experiment = expt_from_model_file(model_file, simulator.q_values, simulator.dq_values)
        
        # Create experiment designer
        designer = ExperimentDesigner(experiment, simulator=simulator)
        
        # Calculate and display prior entropy
        h_prior = designer.prior_entropy()
        click.echo(f"Prior entropy: {h_prior:.4f} bits")
        
        if verbose:
            click.echo(str(designer))
        
        # Run optimization
        click.echo("\nRunning optimization...")
        
        if parallel:
            results, simulated_data = designer.optimize_parallel(
                param_to_optimize=param,
                param_values=param_vals,
                realizations=num_realizations,
                mcmc_steps=mcmc_steps,
                entropy_method=entropy_method,
            )
        else:
            results, simulated_data = designer.optimize(
                param_to_optimize=param,
                param_values=param_vals,
                realizations=num_realizations,
                mcmc_steps=mcmc_steps,
                entropy_method=entropy_method,
            )
        
        # Display results
        click.echo(f"\n{'=' * 50}")
        click.echo("OPTIMIZATION RESULTS")
        click.echo(f"{'=' * 50}")
        click.echo(f"{'Parameter Value':<15} {'Information Gain (bits)':<25}")
        click.echo("-" * 50)
        
        for param_val, info_gain, std_gain in results:
            click.echo(f"{param_val:>12.3f}     ΔH = {info_gain:>6.4f} ± {std_gain:>6.4f}")
        
        # Find optimal value
        best_idx = np.argmax([result[1] for result in results])
        best_value, best_gain, best_std = results[best_idx]
        
        click.echo(f"\nOptimal parameter value: {best_value:.3f}")
        click.echo(f"Maximum information gain: {best_gain:.4f} ± {best_std:.4f} bits")
        
        # Save results to JSON file
        result_dict = {
            "parameter": param,
            "parameter_values": param_vals,
            "results": results,
            "simulated_data": simulated_data,
            "optimal_value": best_value,
            "max_information_gain": best_gain,
            "max_information_gain_std": best_std,
            "prior_entropy": h_prior,
            "settings": {
                "num_realizations": num_realizations,
                "mcmc_steps": mcmc_steps,
                "burn_steps": burn_steps,
                "entropy_method": entropy_method,
                "parallel": parallel,
            }
        }
        
        output_file = os.path.join(output_dir, "optimization_results.json")
        with open(output_file, "w") as f:
            json.dump(result_dict, f, indent=4)
        
        click.echo(f"\nResults saved to: {output_file}")
        
        # Print ASCII graph if requested
        if verbose:
            click.echo("\nInformation Gain Profile:")
            _print_ascii_graph(results)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


def _print_ascii_graph(results):
    """Print an ASCII graph of information gain vs parameter values."""
    values = [result[0] for result in results]
    gains = [result[1] for result in results]
    stds = [result[2] for result in results]
    
    max_gain = max(gains) if gains else 1
    scale = 40 / max_gain if max_gain > 0 else 1
    
    click.echo(f"{'Value':<8} | {'Information Gain'}")
    click.echo("-" * 60)
    
    for value, gain, std in zip(values, gains, stds):
        bar = "#" * int(gain * scale)
        click.echo(f"{value:>6.2f}   | {bar} ({gain:.3f} ± {std:.3f})")


@click.group()
def main():
    """Neutron Reflectometry Experiment Planning Tool."""
    pass


main.add_command(optimize)


if __name__ == "__main__":
    main()
