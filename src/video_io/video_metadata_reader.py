import argparse
import json
import math
from pathlib import Path
from datetime import datetime

import cv2
import yaml


def load_sampling_policy(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def seconds_to_timestamp(seconds: float) -> str:
    total_milliseconds = int(round(seconds * 1000))

    hours = total_milliseconds // 3_600_000
    remaining = total_milliseconds % 3_600_000

    minutes = remaining // 60_000
    remaining = remaining % 60_000

    secs = remaining // 1000
    milliseconds = remaining % 1000

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def read_video_metadata(video_path: str) -> dict:
    path = Path(video_path)

    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(str(path))

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if fps is None or fps <= 0:
        cap.release()
        raise RuntimeError("Invalid FPS value. Video may be corrupted or unsupported.")

    duration_seconds = total_frames / fps if total_frames > 0 else 0

    cap.release()

    return {
        "video_path": str(path.resolve()),
        "file_name": path.name,
        "fps": round(float(fps), 3),
        "total_frames": total_frames,
        "width": width,
        "height": height,
        "duration_seconds": round(duration_seconds, 3),
        "duration_timestamp": seconds_to_timestamp(duration_seconds),
    }


def generate_sampling_points(
    duration_seconds: float,
    source_fps: float,
    sampling_fps: float
) -> list:
    if duration_seconds <= 0:
        return []

    if sampling_fps <= 0:
        raise ValueError("sampling_fps must be greater than zero.")

    interval = 1.0 / sampling_fps
    points = []
    seen_frames = set()

    t = 0.0
    while t <= duration_seconds:
        frame_index = int(round(t * source_fps))

        if frame_index not in seen_frames:
            points.append({
                "time_seconds": round(t, 3),
                "timestamp": seconds_to_timestamp(t),
                "frame_index": frame_index
            })
            seen_frames.add(frame_index)

        t += interval

    return points


def build_metadata_report(video_path: str, config_path: str) -> dict:
    policy = load_sampling_policy(config_path)
    metadata = read_video_metadata(video_path)

    coarse_fps = float(policy["coarse_scan"]["fps"])

    sampling_points = generate_sampling_points(
        duration_seconds=metadata["duration_seconds"],
        source_fps=metadata["fps"],
        sampling_fps=coarse_fps
    )

    report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "video_metadata_reader",
            "created_at": datetime.now().isoformat(timespec="seconds")
        },
        "analysis_strategy": {
            "mode": policy["analysis_strategy"]["mode"],
            "hardware_profile": policy["analysis_strategy"]["hardware_profile"],
            "coarse_scan_fps": coarse_fps
        },
        "video_metadata": metadata,
        "coarse_scan_plan": {
            "sampling_fps": coarse_fps,
            "total_sampling_points": len(sampling_points),
            "sampling_interval_seconds": round(1.0 / coarse_fps, 3),
            "first_points_preview": sampling_points[:10],
            "last_points_preview": sampling_points[-10:] if len(sampling_points) > 10 else sampling_points
        },
        "sampling_points": sampling_points
    }

    return report


def save_json(report: dict, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="CASIT / ÇAŞIT video metadata reader and coarse scan point generator."
    )

    parser.add_argument(
        "--video",
        required=True,
        help="Path to input video file."
    )

    parser.add_argument(
        "--config",
        default="configs/sampling_policy.yaml",
        help="Path to sampling policy YAML config."
    )

    parser.add_argument(
        "--output",
        default=str(Path.home() / "casit-data/outputs/json/video_metadata_report.json"),
        help="Path to output JSON report."
    )

    args = parser.parse_args()

    report = build_metadata_report(
        video_path=args.video,
        config_path=args.config
    )

    save_json(report, args.output)

    metadata = report["video_metadata"]
    plan = report["coarse_scan_plan"]

    print("\nCASIT / ÇAŞIT Video Metadata Report")
    print("-----------------------------------")
    print(f"Video file        : {metadata['file_name']}")
    print(f"Resolution        : {metadata['width']} x {metadata['height']}")
    print(f"Source FPS        : {metadata['fps']}")
    print(f"Total frames      : {metadata['total_frames']}")
    print(f"Duration          : {metadata['duration_timestamp']}")
    print(f"Coarse scan FPS   : {plan['sampling_fps']}")
    print(f"Sampling points   : {plan['total_sampling_points']}")
    print(f"JSON output       : {args.output}")
    print("-----------------------------------\n")


if __name__ == "__main__":
    main()
