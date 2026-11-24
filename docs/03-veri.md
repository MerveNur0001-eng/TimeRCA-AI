# 03 - Veri

## Kaynaklar
| Kaynak | İçerik | Not |
|---|---|---|
| İBB Açık Veri, Saatlik Trafik Yoğunluğu | Aylık CSV, Ocak 2020 - Ocak 2025, 61 dosya | Lisans: İBB Açık Veri Lisansı (atıf: "Kaynak: İBB Açık Veri Portalı") |
| Open-Meteo Historical | Saatlik hava (yüklü aylar için) | Reanalysis, tek nokta, istasyon ölçümü değildir |
| holidays (Python) | Türkiye resmî tatil ve bayramlar | |
| USGS FDSN | Deprem kataloğu, indirilen M>=4 (QUAKE_COVER: Kas 2021-Oca 2022, Eyl-Kas 2022, Şub 2023-Oca 2024, Mar-Nis 2024), yerel CSV | USGS ComCat dünya genelinde yaklaşık M4,5 üstü için tam. AFAD API'si geçmiş sorgulara boş döndü, bu yüzden bu kaynak |

## İBB şeması (İBB veri sözlüğüyle doğrulandı)
DATE_TIME, LATITUDE, LONGITUDE, GEOHASH, MINIMUM_SPEED, MAXIMUM_SPEED, AVERAGE_SPEED, NUMBER_OF_VEHICLES
- Sütunlar adla okunur (dokümandaki sıra dosyadan farklı olabilir).
- Hücre: uzunluğu 6 olan geohash alanı. NUMBER_OF_VEHICLES, verilen saatte o hücredeki farklı araç sayısıdır.
- total_vehicles hücre bazlı sayıların toplamıdır. Bir araç birden fazla hücrede sayılabilir (çıkarım). Bu yüzden "trafik hacmi göstergesi"dir, şehirdeki gerçek araç sayısı değil.
- DATE_TIME formatı YYYY-MM-DD HH24:MI:SS, saatlik. Saat dilimi sözlükte belirtilmemiş. Yerel saat varsayılıyor: gece dibi 03:00, UTC olasılığı dışlandı (bkz. 05-dogrulama.md). USGS çevirisi (UTC+3) bu varsayıma dayanıyor.
- Nisan 2023'te azami hızın yaklaşık %8,8'i 150 km/sa üstünde (gürültü). Ana seri araç sayısıdır, hız verisi kullanılmadı.

## ETL log bulguları (6 ay)
| Ay | Eksik saat | Oran | Blok |
|---|---|---|---|
| 2023-01 | 16 | %2,2 | 3 |
| 2023-02 | 0 | %0 | 0 |
| 2023-03 | 88 | %11,8 | 4 |
| 2023-04 | 35 | %4,9 | 4 |
| 2023-05 | 66 | %8,9 | 5 |
| 2024-01 | 338 | %45,4 | 8 |

- Toplam 24 eksik blok. Kaynak dosyada eksik kayıtlar; nedeni bilinmiyor.
- Şubat 2023 tek boşluksuz ay.
- Ocak 2024'te 15-21 Ocak tam bir hafta yok.
- Kapsam ve yoğunluk kuralları aylık medyana göre çalışır. Eşikler Nisan 2023 üzerinde ayarlandı; Ocak-Şubat 2023 ve Ocak 2024 eşik ayarında kullanılmadı.

## Araç bulguları (Ocak-Mayıs 2023)
- Saatlik seri gürültülü (gündüz saat bazlı log-oran MAD'ı 0,19): tek saatlik oranlara değil, çok saatlik ve günlük düzeye güvenilir.
- Günlük düzeyde en az %15 sapma (Mart-Mayıs): 22 Nisan (-%26, Ramazan Bayramı), 8 Nisan (+%32), 3-6 Mayıs (+%16 ile +%29), 12 Mayıs, 27 Mayıs. 8 Nisan ve 3-6 Mayıs için takvim ve hava nedeni bulunamadı: açıklanamayan adayı.
- Hava: haftalık hacim-yağış korelasyonu -0,42 (12 hafta, Pearson; permütasyon p = 0,183: anlamlı bulunmadı, keşifsel). Hava zayıf kanıt olarak ele alınır.
- Ramazan dönemi hafta içi hacmi öncesinden belirgin farklı değil (4,07 M ve 4,08 M).
- Boşluk komşuluğu (keşif, hipotez veriyi gördükten sonra kuruldu): Mart-Mayıs ve Ocak 2024 üzerinde, 01:00'de başlayan 4 boşlukta 00:00 saati yoğunluk uyarılı (4/4), gün ortasında başlayanlarda 5/8, 00:00'da başlayanlarda 0/9. Neden bilinmiyor.
- 6 Şubat 2023: günlük düzey -%6, temiz saat medyanı 0,94. Aynı gün 19,8 mm yağış ve 49 km/sa rüzgâr vardı. Deprem ve hava aynı güne denk geldiği için hiçbiri neden seçilemez; trafikte belirgin anomali yok. Ertesi hafta -%2 ile -%7, 13 Şubat'tan sonra +%2 ile +%9: gürültüden ayırt edilemez.
- Yarıyıl tatili hipotezi doğrulanmadı: 23 Ocak Pazartesi 4,54 M, 30 Ocak 3,99 M, tutarlı düşüş yok.
- Deprem: USGS saatleri UTC, yerel saate (UTC+3) çevriliyor. Mart-Mayıs 2023'te ilgili deprem olan yalnızca 2 gün var (16-17 Mart, Bolu M4,8). Pilotta deprem etkisi gösterilemedi.

## Bilinen sınırlar
- İBB tarafında gerçek pipeline logu yok. ETL logu bizim yüklememizde gördüklerimizi kaydeder, boşluğun nedenini söylemez.
- Boşluksuz tek ay var (Şubat 2023): baseline yine de eksik veriye dayanıklı olmalı.
- Pandemi dönemi (2020-2021) baseline'ı bozar, pilot dışında tutuldu.
- tools.py yalnızca MONTHS listesindeki 18 ayı yükler. Listede olmayan aylar (ör. Ekim 2023, Şubat 2024) için baseline eksik kalır, pencere 'değerlendirilemedi' olabilir. check_etl_log ay sınırını aşan pencerelerde ilgili tüm ayları okur.
- Araçlar için ayrı birim test yok; davranışları agent_test, selection_test ve series_real_test (gerçek veride tutarlılık) üzerinden sınanır.

## Rapor katmanı bulguları (src/report.py)
- Pencerenin tüm saatleri kaynak dosyada yoksa (19 Nisan 02-09) kural önce "sapma yok" diyordu; düzeltildi: veri hatası destekleniyor.
- Baseline hesaplanamazsa (3 Ocak 2023, verinin ilk haftası) tüm hipotezler "belirsiz", insan incelemesi gerekli.
- Pencerenin bir kısmı eksikse (19 Nisan 10-15, 4/6 saat yok) karar kalan 2 saatin oranına (0,84; eşik 0,85) dayanıyor. Bu zayıf: veri hatası "belirsiz" olarak işaretleniyor, insan incelemesi isteniyor.
- Rapor notları ASCII Türkçe ile yazılıyor (ör. "isaretli"), kozmetik düzeltme bekliyor.
- tests/report_test.py: 7 vakalık regresyon testi. Beklentiler kuralların kendisinden türetildi; doğruluk ölçümü değildir.

## 18 aylık veri üzerinde keşif bulguları (17 Kasım 2026)
Bunlar etiketli değerlendirme DEĞİL, keşif gözlemleridir; kural ayarı için kullanılmadı. Yukarıdaki ETL tablosu ilk 6 ayın dökümüdür, 18 ay yüklüdür.
- Saatlik "bölge" sıklığı (>=3 ardışık saat bant dışı, 394 gün, ETL işaretli saatler hariç; arayüzdeki canlı taban notuyla aynı): günlerin %60'ında en az bir bölge başlar, 12 saati aşan bölge yaklaşık 23 günde bir. İlk keşif ölçümü 397 gün, %61, gün başına 0,87 bölge vermişti; fark sayım ölçütünden olabilir, doğrulanmadı. Bu oranlar gerçek anomalileri de içerir. Kısa bölgeler sıradan dalgalanmadır.
- 28-30 Nisan 2024: kapsam çöküşü. Pencerede n_cells medyanı 54 (normalde yaklaşık 2400), hücre başına araç 1,0 (normalde yaklaşık 85); ETL 43 saatin 39'unu işaretlemiş. Gerçek trafik düşüşü değil, veri kapsamı sorunu görünümündedir (neden bilinmiyor).
- Ocak 2024: 15-23 Ocak öğle saatleri tamamen eksik (9 gün). Öncesinde hafta içi öğle medyanı yaklaşık 140-200 bin, 24 Ocak'tan sonra yaklaşık 360-390 bin; hücre sayısı ve hız değişmedi, pazar günü (28 Ocak) düzey neredeyse aynı (220 bin, önceki pazarlar 194-195 bin). 25 ve 31 Ocak'ta ajanın gördüğü artış (oran yaklaşık 2,1) baseline haftalarının boşluktan önceki düzeyden gelmesiyle uyumludur. Neden bilinmiyor.
- 23 Kasım 2023: öğle medyanı 213 bin, komşu günler 202-262 bin; baseline haftaları (9 ve 16 Kasım) 139-159 bin. 'Artış' baseline'ın düşüklüğünden gelmiş olabilir. 4 Mayıs 2023: öğle medyanı 311 bin, komşu günler 169-232 bin, izole yüksek gün, açıklanamayan.
- Günlük düzey değişkenliği yüksektir (Kasım 2023 hafta içi öğle medyanı 74 bin ile 262 bin arasında). 4 haftalık medyan baseline boşluklara ve düzey kaymasına kırılgandır.
- Hava eşiği farkı (AÇIK): get_weather günlük yağış p90'ını bugünkü çıktılarda 7,5 mm verir, docs/07 E01 teşhis notunda 7,2 mm yazılıdır. Fark açıklanmadı (olası neden: o gün yüklü hava dosyaları kümesinin farklı olması; doğrulanmadı). İlgili pencerelerde yağış her iki eşiğin de altında olduğundan karar etkilenmedi.
- 24 ve 31 Mart 2023: 24 saatin tamamı kaynak dosyada eksik. Bu yüzden 7, 14 ve 21 Nisan 2023 (cuma) için baseline'da yalnızca 2 geçerli hafta kalır (en az 3 gerekir) ve tarama bu günleri 'değerlendirilemedi' olarak gösterir. Hata değil, tasarlanan davranıştır: sistem eksik baseline ile tahmin yürütmez. Bu günler hakkında normal veya anormal denemez.
