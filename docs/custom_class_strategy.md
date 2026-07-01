# CASIT / ÇAŞIT — Custom Class Strategy

Bu belge, `custom_classes_later` alanlarında geçen sınıfları eğitim ve mimari önceliklerine göre sınıflandırır.

## Özet

- Domain policy version: `0.5.0`
- Unique custom class count: `47`

## Öncelik Tablosu

| Priority | Class | Type | Policy Count | Recommended Implementation |
|---|---|---:|---:|---|
| P0 | `restricted_zone` | virtual_zone | 11 | polygon_rule_or_scene_config |
| P0 | `barrier` | physical_object | 6 | custom_yolo_or_vlm_verified_object |
| P0 | `gate` | physical_object | 4 | custom_yolo_or_scene_anchor |
| P1 | `helmet` | ppe_object | 3 | custom_yolo_or_person_crop_classifier |
| P1 | `safety_vest` | ppe_object | 3 | custom_yolo_or_person_crop_classifier |
| P1 | `fence` | physical_boundary | 1 | custom_yolo_or_segmentation |
| P1 | `fire` | visual_state | 1 | vlm_first_then_segmentation_or_classifier |
| P1 | `flame` | visual_state | 1 | merge_with_fire_or_subclass |
| P1 | `forklift` | vehicle_subclass | 1 | custom_yolo |
| P1 | `hard_hat` | ppe_object | 1 | merge_with_helmet_or_alias |
| P1 | `smoke` | visual_state | 1 | vlm_first_then_segmentation_or_classifier |
| P1 | `traffic_cone` | physical_object | 1 | custom_yolo |
| P2 | `crane` | heavy_equipment | 2 | custom_yolo_or_scene_context |
| P2 | `ambulance` | vehicle_subclass | 1 | vehicle_subclass_classifier |
| P2 | `excavator` | heavy_equipment | 1 | custom_yolo |
| P2 | `fire_truck` | vehicle_subclass | 1 | vehicle_subclass_classifier |
| P3 | `license_plate` | ocr_sensitive | 2 | ocr_module_later |
| P3 | `uniform` | person_attribute | 2 | person_crop_attribute_classifier_later |
| P3 | `access_card_reader` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `baggage_cart` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `box` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `bulldozer` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `cargo_area` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `checkpoint_booth` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `container` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `convoy_vehicle` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `crowd_density_zone` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `dock_gate` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `door` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `escort_vehicle` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `evacuation_zone` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `ground_crew` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `loader` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `machine` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `pallet` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `parking_space` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `queue_line` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `rescue_worker` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `roadblock` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `roadwork_sign` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `robot_arm` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `runway_marking` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `service_vehicle` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `ship` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `turnstile` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `wall` | future_candidate | 1 | defer_until_domain_dataset_exists |
| P3 | `warning_sign` | future_candidate | 1 | defer_until_domain_dataset_exists |

## P0/P1 Gerekçeleri

### P0 — `restricted_zone`

- Tip: `virtual_zone`
- Kullanıldığı policy sayısı: `11`
- Önerilen yöntem: `polygon_rule_or_scene_config`
- Eğitim ihtiyacı: `no_yolo_training_initially`
- Gerekçe: Birçok domain için ortak güvenlik bölgesi kavramı. Nesne değil; koordinat/polygon tabanlı kural olarak ele alınmalı.

### P0 — `barrier`

- Tip: `physical_object`
- Kullanıldığı policy sayısı: `6`
- Önerilen yöntem: `custom_yolo_or_vlm_verified_object`
- Eğitim ihtiyacı: `small_custom_dataset`
- Gerekçe: Kontrol noktası, sınır, şantiye ve park alanı için yüksek değerli fiziksel engel sınıfı.

### P0 — `gate`

- Tip: `physical_object`
- Kullanıldığı policy sayısı: `4`
- Önerilen yöntem: `custom_yolo_or_scene_anchor`
- Eğitim ihtiyacı: `small_custom_dataset`
- Gerekçe: Giriş/çıkış ve kontrol noktası karar destek mantığında sahne çıpası olarak kritik.

### P1 — `helmet`

- Tip: `ppe_object`
- Kullanıldığı policy sayısı: `3`
- Önerilen yöntem: `custom_yolo_or_person_crop_classifier`
- Eğitim ihtiyacı: `custom_dataset_or_open_dataset_adaptation`
- Gerekçe: İş güvenliği, fabrika, depo ve güvenlik sahneleri için kişisel koruyucu ekipman sınıfı.

### P1 — `safety_vest`

- Tip: `ppe_object`
- Kullanıldığı policy sayısı: `3`
- Önerilen yöntem: `custom_yolo_or_person_crop_classifier`
- Eğitim ihtiyacı: `custom_dataset_or_open_dataset_adaptation`
- Gerekçe: Şantiye, depo ve endüstriyel saha için yüksek faydalı PPE sınıfı.

### P1 — `fence`

- Tip: `physical_boundary`
- Kullanıldığı policy sayısı: `1`
- Önerilen yöntem: `custom_yolo_or_segmentation`
- Eğitim ihtiyacı: `custom_dataset`
- Gerekçe: Sınır, çevre güvenliği ve kısıtlı alan senaryolarında önemli.

### P1 — `fire`

- Tip: `visual_state`
- Kullanıldığı policy sayısı: `1`
- Önerilen yöntem: `vlm_first_then_segmentation_or_classifier`
- Eğitim ihtiyacı: `specialized_visual_dataset`
- Gerekçe: Acil durum tespiti için yüksek değerli; COCO içinde doğrudan yok.

### P1 — `flame`

- Tip: `visual_state`
- Kullanıldığı policy sayısı: `1`
- Önerilen yöntem: `merge_with_fire_or_subclass`
- Eğitim ihtiyacı: `class_alias_normalization`
- Gerekçe: fire ile aynı olay ailesinde; ilk fazda fire alias olarak ele alınmalı.

### P1 — `forklift`

- Tip: `vehicle_subclass`
- Kullanıldığı policy sayısı: `1`
- Önerilen yöntem: `custom_yolo`
- Eğitim ihtiyacı: `custom_dataset`
- Gerekçe: Depo/lojistik sahalarında insan-araç yakınlaşması için kritik.

### P1 — `hard_hat`

- Tip: `ppe_object`
- Kullanıldığı policy sayısı: `1`
- Önerilen yöntem: `merge_with_helmet_or_alias`
- Eğitim ihtiyacı: `class_alias_normalization`
- Gerekçe: helmet ile aynı anlam ailesinde; veri etiketleme sırasında alias olarak birleştirilmeli.

### P1 — `smoke`

- Tip: `visual_state`
- Kullanıldığı policy sayısı: `1`
- Önerilen yöntem: `vlm_first_then_segmentation_or_classifier`
- Eğitim ihtiyacı: `specialized_visual_dataset`
- Gerekçe: Acil durum ve olay analizi için kritik; kutu yerine segmentation/classification daha uygun olabilir.

### P1 — `traffic_cone`

- Tip: `physical_object`
- Kullanıldığı policy sayısı: `1`
- Önerilen yöntem: `custom_yolo`
- Eğitim ihtiyacı: `small_custom_dataset`
- Gerekçe: Şantiye/yol çalışması bağlamında sahne sınırı ve güvenlik uyarısı sağlar.
