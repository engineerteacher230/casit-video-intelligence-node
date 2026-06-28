#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from collections import defaultdict
from pathlib import Path


SMALL_FAST_CLASSES = {"sports ball"}
PERSON_CLASSES = {"person"}
VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck", "boat", "airplane"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def class_group(class_name):
    if class_name in SMALL_FAST_CLASSES:
        return "small_fast_object"
    if class_name in PERSON_CLASSES:
        return "person_like_object"
    if class_name in VEHICLE_CLASSES:
        return "vehicle_like_object"
    return "general_object"


def thresholds(class_name):
    group = class_group(class_name)

    if group == "person_like_object":
        return {"min_observations": 5, "min_duration_frames": 5}

    if group == "vehicle_like_object":
        return {"min_observations": 3, "min_duration_frames": 3}

    if group == "small_fast_object":
        return {"min_observations": 3, "min_duration_frames": 3}

    return {"min_observations": 3, "min_duration_frames": 3}


def reliability(class_name):
    group = class_group(class_name)

    if group == "small_fast_object":
        return {
            "physical_count_supported": False,
            "confidence": "low_for_physical_count",
            "meaning": "Küçük/hızlı nesnede raw track sayısı fiziksel nesne sayısı değildir."
        }

    if group == "person_like_object":
        return {
            "physical_count_supported": True,
            "confidence": "medium",
            "meaning": "Stabil track sayısı kişi sayısına yaklaşabilir ama kesin değildir."
        }

    if group == "vehicle_like_object":
        return {
            "physical_count_supported": True,
            "confidence": "medium_high",
            "meaning": "Stabil track sayısı araç sayısına daha yakın olabilir."
        }

    return {
        "physical_count_supported": True,
        "confidence": "medium_low",
        "meaning": "Sınıfa özel doğrulama gerekir."
    }


def collect_observations(tracks):
    observations = []

    for tr in tracks:
        track_id = tr.get("track_id")
        class_name = tr.get("class_name")

        for obs in tr.get("observations", []):
            observations.append({
                "track_id": track_id,
                "class_name": class_name,
                "frame_index": obs.get("frame_index"),
                "confidence": obs.get("confidence"),
                "bbox_xyxy": obs.get("bbox_xyxy"),
                "frame_path": obs.get("frame_path")
            })

    return sorted(observations, key=lambda x: x.get("frame_index") or 0)


def build_presence_events(observations, max_gap_frames):
    if not observations:
        return []

    events = []
    current = None
    last_frame = None

    for obs in observations:
        frame = obs.get("frame_index")
        if frame is None:
            continue

        if current is None or (last_frame is not None and frame - last_frame > max_gap_frames):
            if current is not None:
                current["source_track_ids"] = sorted(list(current["source_track_ids"]))
                events.append(current)

            current = {
                "start_frame_index": frame,
                "end_frame_index": frame,
                "observation_count": 0,
                "source_track_ids": set(),
                "max_confidence": 0.0,
                "observations": []
            }

        current["end_frame_index"] = frame
        current["observation_count"] += 1
        current["source_track_ids"].add(obs.get("track_id"))
        current["max_confidence"] = max(current["max_confidence"], float(obs.get("confidence") or 0.0))
        current["observations"].append(obs)

        last_frame = frame

    if current is not None:
        current["source_track_ids"] = sorted(list(current["source_track_ids"]))
        events.append(current)

    for i, ev in enumerate(events, 1):
        ev["event_id"] = f"PRESENCE_{i:04d}"
        ev["duration_frames"] = ev["end_frame_index"] - ev["start_frame_index"] + 1
        ev["max_confidence"] = round(ev["max_confidence"], 4)

    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracked-report", default=str(Path.home() / "casit-data/outputs/json/tracked_detection_report.json"))
    parser.add_argument("--output-json", default=str(Path.home() / "casit-data/outputs/json/refined_tracking_report.json"))
    parser.add_argument("--small-object-event-gap", type=int, default=30)
    args = parser.parse_args()

    tracked_path = Path(args.tracked_report).expanduser()
    output_path = Path(args.output_json).expanduser()

    data = load_json(tracked_path)
    tracks = data.get("tracks", [])

    grouped = defaultdict(list)
    for tr in tracks:
        grouped[tr.get("class_name", "unknown")].append(tr)

    refined = {}

    for class_name, class_tracks in grouped.items():
        th = thresholds(class_name)
        rel = reliability(class_name)

        stable_tracks = []
        for tr in class_tracks:
            obs = int(tr.get("observation_count") or 0)
            dur = int(tr.get("duration_frames") or 0)

            if obs >= th["min_observations"] and dur >= th["min_duration_frames"]:
                stable_tracks.append(tr)

        observations = collect_observations(class_tracks)
        presence_events = build_presence_events(observations, args.small_object_event_gap)

        detection_count = sum(int(tr.get("observation_count") or 0) for tr in class_tracks)
        raw_track_count = len(class_tracks)
        stable_track_count = len(stable_tracks)

        if rel["physical_count_supported"]:
            estimated_physical_count = stable_track_count
        else:
            estimated_physical_count = None

        refined[class_name] = {
            "class_group": class_group(class_name),
            "detection_count": detection_count,
            "raw_track_count": raw_track_count,
            "stable_track_count": stable_track_count,
            "estimated_physical_count": estimated_physical_count,
            "physical_count_reliability": rel,
            "presence_event_count": len(presence_events),
            "presence_events": presence_events,
            "stable_track_ids": [tr.get("track_id") for tr in stable_tracks],
            "raw_track_ids": [tr.get("track_id") for tr in class_tracks]
        }

    report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "track_quality_refiner",
            "version": "0.1"
        },
        "input": {
            "tracked_detection_report_json": str(tracked_path)
        },
        "rule": {
            "detection_count": "Frame bazlı kutu sayısıdır.",
            "raw_track_count": "Ham iz sayısıdır.",
            "stable_track_count": "Daha güvenilir iz sayısıdır.",
            "small_fast_object": "Top gibi küçük/hızlı nesnelerde fiziksel sayı verilmez."
        },
        "refined_class_summary": refined
    }

    save_json(report, output_path)

    print("CASIT Track Quality Refiner")
    print("---------------------------")
    print("Input :", tracked_path)
    print("Output:", output_path)

    for class_name, item in refined.items():
        print()
        print("CLASS:", class_name)
        print("  detection_count          :", item["detection_count"])
        print("  raw_track_count          :", item["raw_track_count"])
        print("  stable_track_count       :", item["stable_track_count"])
        print("  estimated_physical_count :", item["estimated_physical_count"])
        print("  reliability              :", item["physical_count_reliability"]["confidence"])
        print("  presence_event_count     :", item["presence_event_count"])

    print("---------------------------")


if __name__ == "__main__":
    main()
