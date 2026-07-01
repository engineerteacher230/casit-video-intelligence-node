#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Scenario 3 Output Validator

Amaç:
Standardized Scenario 3 JSON çıktısının TEKNOFEST Senaryo 3 karar destek
beklentilerini karşılayıp karşılamadığını doğrulamak.

Bu modül kalite puanı değil, teslim/uygunluk doğrulaması üretir.
"""

import argparse
import json
import re
from pathlib import Path
from datetime import datetime


VALID_RISKS = {"low", "medium", "high", "critical"}
VALID_PRIORITIES = {"low", "normal", "high", "immediate"}

TIME_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}$")


def load_json(path):
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(data, path):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_text(text, path):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def is_nonempty_text(value, min_len=1):
    return isinstance(value, str) and len(value.strip()) >= min_len


def is_valid_time(value):
    return isinstance(value, str) and bool(TIME_PATTERN.match(value.strip()))


def add_check(checks, name, passed, severity, detail):
    checks.append({
        "check": name,
        "passed": bool(passed),
        "severity": severity,
        "detail_tr": detail,
    })


def validate_top_level(data):
    checks = []

    required_top_keys = [
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

    for key in required_top_keys:
        add_check(
            checks,
            f"top_level_{key}",
            key in data,
            "critical",
            f"Top-level `{key}` alanı {'mevcut' if key in data else 'eksik'}."
        )

    add_check(
        checks,
        "summary_tr_nonempty",
        is_nonempty_text(data.get("summary_tr"), min_len=30),
        "critical",
        "Türkçe özet en az 30 karakter olmalıdır."
    )

    add_check(
        checks,
        "decision_support_tr_nonempty",
        is_nonempty_text(data.get("decision_support_tr"), min_len=30),
        "critical",
        "Karar destek metni en az 30 karakter olmalıdır."
    )

    add_check(
        checks,
        "limitations_tr_nonempty",
        is_nonempty_text(data.get("limitations_tr"), min_len=30),
        "major",
        "Sınırlılıklar metni bulunmalıdır."
    )

    add_check(
        checks,
        "overall_risk_valid",
        data.get("overall_risk") in VALID_RISKS,
        "critical",
        f"overall_risk low/medium/high/critical değerlerinden biri olmalıdır. Mevcut: {data.get('overall_risk')}"
    )

    add_check(
        checks,
        "events_is_nonempty_list",
        isinstance(data.get("events"), list) and len(data.get("events", [])) > 0,
        "critical",
        "events alanı boş olmayan liste olmalıdır."
    )

    schema = data.get("schema", {})
    add_check(
        checks,
        "schema_name_present",
        is_nonempty_text(schema.get("name")),
        "major",
        "Şema adı belirtilmelidir."
    )

    add_check(
        checks,
        "schema_version_present",
        is_nonempty_text(schema.get("version")),
        "major",
        "Şema versiyonu belirtilmelidir."
    )

    return checks


def validate_event(event, index):
    checks = []

    prefix = f"event_{index}"

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

    for key in required_event_keys:
        add_check(
            checks,
            f"{prefix}_{key}_exists",
            key in event,
            "critical",
            f"{event.get('event_id', prefix)} için `{key}` alanı {'mevcut' if key in event else 'eksik'}."
        )

    add_check(
        checks,
        f"{prefix}_event_id_nonempty",
        is_nonempty_text(event.get("event_id")),
        "critical",
        "event_id boş olmamalıdır."
    )

    add_check(
        checks,
        f"{prefix}_event_type_nonempty",
        is_nonempty_text(event.get("event_type")),
        "major",
        "event_type boş olmamalıdır."
    )

    add_check(
        checks,
        f"{prefix}_event_name_tr_nonempty",
        is_nonempty_text(event.get("event_name_tr"), min_len=5),
        "major",
        "Türkçe olay adı bulunmalıdır."
    )

    for time_key in ["start_time", "end_time", "peak_time"]:
        add_check(
            checks,
            f"{prefix}_{time_key}_valid",
            is_valid_time(event.get(time_key)),
            "critical",
            f"{time_key} HH:MM:SS.mmm formatında olmalıdır. Mevcut: {event.get(time_key)}"
        )

    add_check(
        checks,
        f"{prefix}_risk_level_valid",
        event.get("risk_level") in VALID_RISKS,
        "critical",
        f"risk_level geçerli olmalıdır. Mevcut: {event.get('risk_level')}"
    )

    add_check(
        checks,
        f"{prefix}_priority_valid",
        event.get("priority") in VALID_PRIORITIES,
        "major",
        f"priority geçerli olmalıdır. Mevcut: {event.get('priority')}"
    )

    add_check(
        checks,
        f"{prefix}_risk_reason_nonempty",
        is_nonempty_text(event.get("risk_reason_tr"), min_len=30),
        "major",
        "Risk gerekçesi en az 30 karakter olmalıdır."
    )

    evidence = event.get("evidence", [])
    add_check(
        checks,
        f"{prefix}_evidence_nonempty",
        isinstance(evidence, list) and len(evidence) > 0,
        "major",
        "Her olayda en az bir kanıt bulunmalıdır."
    )

    actions = event.get("operator_actions_tr", [])
    add_check(
        checks,
        f"{prefix}_actions_nonempty",
        isinstance(actions, list) and len(actions) > 0,
        "critical",
        "Her olayda en az bir operatör aksiyonu bulunmalıdır."
    )

    add_check(
        checks,
        f"{prefix}_actions_minimum_for_high_risk",
        not (
            event.get("risk_level") in {"high", "critical"}
            and isinstance(actions, list)
            and len(actions) < 3
        ),
        "major",
        "High/critical olaylarda en az 3 operatör aksiyonu beklenir."
    )

    add_check(
        checks,
        f"{prefix}_critical_priority_alignment",
        not (
            event.get("risk_level") == "critical"
            and event.get("priority") != "immediate"
        ),
        "critical",
        "Critical olaylarda priority immediate olmalıdır."
    )

    add_check(
        checks,
        f"{prefix}_limitations_nonempty",
        is_nonempty_text(event.get("limitations_tr"), min_len=20),
        "minor",
        "Olay sınırlılığı belirtilmelidir."
    )

    return checks


def compute_status(checks):
    critical_failures = [
        check for check in checks
        if not check["passed"] and check["severity"] == "critical"
    ]

    major_failures = [
        check for check in checks
        if not check["passed"] and check["severity"] == "major"
    ]

    minor_failures = [
        check for check in checks
        if not check["passed"] and check["severity"] == "minor"
    ]

    if critical_failures:
        return "fail"

    if major_failures:
        return "conditional_pass"

    return "pass" if not minor_failures else "pass_with_minor_notes"


def build_validation_report(data):
    checks = []

    checks.extend(validate_top_level(data))

    events = data.get("events", [])
    if isinstance(events, list):
        for idx, event in enumerate(events, start=1):
            checks.extend(validate_event(event, idx))

    passed_count = sum(1 for check in checks if check["passed"])
    failed_count = len(checks) - passed_count

    critical_failed_count = sum(
        1 for check in checks
        if not check["passed"] and check["severity"] == "critical"
    )

    major_failed_count = sum(
        1 for check in checks
        if not check["passed"] and check["severity"] == "major"
    )

    minor_failed_count = sum(
        1 for check in checks
        if not check["passed"] and check["severity"] == "minor"
    )

    validation_status = compute_status(checks)

    return {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "scenario_3_output_validator",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "target": {
            "schema_name": data.get("schema", {}).get("name"),
            "schema_version": data.get("schema", {}).get("version"),
            "overall_risk": data.get("overall_risk"),
            "event_count": len(data.get("events", [])) if isinstance(data.get("events"), list) else 0,
        },
        "validation": {
            "status": validation_status,
            "is_submission_ready": validation_status in {"pass", "pass_with_minor_notes"},
            "passed_count": passed_count,
            "failed_count": failed_count,
            "critical_failed_count": critical_failed_count,
            "major_failed_count": major_failed_count,
            "minor_failed_count": minor_failed_count,
        },
        "checks": checks,
        "recommendations_tr": build_recommendations(validation_status, checks),
    }


def build_recommendations(status, checks):
    failed = [check for check in checks if not check["passed"]]

    if status == "pass":
        return [
            "Standart Scenario 3 çıktısı temel teslim doğrulamasını geçmiştir.",
            "Demo ve rapor aşamasında bu JSON ana karar destek çıktısı olarak kullanılabilir."
        ]

    if status == "pass_with_minor_notes":
        return [
            "Çıktı kullanılabilir durumdadır; küçük notlar dokümantasyon aşamasında iyileştirilebilir."
        ]

    if status == "conditional_pass":
        return [
            "Çıktıda kritik hata yoktur; ancak major seviyede eksikler vardır.",
            "Jüri gösteriminden önce major eksikler giderilmelidir.",
            *[check["detail_tr"] for check in failed[:5]]
        ]

    return [
        "Çıktı şu an teslim için hazır değildir.",
        "Critical seviyedeki doğrulama hataları giderilmelidir.",
        *[check["detail_tr"] for check in failed[:8]]
    ]


def build_markdown(report):
    v = report.get("validation", {})
    target = report.get("target", {})

    lines = []

    lines.append("# CASIT / ÇAŞIT — Scenario 3 Output Validator")
    lines.append("")
    lines.append("Bu rapor standart Scenario 3 JSON çıktısının teslim uygunluğunu doğrular.")
    lines.append("")

    lines.append("## Sonuç")
    lines.append("")
    lines.append(f"- Durum: `{v.get('status')}`")
    lines.append(f"- Teslime hazır mı?: `{v.get('is_submission_ready')}`")
    lines.append(f"- Genel risk: `{target.get('overall_risk')}`")
    lines.append(f"- Olay sayısı: `{target.get('event_count')}`")
    lines.append(f"- Başarılı kontrol: `{v.get('passed_count')}`")
    lines.append(f"- Hatalı kontrol: `{v.get('failed_count')}`")
    lines.append(f"- Critical hata: `{v.get('critical_failed_count')}`")
    lines.append(f"- Major hata: `{v.get('major_failed_count')}`")
    lines.append(f"- Minor hata: `{v.get('minor_failed_count')}`")
    lines.append("")

    lines.append("## Öneriler")
    lines.append("")
    for rec in report.get("recommendations_tr", []):
        lines.append(f"- {rec}")
    lines.append("")

    lines.append("## Başarısız Kontroller")
    lines.append("")

    failed = [check for check in report.get("checks", []) if not check.get("passed")]

    if not failed:
        lines.append("Başarısız kontrol bulunmamaktadır.")
    else:
        for check in failed:
            lines.append(f"- `{check.get('severity')}` / `{check.get('check')}`: {check.get('detail_tr')}")

    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--standardized-output", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)

    args = parser.parse_args()

    data = load_json(args.standardized_output)
    report = build_validation_report(data)

    save_json(report, args.output_json)
    save_text(build_markdown(report), args.output_md)

    v = report.get("validation", {})

    print("CASIT / ÇAŞIT Scenario 3 Output Validator")
    print("-----------------------------------------")
    print("Validation status :", v.get("status"))
    print("Submission ready  :", v.get("is_submission_ready"))
    print("Passed checks     :", v.get("passed_count"))
    print("Failed checks     :", v.get("failed_count"))
    print("Critical failures :", v.get("critical_failed_count"))
    print("Major failures    :", v.get("major_failed_count"))
    print("Minor failures    :", v.get("minor_failed_count"))
    print("Output JSON       :", args.output_json)
    print("Output MD         :", args.output_md)
    print("-----------------------------------------")


if __name__ == "__main__":
    main()
