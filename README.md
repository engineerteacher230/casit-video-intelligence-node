# ÇAŞIT / CASIT Video Intelligence Node

ÇAŞIT / CASIT, bilinmeyen videoları analiz etmek için geliştirilen offline video intelligence ve karar destek prototipidir.

Sistem önce Qwen/VLM ile sahneyi anlamaya çalışır, sonra YOLO dedektörünü sahne bağlamına göre dinamik olarak odaklar. Ardından tracking, track kalite rafinesi, olay kanıtı üretimi ve semantik olay raporu oluşturur.

## Proje Adı

- İnsan-facing ad: ÇAŞIT
- Teknik ad: CASIT

Teknik dosya, klasör, repo ve komutlarda `CASIT`; rapor ve insan-facing metinlerde `ÇAŞIT` kullanılır.

## Güncel Sürüm

CASIT v0.3.1

## Ana Pipeline

1. Video metadata okuma
2. Coarse frame extraction
3. Event energy scanning
4. Context window planning
5. Detail frame extraction
6. Scene scout extraction
7. Qwen/VLM scene prior
8. Domain policy selection
9. Domain-aware YOLO detection
10. Tracking
11. Track quality refinement
12. Event evidence building
13. Final Türkçe rapor
14. Semantic event report

## Temel Mimari Mantık

CASIT futbol videosuna özel değildir. Futbol sadece ilk test örneğidir.

Genel akış:

Bilinmeyen video
→ sahne keşfi
→ VLM/Qwen sahne yorumu
→ domain policy seçimi
→ YOLO odaklama
→ tracking
→ event evidence
→ semantic event report
→ Türkçe final rapor

## Kritik Ayrımlar

Frame detection gerçek fiziksel sayı değildir.

Raw track count kesin kişi/araç sayısı değildir.

Stable track count daha güvenilir tahmindir.

Motion candidate semantic event değildir.

Context window makro olay adayıdır.

Semantic event anlamlandırılmış olaydır.

## Ana Dizinler

Proje dizini:

~/casit/projects/casit-video-intelligence-node

Veri dizini:

~/casit-data

Raw video dizini:

~/casit-data/datasets/raw_videos

Run çıktıları:

~/casit-data/outputs/runs

Latest kısa yolu:

~/casit-data/outputs/runs/latest

## GitHub'a Girecekler

- src/
- config/
- scripts/
- README.md
- CLAUDE.md
- PROJECT_STATUS.md
- requirements*.txt
- .gitignore

## GitHub'a Girmeyecekler

- .venv/
- .venv-vllm/
- raw videolar
- extracted frames
- outputs/runs/
- model weights
- cache dosyaları
- ~/casit-data/

## Full Pipeline Çalıştırma

Proje dizinine gir:

cd ~/casit/projects/casit-video-intelligence-node

YOLO ortamını aktif et:

source .venv/bin/activate

VLM server açık olmalı:

http://127.0.0.1:8000

Bir video analiz et:

./scripts/run_casit_full_pipeline.sh ~/casit-data/datasets/raw_videos/cccc.mp4

## Test Edilen Videolar

insan.mp4:
football_match_goal_celebration / sports

aaa.mp4:
roundabout_traffic / traffic

bbbbb.mp4:
street_confrontation / traffic

cccc.mp4:
construction_site / traffic

cccc.mp4 sonrası önemli düzeltme:
construction_site sahnesi artık traffic_general yerine construction_site_general policy seçer.

## Güncel Policy Listesi

- unknown_general
- traffic_general
- industrial_factory
- warehouse_forklift
- security_general
- crowd_general
- sports_general
- construction_site_general

## Önemli Selector Kuralı

scene_type, domain bilgisinden daha güçlüdür.

Örnek:

scene_type = construction_site
domain = traffic

Doğru policy:

construction_site_general

## Mevcut Sınırlar

Sistem şu anda offline video analizi yapar.

Henüz şunlar yoktur:

- sürekli kamera izleme ürünü
- dashboard
- ByteTrack / BoT-SORT entegrasyonu
- custom construction/safety class modeli
- yüz tanıma
- kimlik tanıma

## Etik Sınır

Yetkisiz kamera veya güvenlik sistemi analizi yapılmamalıdır.

Kişi kimliği, yüz tanıma veya bireysel takip yapılmamalıdır.

Sistem yalnızca izinli, sahip olunan veya test amaçlı videolarla kullanılmalıdır.

## Senaryo 3 Kapsam Kilidi

Bu proje TEKNOFEST 2026 Yapay Zekâ Dil Ajanları Yarışması 3. Senaryo kapsamına göre geliştirilir.

Odak:

- Video dosyası girdisi alma
- Olayları tespit etme
- Kişi, araç ve nesne kanıtlarını çıkarma
- Riskli durumları belirleme
- Kritik anları zaman damgalarıyla listeleme
- Türkçe kısa özet üretme
- Operatöre aksiyon önerileri sunma
- JSON benzeri yapılandırılmış çıktı üretme
- Yerel/offline çalışma
- Dış API veya kapalı servis bağımlılığı olmadan çalışma

Detaylı kapsam dosyası:

SCENARIO_3_SCOPE.md

## Senaryo 3 Odaklı Yol Haritası

### v0.4 — Senaryo 3 Çıktı Standardı

- Standart JSON çıktı şeması
- Türkçe kısa özet
- Zaman damgalı olay listesi
- Risk seviyesi
- Operatör aksiyon önerileri
- Açıklanabilir kanıt alanı
- Belirsizlik / sınırlılık açıklaması

### v0.5 — Event VLM Reasoner

- Her context window için başlangıç, tepe ve bitiş kareleri seçilir.
- Qwen/VLM bu kareleri yorumlar.
- Olay adı, risk gerekçesi ve kritik an açıklaması üretilir.

### v0.6 — Risk & Action Engine

- Olay tipine göre risk seviyesi üretir.
- Operatöre uygulanabilir aksiyon önerileri sunar.
- Çıktıyı Türkçe ve yapılandırılmış formatta verir.

### v0.7 — KPI / Benchmark

- Olay tespit doğruluğu
- Kritik olay yakalama oranı
- Özet kalitesi
- Aksiyon önerisi doğruluğu
- İşlem süresi
- Model inference süresi
- Bellek ve donanım kullanımı

### v0.8 — Yarışma Teslim Paketi

- Ön değerlendirme raporu
- Demo videosu
- Mimari diyagram
- Kurulum dokümantasyonu
- Ölçümleme sonuçları
- Sunum materyali

## Kapsam Notu

CASIT / ÇAŞIT bu fazda kamera izleme ürünü değildir.

CASIT, TEKNOFEST Senaryo 3 kapsamında yüklenen operasyon videosunu yerel ortamda analiz eden ve karar destek çıktısı üreten offline video intelligence sistemidir.
