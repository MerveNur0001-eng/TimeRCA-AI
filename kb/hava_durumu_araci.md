# Hava durumu aracı: get_weather

Kaynak: Open-Meteo Historical (reanalysis), tek nokta (41.01, 28.98). İstasyon ölçümü değildir, tüm İstanbul'u temsil etmez.
Veri kapsamı: güncel ay listesi kapsam_ve_sinirlar.md içindedir. Hava verisi olmayan bir pencerede araç hata döndürür; bu durum 'hava etkisi yok' anlamına gelmez, hipotez belirsiz kalır.
Çıktı: pencere için toplam yağış, en yüksek saatlik yağış, en yüksek rüzgâr, ortalama sıcaklık; karşılaştırma için dönemin günlük yağış medyanı ve %90 değeri.
Bulgu: Mart-Mayıs 2023 haftalık hacim-yağış korelasyonu -0,42 (12 hafta, Pearson), permütasyon testiyle p yaklaşık 0,18: anlamlı bulunmadı, örneklem küçük ve keşifsel. Hava zayıf kanıt olarak ele alınır.
