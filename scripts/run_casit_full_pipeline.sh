#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/casit/projects/casit-video-intelligence-node"
DATA_DIR="$HOME/casit-data"

VIDEO_PATH="${1:-$DATA_DIR/datasets/raw_videos/insan.mp4}"
VIDEO_PATH="$(realpath -m "$VIDEO_PATH")"

VIDEO_FILE="$(basename "$VIDEO_PATH")"
VIDEO_NAME="${VIDEO_FILE%.*}"
VIDEO_SAFE="$(printf '%s' "$VIDEO_NAME" | tr -c '[:alnum:]_-' '_')"

RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${VIDEO_SAFE}_${RUN_STAMP}"
RUN_DIR="$DATA_DIR/outputs/runs/$RUN_ID"

JSON_DIR="$RUN_DIR/json"
REPORT_DIR="$RUN_DIR/reports"
ANNOTATED_DIR="$RUN_DIR/annotated"

PY_YOLO="$PROJECT_DIR/.venv/bin/python"
PY_VLM="$PROJECT_DIR/.venv-vllm/bin/python"

if [[ ! -x "$PY_VLM" ]]; then
  PY_VLM="$PY_YOLO"
fi

SERVER_URL="${CASIT_VLM_SERVER_URL:-http://127.0.0.1:8000}"
MODEL="${CASIT_VLM_MODEL:-casit-vlm-strong}"

cd "$PROJECT_DIR"

mkdir -p "$JSON_DIR"
mkdir -p "$REPORT_DIR"
mkdir -p "$ANNOTATED_DIR"
ln -sfn "$RUN_DIR" "$DATA_DIR/outputs/runs/latest"

cat > "$RUN_DIR/run_info.txt" << INFO
CASIT / ÇAŞIT RUN INFO
Video path : $VIDEO_PATH
Video name : $VIDEO_NAME
Run ID     : $RUN_ID
Run dir    : $RUN_DIR
Project    : $PROJECT_DIR
Data dir   : $DATA_DIR
VLM URL    : $SERVER_URL
VLM model  : $MODEL
INFO

echo "=========================================="
echo "CASIT / ÇAŞIT FULL VIDEO PIPELINE v0.3"
echo "=========================================="
echo "Video path : $VIDEO_PATH"
echo "Video name : $VIDEO_NAME"
echo "Run ID     : $RUN_ID"
echo "Run dir    : $RUN_DIR"
echo "Project   : $PROJECT_DIR"
echo "Data dir  : $DATA_DIR"
echo "VLM URL   : $SERVER_URL"
echo "VLM model : $MODEL"
echo "=========================================="

if [[ ! -f "$VIDEO_PATH" ]]; then
  echo "ERROR: Video bulunamadı: $VIDEO_PATH"
  exit 1
fi

echo ""
echo "[0/14] VLM server kontrol ediliyor..."
"$PY_VLM" - << PY
import urllib.request
url = "$SERVER_URL/v1/models"
try:
    with urllib.request.urlopen(url, timeout=5) as r:
        print("VLM_SERVER_OK")
except Exception as e:
    raise SystemExit(f"ERROR: VLM server erişilemiyor: {url}\\nDetay: {e}")
PY

echo ""
echo "[1/14] Video metadata okunuyor..."
"$PY_YOLO" src/video_io/video_metadata_reader.py \
  --video "$VIDEO_PATH" \
  --output "$JSON_DIR/video_metadata_report.json"

echo ""
echo "[2/14] Coarse frame extraction çalışıyor..."
"$PY_YOLO" src/video_io/coarse_frame_extractor.py \
  --metadata "$JSON_DIR/video_metadata_report.json" \
  --output-frames "$DATA_DIR/datasets/frames" \
  --output-json "$JSON_DIR/coarse_frames_report.json" \
  --resize-width 960

echo ""
echo "[3/14] Event energy scanner çalışıyor..."
"$PY_YOLO" src/adaptive_search/event_energy_scanner.py \
  --frames-report "$JSON_DIR/coarse_frames_report.json" \
  --output-json "$JSON_DIR/event_energy_report.json" \
  --analysis-width 320 \
  --sensitivity 1.0 \
  --min-threshold 0.03

echo ""
echo "[4/14] Context window planner çalışıyor..."
"$PY_YOLO" src/adaptive_search/context_window_planner.py \
  --event-report "$JSON_DIR/event_energy_report.json" \
  --output-json "$JSON_DIR/context_window_plan.json" \
  --max-gap-seconds 0.5

echo ""
echo "[5/14] Detail window extractor çalışıyor..."
"$PY_YOLO" src/video_io/detail_window_extractor.py \
  --context-plan "$JSON_DIR/context_window_plan.json" \
  --output-frames "$DATA_DIR/datasets/frames" \
  --output-json "$JSON_DIR/detail_frames_report.json" \
  --resize-width 1280

echo ""
echo "[6/14] Scene scout extractor çalışıyor..."
"$PY_YOLO" src/scene_understanding/scene_scout_extractor.py \
  --video "$VIDEO_PATH" \
  --output-frames "$DATA_DIR/datasets/frames" \
  --output-json "$JSON_DIR/scene_scout_report.json" \
  --scout-fps 1.0 \
  --resize-width 768

echo ""
echo "[7/14] Qwen/VLM Scene Prior Agent çalışıyor..."
"$PY_VLM" src/scene_understanding/scene_prior_agent.py \
  --scene-scout-report "$JSON_DIR/scene_scout_report.json" \
  --output-json "$JSON_DIR/scene_prior.json" \
  --server-url "$SERVER_URL" \
  --model "$MODEL" \
  --max-frames 6

echo ""
echo "[8/14] Domain policy seçiliyor..."
"$PY_YOLO" src/policies/domain_policy_selector.py \
  --scene-prior "$JSON_DIR/scene_prior.json" \
  --config config/domain_policies.json \
  --output-json "$JSON_DIR/focused_yolo_policy.json"

echo ""
echo "[9/14] Domain-aware YOLO çalışıyor..."
"$PY_YOLO" src/vision/domain_aware_yolo_detector.py \
  --scene-prior "$JSON_DIR/scene_prior.json" \
  --detail-report "$JSON_DIR/detail_frames_report.json" \
  --model yolo11n.pt \
  --output-json "$JSON_DIR/domain_detection_report.json" \
  --focused-policy "$JSON_DIR/focused_yolo_policy.json" \
  --annotated-dir "$ANNOTATED_DIR/domain_aware_yolo_detail" \
  --conf 0.25 \
  --imgsz 640 \
  --device cuda

echo ""
echo "[10/14] Tracking çalışıyor..."
"$PY_YOLO" src/vision/domain_aware_yolo_tracker.py \
  --domain-detection-report "$JSON_DIR/domain_detection_report.json" \
  --focused-policy "$JSON_DIR/focused_yolo_policy.json" \
  --output-json "$JSON_DIR/tracked_detection_report.json" \
  --annotated-dir "$ANNOTATED_DIR/domain_aware_yolo_tracking" \
  --min-iou 0.20 \
  --max-missed 5 \
  --min-center-similarity 0.65

echo ""
echo "[11/14] Track quality refiner çalışıyor..."
"$PY_YOLO" src/vision/track_quality_refiner.py \
  --tracked-report "$JSON_DIR/tracked_detection_report.json" \
  --output-json "$JSON_DIR/refined_tracking_report.json" \
  --small-object-event-gap 30

echo ""
echo "[12/14] Event evidence builder çalışıyor..."
"$PY_YOLO" src/vision/event_evidence_builder.py \
  --scene-prior "$JSON_DIR/scene_prior.json" \
  --focused-policy "$JSON_DIR/focused_yolo_policy.json" \
  --refined-report "$JSON_DIR/refined_tracking_report.json" \
  --output-json "$JSON_DIR/event_evidence_report.json"

echo ""
echo "[13/14] Final Türkçe rapor üretiliyor..."
"$PY_YOLO" src/reporting/final_video_report_builder.py \
  --event-evidence "$JSON_DIR/event_evidence_report.json" \
  --output-md "$REPORT_DIR/final_${VIDEO_SAFE}_analysis_report.md"

echo ""
echo "[14/14] Semantik olay raporu üretiliyor..."
"$PY_YOLO" src/event_reasoning/semantic_event_builder.py \
  --scene-prior "$JSON_DIR/scene_prior.json" \
  --context-plan "$JSON_DIR/context_window_plan.json" \
  --event-energy "$JSON_DIR/event_energy_report.json" \
  --event-evidence "$JSON_DIR/event_evidence_report.json" \
  --output-json "$JSON_DIR/semantic_event_report.json" \
  --output-md "$REPORT_DIR/semantic_event_report.md"

echo ""
echo "=========================================="
echo "FULL PIPELINE TAMAMLANDI"
echo "=========================================="
echo "Run klasörü:"
echo "$RUN_DIR"
echo ""
echo "Final rapor:"
echo "$REPORT_DIR/final_${VIDEO_SAFE}_analysis_report.md"
echo ""
echo "Semantik olay raporu:"
echo "$REPORT_DIR/semantic_event_report.md"
echo ""
echo "Tracking görselleri:"
echo "$ANNOTATED_DIR/domain_aware_yolo_tracking"
echo ""
echo "Latest kısa yolu:"
echo "$DATA_DIR/outputs/runs/latest"
echo "=========================================="
