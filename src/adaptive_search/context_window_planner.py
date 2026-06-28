import argparse
import json
from pathlib import Path
from datetime import datetime


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


def merge_context_windows(candidate_windows: list, max_gap_seconds: float = 0.5) -> list:
    if not candidate_windows:
        return []

    normalized = []

    for window in candidate_windows:
        context = window["context_window"]

        normalized.append({
            "source_candidate_ids": [window["candidate_event_id"]],
            "start_seconds": float(context["start_seconds"]),
            "end_seconds": float(context["end_seconds"]),
            "peak_time_seconds": float(window["peak_time_seconds"]),
            "peak_timestamp": window["peak_timestamp"],
            "peak_event_energy": float(window["peak_event_energy"]),
            "candidate_points_count": int(window["candidate_points_count"]),
            "recommended_fps": int(context.get("recommended_fps", 10)),
            "source_windows": [window]
        })

    normalized = sorted(normalized, key=lambda x: x["start_seconds"])

    merged = [normalized[0]]

    for current in normalized[1:]:
        previous = merged[-1]

        gap = current["start_seconds"] - previous["end_seconds"]

        overlaps_or_close = gap <= max_gap_seconds

        if overlaps_or_close:
            previous["end_seconds"] = max(previous["end_seconds"], current["end_seconds"])
            previous["start_seconds"] = min(previous["start_seconds"], current["start_seconds"])
            previous["source_candidate_ids"].extend(current["source_candidate_ids"])
            previous["candidate_points_count"] += current["candidate_points_count"]
            previous["source_windows"].extend(current["source_windows"])

            if current["peak_event_energy"] > previous["peak_event_energy"]:
                previous["peak_event_energy"] = current["peak_event_energy"]
                previous["peak_time_seconds"] = current["peak_time_seconds"]
                previous["peak_timestamp"] = current["peak_timestamp"]

            previous["recommended_fps"] = max(previous["recommended_fps"], current["recommended_fps"])
        else:
            merged.append(current)

    planned_windows = []

    for idx, item in enumerate(merged, start=1):
        duration = item["end_seconds"] - item["start_seconds"]

        planned_windows.append({
            "context_window_id": f"CTX_{idx:04d}",
            "start_seconds": round(item["start_seconds"], 3),
            "start_timestamp": seconds_to_timestamp(item["start_seconds"]),
            "end_seconds": round(item["end_seconds"], 3),
            "end_timestamp": seconds_to_timestamp(item["end_seconds"]),
            "duration_seconds": round(duration, 3),
            "recommended_fps": item["recommended_fps"],
            "peak_time_seconds": round(item["peak_time_seconds"], 3),
            "peak_timestamp": item["peak_timestamp"],
            "peak_event_energy": round(item["peak_event_energy"], 6),
            "source_candidate_ids": item["source_candidate_ids"],
            "candidate_points_count": item["candidate_points_count"],
            "relationship_reason": "merged_due_to_overlap_or_close_temporal_gap"
        })

    return planned_windows


def build_context_plan(
    event_energy_report_path: str,
    output_json_path: str,
    max_gap_seconds: float = 0.5
) -> dict:
    report = load_json(event_energy_report_path)

    candidate_windows = report.get("candidate_windows", [])
    planned_windows = merge_context_windows(
        candidate_windows=candidate_windows,
        max_gap_seconds=max_gap_seconds
    )

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "context_window_planner",
            "created_at": datetime.now().isoformat(timespec="seconds")
        },
        "source_report": str(Path(event_energy_report_path).resolve()),
        "video": report["video"],
        "planner_config": {
            "max_gap_seconds": max_gap_seconds,
            "merge_rule": "merge_if_context_windows_overlap_or_gap_is_less_than_max_gap"
        },
        "summary": {
            "input_candidate_windows": len(candidate_windows),
            "planned_context_windows": len(planned_windows)
        },
        "planned_context_windows": planned_windows
    }

    save_json(output, output_json_path)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="CASIT / ÇAŞIT context window planner for detailed 10 FPS analysis."
    )

    parser.add_argument(
        "--event-report",
        required=True,
        help="Path to event energy report JSON."
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/context_window_plan.json"),
        help="Path to output context window plan JSON."
    )

    parser.add_argument(
        "--max-gap-seconds",
        type=float,
        default=0.5,
        help="Merge windows if temporal gap is smaller than or equal to this value."
    )

    args = parser.parse_args()

    output = build_context_plan(
        event_energy_report_path=args.event_report,
        output_json_path=args.output_json,
        max_gap_seconds=args.max_gap_seconds
    )

    print("\nCASIT / ÇAŞIT Context Window Planner Report")
    print("-------------------------------------------")
    print(f"Video file               : {output['video']['file_name']}")
    print(f"Input candidate windows  : {output['summary']['input_candidate_windows']}")
    print(f"Planned context windows  : {output['summary']['planned_context_windows']}")

    if output["planned_context_windows"]:
        print("\nPlanned windows:")
        for window in output["planned_context_windows"]:
            print(
                f"- {window['context_window_id']} | "
                f"{window['start_timestamp']} → {window['end_timestamp']} | "
                f"duration: {window['duration_seconds']}s | "
                f"fps: {window['recommended_fps']} | "
                f"peak: {window['peak_timestamp']} | "
                f"sources: {', '.join(window['source_candidate_ids'])}"
            )
    else:
        print("\nNo planned context windows.")

    print(f"\nJSON output              : {args.output_json}")
    print("-------------------------------------------\n")


if __name__ == "__main__":
    main()
