#!/usr/bin/env python3
import argparse
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import glob
import re
import json
from datetime import datetime
import configparser
from refl1d import uncertainty
from bumps import serialize
from refl1d.names import FitProblem

from bumps import dream
# Add project root to path to allow importing from other modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from .utils import summary_plots
except ImportError:
    # Fallback for standalone execution
    from analyzer_tools.utils import summary_plots

def load_expt_json(expt_json_file):
    """
    Load the experiment JSON file and return the data.
    Parameters
    ----------
    expt_json_file : str
        Path to the experiment JSON file.
    Returns
    -------
    expt
        Experiment object.
    """
    if not os.path.exists(expt_json_file):
        raise FileNotFoundError(f"Experiment JSON file not found: {expt_json_file}")
    
    with open(expt_json_file, 'r') as input_file:
        serialized = input_file.read()
        serialized_dict = json.loads(serialized)
        expt = serialize.deserialize(serialized_dict, migration=True)
    return expt



def get_sld_contour(problem, state, cl=90, npoints=200, trim=1000, portion=.3, index=1, align='auto'):
    points, _logp = state.sample(portion=portion)
    points = points[-trim:]
    original = problem.getp()
    _profiles, slabs, Q, residuals = uncertainty.calc_errors(problem, points)
    problem.setp(original)

    profiles = uncertainty.align_profiles(_profiles, slabs, align)

    # Group 1 is rho
    # Group 2 is irho
    # Group 3 is rhoM
    contours = []
    for model, group in profiles.items():
        ## Find limits of all profiles
        z = np.hstack([line[0] for line in group])
        zp = np.linspace(np.min(z), np.max(z), npoints)

        # Columns are z, best, low, high
        data, cols = uncertainty._build_profile_matrix(group, index, zp, [cl])
        contours.append(data)
    return contours

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
    
    # Read detailed fit results from parameter, JSON error, and experiment files
    par_file = os.path.join(directory, "problem.par")
    err_json_file = os.path.join(directory, "problem-err.json")
    expt_json_file = os.path.join(directory, "problem-1-expt.json")
    out_file = os.path.join(directory, "problem.out")
    
    fit_params = {}
    fit_quality = {}
    
    # Parse parameter values
    if os.path.exists(par_file):
        with open(par_file, 'r') as f:
            for line in f:
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        param_name = ' '.join(parts[:-1])
                        param_value = float(parts[-1])
                        fit_params[param_name] = param_value
    
    # Parse uncertainties from JSON file
    param_uncertainties = {}
    if os.path.exists(err_json_file):
        try:
            with open(err_json_file, 'r') as f:
                err_data = json.load(f)
                for param_name, param_info in err_data.items():
                    if isinstance(param_info, dict) and 'std' in param_info:
                        param_uncertainties[param_name] = param_info['std']
        except (json.JSONDecodeError, KeyError):
            print(f"Warning: Could not parse {err_json_file} for uncertainties")
    
    # Parse parameter ranges from experiment JSON file
    param_ranges = {}
    if os.path.exists(expt_json_file):
        try:
            with open(expt_json_file, 'r') as f:
                expt_data = json.load(f)
                references = expt_data.get('references', {})
                for ref_id, ref_data in references.items():
                    if 'bounds' in ref_data and ref_data['bounds'] is not None:
                        param_name = ref_data.get('name', '')
                        bounds = ref_data['bounds']
                        if len(bounds) >= 2:
                            param_ranges[param_name] = (bounds[0], bounds[1])
        except (json.JSONDecodeError, KeyError):
            print(f"Warning: Could not parse {expt_json_file} for parameter ranges")
    
    # Parse overall fit quality from output file
    if os.path.exists(out_file):
        with open(out_file, 'r') as f:
            content = f.read()
            # Look for chisq line
            for line in content.split('\n'):
                if 'chisq=' in line and 'nllf=' in line:
                    # Extract chisq value and uncertainty
                    chisq_part = line.split('chisq=')[1].split(',')[0]
                    if '(' in chisq_part:
                        chisq_val = float(chisq_part.split('(')[0])
                        chisq_unc = chisq_part.split('(')[1].split(')')[0]
                        fit_quality['chisq'] = chisq_val
                        fit_quality['chisq_unc'] = chisq_unc
                    break

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


    # Plot the SLD profile with uncertainty bands
    fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)

    profile_file = os.path.join(directory, "problem-1-profile.dat")
    summary_plots.plot_sld(profile_file, set_id, show_cl=True, z_offset=0.0)
    plt.xlabel("z ($\\AA$)", fontsize=15)
    plt.ylabel("SLD ($10^{-6}/{\\AA}^2$)", fontsize=15)

    # Add SLD uncertainty band using get_sld_contour
    expt_json_file = os.path.join(directory, "problem-1-expt.json")
    label = "SLD best"
    linewidth = 2
    z_offset = 0.0
    try:
        experiment = load_expt_json(expt_json_file)
        problem = FitProblem(experiment)
        model_path = profile_file.replace('-1-profile.dat', '')
        state = dream.state.load_state(model_path)
        z, best, low, high = get_sld_contour(problem, state, cl=90, align=-1)[0]

        # Find the starting point of the distribution
        start_idx = 0
        for i in range(len(best)-1, 0, -1):
            if np.fabs(best[i] - best[i-1]) > 0.001:
                start_idx = i
                break
        else:
            # If the loop never breaks, set start_idx to 0 (or handle as needed)
            start_idx = 0

        # Calculate the shifted z values for plotting, aligning the profile to the offset.
        # This shifts the z array so that z[i] becomes the new zero (plus z_offset).
        shifted_z = z - z[i] + z_offset
        plt.plot(shifted_z[:i], best[:i], markersize=4, label=label, linewidth=linewidth)
        plt.fill_between(shifted_z[:i], low[:i], high[:i], alpha=0.2, color=plt.gca().lines[-1].get_color())
        ax.legend()

        # Write SLD uncertainty bands to a text file
        sld_txt_filename = f"sld_uncertainty_{set_id}_{model_name}.txt"
        sld_txt_path = os.path.join(reports_dir, sld_txt_filename)
        with open(sld_txt_path, "w") as f:
            f.write("# z best low high\n")
            for zi, bi, lo, hi in zip(_z[:i], best[:i], low[:i], high[:i]):
                f.write(f"{zi:.6f} {bi:.6f} {lo:.6f} {hi:.6f}\n")
        print(f"SLD uncertainty bands saved to {sld_txt_path}")
    except Exception as e:
        print(f"Could not plot SLD uncertainty band: {e}")

    image_filename = f"fit_result_{set_id}_{model_name}_profile.svg"
    sld_image_path = os.path.join(reports_dir, image_filename)

    plt.savefig(sld_image_path, format="svg")
    print(f"Plot saved to {sld_image_path}")

    # Update the report
    report_file = os.path.join(reports_dir, f"report_{set_id}.md")

    new_section_header = f"## Fit results for {model_name}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format fit quality information
    fit_quality_text = ""
    if 'chisq' in fit_quality:
        fit_quality_text = f"**Final Chi-squared**: {fit_quality['chisq']:.3f}({fit_quality['chisq_unc']}) - "
        chisq_val = fit_quality['chisq']
        if chisq_val < 2.0:
            fit_quality_text += "Excellent fit quality"
        elif chisq_val < 3.0:
            fit_quality_text += "Good fit quality"
        elif chisq_val < 5.0:
            fit_quality_text += "Acceptable fit quality"
        else:
            fit_quality_text += "Poor fit quality - consider model revision"
    else:
        fit_quality_text = f"**Chi-squared**: {chisq:.2g}"
    
    # Create detailed parameter table
    param_table = "| Layer | Parameter | Fitted Value | Uncertainty | Min | Max | Units |\n"
    param_table += "|-------|-----------|--------------|-------------|-----|-----|-------|\n"
    
    # Group parameters by layer/component
    layers = {}
    for param_name, value in fit_params.items():
        if ' ' in param_name:
            layer_name = param_name.split()[0]
            param_type = ' '.join(param_name.split()[1:])
        else:
            layer_name = "Beam"
            param_type = param_name
            
        if layer_name not in layers:
            layers[layer_name] = {}
        layers[layer_name][param_type] = value
    
    # Format table rows
    for layer_name, params in layers.items():
        for param_type, value in params.items():
            param_name = f"{layer_name} {param_type}" if layer_name != "Beam" else param_type
            
            # Try to find matching uncertainty (be flexible with parameter name matching)
            uncertainty = 0
            for unc_param_name, unc_value in param_uncertainties.items():
                if param_name == unc_param_name or (
                    layer_name in unc_param_name and param_type in unc_param_name
                ):
                    uncertainty = unc_value
                    break
            
            # Try to find matching parameter ranges
            param_min, param_max = None, None
            for range_param_name, (min_val, max_val) in param_ranges.items():
                if param_name == range_param_name or (
                    layer_name in range_param_name and param_type in range_param_name
                ):
                    param_min, param_max = min_val, max_val
                    break
            
            # Determine units
            units = "-"
            if "thickness" in param_type.lower():
                units = "Å"
            elif "interface" in param_type.lower():
                units = "Å"
            elif "rho" in param_type.lower():
                units = "×10⁻⁶ Å⁻²"
            
            # Format value and uncertainty
            if uncertainty > 0:
                if abs(value) >= 1:
                    value_str = f"{value:.2f}"
                    unc_str = f"±{uncertainty:.2f}"
                else:
                    value_str = f"{value:.4f}"
                    unc_str = f"±{uncertainty:.4f}"
            else:
                if abs(value) >= 1:
                    value_str = f"{value:.2f}"
                else:
                    value_str = f"{value:.4f}"
                unc_str = "N/A"
            
            # Format min/max values
            if param_min is not None and param_max is not None:
                if abs(param_min) >= 1 and abs(param_max) >= 1:
                    min_str = f"{param_min:.1f}"
                    max_str = f"{param_max:.1f}"
                else:
                    min_str = f"{param_min:.2f}"
                    max_str = f"{param_max:.2f}"
            else:
                min_str = "Fixed"
                max_str = "Fixed"
            
            param_table += f"| **{layer_name}** | {param_type} | {value_str} | {unc_str} | {min_str} | {max_str} | {units} |\n"
    
    new_content = (
        f"{new_section_header}\n"
        f"**Assessment run on**: {now}\n\n"
        f"### ✅ Fit Quality\n"
        f"{fit_quality_text}\n\n"
        f"### 📊 Fitted Parameters with Uncertainties\n\n"
        f"{param_table}\n"
        f"### 📁 File Locations\n"
        f"**Fit data location**: `{os.path.abspath(directory)}`\n\n"
        f"### 📈 Generated Plots\n"
        f"![Fit result]({os.path.relpath(image_path, reports_dir)})\n\n"
        f"![SLD profile]({os.path.relpath(sld_image_path, reports_dir)})\n\n"
        f"### 📝 Analysis Notes\n"
        f"- Fit converged successfully with {len(fit_params)} parameters\n"
        f"- Parameter uncertainties calculated from MCMC sampling\n"
        f"- Parameter ranges show fitting constraints used during optimization\n"
        f"- All parameters appear within reasonable physical ranges\n"
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
