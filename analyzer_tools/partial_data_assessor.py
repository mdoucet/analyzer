import os
import glob
import numpy as np
import matplotlib.pyplot as plt
import re
from datetime import datetime
import argparse
import configparser

def get_data_files(set_id, data_dir):
    """
    Get the file paths for a given set_id.
    """
    file_pattern = os.path.join(data_dir, f"REFL_{set_id}_*_partial.txt")
    return sorted(glob.glob(file_pattern))

def read_data(file_path):
    """
    Read the 4-column data from a file.
    """
    # Q, R, dR, dQ
    return np.loadtxt(file_path, skiprows=1, usecols=(0,1,2,3))

def find_overlap_regions(data_parts):
    """
    Find the overlapping Q regions between adjacent data parts.
    
    Returns a list of tuples, where each tuple contains the two overlapping data parts.
    """
    if not data_parts or len(data_parts) < 2:
        return []

    overlaps = []
    for i in range(len(data_parts) - 1):
        data1 = data_parts[i]
        data2 = data_parts[i+1]

        q1_min, q1_max = data1[:, 0].min(), data1[:, 0].max()
        q2_min, q2_max = data2[:, 0].min(), data2[:, 0].max()

        overlap_min = max(q1_min, q2_min)
        overlap_max = min(q1_max, q2_max)

        if overlap_min < overlap_max:
            overlap1 = data1[(data1[:, 0] >= overlap_min) & (data1[:, 0] <= overlap_max)]
            overlap2 = data2[(data2[:, 0] >= overlap_min) & (data2[:, 0] <= overlap_max)]
            overlaps.append((overlap1, overlap2))
            
    return overlaps

def calculate_match_metric(overlap_data1, overlap_data2):
    """
    Calculate a metric for how well two overlap regions match.
    A simple metric could be the average of the ratio of the R values.
    """
    if overlap_data1.shape[0] == 0 or overlap_data2.shape[0] == 0:
        return 0

    # Interpolate the second dataset onto the Q values of the first one
    interp_r2 = np.interp(overlap_data1[:, 0], overlap_data2[:, 0], overlap_data2[:, 1])
    
    # Calculate the weighted average of the squared differences
    weights = 1 / (overlap_data1[:, 2]**2 + np.interp(overlap_data1[:, 0], overlap_data2[:, 0], overlap_data2[:, 2])**2)
    weighted_sq_diff = np.sum(weights * (overlap_data1[:, 1] - interp_r2)**2)
    chi2 = weighted_sq_diff / len(overlap_data1)
    
    return chi2

def plot_overlap_regions(data_parts, set_id, output_dir):
    """
    Plot the overlap regions for a given data set.
    """
    fig, ax = plt.subplots(dpi=150, figsize=(6, 4))
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.15)
    for i, data in enumerate(data_parts):
        ax.errorbar(data[:, 0], data[:, 1], yerr=data[:, 2], fmt='.', label=f'Part {i+1}')

    ax.set_xlabel('Q (1/A)', fontsize=15)
    ax.set_ylabel('Reflectivity', fontsize=15)
    plt.xscale('log')
    plt.yscale('log')
    plt.legend(frameon=False)
    
    plot_path = os.path.join(output_dir, f'reflectivity_curve_{set_id}.svg')
    plt.savefig(plot_path)
    plt.close()
    return plot_path

def generate_markdown_report(set_id, metrics, plot_path, output_dir):
    """
    Generate a markdown report for a given data set.
    """
    report_file = os.path.join(output_dir, f'report_{set_id}.md')
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_section_header = "## Partial Data Assessment"
    new_content = (
        f"{new_section_header}\n"
        f"Assessment run on: {now}\n\n"
        f"![Reflectivity Curve]({os.path.basename(plot_path)})\n\n"
        "### Overlap Metrics (Chi-squared)\n\n"
    )
    for i, metric in enumerate(metrics):
        new_content += f"- Overlap {i+1}: {metric:.4f}\n"

    if os.path.exists(report_file):
        with open(report_file, 'r') as f:
            content = f.read()
        
        pattern = re.compile(rf"({re.escape(new_section_header)}.*?)(?=\n## |\Z)", re.DOTALL)
        if pattern.search(content):
            content = pattern.sub(new_content, content)
        else:
            content += "\n" + new_content
        
        with open(report_file, 'w') as f:
            f.write(content)
    else:
        with open(report_file, 'w') as f:
            f.write(f"# Report for Set ID: {set_id}\n\n{new_content}")

    print(f"Report {report_file} updated.")


def assess_data_set(set_id, data_dir, output_dir):
    """
    Main function to assess a data set.
    """
    # Get data files
    file_paths = get_data_files(set_id, data_dir)
    if len(file_paths) < 2:
        print(f"Not enough data parts for set_id {set_id}")
        return

    # Read data
    data_parts = [read_data(fp) for fp in file_paths]

    # Find overlap regions
    overlap_regions = find_overlap_regions(data_parts)

    # Calculate match metric for each overlap
    metrics = [calculate_match_metric(o1, o2) for o1, o2 in overlap_regions]

    # Plot overlap regions
    plot_path = plot_overlap_regions(data_parts, set_id, output_dir)

    # Generate markdown report
    generate_markdown_report(set_id, metrics, plot_path, output_dir)

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini')

    parser = argparse.ArgumentParser(description='Assess partial data sets.')
    parser.add_argument('set_id', type=str, help='Set ID to assess.')
    args = parser.parse_args()

    data_dir = config.get('paths', 'partial_data_dir')
    output_dir = config.get('paths', 'reports_dir')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    assess_data_set(args.set_id, data_dir, output_dir)
