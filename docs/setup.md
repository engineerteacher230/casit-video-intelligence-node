# CASIT / ÇAŞIT — Kurulum ve Çalıştırma

## Proje Dizini

```bash
cd ~/casit/projects/casit-video-intelligence-node
```

## Veri Dizini

Repo içine video, model ağırlığı veya run çıktısı koyulmaz.

Beklenen veri dizini:

```text
~/casit-data
```

Önerilen yapı:

```text
~/casit-data/
├── datasets/
│   └── raw_videos/
├── models/
│   └── yolo11n.pt
└── outputs/
    └── runs/
```

## Python Ortamları

YOLO / pipeline ortamı:

```bash
source .venv/bin/activate
```

VLM / vLLM ortamı:

```bash
source .venv-vllm/bin/activate
```

## VLM Server

Beklenen local endpoint:

```text
http://127.0.0.1:8000
```

Örnek başlatma:

```bash
./scripts/start_vllm_strong.sh
```

## Full Pipeline

```bash
./scripts/run_casit_full_pipeline.sh ~/casit-data/datasets/raw_videos/cccc.mp4
```

## Çok Videolu Test

```bash
./scripts/run_casit_multi_video_tests.sh
```

## Önemli Çıktılar

```text
~/casit-data/outputs/runs/latest/json/standardized_scenario_3_output.json
~/casit-data/outputs/runs/latest/json/executive_jury_report.json
~/casit-data/outputs/runs/latest/reports/executive_jury_report.md
```

## Kurulum Kontrol Scripti

Kurulumdan sonra sistemin hazır olup olmadığını kontrol etmek için:

    ./scripts/check_casit_installation.sh

Başarılı durumda beklenen özet:

    PASS : 36
    WARN : 0
    FAIL : 0
    INSTALLATION_CHECK_OK

Bu kontrol; repo dosyalarını, config JSON dosyalarını, Python ortamlarını, YOLO modelini, raw video klasörünü, pipeline syntax durumunu ve vLLM server erişimini doğrular.
