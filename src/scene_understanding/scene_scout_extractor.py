import argparse
import json
from pathlib import Path
from datetime import datetime

import cv2


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


def safe_timestamp(timestamp: str) -> str:
    return timestamp.replace(":", "-").replace(".", "-")


def resize_keep_aspect(frame, target_width: int):
    if target_width is None or target_width <= 0:
        return frame

    height, width = frame.shape[:2]

    if width <= target_width:
        return frame

    scale = target_width / width
    new_height = int(height * scale)

    return cv2.resize(frame, (target_width, new_height), interpolation=cv2.INTER_AREA)


def extract_scene_scout_frames(
    video_path: str,
    output_frames_root: str,
    output_json_path: str,
    scout_fps: float = 1.0,
    resize_width: int = 768,
    jpeg_quality: int = 90
) -> dict:
    video_file = Path(video_path)

    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")

    cap = cv2.VideoCapture(str(video_file))

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_file}")

    source_fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    duration_seconds = total_frames / source_fps if source_fps > 0 else 0.0

    video_stem = video_file.stem
    output_dir = Path(output_frames_root) / video_stem / "scene_scout_1fps"
    output_dir.mkdir(parents=True, exist_ok=True)

    interval = 1.0 / scout_fps
    time_points = []

    t = 0.0
    while t <= duration_seconds + 1e-9:
        time_points.append(round(t, 3))
        t += interval

    extracted_frames = []
    failed_frames = []

    for idx, time_seconds in enumerate(time_points):
        frame_index = int(round(time_seconds * source_fps))
        timestamp = seconds_to_timestamp(time_seconds)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        success, frame = cap.read()

        if not success or frame is None:
            failed_frames.append({
                "sample_index": idx,
                "time_seconds": time_seconds,
                "timestamp": timestamp,
                "source_frame_index": frame_index,
                "reason": "frame_read_failed"
            })
            continue

        frame = resize_keep_aspect(frame, resize_width)

        filename = (
            f"scout_{idx:06d}"
            f"_src_{frame_index:08d}"
            f"_t_{safe_timestamp(timestamp)}.jpg"
        )

        output_path = output_dir / filename

        cv2.imwrite(
            str(output_path),
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
        )

        saved_height, saved_width = frame.shape[:2]

        extracted_frames.append({
            "sample_index": idx,
            "time_seconds": time_seconds,
            "timestamp": timestamp,
            "source_frame_index": frame_index,
            "image_path": str(output_path.resolve()),
            "saved_width": saved_width,
            "saved_height": saved_height
        })

    cap.release()

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "scene_scout_extractor",
            "created_at": datetime.now().isoformat(timespec="seconds")
        },
        "video": {
            "file_name": video_file.name,
            "video_path": str(video_file.resolve()),
            "source_fps": source_fps,
            "total_frames": total_frames,
            "width": width,
            "height": height,
            "duration_seconds": round(duration_seconds, 3),
            "duration_timestamp": seconds_to_timestamp(duration_seconds)
        },
        "extraction": {
            "mode": "scene_scout_1fps",
            "scout_fps": scout_fps,
            "resize_width": resize_width,
            "jpeg_quality": jpeg_quality,
            "output_dir": str(output_dir.resolve()),
            "requested_frames": len(time_points),
            "extracted_frames": len(extracted_frames),
            "failed_frames": len(failed_frames)
        },
        "frames": extracted_frames,
        "failed": failed_frames
    }

    save_json(output, output_json_path)
    return output


def main():
    parser = argparse.ArgumentParser(
        description="CASIT / ÇAŞIT 1 FPS scene scout frame extractor."
    )

    parser.add_argument(
        "--video",
        required=True,
        help="Path to input video."
    )

    parser.add_argument(
        "--output-frames",
        default=str(Path.home() / "casit-data/datasets/frames"),
        help="Root directory for extracted scene scout frames."
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/scene_scout_report.json"),
        help="Path to output scene scout JSON report."
    )

    parser.add_argument(
        "--scout-fps",
        type=float,
        default=1.0,
        help="Scene scout sampling FPS."
    )

    parser.add_argument(
        "--resize-width",
        type=int,
        default=768,
        help="Resize scout frames to this width while preserving aspect ratio."
    )

    args = parser.parse_args()

    output = extract_scene_scout_frames(
        video_path=args.video,
        output_frames_root=args.output_frames,
        output_json_path=args.output_json,
        scout_fps=args.scout_fps,
        resize_width=args.resize_width
    )

    print("\nCASIT / ÇAŞIT Scene Scout Extraction Report")
    print("-------------------------------------------")
    print(f"Video file        : {output['video']['file_name']}")
    print(f"Duration          : {output['video']['duration_timestamp']}")
    print(f"Mode              : {output['extraction']['mode']}")
    print(f"Requested frames  : {output['extraction']['requested_frames']}")
    print(f"Extracted frames  : {output['extraction']['extracted_frames']}")
    print(f"Failed frames     : {output['extraction']['failed_frames']}")
    print(f"Output directory  : {output['extraction']['output_dir']}")
    print(f"JSON output       : {args.output_json}")
    print("-------------------------------------------\n")


if __name__ == "__main__":
    main()
