# ÇAŞIT — TEKNOFEST Senaryo 3 Teknik Yarışma Raporu Taslağı

## Proje Özeti

ÇAŞIT, video dosyalarını yerel ortamda analiz ederek sahne bağlamı, nesne/personel/araç kanıtı, olay zaman çizelgesi, risk seviyesi ve operatör aksiyon önerileri üreten offline karar destek sistemidir.

## Senaryo Uygunluğu

TEKNOFEST Senaryo 3 beklentileri:

```text
video analizi
olay tespiti
kişi/nesne/riskli durum analizi
kritik anların zaman damgası
Türkçe özet
operatör aksiyon önerileri
yerel/offline çalışma
dış API bağımlılığı olmaması
```

ÇAŞIT bu gereksinimleri pipeline çıktılarıyla karşılar.

## Teknik Mimari

```text
Qwen/VLM scene prior
domain policy selector
domain-aware YOLO detection
tracking
track quality refinement
relation dynamics analyzer
proximity risk engine
semantic event builder
event VLM reasoner
risk & action engine v2
standardized Scenario 3 output
validator
benchmark KPI
executive jury report
```

## Özgün Değer

- Sahne bağlamına göre YOLO odak politikası seçimi
- Frame detection ile unique track ayrımı
- Proximity risk ve relation dynamics tabanlı karar destek
- VLM destekli event reasoning
- Tekleştirilmiş executive jüri raporu
- Custom class strategy ile ileri aşama veri/model planı

## Çıktılar

Ana teslim JSON:

```text
standardized_scenario_3_output.json
```

Ana jüri raporu:

```text
executive_jury_report.md
```

Benchmark raporu:

```text
benchmark_kpi_report.md
```

Validator raporu:

```text
scenario_3_output_validation.md
```

## Sınırlılıklar

- Mevcut KPI doğruluk metriği değildir.
- mAP/precision/recall için manuel etiketli veri seti gerekir.
- Sistem şu anda video dosyası analizi yapar; canlı kamera ürünü değildir.
- Yüz tanıma veya kişi kimliği tespiti yapılmaz.
- Kritik kararlar için operatör doğrulaması gerekir.
