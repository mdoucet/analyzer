import numpy as np
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


from analyzer_tools.utils.model_utils import expt_from_model_file
from analyzer_tools.planner.experiment_design import ExperimentDesigner
from analyzer_tools.planner import instrument


model_name = "models/cu_thf_planner"
example_measurement = "tests/sample_data/REFL_218386_combined_data_auto.txt"

# Create base experiment
simulator = instrument.InstrumentSimulator(data_file=example_measurement)
experiment = expt_from_model_file(model_name, simulator.q_values, simulator.dq_values)

z, sld, _ = experiment.smooth_profile()

designer = ExperimentDesigner(experiment, simulator=simulator)

h_prior = designer.prior_entropy()
print(f"Prior entropy: {h_prior:.4f} bits")

print(designer)

results, simulated_data = designer.optimize_parallel(
    param_to_optimize="THF rho",
    param_values=[1.5, 2.5, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5],
    realizations=4,
)

# Print results
print(f"\n{'=' * 50}")
print("OPTIMIZATION RESULTS")
print(f"{'=' * 50}")
print(f"{'Parameter Value':<15} {'Information Gain (bits)':<20}")
print("-" * 50)

for param_val, info_gain, std_gain in results:
    print(f"Value {param_val}: ΔH = {info_gain:.4f} ± {std_gain:.4f}")


result_dict = {
    "results": results,
    "simulated_data": simulated_data,
}

with open("optimization_results.json", "w") as f:
    json.dump(result_dict, f, indent=4)
