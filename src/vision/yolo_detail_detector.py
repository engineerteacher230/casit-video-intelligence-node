import argparse
import json
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

import cv2
import torch
from ultralytics import YOLO


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


def safe_path_name(text: str) -> str:
    return text.replace(":", "-").replace(".", "-").replace(" ", "_")


def detect_detail_frames(
    detail_frames_report_path: str,
    output_json_path: str,
    annotated_root: str,
    model_name: str = "yolo11n.pt",
    conf_threshold: float = 0.25,
    imgsz: int = 640,
    save_annotated: bool = True
) -> dict:
    report = load_json(detail_frames_report_path)

    frames = report["frames"]
    video = report["video"]

    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = YOLO(model_name)

    video_stem = Path(video["video_path"]).stem
    annotated_dir = Path(annotated_root) / video_stem / "yolo_detail"
    annotated_dir.mkdir(parents=True, exist_ok=True)

    detections_by_frame = []
    class_counter = Counter()
    frames_with_detections = 0
    total_detections = 0

    context_counter = defaultdict(int)

    for frame_item in frames:
        image_path = Path(frame_item["image_path"])

        if not image_path.exists():
            detections_by_frame.append({
                **frame_item,
                "detections": [],
                "error": "image_not_found"
            })
            continue

        results = model.predict(
            source=str(image_path),
            device=device,
            conf=conf_threshold,
            imgsz=imgsz,
            verbose=False
        )

        result = results[0]
        names = result.names

        frame_detections = []

        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                label = names.get(cls_id, str(cls_id))
                confidence = float(box.conf[0].item())

                x1, y1, x2, y2 = box.xyxy[0].tolist()

                detection = {
                    "class_id": cls_id,
                    "label": label,
                    "confidence": round(confidence, 4),
                    "bbox_xyxy": {
                        "x1": round(float(x1), 2),
                        "y1": round(float(y1), 2),
                        "x2": round(float(x2), 2),
                        "y2": round(float(y2), 2)
                    }
                }

                frame_detections.append(detection)
                class_counter[label] += 1
                total_detections += 1

        annotated_path = None

        if save_annotated:
            annotated = result.plot()
            filename = (
                f"{frame_item['context_window_id']}"
                f"_idx_{frame_item['local_index']:06d}"
                f"_t_{safe_path_name(frame_item['timestamp'])}.jpg"
            )
            annotated_path = annotated_dir / filename
            cv2.imwrite(str(annotated_path), annotated)

        if frame_detections:
            frames_with_detections += 1
            context_counter[frame_item["context_window_id"]] += len(frame_detections)

        detections_by_frame.append({
            **frame_item,
            "detections_count": len(frame_detections),
            "detections": frame_detections,
            "annotated_image_path": str(annotated_path.resolve()) if annotated_path else None
        })

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "yolo_detail_detector",
            "created_at": datetime.now().isoformat(timespec="seconds")
        },
        "source_report": str(Path(detail_frames_report_path).resolve()),
        "video": video,
        "model": {
            "model_name": model_name,
            "device": device,
            "conf_threshold": conf_threshold,
            "imgsz": imgsz,
            "torch_cuda_available": torch.cuda.is_available()
        },
        "summary": {
            "total_frames": len(frames),
            "frames_with_detections": frames_with_detections,
            "total_detections": total_detections,
            "class_counts": dict(class_counter),
            "detections_by_context_window": dict(context_counter)
        },
        "outputs": {
            "annotated_dir": str(annotated_dir.resolve()) if save_annotated else None
        },
        "frames": detections_by_frame
    }

    save_json(output, output_json_path)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="CASIT / ÇAŞIT YOLO detector for detail context frames."
    )

    parser.add_argument(
        "--detail-report",
        required=True,
        help="Path to detail frames report JSON."
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/detection_report.json"),
        help="Path to output detection JSON report."
    )

    parser.add_argument(
        "--annotated-root",
        default=str(Path.home() / "casit-data/outputs/annotated"),
        help="Root directory for annotated images."
    )

    parser.add_argument(
        "--model",
        default="yolo11n.pt",
        help="YOLO model file name."
    )

    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Confidence threshold."
    )

    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Inference image size."
    )

    args = parser.parse_args()

    output = detect_detail_frames(
        detail_frames_report_path=args.detail_report,
        output_json_path=args.output_json,
        annotated_root=args.annotated_root,
        model_name=args.model,
        conf_threshold=args.conf,
        imgsz=args.imgsz,
        save_annotated=True
    )

    print("\nCASIT / ÇAŞIT YOLO Detail Detection Report")
    print("------------------------------------------")
    print(f"Video file             : {output['video']['file_name']}")
    print(f"Model                  : {output['model']['model_name']}")
    print(f"Device                 : {output['model']['device']}")
    print(f"Total frames           : {output['summary']['total_frames']}")
    print(f"Frames with detections : {output['summary']['frames_with_detections']}")
    print(f"Total detections       : {output['summary']['total_detections']}")
    print(f"Class counts           : {output['summary']['class_counts']}")
    print(f"Annotated dir          : {output['outputs']['annotated_dir']}")
    print(f"JSON output            : {args.output_json}")
    print("------------------------------------------\n")


if __name__ == "__main__":
    main()
