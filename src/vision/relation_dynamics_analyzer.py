#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Relation Dynamics Analyzer

Amaç:
Tracked detection çıktısından nesneler arası ilişkisel hareketleri çıkarmak.

Bu modül şunları hesaplar:
- person ↔ vehicle yaklaşma / uzaklaşma / yakın temas
- vehicle ↔ vehicle yaklaşma / uzaklaşma / yakın temas
- kalabalık yoğunlaşma / dağılma eğilimi

Önemli not:
Bu modül piksel tabanlı normalize mesafe kullanır.
Bu değer gerçek metre değildir; perspektif ve kamera açısı nedeniyle operatör doğrulaması gerekir.
"""

import argparse
import json
import math
import re
import statistics
from pathlib import Path
from datetime import datetime


VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "train"}
PERSON_CLASSES = {"person"}

RISK_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


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


def bbox_center(bbox):
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    x1, y1, x2, y2 = [float(v) for v in bbox]
    return {
        "x": (x1 + x2) / 2.0,
        "y": (y1 + y2) / 2.0,
        "w": max(0.0, x2 - x1),
        "h": max(0.0, y2 - y1),
        "area": max(0.0, x2 - x1) * max(0.0, y2 - y1),
    }


def parse_time_from_path(path_text):
    """
    Örnek:
    CTX_0001_detail_000000_src_00000017_t_00-00-00-667.jpg
    """
    if not path_text:
        return None, None

    m = re.search(r"_t_(\d{2})-(\d{2})-(\d{2})-(\d{3})", str(path_text))
    if not m:
        return None, None

    hh, mm, ss, ms = [int(x) for x in m.groups()]
    seconds = hh * 3600 + mm * 60 + ss + ms / 1000.0
    text = f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"
    return text, seconds


def seconds_to_timestamp(seconds):
    if seconds is None:
        return None
    seconds = float(seconds)
    hh = int(seconds // 3600)
    seconds -= hh * 3600
    mm = int(seconds // 60)
    seconds -= mm * 60
    ss = int(seconds)
    ms = int(round((seconds - ss) * 1000))
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"


def median_or_none(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return statistics.median(values)


def mean_or_none(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def normalize_distance(p1, p2, image_width, image_height):
    diag = math.sqrt(image_width ** 2 + image_height ** 2)
    if diag <= 0:
        diag = 1.0
    dx = p1["x"] - p2["x"]
    dy = p1["y"] - p2["y"]
    return math.sqrt(dx * dx + dy * dy) / diag


def classify_pair(class_a, class_b, include_person_person=False):
    a_person = class_a in PERSON_CLASSES
    b_person = class_b in PERSON_CLASSES
    a_vehicle = class_a in VEHICLE_CLASSES
    b_vehicle = class_b in VEHICLE_CLASSES

    if (a_person and b_vehicle) or (b_person and a_vehicle):
        return "person_vehicle"

    if a_vehicle and b_vehicle:
        return "vehicle_vehicle"

    if include_person_person and a_person and b_person:
        return "person_person"

    return None


def risk_for_relation(base_type, trend, min_distance, approach_delta):
    """
    min_distance normalize piksel mesafesidir.
    0.00 çok yakın, 1.00 ekran köşegenine yakın uzaklık anlamına gelir.
    """

    if base_type == "person_vehicle":
        if trend == "approaching":
            if min_distance <= 0.07:
                return "critical"
            if min_distance <= 0.12:
                return "high"
            if min_distance <= 0.22:
                return "medium"
            if approach_delta >= 0.08:
                return "medium"
            return "low"

        if trend == "close_proximity":
            if min_distance <= 0.07:
                return "high"
            if min_distance <= 0.12:
                return "medium"
            return "low"

        if trend == "separating":
            if min_distance <= 0.07:
                return "medium"
            return "low"

    if base_type == "vehicle_vehicle":
        if trend == "approaching":
            if min_distance <= 0.08:
                return "high"
            if min_distance <= 0.16:
                return "medium"
            return "low"

        if trend == "close_proximity":
            if min_distance <= 0.08:
                return "medium"
            return "low"

    if base_type == "person_person":
        if trend == "approaching" and min_distance <= 0.08:
            return "medium"
        return "low"

    return "low"


def relation_type_name(base_type, trend):
    if base_type == "person_vehicle":
        if trend == "approaching":
            return "person_vehicle_approach"
        if trend == "separating":
            return "person_vehicle_separation"
        if trend == "close_proximity":
            return "person_vehicle_close_proximity"

    if base_type == "vehicle_vehicle":
        if trend == "approaching":
            return "vehicle_vehicle_approach"
        if trend == "separating":
            return "vehicle_vehicle_separation"
        if trend == "close_proximity":
            return "vehicle_vehicle_close_proximity"

    if base_type == "person_person":
        if trend == "approaching":
            return "person_person_approach"
        if trend == "separating":
            return "person_person_separation"
        if trend == "close_proximity":
            return "person_person_close_proximity"

    return f"{base_type}_{trend}"


def relation_reason_tr(base_type, trend, risk_level, class_a, track_a, class_b, track_b, start_distance, end_distance, min_distance):
    a = f"{class_a}#{track_a}"
    b = f"{class_b}#{track_b}"

    if trend == "approaching":
        motion = "arasındaki normalize mesafe zaman içinde azalmıştır"
    elif trend == "separating":
        motion = "arasındaki normalize mesafe zaman içinde artmıştır"
    else:
        motion = "arasındaki mesafe düşük seviyede kalmıştır"

    if base_type == "person_vehicle":
        subject = "Kişi-araç ilişkisi"
    elif base_type == "vehicle_vehicle":
        subject = "Araç-araç ilişkisi"
    elif base_type == "person_person":
        subject = "Kişi-kişi ilişkisi"
    else:
        subject = "Nesne ilişkisi"

    return (
        f"{subject}: {a} ile {b} {motion}. "
        f"Başlangıç mesafesi {start_distance:.4f}, bitiş mesafesi {end_distance:.4f}, "
        f"minimum mesafe {min_distance:.4f}. Risk seviyesi {risk_level} olarak değerlendirilmiştir."
    )


def build_track_observations(tracked_report, image_width, image_height):
    tracks_out = []

    for track in tracked_report.get("tracks", []):
        track_id = track.get("track_id")
        class_name = track.get("class_name")
        observations = track.get("observations", [])

        obs_by_frame = {}

        for obs in observations:
            bbox = obs.get("bbox_xyxy")
            center = bbox_center(bbox)
            if center is None:
                continue

            frame_index = obs.get("frame_index")
            frame_path = obs.get("frame_path")
            timestamp_text, timestamp_seconds = parse_time_from_path(frame_path)

            if timestamp_seconds is None and frame_index is not None:
                # Detail extractor çoğunlukla 10fps üretir. Kesin zaman yoksa güvenli fallback.
                timestamp_seconds = float(frame_index) / 10.0
                timestamp_text = seconds_to_timestamp(timestamp_seconds)

            obs_by_frame[int(frame_index)] = {
                "frame_index": int(frame_index),
                "timestamp": timestamp_text,
                "timestamp_seconds": timestamp_seconds,
                "bbox_xyxy": bbox,
                "center": center,
                "confidence": obs.get("confidence"),
            }

        if obs_by_frame:
            tracks_out.append({
                "track_id": track_id,
                "class_name": class_name,
                "first_frame_index": track.get("first_frame_index"),
                "last_frame_index": track.get("last_frame_index"),
                "duration_frames": track.get("duration_frames"),
                "observation_count": track.get("observation_count"),
                "max_confidence": track.get("max_confidence"),
                "observations_by_frame": obs_by_frame,
            })

    return tracks_out


def analyze_pair(track_a, track_b, image_width, image_height, min_common_frames, approach_delta_threshold, separation_delta_threshold, near_threshold):
    frames_a = set(track_a["observations_by_frame"].keys())
    frames_b = set(track_b["observations_by_frame"].keys())
    common_frames = sorted(frames_a & frames_b)

    if len(common_frames) < min_common_frames:
        return None

    samples = []

    for frame_index in common_frames:
        obs_a = track_a["observations_by_frame"][frame_index]
        obs_b = track_b["observations_by_frame"][frame_index]

        dist = normalize_distance(
            obs_a["center"],
            obs_b["center"],
            image_width,
            image_height,
        )

        samples.append({
            "frame_index": frame_index,
            "timestamp": obs_a.get("timestamp") or obs_b.get("timestamp"),
            "timestamp_seconds": obs_a.get("timestamp_seconds") or obs_b.get("timestamp_seconds"),
            "normalized_distance": dist,
        })

    if len(samples) < min_common_frames:
        return None

    distances = [s["normalized_distance"] for s in samples]

    segment_size = max(3, int(len(samples) * 0.2))
    first_segment = distances[:segment_size]
    last_segment = distances[-segment_size:]

    start_distance = median_or_none(first_segment)
    end_distance = median_or_none(last_segment)
    min_distance = min(distances)
    min_sample = min(samples, key=lambda s: s["normalized_distance"])

    if start_distance is None or end_distance is None:
        return None

    delta = end_distance - start_distance
    approach_delta = max(0.0, start_distance - end_distance)
    separation_delta = max(0.0, end_distance - start_distance)

    if delta <= -abs(approach_delta_threshold):
        trend = "approaching"
    elif delta >= abs(separation_delta_threshold):
        trend = "separating"
    elif min_distance <= near_threshold:
        trend = "close_proximity"
    else:
        trend = "stable"

    if trend == "stable":
        return None

    base_type = classify_pair(track_a["class_name"], track_b["class_name"])
    if base_type is None:
        return None

    start_time = samples[0].get("timestamp")
    end_time = samples[-1].get("timestamp")
    peak_time = min_sample.get("timestamp")

    duration_seconds = None
    if samples[0].get("timestamp_seconds") is not None and samples[-1].get("timestamp_seconds") is not None:
        duration_seconds = max(0.0, samples[-1]["timestamp_seconds"] - samples[0]["timestamp_seconds"])

    risk_level = risk_for_relation(
        base_type=base_type,
        trend=trend,
        min_distance=min_distance,
        approach_delta=approach_delta,
    )

    relation_score = round(
        (approach_delta * 2.0)
        + (separation_delta * 0.6)
        + max(0.0, near_threshold - min_distance) * 3.0
        + RISK_RANK.get(risk_level, 1) * 0.1,
        4
    )

    relation_type = relation_type_name(base_type, trend)

    return {
        "relation_event_id": None,
        "relation_type": relation_type,
        "base_relation_type": base_type,
        "trend": trend,
        "risk_level": risk_level,
        "track_a": {
            "track_id": track_a["track_id"],
            "class_name": track_a["class_name"],
        },
        "track_b": {
            "track_id": track_b["track_id"],
            "class_name": track_b["class_name"],
        },
        "start_time": start_time,
        "end_time": end_time,
        "peak_time": peak_time,
        "duration_seconds": round(duration_seconds, 3) if duration_seconds is not None else None,
        "common_frame_count": len(samples),
        "start_normalized_distance": round(start_distance, 5),
        "end_normalized_distance": round(end_distance, 5),
        "min_normalized_distance": round(min_distance, 5),
        "approach_delta": round(approach_delta, 5),
        "separation_delta": round(separation_delta, 5),
        "relation_score": relation_score,
        "reason_tr": relation_reason_tr(
            base_type=base_type,
            trend=trend,
            risk_level=risk_level,
            class_a=track_a["class_name"],
            track_a=track_a["track_id"],
            class_b=track_b["class_name"],
            track_b=track_b["track_id"],
            start_distance=start_distance,
            end_distance=end_distance,
            min_distance=min_distance,
        ),
        "samples_preview": samples[:3] + samples[-3:] if len(samples) > 6 else samples,
    }


def analyze_relations(tracks, image_width, image_height, min_common_frames, approach_delta_threshold, separation_delta_threshold, near_threshold, max_relations):
    events = []

    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            a = tracks[i]
            b = tracks[j]

            base_type = classify_pair(a["class_name"], b["class_name"])
            if base_type is None:
                continue

            event = analyze_pair(
                track_a=a,
                track_b=b,
                image_width=image_width,
                image_height=image_height,
                min_common_frames=min_common_frames,
                approach_delta_threshold=approach_delta_threshold,
                separation_delta_threshold=separation_delta_threshold,
                near_threshold=near_threshold,
            )

            if event is not None:
                events.append(event)

    events.sort(
        key=lambda e: (
            RISK_RANK.get(e["risk_level"], 1),
            e["relation_score"],
            -e["min_normalized_distance"]
        ),
        reverse=True
    )

    events = events[:max_relations]

    for idx, event in enumerate(events, start=1):
        event["relation_event_id"] = f"REL_EVT_{idx:04d}"

    return events


def median_person_count_by_segment(person_counts):
    if not person_counts:
        return None, None

    values = sorted(person_counts.items(), key=lambda x: x[0])
    counts = [c for _, c in values]
    seg = max(3, int(len(counts) * 0.2))

    early = median_or_none(counts[:seg])
    late = median_or_none(counts[-seg:])

    return early, late


def analyze_crowd_dynamics(tracked_report, image_width, image_height):
    frames = tracked_report.get("frames", [])
    person_counts = {}
    nearest_distances_by_frame = {}

    for frame in frames:
        frame_index = frame.get("frame_index")
        detections = frame.get("tracked_detections", [])

        person_centers = []

        for det in detections:
            if det.get("class_name") != "person":
                continue

            center = bbox_center(det.get("bbox_xyxy"))
            if center is None:
                continue

            person_centers.append(center)

        person_counts[int(frame_index)] = len(person_centers)

        nearest_distances = []
        for i in range(len(person_centers)):
            nearest = None
            for j in range(len(person_centers)):
                if i == j:
                    continue
                d = normalize_distance(person_centers[i], person_centers[j], image_width, image_height)
                if nearest is None or d < nearest:
                    nearest = d
            if nearest is not None:
                nearest_distances.append(nearest)

        if nearest_distances:
            nearest_distances_by_frame[int(frame_index)] = mean_or_none(nearest_distances)

    if not person_counts:
        return []

    early_count, late_count = median_person_count_by_segment(person_counts)

    nn_values = sorted(nearest_distances_by_frame.items(), key=lambda x: x[0])
    if nn_values:
        nn_distances = [v for _, v in nn_values]
        seg = max(3, int(len(nn_distances) * 0.2))
        early_nn = median_or_none(nn_distances[:seg])
        late_nn = median_or_none(nn_distances[-seg:])
    else:
        early_nn = None
        late_nn = None

    max_person_count = max(person_counts.values()) if person_counts else 0
    avg_person_count = mean_or_none(list(person_counts.values()))

    crowd_events = []

    count_delta = None
    if early_count is not None and late_count is not None:
        count_delta = late_count - early_count

    nn_delta = None
    if early_nn is not None and late_nn is not None:
        nn_delta = late_nn - early_nn

    trend = "stable"
    risk_level = "low"
    reason_parts = []

    if count_delta is not None:
        if count_delta >= 5:
            trend = "crowd_growing"
            risk_level = "medium"
            reason_parts.append(f"Kalabalık sayısı erken bölümde yaklaşık {early_count}, geç bölümde yaklaşık {late_count}.")
        elif count_delta <= -5:
            trend = "crowd_dispersing"
            risk_level = "low"
            reason_parts.append(f"Kalabalık sayısı erken bölümde yaklaşık {early_count}, geç bölümde yaklaşık {late_count}.")

    if nn_delta is not None:
        if nn_delta <= -0.02 and max_person_count >= 8:
            trend = "crowd_concentrating"
            risk_level = "medium" if risk_level == "low" else risk_level
            reason_parts.append(
                f"Kişiler arası ortalama yakın komşu mesafesi azalmış görünüyor: {early_nn:.4f} → {late_nn:.4f}."
            )
        elif nn_delta >= 0.02 and max_person_count >= 8:
            if trend == "stable":
                trend = "crowd_spreading"
            reason_parts.append(
                f"Kişiler arası ortalama yakın komşu mesafesi artmış görünüyor: {early_nn:.4f} → {late_nn:.4f}."
            )

    if max_person_count >= 20 and trend in {"crowd_growing", "crowd_concentrating"}:
        risk_level = "high"

    if trend != "stable":
        crowd_events.append({
            "crowd_event_id": "CROWD_DYN_0001",
            "trend": trend,
            "risk_level": risk_level,
            "max_person_count_in_frame": max_person_count,
            "average_person_count_per_frame": round(avg_person_count, 3) if avg_person_count is not None else None,
            "early_median_person_count": early_count,
            "late_median_person_count": late_count,
            "early_nearest_neighbor_distance": round(early_nn, 5) if early_nn is not None else None,
            "late_nearest_neighbor_distance": round(late_nn, 5) if late_nn is not None else None,
            "reason_tr": " ".join(reason_parts) if reason_parts else "Kalabalık hareketinde zamansal değişim gözlemlenmiştir.",
            "important_note_tr": "Kalabalık dinamiği frame bazlı YOLO/tracking gözlemlerinden çıkarılmıştır; gerçek kişi sayısı olarak kesin kabul edilmemelidir."
        })

    return crowd_events


def build_report(tracked_report, image_width, image_height, args):
    tracks = build_track_observations(
        tracked_report=tracked_report,
        image_width=image_width,
        image_height=image_height,
    )

    relation_events = analyze_relations(
        tracks=tracks,
        image_width=image_width,
        image_height=image_height,
        min_common_frames=args.min_common_frames,
        approach_delta_threshold=args.approach_delta_threshold,
        separation_delta_threshold=args.separation_delta_threshold,
        near_threshold=args.near_threshold,
        max_relations=args.max_relations,
    )

    crowd_dynamics = analyze_crowd_dynamics(
        tracked_report=tracked_report,
        image_width=image_width,
        image_height=image_height,
    )

    high_or_above = [
        e for e in relation_events
        if RISK_RANK.get(e["risk_level"], 1) >= RISK_RANK["high"]
    ]

    medium_or_above = [
        e for e in relation_events
        if RISK_RANK.get(e["risk_level"], 1) >= RISK_RANK["medium"]
    ]

    summary = {
        "total_tracks_in_input": len(tracked_report.get("tracks", [])),
        "usable_tracks": len(tracks),
        "relation_event_count": len(relation_events),
        "high_or_above_relation_event_count": len(high_or_above),
        "medium_or_above_relation_event_count": len(medium_or_above),
        "crowd_dynamics_event_count": len(crowd_dynamics),
    }

    report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "relation_dynamics_analyzer",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "input": {
            "tracked_report_source": tracked_report.get("input", {}),
            "tracking_summary": tracked_report.get("summary", {}),
        },
        "parameters": {
            "image_width": image_width,
            "image_height": image_height,
            "min_common_frames": args.min_common_frames,
            "approach_delta_threshold": args.approach_delta_threshold,
            "separation_delta_threshold": args.separation_delta_threshold,
            "near_threshold": args.near_threshold,
            "max_relations": args.max_relations,
        },
        "summary": summary,
        "relation_events": relation_events,
        "crowd_dynamics": crowd_dynamics,
        "important_notes_tr": [
            "Normalize mesafe piksel tabanlıdır; gerçek metre değildir.",
            "Kamera perspektifi, lens açısı ve nesne ölçeği nedeniyle sonuçlar operatör doğrulaması gerektirir.",
            "Bu modül kimlik tanıma yapmaz; yalnızca track_id seviyesinde nesne hareket ilişkisi hesaplar.",
            "Relation event, semantik olayın yerine geçmez; risk kanıtı olarak kullanılmalıdır."
        ]
    }

    return report


def build_markdown(report):
    lines = []

    lines.append("# CASIT / ÇAŞIT — Relation Dynamics Report")
    lines.append("")
    lines.append("Bu rapor, tracked detection çıktısından nesnelerin birbirine yaklaşma / uzaklaşma / yakın temas ilişkilerini çıkarır.")
    lines.append("")
    lines.append("## Özet")
    lines.append("")
    s = report["summary"]
    lines.append(f"- Girdi track sayısı: `{s['total_tracks_in_input']}`")
    lines.append(f"- Kullanılabilir track sayısı: `{s['usable_tracks']}`")
    lines.append(f"- Relation event sayısı: `{s['relation_event_count']}`")
    lines.append(f"- High ve üzeri relation event: `{s['high_or_above_relation_event_count']}`")
    lines.append(f"- Medium ve üzeri relation event: `{s['medium_or_above_relation_event_count']}`")
    lines.append(f"- Crowd dynamics event sayısı: `{s['crowd_dynamics_event_count']}`")
    lines.append("")

    lines.append("## En Önemli Relation Eventler")
    lines.append("")

    events = report.get("relation_events", [])
    if not events:
        lines.append("Relation event bulunamadı.")
    else:
        for ev in events[:20]:
            a = ev["track_a"]
            b = ev["track_b"]
            lines.append(f"### {ev['relation_event_id']} — {ev['relation_type']}")
            lines.append("")
            lines.append(f"- Risk: `{ev['risk_level']}`")
            lines.append(f"- Trend: `{ev['trend']}`")
            lines.append(f"- Track A: `{a['class_name']}#{a['track_id']}`")
            lines.append(f"- Track B: `{b['class_name']}#{b['track_id']}`")
            lines.append(f"- Zaman: `{ev['start_time']}` → `{ev['end_time']}`")
            lines.append(f"- En yakın an: `{ev['peak_time']}`")
            lines.append(f"- Başlangıç mesafesi: `{ev['start_normalized_distance']}`")
            lines.append(f"- Bitiş mesafesi: `{ev['end_normalized_distance']}`")
            lines.append(f"- Minimum mesafe: `{ev['min_normalized_distance']}`")
            lines.append(f"- Gerekçe: {ev['reason_tr']}")
            lines.append("")

    lines.append("## Crowd Dynamics")
    lines.append("")

    crowd = report.get("crowd_dynamics", [])
    if not crowd:
        lines.append("Belirgin kalabalık yoğunlaşma/dağılma olayı bulunamadı.")
    else:
        for ev in crowd:
            lines.append(f"### {ev['crowd_event_id']} — {ev['trend']}")
            lines.append("")
            lines.append(f"- Risk: `{ev['risk_level']}`")
            lines.append(f"- Maksimum frame içi kişi sayısı: `{ev['max_person_count_in_frame']}`")
            lines.append(f"- Ortalama frame içi kişi sayısı: `{ev['average_person_count_per_frame']}`")
            lines.append(f"- Gerekçe: {ev['reason_tr']}")
            lines.append("")

    lines.append("## Sınırlılıklar")
    lines.append("")
    for note in report.get("important_notes_tr", []):
        lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--tracked-report", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)

    parser.add_argument("--image-width", type=float, default=1280.0)
    parser.add_argument("--image-height", type=float, default=720.0)
    parser.add_argument("--min-common-frames", type=int, default=6)
    parser.add_argument("--approach-delta-threshold", type=float, default=0.03)
    parser.add_argument("--separation-delta-threshold", type=float, default=0.03)
    parser.add_argument("--near-threshold", type=float, default=0.12)
    parser.add_argument("--max-relations", type=int, default=80)

    args = parser.parse_args()

    tracked_report = load_json(Path(args.tracked_report))

    report = build_report(
        tracked_report=tracked_report,
        image_width=args.image_width,
        image_height=args.image_height,
        args=args,
    )

    save_json(report, Path(args.output_json))
    save_text(build_markdown(report), Path(args.output_md))

    print("CASIT / ÇAŞIT Relation Dynamics Analyzer")
    print("----------------------------------------")
    print("Usable tracks              :", report["summary"]["usable_tracks"])
    print("Relation event count       :", report["summary"]["relation_event_count"])
    print("High+ relation event count :", report["summary"]["high_or_above_relation_event_count"])
    print("Crowd dynamics count       :", report["summary"]["crowd_dynamics_event_count"])
    print("Output JSON                :", args.output_json)
    print("Output MD                  :", args.output_md)
    print("----------------------------------------")


if __name__ == "__main__":
    main()
