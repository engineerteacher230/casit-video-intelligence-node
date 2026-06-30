#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Proximity Risk Engine

Amaç:
Relation Dynamics Analyzer çıktısını Senaryo 3 karar destek risklerine dönüştürmek.

Bu modül şunları üretir:
- person_vehicle_collision_risk
- vehicle_vehicle_collision_risk
- crowd_density_risk
- close_proximity_risk
- overall_proximity_risk
- Türkçe risk gerekçesi
- Operatör aksiyon önerileri

Not:
Bu modül gerçek metre hesabı yapmaz. Normalize piksel mesafesi ve track ilişkileri üzerinden
karar destek amaçlı risk kanıtı üretir.
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

RANK_RISK = {
    1: "low",
    2: "medium",
    3: "high",
    4: "critical",
}


def load_json(path: Path, default=None):
    if default is None:
        default = {}
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


def save_text(text: str, path: Path):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_risk(value):
    if not value:
        return "low"
    value = str(value).lower().strip()
    aliases = {
        "düşük": "low",
        "orta": "medium",
        "yüksek": "high",
        "kritik": "critical",
    }
    return aliases.get(value, value if value in RISK_RANK else "low")


def max_risk_level(levels):
    if not levels:
        return "low"
    max_rank = max(RISK_RANK.get(normalize_risk(x), 1) for x in levels)
    return RANK_RISK.get(max_rank, "low")


def risk_type_from_relation(relation_event):
    relation_type = relation_event.get("relation_type", "")
    base_type = relation_event.get("base_relation_type", "")
    trend = relation_event.get("trend", "")

    if base_type == "person_vehicle":
        if trend == "approaching":
            return "person_vehicle_collision_risk"
        if trend == "close_proximity":
            return "person_vehicle_close_proximity_risk"
        if trend == "separating":
            return "person_vehicle_residual_risk"

    if base_type == "vehicle_vehicle":
        if trend == "approaching":
            return "vehicle_vehicle_collision_risk"
        if trend == "close_proximity":
            return "vehicle_vehicle_close_proximity_risk"
        if trend == "separating":
            return "vehicle_vehicle_residual_risk"

    if "crowd" in relation_type:
        return "crowd_density_risk"

    return "generic_proximity_risk"


def priority_from_risk(risk_level, min_distance=None):
    risk_level = normalize_risk(risk_level)
    rank = RISK_RANK.get(risk_level, 1)

    if rank >= 4:
        return "immediate"
    if rank >= 3:
        return "high"
    if rank >= 2:
        return "normal"
    return "low"


def action_templates(risk_type, risk_level):
    risk_level = normalize_risk(risk_level)

    if risk_type == "person_vehicle_collision_risk":
        actions = [
            "Kişi-araç yakınlaşmasının görüldüğü zaman aralığını öncelikli incele.",
            "Araç hareket yönünü ve kişinin konumunu operatör ekranında doğrula.",
            "Saha güvenlik sorumlusuna kişi-araç yakınlaşması bilgisini ilet.",
        ]
    elif risk_type == "person_vehicle_close_proximity_risk":
        actions = [
            "Kişi ile araç arasındaki düşük mesafe anını kontrol et.",
            "Araç çevresindeki yaya güvenlik mesafesini doğrula.",
            "Gerekirse saha içi araç hareketini yavaşlatma/durdurma prosedürünü değerlendir.",
        ]
    elif risk_type == "vehicle_vehicle_collision_risk":
        actions = [
            "Araç-araç yakınlaşmasının görüldüğü zaman aralığını incele.",
            "Çarpışma riski veya manevra ihlali olup olmadığını doğrula.",
            "Trafik/saha sorumlusuna araç yakınlaşma bilgisini ilet.",
        ]
    elif risk_type == "vehicle_vehicle_close_proximity_risk":
        actions = [
            "Araçlar arasındaki düşük mesafe anını kontrol et.",
            "Araçların yön ve hız değişimlerini video üzerinden doğrula.",
            "Gerekirse saha trafik düzenini incele.",
        ]
    elif risk_type == "crowd_density_risk":
        actions = [
            "Kalabalığın yoğunlaştığı veya dağıldığı zaman aralığını incele.",
            "Kalabalık yöneliminde güvenlik riski olup olmadığını doğrula.",
            "Gerekirse saha güvenlik personelini bilgilendir.",
        ]
    else:
        actions = [
            "Belirlenen yakınlık riskini operatör tarafından doğrula.",
            "İlgili zaman aralığını karar destek raporuna ekle.",
            "Gerekirse saha sorumlusuna bilgi ver.",
        ]

    if risk_level == "critical":
        actions.insert(0, "Bu olayı acil inceleme kuyruğuna al.")
        actions.append("Olayı kritik risk olarak işaretle ve raporla.")
    elif risk_level == "high":
        actions.insert(0, "Bu olayı yüksek öncelikli inceleme kuyruğuna al.")

    return actions


def build_relation_risk_reason(event, risk_type):
    a = event.get("track_a", {})
    b = event.get("track_b", {})

    a_text = f"{a.get('class_name')}#{a.get('track_id')}"
    b_text = f"{b.get('class_name')}#{b.get('track_id')}"

    trend = event.get("trend")
    risk_level = normalize_risk(event.get("risk_level"))
    min_d = event.get("min_normalized_distance")
    start_d = event.get("start_normalized_distance")
    end_d = event.get("end_normalized_distance")
    approach_delta = event.get("approach_delta")

    if risk_type == "person_vehicle_collision_risk":
        risk_name = "kişi-araç çarpışma/yakınlaşma riski"
    elif risk_type == "person_vehicle_close_proximity_risk":
        risk_name = "kişi-araç yakın temas riski"
    elif risk_type == "vehicle_vehicle_collision_risk":
        risk_name = "araç-araç çarpışma/yakınlaşma riski"
    elif risk_type == "vehicle_vehicle_close_proximity_risk":
        risk_name = "araç-araç yakın temas riski"
    else:
        risk_name = "yakınlık tabanlı risk"

    if trend == "approaching":
        motion_text = "mesafe zaman içinde azalmış"
    elif trend == "separating":
        motion_text = "mesafe zaman içinde artmış; ancak kısa mesafe nedeniyle artık risk gözlemlenmiş"
    elif trend == "close_proximity":
        motion_text = "nesneler düşük mesafe aralığında kalmış"
    else:
        motion_text = "ilişkisel hareket gözlemlenmiş"

    return (
        f"{a_text} ile {b_text} arasında {risk_name} tespit edilmiştir. "
        f"İlişki trendi: {trend}; {motion_text}. "
        f"Başlangıç mesafesi {start_d}, bitiş mesafesi {end_d}, "
        f"minimum normalize mesafe {min_d}, yaklaşma farkı {approach_delta}. "
        f"Risk seviyesi {risk_level} olarak değerlendirilmiştir."
    )


def build_relation_risk_event(event, index):
    risk_level = normalize_risk(event.get("risk_level"))
    risk_type = risk_type_from_relation(event)

    risk_event = {
        "risk_event_id": f"PROX_RISK_{index:04d}",
        "source_relation_event_id": event.get("relation_event_id"),
        "risk_type": risk_type,
        "risk_level": risk_level,
        "priority": priority_from_risk(risk_level, event.get("min_normalized_distance")),
        "start_time": event.get("start_time"),
        "end_time": event.get("end_time"),
        "peak_time": event.get("peak_time"),
        "involved_tracks": [
            event.get("track_a"),
            event.get("track_b"),
        ],
        "relation_evidence": {
            "relation_type": event.get("relation_type"),
            "base_relation_type": event.get("base_relation_type"),
            "trend": event.get("trend"),
            "start_normalized_distance": event.get("start_normalized_distance"),
            "end_normalized_distance": event.get("end_normalized_distance"),
            "min_normalized_distance": event.get("min_normalized_distance"),
            "approach_delta": event.get("approach_delta"),
            "separation_delta": event.get("separation_delta"),
            "common_frame_count": event.get("common_frame_count"),
        },
        "risk_reason_tr": build_relation_risk_reason(event, risk_type),
        "operator_actions_tr": action_templates(risk_type, risk_level),
        "limitations_tr": (
            "Bu risk normalize piksel mesafesi ve track ilişkileri üzerinden hesaplanmıştır. "
            "Gerçek mesafe, hız ve niyet çıkarımı değildir; operatör doğrulaması gerekir."
        )
    }

    return risk_event


def build_crowd_risk_event(event, index):
    risk_level = normalize_risk(event.get("risk_level"))
    trend = event.get("trend")

    if trend in {"crowd_concentrating", "crowd_growing"}:
        risk_type = "crowd_density_risk"
    elif trend in {"crowd_spreading", "crowd_dispersing"}:
        risk_type = "crowd_flow_change_risk"
    else:
        risk_type = "crowd_dynamics_risk"

    return {
        "risk_event_id": f"CROWD_RISK_{index:04d}",
        "source_crowd_event_id": event.get("crowd_event_id"),
        "risk_type": risk_type,
        "risk_level": risk_level,
        "priority": priority_from_risk(risk_level),
        "start_time": None,
        "end_time": None,
        "peak_time": None,
        "crowd_evidence": {
            "trend": trend,
            "max_person_count_in_frame": event.get("max_person_count_in_frame"),
            "average_person_count_per_frame": event.get("average_person_count_per_frame"),
            "early_median_person_count": event.get("early_median_person_count"),
            "late_median_person_count": event.get("late_median_person_count"),
            "early_nearest_neighbor_distance": event.get("early_nearest_neighbor_distance"),
            "late_nearest_neighbor_distance": event.get("late_nearest_neighbor_distance"),
        },
        "risk_reason_tr": event.get("reason_tr") or "Kalabalık dinamiğinde risk oluşturabilecek zamansal değişim gözlemlenmiştir.",
        "operator_actions_tr": action_templates("crowd_density_risk", risk_level),
        "limitations_tr": (
            "Kalabalık riski frame bazlı kişi tespitleri ve yakın komşu mesafeleri üzerinden hesaplanmıştır. "
            "Gerçek kişi sayısı veya niyet tespiti olarak kabul edilmemelidir."
        )
    }


def infer_overall_risk(risk_events):
    if not risk_events:
        return "low"

    levels = [event.get("risk_level") for event in risk_events]
    base = max_risk_level(levels)

    high_count = sum(1 for event in risk_events if RISK_RANK.get(normalize_risk(event.get("risk_level")), 1) >= 3)
    critical_count = sum(1 for event in risk_events if normalize_risk(event.get("risk_level")) == "critical")

    if critical_count >= 2:
        return "critical"

    if base == "high" and high_count >= 4:
        return "critical"

    return base


def build_overall_reason(risk_events, overall_risk):
    if not risk_events:
        return "Yakınlık tabanlı belirgin risk üretilmemiştir."

    risk_counts = {}
    for event in risk_events:
        level = normalize_risk(event.get("risk_level"))
        risk_counts[level] = risk_counts.get(level, 0) + 1

    top = risk_events[0]
    return (
        f"Yakınlık tabanlı analizde toplam {len(risk_events)} risk olayı üretilmiştir. "
        f"Risk dağılımı: {risk_counts}. "
        f"En güçlü risk tipi: {top.get('risk_type')} ({top.get('risk_level')}). "
        f"Genel yakınlık riski {overall_risk} olarak değerlendirilmiştir."
    )


def build_report(relation_dynamics, min_risk_level):
    relation_events = relation_dynamics.get("relation_events", [])
    crowd_events = relation_dynamics.get("crowd_dynamics", [])

    min_rank = RISK_RANK.get(normalize_risk(min_risk_level), 2)

    risk_events = []

    for event in relation_events:
        risk_level = normalize_risk(event.get("risk_level"))
        if RISK_RANK.get(risk_level, 1) < min_rank:
            continue

        risk_events.append(
            build_relation_risk_event(event, len(risk_events) + 1)
        )

    crowd_index = 1
    for event in crowd_events:
        risk_level = normalize_risk(event.get("risk_level"))
        if RISK_RANK.get(risk_level, 1) < min_rank:
            continue

        risk_events.append(
            build_crowd_risk_event(event, crowd_index)
        )
        crowd_index += 1

    risk_events.sort(
        key=lambda item: (
            RISK_RANK.get(normalize_risk(item.get("risk_level")), 1),
            item.get("priority") == "immediate",
        ),
        reverse=True
    )

    overall_risk = infer_overall_risk(risk_events)

    summary = {
        "source_relation_event_count": len(relation_events),
        "source_crowd_dynamics_count": len(crowd_events),
        "proximity_risk_event_count": len(risk_events),
        "high_or_above_risk_count": sum(
            1 for event in risk_events
            if RISK_RANK.get(normalize_risk(event.get("risk_level")), 1) >= 3
        ),
        "critical_risk_count": sum(
            1 for event in risk_events
            if normalize_risk(event.get("risk_level")) == "critical"
        ),
        "overall_proximity_risk": overall_risk,
    }

    report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "proximity_risk_engine",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "input": {
            "relation_dynamics_project": relation_dynamics.get("project", {}),
            "relation_dynamics_summary": relation_dynamics.get("summary", {}),
        },
        "parameters": {
            "min_risk_level": min_risk_level,
        },
        "summary": summary,
        "overall_proximity_risk": overall_risk,
        "overall_risk_reason_tr": build_overall_reason(risk_events, overall_risk),
        "risk_events": risk_events,
        "operator_summary_tr": build_operator_summary(risk_events, overall_risk),
        "important_notes_tr": [
            "Yakınlık riski normalize piksel mesafesi üzerinden hesaplanmıştır; gerçek metre değildir.",
            "Bu modül kimlik tanıma, yüz tanıma veya bireysel kişi tanıma yapmaz.",
            "Risk çıktıları karar destek amaçlıdır; saha operatörü tarafından doğrulanmalıdır.",
            "Bu modül Relation Dynamics Analyzer çıktısını risk seviyesine dönüştürür; tek başına nihai olay yorumu değildir."
        ]
    }

    return report


def build_operator_summary(risk_events, overall_risk):
    if not risk_events:
        return "Yakınlık tabanlı belirgin bir risk tespit edilmedi. Operatör standart incelemeye devam edebilir."

    critical = [e for e in risk_events if normalize_risk(e.get("risk_level")) == "critical"]
    high = [e for e in risk_events if normalize_risk(e.get("risk_level")) == "high"]

    if critical:
        top = critical[0]
        return (
            f"Yakınlık analizinde kritik risk tespit edildi. "
            f"Öncelikli olay: {top.get('risk_type')} / {top.get('source_relation_event_id')}. "
            f"Operatör ilgili zaman aralığını acil incelemelidir."
        )

    if high:
        top = high[0]
        return (
            f"Yakınlık analizinde yüksek riskli kişi/araç veya nesne ilişkileri tespit edildi. "
            f"Öncelikli olay: {top.get('risk_type')} / {top.get('source_relation_event_id')}. "
            f"Operatör ilgili zaman aralığını öncelikli incelemelidir."
        )

    return (
        f"Yakınlık analizinde {len(risk_events)} adet orta/düşük seviye risk olayı bulundu. "
        f"Genel yakınlık riski {overall_risk} seviyesindedir."
    )


def build_markdown(report):
    lines = []

    lines.append("# CASIT / ÇAŞIT — Proximity Risk Report")
    lines.append("")
    lines.append("Bu rapor, Relation Dynamics Analyzer çıktısını Senaryo 3 karar destek risklerine dönüştürür.")
    lines.append("")
    lines.append("## Özet")
    lines.append("")
    s = report["summary"]
    lines.append(f"- Source relation event sayısı: `{s['source_relation_event_count']}`")
    lines.append(f"- Source crowd dynamics sayısı: `{s['source_crowd_dynamics_count']}`")
    lines.append(f"- Proximity risk event sayısı: `{s['proximity_risk_event_count']}`")
    lines.append(f"- High ve üzeri risk sayısı: `{s['high_or_above_risk_count']}`")
    lines.append(f"- Critical risk sayısı: `{s['critical_risk_count']}`")
    lines.append(f"- Genel proximity risk: `{s['overall_proximity_risk']}`")
    lines.append("")
    lines.append("## Operatör Özeti")
    lines.append("")
    lines.append(report.get("operator_summary_tr", ""))
    lines.append("")
    lines.append("## Genel Risk Gerekçesi")
    lines.append("")
    lines.append(report.get("overall_risk_reason_tr", ""))
    lines.append("")
    lines.append("## Risk Olayları")
    lines.append("")

    events = report.get("risk_events", [])
    if not events:
        lines.append("Yakınlık tabanlı risk olayı bulunmadı.")
    else:
        for event in events[:30]:
            lines.append(f"### {event.get('risk_event_id')} — {event.get('risk_type')}")
            lines.append("")
            lines.append(f"- Risk seviyesi: `{event.get('risk_level')}`")
            lines.append(f"- Öncelik: `{event.get('priority')}`")
            lines.append(f"- Kaynak relation event: `{event.get('source_relation_event_id')}`")
            lines.append(f"- Zaman: `{event.get('start_time')}` → `{event.get('end_time')}`")
            lines.append(f"- Kritik an: `{event.get('peak_time')}`")
            lines.append("")
            lines.append("**Risk gerekçesi:**")
            lines.append("")
            lines.append(event.get("risk_reason_tr", ""))
            lines.append("")
            lines.append("**Operatör aksiyonları:**")
            for action in event.get("operator_actions_tr", []):
                lines.append(f"- {action}")
            lines.append("")

    lines.append("## Sınırlılıklar")
    lines.append("")
    for note in report.get("important_notes_tr", []):
        lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--relation-dynamics", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--min-risk-level", default="medium", choices=["low", "medium", "high", "critical"])

    args = parser.parse_args()

    relation_dynamics = load_json(Path(args.relation_dynamics))
    report = build_report(relation_dynamics, args.min_risk_level)

    save_json(report, Path(args.output_json))
    save_text(build_markdown(report), Path(args.output_md))

    print("CASIT / ÇAŞIT Proximity Risk Engine")
    print("-----------------------------------")
    print("Risk event count    :", report["summary"]["proximity_risk_event_count"])
    print("High+ risk count    :", report["summary"]["high_or_above_risk_count"])
    print("Critical risk count :", report["summary"]["critical_risk_count"])
    print("Overall risk        :", report["summary"]["overall_proximity_risk"])
    print("Output JSON         :", args.output_json)
    print("Output MD           :", args.output_md)
    print("-----------------------------------")


if __name__ == "__main__":
    main()
