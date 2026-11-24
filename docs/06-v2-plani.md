# 06 - v2 Planı (etiketlerden ve ajan çalıştırılmadan önce yazıldı)

## v1 bulgusu
v1: tam eşleşme 8/12, yanlış alarm 0/8, veri_hatasi 0/4. Neden: evidence.py veri_hatasi hipotezini yalnızca
sapma varsa değerlendiriyor ve temiz saat medyanı ETL'de işaretli saatleri zaten dışlıyor. Sapma yoksa 11 saatlik boşluk bile hipotez olmuyor.

## Etiket tanımı (v2)
- label: pencere hacmindeki sapmanın nedeni (veri_hatasi, tatil, hava, deprem, aciklanamayan, etki_yok).
- veri_sorunu (evet/hayır): pencerede eksik saat veya ani hücre/araç çöküşü var mı, sapma olsun olmasın.

## Düzeltme (v2 sonucuna bakmadan sabitlendi)
1. judge() sapmadan bağımsız yeni bir alan döndürür: veri_kalitesi_uyarisi (işaretli saat sayısı, kesişen boşluk saat sayısı, oran).
2. Kesişen boşluk saatleri pencerenin >= %25'i ise veri_hatasi = destekliyor (sapma olmasa da).
3. Tek veya birkaç işaretli saat hipotez değil, yalnızca uyarıdır.
4. Eşlik eden metrik: uyarı VEYA veri_hatasi hipotezi = "veri sorunu bildirildi".
Not: %25 eşiği v1'de görülen vakalardan (V10 %46, V11 %29) türetildi, bu yüzden v2 gerekli.

## Ölçüt
(a) neden doğruluğu (label), (b) veri_sorunu recall ve precision, (c) yanlış alarm (etki_yok). Öncesi/sonrası v2 üzerinde, eşik v2 sonucuna göre değiştirilmez.
