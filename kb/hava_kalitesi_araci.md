# Hava kalitesi ek sinyali: get_air_quality_signal
Girdi: başlangıç ve bitiş zamanı. Kaynak: İBB Hava Kalitesi açık veri servisi (saatlik NO2, PM10, O3 ölçümleri; şehir değeri, o saatte ölçüm yapan istasyonların medyanıdır, en az 3 istasyon gerekir). Trafik oranı ile NO2 oranı aynı baseline kuralıyla (önceki 4 haftanın aynı gün ve saatinin medyanı) yan yana okunur; eşikler 0,85 ve 1,15.
Okuma 1: trafik düşük ve NO2 de normalin altındaysa gerçek bir araç azalmasıyla uyumludur; rüzgâr ve yağış da kirliliği düşürebilir.
Okuma 2: trafik düşük ama NO2 normalse hava kalitesi düşüşü desteklemez; veri hatası ya da yerel sorun olasılığı artar, ancak NO2'nin araç dışı kaynakları da vardır.
Okuma 3: trafik düşük ama NO2 yüksekse durgun hava gibi hava koşulları ya da araç dışı kaynaklar olabilir.
Sınır: ek kanıttır, karar kuralında ve hipotez puanında kullanılmaz; nedensellik kanıtı vermez. Trafik normalse sinyal üretilmez. Veri yoksa, pencere 12 saatten kısaysa ya da baseline yetersizse oran verilmez.
Sınır: veri dosyası git'te değildir, scripts\veri\fetch_hava_kalitesi.py ile indirilir; indirilmemişse araç hata döner ve sinyal gösterilmez.
