import os
import json
import numpy as np

import matplotlib.pyplot as plt

from bumps.fitters import fit
from refl1d.names import FitProblem, QProbe, Experiment

from ..utils.model_utils import expt_from_model_file
from ..utils.model_utils import get_sld_contour

from ..planner.experiment_design import ExperimentRealization


def make_report(json_file="optimization_results.json", output_dir="planner_report"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(json_file, "r") as f:
        result_dict = json.load(f)

    results = result_dict["results"]
    simulated_data = result_dict["simulated_data"]

    # Plot information gain
    param_values = [r[0] for r in results]
    info_gains = [r[1] for r in results]

    fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
    plt.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.17)
    plt.plot(param_values, info_gains, marker="o")
    plt.xlabel("Parameter Value", fontsize=15)
    plt.ylabel("Information Gain (bits)", fontsize=15)
    plt.grid(True)
    plt.savefig(f"{output_dir}/information_gain.png")
    plt.close()

    # Plot simulated data for each parameter value
    for i, set in enumerate(simulated_data):
        fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
        plt.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.17)
        for j, data in enumerate(set):
            plt.errorbar(
                data["q_values"],
                data["noisy_reflectivity"],
                yerr=data["errors"],
                linewidth=1,
                markersize=2,
                marker=".",
                linestyle="",
                label=f"Simulation {j + 1}",
            )
            if j == 0:
                plt.plot(data["q_values"], data["reflectivity"], label="True")
            chi2 = np.average(
                (
                    (
                        np.array(data["noisy_reflectivity"])
                        - np.array(data["reflectivity"])
                    )
                    / np.array(data["errors"])
                )
                ** 2
            )
            plt.title(f"$\\chi^2$={chi2:.3f}")
            plt.xlabel("Q ($1/\\AA$)", fontsize=15)
            plt.ylabel("Reflectivity", fontsize=15)
        plt.xscale("log")
        plt.yscale("log")
        plt.legend(frameon=False)
        plt.savefig(f"{output_dir}/simulated_data_{i}.png")
        plt.close()

    for i, set in enumerate(simulated_data):
        fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
        plt.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.17)
        for j, data in enumerate(set):
            # Find the starting point of the distribution
            start_idx = 0
            for start_idx in range(len(data["sld_best"]) - 1, 0, -1):
                if (
                    np.fabs(
                        data["sld_best"][start_idx] - data["sld_best"][start_idx - 1]
                    )
                    > 0.001
                ):
                    break

            shifted_z = np.asarray(data["z"]) - data["z"][start_idx]
            plt.plot(
                shifted_z[:start_idx],
                data["sld_best"][:start_idx],
                markersize=4,
                label=f"Simulation {j + 1}",
                linewidth=2,
            )
            plt.fill_between(
                shifted_z[:start_idx],
                data["sld_low"][:start_idx],
                data["sld_high"][:start_idx],
                alpha=0.2,
                color=plt.gca().lines[-1].get_color(),
            )

        plt.xlabel("z ($\\AA$)", fontsize=15)
        plt.ylabel("SLD ($10^{-6}/{\\AA}^2$)", fontsize=15)

        plt.legend(frameon=False)
        plt.savefig(f"{output_dir}/sld_contours_{i}.png")
        plt.close()


def evaluate_alternate_model(
    model_name: str,
    json_file="optimization_results.json",
    output_file="optimization_results_alternate.json",
    mcmc_steps: int = 1000,
    burn_steps: int = 1000,
):
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(json_file, "r") as f:
        result_dict = json.load(f)

    simulated_data = result_dict["simulated_data"]
    results = result_dict["results"]

    # Go throught the simulated data and evaluate the alternate model
    alternate_simulated_data = []
    total_fits = len(simulated_data) * len(simulated_data[0])
    print(f"Fitting {total_fits} simulated datasets with alternate model...")

    i_fit = 0
    for i, set in enumerate(simulated_data):
        realization_data = []
        for j, data in enumerate(set):
            i_fit += 1
            print(f"Fitting simulation {j + 1} of {len(set)} ({i_fit} of {total_fits})")
            dq = np.asarray(data["dq_values"])
            experiment = expt_from_model_file(model_name, data["q_values"], dq)

            struct_dict = experiment.parameters()["sample"]["layers"]
            for layer in struct_dict:
                for _, param in layer.items():
                    if isinstance(param, dict):
                        for _, sub_value in param.items():
                            # TODO: need a more general way to set parameter values
                            if sub_value.name == "THF rho":
                                sub_value.value = results[i][0]
                                print(
                                    f"  Setting THF rho to {results[i][0]} for this fit"
                                )

            probe = QProbe(
                data["q_values"], dq, R=data["noisy_reflectivity"], dR=data["errors"]
            )

            expt = Experiment(sample=experiment.sample, probe=probe)

            problem = FitProblem(expt)
            problem.model_update()
            mcmc_result = fit(
                problem, method="dream", samples=mcmc_steps, burn=burn_steps, verbose=1
            )
            mcmc_result.state.keep_best()
            mcmc_result.state.mark_outliers()

            z, best, low, high = get_sld_contour(
                problem,
                mcmc_result.state,
                cl=90,
                npoints=200,
                index=1,
                align=-1,
            )[0]
            _, reflectivity = experiment.reflectivity()

            realization = ExperimentRealization(
                q_values=data["q_values"],
                dq_values=dq,
                reflectivity=reflectivity,
                noisy_reflectivity=data["noisy_reflectivity"],
                errors=data["errors"],
                z=z,
                sld_best=best,
                sld_low=low,
                sld_high=high,
                posterior_entropy=0,
            )
            realization_data.append(realization.model_dump(mode="json"))
        alternate_simulated_data.append(realization_data)

    result_dict = {
        "results": [],
        "simulated_data": alternate_simulated_data,
    }

    with open(output_file, "w") as f:
        json.dump(result_dict, f, indent=4)

    return realization_data


if __name__ == "__main__":
    make_report(
        json_file="optimization_results.json",
        output_dir="/home/mat/Downloads/analyzer/planner",
    )
    if False:
        evaluate_alternate_model(
            model_name="models/cu_thf_no_oxide",
            json_file="optimization_results.json",
            output_file="/home/mat/Downloads/analyzer/planner/optimization_results_no_oxide.json",
            mcmc_steps=2000,
            burn_steps=200,
        )
    make_report(
        json_file="/home/mat/Downloads/analyzer/planner/optimization_results_no_oxide.json",
        output_dir="/home/mat/Downloads/analyzer/planner/alternate_model",
    )
