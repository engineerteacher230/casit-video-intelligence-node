import argparse
import base64
import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

import requests


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


def encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_json_object(text: str) -> dict:
    """
    VLM bazen JSON dışına açıklama ekleyebilir.
    Bu fonksiyon ilk JSON objesini güvenli şekilde ayıklamaya çalışır.
    """
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
        return {
            "parse_error": True,
            "raw_text": text
        }

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {
            "parse_error": True,
            "raw_text": text
        }


def select_representative_frames(frames: list, max_frames: int) -> list:
    if len(frames) <= max_frames:
        return frames

    selected = []

    for i in range(max_frames):
        index = round(i * (len(frames) - 1) / (max_frames - 1))
        selected.append(frames[index])

    return selected


def ask_vlm_about_frame(
    image_path: str,
    timestamp: str,
    server_url: str,
    model: str,
    timeout: int = 180
) -> dict:
    image_b64 = encode_image_base64(image_path)

    prompt = f"""
You are the Scene Prior Agent of CASIT / ÇAŞIT.

Analyze this sampled video frame from timestamp {timestamp}.

Task:
Determine the scene context for configuring YOLO object detection.

Return STRICT JSON only. No markdown. No explanation outside JSON.

Schema:
{{
  "timestamp": "{timestamp}",
  "scene_domain": "sports | traffic | crowd | indoor | outdoor | unknown",
  "scene_type": "short_snake_case_scene_type",
  "is_football_or_soccer_scene": true,
  "is_goal_celebration_possible": true,
  "confidence": 0.0,
  "expected_visual_elements": [],
  "expected_yolo_labels": [],
  "context_inconsistent_yolo_labels": [],
  "short_scene_summary_en": "",
  "short_scene_summary_tr": ""
}}

Important:
- If the scene looks like football/soccer, expected YOLO labels should prioritize "person" and "sports ball".
- Objects such as sheep, horse, baseball bat, baseball glove are context-inconsistent in a football goal celebration unless visually undeniable.
- Do not identify people. Do not infer identities.
"""

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 350
    }

    response = requests.post(
        f"{server_url}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=timeout
    )

    if not response.ok:
        print("---- VLM HTTP ERROR ----")
        print("Status code:", response.status_code)
        print("Response text:")
        print(response.text)
        response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    parsed = extract_json_object(content)

    return {
        "timestamp": timestamp,
        "image_path": image_path,
        "raw_response": content,
        "parsed": parsed
    }


def build_scene_prior_from_observations(observations: list) -> dict:
    parsed_items = [
        obs["parsed"]
        for obs in observations
        if isinstance(obs.get("parsed"), dict) and not obs["parsed"].get("parse_error")
    ]

    if not parsed_items:
        return {
            "scene_type": "unknown",
            "domain": "unknown",
            "confidence": 0.0,
            "description_tr": "VLM çıktıları güvenilir JSON formatında ayrıştırılamadı.",
            "allowed_labels": ["person"],
            "blocked_labels": [],
            "validation_status": "needs_review"
        }

    football_votes = sum(
        1 for item in parsed_items
        if item.get("is_football_or_soccer_scene") is True
    )

    goal_votes = sum(
        1 for item in parsed_items
        if item.get("is_goal_celebration_possible") is True
    )

    scene_domains = Counter(item.get("scene_domain", "unknown") for item in parsed_items)
    scene_types = Counter(item.get("scene_type", "unknown") for item in parsed_items)

    expected_labels = Counter()
    inconsistent_labels = Counter()

    confidence_values = []

    for item in parsed_items:
        try:
            confidence_values.append(float(item.get("confidence", 0.0)))
        except Exception:
            pass

        for label in item.get("expected_yolo_labels", []):
            expected_labels[label] += 1

        for label in item.get("context_inconsistent_yolo_labels", []):
            inconsistent_labels[label] += 1

    avg_confidence = (
        sum(confidence_values) / len(confidence_values)
        if confidence_values else 0.0
    )

    is_football = football_votes >= max(1, len(parsed_items) // 2)
    is_goal_celebration = goal_votes >= max(1, len(parsed_items) // 2)

    if is_football:
        scene_type = "football_match_goal_celebration" if is_goal_celebration else "football_match"
        domain = "sports"

        allowed_labels = ["person", "sports ball"]
        blocked_labels = [
            "sheep",
            "horse",
            "baseball bat",
            "baseball glove",
            "cow",
            "dog",
            "elephant",
            "zebra",
            "giraffe"
        ]

        description_tr = (
            "Video, futbol/soccer maçı bağlamında görünmektedir. "
            "Görüntüler gol sonrası sevinç veya oyuncu toplanması içeriyor olabilir. "
            "YOLO tespitinde kişi ve spor topu sınıfları öncelikli güvenilir kabul edilmelidir."
        )
    else:
        scene_type = scene_types.most_common(1)[0][0]
        domain = scene_domains.most_common(1)[0][0]

        allowed_labels = [
            label for label, count in expected_labels.most_common()
            if count >= 1
        ]

        if "person" not in allowed_labels:
            allowed_labels.insert(0, "person")

        blocked_labels = [
            label for label, count in inconsistent_labels.most_common()
            if count >= 1
        ]

        description_tr = (
            "VLM sahne bağlamını genel olarak çıkardı ancak futbol sahnesi çoğunlukla doğrulanmadı. "
            "YOLO sınıf politikası VLM gözlemlerine göre sınırlı güvenle üretildi."
        )

    return {
        "scene_type": scene_type,
        "domain": domain,
        "confidence": round(avg_confidence, 4),
        "football_votes": football_votes,
        "goal_celebration_votes": goal_votes,
        "observation_count": len(parsed_items),
        "description_tr": description_tr,
        "object_policy": "whitelist_first",
        "allowed_labels": allowed_labels,
        "blocked_labels": blocked_labels,
        "class_confidence_thresholds": {
            "person": 0.35,
            "sports ball": 0.20
        },
        "validation_rules": {
            "reject_context_impossible_objects": True,
            "require_review_for_blocked_labels": True,
            "do_not_use_identity_recognition": True
        },
        "llm_instruction_en": (
            "Use the scene prior to configure YOLO. "
            "If the scene is football/soccer, prioritize person and sports ball detections. "
            "Treat sheep, horse, baseball bat and baseball glove as context-inconsistent unless strongly supported."
        ),
        "validation_status": "approved" if avg_confidence >= 0.50 else "needs_review"
    }


def run_scene_prior_agent(
    scene_scout_report_path: str,
    output_json_path: str,
    server_url: str,
    model: str,
    max_frames: int
) -> dict:
    report = load_json(scene_scout_report_path)

    frames = report["frames"]
    selected_frames = select_representative_frames(frames, max_frames=max_frames)

    observations = []

    for frame in selected_frames:
        print(f"Analyzing frame: {frame['timestamp']}")

        observation = ask_vlm_about_frame(
            image_path=frame["image_path"],
            timestamp=frame["timestamp"],
            server_url=server_url,
            model=model
        )

        observations.append(observation)

    scene_prior = build_scene_prior_from_observations(observations)

    output = {
        "project": {
            "technical_name": "CASIT",
            "display_name": "ÇAŞIT",
            "module": "scene_prior_agent",
            "created_at": datetime.now().isoformat(timespec="seconds")
        },
        "source_report": str(Path(scene_scout_report_path).resolve()),
        "vlm": {
            "server_url": server_url,
            "model": model,
            "max_frames_used": max_frames,
            "image_per_prompt": 1
        },
        "video": report["video"],
        "scene_prior": scene_prior,
        "observations": observations
    }

    save_json(output, output_json_path)

    return output


def main():
    parser = argparse.ArgumentParser(
        description="CASIT / ÇAŞIT Scene Prior Agent using local VLM via vLLM."
    )

    parser.add_argument(
        "--scene-scout-report",
        required=True,
        help="Path to scene_scout_report.json"
    )

    parser.add_argument(
        "--output-json",
        default=str(Path.home() / "casit-data/outputs/json/scene_prior.json"),
        help="Path to output scene_prior.json"
    )

    parser.add_argument(
        "--server-url",
        default="http://127.0.0.1:8000",
        help="Local vLLM OpenAI-compatible server URL"
    )

    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-VL-3B-Instruct",
        help="Served VLM model name"
    )

    parser.add_argument(
        "--max-frames",
        type=int,
        default=6,
        help="Number of representative scout frames to analyze"
    )

    args = parser.parse_args()

    output = run_scene_prior_agent(
        scene_scout_report_path=args.scene_scout_report,
        output_json_path=args.output_json,
        server_url=args.server_url,
        model=args.model,
        max_frames=args.max_frames
    )

    prior = output["scene_prior"]

    print("\nCASIT / ÇAŞIT Scene Prior Agent Report")
    print("--------------------------------------")
    print(f"Video file             : {output['video']['file_name']}")
    print(f"Model                  : {output['vlm']['model']}")
    print(f"Observations used      : {prior.get('observation_count', len(output.get('observations', [])))}")
    print(f"Scene type             : {prior.get('scene_type', 'N/A')}")
    print(f"Domain                 : {prior.get('domain', 'N/A')}")
    print(f"Confidence             : {prior.get('confidence', 'N/A')}")
    print(f"Football votes         : {prior.get('football_votes', 'N/A')}")
    print(f"Goal celebration votes : {prior.get('goal_celebration_votes', 'N/A')}")
    print(f"Allowed labels         : {prior.get('allowed_labels', 'N/A')}")
    print(f"Blocked labels         : {prior.get('blocked_labels', 'N/A')}")
    print(f"Validation status      : {prior.get('validation_status', 'N/A')}")
    print(f"JSON output            : {args.output_json}")
    print("--------------------------------------\n")


if __name__ == "__main__":
    main()
