#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${1:-/home/mpsametozcan/casit-data/outputs/runs/cccc_20260701_213658}"
TAG_NAME="${CASIT_RELEASE_TAG:-v0.8.0-scenario3}"
PACKAGE_ROOT="${CASIT_SUBMISSION_PACKAGE_DIR:-$HOME/casit-data/outputs/submission_packages}"

RUN_DIR="$(readlink -f "$RUN_DIR")"
RUN_NAME="$(basename "$RUN_DIR")"
COMMIT_HASH="$(git -C "$PROJECT_DIR" rev-parse --short HEAD)"
PACKAGE_NAME="casit_${TAG_NAME}_${COMMIT_HASH}_${RUN_NAME}"
PACKAGE_DIR="$PACKAGE_ROOT/$PACKAGE_NAME"

echo "============================================================"
echo "CASIT / ÇAŞIT Final Submission Package Builder"
echo "============================================================"
echo "PROJECT_DIR : $PROJECT_DIR"
echo "RUN_DIR     : $RUN_DIR"
echo "TAG_NAME    : $TAG_NAME"
echo "COMMIT_HASH : $COMMIT_HASH"
echo "PACKAGE_DIR : $PACKAGE_DIR"
echo "============================================================"

required_outputs=(
  "json/standardized_scenario_3_output.json"
  "json/scenario_3_output_validation.json"
  "json/benchmark_kpi_report.json"
  "json/executive_jury_report.json"
  "reports/standardized_scenario_3_output.md"
  "reports/scenario_3_output_validation.md"
  "reports/benchmark_kpi_report.md"
  "reports/executive_jury_report.md"
)

missing=0
for f in "${required_outputs[@]}"; do
  if [[ ! -f "$RUN_DIR/$f" ]]; then
    echo "MISSING: $RUN_DIR/$f"
    missing=$((missing + 1))
  fi
done

if [[ "$missing" -gt 0 ]]; then
  echo "PACKAGE_BUILD_FAILED: missing required run outputs"
  exit 1
fi

rm -rf "$PACKAGE_DIR"
mkdir -p \
  "$PACKAGE_DIR/repo_docs" \
  "$PACKAGE_DIR/config" \
  "$PACKAGE_DIR/scripts" \
  "$PACKAGE_DIR/run_outputs/json" \
  "$PACKAGE_DIR/run_outputs/reports"

echo ""
echo "---- Copy repo documentation ----"
cp "$PROJECT_DIR/README.md" "$PACKAGE_DIR/repo_docs/"
cp "$PROJECT_DIR/SCENARIO_3_SCOPE.md" "$PACKAGE_DIR/repo_docs/"
cp "$PROJECT_DIR/PROJECT_STATUS.md" "$PACKAGE_DIR/repo_docs/"
cp "$PROJECT_DIR/docs/setup.md" "$PACKAGE_DIR/repo_docs/"
cp "$PROJECT_DIR/docs/architecture.md" "$PACKAGE_DIR/repo_docs/"
cp "$PROJECT_DIR/docs/evaluation.md" "$PACKAGE_DIR/repo_docs/"
cp "$PROJECT_DIR/docs/competition_report.md" "$PACKAGE_DIR/repo_docs/"
cp "$PROJECT_DIR/docs/custom_class_strategy.md" "$PACKAGE_DIR/repo_docs/"

echo ""
echo "---- Copy config files ----"
cp "$PROJECT_DIR/config/domain_policies.json" "$PACKAGE_DIR/config/"
cp "$PROJECT_DIR/config/custom_class_strategy.json" "$PACKAGE_DIR/config/"
cp "$PROJECT_DIR/config/multi_video_test_manifest.json" "$PACKAGE_DIR/config/"

echo ""
echo "---- Copy scripts ----"
cp "$PROJECT_DIR/scripts/check_casit_installation.sh" "$PACKAGE_DIR/scripts/"
cp "$PROJECT_DIR/scripts/run_casit_full_pipeline.sh" "$PACKAGE_DIR/scripts/"
cp "$PROJECT_DIR/scripts/run_casit_multi_video_tests.sh" "$PACKAGE_DIR/scripts/"
cp "$PROJECT_DIR/scripts/start_vllm_strong.sh" "$PACKAGE_DIR/scripts/"

echo ""
echo "---- Copy required outputs ----"
for f in "${required_outputs[@]}"; do
  mkdir -p "$PACKAGE_DIR/run_outputs/$(dirname "$f")"
  cp "$RUN_DIR/$f" "$PACKAGE_DIR/run_outputs/$f"
done

echo ""
echo "---- Write package manifest ----"
cat > "$PACKAGE_DIR/SUBMISSION_MANIFEST.md" << EOF
# CASIT / ÇAŞIT Final Submission Package

## Release

- Release tag: \`$TAG_NAME\`
- Commit hash: \`$COMMIT_HASH\`
- Source run: \`$RUN_NAME\`

## Included

### Repo Documentation

- \`repo_docs/README.md\`
- \`repo_docs/SCENARIO_3_SCOPE.md\`
- \`repo_docs/PROJECT_STATUS.md\`
- \`repo_docs/setup.md\`
- \`repo_docs/architecture.md\`
- \`repo_docs/evaluation.md\`
- \`repo_docs/competition_report.md\`
- \`repo_docs/custom_class_strategy.md\`

### Config

- \`config/domain_policies.json\`
- \`config/custom_class_strategy.json\`
- \`config/multi_video_test_manifest.json\`

### Scripts

- \`scripts/check_casit_installation.sh\`
- \`scripts/run_casit_full_pipeline.sh\`
- \`scripts/run_casit_multi_video_tests.sh\`
- \`scripts/start_vllm_strong.sh\`

### Run Outputs

- \`run_outputs/json/standardized_scenario_3_output.json\`
- \`run_outputs/json/scenario_3_output_validation.json\`
- \`run_outputs/json/benchmark_kpi_report.json\`
- \`run_outputs/json/executive_jury_report.json\`
- \`run_outputs/reports/standardized_scenario_3_output.md\`
- \`run_outputs/reports/scenario_3_output_validation.md\`
- \`run_outputs/reports/benchmark_kpi_report.md\`
- \`run_outputs/reports/executive_jury_report.md\`

## Not Included

- Raw videos
- Model weights
- Python virtual environments
- Extracted frames
- Full run cache
- Personal/local environment files
EOF

echo ""
echo "---- Write machine-readable manifest ----"
cat > "$PACKAGE_DIR/submission_manifest.json" << EOF
{
  "project": "CASIT / ÇAŞIT",
  "release_tag": "$TAG_NAME",
  "commit_hash": "$COMMIT_HASH",
  "source_run_name": "$RUN_NAME",
  "main_submission_json": "run_outputs/json/standardized_scenario_3_output.json",
  "main_jury_report": "run_outputs/reports/executive_jury_report.md",
  "benchmark_report": "run_outputs/reports/benchmark_kpi_report.md",
  "validation_report": "run_outputs/reports/scenario_3_output_validation.md",
  "excluded": [
    "raw videos",
    "model weights",
    "virtual environments",
    "extracted frames",
    "full run cache",
    "personal environment files"
  ]
}
EOF

echo ""
echo "---- Package tree ----"
find "$PACKAGE_DIR" -maxdepth 3 -type f -printf "%P\t%k KB\n" | sort

echo ""
echo "PACKAGE_BUILD_OK"
echo "$PACKAGE_DIR"
