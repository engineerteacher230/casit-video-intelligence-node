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

    # Bu bilgisayarda gereksiz upscale yapmıyoruz.
    # Genişlik zaten hedef genişlikten küçükse aynı bırakıyoruz.
    if width <= target_width:
        return frame

    scale = target_width / width
    new_height = int(height * scale)

    return cv2.resize(frame, (target_width, new_height), interpolation=cv2.INTER_AREA)


def generate_time_points(start_seconds: float, end_seconds: float, fps: float) -> list:
    if fps <= 0:
        raise ValueError("fps must be greater than zero.")

    interval = 1.0 / fps
    points = []

    t = start_seconds
    while t <= end_seconds + 1e-9:
        points.append(round(t, 3))
        t += interval

    return points


def extract_detail_windows(
    context_plan_path: str,
    output_frames_root: str,
    output_json_path: str,
    resize_width: int = 1280,
    jpeg_quality: int = 92
) -> dict:
    plan = load_json(context_plan_path)

    video_info = plan["video"]
    video_path = Path(video_info["video_path"])
    video_stem = video_path.stem

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    source_fps = float(video_info["source_fps"])
    planned_windows = plan["planned_context_windows"]

    all_extracted_frames = []
    all_failed_frames = []
    window_reports = []

    for window in planned_windows:
        context_window_id = window["context_window_id"]
        start_seconds = float(window["start_seconds"])
        end_seconds = float(window["end_seconds"])
        recommended_fps = float(window["recommended_fps"])

        # Kaynak FPS değerini aşmıyoruz.
        extraction_fps = min(recommended_fps, source_fps)

        output_dir = (
            Path(output_frames_root)
            / video_stem
            / "detail_10fps"
            / context_window_id
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        time_points = generate_time_points(
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            fps=extraction_fps
        )

        extracted_for_window = []
        failed_for_window = []

        for local_index, time_seconds in enumerate(time_points):
            frame_index = int(round(time_seconds * source_fps))
            timestamp = seconds_to_timestamp(time_seconds)

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = cap.read()

            if not success or frame is None:
                failed_item = {
                    "context_window_id": context_window_id,
                    "local_index": local_index,
                    "source_frame_index": frame_index,
                    "time_seconds": round(time_seconds, 3),
                    "timestamp": timestamp,
                    "reason": "frame_read_failed"
                }
                failed_for_window.append(failed_item)
                all_failed_frames.append(failed_item)
                continue

            frame = resize_keep_aspect(frame, resize_width)

            filename = (
                f"{context_window_id}"
                f"_detail_{local_index:06d}"
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

            frame_item = {
                "context_window_id": context_window_id,
                "local_index": local_index,
                "source_frame_index": frame_index,
                "time_seconds": round(time_seconds, 3),
                "timestamp": timestamp,
                "image_path": str(output_path.resolve()),
                "saved_width": width,
                "saved_height": height
            }

            extracted_for_window.append(frame_item)
            all_extracted_frames.append(frame_item)

        window_reports.append({
            "context_window_id": context_window_id,
            "start_seconds": start_seconds,
            "start_timestamp": window["start_timestamp"],
            "end_seconds": end_seconds,
            "end_timestamp": window["end_timestamp"],
            "duration_seconds": window["duration_seconds"],
            "recommended_fps": recommended_fps,
            "actual_extraction_fps": extraction_fps,
            "output_dir": str(output_dir.resolve()),
            "requested_frames": len(time_points),
            "extracted_frames": len(extracted_for_window),
            "failed_frames": len(failed_for_window),
            "source_candidate_ids": window["source_candidate_ids"],
            "peak_timestamp": window["peak_timestamp"],
            "peak_event_energy": window["peak_event_energy"]
        })

    cap.release()

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "detail_window_extractor",
            "created_at": datetime.now().isoformat(timespec="seconds")
        },
        "source_plan": str(Path(context_plan_path).resolve()),
        "video": video_info,
        "extraction": {
            "mode": "detail_context_windows",
            "resize_width": resize_width,
            "jpeg_quality": jpeg_quality,
            "total_context_windows": len(planned_windows),
            "total_extracted_frames": len(all_extracted_frames),
            "total_failed_frames": len(all_failed_frames)
        },
        "windows": window_reports,
        "frames": all_extracted_frames,
        "failed": all_failed_frames
    }

    save_json(output, output_json_path)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="CASIT / ÇAŞIT detail window extractor for 10 FPS context analysis."
    )

    parser.add_argument(
        "--context-plan",
        required=True,
        help="Path to context window plan JSON."
    )

    parser.add_argument(
        "--output-frames",
        default=str(Path.home() / "casit-data/datasets/frames"),
        help="Root directory for extracted detail frames."
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/detail_frames_report.json"),
        help="Path to output detail frames JSON report."
    )

    parser.add_argument(
        "--resize-width",
        type=int,
        default=1280,
        help="Resize output frames to this width while preserving aspect ratio."
    )

    args = parser.parse_args()

    output = extract_detail_windows(
        context_plan_path=args.context_plan,
        output_frames_root=args.output_frames,
        output_json_path=args.output_json,
        resize_width=args.resize_width
    )

    print("\nCASIT / ÇAŞIT Detail Window Extraction Report")
    print("---------------------------------------------")
    print(f"Video file             : {output['video']['file_name']}")
    print(f"Context windows        : {output['extraction']['total_context_windows']}")
    print(f"Total extracted frames : {output['extraction']['total_extracted_frames']}")
    print(f"Total failed frames    : {output['extraction']['total_failed_frames']}")

    print("\nWindows:")
    for window in output["windows"]:
        print(
            f"- {window['context_window_id']} | "
            f"{window['start_timestamp']} → {window['end_timestamp']} | "
            f"fps: {window['actual_extraction_fps']} | "
            f"requested: {window['requested_frames']} | "
            f"extracted: {window['extracted_frames']} | "
            f"failed: {window['failed_frames']}"
        )

    print(f"\nJSON output            : {args.output_json}")
    print("---------------------------------------------\n")


if __name__ == "__main__":
    main()
