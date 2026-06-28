#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_scene_prior(root):
    if isinstance(root, dict) and "scene_prior" in root:
        return root["scene_prior"]
    return root


def build_class_evidence(class_name, item):
    rel = item.get("physical_count_reliability", {})
    supported = rel.get("physical_count_supported", False)

    evidence = {
        "class_name": class_name,
        "class_group": item.get("class_group"),
        "detection_count": item.get("detection_count"),
        "raw_track_count": item.get("raw_track_count"),
        "stable_track_count": item.get("stable_track_count"),
        "estimated_physical_count": item.get("estimated_physical_count"),
        "reliability": rel.get("confidence"),
        "interpretation": rel.get("meaning"),
        "presence_event_count": item.get("presence_event_count"),
        "evidence_type": None,
        "evidence_statement_tr": None
    }

    if supported:
        evidence["evidence_type"] = "estimated_count"
        evidence["evidence_statement_tr"] = (
            f"{class_name} sınıfı için {item.get('detection_count')} frame-bazlı tespit, "
            f"{item.get('raw_track_count')} ham track ve {item.get('stable_track_count')} stabil track bulundu. "
            f"Tahmini fiziksel sayı: {item.get('estimated_physical_count')}. "
            f"Güven düzeyi: {rel.get('confidence')}."
        )
    else:
        evidence["evidence_type"] = "presence_without_physical_count"
        evidence["evidence_statement_tr"] = (
            f"{class_name} sınıfı {item.get('detection_count')} kez tespit edildi; "
            f"ancak bu sınıf için fiziksel sayı güvenilir hesaplanamaz. "
            f"Raw track sayısı {item.get('raw_track_count')} gerçek nesne sayısı olarak yorumlanmamalıdır. "
            f"Güven düzeyi: {rel.get('confidence')}."
        )

    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-prior", default=str(Path.home() / "casit-data/outputs/json/scene_prior.json"))
    parser.add_argument("--focused-policy", default=str(Path.home() / "casit-data/outputs/json/focused_yolo_policy.json"))
    parser.add_argument("--refined-report", default=str(Path.home() / "casit-data/outputs/json/refined_tracking_report.json"))
    parser.add_argument("--output-json", default=str(Path.home() / "casit-data/outputs/json/event_evidence_report.json"))
    args = parser.parse_args()

    scene_prior_path = Path(args.scene_prior).expanduser()
    focused_policy_path = Path(args.focused_policy).expanduser()
    refined_report_path = Path(args.refined_report).expanduser()
    output_path = Path(args.output_json).expanduser()

    scene_prior_root = load_json(scene_prior_path)
    focused_policy = load_json(focused_policy_path)
    refined_report = load_json(refined_report_path)

    prior = get_scene_prior(scene_prior_root)
    refined_classes = refined_report.get("refined_class_summary", {})

    class_evidence = []
    warnings = []

    for class_name, item in refined_classes.items():
        evidence = build_class_evidence(class_name, item)
        class_evidence.append(evidence)

        if evidence["evidence_type"] == "presence_without_physical_count":
            warnings.append(
                f"{class_name}: fiziksel sayı verilmemeli; yalnızca varlık/tespit kanıtı raporlanmalı."
            )

    event_questions = (
        focused_policy
        .get("event_reasoning", {})
        .get("event_questions", [])
    )

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "event_evidence_builder",
            "version": "0.1"
        },
        "inputs": {
            "scene_prior_json": str(scene_prior_path),
            "focused_policy_json": str(focused_policy_path),
            "refined_tracking_report_json": str(refined_report_path)
        },
        "scene_context": {
            "scene_type": prior.get("scene_type"),
            "domain": prior.get("domain"),
            "confidence": prior.get("confidence"),
            "validation_status": prior.get("validation_status")
        },
        "selected_policy": focused_policy.get("selected_policy", {}),
        "event_questions": event_questions,
        "class_evidence": class_evidence,
        "warnings": warnings,
        "decision_support_summary_tr": {
            "main_result": "Video sahnesi Qwen/VLM ile bağlamsal olarak yorumlandı; YOLO bu bağlama göre odaklandı; tracking ve kalite rafinesi sonrası kanıt seviyeleri ayrıldı.",
            "count_rule": "Detection sayısı gerçek nesne sayısı değildir. Stabil track sayısı daha anlamlıdır. Küçük/hızlı nesnelerde fiziksel sayı verilmez.",
            "next_step": "Bu kanıtlar Türkçe nihai olay raporuna dönüştürülebilir."
        }
    }

    save_json(output, output_path)

    print("CASIT / ÇAŞIT Event Evidence Builder")
    print("------------------------------------")
    print("Scene type :", output["scene_context"]["scene_type"])
    print("Domain     :", output["scene_context"]["domain"])
    print("Policy     :", output["selected_policy"].get("name"))
    print("Output     :", output_path)
    print()
    print("CLASS EVIDENCE")
    print("--------------")

    for ev in class_evidence:
        print()
        print("CLASS:", ev["class_name"])
        print("  evidence_type             :", ev["evidence_type"])
        print("  detection_count           :", ev["detection_count"])
        print("  raw_track_count           :", ev["raw_track_count"])
        print("  stable_track_count        :", ev["stable_track_count"])
        print("  estimated_physical_count  :", ev["estimated_physical_count"])
        print("  reliability               :", ev["reliability"])

    print()
    print("WARNINGS")
    print("--------")
    for w in warnings:
        print("-", w)

    print("------------------------------------")


if __name__ == "__main__":
    main()
