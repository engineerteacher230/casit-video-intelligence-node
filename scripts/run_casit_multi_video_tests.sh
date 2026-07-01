#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

DATA_DIR="${CASIT_DATA_DIR:-$HOME/casit-data}"
MANIFEST_PATH="config/multi_video_test_manifest.json"
DRY_RUN=0
CASE_FILTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --manifest)
      MANIFEST_PATH="$2"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="$2"
      shift 2
      ;;
    --case)
      CASE_FILTER="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 2
      ;;
  esac
done

BATCH_ID="${CASIT_BATCH_ID:-multi_video_$(date +%Y%m%d_%H%M%S)}"
BATCH_DIR="$DATA_DIR/outputs/multi_video_tests/$BATCH_ID"
LOG_DIR="$BATCH_DIR/logs"
RESULTS_JSONL="$BATCH_DIR/case_results.jsonl"

mkdir -p "$LOG_DIR"
: > "$RESULTS_JSONL"

echo "CASIT / ÇAŞIT Multi-video Test Runner"
echo "-------------------------------------"
echo "Manifest : $MANIFEST_PATH"
echo "Data dir : $DATA_DIR"
echo "Batch id : $BATCH_ID"
echo "Batch dir: $BATCH_DIR"
echo "Dry run  : $DRY_RUN"
echo "Case     : ${CASE_FILTER:-ALL}"
echo "-------------------------------------"

mapfile -t CASE_LINES < <(python3 - "$MANIFEST_PATH" "$CASE_FILTER" << 'EOF'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
case_filter = sys.argv[2]

data = json.loads(manifest_path.read_text(encoding="utf-8"))

for case in data.get("test_cases", []):
    if case_filter and case.get("case_id") != case_filter and case.get("file_name") != case_filter:
        continue
    print(f"{case.get('case_id')}\t{case.get('file_name')}\t{case.get('relative_path')}")
EOF
)

if [[ "${#CASE_LINES[@]}" -eq 0 ]]; then
  echo "No test cases found."
  exit 1
fi

for line in "${CASE_LINES[@]}"; do
  IFS=$'\t' read -r CASE_ID FILE_NAME REL_PATH <<< "$line"

  VIDEO_PATH="$DATA_DIR/$REL_PATH"
  LOG_PATH="$LOG_DIR/${CASE_ID}.log"

  echo ""
  echo "======================================"
  echo "CASE: $CASE_ID"
  echo "FILE: $FILE_NAME"
  echo "PATH: $VIDEO_PATH"
  echo "======================================"

  START_TS="$(date +%s)"

  if [[ ! -f "$VIDEO_PATH" ]]; then
    STATUS="failed"
    EXIT_CODE=1
    ERROR_MSG="Video file not found: $VIDEO_PATH"
    RUN_DIR=""

    echo "$ERROR_MSG"

  elif [[ "$DRY_RUN" -eq 1 ]]; then
    STATUS="dry_run"
    EXIT_CODE=0
    ERROR_MSG=""
    RUN_DIR=""

    echo "DRY-RUN: pipeline çalıştırılmadı."

  else
    set +e
    bash scripts/run_casit_full_pipeline.sh "$VIDEO_PATH" 2>&1 | tee "$LOG_PATH"
    EXIT_CODE="${PIPESTATUS[0]}"
    set -e

    if [[ "$EXIT_CODE" -eq 0 ]]; then
      STATUS="success"
      ERROR_MSG=""
      RUN_DIR="$(readlink -f "$DATA_DIR/outputs/runs/latest" || true)"
    else
      STATUS="failed"
      ERROR_MSG="Pipeline failed with exit code $EXIT_CODE"
      RUN_DIR="$(readlink -f "$DATA_DIR/outputs/runs/latest" || true)"
    fi
  fi

  END_TS="$(date +%s)"
  DURATION="$((END_TS - START_TS))"

  CASE_ID="$CASE_ID" \
  FILE_NAME="$FILE_NAME" \
  VIDEO_PATH="$VIDEO_PATH" \
  STATUS="$STATUS" \
  EXIT_CODE="$EXIT_CODE" \
  ERROR_MSG="$ERROR_MSG" \
  RUN_DIR="$RUN_DIR" \
  LOG_PATH="$LOG_PATH" \
  DURATION="$DURATION" \
  RESULTS_JSONL="$RESULTS_JSONL" \
  python3 - << 'EOF'
import json
import os
from pathlib import Path

row = {
    "case_id": os.environ["CASE_ID"],
    "file_name": os.environ["FILE_NAME"],
    "video_path": os.environ["VIDEO_PATH"],
    "status": os.environ["STATUS"],
    "exit_code": int(os.environ["EXIT_CODE"]),
    "error": os.environ["ERROR_MSG"] or None,
    "run_dir": os.environ["RUN_DIR"] or None,
    "log_path": os.environ["LOG_PATH"],
    "duration_seconds": int(os.environ["DURATION"]),
}

p = Path(os.environ["RESULTS_JSONL"])
with p.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
EOF

done

python3 src/evaluation/multi_video_test_aggregator.py \
  --manifest "$MANIFEST_PATH" \
  --case-results "$RESULTS_JSONL" \
  --output-json "$BATCH_DIR/multi_video_test_report.json" \
  --output-md "$BATCH_DIR/multi_video_test_report.md"

echo ""
echo "Multi-video test batch tamamlandı."
echo "Batch dir:"
echo "$BATCH_DIR"
echo ""
echo "Case results:"
echo "$RESULTS_JSONL"
echo ""
echo "Aggregate JSON:"
echo "$BATCH_DIR/multi_video_test_report.json"
echo ""
echo "Aggregate report:"
echo "$BATCH_DIR/multi_video_test_report.md"
