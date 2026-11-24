# Veri Kalitesi Bulguları

- 6 ayın 5'inde eksik saat var. Şubat 2023 tek boşluksuz ay.
- Eksik saat sayıları: Ocak 2023 16, Şubat 2023 0, Mart 2023 88, Nisan 2023 35, Mayıs 2023 66, Ocak 2024 338.
- Toplam 24 eksik blok (Mart 4, Nisan 4, Mayıs 5, Ocak 2024 8, Ocak 2023 3, Şubat 0).
- Ocak 2024'te 15-21 Ocak arası tam bir hafta yok.
- Boşlukların nedeni bilinmiyor. ETL logu yalnızca yüklemede görülenleri kaydeder.
- Keşif bulgusu (hipotez veriyi gördükten sonra kuruldu): 01:00'de başlayan 4 boşlukta önceki saat (00:00) yoğunluk uyarılıydı (4/4); gün ortasında başlayan 8 boşlukta 5/8; 00:00'da başlayan 9 boşlukta 0/9. Analiz Mart-Mayıs 2023 ve Ocak 2024 üzerinde yapıldı. Nedeni bilinmiyor.
- Kapsam ve yoğunluk kuralları aylık medyana göre çalışır. Eşikler tasarım seçimidir, Nisan 2023 üzerinde ayarlandı.
- Saatlik seri gürültülüdür: tek saatlik oranlara değil, çok saatlik ve günlük düzeye güvenilir.
