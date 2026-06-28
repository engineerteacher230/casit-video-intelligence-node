import argparse
import json
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np


def load_json(path: str) -> dict:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, path: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def seconds_to_timestamp(seconds: float) -> str:
    total_milliseconds = int(round(seconds * 1000))

    hours = total_milliseconds // 3_600_000
    remaining = total_milliseconds % 3_600_000

    minutes = remaining // 60_000
    remaining = remaining % 60_000

    secs = remaining // 1000
    milliseconds = remaining % 1000

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def read_frame_gray(image_path: str, analysis_width: int = 320):
    image = cv2.imread(image_path)

    if image is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    height, width = gray.shape[:2]

    if analysis_width and width > analysis_width:
        scale = analysis_width / width
        new_height = int(height * scale)
        gray = cv2.resize(gray, (analysis_width, new_height), interpolation=cv2.INTER_AREA)

    return gray


def histogram_distance(gray_a, gray_b) -> float:
    hist_a = cv2.calcHist([gray_a], [0], None, [64], [0, 256])
    hist_b = cv2.calcHist([gray_b], [0], None, [64], [0, 256])

    cv2.normalize(hist_a, hist_a, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(hist_b, hist_b, 0, 1, cv2.NORM_MINMAX)

    distance = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA)

    return float(np.clip(distance, 0.0, 1.0))


def edge_change_score(gray_a, gray_b) -> float:
    edges_a = cv2.Canny(gray_a, 80, 160)
    edges_b = cv2.Canny(gray_b, 80, 160)

    diff = cv2.absdiff(edges_a, edges_b)
    score = np.mean(diff) / 255.0

    return float(np.clip(score, 0.0, 1.0))


def frame_difference_scores(prev_gray, curr_gray) -> dict:
    diff = cv2.absdiff(prev_gray, curr_gray)

    motion_score = float(np.mean(diff) / 255.0)

    changed_pixels = diff > 25
    changed_pixel_ratio = float(np.mean(changed_pixels))

    scene_change_score = histogram_distance(prev_gray, curr_gray)
    edge_score = edge_change_score(prev_gray, curr_gray)

    event_energy = (
        0.45 * motion_score +
        0.25 * changed_pixel_ratio +
        0.20 * scene_change_score +
        0.10 * edge_score
    )

    return {
        "motion_score": round(motion_score, 6),
        "changed_pixel_ratio": round(changed_pixel_ratio, 6),
        "scene_change_score": round(scene_change_score, 6),
        "edge_change_score": round(edge_score, 6),
        "event_energy": round(float(event_energy), 6)
    }


def calculate_dynamic_threshold(points: list, sensitivity: float = 1.0, min_threshold: float = 0.03) -> float:
    energies = [p["scores"]["event_energy"] for p in points if p["scores"]["event_energy"] > 0]

    if not energies:
        return min_threshold

    mean = float(np.mean(energies))
    std = float(np.std(energies))

    threshold = mean + sensitivity * std

    return round(max(threshold, min_threshold), 6)


def merge_candidate_points(candidate_points: list, video_duration: float, context_seconds: float = 5.0, max_gap_seconds: float = 1.0) -> list:
    if not candidate_points:
        return []

    candidate_points = sorted(candidate_points, key=lambda x: x["time_seconds"])

    groups = []
    current_group = [candidate_points[0]]

    for point in candidate_points[1:]:
        previous = current_group[-1]
        gap = point["time_seconds"] - previous["time_seconds"]

        if gap <= max_gap_seconds:
            current_group.append(point)
        else:
            groups.append(current_group)
            current_group = [point]

    groups.append(current_group)

    windows = []

    for idx, group in enumerate(groups, start=1):
        start_time = group[0]["time_seconds"]
        end_time = group[-1]["time_seconds"]

        peak_point = max(group, key=lambda x: x["scores"]["event_energy"])

        context_start = max(0.0, start_time - context_seconds)
        context_end = min(video_duration, end_time + context_seconds)

        windows.append({
            "candidate_event_id": f"EVT_CAND_{idx:04d}",
            "coarse_start_seconds": round(start_time, 3),
            "coarse_start_timestamp": seconds_to_timestamp(start_time),
            "coarse_end_seconds": round(end_time, 3),
            "coarse_end_timestamp": seconds_to_timestamp(end_time),
            "peak_time_seconds": round(peak_point["time_seconds"], 3),
            "peak_timestamp": peak_point["timestamp"],
            "peak_event_energy": peak_point["scores"]["event_energy"],
            "candidate_points_count": len(group),
            "context_window": {
                "start_seconds": round(context_start, 3),
                "start_timestamp": seconds_to_timestamp(context_start),
                "end_seconds": round(context_end, 3),
                "end_timestamp": seconds_to_timestamp(context_end),
                "recommended_fps": 10
            },
            "reason": "event_energy_above_dynamic_threshold"
        })

    return windows


def scan_event_energy(
    coarse_frames_report_path: str,
    output_json_path: str,
    analysis_width: int = 320,
    sensitivity: float = 1.0,
    min_threshold: float = 0.03
) -> dict:
    report = load_json(coarse_frames_report_path)

    frames = report["frames"]
    video = report["video"]

    if len(frames) < 2:
        raise RuntimeError("At least 2 frames are required for event energy scanning.")

    scan_points = []

    previous_gray = None

    for idx, frame_item in enumerate(frames):
        image_path = frame_item["image_path"]
        current_gray = read_frame_gray(image_path, analysis_width=analysis_width)

        if previous_gray is None:
            scores = {
                "motion_score": 0.0,
                "changed_pixel_ratio": 0.0,
                "scene_change_score": 0.0,
                "edge_change_score": 0.0,
                "event_energy": 0.0
            }
        else:
            scores = frame_difference_scores(previous_gray, current_gray)

        scan_points.append({
            "sample_index": frame_item["sample_index"],
            "source_frame_index": frame_item["source_frame_index"],
            "time_seconds": frame_item["time_seconds"],
            "timestamp": frame_item["timestamp"],
            "image_path": image_path,
            "scores": scores
        })

        previous_gray = current_gray

    threshold = calculate_dynamic_threshold(
        scan_points,
        sensitivity=sensitivity,
        min_threshold=min_threshold
    )

    candidate_points = []

    for point in scan_points:
        is_candidate = point["scores"]["event_energy"] >= threshold
        point["candidate_event_point"] = bool(is_candidate)

        if is_candidate:
            candidate_points.append(point)

    candidate_windows = merge_candidate_points(
        candidate_points=candidate_points,
        video_duration=video["duration_seconds"],
        context_seconds=5.0,
        max_gap_seconds=1.0
    )

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "event_energy_scanner",
            "created_at": datetime.now().isoformat(timespec="seconds")
        },
        "source_report": str(Path(coarse_frames_report_path).resolve()),
        "video": video,
        "scanner_config": {
            "analysis_width": analysis_width,
            "threshold_mode": "dynamic_mean_plus_std",
            "sensitivity": sensitivity,
            "min_threshold": min_threshold,
            "dynamic_threshold": threshold
        },
        "summary": {
            "total_scan_points": len(scan_points),
            "candidate_points": len(candidate_points),
            "candidate_windows": len(candidate_windows)
        },
        "candidate_windows": candidate_windows,
        "scan_points": scan_points
    }

    save_json(output, output_json_path)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="CASIT / ÇAŞIT event energy scanner for coarse 3 FPS frames."
    )

    parser.add_argument(
        "--frames-report",
        required=True,
        help="Path to coarse frames report JSON."
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/event_energy_report.json"),
        help="Path to output event energy JSON report."
    )

    parser.add_argument(
        "--analysis-width",
        type=int,
        default=320,
        help="Resize frames to this width for fast difference analysis."
    )

    parser.add_argument(
        "--sensitivity",
        type=float,
        default=1.0,
        help="Dynamic threshold sensitivity. Lower value detects more candidates."
    )

    parser.add_argument(
        "--min-threshold",
        type=float,
        default=0.03,
        help="Minimum event energy threshold."
    )

    args = parser.parse_args()

    output = scan_event_energy(
        coarse_frames_report_path=args.frames_report,
        output_json_path=args.output_json,
        analysis_width=args.analysis_width,
        sensitivity=args.sensitivity,
        min_threshold=args.min_threshold
    )

    print("\nCASIT / ÇAŞIT Event Energy Scanner Report")
    print("-----------------------------------------")
    print(f"Video file          : {output['video']['file_name']}")
    print(f"Total scan points   : {output['summary']['total_scan_points']}")
    print(f"Dynamic threshold   : {output['scanner_config']['dynamic_threshold']}")
    print(f"Candidate points    : {output['summary']['candidate_points']}")
    print(f"Candidate windows   : {output['summary']['candidate_windows']}")

    if output["candidate_windows"]:
        print("\nCandidate windows:")
        for window in output["candidate_windows"]:
            print(
                f"- {window['candidate_event_id']} | "
                f"{window['context_window']['start_timestamp']} → "
                f"{window['context_window']['end_timestamp']} | "
                f"peak: {window['peak_timestamp']} | "
                f"energy: {window['peak_event_energy']}"
            )
    else:
        print("\nNo candidate event windows detected.")

    print(f"\nJSON output         : {args.output_json}")
    print("-----------------------------------------\n")


if __name__ == "__main__":
    main()
