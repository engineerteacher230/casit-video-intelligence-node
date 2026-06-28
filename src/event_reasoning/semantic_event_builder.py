#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from datetime import datetime


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def scene_to_event_name(scene_type: str, domain: str) -> str:
    s = (scene_type or "").lower()
    d = (domain or "").lower()

    if "confrontation" in s:
        return "Sokak / kalabalık gerilim olayı"
    if "traffic" in s or d == "traffic":
        return "Trafik ve yaya hareketliliği olayı"
    if "crowd" in s:
        return "Kalabalık hareketliliği olayı"
    if "factory" in s or "industrial" in s:
        return "Endüstriyel saha hareketliliği olayı"
    if "security" in s:
        return "Güvenlik izleme olayı"

    return "Genel sahne olayı"


def build_semantic_events(scene_prior, context_plan, event_energy, event_evidence):
    # scene_prior_agent çıktısında esas sahne bilgisi nested gelir:
    # scene_prior["scene_prior"]["scene_type"], ["domain"], ["confidence"]
    prior_core = scene_prior.get("scene_prior", scene_prior)

    scene_type = prior_core.get("scene_type", "unknown")
    domain = prior_core.get("domain", "unknown")
    confidence = prior_core.get("confidence", None)

    # Ek güvenlik: event_evidence içinde scene_context varsa fallback olarak kullan.
    scene_context = event_evidence.get("scene_context", {})
    if scene_type == "unknown":
        scene_type = scene_context.get("scene_type", scene_type)
    if domain == "unknown":
        domain = scene_context.get("domain", domain)
    if confidence is None:
        confidence = scene_context.get("confidence", confidence)

    planned = context_plan.get("planned_context_windows", [])
    candidate_windows = event_energy.get("candidate_windows", [])
    class_evidence = event_evidence.get("class_evidence", [])

    candidate_by_id = {
        c.get("candidate_event_id"): c
        for c in candidate_windows
        if c.get("candidate_event_id")
    }

    semantic_events = []

    for idx, w in enumerate(planned, start=1):
        source_ids = w.get("source_candidate_ids", [])
        source_candidates = [
            candidate_by_id[x]
            for x in source_ids
            if x in candidate_by_id
        ]

        peak_moments = []
        for c in source_candidates:
            peak_moments.append({
                "candidate_event_id": c.get("candidate_event_id"),
                "peak_timestamp": c.get("peak_timestamp"),
                "peak_event_energy": c.get("peak_event_energy"),
                "reason": c.get("reason")
            })

        peak_moments = sorted(
            peak_moments,
            key=lambda x: x.get("peak_event_energy") or 0,
            reverse=True
        )

        top_classes = []
        for item in class_evidence:
            cls = item.get("class_name") or item.get("class")
            if not cls:
                continue
            top_classes.append({
                "class_name": cls,
                "detection_count": item.get("detection_count"),
                "stable_track_count": item.get("stable_track_count"),
                "estimated_physical_count": item.get("estimated_physical_count"),
                "reliability": item.get("reliability")
            })

        semantic_event = {
            "semantic_event_id": f"SEM_EVT_{idx:04d}",
            "context_window_id": w.get("context_window_id"),
            "event_name": scene_to_event_name(scene_type, domain),
            "scene_type": scene_type,
            "domain": domain,
            "scene_confidence": confidence,
            "start_timestamp": w.get("start_timestamp"),
            "end_timestamp": w.get("end_timestamp"),
            "duration_seconds": w.get("duration_seconds"),
            "peak_timestamp": w.get("peak_timestamp"),
            "peak_event_energy": w.get("peak_event_energy"),
            "source_candidate_count": len(source_ids),
            "source_candidate_ids": source_ids,
            "relationship_reason": w.get("relationship_reason"),
            "interpretation": (
                "Bu makro olay, birden fazla hareket yoğunluğu adayının zamansal olarak "
                "birbirine yakın veya örtüşen şekilde aynı bağlam içinde birleşmesiyle oluşmuştur. "
                "Bu nedenle adaylar ayrı ayrı olay değil, aynı olayın alt hareket zirveleri olarak değerlendirilmelidir."
            ),
            "important_moments": peak_moments[:10],
            "object_evidence": top_classes,
            "event_reliability": "medium" if confidence and confidence < 0.90 else "medium_high"
        }

        semantic_events.append(semantic_event)

    return {
        "project": "CASIT / ÇAŞIT",
        "report_type": "semantic_event_report",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scene_summary": {
            "scene_type": scene_type,
            "domain": domain,
            "confidence": confidence
        },
        "summary": {
            "semantic_event_count": len(semantic_events),
            "motion_candidate_count": len(candidate_windows),
            "note": "Motion candidates are treated as sub-moments. Planned context windows are treated as macro semantic events."
        },
        "semantic_events": semantic_events
    }


def write_markdown(path: Path, report):
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# ÇAŞIT Semantik Olay Raporu")
    lines.append("")
    lines.append(f"Rapor zamanı: `{report.get('created_at')}`")
    lines.append("")
    lines.append("## Genel Özet")
    lines.append("")
    s = report.get("scene_summary", {})
    lines.append(f"- Sahne tipi: `{s.get('scene_type')}`")
    lines.append(f"- Domain: `{s.get('domain')}`")
    lines.append(f"- Güven: `{s.get('confidence')}`")
    lines.append(f"- Makro olay sayısı: `{report['summary']['semantic_event_count']}`")
    lines.append(f"- Hareket adayı sayısı: `{report['summary']['motion_candidate_count']}`")
    lines.append("")
    lines.append("> Hareket adayları tek başına olay değildir; aynı bağlamda birleşiyorsa makro olayın alt anlarıdır.")
    lines.append("")

    for ev in report.get("semantic_events", []):
        lines.append(f"## {ev.get('semantic_event_id')} — {ev.get('event_name')}")
        lines.append("")
        lines.append(f"- Zaman aralığı: `{ev.get('start_timestamp')}` → `{ev.get('end_timestamp')}`")
        lines.append(f"- Süre: `{ev.get('duration_seconds')}` saniye")
        lines.append(f"- Tepe anı: `{ev.get('peak_timestamp')}`")
        lines.append(f"- Kaynak hareket adayı sayısı: `{ev.get('source_candidate_count')}`")
        lines.append(f"- Güven: `{ev.get('event_reliability')}`")
        lines.append("")
        lines.append("### Yorum")
        lines.append("")
        lines.append(ev.get("interpretation", ""))
        lines.append("")
        lines.append("### Öne Çıkan Hareket Anları")
        lines.append("")
        for m in ev.get("important_moments", []):
            lines.append(
                f"- `{m.get('candidate_event_id')}` | peak: `{m.get('peak_timestamp')}` | energy: `{m.get('peak_event_energy')}`"
            )
        lines.append("")
        lines.append("### Nesne Kanıtları")
        lines.append("")
        for obj in ev.get("object_evidence", []):
            lines.append(
                f"- `{obj.get('class_name')}` | detection: `{obj.get('detection_count')}` | "
                f"stable track: `{obj.get('stable_track_count')}` | "
                f"tahmini sayı: `{obj.get('estimated_physical_count')}` | "
                f"güven: `{obj.get('reliability')}`"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-prior", required=True)
    parser.add_argument("--context-plan", required=True)
    parser.add_argument("--event-energy", required=True)
    parser.add_argument("--event-evidence", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    scene_prior = load_json(Path(args.scene_prior).expanduser())
    context_plan = load_json(Path(args.context_plan).expanduser())
    event_energy = load_json(Path(args.event_energy).expanduser())
    event_evidence = load_json(Path(args.event_evidence).expanduser())

    report = build_semantic_events(scene_prior, context_plan, event_energy, event_evidence)

    save_json(Path(args.output_json).expanduser(), report)
    write_markdown(Path(args.output_md).expanduser(), report)

    print("CASIT / ÇAŞIT Semantic Event Builder")
    print("-----------------------------------")
    print("Semantic event count :", report["summary"]["semantic_event_count"])
    print("Motion candidate count:", report["summary"]["motion_candidate_count"])
    print("Output JSON:", Path(args.output_json).expanduser())
    print("Output MD  :", Path(args.output_md).expanduser())
    print("-----------------------------------")


if __name__ == "__main__":
    main()
