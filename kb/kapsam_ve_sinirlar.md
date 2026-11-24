# Kapsam ve Sınırlar

- Trafik verisi (İBB saatlik): 18 ay yüklü: Aralık 2021-Ocak 2022, Ekim-Kasım 2022, Ocak-Eylül 2023, Kasım 2023-Ocak 2024, Mart-Nisan 2024. Her ay için ETL logu var; hiçbir ay tamamen boşluksuz varsayılmaz.
- Hava verisi (Open-Meteo): Aralık 2021-Ocak 2022, Ekim-Kasım 2022, Ocak-Eylül 2023, Kasım 2023-Ocak 2024, Mart-Nisan 2024.
- Deprem kataloğu (USGS): 2021-11/2022-02, 2022-09/2022-12, 2023-02/2024-02 ve 2024-03/2024-05 aralıkları; bunların dışı kapsam dışıdır.
- Deprem kataloğunun kapsamadığı yüklü aylar: Ocak 2023. Bu aylarda sapma varsa deprem hipotezi 'belirsiz' kalır (katalog yok).
- Yüklü aylar dışındaki her tarih kapsam dışıdır: Şubat-Eylül 2022, Aralık 2022, Ekim 2023, Şubat 2024, Kasım 2021 ve öncesi, Mayıs 2024 ve sonrası. Bu aylardaki olaylar değerlendirilemez.
- Veri yalnızca İstanbul içindir. Konya gibi başka şehirlerin verisi kullanılmıyor.
- Sel, yangın, grev, etkinlik ve maç gibi olaylar için veri kaynağı yok. Ajan bunları neden olarak destekleyemez.
- Ajan yalnızca kapsam içindeki zaman pencereleri için veri hatası, hava, tatil ve bayram, deprem kanıtlarını değerlendirebilir.
