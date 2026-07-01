#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CASIT / ÇAŞIT Event VLM Reasoner

Amaç:
Her semantic event için başlangıç, peak ve bitiş karelerini Qwen/VLM'e yorumlatmak.

Bu modül:
- semantic_event_report.json okur
- detail_frames_report.json içinden event'e ait temsilci kareleri seçer
- proximity_risk_report.json varsa ilişkisel risk kanıtlarını ekler
- VLM'den STRICT JSON cevap ister
- event_vlm_reasoning_report.json ve Markdown raporu üretir

Etik not:
Kimlik tanıma, yüz tanıma veya kişisel kimlik çıkarımı yapmaz.
Sadece sahne, olay, risk ve operatör aksiyonu yorumlar.
"""

import argparse
import base64
import json
import re
from pathlib import Path
from datetime import datetime

import requests


VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

RISK_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def load_json(path: Path, default=None):
    if default is None:
        default = {}
    path = Path(path).expanduser()
    if not path.exists():
        return default
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


def encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")



def extract_json_object(text: str):
    text = (text or "").strip()

    # VLM bazen ```json ... ``` döndürüyor.
    text = text.replace("```json", "")
    text = text.replace("```JSON", "")
    text = text.replace("```", "")
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start_idx = text.find("{")
    end_idx = text.rfind("}")

    if start_idx >= 0 and end_idx > start_idx:
        candidate = text[start_idx:end_idx + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return {
        "parse_error": True,
        "raw_text": text,
    }


def timestamp_to_seconds(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    m = re.match(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})$", value)
    if not m:
        return None

    hh, mm, ss, ms = [int(x) for x in m.groups()]
    return hh * 3600 + mm * 60 + ss + ms / 1000.0


def normalize_risk(value):
    if not value:
        return "low"

    value = str(value).lower().strip()

    aliases = {
        "düşük": "low",
        "orta": "medium",
        "yüksek": "high",
        "kritik": "critical",
    }

    value = aliases.get(value, value)
    return value if value in VALID_RISK_LEVELS else "low"


def max_risk(levels):
    if not levels:
        return "low"
    return max([normalize_risk(x) for x in levels], key=lambda x: RISK_RANK.get(x, 1))


def select_nearest_frame(frames, context_window_id, target_seconds, role):
    candidates = [
        frame for frame in frames
        if frame.get("context_window_id") == context_window_id
        and frame.get("image_path")
        and frame.get("time_seconds") is not None
    ]

    if not candidates:
        return None

    if target_seconds is None:
        if role == "start":
            selected = candidates[0]
        elif role == "end":
            selected = candidates[-1]
        else:
            selected = candidates[len(candidates) // 2]
    else:
        selected = min(
            candidates,
            key=lambda frame: abs(float(frame.get("time_seconds", 0.0)) - float(target_seconds))
        )

    return {
        "role": role,
        "context_window_id": selected.get("context_window_id"),
        "timestamp": selected.get("timestamp"),
        "time_seconds": selected.get("time_seconds"),
        "image_path": selected.get("image_path"),
        "source_frame_index": selected.get("source_frame_index"),
        "saved_width": selected.get("saved_width"),
        "saved_height": selected.get("saved_height"),
    }


def select_event_frames(event, detail_frames, max_images_per_event=3):
    frames = detail_frames.get("frames", [])
    context_window_id = event.get("context_window_id")

    start_seconds = timestamp_to_seconds(event.get("start_timestamp") or event.get("start_time"))
    peak_seconds = timestamp_to_seconds(event.get("peak_timestamp") or event.get("peak_time"))
    end_seconds = timestamp_to_seconds(event.get("end_timestamp") or event.get("end_time"))

    selected = []

    for role, sec in [
        ("start", start_seconds),
        ("peak", peak_seconds),
        ("end", end_seconds),
    ]:
        frame = select_nearest_frame(frames, context_window_id, sec, role)
        if frame:
            selected.append(frame)

    # Aynı frame tekrar seçildiyse tekilleştir.
    unique = []
    seen_paths = set()

    for frame in selected:
        path = frame.get("image_path")
        if path in seen_paths:
            continue
        seen_paths.add(path)
        unique.append(frame)

    return unique[:max_images_per_event]


def time_overlap_seconds(a_start, a_end, b_start, b_end):
    if None in [a_start, a_end, b_start, b_end]:
        return 0.0

    start = max(float(a_start), float(b_start))
    end = min(float(a_end), float(b_end))

    return max(0.0, end - start)


def select_proximity_evidence_for_event(event, proximity_report, max_items=8):
    event_start = timestamp_to_seconds(event.get("start_timestamp") or event.get("start_time"))
    event_end = timestamp_to_seconds(event.get("end_timestamp") or event.get("end_time"))

    risk_events = proximity_report.get("risk_events", [])
    selected = []

    for risk in risk_events:
        risk_start = timestamp_to_seconds(risk.get("start_time"))
        risk_end = timestamp_to_seconds(risk.get("end_time"))

        overlap = time_overlap_seconds(event_start, event_end, risk_start, risk_end)

        if overlap <= 0:
            continue

        selected.append({
            "risk_event_id": risk.get("risk_event_id"),
            "source_relation_event_id": risk.get("source_relation_event_id"),
            "risk_type": risk.get("risk_type"),
            "risk_level": risk.get("risk_level"),
            "priority": risk.get("priority"),
            "start_time": risk.get("start_time"),
            "end_time": risk.get("end_time"),
            "peak_time": risk.get("peak_time"),
            "overlap_seconds": round(overlap, 3),
            "risk_reason_tr": risk.get("risk_reason_tr"),
        })

    selected.sort(
        key=lambda item: (
            RISK_RANK.get(normalize_risk(item.get("risk_level")), 1),
            item.get("overlap_seconds", 0.0)
        ),
        reverse=True
    )

    return selected[:max_items]





def normalize_event_type(value):
    allowed = {
        "crowd_movement",
        "person_vehicle_risk",
        "vehicle_vehicle_risk",
        "accident_possible",
        "security_attention",
        "normal_activity",
        "unclear",
    }

    if not value:
        return "unclear"

    value = str(value).strip().lower()

    # Model bazen enum listesini komple döndürüyor: "a | b | c"
    if "|" in value:
        value = value.split("|")[0].strip()

    value = value.replace(" ", "_")
    return value if value in allowed else "unclear"


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [str(value)]


def build_prompt(event, selected_frames, proximity_evidence):
    frame = selected_frames[0] if selected_frames else {}

    compact_event = {
        "id": event.get("semantic_event_id"),
        "ctx": event.get("context_window_id"),
        "name": event.get("event_name") or event.get("event_name_tr"),
        "scene": event.get("scene_type"),
        "domain": event.get("domain"),
        "start": event.get("start_timestamp") or event.get("start_time"),
        "peak": event.get("peak_timestamp") or event.get("peak_time"),
        "end": event.get("end_timestamp") or event.get("end_time"),
    }

    compact_frame = {
        "role": frame.get("role"),
        "timestamp": frame.get("timestamp"),
    }

    compact_risks = []
    for item in proximity_evidence[:3]:
        compact_risks.append({
            "type": item.get("risk_type"),
            "level": item.get("risk_level"),
            "time": item.get("peak_time") or item.get("start_time"),
        })

    return f"""
Analyze ONE image frame for CASIT video decision support.
Answer in Turkish.
No identity recognition. No face recognition.
Do not claim injury/crime/collision unless clearly visible.
Return ONLY valid JSON. No markdown. No code block.

Event={json.dumps(compact_event, ensure_ascii=False)}
Frame={json.dumps(compact_frame, ensure_ascii=False)}
Risks={json.dumps(compact_risks, ensure_ascii=False)}

Return exactly these compact keys:
type,risk,desc,entities,actions,evidence,confidence,limits

Allowed type:
crowd_movement, person_vehicle_risk, vehicle_vehicle_risk, accident_possible, security_attention, normal_activity, unclear

Allowed risk:
low, medium, high, critical

Keep short:
desc max 18 words.
entities max 4.
actions max 3.
evidence max 3.
limits max 15 words.
""".strip()


def normalize_vlm_item(parsed, event, frame):
    if not isinstance(parsed, dict):
        parsed = {"parse_error": True, "raw_text": str(parsed)}

    if parsed.get("parse_error"):
        parsed["frame_role"] = frame.get("role")
        parsed["frame_timestamp"] = frame.get("timestamp")
        return parsed

    # Hem compact şema hem eski full şema desteklenir.
    risk_level = normalize_risk(parsed.get("risk_level") or parsed.get("risk"))
    event_type = normalize_event_type(parsed.get("vlm_event_type") or parsed.get("type"))

    description = parsed.get("vlm_description_tr") or parsed.get("desc") or ""
    risk_reason = parsed.get("risk_reason_tr") or parsed.get("desc") or "Görsel olay ve proximity kanıtı birlikte değerlendirilmiştir."

    actions = parsed.get("operator_actions_tr")
    if actions is None:
        actions = parsed.get("actions")
    actions = ensure_list(actions)

    evidence = parsed.get("evidence_tr")
    if evidence is None:
        evidence = parsed.get("evidence")
    evidence = ensure_list(evidence)

    visible_entities = parsed.get("visible_entities")
    if visible_entities is None:
        visible_entities = parsed.get("entities")
    visible_entities = ensure_list(visible_entities)

    confidence = parsed.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return {
        "semantic_event_id": parsed.get("semantic_event_id") or event.get("semantic_event_id"),
        "context_window_id": parsed.get("context_window_id") or event.get("context_window_id"),
        "vlm_event_name_tr": parsed.get("vlm_event_name_tr") or event.get("event_name") or "Video olayı",
        "vlm_event_type": event_type,
        "vlm_description_tr": description,
        "visible_entities": visible_entities[:8],
        "critical_moment_timestamp": parsed.get("critical_moment_timestamp") or frame.get("timestamp") or event.get("peak_timestamp"),
        "risk_level": risk_level,
        "risk_reason_tr": risk_reason,
        "operator_actions_tr": actions[:6],
        "evidence_tr": evidence[:6],
        "confidence": confidence,
        "limitations_tr": parsed.get("limitations_tr") or parsed.get("limits") or "Tek kare yorumu; operatör doğrulaması gerekir.",
        "frame_role": frame.get("role"),
        "frame_timestamp": frame.get("timestamp"),
    }


def ask_vlm_about_single_frame(
    event,
    frame,
    proximity_evidence,
    server_url,
    model,
    timeout,
    temperature,
    max_tokens,
):
    prompt = build_prompt(event, [frame], proximity_evidence)

    prompt += f"\nFrame role: {frame.get('role')}; timestamp: {frame.get('timestamp')}. Analyze only this image."

    image_path = frame.get("image_path")
    image_b64 = encode_image_base64(image_path)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        },
                    },
                ],
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    response = requests.post(
        f"{server_url}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=timeout,
    )

    if not response.ok:
        print("---- VLM HTTP ERROR ----")
        print("Frame role :", frame.get("role"))
        print("Timestamp  :", frame.get("timestamp"))
        print("Status code:", response.status_code)
        print(response.text)
        response.raise_for_status()

    data = response.json()
    content_text = data["choices"][0]["message"]["content"]
    parsed = normalize_vlm_item(
        parsed=extract_json_object(content_text),
        event=event,
        frame=frame,
    )

    return {
        "frame": frame,
        "raw_response": content_text,
        "parsed": parsed,
    }



def merge_unique_lists(lists):
    merged = []
    seen = set()

    for values in lists:
        if not isinstance(values, list):
            continue

        for value in values:
            key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            if key in seen:
                continue
            seen.add(key)
            merged.append(value)

    return merged


def aggregate_single_frame_results(event, frame_results, proximity_evidence):
    parsed_items = [
        item.get("parsed", {})
        for item in frame_results
        if isinstance(item.get("parsed"), dict) and not item.get("parsed", {}).get("parse_error")
    ]

    if not parsed_items:
        return {
            "semantic_event_id": event.get("semantic_event_id"),
            "context_window_id": event.get("context_window_id"),
            "vlm_event_name_tr": event.get("event_name") or "Video olayı",
            "vlm_event_type": "unclear",
            "vlm_description_tr": "VLM kare yorumları güvenilir JSON formatında ayrıştırılamadı.",
            "visible_entities": [],
            "critical_moment_timestamp": event.get("peak_timestamp"),
            "risk_level": max_risk([item.get("risk_level") for item in proximity_evidence]) if proximity_evidence else "medium",
            "risk_reason_tr": "VLM çıktısı ayrıştırılamadığı için risk proximity/semantic kanıtlarla değerlendirilmiştir.",
            "operator_actions_tr": [
                "Olay zaman aralığını manuel olarak incele.",
                "Yakınlık ve hareket kanıtlarını operatör ekranında doğrula.",
                "Belirsizliği rapora ekle."
            ],
            "evidence_tr": [
                "Semantic event metadata",
                "Proximity risk evidence"
            ],
            "confidence": 0.3,
            "limitations_tr": "VLM kare yorumları ayrıştırılamadı.",
            "parse_error": True,
        }

    proximity_max = max_risk([item.get("risk_level") for item in proximity_evidence]) if proximity_evidence else "low"
    vlm_max = max_risk([item.get("risk_level") for item in parsed_items])
    final_risk = max_risk([proximity_max, vlm_max])

    def item_rank(item):
        role_bonus = 1 if item.get("frame_role") == "peak" else 0
        return (
            RISK_RANK.get(normalize_risk(item.get("risk_level")), 1),
            role_bonus,
            float(item.get("confidence", 0.0) or 0.0)
        )

    main_item = sorted(parsed_items, key=item_rank, reverse=True)[0]

    descriptions = []
    risk_reasons = []

    for item in parsed_items:
        role = item.get("frame_role", "frame")
        ts = item.get("frame_timestamp", "")
        desc = item.get("vlm_description_tr")
        reason = item.get("risk_reason_tr")

        if desc:
            descriptions.append(f"{role}/{ts}: {desc}")
        if reason:
            risk_reasons.append(f"{role}/{ts}: {reason}")

    confidences = []
    for item in parsed_items:
        try:
            confidences.append(float(item.get("confidence", 0.0)))
        except Exception:
            pass

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

    evidence = merge_unique_lists([
        item.get("evidence_tr", [])
        for item in parsed_items
    ])

    visible_entities = merge_unique_lists([
        item.get("visible_entities", [])
        for item in parsed_items
    ])

    actions = merge_unique_lists([
        item.get("operator_actions_tr", [])
        for item in parsed_items
    ])

    if proximity_evidence:
        evidence.append("Proximity / relation risk evidence")

    if not actions:
        actions = [
            "Olay zaman aralığını operatör ekranında incele.",
            "Görsel ve ilişkisel hareket kanıtlarını doğrula.",
            "Gerekirse saha sorumlusuna bilgi ver."
        ]

    return {
        "semantic_event_id": event.get("semantic_event_id"),
        "context_window_id": event.get("context_window_id"),
        "vlm_event_name_tr": main_item.get("vlm_event_name_tr") or event.get("event_name") or "Video olayı",
        "vlm_event_type": main_item.get("vlm_event_type") or "unclear",
        "vlm_description_tr": " ".join(descriptions) if descriptions else main_item.get("vlm_description_tr", ""),
        "visible_entities": visible_entities,
        "critical_moment_timestamp": main_item.get("critical_moment_timestamp") or event.get("peak_timestamp"),
        "risk_level": final_risk,
        "risk_reason_tr": " ".join(risk_reasons) if risk_reasons else main_item.get("risk_reason_tr", ""),
        "operator_actions_tr": actions,
        "evidence_tr": evidence if evidence else ["Start/peak/end frame VLM interpretations"],
        "confidence": round(max(0.0, min(1.0, avg_confidence)), 4),
        "limitations_tr": (
            "VLM sunucusu tek promptta bir görsel kabul ettiği için start/peak/end kareleri ayrı ayrı yorumlanmış "
            "ve sonuçlar olay seviyesinde birleştirilmiştir."
        ),
    }



def ask_vlm_about_event(
    event,
    selected_frames,
    proximity_evidence,
    server_url,
    model,
    timeout,
    temperature,
    max_tokens,
):
    frame_results = []

    for frame in selected_frames:
        try:
            result = ask_vlm_about_single_frame(
                event=event,
                frame=frame,
                proximity_evidence=proximity_evidence,
                server_url=server_url,
                model=model,
                timeout=timeout,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            result = {
                "frame": frame,
                "raw_response": "",
                "parsed": {
                    "parse_error": True,
                    "frame_role": frame.get("role"),
                    "frame_timestamp": frame.get("timestamp"),
                    "raw_text": f"VLM frame call failed: {exc}",
                },
            }

        frame_results.append(result)

    aggregated = aggregate_single_frame_results(
        event=event,
        frame_results=frame_results,
        proximity_evidence=proximity_evidence,
    )

    return {
        "semantic_event_id": event.get("semantic_event_id"),
        "context_window_id": event.get("context_window_id"),
        "selected_frames": selected_frames,
        "proximity_evidence": proximity_evidence,
        "frame_level_results": frame_results,
        "raw_response": json.dumps(frame_results, ensure_ascii=False),
        "parsed": aggregated,
    }

def fallback_interpretation(event, selected_frames, proximity_evidence, reason):
    risk_levels = [item.get("risk_level") for item in proximity_evidence]
    risk_level = max_risk(risk_levels) if risk_levels else "medium"

    event_name = event.get("event_name") or event.get("event_name_tr") or "Video olayı"

    return {
        "semantic_event_id": event.get("semantic_event_id"),
        "context_window_id": event.get("context_window_id"),
        "selected_frames": selected_frames,
        "proximity_evidence": proximity_evidence,
        "raw_response": "",
        "parsed": {
            "semantic_event_id": event.get("semantic_event_id"),
            "context_window_id": event.get("context_window_id"),
            "vlm_event_name_tr": event_name,
            "vlm_event_type": "unclear",
            "vlm_description_tr": "VLM yorumu üretilemedi; olay mevcut semantik ve yakınlık kanıtlarıyla sınırlı değerlendirilmiştir.",
            "visible_entities": [],
            "critical_moment_timestamp": event.get("peak_timestamp"),
            "risk_level": risk_level,
            "risk_reason_tr": "VLM çağrısı başarısız olduğu için risk seviyesi proximity/semantic kanıtlara göre korunmuştur.",
            "operator_actions_tr": [
                "Olay zaman aralığını manuel olarak incele.",
                "Yakınlık ve hareket kanıtlarını operatör ekranında doğrula.",
                "Belirsizliği rapora ekle."
            ],
            "evidence_tr": [
                "Semantic event metadata",
                "Proximity risk evidence"
            ],
            "confidence": 0.3,
            "limitations_tr": reason,
            "parse_error": True,
        },
    }



def build_operator_actions(event_type, risk_level):
    risk_level = normalize_risk(risk_level)
    event_type = normalize_event_type(event_type)

    actions = []

    if risk_level in {"critical", "high"}:
        actions.append("Olay zaman aralığını öncelikli inceleme kuyruğuna al.")

    if event_type == "person_vehicle_risk":
        actions.extend([
            "Kişi-araç yakınlaşmasının görüldüğü kareleri operatör ekranında doğrula.",
            "Araç hareket yönü ile yaya/kalabalık konumunu birlikte kontrol et.",
            "Gerekirse saha güvenlik sorumlusuna kişi-araç yakınlaşması bilgisini ilet."
        ])

    elif event_type == "vehicle_vehicle_risk":
        actions.extend([
            "Araçlar arasındaki yakınlaşma veya düşük mesafe anını doğrula.",
            "Araçların yön, manevra ve durma/ilerleme davranışını kontrol et.",
            "Gerekirse saha trafik/sürüş güvenliği sorumlusuna bilgi ver."
        ])

    elif event_type == "crowd_movement":
        actions.extend([
            "Kalabalığın yönünü, yoğunluğunu ve araçlarla kesişip kesişmediğini kontrol et.",
            "Kalabalık hareketinde sıkışma, panik veya güvenlik riski belirtisi olup olmadığını incele.",
            "Gerekirse saha güvenlik ekibini ilgili zaman aralığına yönlendir."
        ])

    elif event_type == "accident_possible":
        actions.extend([
            "Olası kaza belirtisi bulunan kareleri yakınlaştırarak incele.",
            "Hareketsiz kişi, devrilen araç veya çarpışma belirtisi olup olmadığını doğrula.",
            "Şüphe güçlüyse acil müdahale prosedürünü başlatmak için sorumlu operatöre bildir."
        ])

    elif event_type == "security_attention":
        actions.extend([
            "Güvenlik dikkati gerektiren hareket veya kalabalık davranışını incele.",
            "Olayın normal saha faaliyeti mi yoksa olağandışı hareket mi olduğunu doğrula.",
            "Gerekirse olay zaman aralığını güvenlik raporuna ekle."
        ])

    elif event_type == "normal_activity":
        actions.extend([
            "Olayı düşük öncelikli izleme kaydına al.",
            "Yakınlık/risk kanıtı varsa ilgili kareleri yine de doğrula.",
            "Ek risk belirtisi yoksa standart izlemeye devam et."
        ])

    else:
        actions.extend([
            "Olay zaman aralığını manuel olarak incele.",
            "VLM yorumu ile proximity risk kanıtlarını karşılaştır.",
            "Belirsizliği karar destek raporunda açıkça belirt."
        ])

    # Tekilleştir ve fazla uzatmayı engelle.
    clean = []
    seen = set()
    for action in actions:
        if action in seen:
            continue
        seen.add(action)
        clean.append(action)

    return clean[:5]


def build_turkish_description(event_type, risk_level, source_event, parsed):
    event_type = normalize_event_type(event_type)
    risk_level = normalize_risk(risk_level)

    critical_time = (
        parsed.get("critical_moment_timestamp")
        or source_event.get("peak_timestamp")
        or source_event.get("peak_time")
    )

    if event_type == "person_vehicle_risk":
        return (
            f"VLM kare yorumuna göre kişi/kalabalık ile araç hareketi aynı olay penceresinde kesişmektedir. "
            f"Kritik an yaklaşık {critical_time}; risk seviyesi {risk_level}."
        )

    if event_type == "vehicle_vehicle_risk":
        return (
            f"VLM kare yorumuna göre araçlar arasında düşük mesafe veya yakın hareket ilişkisi bulunmaktadır. "
            f"Kritik an yaklaşık {critical_time}; risk seviyesi {risk_level}."
        )

    if event_type == "crowd_movement":
        return (
            f"VLM kare yorumuna göre olay penceresinde belirgin kalabalık hareketliliği görülmektedir. "
            f"Kritik an yaklaşık {critical_time}; risk seviyesi {risk_level}."
        )

    if event_type == "accident_possible":
        return (
            f"VLM kare yorumuna göre olay penceresinde kaza ihtimali açısından incelenmesi gereken görsel işaretler vardır. "
            f"Kritik an yaklaşık {critical_time}; risk seviyesi {risk_level}."
        )

    if event_type == "security_attention":
        return (
            f"VLM kare yorumuna göre olay penceresi güvenlik dikkati gerektiren hareketler içerebilir. "
            f"Kritik an yaklaşık {critical_time}; risk seviyesi {risk_level}."
        )

    if event_type == "normal_activity":
        return (
            f"VLM kare yorumuna göre olay penceresi çoğunlukla normal faaliyet görünümündedir. "
            f"Kritik an yaklaşık {critical_time}; risk seviyesi {risk_level}."
        )

    return (
        f"VLM kare yorumu olay türünü kesinleştiremedi. "
        f"Kritik an yaklaşık {critical_time}; risk seviyesi {risk_level}."
    )


def build_turkish_risk_reason(event_type, risk_level, proximity_max):
    event_type = normalize_event_type(event_type)
    risk_level = normalize_risk(risk_level)
    proximity_max = normalize_risk(proximity_max)

    if event_type == "person_vehicle_risk":
        return (
            f"Kişi/kalabalık ile araçların aynı zaman aralığında yakın görünmesi ve proximity risk seviyesinin "
            f"{proximity_max} olması nedeniyle nihai risk {risk_level} olarak tutulmuştur."
        )

    if event_type == "vehicle_vehicle_risk":
        return (
            f"Araçlar arasında yakın hareket ilişkisi ve proximity kanıtı bulunduğu için nihai risk "
            f"{risk_level} olarak değerlendirilmiştir."
        )

    if event_type == "crowd_movement":
        return (
            f"Kalabalık hareketliliği, yoğunluk ve proximity kanıtları birlikte değerlendirildiği için nihai risk "
            f"{risk_level} seviyesindedir."
        )

    if event_type == "accident_possible":
        return (
            f"VLM görsel yorumu olası kaza belirtisi ürettiği ve proximity kanıtı bulunduğu için risk "
            f"{risk_level} seviyesinde tutulmuştur."
        )

    if event_type == "security_attention":
        return (
            f"Olay güvenlik dikkati gerektiren görsel hareketler içerebildiği için risk "
            f"{risk_level} olarak değerlendirilmiştir."
        )

    return (
        f"Risk seviyesi VLM kare yorumu ve proximity kanıtlarının birlikte değerlendirilmesiyle "
        f"{risk_level} olarak belirlenmiştir."
    )


def sanitize_parsed_event(parsed, source_event, proximity_evidence):
    if not isinstance(parsed, dict):
        parsed = {}

    proximity_max = max_risk([item.get("risk_level") for item in proximity_evidence])

    parsed_risk = normalize_risk(parsed.get("risk_level") or parsed.get("risk"))
    risk_level = max_risk([parsed_risk, proximity_max])

    event_type = normalize_event_type(parsed.get("vlm_event_type") or parsed.get("type"))

    visible_entities = parsed.get("visible_entities")
    if visible_entities is None:
        visible_entities = parsed.get("entities")
    visible_entities = ensure_list(visible_entities)[:8]

    evidence = parsed.get("evidence_tr")
    if evidence is None:
        evidence = parsed.get("evidence")
    evidence = ensure_list(evidence)

    if "Başlangıç/peak/bitiş kareleri VLM yorumu" not in evidence:
        evidence.append("Başlangıç/peak/bitiş kareleri VLM yorumu")

    if proximity_evidence and "Proximity risk kanıtı" not in evidence:
        evidence.append("Proximity risk kanıtı")

    confidence = parsed.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    description_tr = build_turkish_description(
        event_type=event_type,
        risk_level=risk_level,
        source_event=source_event,
        parsed=parsed,
    )

    risk_reason_tr = build_turkish_risk_reason(
        event_type=event_type,
        risk_level=risk_level,
        proximity_max=proximity_max,
    )

    return {
        "semantic_event_id": parsed.get("semantic_event_id") or source_event.get("semantic_event_id"),
        "context_window_id": parsed.get("context_window_id") or source_event.get("context_window_id"),
        "vlm_event_name_tr": parsed.get("vlm_event_name_tr") or source_event.get("event_name") or "Video olayı",
        "vlm_event_type": event_type,
        "vlm_description_tr": description_tr,
        "visible_entities": visible_entities,
        "critical_moment_timestamp": parsed.get("critical_moment_timestamp") or source_event.get("peak_timestamp"),
        "risk_level": risk_level,
        "risk_reason_tr": risk_reason_tr,
        "operator_actions_tr": build_operator_actions(event_type, risk_level),
        "evidence_tr": evidence[:6],
        "confidence": confidence,
        "limitations_tr": (
            "VLM yorumu temsilci karelere dayanır; nihai karar için operatör doğrulaması gerekir."
        ),
    }


def build_report(
    semantic_report,
    detail_frames,
    proximity_report,
    server_url,
    model,
    max_events,
    max_images_per_event,
    timeout,
    temperature,
    max_tokens,
):
    semantic_events = semantic_report.get("semantic_events", [])
    selected_events = semantic_events[:max_events] if max_events > 0 else semantic_events

    outputs = []

    for idx, event in enumerate(selected_events, start=1):
        print(f"Analyzing semantic event {idx}/{len(selected_events)}: {event.get('semantic_event_id')}")

        selected_frames = select_event_frames(
            event=event,
            detail_frames=detail_frames,
            max_images_per_event=max_images_per_event,
        )

        proximity_evidence = select_proximity_evidence_for_event(
            event=event,
            proximity_report=proximity_report,
            max_items=8,
        )

        if not selected_frames:
            item = fallback_interpretation(
                event=event,
                selected_frames=[],
                proximity_evidence=proximity_evidence,
                reason="Temsilci event frame seçilemedi."
            )
        else:
            try:
                item = ask_vlm_about_event(
                    event=event,
                    selected_frames=selected_frames,
                    proximity_evidence=proximity_evidence,
                    server_url=server_url,
                    model=model,
                    timeout=timeout,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                item = fallback_interpretation(
                    event=event,
                    selected_frames=selected_frames,
                    proximity_evidence=proximity_evidence,
                    reason=f"VLM çağrısı başarısız: {exc}"
                )

        item["normalized_interpretation"] = sanitize_parsed_event(
            parsed=item.get("parsed", {}),
            source_event=event,
            proximity_evidence=proximity_evidence,
        )

        outputs.append(item)

    risk_levels = [
        item["normalized_interpretation"].get("risk_level")
        for item in outputs
    ]

    parse_error_count = sum(
        1 for item in outputs
        if isinstance(item.get("parsed"), dict) and item["parsed"].get("parse_error")
    )

    report = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "event_vlm_reasoner",
            "version": "0.1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "input": {
            "semantic_event_count": len(semantic_events),
            "analyzed_event_count": len(outputs),
            "detail_frame_count": len(detail_frames.get("frames", [])),
            "proximity_risk_event_count": len(proximity_report.get("risk_events", [])),
        },
        "model": {
            "server_url": server_url,
            "model": model,
            "max_images_per_event": max_images_per_event,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        "summary": {
            "vlm_reasoned_event_count": len(outputs),
            "parse_error_count": parse_error_count,
            "overall_vlm_risk": max_risk(risk_levels),
        },
        "vlm_event_interpretations": outputs,
        "important_notes_tr": [
            "VLM yorumu temsilci karelere dayanır; video akışının tamamını birebir temsil etmeyebilir.",
            "Bu modül kimlik veya yüz tanıma yapmaz.",
            "Risk yorumları karar destek amaçlıdır; operatör doğrulaması gerekir.",
            "Proximity risk kanıtları, VLM yorumuna yardımcı bağlam olarak verilmiştir."
        ]
    }

    return report


def build_markdown(report):
    lines = []

    lines.append("# CASIT / ÇAŞIT — Event VLM Reasoning Report")
    lines.append("")
    lines.append("Bu rapor, semantic event pencerelerinin başlangıç / peak / bitiş karelerini VLM ile yorumlar.")
    lines.append("")
    lines.append("## Özet")
    lines.append("")
    s = report.get("summary", {})
    lines.append(f"- VLM ile yorumlanan olay sayısı: `{s.get('vlm_reasoned_event_count')}`")
    lines.append(f"- Parse error sayısı: `{s.get('parse_error_count')}`")
    lines.append(f"- Genel VLM risk: `{s.get('overall_vlm_risk')}`")
    lines.append("")

    lines.append("## Olay Yorumları")
    lines.append("")

    for item in report.get("vlm_event_interpretations", []):
        ev = item.get("normalized_interpretation", {})
        lines.append(f"### {ev.get('semantic_event_id')} — {ev.get('vlm_event_name_tr')}")
        lines.append("")
        lines.append(f"- Context window: `{ev.get('context_window_id')}`")
        lines.append(f"- Olay tipi: `{ev.get('vlm_event_type')}`")
        lines.append(f"- Risk seviyesi: `{ev.get('risk_level')}`")
        lines.append(f"- Kritik an: `{ev.get('critical_moment_timestamp')}`")
        lines.append(f"- Güven: `{ev.get('confidence')}`")
        lines.append("")
        lines.append("**Açıklama:**")
        lines.append("")
        lines.append(ev.get("vlm_description_tr", ""))
        lines.append("")
        lines.append("**Risk gerekçesi:**")
        lines.append("")
        lines.append(ev.get("risk_reason_tr", ""))
        lines.append("")
        lines.append("**Görülen unsurlar:**")
        for entity in ev.get("visible_entities", []):
            lines.append(f"- {entity}")
        lines.append("")
        lines.append("**Kanıtlar:**")
        for evidence in ev.get("evidence_tr", []):
            lines.append(f"- {evidence}")
        lines.append("")
        lines.append("**Operatör aksiyonları:**")
        for action in ev.get("operator_actions_tr", []):
            lines.append(f"- {action}")
        lines.append("")
        lines.append("**Sınırlılık:**")
        lines.append("")
        lines.append(ev.get("limitations_tr", ""))
        lines.append("")

    lines.append("## Genel Sınırlılıklar")
    lines.append("")
    for note in report.get("important_notes_tr", []):
        lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--semantic-event", required=True)
    parser.add_argument("--detail-frames", required=True)
    parser.add_argument("--proximity-risk", required=False)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)

    parser.add_argument("--server-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-events", type=int, default=5)
    parser.add_argument("--max-images-per-event", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=260)

    args = parser.parse_args()

    semantic_report = load_json(Path(args.semantic_event))
    detail_frames = load_json(Path(args.detail_frames))
    proximity_report = load_json(Path(args.proximity_risk)) if args.proximity_risk else {}

    report = build_report(
        semantic_report=semantic_report,
        detail_frames=detail_frames,
        proximity_report=proximity_report,
        server_url=args.server_url,
        model=args.model,
        max_events=args.max_events,
        max_images_per_event=args.max_images_per_event,
        timeout=args.timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    save_json(report, Path(args.output_json))
    save_text(build_markdown(report), Path(args.output_md))

    print("CASIT / ÇAŞIT Event VLM Reasoner")
    print("--------------------------------")
    print("Analyzed events  :", report["summary"]["vlm_reasoned_event_count"])
    print("Parse errors     :", report["summary"]["parse_error_count"])
    print("Overall VLM risk :", report["summary"]["overall_vlm_risk"])
    print("Output JSON      :", args.output_json)
    print("Output MD        :", args.output_md)
    print("--------------------------------")


if __name__ == "__main__":
    main()
