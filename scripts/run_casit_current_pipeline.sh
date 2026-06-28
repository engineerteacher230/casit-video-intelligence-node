#!/usr/bin/env bash
set -e

PROJECT_DIR="$HOME/casit/projects/casit-video-intelligence-node"
DATA_DIR="$HOME/casit-data"
VIDEO_NAME="insan"

cd "$PROJECT_DIR"

echo "=========================================="
echo "CASIT / ÇAŞIT CURRENT PIPELINE"
echo "=========================================="
echo "Project dir : $PROJECT_DIR"
echo "Data dir    : $DATA_DIR"
echo "Video name  : $VIDEO_NAME"
echo "=========================================="

echo ""
echo "[1/6] Domain policy seçiliyor..."
python src/policies/domain_policy_selector.py \
  --scene-prior "$DATA_DIR/outputs/json/scene_prior.json" \
  --config config/domain_policies.json \
  --output-json "$DATA_DIR/outputs/json/focused_yolo_policy.json"

echo ""
echo "[2/6] Domain-aware YOLO çalışıyor..."
python src/vision/domain_aware_yolo_detector.py \
  --scene-prior "$DATA_DIR/outputs/json/scene_prior.json" \
  --detail-report "$DATA_DIR/outputs/json/detail_frames_report.json" \
  --model yolo11n.pt \
  --output-json "$DATA_DIR/outputs/json/domain_detection_report.json" \
  --annotated-dir "$DATA_DIR/outputs/annotated/$VIDEO_NAME/domain_aware_yolo_detail" \
  --conf 0.25 \
  --imgsz 640 \
  --device cuda

echo ""
echo "[3/6] Tracking çalışıyor..."
python src/vision/domain_aware_yolo_tracker.py \
  --domain-detection-report "$DATA_DIR/outputs/json/domain_detection_report.json" \
  --focused-policy "$DATA_DIR/outputs/json/focused_yolo_policy.json" \
  --output-json "$DATA_DIR/outputs/json/tracked_detection_report.json" \
  --annotated-dir "$DATA_DIR/outputs/annotated/$VIDEO_NAME/domain_aware_yolo_tracking" \
  --min-iou 0.20 \
  --max-missed 5 \
  --min-center-similarity 0.65

echo ""
echo "[4/6] Track quality refiner çalışıyor..."
python src/vision/track_quality_refiner.py \
  --tracked-report "$DATA_DIR/outputs/json/tracked_detection_report.json" \
  --output-json "$DATA_DIR/outputs/json/refined_tracking_report.json" \
  --small-object-event-gap 30

echo ""
echo "[5/6] Event evidence builder çalışıyor..."
python src/vision/event_evidence_builder.py \
  --scene-prior "$DATA_DIR/outputs/json/scene_prior.json" \
  --focused-policy "$DATA_DIR/outputs/json/focused_yolo_policy.json" \
  --refined-report "$DATA_DIR/outputs/json/refined_tracking_report.json" \
  --output-json "$DATA_DIR/outputs/json/event_evidence_report.json"

echo ""
echo "[6/6] Final Türkçe rapor üretiliyor..."
python src/reporting/final_video_report_builder.py \
  --event-evidence "$DATA_DIR/outputs/json/event_evidence_report.json" \
  --output-md "$DATA_DIR/outputs/reports/final_video_analysis_report.md"

echo ""
echo "=========================================="
echo "PIPELINE TAMAMLANDI"
echo "=========================================="
echo "Final rapor:"
echo "$DATA_DIR/outputs/reports/final_video_analysis_report.md"
echo ""
echo "Tracking görselleri:"
echo "$DATA_DIR/outputs/annotated/$VIDEO_NAME/domain_aware_yolo_tracking"
echo "=========================================="
