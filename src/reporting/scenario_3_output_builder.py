#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Scenario 3 Output Builder

Amaç:
TEKNOFEST Senaryo 3 için resmi karar destek çıktısını üretmek.

Bu modül mevcut CASIT çıktılarından tek bir yarışma uyumlu JSON üretir:

- summary_tr
- events
- overall_risk
- decision_support_tr
- limitations_tr

Girdi kaynakları:
- scene_prior.json
- focused_yolo_policy.json
- refined_tracking_report.json
- event_evidence_report.json
- semantic_event_report.json
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


def load_json(path: Path, default=None):
    if default is None:
        default = {}
    if path is None:
        return default
    path = Path(path).expanduser()
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: Path):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_md(text: str, path: Path):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def get_scene_prior(scene_root):
    if isinstance(scene_root, dict) and "scene_prior" in scene_root:
        return scene_root.get("scene_prior", {})
    return scene_root if isinstance(scene_root, dict) else {}


def safe_get(data, path, default=None):
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def normalize_risk_word(value):
    if not value:
        return "low"
    value = str(value).lower().strip()
    mapping = {
        "düşük": "low",
        "orta": "medium",
        "yüksek": "high",
        "kritik": "critical",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "critical": "critical",
    }
    return mapping.get(value, value)


def risk_rank(risk):
    order = {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }
    return order.get(normalize_risk_word(risk), 1)


def infer_event_risk(event_name, scene_type, class_counts, stable_counts):
    text = f"{event_name} {scene_type}".lower()

    critical_terms = [
        "hareketsiz kişi",
        "yaralanma",
        "devril",
        "kaza",
        "yangın",
        "patlama",
        "çarpışma",
        "düşme",
        "silah",
        "şiddet",
    ]

    high_terms = [
        "gerilim",
        "tehlike",
        "risk",
        "yakınlaşma",
        "kalabalık",
        "müdahale",
        "acil",
        "confrontation",
        "accident",
    ]

    medium_terms = [
        "trafik",
        "yaya",
        "araç",
        "construction",
        "construction_site",
        "work_zone",
        "hareketlilik",
    ]

    if any(term in text for term in critical_terms):
        return "critical"

    if any(term in text for term in high_terms):
        return "high"

    if any(term in text for term in medium_terms):
        return "medium"

    person_count = stable_counts.get("person") or class_counts.get("person") or 0
    vehicle_count = (
        (stable_counts.get("car") or class_counts.get("car") or 0)
        + (stable_counts.get("truck") or class_counts.get("truck") or 0)
        + (stable_counts.get("bus") or class_counts.get("bus") or 0)
        + (stable_counts.get("motorcycle") or class_counts.get("motorcycle") or 0)
    )

    if person_count and vehicle_count:
        return "medium"

    return "low"


def actions_for_event(event_name, risk_level, scene_type):
    text = f"{event_name} {scene_type}".lower()

    actions = []

    if "hareketsiz" in text or "yaralan" in text:
        actions.extend([
            "Sağlık ekibini olay noktasına yönlendir.",
            "Alanı güvenlik altına al.",
            "Olay kaydını ve zaman damgasını operatöre göster."
        ])
    elif "kaza" in text or "devril" in text or "çarpış" in text:
        actions.extend([
            "Olay bölgesini güvenlik altına al.",
            "Araç ve personel hareketini geçici olarak durdur.",
            "Saha sorumlusuna olay zaman damgasını bildir."
        ])
    elif "construction" in text or "inşaat" in text or "work_zone" in text:
        actions.extend([
            "Çalışma alanındaki personel-araç yakınlığını kontrol et.",
            "Ağır araç hareketlerini ve yaya geçişlerini doğrula.",
            "Gerekirse alan güvenlik şeridi ve uyarı işaretlerini kontrol et."
        ])
    elif "trafik" in text or "araç" in text or "yaya" in text:
        actions.extend([
            "Araç ve yaya hareketlerini kritik zaman damgasında incele.",
            "Riskli yakınlaşma olup olmadığını operatör ekranında doğrula.",
            "Gerekirse saha güvenliği veya trafik sorumlusuna bilgi ver."
        ])
    elif "kalabalık" in text or "gerilim" in text or "confrontation" in text:
        actions.extend([
            "Kalabalığın yoğunlaştığı zaman aralığını incele.",
            "Güvenlik personeline olay noktasını bildir.",
            "Olayın büyüme riski açısından kayıtları kontrol et."
        ])
    else:
        actions.extend([
            "Belirlenen zaman aralığını operatör tarafından kontrol et.",
            "Nesne ve hareket kanıtlarını doğrula.",
            "Gerekirse olay kaydını işaretle ve rapora ekle."
        ])

    if risk_level in ["high", "critical"]:
        actions.append("Olayı öncelikli inceleme kuyruğuna al.")

    return actions


def extract_class_counts(detection_or_evidence, refined_tracking):
    class_counts = {}

    # event_evidence_report içinden class_evidence arama
    class_evidence = detection_or_evidence.get("class_evidence", {})
    if isinstance(class_evidence, dict):
        for label, info in class_evidence.items():
            if isinstance(info, dict):
                count = (
                    info.get("detection_count")
                    or info.get("frame_detection_count")
                    or info.get("count")
                    or 0
                )
                class_counts[label] = count

    # refined_tracking_report içinden stable_track_count arama
    stable_counts = {}
    refined = refined_tracking.get("refined_classes") or refined_tracking.get("class_refinements") or {}
    if isinstance(refined, dict):
        for label, info in refined.items():
            if isinstance(info, dict):
                stable_counts[label] = (
                    info.get("stable_track_count")
                    or info.get("estimated_physical_count")
                    or 0
                )

    return class_counts, stable_counts


def build_summary_tr(scene_type, domain, events, overall_risk):
    if events:
        event_names = [e.get("event_name_tr", "olay") for e in events]
        first_event = event_names[0]
        if len(events) == 1:
            return (
                f"Video {scene_type or 'bilinmeyen'} bağlamında analiz edilmiştir. "
                f"Sistemde 1 ana olay belirlenmiştir: {first_event}. "
                f"Genel risk seviyesi {overall_risk} olarak değerlendirilmiştir."
            )
        return (
            f"Video {scene_type or 'bilinmeyen'} bağlamında analiz edilmiştir. "
            f"Sistemde {len(events)} olay belirlenmiştir. "
            f"Öne çıkan olay: {first_event}. "
            f"Genel risk seviyesi {overall_risk} olarak değerlendirilmiştir."
        )

    return (
        f"Video {scene_type or 'bilinmeyen'} bağlamında analiz edilmiştir. "
        f"Belirgin semantik olay tespit edilmemiştir. "
        f"Genel risk seviyesi {overall_risk} olarak değerlendirilmiştir."
    )


def build_decision_support(events, overall_risk):
    if not events:
        return (
            "Operatör için belirgin bir kritik olay üretilmemiştir. "
            "Yine de video kayıtları ve algılama kanıtları manuel doğrulama için incelenebilir."
        )

    if overall_risk in ["critical", "high"]:
        return (
            "Operatör, yüksek öncelikli olay zaman damgalarını incelemeli, "
            "alan güvenliği ve ilgili müdahale birimlerini değerlendirmelidir."
        )

    if overall_risk == "medium":
        return (
            "Operatör, belirlenen olay zaman aralığını incelemeli ve kişi-araç-nesne "
            "yakınlaşmaları gibi bağlamsal riskleri doğrulamalıdır."
        )

    return (
        "Operatör, düşük riskli olay kayıtlarını doğrulama amacıyla inceleyebilir. "
        "Acil müdahale gerektiren açık bir bulgu üretilmemiştir."
    )


def convert_semantic_events(semantic_report, scene_type, class_counts, stable_counts):
    semantic_events = semantic_report.get("semantic_events", [])
    output_events = []

    if not isinstance(semantic_events, list):
        return output_events

    for idx, event in enumerate(semantic_events, start=1):
        event_name = (
            event.get("event_name")
            or event.get("event_name_tr")
            or event.get("name")
            or "Anlamlandırılmış video olayı"
        )

        risk_level = infer_event_risk(
            event_name=event_name,
            scene_type=scene_type,
            class_counts=class_counts,
            stable_counts=stable_counts,
        )

        evidence = []

        source_candidates = event.get("source_candidate_ids") or event.get("source_candidates")
        if source_candidates:
            evidence.append(f"Hareket adayı kaynakları: {source_candidates}")

        for label, count in stable_counts.items():
            if count:
                evidence.append(f"{label}: yaklaşık {count} stable track")

        for label, count in class_counts.items():
            if count and label not in stable_counts:
                evidence.append(f"{label}: {count} frame-level detection")

        if not evidence:
            evidence.append("Semantik olay, context window ve hareket enerjisi üzerinden çıkarılmıştır.")

        output_events.append({
            "event_id": event.get("semantic_event_id") or f"EVT_{idx:03d}",
            "start_time": event.get("start_timestamp") or event.get("start_time"),
            "end_time": event.get("end_timestamp") or event.get("end_time"),
            "peak_time": event.get("peak_timestamp") or event.get("peak_time"),
            "event_type": event.get("event_type") or "semantic_video_event",
            "event_name_tr": event_name,
            "risk_level": risk_level,
            "evidence": evidence,
            "operator_actions_tr": actions_for_event(event_name, risk_level, scene_type),
        })

    return output_events


def build_scenario_3_output(
    scene_prior_path,
    focused_policy_path,
    refined_tracking_path,
    event_evidence_path,
    semantic_event_path,
):
    scene_root = load_json(scene_prior_path)
    focused_policy = load_json(focused_policy_path)
    refined_tracking = load_json(refined_tracking_path)
    event_evidence = load_json(event_evidence_path)
    semantic_report = load_json(semantic_event_path)

    prior = get_scene_prior(scene_root)

    scene_type = prior.get("scene_type") or safe_get(event_evidence, ["scene_context", "scene_type"])
    domain = prior.get("domain") or safe_get(event_evidence, ["scene_context", "domain"])
    confidence = prior.get("confidence") or safe_get(event_evidence, ["scene_context", "confidence"])

    selected_policy = (
        safe_get(focused_policy, ["selected_policy", "name"])
        or focused_policy.get("policy_name")
    )

    class_counts, stable_counts = extract_class_counts(event_evidence, refined_tracking)

    events = convert_semantic_events(
        semantic_report=semantic_report,
        scene_type=scene_type,
        class_counts=class_counts,
        stable_counts=stable_counts,
    )

    if events:
        overall_risk = max(
            [e.get("risk_level", "low") for e in events],
            key=risk_rank,
        )
    else:
        overall_risk = "low"

    summary_tr = build_summary_tr(scene_type, domain, events, overall_risk)
    decision_support_tr = build_decision_support(events, overall_risk)

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "scenario_3_output_builder",
            "version": "0.4.0-draft",
            "generated_at": datetime.now().isoformat(timespec="seconds")
        },
        "scenario": {
            "competition": "TEKNOFEST 2026 Türkçe Yapay Zekâ Dil Ajanları Yarışması",
            "scenario_name": "Senaryo 3: Video Analiz ve Karar Destek Sistemi",
            "scope_lock": "SCENARIO_3_SCOPE.md"
        },
        "input_context": {
            "scene_type": scene_type,
            "domain": domain,
            "scene_confidence": confidence,
            "selected_policy": selected_policy
        },
        "summary_tr": summary_tr,
        "events": events,
        "overall_risk": overall_risk,
        "decision_support_tr": decision_support_tr,
        "limitations_tr": (
            "Bu çıktı CASIT v0.4 taslak karar destek şemasına göre üretilmiştir. "
            "Risk seviyesi ve aksiyon önerileri, mevcut nesne tespiti, tracking, hareket enerjisi "
            "ve semantik olay katmanı üzerinden çıkarılmıştır. Kritik kararlar için operatör doğrulaması gereklidir."
        ),
        "machine_readable_notes": {
            "detection_count_note": "Frame-level detection count gerçek fiziksel nesne sayısı değildir.",
            "tracking_count_note": "Stable track count tahmini fiziksel sayıdır; mutlak gerçek kabul edilmemelidir.",
            "event_note": "Motion candidate semantik olay değildir; semantic event yorumlanmış olay katmanıdır."
        }
    }

    return output


def build_markdown_report(data):
    lines = []

    lines.append("# CASIT / ÇAŞIT — Senaryo 3 Karar Destek Çıktısı")
    lines.append("")
    lines.append(f"**Senaryo:** {data['scenario']['scenario_name']}")
    lines.append(f"**Sahne tipi:** `{data['input_context'].get('scene_type')}`")
    lines.append(f"**Domain:** `{data['input_context'].get('domain')}`")
    lines.append(f"**Seçilen policy:** `{data['input_context'].get('selected_policy')}`")
    lines.append(f"**Genel risk:** `{data.get('overall_risk')}`")
    lines.append("")
    lines.append("## Türkçe Özet")
    lines.append("")
    lines.append(data.get("summary_tr", ""))
    lines.append("")
    lines.append("## Operatör Karar Desteği")
    lines.append("")
    lines.append(data.get("decision_support_tr", ""))
    lines.append("")
    lines.append("## Olaylar")
    lines.append("")

    events = data.get("events", [])
    if not events:
        lines.append("Belirgin semantik olay tespit edilmedi.")
    else:
        for event in events:
            lines.append(f"### {event.get('event_id')} — {event.get('event_name_tr')}")
            lines.append("")
            lines.append(f"- Başlangıç: `{event.get('start_time')}`")
            lines.append(f"- Bitiş: `{event.get('end_time')}`")
            lines.append(f"- Kritik / tepe an: `{event.get('peak_time')}`")
            lines.append(f"- Risk seviyesi: `{event.get('risk_level')}`")
            lines.append("")
            lines.append("**Kanıtlar:**")
            for ev in event.get("evidence", []):
                lines.append(f"- {ev}")
            lines.append("")
            lines.append("**Operatör aksiyon önerileri:**")
            for action in event.get("operator_actions_tr", []):
                lines.append(f"- {action}")
            lines.append("")

    lines.append("## Sınırlılıklar")
    lines.append("")
    lines.append(data.get("limitations_tr", ""))

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--scene-prior", required=True)
    parser.add_argument("--focused-policy", required=True)
    parser.add_argument("--refined-tracking", required=True)
    parser.add_argument("--event-evidence", required=True)
    parser.add_argument("--semantic-event", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)

    args = parser.parse_args()

    output = build_scenario_3_output(
        scene_prior_path=Path(args.scene_prior),
        focused_policy_path=Path(args.focused_policy),
        refined_tracking_path=Path(args.refined_tracking),
        event_evidence_path=Path(args.event_evidence),
        semantic_event_path=Path(args.semantic_event),
    )

    save_json(output, Path(args.output_json))
    save_md(build_markdown_report(output), Path(args.output_md))

    print("CASIT / ÇAŞIT Scenario 3 Output Builder")
    print("--------------------------------------")
    print("Scene type      :", output["input_context"].get("scene_type"))
    print("Domain          :", output["input_context"].get("domain"))
    print("Selected policy :", output["input_context"].get("selected_policy"))
    print("Event count     :", len(output.get("events", [])))
    print("Overall risk    :", output.get("overall_risk"))
    print("Output JSON     :", args.output_json)
    print("Output MD       :", args.output_md)
    print("--------------------------------------")


if __name__ == "__main__":
    main()
