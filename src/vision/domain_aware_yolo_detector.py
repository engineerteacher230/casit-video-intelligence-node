#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Domain-Aware YOLO Detector

Bu modül:
1. scene_prior.json dosyasını okur.
2. VLM'in izin verdiği YOLO sınıflarını alır.
3. detail_frames_report.json içindeki detay karelerini bulur.
4. YOLO'yu sadece bağlama uygun sınıflarla çalıştırır.
5. Domain-aware detection raporu üretir.

Örnek:
Futbol sahnesinde izinli sınıflar:
- person
- sports ball

Bloklanan sınıflar:
- sheep
- horse
- baseball bat
- baseball glove
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def collect_image_paths_from_json(obj):
    """
    JSON içindeki tüm görsel dosya yollarını esnek şekilde toplar.
    detail_frames_report.json formatı değişse bile çalışması için recursive yazıldı.
    """
    found = []

    if isinstance(obj, dict):
        for value in obj.values():
            found.extend(collect_image_paths_from_json(value))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_image_paths_from_json(item))

    elif isinstance(obj, str):
        p = Path(obj).expanduser()
        if p.suffix.lower() in IMAGE_EXTENSIONS:
            found.append(p)

    return found


def dedupe_existing_paths(paths):
    clean = []
    seen = set()

    for p in paths:
        p = p.expanduser()
        key = str(p)

        if key in seen:
            continue

        if p.exists():
            clean.append(p)
            seen.add(key)

    return clean


def get_scene_prior(scene_prior_root):
    if "scene_prior" in scene_prior_root:
        return scene_prior_root["scene_prior"]
    return scene_prior_root


def get_allowed_class_ids(model, allowed_labels):
    """
    YOLO model.names içinden allowed label isimlerine karşılık gelen class id listesini çıkarır.
    """
    allowed = set(allowed_labels)
    class_ids = []

    for class_id, class_name in model.names.items():
        if class_name in allowed:
            class_ids.append(int(class_id))

    return class_ids


def run_domain_aware_detection(
    scene_prior_path: Path,
    detail_report_path: Path,
    model_path: str,
    output_json_path: Path,
    annotated_dir: Path,
    conf: float,
    imgsz: int,
    device: str,
    focused_policy_path: Path = None,
):
    scene_prior_root = load_json(scene_prior_path)
    detail_report = load_json(detail_report_path)

    prior = get_scene_prior(scene_prior_root)

    allowed_labels = prior.get("allowed_labels", ["person"])
    blocked_labels = prior.get("blocked_labels", [])

    # Eğer focused_yolo_policy.json verilmişse son karar mercii odur.
    if focused_policy_path is not None and focused_policy_path.exists():
        focused_policy = load_json(focused_policy_path)
        yolo_focus = focused_policy.get("yolo_focus", {})
        allowed_labels = yolo_focus.get("allowed_labels", allowed_labels)
        blocked_labels = yolo_focus.get("blocked_labels", blocked_labels)

    # Kritik kural:
    # Aynı sınıf hem allowed hem blocked olamaz.
    # allowed kazanır.
    blocked_labels = [
        label for label in blocked_labels
        if label not in allowed_labels
    ]

    model = YOLO(model_path)

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    allowed_class_ids = get_allowed_class_ids(model, allowed_labels)

    if not allowed_class_ids:
        raise RuntimeError(
            f"Allowed labels YOLO model içinde bulunamadı: {allowed_labels}"
        )

    frame_paths = collect_image_paths_from_json(detail_report)
    frame_paths = dedupe_existing_paths(frame_paths)

    if not frame_paths:
        raise RuntimeError(
            "detail_frames_report.json içinde geçerli detay frame yolu bulunamadı."
        )

    annotated_dir.mkdir(parents=True, exist_ok=True)

    detections = []
    class_counts = Counter()
    frames_with_detections = 0
    blocked_detection_count = 0

    print("CASIT Domain-Aware YOLO started")
    print("--------------------------------")
    print("Scene type     :", prior.get("scene_type"))
    print("Domain         :", prior.get("domain"))
    print("Allowed labels :", allowed_labels)
    print("Blocked labels :", blocked_labels)
    print("YOLO class ids :", allowed_class_ids)
    print("Frame count    :", len(frame_paths))
    print("Device         :", device)
    print("--------------------------------")

    for index, frame_path in enumerate(frame_paths, 1):
        result_list = model.predict(
            source=str(frame_path),
            classes=allowed_class_ids,
            conf=conf,
            imgsz=imgsz,
            device=device,
            verbose=False
        )

        result = result_list[0]
        frame_detections = []

        if result.boxes is not None and len(result.boxes) > 0:
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                class_name = model.names[class_id]
                score = float(box.conf[0].item())
                xyxy = [float(x) for x in box.xyxy[0].tolist()]

                if class_name in blocked_labels:
                    blocked_detection_count += 1
                    continue

                if class_name not in allowed_labels:
                    continue

                det = {
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": round(score, 4),
                    "bbox_xyxy": [round(x, 2) for x in xyxy]
                }

                frame_detections.append(det)
                class_counts[class_name] += 1

        if frame_detections:
            frames_with_detections += 1

        annotated_image = result.plot()
        annotated_path = annotated_dir / frame_path.name
        cv2.imwrite(str(annotated_path), annotated_image)

        detections.append({
            "frame_index": index,
            "frame_path": str(frame_path),
            "annotated_path": str(annotated_path),
            "detections": frame_detections,
            "detection_count": len(frame_detections)
        })

        if index % 25 == 0 or index == len(frame_paths):
            print(f"Processed {index}/{len(frame_paths)} frames")

    report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "domain_aware_yolo_detector"
        },
        "scene_prior": {
            "scene_type": prior.get("scene_type"),
            "domain": prior.get("domain"),
            "confidence": prior.get("confidence"),
            "validation_status": prior.get("validation_status"),
            "allowed_labels": allowed_labels,
            "blocked_labels": blocked_labels
        },
        "yolo": {
            "model_path": model_path,
            "device": device,
            "confidence_threshold": conf,
            "image_size": imgsz,
            "allowed_class_ids": allowed_class_ids
        },
        "summary": {
            "total_frames": len(frame_paths),
            "frames_with_detections": frames_with_detections,
            "total_detections": sum(class_counts.values()),
            "class_counts": dict(class_counts),
            "blocked_detection_count": blocked_detection_count
        },
        "detections": detections
    }

    save_json(report, output_json_path)

    print("\nCASIT Domain-Aware YOLO Report")
    print("------------------------------")
    print("Total frames              :", report["summary"]["total_frames"])
    print("Frames with detections    :", report["summary"]["frames_with_detections"])
    print("Total detections          :", report["summary"]["total_detections"])
    print("Class counts              :", report["summary"]["class_counts"])
    print("Blocked detection count   :", report["summary"]["blocked_detection_count"])
    print("JSON output               :", output_json_path)
    print("Annotated output dir      :", annotated_dir)
    print("------------------------------\n")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scene-prior",
        default=str(Path.home() / "casit-data/outputs/json/scene_prior.json")
    )

    parser.add_argument(
        "--detail-report",
        default=str(Path.home() / "casit-data/outputs/json/detail_frames_report.json")
    )

    parser.add_argument(
        "--model",
        default="yolo11n.pt"
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/domain_detection_report.json")
    )

    parser.add_argument(
        "--annotated-dir",
        default=str(Path.home() / "casit-data/outputs/annotated/insan/domain_aware_yolo_detail")
    )

    parser.add_argument(
        "--focused-policy",
        default=str(Path.home() / "casit-data/outputs/json/focused_yolo_policy.json")
    )

    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="auto")

    args = parser.parse_args()

    run_domain_aware_detection(
        scene_prior_path=Path(args.scene_prior).expanduser(),
        detail_report_path=Path(args.detail_report).expanduser(),
        model_path=args.model,
        output_json_path=Path(args.output_json).expanduser(),
        annotated_dir=Path(args.annotated_dir).expanduser(),
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device,
        focused_policy_path=Path(args.focused_policy).expanduser(),
    )


if __name__ == "__main__":
    main()
