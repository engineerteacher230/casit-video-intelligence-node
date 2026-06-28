#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Domain Policy Selector

Amaç:
Dışarıdan gelen videonun ne videosu olduğunu başta bilmiyoruz.

Bu modül:
1. Qwen/VLM tarafından oluşturulan scene_prior.json dosyasını okur.
2. Sahne türünü ve domain bilgisini inceler.
3. config/domain_policies.json içinden uygun YOLO odak politikasını seçer.
4. focused_yolo_policy.json üretir.

Bu modül futbol özel değildir.
Futbol, trafik, fabrika, forklift, güvenlik, kalabalık veya bilinmeyen sahneler için
genel politika seçimi yapar.
"""

import argparse
import json
from pathlib import Path


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_text(value):
    if value is None:
        return ""
    return str(value).lower().strip().replace("-", "_").replace(" ", "_")


def unique_keep_order(items):
    seen = set()
    result = []

    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


def get_scene_prior(scene_prior_root):
    """
    scene_prior.json bazen şu yapıda olabilir:
    {
      "scene_prior": {...}
    }

    Bazense doğrudan prior objesi olabilir.
    İki yapıyı da destekliyoruz.
    """
    if isinstance(scene_prior_root, dict) and "scene_prior" in scene_prior_root:
        return scene_prior_root["scene_prior"]
    return scene_prior_root


def build_keyword_haystack(prior):
    parts = []

    for key in [
        "scene_type",
        "domain",
        "description",
        "summary",
        "dominant_activity",
        "environment",
        "risk_context"
    ]:
        value = prior.get(key)
        if value:
            parts.append(str(value))

    for key in ["scene_tags", "tags", "objects", "activities"]:
        value = prior.get(key)
        if isinstance(value, list):
            parts.extend([str(x) for x in value])

    return normalize_text(" ".join(parts))


def select_policy(prior, config):
    scene_type = normalize_text(prior.get("scene_type"))
    domain = normalize_text(prior.get("domain"))

    mapping = config.get("scene_type_mapping", {})
    policies = config.get("policies", {})
    default_policy = config.get("default_policy", "unknown_general")
    haystack = build_keyword_haystack(prior)

    # 1. En güçlü sinyal: scene_type exact mapping
    if scene_type in mapping:
        return mapping[scene_type], f"scene_type_exact:{scene_type}"

    # 2. Policy içindeki scene_type_keywords, domain'den önce gelir.
    # Örnek: scene_type=construction_site, domain=traffic olsa bile
    # construction_site_general seçilmelidir.
    for policy_name, policy in policies.items():
        for keyword in policy.get("scene_type_keywords", []):
            keyword_norm = normalize_text(keyword)
            if not keyword_norm:
                continue
            if scene_type == keyword_norm:
                return policy_name, f"policy_scene_type_exact:{keyword_norm}"

    # 3. scene_type içinde geçen policy keyword
    for policy_name, policy in policies.items():
        for keyword in policy.get("scene_type_keywords", []):
            keyword_norm = normalize_text(keyword)
            if not keyword_norm:
                continue
            if keyword_norm in scene_type or keyword_norm in haystack:
                return policy_name, f"policy_scene_type_keyword:{keyword_norm}"

    # 4. Domain exact mapping daha sonra gelir.
    if domain in mapping:
        return mapping[domain], f"domain_exact:{domain}"

    # 5. Policy domain keyword
    for policy_name, policy in policies.items():
        for keyword in policy.get("domain_keywords", []):
            keyword_norm = normalize_text(keyword)
            if not keyword_norm:
                continue
            if domain == keyword_norm or keyword_norm in haystack:
                return policy_name, f"policy_domain_keyword:{keyword_norm}"

    # 6. Eski genel keyword mapping fallback
    for rule in config.get("keyword_mapping", []):
        policy_name = rule.get("policy")
        keywords = rule.get("keywords", [])

        for keyword in keywords:
            keyword_norm = normalize_text(keyword)
            if keyword_norm and keyword_norm in haystack:
                return policy_name, f"keyword:{keyword_norm}"

    return default_policy, "default_fallback"


def build_focused_policy(scene_prior_path: Path, config_path: Path, output_path: Path):
    scene_prior_root = load_json(scene_prior_path)
    config = load_json(config_path)

    prior = get_scene_prior(scene_prior_root)

    policy_name, reason = select_policy(prior, config)

    policies = config.get("policies", {})
    if policy_name not in policies:
        raise RuntimeError(f"Policy config içinde bulunamadı: {policy_name}")

    policy = policies[policy_name]

    prior_allowed = prior.get("allowed_labels", [])
    prior_blocked = prior.get("blocked_labels", [])

    allowed_yolo_labels = unique_keep_order(policy.get("allowed_yolo_labels", []))
    raw_blocked_yolo_labels = unique_keep_order(
        policy.get("blocked_yolo_labels", []) + prior_blocked
    )

    # Kritik kural:
    # Bir sınıf aynı anda hem allowed hem blocked olamaz.
    # Domain policy allowed diyorsa allowed kazanır.
    blocked_yolo_labels = [
        label for label in raw_blocked_yolo_labels
        if label not in allowed_yolo_labels
    ]

    tracking_targets = unique_keep_order(policy.get("tracking_targets", []))
    event_questions = policy.get("event_questions", [])
    custom_classes_later = policy.get("custom_classes_later", [])

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "domain_policy_selector",
            "version": "0.1"
        },
        "input": {
            "scene_prior_json": str(scene_prior_path),
            "domain_policy_config": str(config_path)
        },
        "source_scene_prior": {
            "scene_type": prior.get("scene_type"),
            "domain": prior.get("domain"),
            "confidence": prior.get("confidence"),
            "validation_status": prior.get("validation_status"),
            "vlm_allowed_labels": prior_allowed,
            "vlm_blocked_labels": prior_blocked
        },
        "selected_policy": {
            "name": policy_name,
            "reason": reason,
            "description": policy.get("description")
        },
        "yolo_focus": {
            "allowed_labels": allowed_yolo_labels,
            "blocked_labels": blocked_yolo_labels
        },
        "tracking": {
            "enabled": True,
            "target_labels": tracking_targets,
            "note": "Detection count is not unique object count. Tracking is required for unique people/vehicle/object counts."
        },
        "event_reasoning": {
            "event_questions": event_questions,
            "custom_classes_later": custom_classes_later
        }
    }

    save_json(output, output_path)

    print("CASIT / ÇAŞIT Domain Policy Selector Report")
    print("-------------------------------------------")
    print("Scene type        :", prior.get("scene_type"))
    print("Domain            :", prior.get("domain"))
    print("Confidence        :", prior.get("confidence"))
    print("Selected policy   :", policy_name)
    print("Selection reason  :", reason)
    print("Allowed labels    :", allowed_yolo_labels)
    print("Blocked labels    :", blocked_yolo_labels)
    print("Tracking targets  :", tracking_targets)
    print("Output JSON       :", output_path)
    print("-------------------------------------------")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scene-prior",
        default=str(Path.home() / "casit-data/outputs/json/scene_prior.json")
    )

    parser.add_argument(
        "--config",
        default="config/domain_policies.json"
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/focused_yolo_policy.json")
    )

    args = parser.parse_args()

    build_focused_policy(
        scene_prior_path=Path(args.scene_prior).expanduser(),
        config_path=Path(args.config).expanduser(),
        output_path=Path(args.output_json).expanduser()
    )


if __name__ == "__main__":
    main()
