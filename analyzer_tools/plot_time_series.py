#!/usr/bin/env python3
"""
Time Series Reflectivity Plotter

Plot multiple reflectivity curves together with vertical offset for time series visualization.
"""

import glob
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

import click
import matplotlib.pyplot as plt
import numpy as np


def natural_sort_key(s: str) -> List:
    """
    Sort strings with embedded numbers in natural order.
    E.g., ['file_1', 'file_10', 'file_2'] -> ['file_1', 'file_2', 'file_10']
    """
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


def load_reflectivity_file(filepath: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Load a reflectivity data file.
    
    Expects 4 columns: Q, R, dR, dQ
    
    Args:
        filepath: Path to the data file
        
    Returns:
        Tuple of (Q, R, dR, dQ) arrays
    """
    data = np.loadtxt(filepath)
    if data.ndim == 1:
        raise ValueError(f"File {filepath} has only 1 dimension")
    
    if data.shape[1] >= 4:
        return data[:, 0], data[:, 1], data[:, 2], data[:, 3]
    elif data.shape[1] == 3:
        return data[:, 0], data[:, 1], data[:, 2], np.zeros_like(data[:, 0])
    elif data.shape[1] == 2:
        return data[:, 0], data[:, 1], np.zeros_like(data[:, 1]), np.zeros_like(data[:, 0])
    else:
        raise ValueError(f"File {filepath} has unexpected number of columns: {data.shape[1]}")


def plot_time_series(
    data_dir: str,
    pattern: str = "*.txt",
    offset_factor: float = 10.0,
    exclude: Optional[str] = None,
    output: Optional[str] = None,
    title: Optional[str] = None,
    figsize: Tuple[float, float] = (10, 8),
    show_legend: bool = True,
    reverse: bool = False,
    colormap: str = "viridis",
    show_errors: bool = False,
) -> plt.Figure:
    """
    Plot multiple reflectivity curves with vertical offset.
    
    Args:
        data_dir: Directory containing data files
        pattern: Glob pattern to match files
        offset_factor: Multiplicative offset between curves (in log scale)
        exclude: Exclude files containing this string
        output: Output file path for saving the plot
        title: Plot title
        figsize: Figure size (width, height)
        show_legend: Whether to show legend
        reverse: If True, reverse the order (first file at top)
        colormap: Matplotlib colormap name
        show_errors: Whether to show error bars
        
    Returns:
        Matplotlib figure
    """
    data_dir = Path(data_dir)
    all_files = glob.glob(str(data_dir / pattern))
    
    # Filter and sort files
    if exclude:
        files = [f for f in all_files if exclude not in Path(f).name]
    else:
        files = all_files
    
    # Exclude JSON files by default
    files = [f for f in files if not f.endswith('.json')]
    
    files = sorted(files, key=lambda x: natural_sort_key(Path(x).name))
    
    if not files:
        raise ValueError(f"No files found matching pattern {pattern} in {data_dir}")
    
    print(f"Found {len(files)} files to plot")
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Get colormap
    cmap = plt.get_cmap(colormap)
    colors = [cmap(i / max(1, len(files) - 1)) for i in range(len(files))]
    
    # Determine order (first file at bottom by default)
    if reverse:
        files = files[::-1]
        colors = colors[::-1]
    
    # Plot each file
    for i, filepath in enumerate(files):
        filename = Path(filepath).stem
        
        try:
            Q, R, dR, dQ = load_reflectivity_file(filepath)
            
            # Apply offset (multiplicative in log scale)
            offset = offset_factor ** i
            R_offset = R * offset
            dR_offset = dR * offset
            
            # Create label (shorten if needed)
            label = filename
            if len(label) > 30:
                label = label[:27] + "..."
            
            if show_errors:
                ax.errorbar(Q, R_offset, yerr=dR_offset, fmt='o-', markersize=2,
                           color=colors[i], label=label, alpha=0.8, linewidth=0.5)
            else:
                ax.plot(Q, R_offset, 'o-', markersize=2, color=colors[i],
                       label=label, alpha=0.8, linewidth=0.5)
            
        except Exception as e:
            print(f"  Warning: Could not load {filename}: {e}")
    
    # Configure axes
    ax.set_yscale('log')
    ax.set_xlabel('Q (Å⁻¹)')
    ax.set_ylabel('Reflectivity (offset)')
    
    if title:
        ax.set_title(title)
    else:
        ax.set_title(f'Time Series: {data_dir.name}')
    
    # Legend
    if show_legend and len(files) <= 20:
        ax.legend(loc='upper right', fontsize=8, ncol=1)
    elif show_legend:
        ax.legend(loc='upper right', fontsize=6, ncol=2)
    
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save if output specified
    if output:
        fig.savefig(output, dpi=150, bbox_inches='tight')
        print(f"Saved plot to: {output}")
    
    return fig


@click.command()
@click.option(
    '--data-dir',
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help='Directory containing reflectivity data files'
)
@click.option(
    '--pattern',
    type=str,
    default='*.txt',
    show_default=True,
    help='Glob pattern to match files'
)
@click.option(
    '--offset',
    type=float,
    default=10.0,
    show_default=True,
    help='Multiplicative offset factor between curves'
)
@click.option(
    '--exclude',
    type=str,
    default=None,
    help='Exclude files containing this string'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    default=None,
    help='Output file path for saving the plot (e.g., plot.png)'
)
@click.option(
    '--title', '-t',
    type=str,
    default=None,
    help='Plot title'
)
@click.option(
    '--reverse',
    is_flag=True,
    help='Reverse order (first file at top instead of bottom)'
)
@click.option(
    '--colormap', '-c',
    type=str,
    default='viridis',
    show_default=True,
    help='Matplotlib colormap name'
)
@click.option(
    '--errors',
    is_flag=True,
    help='Show error bars'
)
@click.option(
    '--no-legend',
    is_flag=True,
    help='Hide legend'
)
@click.option(
    '--show/--no-show',
    default=True,
    help='Show interactive plot window'
)
def main(data_dir: str, pattern: str, offset: float, exclude: Optional[str],
         output: Optional[str], title: Optional[str], reverse: bool,
         colormap: str, errors: bool, no_legend: bool, show: bool) -> int:
    """Plot time series of reflectivity curves with vertical offset.
    
    Reads reflectivity data files (Q, R, dR, dQ columns) and plots them
    together with a multiplicative vertical offset for easy comparison.
    
    Examples:
    
    \b
      # Basic usage - plot all .txt files
      plot-time-series --data-dir /path/to/data
    
    \b
      # Save to file
      plot-time-series --data-dir /path/to/data -o timeseries.png
    
    \b
      # Custom offset and colormap
      plot-time-series --data-dir /path/to/data --offset 5 --colormap plasma
    
    \b
      # Exclude certain files
      plot-time-series --data-dir /path/to/data --exclude reduction
    """
    print("Time Series Reflectivity Plotter")
    print("=" * 60)
    print(f"Data directory: {data_dir}")
    print(f"Pattern: {pattern}")
    print(f"Offset factor: {offset}")
    print()
    
    try:
        fig = plot_time_series(
            data_dir=data_dir,
            pattern=pattern,
            offset_factor=offset,
            exclude=exclude,
            output=output,
            title=title,
            show_legend=not no_legend,
            reverse=reverse,
            colormap=colormap,
            show_errors=errors,
        )
        
        if show:
            plt.show()
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
