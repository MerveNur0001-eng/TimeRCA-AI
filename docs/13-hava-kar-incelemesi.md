# 13 - Hava kuralı incelemesi (19 Kasım 2026)

Soru: 25 Ocak 2022 düşüşü hava kaynaklı mı, hava kuralı düzeltilmeli mi?

## Kural (evidence.py)
- Hava destekliyor = pencere toplam yağışı > dönem günlük p90 (7,5 mm) veya pencere azami rüzgârı > 40 km/sa.
- Sıcaklık kullanılmaz. Hava aracı yalnız sapma varsa çağrılır. Yön (düşüş/artış) ayrımı yapılmaz.

## Bulgular (ölçülmüş, betimleyici, küçük örneklem)
- 25 Ocak 2022: oran 0,56; yağış 3,7 mm; sıcaklık -0,2 °C; rüzgâr 31,2 km/sa. Hava desteklemiyor, açıklanamayan destekliyor, insan onayı. Eldeki kanıtla beklenen davranış.
- Yağış 24 Ocak 20:00 - 25 Ocak 03:00 arasında görünüyor. Gün sınırı olayı 4,3 + 3,7 mm'ye bölüyor (toplam 8,0 mm). Model zamanlaması docs/08'deki 24 Ocak zirve bilgisiyle uyuşmuyor; hangisinin doğru olduğu bu veriyle bilinemez.
- Günlük değerlendirme (409 gün, 58 sapmalı, genel sapma oranı 0,14):
  - mevcut kural: 36 gün, 6 sapmalı, 0,17
  - soğuk-yağışlı (sıcaklık <= 1,5 ve yağış >= 2 mm): 5 gün, 1 sapmalı, 0,20 (tek vaka 25 Ocak)
  - saatlik sağanak (en yağışlı saat >= 5 mm): 9 gün, 2 sapmalı, 0,22
  - kayan 24 saat yağış > p90 (12,2 mm): 41 gün, 7 sapmalı, 0,17 (25 Ocak kayan toplamı 8,2 mm, eşiğin altında)
  Hiçbiri sapma oranını anlamlı artırmadı.

## Karar
Kural değiştirilmedi. Tek bir olaya uydurulan kural doğrulama değil aşırı uyum olur ve v3 değerlendirmesini geçersiz kılar. Sıcaklık ve kayan pencere kuralları ölçüldü, eklenmedi.
25 Ocak için açıklanamayan + insan onayı beklenen sonuçtur. Gerçek neden (kar; docs/08'e göre 25 Ocak'ta kamu idari izni) kullanıcı tarafından girilir, sistem bunu kendisi kanıt saymaz.

## Bilinen sınırlama (ölçülmüş)
Pencere toplam yağışı günlük p90 ile karşılaştırılır; pencere uzadıkça hava destekliyor kolaylaşır.
- 3 günlük kayan pencereler (390 pencere, 20 sapmalı): hava destekliyor 6. Penceredeki en yağışlı gün kullanılsa 4 olurdu. Karar değişen 2 pencere: 24-26 Ocak 2022 (toplam 8,5; en yağışlı gün 4,6) ve 3-5 Mayıs 2023 (8,3; 6,4).
- 7 günlük pencereler (347 pencere, 10 sapmalı): değişen yok.
- Tek günlük pencerelerde fark yoktur.
- Kural yön ayırmaz: 3-5 Mayıs 2023 penceresi oran 1,22 (artış) iken hava destekliyor.
Etki küçük olduğu için kod değiştirilmedi. Olası düzeltme: get_weather'a precip_max_day_mm eklemek, evidence'ta geri düşüş ile kullanmak; ölçülmemiş değişiklik olarak belgelenmeli.

## Diğer
- Birim düzeltmesi: rüzgâr km/s yerine km/sa (commit a88c91a). docs/08'deki eski yazım hatası da düzeltildi.
- Reanalysis tek nokta, istasyon ölçümü değil (get_weather limits alanı).

## Düzeltme uygulandı (19 Kasım 2026 gece; ÖLÇÜLMEMİŞ karar kuralı değişikliği)
- get_weather precip_max_day_mm döner (penceredeki en yağışlı takvim gününün toplam yağışı). Hava kuralı artık bu değeri günlük p90 ile karşılaştırır; rüzgâr kuralı (> 40 km/sa) aynı.
- Tek günlük pencerelerde precip_max_day_mm = precip_total_mm (weather_window_test W5, yüklü tüm günlerde): karar değişmez.
- Değişen pencereler: 24-26 Ocak 2022 (toplam 8,5; en yağışlı gün 4,6) ve 3-5 Mayıs 2023 (8,3; 6,4) artık hava destekliyor demez (W3, W4). 7 günlük kayan pencerelerde fark yoktu.
- Bir günden kısa pencerede kısmi gün toplamı kullanılır (daha tutucu); bu etki ölçülmedi.
- v3 etiketli değerlendirme (etiket v3-degerlendirme) değiştirilmedi ve bu kuralla yeniden hesaplanmadı; bu değişiklik v4 adayı gibi ele alınmalıdır. Yukarıdaki Bilinen sınırlama bölümü değişiklik öncesi durumu anlatır.
