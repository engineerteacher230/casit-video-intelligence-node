#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Benchmark & KPI Reporter

Amaç:
CASIT pipeline çıktılarından ölçülebilir KPI ve demo/teslim hazırlık göstergeleri üretmek.

Not:
Bu modül ground-truth accuracy ölçmez. Çünkü etiketli doğruluk verisi olmadan
mAP, precision, recall gibi gerçek doğruluk metrikleri üretilemez.

Bu modül şunları ölçer:
- Pipeline çıktı doluluğu
- Scenario 3 kapsam uygunluğu
- Olay/risk/aksiyon üretim sayıları
- Validation ve quality readiness göstergeleri
- Jüri/demo hazırlık KPI skoru
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


def load_json(path, default=None):
    if default is None:
        default = {}
    if not path:
        return default

    p = Path(path).expanduser()
    if not p.exists():
        return default

    return json.loads(p.read_text(encoding="utf-8"))


def save_json(data, path):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_text(text, path):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def safe_get(data, path, default=None):
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur

def find_first_key(data, candidate_keys, default=None):
    """
    JSON içinde farklı modüllerden gelen değişken metadata adlarını
    recursive olarak arar.
    """
    if not isinstance(candidate_keys, (list, tuple, set)):
        candidate_keys = [candidate_keys]

    candidate_keys = set(candidate_keys)

    if isinstance(data, dict):
        for key, value in data.items():
            if key in candidate_keys and value is not None:
                return value

        for value in data.values():
            found = find_first_key(value, candidate_keys, default=None)
            if found is not None:
                return found

    elif isinstance(data, list):
        for item in data:
            found = find_first_key(item, candidate_keys, default=None)
            if found is not None:
                return found

    return default



def count_by_risk(events):
    out = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }

    for event in events or []:
        risk = event.get("risk_level") or event.get("final_risk_level")
        if risk in out:
            out[risk] += 1

    return out


def score_bool(condition, points):
    return points if condition else 0


def build_kpi_score(inputs):
    """
    100 puanlık internal readiness KPI.
    Bu skor doğruluk skoru değildir; teslim/demoya hazır çıktı üretim skorudur.
    """

    metadata = inputs["metadata"]
    detection = inputs["detection"]
    tracking = inputs["tracking"]
    semantic = inputs["semantic"]
    proximity = inputs["proximity"]
    event_vlm = inputs["event_vlm"]
    risk_action = inputs["risk_action"]
    standardized = inputs["standardized"]
    validation = inputs["validation"]
    quality = inputs["quality"]

    score_items = []

    def add(name, points, earned, detail):
        score_items.append({
            "name": name,
            "points": points,
            "earned": earned,
            "detail_tr": detail,
        })

    add(
        "video_metadata_available",
        8,
        score_bool(bool(metadata), 8),
        "Video metadata çıktısı mevcut olmalıdır."
    )

    add(
        "detection_output_available",
        10,
        score_bool(safe_get(detection, ["summary", "total_detections"], 0) > 0, 10),
        "Nesne tespiti en az bir detection üretmelidir."
    )

    add(
        "tracking_output_available",
        10,
        score_bool(safe_get(tracking, ["summary", "tracked_detection_count"], 0) > 0, 10),
        "Tracking katmanı en az bir takipli detection üretmelidir."
    )

    add(
        "semantic_events_available",
        12,
        score_bool(safe_get(semantic, ["summary", "semantic_event_count"], 0) > 0, 12),
        "Semantic event katmanı en az bir olay üretmelidir."
    )

    add(
        "proximity_risk_available",
        12,
        score_bool(safe_get(proximity, ["summary", "proximity_risk_event_count"], 0) > 0, 12),
        "Proximity risk katmanı risk event üretmelidir."
    )

    add(
        "event_vlm_reasoning_available",
        12,
        score_bool(safe_get(event_vlm, ["summary", "vlm_reasoned_event_count"], 0) > 0, 12),
        "Event VLM Reasoner en az bir olay yorumlamalıdır."
    )

    add(
        "risk_action_v2_available",
        12,
        score_bool(safe_get(risk_action, ["summary", "risk_action_event_count"], 0) > 0, 12),
        "Risk & Action v2 nihai olay kararı üretmelidir."
    )

    add(
        "standardized_output_available",
        12,
        score_bool(bool(standardized.get("events")), 12),
        "Standardized Scenario 3 output events listesi üretmelidir."
    )

    add(
        "scenario_3_validation_passed",
        8,
        score_bool(safe_get(validation, ["validation", "status"]) == "pass", 8),
        "Scenario 3 Output Validator pass dönmelidir."
    )

    add(
        "quality_review_ready",
        4,
        score_bool(
            safe_get(quality, ["quality_grade"]) in {"excellent", "good"}
            or safe_get(quality, ["quality_score"], 0) >= 80,
            4
        ),
        "Quality reviewer sonucu iyi veya mükemmel olmalıdır."
    )

    total = sum(item["points"] for item in score_items)
    earned = sum(item["earned"] for item in score_items)

    return {
        "score": round((earned / total) * 100, 2) if total else 0.0,
        "earned_points": earned,
        "total_points": total,
        "items": score_items,
        "note_tr": "Bu skor doğruluk skoru değildir; pipeline çıktı/doluluk/teslim hazırlığı KPI skorudur."
    }


def build_report(inputs):
    metadata = inputs["metadata"]
    detection = inputs["detection"]
    tracking = inputs["tracking"]
    refined_tracking = inputs["refined_tracking"]
    semantic = inputs["semantic"]
    proximity = inputs["proximity"]
    event_vlm = inputs["event_vlm"]
    risk_action = inputs["risk_action"]
    standardized = inputs["standardized"]
    validation = inputs["validation"]
    quality = inputs["quality"]

    std_events = standardized.get("events", [])
    risk_counts = count_by_risk(std_events)

    video_metrics = {
        "duration_seconds": (
            safe_get(metadata, ["video", "duration_seconds"])
            or safe_get(metadata, ["metadata", "duration_seconds"])
            or safe_get(metadata, ["summary", "duration_seconds"])
            or find_first_key(metadata, ["duration_seconds", "duration_sec", "duration"])
        ),
        "fps": (
            safe_get(metadata, ["video", "fps"])
            or safe_get(metadata, ["metadata", "fps"])
            or safe_get(metadata, ["summary", "fps"])
            or find_first_key(metadata, ["fps", "frame_rate"])
        ),
        "frame_count": (
            safe_get(metadata, ["video", "frame_count"])
            or safe_get(metadata, ["metadata", "frame_count"])
            or safe_get(metadata, ["summary", "frame_count"])
            or find_first_key(metadata, ["frame_count", "total_frames", "frames"])
        ),
        "width": (
            safe_get(metadata, ["video", "width"])
            or safe_get(metadata, ["metadata", "width"])
            or find_first_key(metadata, ["width", "frame_width"])
        ),
        "height": (
            safe_get(metadata, ["video", "height"])
            or safe_get(metadata, ["metadata", "height"])
            or find_first_key(metadata, ["height", "frame_height"])
        ),
    }

    perception_metrics = {
        "detection_total_frames": safe_get(detection, ["summary", "total_frames"], 0),
        "frames_with_detections": safe_get(detection, ["summary", "frames_with_detections"], 0),
        "total_detections": safe_get(detection, ["summary", "total_detections"], 0),
        "class_counts": safe_get(detection, ["summary", "class_counts"], {}),
        "tracked_detection_count": safe_get(tracking, ["summary", "tracked_detection_count"], 0),
        "total_unique_tracks": safe_get(tracking, ["summary", "total_unique_tracks"], 0),
        "unique_track_counts": safe_get(tracking, ["summary", "unique_track_counts"], {}),
        "refined_class_summary": refined_tracking.get("refined_class_summary", {}),
    }

    reasoning_metrics = {
        "semantic_event_count": safe_get(semantic, ["summary", "semantic_event_count"], 0),
        "motion_candidate_count": safe_get(semantic, ["summary", "motion_candidate_count"], 0),
        "proximity_risk_event_count": safe_get(proximity, ["summary", "proximity_risk_event_count"], 0),
        "proximity_critical_count": safe_get(proximity, ["summary", "critical_risk_count"], 0),
        "proximity_high_or_above_count": safe_get(proximity, ["summary", "high_or_above_risk_count"], 0),
        "vlm_reasoned_event_count": safe_get(event_vlm, ["summary", "vlm_reasoned_event_count"], 0),
        "vlm_parse_error_count": safe_get(event_vlm, ["summary", "parse_error_count"], 0),
        "risk_action_event_count": safe_get(risk_action, ["summary", "risk_action_event_count"], 0),
    }

    scenario_3_metrics = {
        "standardized_event_count": len(std_events),
        "overall_risk": standardized.get("overall_risk"),
        "risk_counts": risk_counts,
        "submission_ready": safe_get(validation, ["validation", "is_submission_ready"]),
        "validation_status": safe_get(validation, ["validation", "status"]),
        "validation_failed_count": safe_get(validation, ["validation", "failed_count"]),
        "quality_score": quality.get("quality_score"),
        "quality_grade": quality.get("quality_grade"),
        "source_alignment": standardized.get("source_alignment", {}),
    }

    kpi_score = build_kpi_score(inputs)

    return {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "benchmark_kpi_reporter",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "benchmark_type": "internal_pipeline_kpi",
        "important_note_tr": (
            "Bu rapor etiketli ground-truth doğruluk benchmark'ı değildir. "
            "mAP, precision, recall gibi metrikler için ayrıca elle etiketlenmiş test seti gerekir."
        ),
        "video_metrics": video_metrics,
        "perception_metrics": perception_metrics,
        "reasoning_metrics": reasoning_metrics,
        "scenario_3_metrics": scenario_3_metrics,
        "internal_readiness_kpi": kpi_score,
        "recommendations_tr": build_recommendations(kpi_score, scenario_3_metrics, reasoning_metrics),
    }


def build_recommendations(kpi_score, scenario_3_metrics, reasoning_metrics):
    recs = []

    score = kpi_score.get("score", 0)

    if score >= 90:
        recs.append("Pipeline çıktı/doluluk açısından demo ve rapor aşaması için güçlü durumdadır.")
    elif score >= 75:
        recs.append("Pipeline genel olarak çalışır durumdadır; demo öncesi eksik KPI maddeleri iyileştirilmelidir.")
    else:
        recs.append("Pipeline KPI skoru düşük; eksik modül çıktıları tamamlanmadan demo yapılmamalıdır.")

    if scenario_3_metrics.get("validation_status") == "pass":
        recs.append("Standardized Scenario 3 output validasyondan geçmiştir; ana teslim JSON'u olarak kullanılabilir.")
    else:
        recs.append("Standardized Scenario 3 output validasyon hataları giderilmelidir.")

    if reasoning_metrics.get("vlm_parse_error_count", 0) > 0:
        recs.append("VLM parse hataları azaltılmalıdır; JSON format kararlılığı gözden geçirilmelidir.")

    if scenario_3_metrics.get("standardized_event_count", 0) == 0:
        recs.append("Olay listesi boş; Scenario 3 kapsamı için semantic event üretimi iyileştirilmelidir.")

    recs.append("Gerçek doğruluk ölçümü için Aşama 64'te çok videolu test seti ve manuel etiketli ground-truth hazırlanmalıdır.")

    return recs


def build_markdown(report):
    lines = []

    lines.append("# CASIT / ÇAŞIT — Benchmark & KPI Report")
    lines.append("")
    lines.append(report.get("important_note_tr", ""))
    lines.append("")

    kpi = report.get("internal_readiness_kpi", {})
    scenario = report.get("scenario_3_metrics", {})
    video = report.get("video_metrics", {})
    perception = report.get("perception_metrics", {})
    reasoning = report.get("reasoning_metrics", {})

    lines.append("## Genel KPI")
    lines.append("")
    lines.append(f"- Internal readiness KPI: `{kpi.get('score')}` / 100")
    lines.append(f"- Puan: `{kpi.get('earned_points')}` / `{kpi.get('total_points')}`")
    lines.append(f"- Submission ready: `{scenario.get('submission_ready')}`")
    lines.append(f"- Validation status: `{scenario.get('validation_status')}`")
    lines.append(f"- Overall risk: `{scenario.get('overall_risk')}`")
    lines.append("")

    lines.append("## Video Metrikleri")
    lines.append("")
    for key, value in video.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")

    lines.append("## Algılama / Tracking Metrikleri")
    lines.append("")
    lines.append(f"- Total detections: `{perception.get('total_detections')}`")
    lines.append(f"- Frames with detections: `{perception.get('frames_with_detections')}`")
    lines.append(f"- Tracked detections: `{perception.get('tracked_detection_count')}`")
    lines.append(f"- Total unique tracks: `{perception.get('total_unique_tracks')}`")
    lines.append(f"- Class counts: `{perception.get('class_counts')}`")
    lines.append(f"- Unique track counts: `{perception.get('unique_track_counts')}`")
    lines.append("")

    lines.append("## Reasoning / Risk Metrikleri")
    lines.append("")
    for key, value in reasoning.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")

    lines.append("## Scenario 3 Metrikleri")
    lines.append("")
    lines.append(f"- Standardized event count: `{scenario.get('standardized_event_count')}`")
    lines.append(f"- Risk counts: `{scenario.get('risk_counts')}`")
    lines.append(f"- Quality score: `{scenario.get('quality_score')}`")
    lines.append(f"- Quality grade: `{scenario.get('quality_grade')}`")
    lines.append(f"- Source alignment: `{scenario.get('source_alignment')}`")
    lines.append("")

    lines.append("## KPI Kalemleri")
    lines.append("")
    for item in kpi.get("items", []):
        lines.append(
            f"- `{item.get('name')}`: `{item.get('earned')}/{item.get('points')}` — {item.get('detail_tr')}"
        )
    lines.append("")

    lines.append("## Öneriler")
    lines.append("")
    for rec in report.get("recommendations_tr", []):
        lines.append(f"- {rec}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--metadata", required=False)
    parser.add_argument("--detection", required=False)
    parser.add_argument("--tracking", required=False)
    parser.add_argument("--refined-tracking", required=False)
    parser.add_argument("--semantic-event", required=False)
    parser.add_argument("--proximity-risk", required=False)
    parser.add_argument("--event-vlm", required=False)
    parser.add_argument("--risk-action-v2", required=False)
    parser.add_argument("--standardized-output", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--quality-review", required=False)

    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)

    args = parser.parse_args()

    inputs = {
        "metadata": load_json(args.metadata),
        "detection": load_json(args.detection),
        "tracking": load_json(args.tracking),
        "refined_tracking": load_json(args.refined_tracking),
        "semantic": load_json(args.semantic_event),
        "proximity": load_json(args.proximity_risk),
        "event_vlm": load_json(args.event_vlm),
        "risk_action": load_json(args.risk_action_v2),
        "standardized": load_json(args.standardized_output),
        "validation": load_json(args.validation),
        "quality": load_json(args.quality_review),
    }

    report = build_report(inputs)

    save_json(report, args.output_json)
    save_text(build_markdown(report), args.output_md)

    kpi = report.get("internal_readiness_kpi", {})
    scenario = report.get("scenario_3_metrics", {})

    print("CASIT / ÇAŞIT Benchmark & KPI Reporter")
    print("--------------------------------------")
    print("Internal KPI      :", kpi.get("score"))
    print("Submission ready  :", scenario.get("submission_ready"))
    print("Validation status :", scenario.get("validation_status"))
    print("Overall risk      :", scenario.get("overall_risk"))
    print("Events            :", scenario.get("standardized_event_count"))
    print("Output JSON       :", args.output_json)
    print("Output MD         :", args.output_md)
    print("--------------------------------------")


if __name__ == "__main__":
    main()
