#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Domain-Aware YOLO Tracker

Amaç:
Detection sayısı ile gerçek/benzersiz nesne sayısını ayırmak.

Önemli ayrım:
- Detection count: Her frame'deki kutuların toplamı.
- Unique track count: Aynı nesnenin kareler boyunca takip edilerek tek iz olarak sayılması.

Bu modül:
1. domain_detection_report.json dosyasını okur.
2. focused_yolo_policy.json dosyasından tracking hedeflerini okur.
3. Her frame'deki bbox tespitlerini basit IoU + merkez yakınlığı ile takip eder.
4. Her nesneye track_id verir.
5. tracked_detection_report.json üretir.
6. Üzerinde track_id yazan annotated görseller üretir.

Not:
Bu ilk MVP tracker'dır. Sonraki aşamada ByteTrack / BoT-SORT ile değiştirilebilir.
"""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import cv2


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def bbox_area(box):
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter = bbox_area([ix1, iy1, ix2, iy2])
    union = bbox_area(a) + bbox_area(b) - inter

    if union <= 0:
        return 0.0

    return inter / union


def bbox_center(box):
    x1, y1, x2, y2 = box
    return [(x1 + x2) / 2.0, (y1 + y2) / 2.0]


def center_similarity(a, b, image_width=None, image_height=None):
    acx, acy = bbox_center(a)
    bcx, bcy = bbox_center(b)

    dist = math.sqrt((acx - bcx) ** 2 + (acy - bcy) ** 2)

    if image_width and image_height:
        diag = math.sqrt(image_width ** 2 + image_height ** 2)
    else:
        diag = 1500.0

    if diag <= 0:
        return 0.0

    return max(0.0, 1.0 - (dist / diag))


def make_color(track_id):
    """
    Track ID'ye göre sabit renk üretir.
    OpenCV BGR formatı kullanılır.
    """
    r = (track_id * 37) % 255
    g = (track_id * 67) % 255
    b = (track_id * 97) % 255
    return int(b), int(g), int(r)


def draw_tracked_detections(image, tracked_detections):
    for det in tracked_detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox_xyxy"]]
        track_id = det["track_id"]
        class_name = det["class_name"]
        confidence = det["confidence"]

        color = make_color(track_id)

        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

        label = f"{class_name}#{track_id} {confidence:.2f}"

        y_text = max(20, y1 - 8)
        cv2.putText(
            image,
            label,
            (x1, y_text),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA
        )

    return image


def get_tracking_targets(policy_root, detection_report):
    """
    Öncelik focused_yolo_policy.json içindeki tracking hedeflerinde.
    Eğer dosya yoksa domain_detection_report.json içindeki allowed_labels kullanılır.
    """

    if policy_root:
        tracking = policy_root.get("tracking", {})
        targets = tracking.get("target_labels", [])
        if targets:
            return targets

        yolo_focus = policy_root.get("yolo_focus", {})
        targets = yolo_focus.get("allowed_labels", [])
        if targets:
            return targets

    scene_prior = detection_report.get("scene_prior", {})
    targets = scene_prior.get("allowed_labels", [])

    return targets


def match_detection_to_track(
    det,
    active_tracks,
    assigned_track_ids,
    frame_index,
    max_missed,
    min_iou,
    min_center_similarity,
    image_width,
    image_height
):
    best_track_id = None
    best_score = -1.0
    best_iou = 0.0
    best_center = 0.0

    det_box = det["bbox_xyxy"]
    det_class = det["class_name"]

    for track_id, track in active_tracks.items():
        if track_id in assigned_track_ids:
            continue

        if track["class_name"] != det_class:
            continue

        missed = frame_index - track["last_frame_index"]
        if missed > max_missed:
            continue

        iou = bbox_iou(det_box, track["last_bbox_xyxy"])
        center_score = center_similarity(
            det_box,
            track["last_bbox_xyxy"],
            image_width=image_width,
            image_height=image_height
        )

        score = (0.70 * iou) + (0.30 * center_score)

        if iou >= min_iou or center_score >= min_center_similarity:
            if score > best_score:
                best_score = score
                best_track_id = track_id
                best_iou = iou
                best_center = center_score

    return best_track_id, best_score, best_iou, best_center


def run_tracker(
    domain_detection_report_path: Path,
    focused_policy_path: Path,
    output_json_path: Path,
    annotated_dir: Path,
    min_iou: float,
    max_missed: int,
    min_center_similarity: float
):
    detection_report = load_json(domain_detection_report_path)

    policy_root = None
    if focused_policy_path.exists():
        policy_root = load_json(focused_policy_path)

    tracking_targets = get_tracking_targets(policy_root, detection_report)
    tracking_targets = set(tracking_targets)

    frames = detection_report.get("detections", [])

    if not frames:
        raise RuntimeError("domain_detection_report.json içinde detections listesi bulunamadı.")

    annotated_dir.mkdir(parents=True, exist_ok=True)

    active_tracks = {}
    finished_tracks = {}
    next_track_id = 1

    total_input_detections = 0
    tracked_detection_count = 0
    class_detection_counts = Counter()
    unique_track_counts = Counter()

    tracked_frames = []

    print("CASIT / ÇAŞIT Domain-Aware YOLO Tracker started")
    print("-----------------------------------------------")
    print("Input report      :", domain_detection_report_path)
    print("Focused policy    :", focused_policy_path if focused_policy_path.exists() else "NOT FOUND - using detection report labels")
    print("Tracking targets  :", sorted(tracking_targets))
    print("Min IoU           :", min_iou)
    print("Max missed frames :", max_missed)
    print("-----------------------------------------------")

    for frame_order, frame_item in enumerate(frames, 1):
        frame_index = frame_item.get("frame_index", frame_order)
        frame_path = Path(frame_item.get("frame_path", "")).expanduser()
        detections = frame_item.get("detections", [])

        image = None
        image_height = None
        image_width = None

        if frame_path.exists():
            image = cv2.imread(str(frame_path))
            if image is not None:
                image_height, image_width = image.shape[:2]

        frame_tracked_detections = []
        assigned_track_ids = set()

        for det in detections:
            class_name = det.get("class_name")

            if tracking_targets and class_name not in tracking_targets:
                continue

            total_input_detections += 1
            class_detection_counts[class_name] += 1

            det_box = det.get("bbox_xyxy")
            if not det_box:
                continue

            track_id, score, iou, center_score = match_detection_to_track(
                det=det,
                active_tracks=active_tracks,
                assigned_track_ids=assigned_track_ids,
                frame_index=frame_index,
                max_missed=max_missed,
                min_iou=min_iou,
                min_center_similarity=min_center_similarity,
                image_width=image_width,
                image_height=image_height
            )

            if track_id is None:
                track_id = next_track_id
                next_track_id += 1

                active_tracks[track_id] = {
                    "track_id": track_id,
                    "class_name": class_name,
                    "first_frame_index": frame_index,
                    "last_frame_index": frame_index,
                    "first_frame_path": str(frame_path),
                    "last_frame_path": str(frame_path),
                    "last_bbox_xyxy": det_box,
                    "observation_count": 0,
                    "max_confidence": 0.0,
                    "observations": []
                }

                unique_track_counts[class_name] += 1

            track = active_tracks[track_id]
            confidence = float(det.get("confidence", 0.0))

            track["last_frame_index"] = frame_index
            track["last_frame_path"] = str(frame_path)
            track["last_bbox_xyxy"] = det_box
            track["observation_count"] += 1
            track["max_confidence"] = max(track["max_confidence"], confidence)

            observation = {
                "frame_index": frame_index,
                "frame_path": str(frame_path),
                "class_name": class_name,
                "confidence": round(confidence, 4),
                "bbox_xyxy": det_box,
                "match_score": round(score, 4) if score is not None else None,
                "match_iou": round(iou, 4) if iou is not None else None,
                "match_center_similarity": round(center_score, 4) if center_score is not None else None
            }

            track["observations"].append(observation)
            assigned_track_ids.add(track_id)
            tracked_detection_count += 1

            tracked_det = {
                "track_id": track_id,
                "class_name": class_name,
                "confidence": round(confidence, 4),
                "bbox_xyxy": det_box
            }

            frame_tracked_detections.append(tracked_det)

        if image is not None:
            image = draw_tracked_detections(image, frame_tracked_detections)
            annotated_path = annotated_dir / frame_path.name
            cv2.imwrite(str(annotated_path), image)
        else:
            annotated_path = None

        tracked_frames.append({
            "frame_index": frame_index,
            "frame_path": str(frame_path),
            "annotated_path": str(annotated_path) if annotated_path else None,
            "tracked_detections": frame_tracked_detections,
            "tracked_detection_count": len(frame_tracked_detections)
        })

        # Uzun süre görünmeyen track'leri finished listesine taşı
        stale_track_ids = []
        for track_id, track in active_tracks.items():
            if frame_index - track["last_frame_index"] > max_missed:
                stale_track_ids.append(track_id)

        for track_id in stale_track_ids:
            finished_tracks[track_id] = active_tracks.pop(track_id)

        if frame_order % 25 == 0 or frame_order == len(frames):
            print(f"Tracked {frame_order}/{len(frames)} frames")

    # Kalan aktif track'leri de rapora ekle
    for track_id, track in active_tracks.items():
        finished_tracks[track_id] = track

    tracks = []
    for track_id in sorted(finished_tracks.keys()):
        track = finished_tracks[track_id]
        duration_frames = track["last_frame_index"] - track["first_frame_index"] + 1

        tracks.append({
            "track_id": track["track_id"],
            "class_name": track["class_name"],
            "first_frame_index": track["first_frame_index"],
            "last_frame_index": track["last_frame_index"],
            "duration_frames": duration_frames,
            "observation_count": track["observation_count"],
            "max_confidence": round(track["max_confidence"], 4),
            "first_frame_path": track["first_frame_path"],
            "last_frame_path": track["last_frame_path"],
            "observations": track["observations"]
        })

    tracks_by_class = defaultdict(list)
    for track in tracks:
        tracks_by_class[track["class_name"]].append(track["track_id"])

    report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "domain_aware_yolo_tracker",
            "version": "0.1"
        },
        "input": {
            "domain_detection_report_json": str(domain_detection_report_path),
            "focused_yolo_policy_json": str(focused_policy_path)
        },
        "tracking_parameters": {
            "min_iou": min_iou,
            "max_missed": max_missed,
            "min_center_similarity": min_center_similarity,
            "tracking_targets": sorted(tracking_targets)
        },
        "summary": {
            "total_frames": len(frames),
            "total_frame_detections": total_input_detections,
            "tracked_detection_count": tracked_detection_count,
            "class_detection_counts": dict(class_detection_counts),
            "unique_track_counts": dict(unique_track_counts),
            "total_unique_tracks": len(tracks),
            "tracks_by_class": {k: v for k, v in tracks_by_class.items()}
        },
        "important_note": {
            "detection_count_meaning": "Frame-based detections. The same object can appear many times across frames.",
            "unique_track_count_meaning": "Estimated unique objects tracked across frames. This is closer to real object/person count."
        },
        "tracks": tracks,
        "frames": tracked_frames
    }

    save_json(report, output_json_path)

    print("\nCASIT / ÇAŞIT Tracking Report")
    print("-----------------------------")
    print("Total frames             :", report["summary"]["total_frames"])
    print("Total frame detections   :", report["summary"]["total_frame_detections"])
    print("Tracked detections       :", report["summary"]["tracked_detection_count"])
    print("Class detection counts   :", report["summary"]["class_detection_counts"])
    print("Unique track counts      :", report["summary"]["unique_track_counts"])
    print("Total unique tracks      :", report["summary"]["total_unique_tracks"])
    print("JSON output              :", output_json_path)
    print("Annotated output dir     :", annotated_dir)
    print("-----------------------------")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--domain-detection-report",
        default=str(Path.home() / "casit-data/outputs/json/domain_detection_report.json")
    )

    parser.add_argument(
        "--focused-policy",
        default=str(Path.home() / "casit-data/outputs/json/focused_yolo_policy.json")
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/tracked_detection_report.json")
    )

    parser.add_argument(
        "--annotated-dir",
        default=str(Path.home() / "casit-data/outputs/annotated/insan/domain_aware_yolo_tracking")
    )

    parser.add_argument("--min-iou", type=float, default=0.20)
    parser.add_argument("--max-missed", type=int, default=5)
    parser.add_argument("--min-center-similarity", type=float, default=0.65)

    args = parser.parse_args()

    run_tracker(
        domain_detection_report_path=Path(args.domain_detection_report).expanduser(),
        focused_policy_path=Path(args.focused_policy).expanduser(),
        output_json_path=Path(args.output_json).expanduser(),
        annotated_dir=Path(args.annotated_dir).expanduser(),
        min_iou=args.min_iou,
        max_missed=args.max_missed,
        min_center_similarity=args.min_center_similarity
    )


if __name__ == "__main__":
    main()
