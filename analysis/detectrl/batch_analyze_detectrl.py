import os
import subprocess
import pandas as pd
import json
import argparse
import numpy as np

def run_analysis_for_folder(script_path, folder, prefix):
    print(f"=== Processing {folder} ===")
    cmd = [
        "python", script_path,
        "--folder", folder,
        "--prefix", prefix
    ]
    subprocess.run(cmd, check=True)
    result_csv_path = os.path.join(folder, f"{prefix}ai_human_judgement_summary.csv")
    if not os.path.exists(result_csv_path):
        print(f"Result file not found: {result_csv_path}, skipping.")
        return None
    df = pd.read_csv(result_csv_path, keep_default_na=False, na_values=[''])
    df['file_id'] = df['global_id'].astype(str).str.split('.').str[0]
    label_cols = [col for col in df.columns if col.endswith('_label')]
    total_files = df['file_id'].nunique()
    result = []
    for col in label_cols:
        method = col.replace('_label', '')
        # If the entire column is NaN, keep NaN instead of computing 0
        if df[col].isna().all():
            result.append({
                'method': method,
                'AI_file_count': np.nan,
                'total_files': total_files,
                'AI_percent': np.nan
            })
            continue
        ai_files = df.groupby('file_id')[col].apply(lambda x: (x == 'AI').any())
        ai_count = ai_files.sum()
        ai_percent = (ai_count / total_files) * 100
        result.append({
            'method': method,
            'AI_file_count': int(ai_count),
            'total_files': total_files,
            'AI_percent': round(ai_percent, 2)
        })
    result_df = pd.DataFrame(result)
    result_df['folder'] = os.path.basename(folder)
    return result_df

def main():
    parser = argparse.ArgumentParser(description="Batch analyze AI detection results across multiple time folders")
    parser.add_argument("--script", type=str, required=True, help="Path to single-folder analysis script, e.g., analyze_detectrl_result.py")
    parser.add_argument("--base_folder", type=str, required=True, help="Parent directory containing time folders")
    parser.add_argument("--prefix", type=str, required=True, help="File prefix")
    args = parser.parse_args()
    script_path = args.script
    base_folder = args.base_folder
    prefix = args.prefix
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    # Extract parent directory name, e.g., base_folder="/pandas"
    parent_name = os.path.basename(os.path.normpath(base_folder))
    # Time folders to process
    time_folders = [
        "2021-10", "2022-10", "2023-10", "2024-10", "2025-10"
    ]
    all_results = []
    for t in time_folders:
        folder_path = os.path.join(base_folder, t)
        if not os.path.exists(folder_path):
            print(f"Folder does not exist: {folder_path}, skipping.")
            continue
        result_df = run_analysis_for_folder(script_path, folder_path, prefix)
        if result_df is not None:
            out_csv = os.path.join(folder_path, f"{t}_result_summary.csv")
            result_df.to_csv(out_csv, index=False)
            print(f"Single-period result saved: {out_csv}")
            all_results.append(result_df)
    # === Aggregate all results ===
    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)
        pivot_df = combined_df.pivot_table(index='folder', columns='method', values='AI_percent').sort_index()
        # Build output filename
        clean_prefix = prefix.rstrip('_')  # Remove trailing underscore
        pivot_filename = f"all_periods_AI_percent_summary_{parent_name}_{clean_prefix}.csv"
        pivot_csv = os.path.join(output_dir, pivot_filename)
        pivot_df.to_csv(pivot_csv)
        print(f"\n=== All-period summary saved: {pivot_csv} ===")
        print(pivot_df)
    else:
        print("No results were generated.")

if __name__ == "__main__":
    main()