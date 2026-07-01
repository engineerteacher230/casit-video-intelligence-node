#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Risk & Action Engine v2

Amaç:
Semantic event, proximity risk ve Event VLM Reasoner çıktılarını birleştirerek
daha güçlü nihai risk ve operatör aksiyonu üretmek.

Girdi:
- semantic_event_report.json
- proximity_risk_report.json
- event_vlm_reasoning_report.json
- scenario_3_output.json optional

Çıktı:
- risk_action_report_v2.json
- risk_action_report_v2.md
"""

import argparse
import json
import re
from pathlib import Path
from datetime import datetime


RISK_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

RANK_RISK = {
    1: "low",
    2: "medium",
    3: "high",
    4: "critical",
}


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


def timestamp_to_seconds(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()
    m = re.match(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})$", value)
    if not m:
        return None

    hh, mm, ss, ms = [int(x) for x in m.groups()]
    return hh * 3600 + mm * 60 + ss + ms / 1000.0


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
    return value if value in RISK_RANK else "low"


def max_risk(values):
    values = [normalize_risk(v) for v in values if v]
    if not values:
        return "low"

    return max(values, key=lambda v: RISK_RANK.get(v, 1))


def priority_for_risk(risk):
    risk = normalize_risk(risk)

    if risk == "critical":
        return "immediate"
    if risk == "high":
        return "high"
    if risk == "medium":
        return "normal"
    return "low"


def time_overlap_seconds(a_start, a_end, b_start, b_end):
    if None in [a_start, a_end, b_start, b_end]:
        return 0.0

    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def dedupe_key(value):
    text = str(value).strip().lower()

    # Noktalama ve küçük farkları azalt
    text = text.replace(".", "")
    text = text.replace(",", "")
    text = text.replace(";", "")
    text = text.replace(":", "")
    text = " ".join(text.split())

    # Öncelik / acil inceleme ifadeleri
    if "inceleme kuyruğuna al" in text:
        return "priority_queue"

    if "öncelikli incele" in text and "kişi-araç" not in text:
        return "priority_queue"

    if "acil inceleme" in text:
        return "priority_queue"

    # Kritik doğrulama
    if "kritik risk olarak işaretle" in text:
        return "critical_verify"

    if "operatör doğrulaması iste" in text:
        return "critical_verify"

    # Kişi-araç yakınlaşması doğrulama ailesi
    if "kişi-araç yakınlaş" in text:
        if any(x in text for x in ["zaman damga", "zaman aralığı", "kare", "kontrol et", "doğrula", "öncelikli incele"]):
            return "person_vehicle_proximity_verify"

    # Araç yönü + yaya/kalabalık konumu ailesi
    if "araç hareket yönü" in text and "yaya/kalabalık konumunu" in text:
        return "vehicle_pedestrian_position_check"

    # Saha güvenlik bilgilendirme ailesi
    if "saha güvenlik" in text and "kişi-araç" in text:
        return "notify_security_person_vehicle"

    # Kalabalık yön/yoğunluk/araç kesişimi ailesi
    if "kalabalığın yönünü" in text and "yoğunluğunu" in text:
        return "crowd_vehicle_intersection_check"

    if "araçlarla kesiş" in text and "kalabalık" in text:
        return "crowd_vehicle_intersection_check"

    # Kalabalık sıkışma/panik/güvenlik riski ailesi
    if "sıkışma" in text and "panik" in text:
        return "crowd_panic_security_check"

    if "güvenlik riski" in text and "kalabalık" in text:
        return "crowd_panic_security_check"

    # Saha güvenlik ekibi yönlendirme
    if "saha güvenlik ekibini" in text and "yönlendir" in text:
        return "dispatch_security_team"

    # Kaza kontrol ailesi
    if "olası kaza" in text and "kare" in text:
        return "accident_frame_review"

    if "hareketsiz kişi" in text or "devrilen araç" in text or "çarpışma belirtisi" in text:
        return "accident_evidence_verify"

    return text


def dedupe(items, max_items=None):
    out = []
    seen = set()

    for item in items:
        if item is None:
            continue

        if isinstance(item, list):
            source = item
        else:
            source = [item]

        for value in source:
            if value is None:
                continue

            text = str(value).strip()
            if not text:
                continue

            key = dedupe_key(text)
            if key in seen:
                continue

            seen.add(key)
            out.append(value)

            if max_items and len(out) >= max_items:
                return out

    return out


def compact_reason(text, max_len=500):
    if not text:
        return ""
    text = str(text).replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


def select_proximity_for_event(event, proximity_report, max_items=8):
    start = timestamp_to_seconds(event.get("start_timestamp") or event.get("start_time"))
    end = timestamp_to_seconds(event.get("end_timestamp") or event.get("end_time"))

    selected = []

    for risk in proximity_report.get("risk_events", []):
        r_start = timestamp_to_seconds(risk.get("start_time"))
        r_end = timestamp_to_seconds(risk.get("end_time"))

        overlap = time_overlap_seconds(start, end, r_start, r_end)
        if overlap <= 0:
            continue

        selected.append({
            "risk_event_id": risk.get("risk_event_id"),
            "risk_type": risk.get("risk_type"),
            "risk_level": normalize_risk(risk.get("risk_level")),
            "priority": risk.get("priority"),
            "start_time": risk.get("start_time"),
            "end_time": risk.get("end_time"),
            "peak_time": risk.get("peak_time"),
            "overlap_seconds": round(overlap, 3),
            "risk_reason_tr": compact_reason(risk.get("risk_reason_tr"), 450),
            "operator_actions_tr": risk.get("operator_actions_tr", []),
        })

    selected.sort(
        key=lambda x: (
            RISK_RANK.get(x.get("risk_level"), 1),
            x.get("overlap_seconds", 0.0),
        ),
        reverse=True,
    )

    return selected[:max_items]


def build_vlm_map(event_vlm_report):
    mapping = {}

    for item in event_vlm_report.get("vlm_event_interpretations", []):
        ev = item.get("normalized_interpretation", {})
        event_id = ev.get("semantic_event_id") or item.get("semantic_event_id")
        if not event_id:
            continue
        mapping[event_id] = ev

    return mapping


def infer_event_type(semantic_event, vlm_event, proximity_items):
    if vlm_event.get("vlm_event_type"):
        return vlm_event.get("vlm_event_type")

    types = [p.get("risk_type", "") for p in proximity_items]
    joined = " ".join(types).lower()

    if "person_vehicle" in joined:
        return "person_vehicle_risk"
    if "vehicle_vehicle" in joined:
        return "vehicle_vehicle_risk"
    if "crowd" in joined:
        return "crowd_movement"

    name = (semantic_event.get("event_name") or "").lower()
    if "kalabalık" in name or "crowd" in name:
        return "crowd_movement"

    return "semantic_video_event"


def build_final_actions(event_type, final_risk, vlm_actions, proximity_actions):
    actions = []

    if final_risk in {"critical", "high"}:
        actions.append("Olayı öncelikli inceleme kuyruğuna al.")

    if final_risk == "critical":
        actions.append("Kritik risk olarak işaretle ve operatör doğrulaması iste.")

    if event_type == "person_vehicle_risk":
        actions.extend([
            "Kişi-araç yakınlaşmasının olduğu zaman damgalarını kontrol et.",
            "Araç hareket yönü ile yaya/kalabalık konumunu birlikte doğrula.",
            "Saha güvenlik sorumlusuna kişi-araç yakınlaşması bilgisini ilet."
        ])

    elif event_type == "vehicle_vehicle_risk":
        actions.extend([
            "Araçlar arasındaki düşük mesafe veya yakınlaşma anını kontrol et.",
            "Araçların yön ve manevra davranışlarını doğrula.",
            "Saha trafik/sürüş güvenliği sorumlusuna bilgi ver."
        ])

    elif event_type == "crowd_movement":
        actions.extend([
            "Kalabalığın yönünü, yoğunluğunu ve araçlarla kesişimini kontrol et.",
            "Sıkışma, panik veya olağandışı hareket belirtisi olup olmadığını incele.",
            "Gerekirse saha güvenlik ekibini ilgili zaman aralığına yönlendir."
        ])

    elif event_type == "accident_possible":
        actions.extend([
            "Olası kaza belirtisi bulunan kareleri yakınlaştırarak incele.",
            "Hareketsiz kişi, devrilen araç veya çarpışma belirtisi olup olmadığını doğrula.",
            "Şüphe güçlüyse acil müdahale prosedürünü değerlendirmek üzere sorumluya bildir."
        ])

    else:
        actions.extend([
            "Olay zaman aralığını manuel olarak incele.",
            "VLM yorumu, proximity riski ve semantic event kanıtlarını karşılaştır.",
            "Belirsizliği karar destek raporunda açıkça belirt."
        ])

    actions.extend(vlm_actions or [])
    actions.extend(proximity_actions or [])

    return dedupe(actions, max_items=5)


def build_escalation_reason(final_risk, semantic_risk, vlm_risk, proximity_risk, event_type):
    return (
        f"Nihai risk {final_risk} seçildi. "
        f"Semantic risk: {semantic_risk}; VLM risk: {vlm_risk}; proximity risk: {proximity_risk}. "
        f"Olay tipi: {event_type}. "
        f"Karar, görsel VLM yorumu ile kişi/araç/kalabalık yakınlık kanıtlarının birlikte değerlendirilmesine dayanır."
    )


def semantic_risk_guess(event):
    # Eski semantic event raporunda risk yoksa güvenli varsayılan.
    if event.get("risk_level"):
        return normalize_risk(event.get("risk_level"))

    name = (event.get("event_name") or event.get("event_name_tr") or "").lower()
    scene = (event.get("scene_type") or "").lower()

    text = f"{name} {scene}"

    if any(k in text for k in ["accident", "kaza", "collision", "çarpışma"]):
        return "high"

    if any(k in text for k in ["crowd", "kalabalık", "security", "güvenlik"]):
        return "medium"

    return "low"


def build_event_decision(semantic_event, vlm_map, proximity_report):
    event_id = semantic_event.get("semantic_event_id")
    vlm_event = vlm_map.get(event_id, {})

    proximity_items = select_proximity_for_event(
        event=semantic_event,
        proximity_report=proximity_report,
        max_items=8,
    )

    semantic_risk = semantic_risk_guess(semantic_event)
    vlm_risk = normalize_risk(vlm_event.get("risk_level"))
    proximity_risk = max_risk([item.get("risk_level") for item in proximity_items])

    final_risk = max_risk([semantic_risk, vlm_risk, proximity_risk])
    event_type = infer_event_type(semantic_event, vlm_event, proximity_items)

    vlm_actions = vlm_event.get("operator_actions_tr", [])
    proximity_actions = []
    for item in proximity_items:
        proximity_actions.extend(item.get("operator_actions_tr", []))

    actions = build_final_actions(
        event_type=event_type,
        final_risk=final_risk,
        vlm_actions=vlm_actions,
        proximity_actions=proximity_actions,
    )

    evidence = []

    source_candidates = (
        semantic_event.get("source_candidate_ids")
        or semantic_event.get("source_candidates")
        or []
    )

    if source_candidates:
        evidence.append(f"Hareket adayı kaynakları: {source_candidates}")

    if vlm_event:
        evidence.append(f"VLM olay tipi: {vlm_event.get('vlm_event_type')}")
        evidence.append(f"VLM gerekçesi: {vlm_event.get('risk_reason_tr')}")

    if proximity_items:
        top = proximity_items[0]
        evidence.append(
            f"En güçlü proximity kanıtı: {top.get('risk_event_id')} / "
            f"{top.get('risk_type')} / {top.get('risk_level')} / "
            f"{top.get('start_time')}→{top.get('end_time')}"
        )

    return {
        "event_id": event_id,
        "context_window_id": semantic_event.get("context_window_id"),
        "start_time": semantic_event.get("start_timestamp") or semantic_event.get("start_time"),
        "end_time": semantic_event.get("end_timestamp") or semantic_event.get("end_time"),
        "peak_time": (
            vlm_event.get("critical_moment_timestamp")
            or semantic_event.get("peak_timestamp")
            or semantic_event.get("peak_time")
        ),
        "event_type": event_type,
        "event_name_tr": (
            vlm_event.get("vlm_event_name_tr")
            or semantic_event.get("event_name")
            or semantic_event.get("event_name_tr")
            or "Video olayı"
        ),
        "final_risk_level": final_risk,
        "priority": priority_for_risk(final_risk),
        "risk_sources": {
            "semantic_risk": semantic_risk,
            "vlm_risk": vlm_risk,
            "proximity_risk": proximity_risk,
        },
        "risk_reason_tr": build_escalation_reason(
            final_risk=final_risk,
            semantic_risk=semantic_risk,
            vlm_risk=vlm_risk,
            proximity_risk=proximity_risk,
            event_type=event_type,
        ),
        "vlm_description_tr": vlm_event.get("vlm_description_tr"),
        "evidence": dedupe(evidence, max_items=8),
        "linked_proximity_risks": proximity_items,
        "operator_actions_tr": actions,
        "limitations_tr": (
            "Nihai risk; semantic event, proximity risk ve temsilci karelere dayalı VLM yorumlarının "
            "birleşimidir. Operatör doğrulaması zorunludur."
        )
    }


def build_operator_summary(event_decisions, overall_risk):
    if not event_decisions:
        return "Belirgin karar destek olayı üretilmedi."

    critical_events = [
        event for event in event_decisions
        if event.get("final_risk_level") == "critical"
    ]

    high_events = [
        event for event in event_decisions
        if event.get("final_risk_level") == "high"
    ]

    if critical_events:
        first = critical_events[0]
        return (
            f"{len(critical_events)} kritik olay tespit edildi. "
            f"İlk öncelik: {first.get('event_id')} / {first.get('event_type')} / "
            f"{first.get('peak_time')}. Operatör acil doğrulama yapmalıdır."
        )

    if high_events:
        first = high_events[0]
        return (
            f"{len(high_events)} yüksek riskli olay tespit edildi. "
            f"İlk öncelik: {first.get('event_id')} / {first.get('event_type')} / "
            f"{first.get('peak_time')}."
        )

    return (
        f"Toplam {len(event_decisions)} olay değerlendirildi. "
        f"Genel risk {overall_risk} seviyesindedir."
    )


def build_report(semantic_report, proximity_report, event_vlm_report, scenario_3_output):
    semantic_events = semantic_report.get("semantic_events", [])
    vlm_map = build_vlm_map(event_vlm_report)

    event_decisions = [
        build_event_decision(event, vlm_map, proximity_report)
        for event in semantic_events
    ]

    overall_risk = max_risk([
        event.get("final_risk_level")
        for event in event_decisions
    ])

    summary = {
        "semantic_event_count": len(semantic_events),
        "event_vlm_count": len(vlm_map),
        "proximity_risk_event_count": len(proximity_report.get("risk_events", [])),
        "risk_action_event_count": len(event_decisions),
        "critical_event_count": sum(1 for e in event_decisions if e.get("final_risk_level") == "critical"),
        "high_event_count": sum(1 for e in event_decisions if e.get("final_risk_level") == "high"),
        "overall_risk_v2": overall_risk,
        "previous_scenario_3_overall_risk": scenario_3_output.get("overall_risk"),
    }

    return {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "risk_action_engine_v2",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "summary": summary,
        "overall_risk_v2": overall_risk,
        "operator_summary_tr": build_operator_summary(event_decisions, overall_risk),
        "event_decisions": event_decisions,
        "integration_notes_tr": [
            "Bu modül Scenario 3 output builder öncesinde nihai risk/aksiyon kararını güçlendirmek için tasarlanmıştır.",
            "Eski scenario_3_output yüksek riskte kalabilir; v2 proximity ve VLM katmanlarını dikkate alır.",
            "Kritik kararlar için operatör doğrulaması zorunludur."
        ]
    }


def build_markdown(report):
    lines = []

    lines.append("# CASIT / ÇAŞIT — Risk & Action Report v2")
    lines.append("")
    lines.append("Bu rapor semantic event, proximity risk ve Event VLM Reasoner çıktılarını birleştirir.")
    lines.append("")

    s = report.get("summary", {})

    lines.append("## Özet")
    lines.append("")
    lines.append(f"- Semantic event sayısı: `{s.get('semantic_event_count')}`")
    lines.append(f"- VLM event sayısı: `{s.get('event_vlm_count')}`")
    lines.append(f"- Proximity risk event sayısı: `{s.get('proximity_risk_event_count')}`")
    lines.append(f"- Risk/action event sayısı: `{s.get('risk_action_event_count')}`")
    lines.append(f"- Critical event sayısı: `{s.get('critical_event_count')}`")
    lines.append(f"- High event sayısı: `{s.get('high_event_count')}`")
    lines.append(f"- Önceki Scenario 3 genel risk: `{s.get('previous_scenario_3_overall_risk')}`")
    lines.append(f"- Risk v2 genel risk: `{s.get('overall_risk_v2')}`")
    lines.append("")

    lines.append("## Operatör Özeti")
    lines.append("")
    lines.append(report.get("operator_summary_tr", ""))
    lines.append("")

    lines.append("## Event Kararları")
    lines.append("")

    for event in report.get("event_decisions", []):
        lines.append(f"### {event.get('event_id')} — {event.get('event_name_tr')}")
        lines.append("")
        lines.append(f"- Zaman: `{event.get('start_time')}` → `{event.get('end_time')}`")
        lines.append(f"- Kritik an: `{event.get('peak_time')}`")
        lines.append(f"- Event tipi: `{event.get('event_type')}`")
        lines.append(f"- Nihai risk: `{event.get('final_risk_level')}`")
        lines.append(f"- Öncelik: `{event.get('priority')}`")
        lines.append(f"- Risk kaynakları: `{event.get('risk_sources')}`")
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

    lines.append("## Notlar")
    lines.append("")
    for note in report.get("integration_notes_tr", []):
        lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--semantic-event", required=True)
    parser.add_argument("--proximity-risk", required=True)
    parser.add_argument("--event-vlm", required=True)
    parser.add_argument("--scenario-3-output", required=False)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)

    args = parser.parse_args()

    semantic_report = load_json(args.semantic_event)
    proximity_report = load_json(args.proximity_risk)
    event_vlm_report = load_json(args.event_vlm)
    scenario_3_output = load_json(args.scenario_3_output) if args.scenario_3_output else {}

    report = build_report(
        semantic_report=semantic_report,
        proximity_report=proximity_report,
        event_vlm_report=event_vlm_report,
        scenario_3_output=scenario_3_output,
    )

    save_json(report, args.output_json)
    save_text(build_markdown(report), args.output_md)

    print("CASIT / ÇAŞIT Risk & Action Engine v2")
    print("-------------------------------------")
    print("Event decisions :", report["summary"]["risk_action_event_count"])
    print("Critical events :", report["summary"]["critical_event_count"])
    print("High events     :", report["summary"]["high_event_count"])
    print("Overall risk v2 :", report["summary"]["overall_risk_v2"])
    print("Previous risk   :", report["summary"]["previous_scenario_3_overall_risk"])
    print("Output JSON     :", args.output_json)
    print("Output MD       :", args.output_md)
    print("-------------------------------------")


if __name__ == "__main__":
    main()
