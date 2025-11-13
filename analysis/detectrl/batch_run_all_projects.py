import subprocess
import os

# === Fixed paths ===
SCRIPT_PATH = "analyze_detectrl_result.py"
BATCH_SCRIPT = "batch_analyze_detectrl.py"

# === Root directories to process ===
BASE_FOLDERS = [
    "pandas",
    "act",
    "guava",
    "jadx",
    "go-github",
    "liquid",
    "zap",
    "kafka",
]

# === File prefixes to process ===
PREFIXES = [
    "comments_content_small_size_",
]

# === Execute analysis ===
for base in BASE_FOLDERS:
    for prefix in PREFIXES:
        print(f"\n=== Processing {base} ({prefix}) ===")
        cmd = [
            "python", BATCH_SCRIPT,
            "--script", SCRIPT_PATH,
            "--base_folder", base,
            "--prefix", prefix
        ]
        try:
            subprocess.run(cmd, check=True)
            print(f"Completed: {os.path.basename(base)} - {prefix}")
        except subprocess.CalledProcessError:
            print(f"Failed: {os.path.basename(base)} - {prefix}")