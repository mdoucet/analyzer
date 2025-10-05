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


model_name = "models/cu_thf_planner"

# Create Q values
q_values = np.logspace(np.log10(0.008), np.log10(0.2), 100)
dq_values = q_values * 0.025


# Create base experiment
# TODO: write a test for this.
experiment = expt_from_model_file(model_name, q_values, dq_values)

designer = ExperimentDesigner(experiment)

# TODO: write a test for this.
designer.get_parameters()

# TODO: write a test for this.
h_prior =  designer.prior_entropy()
print(f"Prior entropy: {h_prior:.4f} bits")

print(designer)

# TODO: write a test for this.
print(designer._model_parameters_to_dict())

designer.set_parameter_to_optimize("THF rho", 5.0)

results, simulated_data = designer.optimize(param_to_optimize="THF rho", param_values=[1.5, 2.5,3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5], realizations=5)

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


result_dict = {
    "results": results,
    "simulated_data": simulated_data,
}

with open("optimization_results.json", "w") as f:
    json.dump(result_dict, f, indent=4)
