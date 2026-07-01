# CASIT / ÇAŞIT — Değerlendirme ve KPI

## Amaç

Bu doküman CASIT pipeline çıktılarının nasıl değerlendirildiğini açıklar.

## Mevcut KPI Türü

Mevcut benchmark KPI, ground-truth doğruluk skoru değildir.

Ölçülenler:

```text
pipeline completeness
output availability
Scenario 3 schema compliance
validation status
quality readiness
reasoning stack health
```

Şu an ölçülmeyenler:

```text
mAP
precision
recall
F1 score
true positive / false positive oranları
```

Bu metrikler için elle etiketlenmiş ground-truth video seti gerekir.

## Ana Değerlendirme Modülleri

```text
src/evaluation/scenario_3_output_validator.py
src/evaluation/scenario_3_quality_reviewer.py
src/evaluation/benchmark_kpi_reporter.py
src/evaluation/multi_video_test_aggregator.py
```

## Ana Raporlar

```text
reports/scenario_3_output_validation.md
reports/v0.4_quality_review.md
reports/benchmark_kpi_report.md
reports/executive_jury_report.md
```

## Gerçek Doğruluk Benchmark İçin Gerekenler

1. Video seti sabitlenmeli.
2. Ground-truth annotation yapılmalı.
3. Nesne sınıfları netleştirilmeli.
4. Event-level ground truth tanımlanmalı.
5. Detection ve event matching kuralları belirlenmeli.
6. Otomatik benchmark scripti yazılmalı.
