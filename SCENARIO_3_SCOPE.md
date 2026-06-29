# CASIT / ÇAŞIT — Senaryo 3 Kapsam Kilidi

Bu dosya, CASIT / ÇAŞIT projesinin TEKNOFEST 2026 Yapay Zekâ Dil Ajanları Yarışması 3. Senaryo kapsamına göre sınırlarını belirler.

## Resmi Senaryo

Senaryo 3: Video Analiz ve Karar Destek Sistemi

Amaç:

Savunma, güvenlik ve saha operasyonlarında kullanılan videoları analiz eden; videodaki olayları, kişileri ve riskli durumları tespit eden; kritik anları zaman damgalarıyla belirleyen; Türkçe özet oluşturan ve operatöre aksiyon önerileri sunan yerel bir yapay zekâ sistemi geliştirmek.

## Kapsama Dahil Olanlar

CASIT şu başlıklara odaklanır:

1. Video dosyası girdisi alma
2. Video içeriğini yerel ortamda analiz etme
3. Sahne bağlamını multimodal model ile anlama
4. Kişi, araç, nesne ve hareket kanıtlarını çıkarma
5. Olayları zaman damgalarıyla listeleme
6. Kritik anları belirleme
7. Risk değerlendirmesi üretme
8. Operatöre uygulanabilir aksiyon önerileri sunma
9. Türkçe kısa ve anlaşılır özet oluşturma
10. JSON benzeri yapılandırılmış çıktı üretme
11. Açıklanabilir karar destek kanıtı sunma
12. Dış API veya kapalı servis bağımlılığı olmadan yerel çalışma
13. vLLM veya benzeri yerel model servisleme altyapısı kullanma

## Kapsam Dışında Kalanlar

Bu aşamada aşağıdaki başlıklar proje kapsamı dışındadır:

1. Canlı yayın izleme
2. RTSP kamera takibi
3. MOBESE veya kamu kamerası entegrasyonu
4. Webcam tabanlı sürekli izleme
5. Kimlik tanıma
6. Yüz tanıma
7. Bireysel kişi takibi
8. Yetkisiz kamera veya güvenlik sistemi analizi

## Mühendislik Kararı

CASIT bu fazda bir kamera izleme ürünü değildir.

CASIT, yüklenen operasyon videosunu analiz eden ve karar destek çıktısı üreten offline / yerel bir video zekâ sistemidir.

Doğru mimari odak:

Video dosyası
→ sahne keşfi
→ VLM/Qwen bağlam analizi
→ domain policy seçimi
→ YOLO odaklama
→ tracking
→ hareket / olay kanıtı
→ semantik olay yorumu
→ risk değerlendirmesi
→ aksiyon önerisi
→ Türkçe özet
→ yapılandırılmış JSON çıktı

## v0.4 Hedef Çıktı Şeması

CASIT v0.4 ile hedeflenen standart çıktı şeması:

{
  "summary_tr": "Videonun kısa Türkçe özeti",
  "events": [
    {
      "event_id": "EVT_001",
      "start_time": "00:00:15.000",
      "end_time": "00:00:22.000",
      "peak_time": "00:00:18.500",
      "event_type": "riskli_durum",
      "event_name_tr": "Personel ve araç yakınlaşması",
      "risk_level": "medium",
      "evidence": [
        "person tespitleri",
        "truck tespitleri",
        "hareket yoğunluğu",
        "VLM sahne yorumu"
      ],
      "operator_actions_tr": [
        "Alanı kontrol et",
        "Personel-araç mesafesini doğrula",
        "Güvenlik kaydını incele"
      ]
    }
  ],
  "overall_risk": "medium",
  "decision_support_tr": "Operatör için kısa karar destek açıklaması",
  "limitations_tr": "Model belirsizlikleri ve güven düzeyi"
}

## Kritik Yorumlama Kuralları

Detection count gerçek fiziksel sayı değildir.

Raw track count kesin kişi veya araç sayısı değildir.

Stable track count daha güvenilir tahmindir ama mutlak gerçek değildir.

Motion candidate semantik olay değildir.

Context window makro olay adayıdır.

Semantic event anlamlandırılmış olaydır.

Risk seviyesi yalnızca nesne sayısından değil; olay bağlamı, zaman, hareket yoğunluğu ve sahne yorumu birlikte değerlendirilerek üretilmelidir.

## Yeni Yol Haritası

### v0.3.1

Çalışan offline video intelligence MVP.

### v0.4 — Senaryo 3 Çıktı Standardı

- summary_tr
- events
- timestamps
- risk_level
- operator_actions_tr
- evidence
- limitations_tr

### v0.5 — Event VLM Reasoner

Her context window için başlangıç, tepe ve bitiş kareleri seçilir. Qwen/VLM bu kareler üzerinden olayın ne olduğunu, riskini ve etkisini yorumlar.

### v0.6 — Risk & Action Engine

Olay tipine göre risk seviyesi ve operatör aksiyon önerileri üretilir.

### v0.7 — KPI / Benchmark

- olay tespit doğruluğu
- kritik olay yakalama oranı
- özet kalitesi
- aksiyon önerisi doğruluğu
- işlem süresi
- model inference süresi

### v0.8 — Yarışma Teslim Paketi

- Ön değerlendirme raporu
- Teknik mimari dokümantasyon
- Demo videosu
- Sunum dosyası
- Mimari diyagram
- Kurulum ve çalıştırma dokümanı
- Ölçümleme sonuçları

## Claude / AI Assistant Talimatı

Bu projede geliştirme yaparken Senaryo 3 dışına çıkma.

Canlı yayın, RTSP, MOBESE veya webcam temelli ürün yönüne gitme.

Öncelik:

1. Offline video analizi
2. Semantik olay yorumu
3. Risk değerlendirmesi
4. Operatör aksiyon önerileri
5. Türkçe özet
6. JSON çıktı
7. Yerel çalışma
8. Açıklanabilirlik
