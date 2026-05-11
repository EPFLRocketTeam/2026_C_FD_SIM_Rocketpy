import argparse
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
import seaborn as sns
import os
import re
import glob

def compute_stats(df):
    grouped = df.groupby('gen')
    best_fit = grouped['fitness'].max()
    mean_fit = grouped['fitness'].mean()
    min_fit = grouped['fitness'].min()
    max_fit = grouped['fitness'].max()

    best_apogee = grouped['apogee'].max()
    mean_apogee = grouped['apogee'].mean()
    min_apogee = grouped['apogee'].min()
    max_apogee = grouped['apogee'].max()

    return (best_fit, mean_fit, min_fit, max_fit, best_apogee, mean_apogee, min_apogee, max_apogee)

def plot_best_fitness(best_fit, label='Best Fitness'):
    plt.figure(figsize=(10, 6))
    gens = best_fit.index.values
    plt.plot(gens, best_fit.values, marker='o', linestyle='-', color='b', label=label)
    plt.xlabel('Generation')
    plt.ylabel('Fitness')
    plt.title('Best Fitness per Generation')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

def plot_mean_fitness_with_error(mean_fit, min_fit, max_fit):
    plt.figure(figsize=(10, 6))
    gens = mean_fit.index.values
    yerr_lower = mean_fit.values - min_fit.values
    yerr_upper = max_fit.values - mean_fit.values
    errors = np.vstack([yerr_lower, yerr_upper])
    plt.bar(gens, mean_fit.values, yerr=errors, capsize=5, color='skyblue', edgecolor='navy', align='center', label='Mean Fitness')
    plt.xlabel('Generation')
    plt.ylabel('Fitness')
    plt.title('Mean Fitness per Generation with Min‑Max Range')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.legend()
    plt.tight_layout()

def plot_best_apogee(best_apogee):
    plt.figure(figsize=(10, 6))
    gens = best_apogee.index.values
    plt.plot(gens, best_apogee.values, marker='s', linestyle='--', color='g', label='Best Apogee (m)')
    plt.axhline(y=3000, color='r', linestyle=':', label='Target Apogee (3000 m)')
    plt.xlabel('Generation')
    plt.ylabel('Apogee (m)')
    plt.title('Best Apogee per Generation')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

def plot_mean_apogee_with_error(mean_apogee, min_apogee, max_apogee):
    plt.figure(figsize=(10, 6))
    gens = mean_apogee.index.values
    yerr_lower = mean_apogee.values - min_apogee.values
    yerr_upper = max_apogee.values - mean_apogee.values
    errors = np.vstack([yerr_lower, yerr_upper])
    plt.bar(gens, mean_apogee.values, yerr=errors, capsize=5, color='lightgreen',
            edgecolor='darkgreen', align='center', label='Mean Apogee')
    plt.axhline(y=3000, color='r', linestyle=':', label='Target Apogee (3000 m)')
    plt.xlabel('Generation')
    plt.ylabel('Apogee (m)')
    plt.title('Mean Apogee per Generation with Min‑Max Range')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.legend()
    plt.tight_layout()

def plot_drift_evolution(df):
    """Best drift per generation (lower is better)."""
    grouped = df.groupby('gen')
    best_drift = grouped['drift'].min()   # we want minimal drift
    plt.figure(figsize=(10, 6))
    gens = best_drift.index.values
    plt.plot(gens, best_drift.values, marker='x', linestyle='-', color='purple', label='Min Drift (m)')
    plt.xlabel('Generation')
    plt.ylabel('Drift (m)')
    plt.title('Best (Minimum) Drift per Generation')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()


def plot_sm_evolution(df):
    """Mean stability margin with error bars, plus acceptable bounds."""
    grouped = df.groupby('gen')
    mean_sm = grouped['sm'].mean()
    min_sm = grouped['sm'].min()
    max_sm = grouped['sm'].max()

    plt.figure(figsize=(10, 6))
    gens = mean_sm.index.values
    yerr_lower = mean_sm.values - min_sm.values
    yerr_upper = max_sm.values - mean_sm.values
    errors = np.vstack([yerr_lower, yerr_upper])
    plt.bar(gens, mean_sm.values, yerr=errors, capsize=5, color='salmon',
            edgecolor='maroon', label='Mean Stability Margin')
    plt.axhline(y=1.5, color='green', linestyle='--', label='Min allowed (1.5)')
    plt.axhline(y=5.0, color='green', linestyle='--', label='Max allowed (5.0)')
    plt.xlabel('Generation')
    plt.ylabel('Stability Margin')
    plt.title('Mean Stability Margin per Generation with Min‑Max Range')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.legend()
    plt.tight_layout()


def plot_parameter_traces(df):
    """Trace of each variable's mean value across generations."""
    param_cols = [c for c in df.columns if c not in ['gen', 'iter', 'fitness', 'apogee', 'drift', 'sm']]
    n_params = len(param_cols)
    if n_params == 0:
        return
    ncols = 3
    nrows = int(np.ceil(n_params / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(15, 4 * nrows))
    axes = np.array(axes).flatten()
    for i, col in enumerate(param_cols):
        ax = axes[i]
        grouped = df.groupby('gen')[col]
        mean_val = grouped.mean()
        gen_vals = mean_val.index.values
        ax.plot(gen_vals, mean_val.values, marker='.', linestyle='-', color='teal')
        ax.set_title(col.replace('_', ' ').title())
        ax.set_xlabel('Generation')
        ax.set_ylabel(col)
        ax.grid(True, linestyle=':', alpha=0.6)
    for j in range(i+1, len(axes)):
        fig.delaxes(axes[j])
    fig.suptitle('Mean Parameter Values Across Generations', fontsize=14)
    plt.tight_layout()


def plot_correlation_heatmap(df):
    """Heatmap of correlations between all numeric variables."""
    param_cols = [c for c in df.columns if c not in ['gen', 'iter']]
    corr = df[param_cols].corr()
    plt.figure(figsize=(12, 10))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='coolwarm', square=True, linewidths=0.5, cbar_kws={"shrink": 0.8})
    plt.title('Correlation Matrix of Design Parameters and Outputs')
    plt.tight_layout()


def plot_apogee_fitness_scatter(df):
    """Scatter of apogee vs fitness for all individuals, color by generation."""
    plt.figure(figsize=(10, 6))
    scatter = plt.scatter(df['apogee'], df['fitness'], c=df['gen'], cmap='viridis', alpha=0.7, edgecolors='w', linewidth=0.5)
    
    plt.colorbar(scatter, label='Generation')
    plt.xlabel('Apogee (m)')
    plt.ylabel('Fitness')
    plt.title('Fitness vs Apogee for All Evaluated Designs')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()


def plot_feasibility(df):
    """Stacked bar of feasible vs infeasible designs per generation.
       Feasible: apogee > 0 and 1.5 <= sm <= 5.0"""
    feasible = (df['apogee'] > 0) & (df['sm'] >= 1.5) & (df['sm'] <= 5.0)
    df_feas = df.assign(feasible=feasible)
    counts = df_feas.groupby(['gen', 'feasible']).size().unstack(fill_value=0)
    if True not in counts.columns:
        counts[True] = 0
    if False not in counts.columns:
        counts[False] = 0
    counts = counts.sort_index()

    plt.figure(figsize=(10, 6))
    gens = counts.index.values
    plt.bar(gens, counts[True], color='green', label='Feasible')
    plt.bar(gens, counts[False], bottom=counts[True], color='red', label='Infeasible')
    plt.xlabel('Generation')
    plt.ylabel('Number of Designs')
    plt.title('Feasible vs Infeasible Designs per Generation')
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()


def parse_timestamp_from_filename(filename):
    """Extract timestamp from a backtest_algo_YYYYMMDDHHMMSS.csv filename."""
    base = os.path.basename(filename)
    match = re.search(r'(\d{14})', base)
    if match: return match.group(1)
    return ""

def find_latest_backtest():
    """Return the path to the newest CSV in the backtests/ folder."""
    backtest_dir = "backtests"
    if not os.path.isdir(backtest_dir): raise FileNotFoundError(f"Directory '{backtest_dir}' not found.")
    csv_files = glob.glob(os.path.join(backtest_dir, "backtest_*.csv"))
    if not csv_files: raise FileNotFoundError(f"No backtest CSV files found in '{backtest_dir}'.")
    csv_files.sort(key=lambda f: parse_timestamp_from_filename(f), reverse=True)
    return csv_files[0]

def resolve_path(filename):
    """Look for filename inside the backtests/ directory; return full path or raise error."""
    full_path = os.path.join("backtests", filename)
    if os.path.exists(full_path): return full_path
    raise FileNotFoundError(f"File not found: backtests/{filename}")

def main():
    parser = argparse.ArgumentParser(description='Visualize rocket optimization log.')
    parser.add_argument('csv_file', nargs='?', default=None, help='Name of the CSV log file (inside backtests/ folder). If not given, the latest is used.')
    args = parser.parse_args()

    if args.csv_file is None:
        selected_file = find_latest_backtest()
        print(f"Auto-selected latest log: {os.path.basename(selected_file)}")
    else:
        selected_file = resolve_path(args.csv_file)
        print(f"Using specified log: {os.path.basename(selected_file)}")

    try:
        df = pd.read_csv(selected_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    required_cols = ['gen', 'iter', 'fitness', 'apogee', 'drift', 'sm']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"Error: CSV is missing required columns: {missing}")
        sys.exit(1)

    stats = compute_stats(df)
    (best_fit, mean_fit, min_fit, max_fit,
     best_apogee, mean_apogee, min_apogee, max_apogee) = stats

    plot_best_fitness(best_fit)
    plot_mean_fitness_with_error(mean_fit, min_fit, max_fit)
    plot_drift_evolution(df)
    plot_sm_evolution(df)
    plot_parameter_traces(df)
    plot_correlation_heatmap(df)
    plot_apogee_fitness_scatter(df)
    plot_feasibility(df)
    plot_mean_apogee_with_error(mean_apogee, min_apogee, max_apogee)
    plot_best_apogee(best_apogee)

    plt.show()

if __name__ == '__main__':
    main()