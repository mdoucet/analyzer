#!/usr/bin/env python3
import argparse
import os
import numpy as np
import matplotlib.pyplot as plt
import glob
import re
from datetime import datetime
import configparser

from .utils import summary_plots


def assess_result(directory, set_id, model_name, reports_dir):
    """
    Reads the *-refl.dat file, plots the data, and updates the report.
    Parameters
    ----------
    directory : str
        The directory containing the fit results.
    set_id : str
        The set ID of the data.
    model_name : str
        The name of the model used for the fit.
    reports_dir : str
        The directory where reports are saved.
    """
    # Find the data file
    data_files = glob.glob(os.path.join(directory, "*-refl.dat"))
    if not data_files:
        print(f"Error: No *-refl.dat file found in {directory}.")
        return
    data_file = data_files[0]

    # Read the data, skipping the header
    data = np.loadtxt(data_file).T

    # Calculate chi-squared
    chisq = np.mean((data[2] - data[4]) ** 2 / data[3] ** 2)

    # Create the plot
    fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)

    plt.errorbar(data[0], data[2], yerr=data[3], fmt=".", label="Data")
    plt.plot(data[0], data[4], label="Fit")
    plt.xlabel("Q (1/A)", fontsize=15)
    plt.ylabel("Reflectivity", fontsize=15)
    plt.xscale("log")
    plt.yscale("log")
    plt.legend(frameon=False)

    # Save the plot
    config = configparser.ConfigParser()
    config.read('config.ini')

    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    image_filename = f"fit_result_{set_id}_{model_name}_reflectivity.svg"
    image_path = os.path.join(reports_dir, image_filename)
    plt.savefig(image_path, format="svg")
    print(f"Plot saved to {image_path}")

    # Plot the SLD profile
    fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)

    profile_file = os.path.join(directory, "problem-1-profile.dat")
    summary_plots.plot_sld(profile_file, set_id, show_cl=True, z_offset=0.0)
    plt.xlabel("z ($\\AA$)", fontsize=15)
    plt.ylabel("SLD ($10^{-6}/{\\AA}^2$)", fontsize=15)

    image_filename = f"fit_result_{set_id}_{model_name}_profile.svg"
    sld_image_path = os.path.join(reports_dir, image_filename)

    plt.savefig(sld_image_path, format="svg")
    print(f"Plot saved to {sld_image_path}")

    # Update the report
    report_file = os.path.join(reports_dir, f"report_{set_id}.md")

    new_section_header = f"## Fit results for {model_name}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_content = (
        f"{new_section_header}\n"
        f"Assessment run on: {now}\n\n"
        f"Chi-squared: {chisq:.2g}\n\n"
        f"Fit data is located in: `{os.path.abspath(directory)}`\n\n"
        f"![Fit result]({os.path.relpath(image_path, reports_dir)})\n"
        f"![SLD profile]({os.path.relpath(sld_image_path, reports_dir)})\n"
    )

    if os.path.exists(report_file):
        with open(report_file, "r") as f:
            content = f.read()

        # Use regex to find and replace the section for the same model
        pattern = re.compile(
            rf"({re.escape(new_section_header)}.*?)(?=\n## |\Z)", re.DOTALL
        )
        if pattern.search(content):
            content = pattern.sub(new_content, content)
        else:
            content += "\n" + new_content

        with open(report_file, "w") as f:
            f.write(content)
    else:
        with open(report_file, "w") as f:
            f.write(f"# Report for Set {set_id}\n\n{new_content}")

    print(f"Report {report_file} updated.")


def main():
    config = configparser.ConfigParser()
    config.read('config.ini')

    parser = argparse.ArgumentParser(description="Assess the result of a fit.")
    parser.add_argument(
        "directory", type=str, help="Directory containing the fit results."
    )
    parser.add_argument("set_id", type=str, help="The set ID of the data.")
    parser.add_argument(
        "model_name", type=str, default="model", help="Name of the model used for the fit."
    )
    output_dir = config.get('paths', 'reports_dir')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    args = parser.parse_args()

    assess_result(args.directory, args.set_id, args.model_name, output_dir)


if __name__ == "__main__":
    main()
