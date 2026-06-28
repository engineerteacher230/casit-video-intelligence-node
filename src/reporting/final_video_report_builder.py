#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path
from datetime import datetime


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_text(text, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def safe(value, default="Belirtilmedi"):
    if value is None:
        return default
    if value == "":
        return default
    return value


def build_class_section(class_evidence):
    lines = []

    for ev in class_evidence:
        class_name = ev.get("class_name")
        evidence_type = ev.get("evidence_type")
        detection_count = ev.get("detection_count")
        raw_track_count = ev.get("raw_track_count")
        stable_track_count = ev.get("stable_track_count")
        estimated_physical_count = ev.get("estimated_physical_count")
        reliability = ev.get("reliability")
        statement = ev.get("evidence_statement_tr")

        lines.append(f"### Sınıf: `{class_name}`")
        lines.append("")
        lines.append(f"- Kanıt tipi: `{evidence_type}`")
        lines.append(f"- Frame bazlı tespit sayısı: `{detection_count}`")
        lines.append(f"- Ham track sayısı: `{raw_track_count}`")
        lines.append(f"- Stabil track sayısı: `{stable_track_count}`")
        lines.append(f"- Tahmini fiziksel sayı: `{estimated_physical_count}`")
        lines.append(f"- Güven düzeyi: `{reliability}`")
        lines.append("")
        lines.append(f"**Yorum:** {statement}")
        lines.append("")

    return "\n".join(lines)


def build_warning_section(warnings):
    if not warnings:
        return "Uyarı bulunmuyor."

    lines = []
    for warning in warnings:
        lines.append(f"- {warning}")
    return "\n".join(lines)


def build_report(event_report):
    scene = event_report.get("scene_context", {})
    selected_policy = event_report.get("selected_policy", {})
    class_evidence = event_report.get("class_evidence", [])
    warnings = event_report.get("warnings", [])
    event_questions = event_report.get("event_questions", [])
    summary = event_report.get("decision_support_summary_tr", {})

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []

    lines.append("# ÇAŞIT Video Analiz ve Karar Destek Raporu")
    lines.append("")
    lines.append(f"Rapor zamanı: `{now}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Genel Durum")
    lines.append("")
    lines.append("Bu rapor, dışarıdan gelen bilinmeyen bir videonun önce Qwen/VLM ile sahne bağlamının anlaşılması, ardından YOLO dedektörünün bu bağlama göre odaklanması ve tracking/kanıt rafinesi ile yorumlanması sonucunda üretilmiştir.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Sahne Bağlamı")
    lines.append("")
    lines.append(f"- Sahne tipi: `{safe(scene.get('scene_type'))}`")
    lines.append(f"- Domain: `{safe(scene.get('domain'))}`")
    lines.append(f"- Qwen/VLM güveni: `{safe(scene.get('confidence'))}`")
    lines.append(f"- Doğrulama durumu: `{safe(scene.get('validation_status'))}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Seçilen YOLO Odak Politikası")
    lines.append("")
    lines.append(f"- Politika adı: `{safe(selected_policy.get('name'))}`")
    lines.append(f"- Seçim nedeni: `{safe(selected_policy.get('reason'))}`")
    lines.append(f"- Açıklama: {safe(selected_policy.get('description'))}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Kanıt Özeti")
    lines.append("")
    lines.append(build_class_section(class_evidence))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Uyarılar")
    lines.append("")
    lines.append(build_warning_section(warnings))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. Olay Soruları")
    lines.append("")

    if event_questions:
        for q in event_questions:
            lines.append(f"- {q}")
    else:
        lines.append("- Bu sahne için tanımlı olay sorusu bulunamadı.")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. Karar Destek Yorumu")
    lines.append("")
    lines.append(f"- Ana sonuç: {safe(summary.get('main_result'))}")
    lines.append(f"- Sayım kuralı: {safe(summary.get('count_rule'))}")
    lines.append(f"- Sonraki adım: {safe(summary.get('next_step'))}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 8. Kritik Yorum")
    lines.append("")
    lines.append("Detection sayısı gerçek kişi/nesne sayısı değildir. Aynı nesne farklı karelerde tekrar tekrar tespit edilmiş olabilir. Bu nedenle stabil track sayısı, ham detection sayısından daha anlamlıdır.")
    lines.append("")
    lines.append("Küçük ve hızlı nesnelerde, örneğin top gibi sınıflarda, fiziksel nesne sayısı güvenilir şekilde verilmemelidir. Bu tür nesneler için varlık/tespit kanıtı raporlanmalıdır.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-evidence", default=str(Path.home() / "casit-data/outputs/json/event_evidence_report.json"))
    parser.add_argument("--output-md", default=str(Path.home() / "casit-data/outputs/reports/final_video_analysis_report.md"))
    args = parser.parse_args()

    event_path = Path(args.event_evidence).expanduser()
    output_path = Path(args.output_md).expanduser()

    event_report = load_json(event_path)
    report_text = build_report(event_report)

    save_text(report_text, output_path)

    print("CASIT / ÇAŞIT Final Video Report Builder")
    print("----------------------------------------")
    print("Input :", event_path)
    print("Output:", output_path)
    print("----------------------------------------")
    print()
    print(report_text[:1500])
    print()
    print("... raporun tamamı dosyaya yazıldı.")


if __name__ == "__main__":
    main()
