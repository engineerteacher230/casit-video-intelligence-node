# CASIT / ÇAŞIT Project Status

## Current Version

CASIT v0.3.1

Status:

Working offline video intelligence MVP.

The system can process an unknown video, infer scene context with Qwen/VLM, select a domain policy, focus YOLO detection, track objects, refine tracking quality, build evidence, and generate Turkish reports.

---

## Current Architecture

Main pipeline:

1. Video metadata reader
2. Coarse frame extractor
3. Event energy scanner
4. Context window planner
5. Detail window extractor
6. Scene scout extractor
7. Qwen/VLM scene prior agent
8. Domain policy selector
9. Domain-aware YOLO detector
10. Domain-aware YOLO tracker
11. Track quality refiner
12. Event evidence builder
13. Final video report builder
14. Semantic event builder

Main script:

scripts/run_casit_full_pipeline.sh

---

## Current Working Command

From project root:

cd ~/casit/projects/casit-video-intelligence-node

Activate environment:

source .venv/bin/activate

Run full pipeline:

./scripts/run_casit_full_pipeline.sh ~/casit-data/datasets/raw_videos/cccc.mp4

---

## Current Data Layout

Project root:

~/casit/projects/casit-video-intelligence-node

Data root:

~/casit-data

Raw videos:

~/casit-data/datasets/raw_videos

Run outputs:

~/casit-data/outputs/runs

Latest run shortcut:

~/casit-data/outputs/runs/latest

---

## Tested Videos

### insan.mp4

Interpreted scene:

football_match_goal_celebration

Domain:

sports

Policy:

sports_general

### aaa.mp4

Interpreted scene:

roundabout_traffic

Domain:

traffic

Policy:

traffic_general

### bbbbb.mp4

Interpreted scene:

street_confrontation

Domain:

traffic

Policy:

traffic_general

Semantic event:

Sokak / kalabalık gerilim olayı

### cccc.mp4

Interpreted scene:

construction_site

Domain:

traffic

Initial problem:

The selector first chose traffic_general because domain=traffic.

Fix:

Policy selector priority was updated so scene_type is stronger than domain.

Correct current policy:

construction_site_general

---

## Important Fixes Completed

### 1. Allowed labels win over blocked labels

Problem:

A label could appear in both allowed and blocked lists.

Fix:

If a label is allowed by the domain policy, it is removed from blocked labels.

### 2. Detector now uses focused policy

Problem:

domain_aware_yolo_detector.py was reading scene_prior information directly.

Fix:

Detector now accepts focused_yolo_policy.json.

### 3. Timestamped run folders

Problem:

Old outputs could overwrite each other.

Fix:

Every full pipeline run now creates:

~/casit-data/outputs/runs/<video_name>_<timestamp>

### 4. Latest symlink

Current latest run is linked at:

~/casit-data/outputs/runs/latest

### 5. Semantic event layer

Problem:

The system was detecting objects but not clearly reporting semantic events.

Fix:

semantic_event_builder.py was added.

It groups motion candidates and context windows into meaningful semantic event reports.

### 6. Nested scene_prior fix

Problem:

semantic_event_builder.py initially read scene_type as unknown.

Fix:

It now correctly reads:

scene_prior.scene_type
scene_prior.domain
scene_prior.confidence

### 7. construction_site policy

Problem:

construction_site was mapped to traffic_general because domain=traffic.

Fix:

construction_site_general policy was added and selector priority was updated.

Correct rule:

scene_type > domain

---

## Current Domain Policies

Policy file:

config/domain_policies.json

Current policies:

- unknown_general
- traffic_general
- industrial_factory
- warehouse_forklift
- security_general
- crowd_general
- sports_general
- construction_site_general

---

## Current Known Limitations

The system is still offline.

It does not yet support:

- live stream / RTSP monitoring
- dashboard
- strong multi-object tracking such as ByteTrack or BoT-SORT
- custom trained construction or safety object classes
- face recognition
- identity recognition
- named person tracking

Current tracking is MVP-level and may fragment tracks.

Stable track count is only an estimate.

---

## Critical Interpretation Rules

Detection count is not real physical count.

Raw track count can be fragmented.

Stable track count is more useful but still not absolute truth.

Motion candidate is not semantic event.

Context window is a macro event candidate.

Semantic event is the interpreted event layer.

---

## Ethical Boundary

Do not use the system for unauthorized MOBESE, CCTV, or public/security camera access.

Do not perform face recognition.

Do not perform identity recognition.

Do not track named individuals.

Use only owned, permitted, or test videos.

---

## Recommended Next Steps

### Immediate project finalization

1. Clean requirements files.
2. Check git status.
3. Initialize git repository if not already initialized.
4. Commit clean code and documentation.
5. Create private GitHub repository.
6. Push code to GitHub.
7. Share private repo access with collaborator.

### Technical v0.4

Add live stream / chunk-based monitoring:

RTSP or webcam
→ 10-30 second chunks
→ CASIT full pipeline or reduced fast pipeline
→ semantic event report
→ alert/dashboard

### Technical v0.5

Add VLM-based event reasoning per context window:

For each planned_context_window:

start frame
peak frame
end frame
→ Qwen/VLM event interpretation
→ event name
→ risk level
→ evidence summary
→ recommended action

### Technical v0.6

Add dashboard:

- run browser
- event timeline
- report viewer
- evidence thumbnails
- video/frame preview

### Technical v0.7

Improve tracking:

- ByteTrack
- BoT-SORT
- better unique object/person estimation

### Technical v0.8

Custom model classes:

- excavator
- crane
- loader
- bulldozer
- hard_hat
- safety_vest
- traffic_cone
- barrier
- roadwork_sign

---

## Sharing Recommendation

Use GitHub private repository for code.

Do not share large data through GitHub.

Share videos and run outputs separately through local disk, external drive, or cloud storage.

The collaborator should clone the repository and create their own local:

~/casit-data

folder.
