import os
import json
import numpy as np

import matplotlib.pyplot as plt


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
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)

    plt.plot(param_values, info_gains, marker="o")
    plt.xlabel("Parameter Value", fontsize=15)
    plt.ylabel("Information Gain (bits)", fontsize=15)
    plt.title("Information Gain vs Parameter Value", fontsize=15)
    plt.grid(True)
    plt.savefig(f"{output_dir}/information_gain.png")
    plt.close()

    # Plot simulated data for each parameter value
    for i, set in enumerate(simulated_data):
        fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
        plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)
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
            #plt.plot(data["q_values"], data["reflectivity"], label="True")
            plt.xlabel("Q (1/A)", fontsize=15)
            plt.ylabel("Reflectivity", fontsize=15)
        plt.xscale("log")
        plt.yscale("log")
        plt.legend(frameon=False)
        plt.savefig(f"{output_dir}/simulated_data_{i}.png")
        plt.close()

    for i, set in enumerate(simulated_data):
        fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
        plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)
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


if __name__ == "__main__":
    make_report(
        json_file="optimization_results.json",
        output_dir="/home/mat/Downloads/analyzer/planner",
    )
