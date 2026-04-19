#!/usr/bin/env python
"""
Plot histograms of theta offsets grouped by theta angle.

Produces two figures:
  1. Per-sample histograms (one subplot per sample, colours = theta groups)
  2. Per-angle histograms summed over all samples (one subplot per theta group)

Usage:
    python scripts/plot_offset_histograms.py ~/data/theta_offsets
    python scripts/plot_offset_histograms.py ~/data/theta_offsets --output offset_histograms.png
"""
import os
import glob

import click
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _bin_theta(theta_vals):
    """Group theta_motor values into clusters using rounding to 1 decimal."""
    return np.round(theta_vals, 1)


def _load_all(data_dir):
    """Load and concatenate all sample CSVs, adding a 'sample' column."""
    frames = []
    for sample_dir in sorted(glob.glob(os.path.join(data_dir, "sample*"))):
        sample_name = os.path.basename(sample_dir)
        for csv_file in glob.glob(os.path.join(sample_dir, "*.csv")):
            df = pd.read_csv(csv_file)
            df["sample"] = sample_name
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    combined["theta_group"] = _bin_theta(combined["theta_motor"])
    # Remove outliers: drop rows beyond 1.5× IQR within each theta group
    n_before = len(combined)
    cleaned = []
    for _, grp in combined.groupby("theta_group"):
        q1 = grp["offset"].quantile(0.25)
        q3 = grp["offset"].quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        cleaned.append(grp[(grp["offset"] >= lo) & (grp["offset"] <= hi)])
    result = pd.concat(cleaned, ignore_index=True)
    n_removed = n_before - len(result)
    if n_removed:
        click.echo(f"Removed {n_removed} outlier(s) via 1.5×IQR filter ({n_before} → {len(result)} rows)")
    return result


@click.command()
@click.argument("data_dir", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Save per-sample figure to this path (default: show).")
@click.option("--bins", default=15, help="Number of histogram bins [default: 15].")
def main(data_dir, output, bins):
    """Plot offset histograms grouped by theta for all samples in DATA_DIR."""
    df_all = _load_all(data_dir)
    if df_all.empty:
        click.echo(f"No CSV data found in {data_dir}")
        return

    samples = sorted(df_all["sample"].unique())
    theta_groups = sorted(df_all["theta_group"].unique())

    # ── Figure 1: per-sample ──────────────────────────────────────────────
    n_samples = len(samples)
    fig1, axes1 = plt.subplots(n_samples, 1, figsize=(8, 3 * n_samples), squeeze=False)

    for idx, sample_name in enumerate(samples):
        ax = axes1[idx, 0]
        sample_df = df_all[df_all["sample"] == sample_name]
        for theta in theta_groups:
            subset = sample_df[sample_df["theta_group"] == theta]
            if subset.empty:
                continue
            ax.hist(
                subset["offset"],
                bins=bins,
                alpha=0.6,
                label=f"θ ≈ {theta:.1f}°  (n={len(subset)})",
            )
        ax.set_xlabel("Offset (°)")
        ax.set_ylabel("Count")
        ax.set_title(sample_name)
        ax.legend(fontsize=8)

    fig1.tight_layout()

    # ── Figure 2: per-angle (all samples combined) ────────────────────────
    n_angles = len(theta_groups)
    fig2, axes2 = plt.subplots(1, n_angles, figsize=(5 * n_angles, 4), squeeze=False)

    for idx, theta in enumerate(theta_groups):
        ax = axes2[0, idx]
        subset = df_all[df_all["theta_group"] == theta]
        ax.hist(subset["offset"], bins=bins, alpha=0.7, color=f"C{idx}")
        ax.set_xlabel("Offset (°)")
        ax.set_ylabel("Count")
        ax.set_title(f"θ ≈ {theta:.1f}°  (n={len(subset)}, all samples)")

    fig2.tight_layout()

    # ── Save / show ───────────────────────────────────────────────────────
    if output:
        fig1.savefig(output, dpi=150)
        click.echo(f"Per-sample figure saved to {output}")
        stem, ext = os.path.splitext(output)
        per_angle_path = f"{stem}_per_angle{ext}"
        fig2.savefig(per_angle_path, dpi=150)
        click.echo(f"Per-angle figure saved to {per_angle_path}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
