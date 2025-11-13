import json
import os
import pandas as pd
import argparse
import numpy as np

def main():
    parser = argparse.ArgumentParser(description="Determine whether text is AI-generated based on thresholds")
    parser.add_argument("--folder", type=str, required=True, help="Folder path containing data files")
    parser.add_argument("--prefix", type=str, required=True, help="File prefix, e.g., text_content_small_size_")
    args = parser.parse_args()
    folder = args.folder
    prefix = args.prefix

    # === Feature names and thresholds for each method (largest dataset) ===
    criteria = {
        "bino_data": ("bino_score", -0.9048),
        "DetectGPT_detected": ("detectgpt_score_10", 1.0311),
        "entropy_data": ("entropy", 3.7868),
        "Fast_DetectGPT_results": ("text_crit", 5.4758),
        "likelihood_results": ("log_likelihood", -2.2392),
        "logRank_data": ("text_logrank", -1.0869),
        "LRR_result": ("text_LRR", 2.1119),
        "NPR_results": ("npr_100", 0.0782),
        "rank_data": ("text_rank", -17.7182)
    }



    results = []
    base_df = None

    for key, (feature, threshold) in criteria.items():
        file_path = os.path.join(folder, f"{prefix}{key}.json")
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}, skipping.")
            continue

        # Load JSON file
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
                print(f"Processing file: {file_path}")
            except json.JSONDecodeError:
                print(f"Invalid JSON format in {file_path}, skipping.")
                continue

        if isinstance(data, dict):
            data = list(data.values())
        df = pd.DataFrame(data)

        if 'global_id' not in df.columns:
            print(f"Missing 'global_id' column in {file_path}, skipping.")
            continue
        if feature not in df.columns:
            print(f"Feature {feature} not found in {file_path}, skipping.")
            continue

        print(f"Processing: {key} -> {feature}, threshold: {threshold}")
        label_col = f"{key}_label"

        # Assign label: AI if value > threshold, human otherwise, NaN if null
        df[label_col] = df[feature].apply(
            lambda x: "AI" if pd.notnull(x) and x > threshold
            else ("human" if pd.notnull(x) else np.nan)
        )

        df = df[['global_id', feature, label_col]]
        if base_df is None:
            base_df = df[['global_id']].copy()

        results.append(df[['global_id', feature, label_col]])

    # === Merge all results ===
    if results and base_df is not None:
        combined = base_df.copy()
        for result_df in results:
            combined = pd.merge(combined, result_df, on='global_id', how='left')

        # Clean up column names
        new_columns = []
        for col in combined.columns:
            if col == 'global_id':
                new_columns.append(col)
            elif col.endswith("_label"):
                name = col.replace("_data_label", "_label").replace("_result_label", "_label").replace("_results_label", "_label")
                parts = name.split("_")
                if len(parts) > 2:
                    name = parts[0] + "_label"
                new_columns.append(name)
            else:
                new_columns.append(col)
        combined.columns = new_columns

        output_file = os.path.join(folder, f"{prefix}ai_human_judgement_summary.csv")

        # Force label columns to object type to preserve NaN (avoid conversion to 0)
        for col in combined.columns:
            if col.endswith('_label'):
                combined[col] = combined[col].astype('object')

        combined.to_csv(output_file, index=False, na_rep='')
        print(f"Result file generated: {output_file}")
        print(f"Total records: {len(combined)}")

        df = combined
    else:
        print(f"No valid data files found in {folder}, skipping analysis.")
        return  # Exit gracefully without crashing

    # Extract main file ID from global_id
    df['file_id'] = df['global_id'].astype(str).str.split('.').str[0]
    label_cols = [col for col in df.columns if col.endswith('_label')]
    total_files = df['file_id'].nunique()
    result = []

    for col in label_cols:
        method = col.replace('_label', '')
        if df[col].isna().all():
            result.append({
                'method': method,
                'AI_file_count': np.nan,
                'total_files': total_files,
                'AI_percent': np.nan
            })
            continue

        # Count files where at least one chunk is labeled AI
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
    print(result_df)

    # Summarize per-chunk majority vote
    def summarize_split(row):
        labels = [row[col] for col in label_cols]
        ai_count = labels.count('AI')
        human_count = labels.count('human')
        majority_label = 'AI' if ai_count > human_count else 'human'
        all_same_label = len(set([l for l in labels if pd.notnull(l)])) <= 1
        return pd.Series({'majority_label': majority_label, 'all_same_label': all_same_label})

    split_df = df.copy()
    split_df[['majority_label', 'all_same_label']] = df.apply(summarize_split, axis=1)
    split_result = split_df[['global_id', 'majority_label', 'all_same_label']]
    print("Per-chunk judgment result:")
    print(split_result.head())

if __name__ == "__main__":
    main()