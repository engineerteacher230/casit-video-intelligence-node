# ÇAŞIT / CASIT Video Intelligence Node

ÇAŞIT / CASIT, TEKNOFEST 2026 Yapay Zekâ Dil Ajanları Yarışması **Senaryo 3: Video Analiz ve Karar Destek Sistemi** için geliştirilen offline video analiz ve karar destek prototipidir.

Sistem; video dosyasını yerel ortamda analiz eder, sahne bağlamını çıkarır, kişi/araç/nesne kanıtlarını üretir, olayları zaman damgalarıyla belirler, risk seviyesini değerlendirir, Türkçe özet ve operatör aksiyon önerileri üretir.

## İsimlendirme

- İnsan-facing ad: **ÇAŞIT**
- Teknik ad: **CASIT**

Kod, klasör, dosya ve komutlarda `CASIT`; rapor ve kullanıcıya görünen metinlerde `ÇAŞIT` kullanılır.

## Güncel Kabiliyetler

- 24 adımlı uçtan uca video analiz pipeline
- Yerel Qwen/VLM sahne yorumu
- Domain policy tabanlı YOLO odaklama
- Detection, tracking ve track kalite rafinesi
- Relation Dynamics Analyzer
- Proximity Risk Engine
- Event VLM Reasoner
- Risk & Action Engine v2
- Standardized Scenario 3 JSON output
- Scenario 3 Output Validator
- Benchmark / KPI Reporter
- Executive Jury Report Builder
- Multi-video test runner
- Custom class strategy

## Senaryo 3 Kapsamı

Bu proje şu işleri hedefler:

- Video dosyası girdisi alma
- Videodaki olayları, kişileri, araçları ve riskli durumları analiz etme
- Kritik anları zaman damgalarıyla belirleme
- Türkçe kısa özet üretme
- Operatöre aksiyon önerileri sunma
- JSON ve Markdown rapor üretme
- Yerel/offline çalışabilme
- Dış API veya kapalı servis bağımlılığı olmadan çalışabilme

Bu proje şu anda şunları hedeflemez:

- Canlı kamera / RTSP / MOBESE izleme
- Yüz tanıma
- Kişi kimliği tespiti
- Bireysel takip
- Yetkisiz kamera analizi
- Gerçek zamanlı operasyon ürünü

## Ana Mimari Akış

```text
Video dosyası
→ metadata okuma
→ coarse frame extraction
→ event energy scanning
→ context window planning
→ detail frame extraction
→ scene scout
→ Qwen/VLM scene prior
→ domain policy selection
→ domain-aware YOLO detection
→ tracking
→ relation dynamics
→ proximity risk
→ track quality refinement
→ event evidence
→ semantic event
→ event VLM reasoning
→ risk/action v2
→ Scenario 3 output
→ schema standardization
→ validation
→ quality review
→ benchmark KPI
→ executive jury report
```

## Kurulum Kontrolü

Projeyi çalıştırmadan önce tek komutla kurulum ve çalışma ortamı kontrol edilebilir:

    ./scripts/check_casit_installation.sh

Bu script şu başlıkları kontrol eder:

- repo dosyaları
- requirements dosyaları
- dokümantasyon dosyaları
- config JSON geçerliliği
- Python ortamları
- veri dizini
- YOLO model yolu
- raw video klasörü
- pipeline script syntax
- core Python module compile
- vLLM server erişimi

Başarılı çıktı:

    INSTALLATION_CHECK_OK

## Full Pipeline Çalıştırma

```bash
cd ~/casit/projects/casit-video-intelligence-node
source .venv/bin/activate
./scripts/run_casit_full_pipeline.sh ~/casit-data/datasets/raw_videos/cccc.mp4
```

VLM server açık olmalıdır:

```text
http://127.0.0.1:8000
```

Varsayılan VLM model:

```text
Qwen/Qwen2.5-VL-3B-Instruct
```

Varsayılan YOLO model:

```text
~/casit-data/models/yolo11n.pt
```

## Önemli Çıktılar

Her run şu dizine yazılır:

```text
~/casit-data/outputs/runs/<video_name>_<timestamp>
```

Latest symlink:

```text
~/casit-data/outputs/runs/latest
```

Ana teslim JSON adayı:

```text
json/standardized_scenario_3_output.json
```

Jüri/demo için ana rapor:

```text
reports/executive_jury_report.md
```

Diğer önemli raporlar:

```text
reports/benchmark_kpi_report.md
reports/scenario_3_output_validation.md
reports/standardized_scenario_3_output.md
```

## Test Videoları

```text
aaa.mp4    → roundabout_traffic / traffic
bbbbb.mp4  → street_confrontation / traffic
cccc.mp4   → construction_site / traffic
ddd.mp4    → crowd / outdoor
insan.mp4  → football_match_goal_celebration / sports
```

## Domain Policy Yaklaşımı

CASIT tek bir sabit YOLO sınıf listesiyle çalışmaz. Önce sahne bağlamını çıkarır, sonra uygun domain policy seçer.

Mevcut policy ailesi:

```text
unknown_general
traffic_general
industrial_factory
warehouse_forklift
security_general
crowd_general
sports_general
construction_site_general
checkpoint_security
convoy_movement
harbor_port
airport_runway
emergency_fire_smoke
border_restricted_area
parking_lot_general
indoor_corridor_entrance
```

## Custom Class Strategy

`config/custom_class_strategy.json` ve `docs/custom_class_strategy.md`, COCO/YOLO içinde doğrudan bulunmayan ama Scenario 3 için önemli özel sınıfları önceliklendirir.

Örnekler:

```text
restricted_zone
barrier
gate
helmet
safety_vest
fire
smoke
forklift
traffic_cone
```

## Etik Sınır

Bu sistem yalnızca izinli, sahip olunan veya test amaçlı videolarla kullanılmalıdır.

Yüz tanıma, kişi kimliği tespiti, bireysel takip veya yetkisiz kamera analizi amacıyla kullanılmamalıdır.

## Not

Benchmark / KPI raporu ground-truth doğruluk raporu değildir. mAP, precision, recall gibi metrikler için manuel etiketli test seti gerekir.
