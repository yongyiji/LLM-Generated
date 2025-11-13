import re
from collections import defaultdict
import chardet

# ====== Configuration Paths ======
CLONES_FILE = "clones.txt"
FILE_LIST = "file.txt"

# ====== Detect file encoding automatically ======
with open(FILE_LIST, "rb") as f:
    raw_data = f.read(4096)
    detected = chardet.detect(raw_data)
    encoding = detected["encoding"] or "utf-8"
    print(f"Detected encoding for file_list.txt: {encoding}")

# ====== Read file list ======
file_paths = []
with open(FILE_LIST, encoding=encoding, errors="ignore") as f:
    for line in f:
        path = line.strip()
        if not path or not ("\\" in path or "/" in path):
            continue
        file_paths.append(path)

total_files = len(file_paths)
print(f"Total number of files: {total_files}")

# ====== Detect clone file encoding automatically ======
with open(CLONES_FILE, "rb") as f:
    raw_data = f.read(4096)
    detected = chardet.detect(raw_data)
    clone_encoding = detected["encoding"] or "utf-8"
    print(f"Detected encoding for txt: {clone_encoding}")

# ====== Parse clone pairs ======
clone_pairs = 0
file_clone_count = defaultdict(int)      # Number of clone instances per file
file_clone_length = defaultdict(int)     # Total cloned lines per file

in_pairs = False
with open(CLONES_FILE, encoding=clone_encoding, errors="ignore") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        if line.startswith("clone_pairs"):
            in_pairs = True
            continue
        if not in_pairs or line == "}" or line.startswith("source_file_remarks"):
            continue

        parts = re.split(r'\s+', line)
        if len(parts) < 3:
            continue

        # Format: group_id, left, right
        _, left, right = parts[:3]

        m = re.match(r"(\d+)\.(\d+)-(\d+)", left)
        n = re.match(r"(\d+)\.(\d+)-(\d+)", right)
        if not (m and n):
            continue

        try:
            file1, s1, e1 = map(int, m.groups())
            file2, s2, e2 = map(int, n.groups())
        except ValueError:
            continue

        # Validate file indices are within bounds
        if not (1 <= file1 <= total_files and 1 <= file2 <= total_files):
            continue

        clone_pairs += 1
        len1 = e1 - s1
        len2 = e2 - s2
        file_clone_count[file1] += 1
        file_clone_count[file2] += 1
        file_clone_length[file1] += len1
        file_clone_length[file2] += len2

# ====== Output results ======
total_files_with_clones = len(file_clone_count)
file_clone_ratio = (total_files_with_clones / total_files * 100) if total_files else 0

print(f"\nNumber of detected clone pairs: {clone_pairs}")
print(f"Number of files containing clones: {total_files_with_clones}")
print(f"Clone file ratio: {file_clone_ratio:.2f}% ({total_files_with_clones}/{total_files})")