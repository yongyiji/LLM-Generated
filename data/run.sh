#!/usr/bin/env bash
set -euo pipefail

# ===== REQUIRED: Path to your classify_repo_files.py script =====
CLASSIFIER="/scratch/nlp/shared/repository_result_yj/download_new.py"

# ===== Output root directory: Only preprocessing results are saved (source code is NOT retained) =====
OUT_ROOT="/scratch/nlp/shared/repository_new"

# ===== Base temporary directory (use large disk space; will be cleaned automatically) =====
BASE_TMP="${TMPDIR:-/tmp}"
mkdir -p "$OUT_ROOT" "$BASE_TMP"

# ===== Backtracking configuration: How many months back from now; step = 3 months =====
MONTHS_BACK=48
STEP=3

# ===== Parameters passed to classify_repo_files.py =====
CODE_EXT="py,java,js,ts,go,php,rb"
TEXT_EXT="md"
MAX_WORDS=512

# ===== Repositories to process (GitHub URLs) =====
REPOS=(
  "https://github.com/pandas-dev/pandas"           # company: Community (pandas-dev org)
  "https://github.com/apache/kafka"                # company: Foundation (Apache)
  "https://github.com/google/guava"                # company: Google
  "https://github.com/google/go-github"            # company: Google | lang: Go
  "https://github.com/Shopify/liquid"              # company: Shopify | lang: Ruby
  "https://github.com/uber-go/zap"                 # company: Uber | lang: Go
  "https://github.com/nektos/act"                  # company: Personal | lang: Go
  "https://github.com/skylot/jadx"                 # company: Personal | lang: Java
)

# ——— Utility functions: Date calculations ——— #

# Last moment of the month in UTC (23:59:59) — used for --before
last_moment_of_month_utc() {
  local months_ago="$1"
  date -u -d "$(date +%Y-%m-01) -${months_ago} months +1 month -1 day 23:59:59" +"%Y-%m-%d 23:59:59 UTC"
}

# YYYY-MM format (used for directory names)
yyyymm_from_months_ago() {
  local months_ago="$1"
  date -u -d "$(date +%Y-%m-01) -${months_ago} months" +"%Y-%m"
}

# ================= Main Loop ================= #
for URL in "${REPOS[@]}"; do
  PATH_PART="${URL#*github.com/}"; PATH_PART="${PATH_PART%.git}"
  ORG="${PATH_PART%%/*}"; REPO="${PATH_PART#*/}"
  REPO_NAME="$REPO"
  echo -e "\n=== Processing repository: $ORG/$REPO ==="

  # Clone repository in bare mode to a temporary directory; deleted after processing
  WORK_DIR="$(mktemp -d -p "$BASE_TMP")"
  echo "→ Temporary bare clone to: $WORK_DIR"
  if ! git clone --bare "$URL" "$WORK_DIR/.git" >/dev/null 2>&1; then
    echo " Clone failed: $URL"; rm -rf "$WORK_DIR"; continue
  fi
  git --git-dir="$WORK_DIR/.git" fetch --all --prune --tags >/dev/null 2>&1 || true

  # Track processed commit SHAs to avoid duplicates
  declare -A SEEN_SHAS=()

  for (( M=0; M<=MONTHS_BACK; M+=STEP )); do
    TARGET_HUMAN="$(yyyymm_from_months_ago "$M")"
    TARGET_CUTOFF="$(last_moment_of_month_utc "$M")"

    # Find the most recent commit before the cutoff time
    SHA="$(git --git-dir="$WORK_DIR/.git" rev-list -n 1 --before="$TARGET_CUTOFF" HEAD || true)"
    if [[ -z "${SHA:-}" ]]; then
      echo " - [$TARGET_HUMAN] No commits, skipping"
      continue
    fi
    if [[ -n "${SEEN_SHAS[$SHA]+x}" ]]; then
      echo " - [$TARGET_HUMAN] Duplicate commit ${SHA:0:7}, skipping"
      continue
    fi
    SEEN_SHAS[$SHA]=1

    OUT_DIR="$OUT_ROOT/$REPO_NAME/$TARGET_HUMAN"
    if [[ -f "$OUT_DIR/text_files.jsonl" ]]; then
      echo " - [$TARGET_HUMAN] Results already exist, skipping: $OUT_DIR"
      continue
    fi
    mkdir -p "$OUT_DIR"

    # Export snapshot of the commit to a temporary directory (used only for preprocessing)
    SNAP_DIR="$(mktemp -d -p "$BASE_TMP")"
    echo " - [$TARGET_HUMAN] Exporting ${SHA:0:7} → preprocessing → $OUT_DIR"
    if ! git --git-dir="$WORK_DIR/.git" archive --format=tar "$SHA" | tar -x -C "$SNAP_DIR"; then
      echo " Export failed"; rm -rf "$SNAP_DIR"; continue
    fi

    # —— Key: Run classify_repo_files.py on the snapshot —— #
    if ! python "$CLASSIFIER" \
      --repo_path "$SNAP_DIR" \
      --output_dir "$OUT_DIR" \
      --code-ext "$CODE_EXT" \
      --text-ext "$TEXT_EXT" \
      --max_words "$MAX_WORDS"
    then
      echo " Preprocessing failed (output cleaned)"
      rm -rf "$OUT_DIR"; rm -rf "$SNAP_DIR"; continue
    fi

    # Remove source snapshot to ensure OUT_ROOT contains only preprocessed data
    rm -rf "$SNAP_DIR"
  done

  # Clean up temporary bare repository
  rm -rf "$WORK_DIR"
done

echo -e "\nDone: Results are stored in $OUT_ROOT/<repo>/<YYYY-MM>/ (preprocessed data only)"