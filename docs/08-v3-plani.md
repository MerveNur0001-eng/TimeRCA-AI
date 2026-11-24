# 08 - v3 Planı: gerçek olaylarla ölçüm (13 Kasım 2026)

## Kural (değişmez)
1. Olay önce seçilir, etiket DIŞ kaynaktan gelir (resmî takvim, haber, USGS). Trafik verisine bakarak etiket verilmez.
2. Bu dosya, ajan çalıştırılmadan önce commit'lenir (beklentiler dahil).
3. Ajan her vaka için BİR kez çalışır; sonuç olduğu gibi kaydedilir, iyi görünsün diye seçilmez/silinmez.
4. Gerekirse plana bağlı TEK düzeltme turu; sonrası "önce/sonra" olarak ayrı raporlanır. v3 düzeltme vakalarından türetilirse bağımsız set sayılmaz.
5. Kanıt yetersizse doğru cevap "açıklanamayan" + insan onayıdır; bu bir başarı sayılır, hata değil.

## Vaka listesi (taslak; doğrulama sütunu doldurulmadan çalıştırma yok)
| ID | Olay | Beklenen etiket | Etiket kaynağı | Doğrulama | Beklentim |
|---|---|---|---|---|---|
| E01 | İstanbul kar fırtınası, ~24-26 Ocak 2022 | hava | haber + Open-Meteo kar/yağış | ? | hava; ETL yoğunluk uyarıları 23-26 Ocak'ta var |
| E02 | Ramazan Bayramı 9 günlük tatil, ~6-14 Nisan 2024 | tatil | resmî takvim / Resmî Gazete (idari izin) | ? | tatil; Nisan 2024 baseline'ı bayramı da içeriyor olabilir -> dikkat |
| E03 | Kurban Bayramı ~28 Haz-1 Tem 2023 (uzatma var mı?) | tatil | resmî takvim | ? | tatil; 3 Temmuz uzatması doğrulanmalı |
| E04 | Ramazan Bayramı ~21-23 Nisan 2023 | tatil | resmî takvim | ? | tatil (eski ayda, ayarlı eşiklerle yakın; iyimser) |
| E05 | Düzce depremi M6.1, 23 Kas 2022 01:08 UTC (04:08 TSİ) | deprem veya etki_yok | USGS + haber (İstanbul etkisi) | ? | İstanbul etkisi haberle doğrulanmazsa etiket: etki_yok / açıklanamayan |
| E06 | Kahramanmaraş depremleri 6 Şubat 2023 | deprem (etki varsa) | USGS + haber (okul/ulaşım kararları) | ? | etki belirsiz; açıklanamayan kabul edilebilir |
| E07 | Kasım 2023 13-14 arası 48 saatlik veri boşluğu | veri_hatasi | ETL logu (kaynak boşluğu) + portal | ? | veri_hatasi veya değerlendirilemedi |
| E08 | Nisan 2024 sonu (28-29) hücre kapsamı düşüşü | veri_hatasi | ETL logu; haber/hava olay yok ise | ? | veri_hatasi; yoksa açıklanamayan |
| E09 | Ocak 2024 (338 eksik saat) | veri_hatasi | ETL logu | ? | değerlendirilemedi / veri_hatasi |
| E10 | Olaysız kontrol günleri (en az 4, takvim+hava+USGS'te olay yok) | etki_yok | aynı üç kaynak | ? | yanlış alarm 0 |

## Ölçütler
- Tam eşleşme (etiket), yanlış alarm (etki_yok vakalarında), veri_sorunu recall/precision
- Kanıt yetersizken "açıklanamayan"a dönme oranı ayrı raporlanır
- Her vaka için: ajan notları, kaynaklar, insana soru bayrağı

## Bilinen riskler
- Ekim 2022 portal kaydı eski (yerel > portal), veri kendi içinde tam (744 saat)
- Aynı ayın içindeki bayram günleri baseline'ı bozabilir (W10/W12 dersi)
- Küçük örneklem: sonuçlar kesin değil, eğilim gösterir

## Doğrulama (13 Kasım 2026, ajan çalıştırılmadan önce; ilk commit 46a21da korunur)
- E01 doğrulandı: kar 22 Ocak akşamı başladı, 24 Ocak zirve, İST havalimanı uçuşları durdu, 25 Ocak kamu idari izinli. Not: ETL'de 23 Ocak 05-09 arası 5 saatlik boşluk kar sırasında; hava/veri karışımı riski.
- E02 doğrulandı: bayram 10-12 Nisan, arife 9 Nisan yarım gün; kamuda 8 Nisan tam + 9 Nisan yarım gün idari izin (9 gün, 6-14 Nisan); özel sektörde otomatik değil; okul ara tatili aynı hafta. Etki karışık, etiket: tatil.
- E03 DÜZELTME: uzatma 3 Temmuz'a değil; idari izin 26-27 Haziran, tatil 24 Haziran-2 Temmuz, 3 Temmuz normal iş günü. Etiket: tatil.
- E04: tarih doğrulandı (arife 20 Nisan, bayram 21-23 Nisan 2023). İdari izin doğrulanmadı.
- E05: Düzce depremi İstanbul'da hissedildi (vali açıklaması) ama İstanbul'da okul/ulaşım kararı yok; okullar Düzce, Sakarya, Bolu, Ereğli'de tatil. Deprem 04:08 (düşük trafik saati). Etiket: etki_yok. Ajan "deprem" derse aşırı atıf sayılır. Büyüklük: haberlerde 5.9, USGS 6.1.
- E06: 6 Şubat 2023 sonrası okullar tüm Türkiye'de önce 13, sonra 20 Şubat'a kadar tatil; YÖK tüm yükseköğretimi durdurdu. Etiket: deprem. Beklenti: İstanbul yarıyıl tatili de ocak sonuna kadardı, Ocak baseline'ına benzeyebilir; ajan etki görmeyebilir, bu doğru bulgu sayılır.
- E07, E09: etiket kaynağı ham CSV'de ilgili saat satırının olmaması. ETL logu ajan girdisi olduğu için bağımsız dış doğrulama değil; 'veri hatası tespiti' testi olarak AYRI raporlanır.
- E08 ÇIKARILDI: dış kaynakta etiket bulunamadı (sonuca bakılarak değil, etiket kaynağı olmadığı için).

## E10 kontrol günleri (kural ile seçildi; trafik verisine bakılmadı)
Kural: Salı-Perşembe; aylar 2021-12, 2022-10, 2022-11, 2023-11, 2023-12, 2024-03; bayram/resmî tatil/olası ara tatil/E05/E07 günleri dışarıda; yağış<=0.5 mm, rüzgâr<=35 km/sa, min sıcaklık>0 (Open-Meteo); İstanbul'a 300 km içinde M4+ deprem +-1 gün yok (USGS); seed 20261113, 6 gün.
Günler: 2021-12-01, 2021-12-02, 2022-10-12, 2022-10-19, 2022-11-30, 2023-12-19
Beklenen etiket: etki_yok (yanlış alarm 0).

- E04 v3'ten ÇIKARILDI (13 Kasım): 21 Nisan 2023 penceresi v2'deki W10 ile çakışıyor (Ramazan Bayramı 2023 zaten ölçüldü: W10 tatil, ajan değerlendirilemedi). Çakışma kontrolü scripts\olcum\build_v3_sheet.py içinde; gerekçe sonuç değil, bağımsızlık.
- Pencereler: bayram/olay günleri takvimden (ilk hafta içi gün), veri_sorunu ham veride eksik saat varsa 'evet' (trafik değerine bakılmaz; hücre kapsamı düşüşü yakalanmaz).
