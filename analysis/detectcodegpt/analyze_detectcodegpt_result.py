import os
import json
import pandas as pd
import argparse

def analyze_jsonl(file_path, threshold):
    """Analyze a single detectcodegpt_result.jsonl file"""
    group_scores = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            gid = data.get("global_id")
            npr_score = data.get("npr_score", 0)
            if gid is None:
                continue
            main_id = gid.split('.')[0]
            if npr_score > threshold:
                group_scores[main_id] = True
            else:
                group_scores.setdefault(main_id, False)
    total = len(group_scores)
    count_above = sum(group_scores.values())
    percentage = (count_above / total) * 100 if total > 0 else 0
    return total, count_above, percentage

def main():
    parser = argparse.ArgumentParser(description="Batch calculate percentage of npr_score exceeding threshold in detectcodegpt_result.jsonl files")
    parser.add_argument("--base_folder", type=str, required=True, help="Base directory path")
    args = parser.parse_args()
    
    base_folder = args.base_folder
    threshold = 1.3
    parent_name = os.path.basename(os.path.normpath(base_folder))
    
    time_folders = [
        "2021-10",  "2022-10",
        "2023-10", "2024-10", "2025-10"
    ]
    
    results = {}
    for t in time_folders:
        folder_path = os.path.join(base_folder, t)
        file_path = os.path.join(folder_path, "detectcodegpt_result.jsonl")
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}, skipping.")
            results[t] = None
            continue
        total, count_above, percentage = analyze_jsonl(file_path, threshold)
        print(f"[{t}] total={total}, above={count_above}, percentage={percentage:.2f}%")
        results[t] = round(percentage, 2)
    
    # Generate DataFrame
    df = pd.DataFrame([results], index=[parent_name])
    output_path = os.path.join(base_folder, f"detectcodegpt_threshold_summary_{parent_name}.csv")
    df.to_csv(output_path)
    print(f"\nSummary results saved: {output_path}")
    print(df)

if __name__ == "__main__":
    main()