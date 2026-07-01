#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Executive Jury Report Builder

Amaç:
Pipeline'ın parçalı JSON çıktılarını jüri/demo için tek, okunabilir,
karar-destek odaklı bir executive rapora dönüştürmek.

Bu modül ground-truth doğruluk raporu üretmez.
mAP / precision / recall için manuel etiketli test seti gerekir.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


RISK_ORDER = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def load_json(path, default=None):
    if default is None:
        default = {}
    p = Path(path).expanduser()
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


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


def find_first_key(data, key_names, default=None):
    """Nested JSON içinde verilen key isimlerinden ilk bulunan değeri döndürür."""
    if isinstance(key_names, str):
        key_names = [key_names]

    if isinstance(data, dict):
        for key in key_names:
            if key in data and data[key] not in [None, "", [], {}]:
                return data[key]

        for value in data.values():
            found = find_first_key(value, key_names, default=None)
            if found not in [None, "", [], {}]:
                return found

    elif isinstance(data, list):
        for item in data:
            found = find_first_key(item, key_names, default=None)
            if found not in [None, "", [], {}]:
                return found

    return default


def find_first_numeric_key(data, key_names, default=None):
    """Nested JSON içinde verilen key isimlerinden ilk sayısal değeri döndürür."""
    if isinstance(key_names, str):
        key_names = [key_names]

    if isinstance(data, dict):
        for key in key_names:
            value = data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value

        for value in data.values():
            found = find_first_numeric_key(value, key_names, default=None)
            if isinstance(found, (int, float)) and not isinstance(found, bool):
                return found

    elif isinstance(data, list):
        for item in data:
            found = find_first_numeric_key(item, key_names, default=None)
            if isinstance(found, (int, float)) and not isinstance(found, bool):
                return found

    return default


def count_if_list(value, default=None):
    if isinstance(value, list):
        return len(value)
    return default


def sum_list_lengths_by_key(data, target_key):
    """Nested JSON içinde target_key adlı tüm listelerin uzunluklarını toplar."""
    total = 0

    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key and isinstance(value, list):
                total += len(value)
            else:
                total += sum_list_lengths_by_key(value, target_key)

    elif isinstance(data, list):
        for item in data:
            total += sum_list_lengths_by_key(item, target_key)

    return total


def infer_video_name(run_dir, metadata):
    candidates = [
        find_first_key(metadata, ["video_file", "file_name", "video_name"]),
        Path(str(find_first_key(metadata, ["video_path", "path"], ""))).name,
    ]

    for c in candidates:
        if c not in [None, "", ".", "unknown_video"]:
            return c

    run_name = Path(run_dir).name
    # örn: cccc_20260701_213658 -> cccc.mp4 yerine güvenli kısa ad
    parts = run_name.split("_")
    if len(parts) >= 3:
        return parts[0]

    return run_name or "unknown_video"


def first_value(*values, default=None):
    for value in values:
        if value not in [None, "", [], {}]:
            return value
    return default


def normalize_risk(value):
    if not isinstance(value, str):
        return None
    value = value.lower().strip()
    return value if value in RISK_ORDER else None


def risk_label_tr(risk):
    return {
        "none": "Yok",
        "low": "Düşük",
        "medium": "Orta",
        "high": "Yüksek",
        "critical": "Kritik",
    }.get(risk, "Belirsiz")


def action_posture_tr(risk):
    if risk == "critical":
        return "Operatör acil öncelikli inceleme yapmalı; saha sorumlusu ve güvenlik birimiyle hızlı doğrulama önerilir."
    if risk == "high":
        return "Operatör olayı öncelikli inceleme kuyruğuna almalı; kişi/araç/alan yakınlaşmaları doğrulanmalıdır."
    if risk == "medium":
        return "Operatör olayı izlemeli; bağlamsal riskler ve hareketlilik gözden geçirilmelidir."
    if risk == "low":
        return "Operatör düşük öncelikli izleme yapabilir; belirgin risk kanıtı sınırlıdır."
    return "Risk seviyesi belirsiz; operatör temel görsel doğrulama yapmalıdır."


def extract_source_paths(run_dir):
    json_dir = run_dir / "json"
    report_dir = run_dir / "reports"

    expected_json = [
        "video_metadata_report.json",
        "scene_prior.json",
        "focused_yolo_policy.json",
        "domain_detection_report.json",
        "tracked_detection_report.json",
        "refined_tracking_report.json",
        "semantic_event_report.json",
        "relation_dynamics_report.json",
        "proximity_risk_report.json",
        "event_vlm_reasoning_report.json",
        "risk_action_report_v2.json",
        "standardized_scenario_3_output.json",
        "scenario_3_output_validation.json",
        "scenario_3_quality_review.json",
        "benchmark_kpi_report.json",
    ]

    return {
        "json_dir": str(json_dir),
        "report_dir": str(report_dir),
        "json_files": {
            name: str(json_dir / name)
            for name in expected_json
            if (json_dir / name).exists()
        },
        "missing_json_files": [
            name for name in expected_json
            if not (json_dir / name).exists()
        ],
    }


def build_executive_report(run_dir):
    run_dir = Path(run_dir).expanduser().resolve()
    json_dir = run_dir / "json"

    metadata = load_json(json_dir / "video_metadata_report.json")
    scene_prior_raw = load_json(json_dir / "scene_prior.json")
    focused_policy = load_json(json_dir / "focused_yolo_policy.json")
    detection = load_json(json_dir / "domain_detection_report.json")
    tracking = load_json(json_dir / "tracked_detection_report.json")
    refined = load_json(json_dir / "refined_tracking_report.json")
    semantic = load_json(json_dir / "semantic_event_report.json")
    relation = load_json(json_dir / "relation_dynamics_report.json")
    proximity = load_json(json_dir / "proximity_risk_report.json")
    event_vlm = load_json(json_dir / "event_vlm_reasoning_report.json")
    risk_action = load_json(json_dir / "risk_action_report_v2.json")
    standardized = load_json(json_dir / "standardized_scenario_3_output.json")
    validation = load_json(json_dir / "scenario_3_output_validation.json")
    quality = load_json(json_dir / "scenario_3_quality_review.json")
    benchmark = load_json(json_dir / "benchmark_kpi_report.json")

    scene_prior = scene_prior_raw.get("scene_prior", scene_prior_raw)

    events = standardized.get("events", [])
    if not isinstance(events, list):
        events = []

    risk_counts = first_value(
        safe_get(benchmark, ["scenario_3_metrics", "risk_counts"]),
        standardized.get("risk_counts"),
        default={}
    )

    overall_risk = normalize_risk(first_value(
        standardized.get("overall_risk"),
        safe_get(risk_action, ["summary", "overall_risk_v2"]),
        risk_action.get("overall_risk_v2"),
        safe_get(benchmark, ["scenario_3_metrics", "overall_risk"]),
        benchmark.get("overall_risk"),
        default=None
    ))

    if overall_risk is None:
        event_risks = [
            normalize_risk(first_value(e.get("risk"), e.get("risk_level")))
            for e in events
            if isinstance(e, dict)
        ]
        event_risks = [r for r in event_risks if r]
        overall_risk = max(event_risks, key=lambda r: RISK_ORDER[r]) if event_risks else "unknown"

    video_name = infer_video_name(run_dir, metadata)

    executive_summary = {
        "video_name": video_name,
        "run_dir": str(run_dir),
        "scene_type": first_value(scene_prior.get("scene_type"), standardized.get("scene_type"), default="unknown"),
        "domain": first_value(scene_prior.get("domain"), standardized.get("domain"), default="unknown"),
        "selected_policy": first_value(
            safe_get(focused_policy, ["selected_policy", "name"]),
            focused_policy.get("policy_name"),
            standardized.get("selected_policy"),
            default="unknown"
        ),
        "overall_risk": overall_risk,
        "overall_risk_tr": risk_label_tr(overall_risk),
        "event_count": len(events),
        "critical_event_count": risk_counts.get("critical", 0) if isinstance(risk_counts, dict) else 0,
        "high_event_count": risk_counts.get("high", 0) if isinstance(risk_counts, dict) else 0,
        "submission_ready": first_value(
            safe_get(validation, ["validation", "is_submission_ready"]),
            validation.get("submission_ready"),
            safe_get(benchmark, ["summary", "submission_ready"]),
            benchmark.get("submission_ready"),
            default=None
        ),
        "validation_status": first_value(
            safe_get(validation, ["validation", "status"]),
            validation.get("validation_status"),
            benchmark.get("validation_status"),
            default=None
        ),
        "internal_kpi": first_value(
            safe_get(benchmark, ["internal_readiness_kpi", "score"]),
            safe_get(benchmark, ["summary", "internal_kpi"]),
            benchmark.get("internal_kpi"),
            default=None
        ),
        "quality_score": first_value(
            quality.get("quality_score"),
            safe_get(benchmark, ["scenario_3_metrics", "quality_score"]),
            default=None
        ),
        "quality_grade": first_value(
            quality.get("quality_grade"),
            safe_get(benchmark, ["scenario_3_metrics", "quality_grade"]),
            default=None
        ),
    }

    video_metrics = {
        "duration_seconds": first_value(
            metadata.get("duration_seconds"),
            safe_get(benchmark, ["video_metrics", "duration_seconds"]),
            default=None
        ),
        "fps": first_value(
            metadata.get("fps"),
            metadata.get("source_fps"),
            safe_get(benchmark, ["video_metrics", "fps"]),
            default=None
        ),
        "frame_count": first_value(
            metadata.get("frame_count"),
            metadata.get("total_frames"),
            safe_get(benchmark, ["video_metrics", "frame_count"]),
            default=None
        ),
        "width": first_value(
            metadata.get("width"),
            safe_get(benchmark, ["video_metrics", "width"]),
            default=None
        ),
        "height": first_value(
            metadata.get("height"),
            safe_get(benchmark, ["video_metrics", "height"]),
            default=None
        ),
    }

    detection_tracking = {
        "total_detections": first_value(
            find_first_key(detection, "total_detections"),
            find_first_key(benchmark, "total_detections"),
            default=None
        ),
        "frames_with_detections": first_value(
            find_first_key(detection, "frames_with_detections"),
            find_first_key(benchmark, "frames_with_detections"),
            default=None
        ),
        "tracked_detections": first_value(
            find_first_numeric_key(benchmark, "tracked_detections"),
            find_first_numeric_key(tracking, "tracked_detections"),
            sum_list_lengths_by_key(tracking, "tracked_detections"),
            default=None
        ),
        "total_unique_tracks": first_value(
            find_first_key(tracking, "total_unique_tracks"),
            find_first_key(benchmark, "total_unique_tracks"),
            default=None
        ),
        "class_counts": first_value(
            find_first_key(detection, "class_counts"),
            find_first_key(benchmark, "class_counts"),
            default={}
        ),
        "unique_track_counts": first_value(
            find_first_key(tracking, "unique_track_counts"),
            find_first_key(benchmark, "unique_track_counts"),
            default={}
        ),
    }

    reasoning_metrics = {
        "semantic_event_count": first_value(
            semantic.get("semantic_event_count"),
            len(semantic.get("semantic_events", [])) if isinstance(semantic.get("semantic_events"), list) else None,
            safe_get(benchmark, ["reasoning_metrics", "semantic_event_count"]),
            default=len(events)
        ),
        "relation_event_count": first_value(
            relation.get("relation_event_count"),
            safe_get(relation, ["summary", "relation_event_count"]),
            default=None
        ),
        "proximity_risk_event_count": first_value(
            proximity.get("risk_event_count"),
            safe_get(benchmark, ["reasoning_metrics", "proximity_risk_event_count"]),
            default=None
        ),
        "proximity_high_or_above_count": first_value(
            proximity.get("high_or_above_count"),
            safe_get(benchmark, ["reasoning_metrics", "proximity_high_or_above_count"]),
            default=None
        ),
        "vlm_reasoned_event_count": first_value(
            event_vlm.get("analyzed_events"),
            safe_get(benchmark, ["reasoning_metrics", "vlm_reasoned_event_count"]),
            default=None
        ),
        "vlm_parse_error_count": first_value(
            event_vlm.get("parse_errors"),
            safe_get(benchmark, ["reasoning_metrics", "vlm_parse_error_count"]),
            default=None
        ),
        "risk_action_event_count": first_value(
            risk_action.get("event_decision_count"),
            len(risk_action.get("event_decisions", [])) if isinstance(risk_action.get("event_decisions"), list) else None,
            safe_get(benchmark, ["reasoning_metrics", "risk_action_event_count"]),
            default=None
        ),
    }

    timeline = []
    for event in events:
        if not isinstance(event, dict):
            continue

        event_id = first_value(event.get("event_id"), event.get("id"), default="unknown_event")
        risk = normalize_risk(first_value(event.get("risk"), event.get("risk_level"), event.get("priority")))
        event_type = first_value(event.get("event_type"), event.get("type"), default="unknown")
        event_name = first_value(event.get("event_name_tr"), event.get("name"), event.get("title"), default=event_id)

        timeline.append({
            "event_id": event_id,
            "event_name_tr": event_name,
            "event_type": event_type,
            "start_time": first_value(event.get("start_time"), event.get("start"), default=None),
            "end_time": first_value(event.get("end_time"), event.get("end"), default=None),
            "peak_time": first_value(event.get("peak_time"), event.get("critical_time"), event.get("timestamp"), default=None),
            "risk": risk,
            "risk_tr": risk_label_tr(risk),
            "priority": first_value(event.get("priority"), risk, default=None),
            "risk_reason_tr": first_value(event.get("risk_reason_tr"), event.get("risk_reason"), default=None),
            "vlm_explanation_tr": first_value(event.get("vlm_explanation_tr"), event.get("vlm_explanation"), default=None),
            "operator_actions_tr": first_value(event.get("operator_actions_tr"), event.get("operator_actions"), default=[]),
            "evidence": first_value(event.get("evidence"), default=[]),
        })

    timeline.sort(
        key=lambda e: (
            -RISK_ORDER.get(e.get("risk") or "none", 0),
            str(e.get("peak_time") or "")
        )
    )

    source_paths = extract_source_paths(run_dir)

    report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "executive_jury_report_builder",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "executive_summary": executive_summary,
        "operator_decision_support": {
            "recommended_posture_tr": action_posture_tr(overall_risk),
            "first_priority_event": timeline[0] if timeline else None,
        },
        "video_metrics": video_metrics,
        "detection_tracking_summary": detection_tracking,
        "reasoning_stack_summary": reasoning_metrics,
        "event_timeline": timeline,
        "evidence_health": {
            "source_json_count": len(source_paths["json_files"]),
            "missing_json_count": len(source_paths["missing_json_files"]),
            "missing_json_files": source_paths["missing_json_files"],
            "schema_validation_status": executive_summary["validation_status"],
            "submission_ready": executive_summary["submission_ready"],
        },
        "jury_highlights_tr": [
            "Sistem video girdisini uçtan uca işleyerek sahne bağlamı, nesne/tracking kanıtı, semantik olay, VLM yorumu, risk ve aksiyon çıktısını tek zincirde birleştirir.",
            "YOLO odak politikası sahne bağlamına göre seçilir; bu sayede sistem tek bir sabit sınıf listesine bağlı kalmaz.",
            "Frame bazlı detection sayıları ile benzersiz fiziksel nesne/kişi tahminleri ayrıştırılır.",
            "Nihai karar standardize edilmiş Scenario 3 JSON şeması ve validator ile kontrol edilir.",
            "Bu rapor jüri/demo anlatımı içindir; gerçek doğruluk için manuel etiketli ground-truth gerekir."
        ],
        "limitations_tr": [
            "VLM ve YOLO çıktıları operatör doğrulaması gerektiren karar destek kanıtlarıdır; tek başına kesin hüküm değildir.",
            "mAP, precision ve recall gibi doğruluk metrikleri bu raporda verilmez; bunun için etiketli test seti gerekir.",
            "Custom class stratejisindeki bazı kavramlar YOLO nesnesi değil, sanal bölge veya kural tabanlı semantik kavramdır.",
            "Risk seviyesi, mevcut video örneği ve pipeline kanıtlarına göre otomatik üretilmiş önceliklendirmedir."
        ],
        "source_paths": source_paths,
    }

    return report


def build_markdown(report):
    s = report["executive_summary"]
    ds = report["detection_tracking_summary"]
    rs = report["reasoning_stack_summary"]
    vm = report["video_metrics"]
    health = report["evidence_health"]

    lines = []
    lines.append("# ÇAŞIT — Jüri İçin Executive Video Analiz Raporu")
    lines.append("")
    lines.append("> Bu rapor, CASIT/ÇAŞIT pipeline çıktılarının tekleştirilmiş karar-destek özetidir.")
    lines.append("")

    lines.append("## 1. Yönetici Özeti")
    lines.append("")
    lines.append(f"- Video: `{s.get('video_name')}`")
    lines.append(f"- Sahne tipi: `{s.get('scene_type')}`")
    lines.append(f"- Domain: `{s.get('domain')}`")
    lines.append(f"- Seçilen policy: `{s.get('selected_policy')}`")
    lines.append(f"- Nihai risk: **{s.get('overall_risk_tr')}** (`{s.get('overall_risk')}`)")
    lines.append(f"- Olay sayısı: `{s.get('event_count')}`")
    lines.append(f"- Yüksek riskli olay: `{s.get('high_event_count')}`")
    lines.append(f"- Kritik olay: `{s.get('critical_event_count')}`")
    lines.append(f"- Submission ready: `{s.get('submission_ready')}`")
    lines.append(f"- Validation status: `{s.get('validation_status')}`")
    lines.append(f"- Internal KPI: `{s.get('internal_kpi')}`")
    lines.append(f"- Quality: `{s.get('quality_score')}` / `{s.get('quality_grade')}`")
    lines.append("")

    lines.append("## 2. Operatör Karar Desteği")
    lines.append("")
    lines.append(report["operator_decision_support"]["recommended_posture_tr"])
    lines.append("")

    first_event = report["operator_decision_support"].get("first_priority_event")
    if first_event:
        lines.append("**İlk öncelikli olay:**")
        lines.append("")
        lines.append(f"- Event ID: `{first_event.get('event_id')}`")
        lines.append(f"- Event adı: {first_event.get('event_name_tr')}")
        lines.append(f"- Event tipi: `{first_event.get('event_type')}`")
        lines.append(f"- Kritik an: `{first_event.get('peak_time')}`")
        lines.append(f"- Risk: `{first_event.get('risk')}`")
        lines.append("")

    lines.append("## 3. Olay Zaman Çizelgesi")
    lines.append("")
    if report["event_timeline"]:
        lines.append("| Öncelik | Event | Tip | Zaman | Kritik An | Risk |")
        lines.append("|---|---|---|---|---|---|")
        for e in report["event_timeline"]:
            lines.append(
                f"| `{e.get('priority')}` | `{e.get('event_id')}` — {e.get('event_name_tr')} | "
                f"`{e.get('event_type')}` | `{e.get('start_time')}` → `{e.get('end_time')}` | "
                f"`{e.get('peak_time')}` | `{e.get('risk')}` |"
            )
    else:
        lines.append("Olay bulunamadı.")
    lines.append("")

    for e in report["event_timeline"]:
        lines.append(f"### {e.get('event_id')} — {e.get('event_name_tr')}")
        lines.append("")
        lines.append(f"- Olay tipi: `{e.get('event_type')}`")
        lines.append(f"- Risk: `{e.get('risk')}`")
        if e.get("risk_reason_tr"):
            lines.append(f"- Risk gerekçesi: {e.get('risk_reason_tr')}")
        if e.get("vlm_explanation_tr"):
            lines.append(f"- VLM açıklaması: {e.get('vlm_explanation_tr')}")
        actions = e.get("operator_actions_tr") or []
        if actions:
            lines.append("")
            lines.append("**Operatör aksiyonları:**")
            for action in actions:
                lines.append(f"- {action}")
        lines.append("")

    lines.append("## 4. Algılama ve Tracking Özeti")
    lines.append("")
    lines.append(f"- Toplam detection: `{ds.get('total_detections')}`")
    lines.append(f"- Detection olan frame: `{ds.get('frames_with_detections')}`")
    lines.append(f"- Tracked detection: `{ds.get('tracked_detections')}`")
    lines.append(f"- Benzersiz track sayısı: `{ds.get('total_unique_tracks')}`")
    lines.append(f"- Class counts: `{ds.get('class_counts')}`")
    lines.append(f"- Unique track counts: `{ds.get('unique_track_counts')}`")
    lines.append("")

    lines.append("## 5. Akıl Yürütme Zinciri")
    lines.append("")
    lines.append(f"- Semantic event count: `{rs.get('semantic_event_count')}`")
    lines.append(f"- Relation event count: `{rs.get('relation_event_count')}`")
    lines.append(f"- Proximity risk event count: `{rs.get('proximity_risk_event_count')}`")
    lines.append(f"- Proximity high+ count: `{rs.get('proximity_high_or_above_count')}`")
    lines.append(f"- VLM reasoned event count: `{rs.get('vlm_reasoned_event_count')}`")
    lines.append(f"- VLM parse error count: `{rs.get('vlm_parse_error_count')}`")
    lines.append(f"- Risk action event count: `{rs.get('risk_action_event_count')}`")
    lines.append("")

    lines.append("## 6. Video Metrikleri")
    lines.append("")
    lines.append(f"- Süre: `{vm.get('duration_seconds')}` saniye")
    lines.append(f"- FPS: `{vm.get('fps')}`")
    lines.append(f"- Frame count: `{vm.get('frame_count')}`")
    lines.append(f"- Çözünürlük: `{vm.get('width')}x{vm.get('height')}`")
    lines.append("")

    lines.append("## 7. Kanıt Sağlığı")
    lines.append("")
    lines.append(f"- Kaynak JSON sayısı: `{health.get('source_json_count')}`")
    lines.append(f"- Eksik JSON sayısı: `{health.get('missing_json_count')}`")
    lines.append(f"- Validation status: `{health.get('schema_validation_status')}`")
    lines.append(f"- Submission ready: `{health.get('submission_ready')}`")
    if health.get("missing_json_files"):
        lines.append("- Eksik dosyalar:")
        for item in health["missing_json_files"]:
            lines.append(f"  - `{item}`")
    lines.append("")

    lines.append("## 8. Jüri İçin Öne Çıkan Noktalar")
    lines.append("")
    for item in report.get("jury_highlights_tr", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 9. Sınırlılıklar")
    lines.append("")
    for item in report.get("limitations_tr", []):
        lines.append(f"- {item}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run-dir",
        default=str(Path.home() / "casit-data/outputs/runs/latest")
    )

    parser.add_argument(
        "--output-json",
        required=True
    )

    parser.add_argument(
        "--output-md",
        required=True
    )

    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser()
    if run_dir.is_symlink():
        run_dir = run_dir.resolve()

    report = build_executive_report(run_dir)

    save_json(report, args.output_json)
    save_text(build_markdown(report), args.output_md)

    s = report["executive_summary"]

    print("CASIT / ÇAŞIT Executive Jury Report Builder")
    print("-------------------------------------------")
    print("Video           :", s.get("video_name"))
    print("Scene           :", s.get("scene_type"))
    print("Domain          :", s.get("domain"))
    print("Overall risk    :", s.get("overall_risk"))
    print("Event count     :", s.get("event_count"))
    print("Submission ready:", s.get("submission_ready"))
    print("Validation      :", s.get("validation_status"))
    print("Internal KPI    :", s.get("internal_kpi"))
    print("Output JSON     :", args.output_json)
    print("Output MD       :", args.output_md)
    print("-------------------------------------------")


if __name__ == "__main__":
    main()
