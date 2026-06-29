#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Scenario 3 Quality Reviewer

Amaç:
scenario_3_output.json dosyasını jüriye gösterilebilirlik açısından kontrol etmek.

Kontrol edilen başlıklar:
- summary_tr
- events
- event_name_tr
- risk_level
- evidence
- operator_actions_tr
- decision_support_tr
- limitations_tr
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}


def load_json(path: Path):
    path = Path(path).expanduser()
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


def score_text_field(value, min_len=40):
    if not isinstance(value, str) or not value.strip():
        return 0, "Alan boş veya metin değil."
    if len(value.strip()) < min_len:
        return 50, f"Alan var ama kısa görünüyor: {len(value.strip())} karakter."
    return 100, "Alan yeterli görünüyor."


def score_list_field(value, min_items=1):
    if not isinstance(value, list):
        return 0, "Alan liste tipinde değil."
    if len(value) < min_items:
        return 0, "Liste boş."
    return 100, f"Liste dolu: {len(value)} öğe."


def review_event(event, index):
    checks = []

    event_id = event.get("event_id")
    event_name = event.get("event_name_tr")
    risk_level = event.get("risk_level")
    evidence = event.get("evidence")
    actions = event.get("operator_actions_tr")
    start_time = event.get("start_time")
    end_time = event.get("end_time")
    peak_time = event.get("peak_time")

    score, note = score_text_field(str(event_id) if event_id else "", min_len=3)
    checks.append({
        "field": "event_id",
        "score": score,
        "status": "pass" if score == 100 else "fail",
        "note": note
    })

    score, note = score_text_field(event_name, min_len=12)
    checks.append({
        "field": "event_name_tr",
        "score": score,
        "status": "pass" if score == 100 else "warn" if score >= 50 else "fail",
        "note": note
    })

    if risk_level in VALID_RISK_LEVELS:
        checks.append({
            "field": "risk_level",
            "score": 100,
            "status": "pass",
            "note": f"Geçerli risk seviyesi: {risk_level}"
        })
    else:
        checks.append({
            "field": "risk_level",
            "score": 0,
            "status": "fail",
            "note": f"Geçersiz risk seviyesi: {risk_level}"
        })

    for field_name, value in [
        ("start_time", start_time),
        ("end_time", end_time),
        ("peak_time", peak_time),
    ]:
        score, note = score_text_field(str(value) if value else "", min_len=5)
        checks.append({
            "field": field_name,
            "score": score,
            "status": "pass" if score == 100 else "fail",
            "note": note
        })

    score, note = score_list_field(evidence, min_items=1)
    checks.append({
        "field": "evidence",
        "score": score,
        "status": "pass" if score == 100 else "fail",
        "note": note
    })

    score, note = score_list_field(actions, min_items=1)
    checks.append({
        "field": "operator_actions_tr",
        "score": score,
        "status": "pass" if score == 100 else "fail",
        "note": note
    })

    event_score = round(sum(item["score"] for item in checks) / max(len(checks), 1), 2)

    if event_score >= 90:
        grade = "excellent"
    elif event_score >= 75:
        grade = "good"
    elif event_score >= 60:
        grade = "needs_improvement"
    else:
        grade = "weak"

    return {
        "event_index": index,
        "event_id": event_id,
        "event_name_tr": event_name,
        "event_score": event_score,
        "event_grade": grade,
        "checks": checks
    }


def build_review(data):
    checks = []

    score, note = score_text_field(data.get("summary_tr"), min_len=60)
    checks.append({
        "field": "summary_tr",
        "score": score,
        "status": "pass" if score == 100 else "warn" if score >= 50 else "fail",
        "note": note
    })

    score, note = score_text_field(data.get("decision_support_tr"), min_len=60)
    checks.append({
        "field": "decision_support_tr",
        "score": score,
        "status": "pass" if score == 100 else "warn" if score >= 50 else "fail",
        "note": note
    })

    score, note = score_text_field(data.get("limitations_tr"), min_len=80)
    checks.append({
        "field": "limitations_tr",
        "score": score,
        "status": "pass" if score == 100 else "warn" if score >= 50 else "fail",
        "note": note
    })

    overall_risk = data.get("overall_risk")
    if overall_risk in VALID_RISK_LEVELS:
        checks.append({
            "field": "overall_risk",
            "score": 100,
            "status": "pass",
            "note": f"Geçerli genel risk seviyesi: {overall_risk}"
        })
    else:
        checks.append({
            "field": "overall_risk",
            "score": 0,
            "status": "fail",
            "note": f"Geçersiz genel risk seviyesi: {overall_risk}"
        })

    events = data.get("events")
    score, note = score_list_field(events, min_items=1)
    checks.append({
        "field": "events",
        "score": score,
        "status": "pass" if score == 100 else "fail",
        "note": note
    })

    event_reviews = []
    if isinstance(events, list):
        for idx, event in enumerate(events, start=1):
            if isinstance(event, dict):
                event_reviews.append(review_event(event, idx))

    top_score_items = checks + [
        {
            "field": f"event_{item['event_index']}",
            "score": item["event_score"],
            "status": "pass" if item["event_score"] >= 75 else "warn",
            "note": item["event_grade"]
        }
        for item in event_reviews
    ]

    total_score = round(
        sum(item["score"] for item in top_score_items) / max(len(top_score_items), 1),
        2
    )

    if total_score >= 90:
        quality_grade = "excellent"
        readiness = "Jüri gösterimi için güçlü aday."
    elif total_score >= 75:
        quality_grade = "good"
        readiness = "Jüri gösterimi için kullanılabilir; küçük iyileştirmeler önerilir."
    elif total_score >= 60:
        quality_grade = "needs_improvement"
        readiness = "Çalışıyor ancak yarışma kalitesi için iyileştirme gerekir."
    else:
        quality_grade = "weak"
        readiness = "Jüri gösterimi için henüz zayıf."

    recommendations = []

    if not isinstance(events, list) or not events:
        recommendations.append("En az bir zaman damgalı olay üretilmelidir.")

    for item in checks:
        if item["status"] != "pass":
            recommendations.append(f"{item['field']} alanı iyileştirilmeli: {item['note']}")

    for ev_review in event_reviews:
        if ev_review["event_score"] < 90:
            recommendations.append(
                f"{ev_review['event_id']} olayı için açıklama, kanıt veya aksiyon kalitesi artırılmalı."
            )

    if not recommendations:
        recommendations.append("Mevcut çıktı temel jüri incelemesi için yeterli görünüyor.")

    review = {
        "project": "CASIT / ÇAŞIT",
        "module": "scenario_3_quality_reviewer",
        "version": "0.4.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "quality_score": total_score,
        "quality_grade": quality_grade,
        "readiness_assessment_tr": readiness,
        "top_level_checks": checks,
        "event_reviews": event_reviews,
        "recommendations_tr": recommendations
    }

    return review


def build_markdown(review):
    lines = []

    lines.append("# CASIT / ÇAŞIT — v0.4 Çıktı Kalite Kontrol Raporu")
    lines.append("")
    lines.append(f"**Kalite puanı:** `{review['quality_score']}/100`")
    lines.append(f"**Kalite sınıfı:** `{review['quality_grade']}`")
    lines.append("")
    lines.append("## Hazırlık Değerlendirmesi")
    lines.append("")
    lines.append(review["readiness_assessment_tr"])
    lines.append("")
    lines.append("## Üst Seviye Kontroller")
    lines.append("")
    lines.append("| Alan | Durum | Puan | Not |")
    lines.append("|---|---:|---:|---|")
    for item in review["top_level_checks"]:
        lines.append(
            f"| `{item['field']}` | `{item['status']}` | `{item['score']}` | {item['note']} |"
        )

    lines.append("")
    lines.append("## Olay Kontrolleri")
    lines.append("")

    if not review["event_reviews"]:
        lines.append("Olay bulunamadı.")
    else:
        for ev in review["event_reviews"]:
            lines.append(f"### {ev['event_id']} — {ev.get('event_name_tr')}")
            lines.append("")
            lines.append(f"- Olay puanı: `{ev['event_score']}/100`")
            lines.append(f"- Sınıf: `{ev['event_grade']}`")
            lines.append("")
            lines.append("| Alan | Durum | Puan | Not |")
            lines.append("|---|---:|---:|---|")
            for check in ev["checks"]:
                lines.append(
                    f"| `{check['field']}` | `{check['status']}` | `{check['score']}` | {check['note']} |"
                )
            lines.append("")

    lines.append("## Öneriler")
    lines.append("")
    for rec in review["recommendations_tr"]:
        lines.append(f"- {rec}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario-output", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    data = load_json(Path(args.scenario_output))
    review = build_review(data)

    save_json(review, Path(args.output_json))
    save_text(build_markdown(review), Path(args.output_md))

    print("CASIT / ÇAŞIT Scenario 3 Quality Reviewer")
    print("-----------------------------------------")
    print("Quality score :", review["quality_score"])
    print("Quality grade :", review["quality_grade"])
    print("Assessment    :", review["readiness_assessment_tr"])
    print("Output JSON   :", args.output_json)
    print("Output MD     :", args.output_md)
    print("-----------------------------------------")


if __name__ == "__main__":
    main()
