import argparse
import numpy as np


from analyzer_tools.utils.model_utils import expt_from_model_file
from analyzer_tools.planner.experiment_design import ExperimentDesigner


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Optimize neutron reflectometry experiments"
    )
    parser.add_argument("model_name", help="Name of the model in models/ directory")
    parser.add_argument("--param", required=True, help="Parameter name to optimize")
    parser.add_argument(
        "--values", required=True, help="Parameter values to test (comma-separated)"
    )
    parser.add_argument(
        "--q-min", type=float, default=0.005, help="Minimum Q value (1/Å)"
    )
    parser.add_argument(
        "--q-max", type=float, default=0.3, help="Maximum Q value (1/Å)"
    )
    parser.add_argument("--n-q", type=int, default=100, help="Number of Q points")
    parser.add_argument(
        "--realizations", type=int, default=3, help="Number of noise realizations"
    )
    parser.add_argument(
        "--method",
        choices=["mvn", "kdn"],
        default="mvn",
        help="Entropy calculation method",
    )
    parser.add_argument(
        "--mcmc-steps", type=int, default=2000, help="MCMC steps per realization"
    )
    parser.add_argument(
        "--counting-time", type=float, default=1.0, help="Relative counting time"
    )
    parser.add_argument("--output", help="Output directory for results")
    parser.add_argument("--plot", help="Save plot to this file")
    parser.add_argument(
        "--parameters-of-interest",
        help="Comma-separated list of parameters to focus on for information gain calculation. If not specified, all parameters are used.",
    )

    args = parser.parse_args()

    # Parse parameter values
    try:
        param_values = [float(x.strip()) for x in args.values.split(",")]
    except ValueError:
        print("Error: Parameter values must be comma-separated numbers")
        return 1

    # Parse parameters of interest
    parameters_of_interest = None
    if args.parameters_of_interest:
        parameters_of_interest = [
            x.strip() for x in args.parameters_of_interest.split(",")
        ]

    # Create Q values
    q_values = np.logspace(np.log10(args.q_min), np.log10(args.q_max), args.n_q)
    dq_values = q_values * 0.025

    # Create base experiment
    experiment = expt_from_model_file(args.model_name, q_values, dq_values)

    designer = ExperimentDesigner(experiment)

    # Run optimization
    print("\nRunning optimization...")
    results = designer.optimize(
        param_name=args.param,
        param_values=param_values,
        parameters_of_interest=parameters_of_interest,
        realizations=args.realizations,
        entropy_method=args.method,
        counting_time=args.counting_time,
        mcmc_steps=args.mcmc_steps,
    )

    # Print results
    print(f"\n{'=' * 50}")
    print("OPTIMIZATION RESULTS")
    print(f"{'=' * 50}")
    print(f"{'Parameter Value':<15} {'Information Gain (bits)':<20}")
    print("-" * 35)

    for param_val, info_gain in results:
        print(f"{param_val:<15.4f} {info_gain:<20.4f}")

    # Find optimal value
    max_idx = np.argmax([ig for _, ig in results])
    optimal_value = results[max_idx][0]
    max_gain = results[max_idx][1]

    print(f"\nOptimal {args.param}: {optimal_value:.4f}")
    print(f"Maximum Information Gain: {max_gain:.4f} bits")









    # Save results
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        results_file = os.path.join(args.output, f"optimization_{args.param}.json")

        result_data = {
            "model_name": args.model_name,
            "parameter_optimized": args.param,
            "method": args.method,
            "mcmc_steps": args.mcmc_steps,
            "realizations": args.realizations,
            "counting_time": args.counting_time,
            "q_range": [args.q_min, args.q_max],
            "n_q_points": args.n_q,
            "results": results,
            "optimal_value": optimal_value,
            "max_information_gain": max_gain,
            "base_parameters": base_params,
            "priors": priors,
            "timestamp": datetime.now().isoformat(),
        }

        with open(results_file, "w") as f:
            json.dump(result_data, f, indent=2)
        print(f"\nResults saved to {results_file}")

    # Create plot
    if args.plot or args.output:
        plot_file = (
            args.plot
            if args.plot
            else os.path.join(args.output, f"optimization_{args.param}.png")
        )
        agent.plot_optimization_results(results, args.param, plot_file)

    return 0


if __name__ == "__main__":
    main()
