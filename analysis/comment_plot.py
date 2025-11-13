import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import glob
import itertools

# Root directory containing summary CSV files
base_dir = "detectrl_result_folder"

# Output directory for generated plots
output_dir = "output_directory"
os.makedirs(output_dir, exist_ok=True)

# Columns (methods) to plot
columns_to_plot = ['DetectGPT', 'Fast', 'LRR', 'bino',
                   'entropy', 'likelihood', 'logRank', 'rank']

# Line colors for each method (consistent across all plots)
method_colors = {
    'DetectGPT': '#1f77b4',
    'Fast': '#ff7f0e',
    'LRR': '#2ca02c',
    'bino': '#9467bd',
    'entropy': '#8c564b',
    'likelihood': '#e377c2',
    'logRank': '#7f7f7f',
    'rank': '#17becf'
}

# Extract repository name from filename, e.g., act_comments -> act
def extract_repo_name(file_name, target_kind):
    if "summary_" in file_name and "_content" in file_name:
        middle = file_name.split("summary_")[1].split("_content")[0]
        if target_kind == "comment":
            if middle.endswith("_comments"):
                return middle.replace("_comments", "")
        elif target_kind == "text":
            if middle.endswith("_text"):
                return middle.replace("_text", "")
    return None

# Collect CSV files grouped by repository and kind (comment/text)
def collect_files_by_kind(target_kind="comment"):
    csv_files = glob.glob(os.path.join(base_dir, "*.csv"))
    grouped = {}
    for path in csv_files:
        fname = os.path.basename(path)
        repo = extract_repo_name(fname, target_kind)
        if repo:
            grouped[repo] = path
    return grouped

# Normalize 'folder' column to year string (e.g., 2021, 2022, ...)
def normalize_folder_column(df):
    folder_values = []
    for v in df['folder']:
        s = str(v)
        if len(s) >= 4 and s[:4].isdigit():
            folder_values.append(s[:4])
        else:
            folder_values.append(s)
    df['folder'] = folder_values
    return df

# Detect overlapping lines between methods within a repository
def detect_overlaps(df, repo, group_name, threshold=0.5):
    overlaps = []
    available_methods = [m for m in columns_to_plot if m in df.columns]
    for m1, m2 in itertools.combinations(available_methods, 2):
        diff = np.abs(df[m1] - df[m2])
        if np.any(diff < threshold):
            overlaps.append((m1, m2))
    if overlaps:
        overlap_pairs = ', '.join([f"{a} and {b}" for a, b in overlaps])
        print(f"[comments_group_{group_name} - {repo}] Overlap detected: {overlap_pairs}")
    return overlaps

# Plot a subset of repositories in a fixed 4x1 layout
def plot_subset(repos_subset, name, target_kind="comment"):
    plt.rcParams.update({
        'font.size': 10,
        'axes.titlesize': 16,
        'axes.labelsize': 14,
        'xtick.labelsize': 12,
        'ytick.labelsize': 12,
    })
    
    repo_to_file = collect_files_by_kind(target_kind)
    data_per_repo = {}

    # Load data for each repository
    for repo in repos_subset:
        if repo in repo_to_file:
            csv_path = repo_to_file[repo]
            try:
                df = pd.read_csv(csv_path)
                if "folder" in df.columns:
                    df = normalize_folder_column(df)
                    data_per_repo[repo] = df
            except Exception as e:
                print(f"Failed to read {csv_path}: {e}")

    # Fixed layout: 4 rows x 1 column
    n_rows = 4
    n_cols = 1
    fig_width = 6
    fig_height = 3 * n_rows
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height), squeeze=False)

    for idx in range(n_rows):
        ax = axes[idx][0]
        if idx < len(repos_subset):
            repo = repos_subset[idx]
            if repo in data_per_repo:
                df = data_per_repo[repo]
                # Check for overlaps
                detect_overlaps(df, repo, name, threshold=0.5)
                # Plot each method
                for method in columns_to_plot:
                    if method not in df.columns:
                        continue
                    ax.plot(
                        df['folder'],
                        df[method],
                        label=method,
                        marker='o',
                        linewidth=2,
                        markersize=3,
                        color=method_colors.get(method, None)
                    )
                ax.set_title(repo, fontsize=12, fontweight='bold')
                ax.set_xlabel('Year', fontsize=10)
                ax.set_ylabel('Percentage (%)', fontsize=10)
                ax.tick_params(axis='x', labelrotation=0, labelsize=10)
                ax.tick_params(axis='y', labelsize=8)
                ax.set_xticks(sorted(df['folder'].unique()))
            else:
                ax.text(0.5, 0.5, f"No data for {repo}", ha='center', va='center', fontsize=10)
                ax.axis('off')
        else:
            ax.axis('off')

    # Add unified legend (commented out to avoid clutter; can be enabled if needed)
    # handles, labels = ax.get_legend_handles_labels()
    # if handles:
    #     fig.legend(handles, labels, loc='lower center', ncol=4952, fontsize=9)

    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    out_path = os.path.join(output_dir, f"comments_group_{name}.png")
    plt.savefig(out_path, dpi=500, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved plot: {out_path}")

# Main workflow: Generate two comment-based group plots
def main():
    group1 = ['go-github', 'guava', 'liquid', 'zap']
    group2 = ['act', 'jadx', 'kafka', 'pandas']
    plot_subset(group1, "1", target_kind="comment")
    plot_subset(group2, "2", target_kind="comment")

if __name__ == "__main__":
    main()