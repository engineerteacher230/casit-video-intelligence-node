# CASIT / ÇAŞIT — Mimari Dokümantasyon

## Amaç

CASIT, bilinmeyen bir video dosyasını offline ortamda analiz ederek TEKNOFEST Senaryo 3 formatında karar destek çıktısı üretir.

## Katmanlar

### 1. Video I/O

```text
src/video_io/video_metadata_reader.py
src/video_io/coarse_frame_extractor.py
src/video_io/detail_window_extractor.py
```

### 2. Adaptive Search

```text
src/adaptive_search/event_energy_scanner.py
src/adaptive_search/context_window_planner.py
```

### 3. Scene Understanding

```text
src/scene_understanding/scene_scout_extractor.py
src/scene_understanding/scene_prior_agent.py
```

### 4. Policy Layer

```text
config/domain_policies.json
src/policies/domain_policy_selector.py
```

### 5. Vision Layer

```text
src/vision/domain_aware_yolo_detector.py
src/vision/domain_aware_yolo_tracker.py
src/vision/track_quality_refiner.py
src/vision/event_evidence_builder.py
src/vision/relation_dynamics_analyzer.py
```

### 6. Risk Layer

```text
src/risk/proximity_risk_engine.py
src/risk/risk_action_engine_v2.py
```

### 7. Event Reasoning

```text
src/event_reasoning/semantic_event_builder.py
src/event_reasoning/event_vlm_reasoner.py
```

### 8. Reporting / Evaluation

```text
src/reporting/scenario_3_output_builder.py
src/reporting/json_schema_standardizer.py
src/reporting/executive_jury_report_builder.py
src/evaluation/scenario_3_output_validator.py
src/evaluation/scenario_3_quality_reviewer.py
src/evaluation/benchmark_kpi_reporter.py
```

## Ana Teslim Çıktıları

```text
standardized_scenario_3_output.json
scenario_3_output_validation.json
executive_jury_report.md
```

## Kritik Mimari Karar

CASIT önce sahneyi anlamaya çalışır; sonra YOLO sınıf listesini sahneye göre odaklar. Bu yüzden farklı video domainlerinde aynı pipeline korunabilir.
