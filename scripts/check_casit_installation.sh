#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${CASIT_DATA_DIR:-$HOME/casit-data}"
YOLO_MODEL="${CASIT_YOLO_MODEL:-$DATA_DIR/models/yolo11n.pt}"
VLM_SERVER_URL="${CASIT_VLM_SERVER_URL:-http://127.0.0.1:8000}"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() {
  echo "✅ PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

warn() {
  echo "⚠️  WARN: $1"
  WARN_COUNT=$((WARN_COUNT + 1))
}

fail() {
  echo "❌ FAIL: $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

check_file() {
  local file="$1"
  local label="$2"

  if [[ -f "$file" ]]; then
    pass "$label"
  else
    fail "$label missing: $file"
  fi
}

check_dir() {
  local dir="$1"
  local label="$2"

  if [[ -d "$dir" ]]; then
    pass "$label"
  else
    fail "$label missing: $dir"
  fi
}

check_executable() {
  local file="$1"
  local label="$2"

  if [[ -x "$file" ]]; then
    pass "$label executable"
  elif [[ -f "$file" ]]; then
    warn "$label exists but not executable: $file"
  else
    fail "$label missing: $file"
  fi
}

echo "============================================================"
echo "CASIT / ÇAŞIT Installation Checker"
echo "============================================================"
echo "PROJECT_DIR     : $PROJECT_DIR"
echo "DATA_DIR        : $DATA_DIR"
echo "YOLO_MODEL      : $YOLO_MODEL"
echo "VLM_SERVER_URL  : $VLM_SERVER_URL"
echo "============================================================"

cd "$PROJECT_DIR" || {
  echo "Cannot enter project dir: $PROJECT_DIR"
  exit 1
}

echo ""
echo "---- 1. Repository files ----"
check_file "README.md" "README.md"
check_file "SCENARIO_3_SCOPE.md" "SCENARIO_3_SCOPE.md"
check_file "PROJECT_STATUS.md" "PROJECT_STATUS.md"
check_file ".gitignore" ".gitignore"
check_file ".env.example" ".env.example"

echo ""
echo "---- 2. Requirements ----"
check_file "requirements.txt" "requirements.txt"
check_file "requirements-yolo.txt" "requirements-yolo.txt"
check_file "requirements-vllm.txt" "requirements-vllm.txt"

echo ""
echo "---- 3. Documentation ----"
check_file "docs/setup.md" "docs/setup.md"
check_file "docs/architecture.md" "docs/architecture.md"
check_file "docs/evaluation.md" "docs/evaluation.md"
check_file "docs/competition_report.md" "docs/competition_report.md"
check_file "docs/custom_class_strategy.md" "docs/custom_class_strategy.md"

echo ""
echo "---- 4. Config files ----"
check_file "config/domain_policies.json" "domain_policies.json"
check_file "config/custom_class_strategy.json" "custom_class_strategy.json"
check_file "config/multi_video_test_manifest.json" "multi_video_test_manifest.json"

echo ""
echo "---- 5. Script files ----"
check_executable "scripts/run_casit_full_pipeline.sh" "Full pipeline"
check_executable "scripts/run_casit_multi_video_tests.sh" "Multi-video test runner"
check_executable "scripts/start_vllm_strong.sh" "vLLM starter"
check_file "scripts/check_vllm.sh" "check_vllm.sh"
check_file "scripts/diagnose_vllm_failure.sh" "diagnose_vllm_failure.sh"

echo ""
echo "---- 6. Python environments ----"
if [[ -x ".venv/bin/python" ]]; then
  pass ".venv Python available"
else
  fail ".venv Python missing"
fi

if [[ -x ".venv-vllm/bin/python" ]]; then
  pass ".venv-vllm Python available"
else
  warn ".venv-vllm Python missing or not executable"
fi

echo ""
echo "---- 7. Data and model paths ----"
check_dir "$DATA_DIR" "CASIT data directory"
check_dir "$DATA_DIR/datasets/raw_videos" "Raw video directory"
check_dir "$DATA_DIR/models" "Model directory"
check_file "$YOLO_MODEL" "YOLO model"

RAW_VIDEO_COUNT="$(find "$DATA_DIR/datasets/raw_videos" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.avi" -o -name "*.mov" -o -name "*.mkv" \) 2>/dev/null | wc -l || true)"
if [[ "$RAW_VIDEO_COUNT" -gt 0 ]]; then
  pass "Raw videos available: $RAW_VIDEO_COUNT"
else
  warn "No raw videos found in $DATA_DIR/datasets/raw_videos"
fi

echo ""
echo "---- 8. JSON validation ----"
if command -v python3 >/dev/null 2>&1; then
  python3 -m json.tool config/domain_policies.json >/tmp/casit_domain_policies_check.json \
    && pass "domain_policies.json valid JSON" \
    || fail "domain_policies.json invalid JSON"

  python3 -m json.tool config/custom_class_strategy.json >/tmp/casit_custom_class_strategy_check.json \
    && pass "custom_class_strategy.json valid JSON" \
    || fail "custom_class_strategy.json invalid JSON"

  python3 -m json.tool config/multi_video_test_manifest.json >/tmp/casit_multi_video_manifest_check.json \
    && pass "multi_video_test_manifest.json valid JSON" \
    || fail "multi_video_test_manifest.json invalid JSON"
else
  fail "python3 command not found"
fi

echo ""
echo "---- 9. Shell syntax checks ----"
bash -n scripts/run_casit_full_pipeline.sh \
  && pass "run_casit_full_pipeline.sh syntax OK" \
  || fail "run_casit_full_pipeline.sh syntax error"

bash -n scripts/run_casit_multi_video_tests.sh \
  && pass "run_casit_multi_video_tests.sh syntax OK" \
  || fail "run_casit_multi_video_tests.sh syntax error"

bash -n scripts/start_vllm_strong.sh \
  && pass "start_vllm_strong.sh syntax OK" \
  || fail "start_vllm_strong.sh syntax error"

echo ""
echo "---- 10. Python compile checks ----"
if [[ -x ".venv/bin/python" ]]; then
  .venv/bin/python -m py_compile \
    src/reporting/executive_jury_report_builder.py \
    src/reporting/json_schema_standardizer.py \
    src/evaluation/scenario_3_output_validator.py \
    src/evaluation/benchmark_kpi_reporter.py \
    src/policies/domain_policy_selector.py \
    && pass "core Python modules compile OK" \
    || fail "core Python module compile error"
else
  fail "Cannot compile Python modules because .venv is missing"
fi

echo ""
echo "---- 11. vLLM server check ----"
if command -v python3 >/dev/null 2>&1; then
  CASIT_VLM_SERVER_URL="$VLM_SERVER_URL" python3 - << 'PYVLLM'
import json
import os
import urllib.request

url = os.environ.get("CASIT_VLM_SERVER_URL", "http://127.0.0.1:8000").rstrip("/") + "/v1/models"

try:
    with urllib.request.urlopen(url, timeout=5) as r:
        data = json.loads(r.read().decode("utf-8"))
    models = [m.get("id") for m in data.get("data", [])]
    print("VLLM_SERVER_OK")
    print("models:", models)
except Exception as e:
    print("VLLM_SERVER_NOT_REACHABLE")
    print(type(e).__name__, str(e))
    raise SystemExit(2)
PYVLLM

  case "$?" in
    0) pass "vLLM server reachable" ;;
    *) warn "vLLM server not reachable. Start it with scripts/start_vllm_strong.sh" ;;
  esac
fi

echo ""
echo "============================================================"
echo "CASIT Installation Check Summary"
echo "============================================================"
echo "PASS : $PASS_COUNT"
echo "WARN : $WARN_COUNT"
echo "FAIL : $FAIL_COUNT"
echo "============================================================"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "INSTALLATION_CHECK_FAILED"
  exit 1
fi

echo "INSTALLATION_CHECK_OK"
exit 0
