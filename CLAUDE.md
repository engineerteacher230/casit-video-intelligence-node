# CLAUDE.md — CASIT / ÇAŞIT Developer Guide

This file gives Claude or any AI coding assistant the project context, architectural rules, and development constraints.

## Project Identity

Human-facing name: ÇAŞIT  
Technical name: CASIT

Use CASIT for code, folders, commands, repository names, and ASCII-safe identifiers.  
Use ÇAŞIT only in human-facing reports and documentation.

## Current Stage

CASIT is currently at:

CASIT v0.3.1

The system is a working offline video intelligence MVP.

It can analyze an unknown video, infer the scene type with Qwen/VLM, select a domain policy, focus YOLO detection, track objects, refine track quality, build evidence, and generate Turkish reports.

## Main Architecture

Pipeline:

1. video metadata reader
2. coarse frame extractor
3. event energy scanner
4. context window planner
5. detail window extractor
6. scene scout extractor
7. scene prior agent using Qwen/VLM
8. domain policy selector
9. domain-aware YOLO detector
10. domain-aware YOLO tracker
11. track quality refiner
12. event evidence builder
13. final Turkish report builder
14. semantic event builder

Main script:

scripts/run_casit_full_pipeline.sh

## Core Design Principle

CASIT is general-purpose.

Do not hard-code the system around football, traffic, construction, or any single video type.

The correct logic is:

unknown video
→ VLM scene understanding
→ domain policy selection
→ focused detection
→ tracking
→ evidence
→ semantic event reasoning
→ report

## Critical Reasoning Rules

Detection count is not the real physical object count.

Raw track count is not always reliable because tracks may fragment.

Stable track count is a better estimate, but still not absolute truth.

Motion candidate is not a semantic event.

Context window is a macro event candidate.

Semantic event is an interpreted meaningful event.

## Policy Selection Rule

scene_type is stronger than domain.

Example:

scene_type = construction_site  
domain = traffic

Correct selected policy:

construction_site_general

Do not let a generic domain such as traffic override a more specific scene_type.

## Current Important Policies

Policy file:

config/domain_policies.json

Known policies:

- unknown_general
- traffic_general
- industrial_factory
- warehouse_forklift
- security_general
- crowd_general
- sports_general
- construction_site_general

## Important Recent Fixes

1. If a YOLO label exists in both allowed and blocked labels, allowed wins.
2. domain_aware_yolo_detector.py accepts focused policy input.
3. run_casit_full_pipeline.sh writes every run to a timestamped run directory.
4. semantic_event_builder.py correctly reads nested scene_prior JSON.
5. construction_site now selects construction_site_general instead of traffic_general.

## Current Tested Videos

insan.mp4:
football_match_goal_celebration / sports

aaa.mp4:
roundabout_traffic / traffic

bbbbb.mp4:
street_confrontation / traffic

cccc.mp4:
construction_site / traffic
corrected selected policy: construction_site_general

## Do Not Commit

Do not commit:

- .venv/
- .venv-vllm/
- raw videos
- extracted frames
- outputs/runs/
- model weights
- cache files
- ~/casit-data/

## Local Data Assumption

Project root:

~/casit/projects/casit-video-intelligence-node

Local data root:

~/casit-data

Raw videos:

~/casit-data/datasets/raw_videos

Run outputs:

~/casit-data/outputs/runs

Latest run shortcut:

~/casit-data/outputs/runs/latest

## How To Run

Activate YOLO environment:

source .venv/bin/activate

Make sure VLM server is running at:

http://127.0.0.1:8000

Run full pipeline:

./scripts/run_casit_full_pipeline.sh ~/casit-data/datasets/raw_videos/cccc.mp4

## Development Priorities

Next development steps must stay strictly aligned with TEKNOFEST Scenario 3.

Priority order:

1. Follow SCENARIO_3_SCOPE.md as the scope lock.
2. Standardize the official Scenario 3 JSON output schema.
3. Improve semantic event reasoning.
4. Add VLM-based event reasoning per context window.
5. Add risk scoring.
6. Add Turkish operator action recommendations.
7. Add Turkish decision-support summary.
8. Add explainable evidence mapping.
9. Add KPI and benchmark outputs.
10. Prepare competition documentation and demo materials.

## Scenario 3 Output Target

The target output should include:

- summary_tr
- events
- start_time
- end_time
- peak_time
- event_type
- event_name_tr
- risk_level
- evidence
- operator_actions_tr
- overall_risk
- decision_support_tr
- limitations_tr

## Ethical Boundaries

Do not build or suggest unauthorized camera access.

Do not perform face recognition.

Do not perform identity recognition.

Do not track named individuals.

Use only owned, permitted, or test videos.

## Preferred AI Assistant Behavior

When modifying the project:

- Make small patches.
- Verify syntax after each patch.
- Do not rewrite working modules unnecessarily.
- Preserve general-purpose Scenario 3 architecture.
- Do not make the system football-specific.
- Do not shift the project toward camera monitoring.
- Do not confuse frame detections with real object counts.
- Prioritize event, risk, action, Turkish summary, and JSON output.
- Keep reports Turkish.
- Keep code identifiers ASCII-safe.
