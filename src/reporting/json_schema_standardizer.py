#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT JSON Schema Standardizer

Amaç:
CASIT'in farklı modüllerinden gelen JSON çıktılarını tek, standart ve jüriye uygun
Senaryo 3 karar destek şemasına dönüştürmek.

Öncelik sırası:
1. risk_action_report_v2.json
2. event_vlm_reasoning_report.json
3. proximity_risk_report.json
4. scenario_3_output.json
5. semantic_event_report.json

Standart çıktı:
- standardized_scenario_3_output.json
- standardized_scenario_3_output.md
- schema_standardization_report.json
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


RISK_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

VALID_RISKS = set(RISK_RANK.keys())


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


def normalize_risk(value):
    if not value:
        return "low"

    value = str(value).strip().lower()

    aliases = {
        "düşük": "low",
        "orta": "medium",
        "yüksek": "high",
        "kritik": "critical",
    }

    value = aliases.get(value, value)
    return value if value in VALID_RISKS else "low"


def max_risk(values):
    values = [normalize_risk(v) for v in values if v]
    if not values:
        return "low"
    return max(values, key=lambda v: RISK_RANK.get(v, 1))


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def dedupe(values, max_items=None):
    out = []
    seen = set()

    for value in values:
        if value is None:
            continue

        if isinstance(value, list):
            source = value
        else:
            source = [value]

        for item in source:
            if item is None:
                continue

            key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item).strip()

            if not key or key in seen:
                continue

            seen.add(key)
            out.append(item)

            if max_items and len(out) >= max_items:
                return out

    return out


def get_scene_context(scene_prior, event_evidence, scenario_3_output):
    prior = scene_prior.get("scene_prior", scene_prior)

    input_context = scenario_3_output.get("input_context", {}) if isinstance(scenario_3_output, dict) else {}

    return {
        "scene_type": (
            prior.get("scene_type")
            or input_context.get("scene_type")
            or event_evidence.get("scene_context", {}).get("scene_type")
            or "unknown"
        ),
        "domain": (
            prior.get("domain")
            or input_context.get("domain")
            or event_evidence.get("scene_context", {}).get("domain")
            or "unknown"
        ),
        "scene_confidence": (
            prior.get("confidence")
            or input_context.get("scene_confidence")
            or event_evidence.get("scene_context", {}).get("confidence")
            or 0.0
        ),
        "selected_policy": (
            input_context.get("selected_policy")
            or event_evidence.get("selected_policy", {}).get("policy_name")
            or event_evidence.get("selected_policy", {}).get("selected_policy")
            or "unknown"
        )
    }


def build_event_from_risk_action(event_decision):
    risk_level = normalize_risk(event_decision.get("final_risk_level") or event_decision.get("risk_level"))

    return {
        "event_id": event_decision.get("event_id"),
        "context_window_id": event_decision.get("context_window_id"),
        "event_type": event_decision.get("event_type") or "semantic_video_event",
        "event_name_tr": event_decision.get("event_name_tr") or "Video olayı",
        "start_time": event_decision.get("start_time"),
        "end_time": event_decision.get("end_time"),
        "peak_time": event_decision.get("peak_time"),
        "risk_level": risk_level,
        "priority": event_decision.get("priority") or priority_for_risk(risk_level),
        "risk_reason_tr": event_decision.get("risk_reason_tr"),
        "vlm_description_tr": event_decision.get("vlm_description_tr"),
        "risk_sources": event_decision.get("risk_sources", {}),
        "evidence": ensure_list(event_decision.get("evidence")),
        "linked_proximity_risks": ensure_list(event_decision.get("linked_proximity_risks")),
        "operator_actions_tr": dedupe(event_decision.get("operator_actions_tr", []), max_items=8),
        "limitations_tr": event_decision.get("limitations_tr") or "Operatör doğrulaması gereklidir."
    }


def priority_for_risk(risk_level):
    risk_level = normalize_risk(risk_level)

    if risk_level == "critical":
        return "immediate"
    if risk_level == "high":
        return "high"
    if risk_level == "medium":
        return "normal"
    return "low"


def build_events_from_scenario_3(scenario_3_output):
    events = []

    for event in scenario_3_output.get("events", []):
        risk_level = normalize_risk(event.get("risk_level"))

        events.append({
            "event_id": event.get("event_id"),
            "context_window_id": event.get("context_window_id"),
            "event_type": event.get("event_type") or "semantic_video_event",
            "event_name_tr": event.get("event_name_tr") or "Video olayı",
            "start_time": event.get("start_time"),
            "end_time": event.get("end_time"),
            "peak_time": event.get("peak_time"),
            "risk_level": risk_level,
            "priority": priority_for_risk(risk_level),
            "risk_reason_tr": event.get("risk_reason_tr") or "Risk seviyesi önceki Scenario 3 çıktı katmanından alınmıştır.",
            "vlm_description_tr": event.get("vlm_description_tr"),
            "risk_sources": {
                "scenario_3_risk": risk_level
            },
            "evidence": ensure_list(event.get("evidence")),
            "linked_proximity_risks": [],
            "operator_actions_tr": dedupe(event.get("operator_actions_tr", []), max_items=8),
            "limitations_tr": event.get("limitations_tr") or "Operatör doğrulaması gereklidir."
        })

    return events


def build_standard_events(risk_action_report, scenario_3_output):
    event_decisions = risk_action_report.get("event_decisions", [])

    if isinstance(event_decisions, list) and event_decisions:
        return [
            build_event_from_risk_action(event)
            for event in event_decisions
        ]

    return build_events_from_scenario_3(scenario_3_output)


def build_summary_tr(scene_context, events, overall_risk):
    scene_type = scene_context.get("scene_type", "unknown")
    domain = scene_context.get("domain", "unknown")

    if not events:
        return (
            f"Video {scene_type}/{domain} bağlamında analiz edilmiştir. "
            f"Standart şemada olay bulunmamıştır. Genel risk {overall_risk} seviyesindedir."
        )

    critical_count = sum(1 for event in events if event.get("risk_level") == "critical")
    high_count = sum(1 for event in events if event.get("risk_level") == "high")

    first = events[0]

    return (
        f"Video {scene_type}/{domain} bağlamında analiz edilmiştir. "
        f"Standart şemada {len(events)} olay üretilmiştir. "
        f"Kritik olay sayısı {critical_count}, yüksek riskli olay sayısı {high_count}. "
        f"Öncelikli olay {first.get('event_id')} / {first.get('event_type')} / {first.get('peak_time')}. "
        f"Genel risk {overall_risk} seviyesidir."
    )


def build_decision_support_tr(events, overall_risk):
    if not events:
        return "Operatör standart izlemeye devam edebilir; belirgin olay üretilmemiştir."

    if overall_risk == "critical":
        critical_events = [event for event in events if event.get("risk_level") == "critical"]
        first = critical_events[0] if critical_events else events[0]

        return (
            f"Operatör {first.get('event_id')} olayını acil öncelikle incelemelidir. "
            f"Kritik zaman damgası {first.get('peak_time')} olarak işaretlenmiştir. "
            f"Kişi/araç/kalabalık yakınlığı ve VLM görsel yorumu birlikte doğrulanmalıdır."
        )

    if overall_risk == "high":
        return (
            "Operatör yüksek riskli olayları öncelikli incelemeli, saha güvenliği ve müdahale ihtiyacını değerlendirmelidir."
        )

    if overall_risk == "medium":
        return (
            "Operatör olay zaman aralıklarını doğrulamalı, kalabalık veya araç yakınlaşması gibi bağlamsal riskleri kontrol etmelidir."
        )

    return (
        "Operatör düşük riskli olay kayıtlarını doğrulama amacıyla inceleyebilir; acil aksiyon gereksinimi görünmemektedir."
    )


def build_standard_output(scene_prior, event_evidence, risk_action_report, scenario_3_output):
    scene_context = get_scene_context(scene_prior, event_evidence, scenario_3_output)
    events = build_standard_events(risk_action_report, scenario_3_output)

    overall_risk = max_risk([event.get("risk_level") for event in events])

    if risk_action_report.get("overall_risk_v2"):
        overall_risk = max_risk([overall_risk, risk_action_report.get("overall_risk_v2")])

    previous_risk = scenario_3_output.get("overall_risk")

    standard = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "json_schema_standardizer",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "schema": {
            "name": "casit.scenario_3.standard_output",
            "version": "1.0.0",
            "language": "tr",
            "risk_levels": ["low", "medium", "high", "critical"],
            "event_time_format": "HH:MM:SS.mmm",
        },
        "scenario": {
            "competition": "TEKNOFEST 2026 Türkçe Yapay Zekâ Dil Ajanları Yarışması",
            "scenario_name": "Senaryo 3: Video Analiz ve Karar Destek Sistemi",
            "scope_lock": "SCENARIO_3_SCOPE.md",
        },
        "input_context": scene_context,
        "summary_tr": build_summary_tr(scene_context, events, overall_risk),
        "events": events,
        "overall_risk": overall_risk,
        "decision_support_tr": build_decision_support_tr(events, overall_risk),
        "operator_summary_tr": risk_action_report.get("operator_summary_tr"),
        "limitations_tr": (
            "Bu standart çıktı; semantic event, proximity risk, Event VLM Reasoner ve Risk & Action v2 "
            "katmanlarının birleştirilmesiyle üretilmiştir. Kritik kararlar için operatör doğrulaması zorunludur."
        ),
        "source_alignment": {
            "previous_scenario_3_overall_risk": previous_risk,
            "risk_action_overall_risk_v2": risk_action_report.get("overall_risk_v2"),
            "standardized_overall_risk": overall_risk,
            "uses_risk_action_v2": bool(risk_action_report.get("event_decisions")),
        },
        "machine_readable_notes": {
            "event_schema_note": "events dizisi standartlaştırılmış nihai olay listesidir.",
            "risk_schema_note": "risk_level alanı low, medium, high, critical değerlerinden biridir.",
            "priority_schema_note": "priority alanı low, normal, high, immediate değerlerinden biridir.",
            "operator_action_note": "operator_actions_tr karar destek amaçlıdır; otomatik müdahale komutu değildir.",
        }
    }

    return standard


def validate_standard_output(data):
    checks = []

    def add(name, passed, detail):
        checks.append({
            "check": name,
            "passed": bool(passed),
            "detail": detail,
        })

    required_top = [
        "project",
        "schema",
        "scenario",
        "input_context",
        "summary_tr",
        "events",
        "overall_risk",
        "decision_support_tr",
        "limitations_tr",
        "source_alignment",
        "machine_readable_notes",
    ]

    for key in required_top:
        add(
            f"top_level_{key}",
            key in data,
            f"Top-level key `{key}` {'exists' if key in data else 'missing'}."
        )

    add(
        "overall_risk_valid",
        normalize_risk(data.get("overall_risk")) == data.get("overall_risk"),
        f"overall_risk={data.get('overall_risk')}"
    )

    events = data.get("events", [])

    add(
        "events_is_list",
        isinstance(events, list),
        "events alanı liste olmalıdır."
    )

    required_event_keys = [
        "event_id",
        "event_type",
        "event_name_tr",
        "start_time",
        "end_time",
        "peak_time",
        "risk_level",
        "priority",
        "risk_reason_tr",
        "evidence",
        "operator_actions_tr",
        "limitations_tr",
    ]

    for idx, event in enumerate(events, start=1):
        for key in required_event_keys:
            add(
                f"event_{idx}_{key}",
                key in event,
                f"{event.get('event_id')} için `{key}` {'exists' if key in event else 'missing'}."
            )

        add(
            f"event_{idx}_risk_valid",
            event.get("risk_level") in VALID_RISKS,
            f"{event.get('event_id')} risk_level={event.get('risk_level')}"
        )

        add(
            f"event_{idx}_actions_nonempty",
            bool(event.get("operator_actions_tr")),
            f"{event.get('event_id')} operator action count={len(event.get('operator_actions_tr', []))}"
        )

    passed_count = sum(1 for check in checks if check["passed"])
    failed_count = len(checks) - passed_count

    return {
        "schema_validation_passed": failed_count == 0,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "checks": checks,
    }


def build_markdown(data):
    lines = []

    lines.append("# CASIT / ÇAŞIT — Standardized Scenario 3 Output")
    lines.append("")
    lines.append(data.get("summary_tr", ""))
    lines.append("")

    lines.append("## Genel Bilgi")
    lines.append("")
    lines.append(f"- Şema: `{data.get('schema', {}).get('name')}`")
    lines.append(f"- Şema versiyonu: `{data.get('schema', {}).get('version')}`")
    lines.append(f"- Genel risk: `{data.get('overall_risk')}`")
    lines.append(f"- Önceki Scenario 3 risk: `{data.get('source_alignment', {}).get('previous_scenario_3_overall_risk')}`")
    lines.append(f"- Risk Action v2 risk: `{data.get('source_alignment', {}).get('risk_action_overall_risk_v2')}`")
    lines.append("")

    lines.append("## Karar Destek Özeti")
    lines.append("")
    lines.append(data.get("decision_support_tr", ""))
    lines.append("")

    if data.get("operator_summary_tr"):
        lines.append("## Operatör Özeti")
        lines.append("")
        lines.append(data.get("operator_summary_tr"))
        lines.append("")

    lines.append("## Olaylar")
    lines.append("")

    for event in data.get("events", []):
        lines.append(f"### {event.get('event_id')} — {event.get('event_name_tr')}")
        lines.append("")
        lines.append(f"- Olay tipi: `{event.get('event_type')}`")
        lines.append(f"- Zaman: `{event.get('start_time')}` → `{event.get('end_time')}`")
        lines.append(f"- Kritik an: `{event.get('peak_time')}`")
        lines.append(f"- Risk: `{event.get('risk_level')}`")
        lines.append(f"- Öncelik: `{event.get('priority')}`")
        lines.append("")
        lines.append("**Risk gerekçesi:**")
        lines.append("")
        lines.append(event.get("risk_reason_tr", ""))
        lines.append("")

        if event.get("vlm_description_tr"):
            lines.append("**VLM açıklaması:**")
            lines.append("")
            lines.append(event.get("vlm_description_tr"))
            lines.append("")

        lines.append("**Kanıtlar:**")
        for evidence in event.get("evidence", []):
            lines.append(f"- {evidence}")
        lines.append("")

        lines.append("**Operatör aksiyonları:**")
        for action in event.get("operator_actions_tr", []):
            lines.append(f"- {action}")
        lines.append("")

    lines.append("## Sınırlılıklar")
    lines.append("")
    lines.append(data.get("limitations_tr", ""))

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--scene-prior", required=False)
    parser.add_argument("--event-evidence", required=False)
    parser.add_argument("--risk-action-v2", required=True)
    parser.add_argument("--scenario-3-output", required=False)

    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--validation-json", required=True)

    args = parser.parse_args()

    scene_prior = load_json(args.scene_prior)
    event_evidence = load_json(args.event_evidence)
    risk_action_report = load_json(args.risk_action_v2)
    scenario_3_output = load_json(args.scenario_3_output)

    standard = build_standard_output(
        scene_prior=scene_prior,
        event_evidence=event_evidence,
        risk_action_report=risk_action_report,
        scenario_3_output=scenario_3_output,
    )

    validation = validate_standard_output(standard)

    validation_report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "json_schema_standardizer",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "target_schema": standard.get("schema", {}),
        "validation": validation,
        "summary": {
            "standardized_event_count": len(standard.get("events", [])),
            "standardized_overall_risk": standard.get("overall_risk"),
            "schema_validation_passed": validation.get("schema_validation_passed"),
            "failed_count": validation.get("failed_count"),
        }
    }

    save_json(standard, args.output_json)
    save_text(build_markdown(standard), args.output_md)
    save_json(validation_report, args.validation_json)

    print("CASIT / ÇAŞIT JSON Schema Standardizer")
    print("--------------------------------------")
    print("Standardized events :", len(standard.get("events", [])))
    print("Overall risk        :", standard.get("overall_risk"))
    print("Validation passed   :", validation.get("schema_validation_passed"))
    print("Validation failures :", validation.get("failed_count"))
    print("Output JSON         :", args.output_json)
    print("Output MD           :", args.output_md)
    print("Validation JSON     :", args.validation_json)
    print("--------------------------------------")


if __name__ == "__main__":
    main()
