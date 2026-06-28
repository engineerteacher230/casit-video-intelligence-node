import argparse
import json
from pathlib import Path
from datetime import datetime

import cv2


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


def safe_timestamp(timestamp: str) -> str:
    return (
        timestamp
        .replace(":", "-")
        .replace(".", "-")
    )


def resize_keep_aspect(frame, target_width: int):
    if target_width is None or target_width <= 0:
        return frame

    height, width = frame.shape[:2]

    if width <= target_width:
        return frame

    scale = target_width / width
    new_height = int(height * scale)

    return cv2.resize(frame, (target_width, new_height), interpolation=cv2.INTER_AREA)


def extract_frames_from_report(
    metadata_report_path: str,
    output_frames_root: str,
    output_json_path: str,
    resize_width: int = 960,
    jpeg_quality: int = 90
) -> dict:
    report = load_json(metadata_report_path)

    video_metadata = report["video_metadata"]
    sampling_points = report["sampling_points"]

    video_path = Path(video_metadata["video_path"])
    video_stem = video_path.stem

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_dir = Path(output_frames_root) / video_stem / "coarse_3fps"
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    extracted_frames = []
    failed_frames = []

    for idx, point in enumerate(sampling_points):
        frame_index = int(point["frame_index"])
        timestamp = point["timestamp"]
        time_seconds = point["time_seconds"]

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        success, frame = cap.read()

        if not success or frame is None:
            failed_frames.append({
                "frame_index": frame_index,
                "timestamp": timestamp,
                "reason": "frame_read_failed"
            })
            continue

        frame = resize_keep_aspect(frame, resize_width)

        filename = (
            f"frame_{idx:06d}"
            f"_src_{frame_index:08d}"
            f"_t_{safe_timestamp(timestamp)}.jpg"
        )

        output_path = output_dir / filename

        cv2.imwrite(
            str(output_path),
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
        )

        height, width = frame.shape[:2]

        extracted_frames.append({
            "sample_index": idx,
            "source_frame_index": frame_index,
            "time_seconds": time_seconds,
            "timestamp": timestamp,
            "image_path": str(output_path.resolve()),
            "saved_width": width,
            "saved_height": height
        })

    cap.release()

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "coarse_frame_extractor",
            "created_at": datetime.now().isoformat(timespec="seconds")
        },
        "source_report": str(Path(metadata_report_path).resolve()),
        "video": {
            "file_name": video_metadata["file_name"],
            "video_path": video_metadata["video_path"],
            "source_fps": video_metadata["fps"],
            "duration_seconds": video_metadata["duration_seconds"],
            "width": video_metadata["width"],
            "height": video_metadata["height"]
        },
        "extraction": {
            "mode": "coarse_3fps",
            "resize_width": resize_width,
            "jpeg_quality": jpeg_quality,
            "output_dir": str(output_dir.resolve()),
            "requested_frames": len(sampling_points),
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
        description="CASIT / ÇAŞIT coarse frame extractor from metadata report."
    )

    parser.add_argument(
        "--metadata",
        required=True,
        help="Path to video metadata report JSON."
    )

    parser.add_argument(
        "--output-frames",
        default=str(Path.home() / "casit-data/datasets/frames"),
        help="Root directory for extracted frames."
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/coarse_frames_report.json"),
        help="Path to output frame extraction JSON report."
    )

    parser.add_argument(
        "--resize-width",
        type=int,
        default=960,
        help="Resize output frames to this width while preserving aspect ratio."
    )

    args = parser.parse_args()

    output = extract_frames_from_report(
        metadata_report_path=args.metadata,
        output_frames_root=args.output_frames,
        output_json_path=args.output_json,
        resize_width=args.resize_width
    )

    print("\nCASIT / ÇAŞIT Coarse Frame Extraction Report")
    print("--------------------------------------------")
    print(f"Video file        : {output['video']['file_name']}")
    print(f"Mode              : {output['extraction']['mode']}")
    print(f"Requested frames  : {output['extraction']['requested_frames']}")
    print(f"Extracted frames  : {output['extraction']['extracted_frames']}")
    print(f"Failed frames     : {output['extraction']['failed_frames']}")
    print(f"Output directory  : {output['extraction']['output_dir']}")
    print(f"JSON output       : {args.output_json}")
    print("--------------------------------------------\n")


if __name__ == "__main__":
    main()
