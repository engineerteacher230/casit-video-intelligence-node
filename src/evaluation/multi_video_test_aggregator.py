#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Multi-video Test Aggregator

Amaç:
Multi-video test koşularından gelen case_results.jsonl dosyasını okuyarak
toplu Scenario 3 / KPI raporu üretmek.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


def load_json(path, default=None):
    if default is None:
        default = {}
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


def read_jsonl(path):
    p = Path(path).expanduser()
    if not p.exists():
        return []

    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def safe_get(data, path, default=None):
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def get_manifest_case_map(manifest):
    return {
        case.get("case_id"): case
        for case in manifest.get("test_cases", [])
    }


def summarize_case(result, manifest_case):
    run_dir = Path(result.get("run_dir", "")).expanduser() if result.get("run_dir") else None

    benchmark = {}
    validation = {}
    standardized = {}
    scene_prior = {}

    if run_dir and run_dir.exists():
        benchmark = load_json(run_dir / "json" / "benchmark_kpi_report.json")
        validation = load_json(run_dir / "json" / "scenario_3_output_validation.json")
        standardized = load_json(run_dir / "json" / "standardized_scenario_3_output.json")
        scene_prior = load_json(run_dir / "json" / "scene_prior.json")

    scene_core = scene_prior.get("scene_prior", {})

    events = standardized.get("events", [])
    risk_counts = safe_get(benchmark, ["scenario_3_metrics", "risk_counts"], {})

    return {
        "case_id": result.get("case_id"),
        "file_name": result.get("file_name"),
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "duration_seconds": result.get("duration_seconds"),
        "run_dir": result.get("run_dir"),
        "log_path": result.get("log_path"),
        "expected_profile": manifest_case.get("expected_profile", {}) if manifest_case else {},
        "observed_scene": {
            "scene_type": scene_core.get("scene_type"),
            "domain": scene_core.get("domain"),
            "confidence": scene_core.get("confidence"),
        },
        "scenario_3": {
            "overall_risk": standardized.get("overall_risk"),
            "event_count": len(events),
            "risk_counts": risk_counts,
            "submission_ready": safe_get(validation, ["validation", "is_submission_ready"]),
            "validation_status": safe_get(validation, ["validation", "status"]),
            "validation_failed_count": safe_get(validation, ["validation", "failed_count"]),
        },
        "kpi": {
            "internal_readiness_score": safe_get(benchmark, ["internal_readiness_kpi", "score"]),
            "earned_points": safe_get(benchmark, ["internal_readiness_kpi", "earned_points"]),
            "total_points": safe_get(benchmark, ["internal_readiness_kpi", "total_points"]),
        },
        "reasoning": {
            "semantic_event_count": safe_get(benchmark, ["reasoning_metrics", "semantic_event_count"]),
            "proximity_risk_event_count": safe_get(benchmark, ["reasoning_metrics", "proximity_risk_event_count"]),
            "vlm_reasoned_event_count": safe_get(benchmark, ["reasoning_metrics", "vlm_reasoned_event_count"]),
            "vlm_parse_error_count": safe_get(benchmark, ["reasoning_metrics", "vlm_parse_error_count"]),
        },
        "error": result.get("error"),
    }


def build_report(manifest, case_results):
    case_map = get_manifest_case_map(manifest)
    cases = [
        summarize_case(result, case_map.get(result.get("case_id"), {}))
        for result in case_results
    ]

    success_cases = [c for c in cases if c.get("status") == "success"]
    failed_cases = [c for c in cases if c.get("status") == "failed"]
    dry_cases = [c for c in cases if c.get("status") == "dry_run"]

    ready_cases = [
        c for c in success_cases
        if c.get("scenario_3", {}).get("submission_ready") is True
    ]

    validation_pass_cases = [
        c for c in success_cases
        if c.get("scenario_3", {}).get("validation_status") == "pass"
    ]

    kpi_values = [
        c.get("kpi", {}).get("internal_readiness_score")
        for c in success_cases
        if isinstance(c.get("kpi", {}).get("internal_readiness_score"), (int, float))
    ]

    avg_kpi = round(sum(kpi_values) / len(kpi_values), 2) if kpi_values else None

    criteria = manifest.get("success_criteria", {})
    minimum_cases = criteria.get("minimum_cases", 0)
    required_ready = criteria.get("required_submission_ready_cases", 0)
    min_kpi = criteria.get("minimum_internal_kpi_for_demo", 0)
    max_vlm_parse = criteria.get("maximum_vlm_parse_error_per_case", 0)

    vlm_parse_ok = all(
        (c.get("reasoning", {}).get("vlm_parse_error_count") or 0) <= max_vlm_parse
        for c in success_cases
    )

    aggregate_pass = (
        len(cases) >= minimum_cases
        and len(ready_cases) >= required_ready
        and (avg_kpi is not None and avg_kpi >= min_kpi)
        and vlm_parse_ok
        and len(failed_cases) == 0
        and len(dry_cases) == 0
    )

    return {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "multi_video_test_aggregator",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "manifest_type": manifest.get("manifest_type"),
        "summary": {
            "total_cases": len(cases),
            "success_cases": len(success_cases),
            "failed_cases": len(failed_cases),
            "dry_run_cases": len(dry_cases),
            "submission_ready_cases": len(ready_cases),
            "validation_pass_cases": len(validation_pass_cases),
            "average_internal_kpi": avg_kpi,
            "aggregate_pass": aggregate_pass,
        },
        "success_criteria": criteria,
        "case_summaries": cases,
        "recommendations_tr": build_recommendations(
            aggregate_pass=aggregate_pass,
            failed_cases=failed_cases,
            dry_cases=dry_cases,
            avg_kpi=avg_kpi,
            criteria=criteria,
        ),
        "important_note_tr": (
            "Bu rapor çok videolu regresyon/KPI raporudur. Etiketli ground-truth olmadığı için "
            "mAP, precision, recall gibi doğruluk metrikleri üretmez."
        )
    }


def build_recommendations(aggregate_pass, failed_cases, dry_cases, avg_kpi, criteria):
    recs = []

    if dry_cases:
        recs.append("Dry-run çalışılmıştır; gerçek çok videolu test için dry-run olmadan çalıştırılmalıdır.")

    if failed_cases:
        recs.append("Başarısız video koşuları vardır; ilgili log dosyaları incelenmelidir.")

    if avg_kpi is not None and avg_kpi < criteria.get("minimum_internal_kpi_for_demo", 0):
        recs.append("Ortalama KPI demo eşiğinin altındadır; eksik modül çıktıları iyileştirilmelidir.")

    if aggregate_pass:
        recs.append("Çok videolu test kriterleri geçilmiştir; demo ve rapor aşamasında kullanılabilir.")
    else:
        recs.append("Çok videolu test henüz tam geçilmiş sayılmaz; tüm case'ler gerçek pipeline ile çalıştırılmalıdır.")

    return recs


def build_markdown(report):
    s = report.get("summary", {})

    lines = []
    lines.append("# CASIT / ÇAŞIT — Multi-video Test Report")
    lines.append("")
    lines.append(report.get("important_note_tr", ""))
    lines.append("")

    lines.append("## Özet")
    lines.append("")
    lines.append(f"- Toplam case: `{s.get('total_cases')}`")
    lines.append(f"- Başarılı case: `{s.get('success_cases')}`")
    lines.append(f"- Başarısız case: `{s.get('failed_cases')}`")
    lines.append(f"- Dry-run case: `{s.get('dry_run_cases')}`")
    lines.append(f"- Submission ready case: `{s.get('submission_ready_cases')}`")
    lines.append(f"- Validation pass case: `{s.get('validation_pass_cases')}`")
    lines.append(f"- Ortalama internal KPI: `{s.get('average_internal_kpi')}`")
    lines.append(f"- Aggregate pass: `{s.get('aggregate_pass')}`")
    lines.append("")

    lines.append("## Case Sonuçları")
    lines.append("")

    for case in report.get("case_summaries", []):
        lines.append(f"### {case.get('case_id')} — {case.get('file_name')}")
        lines.append("")
        lines.append(f"- Durum: `{case.get('status')}`")
        lines.append(f"- Run dir: `{case.get('run_dir')}`")
        lines.append(f"- Beklenen sahne: `{case.get('expected_profile', {}).get('scene_hint')}`")
        lines.append(f"- Gözlenen sahne: `{case.get('observed_scene')}`")
        lines.append(f"- Overall risk: `{case.get('scenario_3', {}).get('overall_risk')}`")
        lines.append(f"- Event count: `{case.get('scenario_3', {}).get('event_count')}`")
        lines.append(f"- Submission ready: `{case.get('scenario_3', {}).get('submission_ready')}`")
        lines.append(f"- Validation status: `{case.get('scenario_3', {}).get('validation_status')}`")
        lines.append(f"- KPI: `{case.get('kpi', {}).get('internal_readiness_score')}`")
        lines.append(f"- VLM parse error: `{case.get('reasoning', {}).get('vlm_parse_error_count')}`")
        if case.get("error"):
            lines.append(f"- Hata: `{case.get('error')}`")
        lines.append("")

    lines.append("## Öneriler")
    lines.append("")
    for rec in report.get("recommendations_tr", []):
        lines.append(f"- {rec}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--case-results", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)

    args = parser.parse_args()

    manifest = load_json(args.manifest)
    case_results = read_jsonl(args.case_results)
    report = build_report(manifest, case_results)

    save_json(report, args.output_json)
    save_text(build_markdown(report), args.output_md)

    s = report.get("summary", {})

    print("CASIT / ÇAŞIT Multi-video Test Aggregator")
    print("-----------------------------------------")
    print("Total cases     :", s.get("total_cases"))
    print("Success cases   :", s.get("success_cases"))
    print("Failed cases    :", s.get("failed_cases"))
    print("Dry-run cases   :", s.get("dry_run_cases"))
    print("Average KPI     :", s.get("average_internal_kpi"))
    print("Aggregate pass  :", s.get("aggregate_pass"))
    print("Output JSON     :", args.output_json)
    print("Output MD       :", args.output_md)
    print("-----------------------------------------")


if __name__ == "__main__":
    main()
