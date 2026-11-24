# 07 - Değerlendirme Sonuçları ve Bilinen Sınırlar (13 Kasım 2026)

| Set | Sonuç |
|---|---|
| v0 (16 pencere, eşikler Nisan 2023 üzerinde ayarlı, iyimser) | 14/16, yanlış alarm 0/6 |
| v1 (12 rastgele, bağımsız etiket) | 8/12, yanlış alarm 0/8, veri_hatası 0/4 |
| v2 önce (14 tabakalı, label + veri_sorunu) | 11/14, veri_sorunu recall 3/5, precision 3/4 |
| v2 sonra (düzeltme: boşluk >= %25, uyarı alanı) | 12/14, recall 4/5, precision 4/5 (W10 hariç 4/4) |

Düzeltme v1 vakalarından türetildi; v2 yalnızca küçük bir doğrulama (14 pencere).

## Bilinen sınırlar
- W11: ani düşüş ETL tarafından işaretlenmediğinde veri sorunu yakalanmıyor.
- W10: baseline'da 3'ten az geçerli hafta varsa "değerlendirilemedi" (doğru davranış, metrikte precision'ı düşürür).
- W12: günlük medyan, yalnızca gündüz görünen tatil etkisini seyreltiyor (0.86 ve eşik 0.85).
- Hava ve deprem etiketli pencere örnekte yok: bu nedenleri ayırma becerisi ölçülmedi.
- RAG: bilgi tabanında cevabı olmayan ama konu içi sorularda ilgisiz not dönüyor (3/3 zor soru).
- LLM yalnızca açıklama üretir; karar kuraldadır, doğrulayıcı reddederse kural metni kullanılır.
- Ajan notları araç adına göre getirir; anlamsal arama ayrı soru-cevap yolunda.

## v3 (13 pencere, dış etiket, İLK KOŞU, düzeltme yapılmadı; 13 Kasım 2026)
- Neden: tam eşleşme 11/13; yanlış alarm (etki_yok) 0/7 ama 4/7'si değerlendirilemedi (C01-C04, baseline yetersiz); E05'te ajan "deprem" demedi, belirsiz bırakıp insana sordu.
- veri_sorunu: recall 3/3, precision 3/9, doğru negatif 4/10. Etiket yalnız eksik saate bakar; hücre kapsamı düşüşü yakalanmaz, precision alt sınır olabilir.
- Olay nedenleri: tatil 2/2 (E02, E03), hava 0/1 (E01 kar), deprem 0/1 (E06). Örneklem birer vaka, kesin değil.
- Bulgu: ETL yoğunluk kuralı (ay medyanı) bayram ve kar günlerini veri sorunu diye işaretliyor (E01, E02, E03 ETL logunda işaretli).
- Hata (benim): kontrol günleri komşu ay olmayan aylardan seçildi, 4/7 kontrol değerlendirilemedi.
- E07 ve E09 etiketleri veri boşluğuna dayanır, bağımsız dış doğrulama değildir.

## v3 sonrası notlar (13 Kasım 2026; sonuçlar değişmedi)
- E01 karışık vaka: 24 Ocak 2022 aynı zamanda yarıyıl tatilinin ilk günü (MEB takvimi 24 Ocak - 4 Şubat). Baseline (17/10/3 Ocak, 27 Aralık) büyük ölçüde okul günleri. Bu nedenle "hava 0/1" tek başına hava tespitinin ölçüsü değildir; etiket dış kaynaktandır, kısıt planlama sırasında gözden kaçtı (E02'de ara tatil not edilmişti, E01'de edilmedi).
- get_calendar yalnız resmî tatil ve bayramı bilir; okul takvimi (yarıyıl, ara tatil) yok.
- E06: get_earthquakes lookback_h=12 varsayılanı, 6 Şubat depremini 9 Şubat penceresinin dışında bıraktı; araç gecikmeli kurumsal etkileri "deprem" olarak açıklayamaz (tasarım sınırı, hata değil).
- ETL yoğunluk ve kapsam işaretleri baseline'dan çıkarır; E01'de 21-23 saatleri kapsam listesinde (oran 0.89-0.90), kapsam eşiği 0.9.

## v3 veri_sorunu dökümü (snap_v3.jsonl'den hesaplandı, 13 Kasım 2026)
- E01: veri_sorunu=hayır | veri_hatası hipotezi: yalnız_uyarı
- E02: veri_sorunu=hayır | veri_hatası hipotezi: yalnız_uyarı
- E03: veri_sorunu=hayır | veri_hatası hipotezi: yalnız_uyarı
- E05: veri_sorunu=hayır | veri_hatası hipotezi: yok
- E06: veri_sorunu=hayır | veri_hatası hipotezi: yok
- E07: veri_sorunu=evet | veri_hatası hipotezi: destekliyor
- E09: veri_sorunu=evet | veri_hatası hipotezi: destekliyor
- C01: veri_sorunu=hayır | veri_hatası hipotezi: belirsiz
- C02: veri_sorunu=hayır | veri_hatası hipotezi: belirsiz
- C03: veri_sorunu=evet | veri_hatası hipotezi: belirsiz
- C04: veri_sorunu=hayır | veri_hatası hipotezi: belirsiz
- C05: veri_sorunu=hayır | veri_hatası hipotezi: yok
- C06: veri_sorunu=hayır | veri_hatası hipotezi: yok
- sıkı (yalnız "destekliyor"): recall 2/3 | precision 2/2
- orta ("destekliyor" + "belirsiz"): recall 3/3 | precision 3/6
- gevşek = resmî (hipotez desteklemiyor değilse veya ETL uyarısı varsa): recall 3/3 | precision 3/9

## v3 teşhis düzeltmesi (13 Kasım 2026; evidence.py okundu; sonuçlar değişmedi)
- E01 ve E06 karar kapısında durdu: neden hipotezleri yalnız pencere medyan oranı <0.85 veya >1.15 ise değerlendirilir. E01 temiz medyan 0.91, yani "belirgin sapma yok". Aşırı hava kuralı da sağlanmıyor (yağış 4.6 < p90 7.2; rüzgâr 33.4 < 40). Saat bazlı yerel düşüş (n_clean_below_0.7=3, 20:00 oranı 0.59) hesaplanır ama karar kuralında kullanılmaz (yalnız LLM özetinde).
- Önceki nota düzeltme: E06'da lookback_h tek başına neden değil; pencere kapıda durdu. Ayrıca evidence.py'de deprem hiçbir koşulda "destekliyor" olmaz (en fazla "belirsiz"); etiket "deprem" için tam eşleşme yapısal olarak imkânsız, doğru davranış belirsiz ve insana sor (E05'te böyle davrandı).
- Okul takvimi, kapsam-yalnız dışlama ve hava eşiği önerileri E01'i değiştirmezdi (kapının arkasında). Düzeltme turu KULLANILMADI: tek gerçek çözüm kapıyı (saat bazlı yerel kural) değiştirmek olurdu; E01'e uydurma ve yanlış alarm riski. Bilinen sınır olarak raporlanır: gün düzeyi medyan, yerel ve saatlik etkileri seyreltir.
- veri_sorunu precision tanımı: eval "rapor" = hipotez desteklemiyor değilse VEYA herhangi bir ETL işaretli saat; "belirsiz" ve tek saatlik işaret "bildirildi" sayılır. Resmî sayı 3/9 kalır; sıkı, orta ve gevşek döküm yukarıda ayrı verilir (post-hoc, ölçüm tanımı, ajan değişmedi).

## 17 Kasım 2026: v3 sonrası değişiklikler ve keşif bulguları (v3 sayıları DEĞİŞMEDİ)
- v3 sayıları (11/13, yanlış alarm 0/7, veri_sorunu recall 3/3, precision 3/9), v3 etiketinden ÖNCEKİ kuralla elde edilen ilk koşudur ve değişmemiştir.
- v3 etiketinden sonra karar kuralını değiştiren tek ekleme: karışık durum kuralı (pencerenin >= %25'i kaynak dosyada eksik ve sapma temiz saatlerde sürüyorsa güven düşük ve insan gerekli). Bu kural etiketli pencerelerle ÖLÇÜLMEDİ; v4 kapsamında ölçülene kadar "ölçülmemiş" sayılır. G_yarı_eksik kapılarının beklentileri bu kurala göre güncellendi (kural testlere göre ayarlanmadı).
- Diğer eklemeler (tarama, grafik, olası nedenler, kanıt türü, genel değerlendirme, kaynak bilgisi, saatlik bilgi, iki aşamalı araç seçimi, geri bildirim kaydı) gösterim veya kayıt katmanıdır; karar çıktısını değiştirmez.
- Keşif (etiketsiz) 10 şiddetli pencerede ajan davranışı: 4 pencerede neden desteklendi (tatil 3: 9-10 Nis 2024, 12 Nis 2024, 28-29 Haz 2023; hava 1: 24-25 Oca 2022), 6 pencerede "açıklanamayan", güven düşük, insan gerekli (25 Oca 2024, 31 Oca 2024, 4 Mayıs 2023, 23 Kas 2023, 8 Nis 2023, 28-30 Nis 2024). Hiçbirine uydurma neden yazılmadı. Bu koşuda --answer onayla ile onay otomatik verildi; "onaylandı" gerçek insan kararı değildir ve doğruluk ölçüsü değildir.
- Bilinen yeni sınırlar: (1) 4 haftalık baseline boşluk ve düzey kaymasına kırılgan (Ocak 2024: 15-23 Ocak eksik, sonrasında düzey yaklaşık 2 kat; 25 ve 31 Ocak "artış" oranı 2.1, açıklanamayan). (2) ETL işaretli saat oranı yüksekken (28-30 Nis 2024: 43 saatin 39'u, temiz saat 4) karışık durum kuralı yalnız eksik saati sayar; ajan "veri hatası: desteklemiyor", "açıklanamayan", insan gerekli der. Sonuç güvenli ama etiket yanıltıcı olabilir. (3) Gün düzeyi gürültü yüksek: 3 saatlik yerel bölge günlerin %60'ında çıkar (arayüz taban notu, 394 gün), gösterimde şiddete göre sıralanır. (4) Okul tatili ve arife yarım günü araçta yok. (5) p90 yağış eşiği 7.5 mm (araç) ile 7.2 mm (E01 notu) arasındaki fark açıklanmadı.
- v4 adayları (kural değişikliği; yalnız yeni, önceden etiketlenmiş pencerelerle değerlendirilir): baseline kalitesi (baseline haftalarının eksikliği ve düzey farkı), kalıcı düzey kayması, ETL işaretli saat oranını karışık duruma katmak, hücre kapsamı ve saatlik yerel düşüşün kararda kullanımı, MEB okul takvimi ve arife bağlamı, komşu gün ikinci referans.
- RAG: mesafe eşiği "bilgi tabanında cevap var mı" sorusunu ayırt edemez (AUC 0.80); bu nedenle kapsam kararı kodda (scope.py). Rerank adımı uygulanmadı.
- Arayüz denemesi (17 Kasım, keşif, etiketsiz): (6) 25 Nisan 2023 14:00-18:00 penceresinde 14 eksik saat pencere dışında kaldığı için (pencere dışı eksik saat) karışık durum kuralı tetiklenmedi, sonuç "açıklanamayan, güven düşük, insan gerekli"; ek inceleme gün düzeyinde 14/24 eksik gösterdi. (7) Ret formundaki iddia (kayıt no 2: "bu günün verisinin büyük kısmı eksik") pencereye göre sınandı, pencerede eksik saat olmadığı için "kanıt_yok, sonuç_korundu" çıktı; gün düzeyinde doğru olsa bile pencerede doğrulanmadı. İki durum da v4 adayı: komşu saat ve gün kapsamını kararda kullanma ve iddiayı gün düzeyinde de sınama.

## v4 (18 pencere, dış etiket, İLK KOŞU, kural ve eşik değiştirilmedi; 20 Kasım 2026)
- Kod: 159cd70 (dal v4-olcum, master 509c33f üzerine yalnız eval dosyaları ve betikler; ajan kodu değişmedi). Ölçüt eval_v4.py'de sonuçlardan önce commit edildi. v3 ile birleştirilmedi.
- Veri kapsamı bulgusu: 2021-12..2024-04 aralığında yalnız 465 tam gün (24 saat) var. Şubat-Eylül 2022, Aralık 2022, Ekim 2023 ve Şubat 2024 tamamen yok, Ocak 2024 kısmi. 13 adayın 7'si kapsam şartını (24 saat ve en az 3 geçerli baseline haftası) sağlamadığı için elendi; şart gevşetilmedi. Elenenler: V4-01 (10 Mart 2022 kar), V4-02 ve V4-03 (Ağustos 2022 sağanak), V4-04 (26 Haziran 2023 idari izin), V4-06 (27 Mart 2022 yarı maraton), V4-08 (5 Kasım 2023 maraton), V4-11 (14 Mayıs 2023 seçim). Kalan: 6 olay + 12 seed'li kontrol günü.
- Sonuç: tam eşleşme 15/18. hava 1/2, araç_dışı 3/4, etki_yok (kontrol) 11/12. Kontrol yanlış alarm 1/12, değerlendirilemedi 0/12.
- Ölçüt notu (ölçüt kodundaki hata): V4-05'te ajan "açıklanamayan", güven düşük, insana sordu. Kayıtlı niyet bu davranışı doğru saymaktı ama kodda "açıklanamayan" da "destekliyor" sayılıp MISS yazıldı. Resmî sayı 15/18 kalır. Yan not (post-hoc): adlandırılmış neden (hava, tatil, deprem, veri_hatası) uydurma 4 araç_dışı günde 0. Bu 0'ın değeri sınırlı: V4-07, V4-12 ve V4-13'te sistem sapma görmedi, "neden yazmama" yolu yalnız V4-05'te sınandı.
- V4-09 (28 Eylül 2023 sağanak): hava doğru bulundu. V4-10 (29 Kasım 2023 fırtına ve sağanak): neden desteklenmedi. Teşhis (post-hoc, kural değişmedi): tüm saatlerle günlük medyan oranı 0.83 (<0.85, kapı açılırdı); ETL yoğunluk kuralı 13:00, 14:00 ve 16:00'yı (oran 0.41-0.49) veri sorunu diye işaretleyip temiz medyandan çıkarınca oran 0.89 oldu, kapı kapandı, hava aracı hiç çağrılmadı. Kapı açılsaydı hava kuralının sonucu bilinmiyor. v3'te E01, E02 ve E03'te görülen "ETL yoğunluk kuralı hava ve bayram günlerini veri sorunu sayıyor" bulgusunun bağımsız ikinci olayda tekrarı.
- VC08 (5 Ağustos 2023, Cumartesi, kontrol): oran 0.83, yağış 0, tatil ve deprem yok; ajan "açıklanamayan", güven düşük, insana sordu (tasarıma uygun). v3 ölçütüyle yanlış alarm sayıldı. Olası nedenler (doğrulanmadı): yaz düzeyi düşüşü (baseline Temmuz), baseline'da 15 Temmuz resmî tatili. Kontrol günü seçimi baseline haftalarının tatilini dışlamadı (benim eksiğim); kontrol günlerinin hava ve olay durumu ayrıca doğrulanmadı.
- veri_sorunu: recall 0/0 (veri_sorunu=evet pencere yok), precision 0/7, doğru negatif 11/18. 7 pencerede ETL işareti "bildirildi" sayıldı (V4-05, V4-09, V4-10, V4-13, VC03, VC07, VC09); v3'teki "ETL işareti fazla bildiriyor" bulgusu (3/9) tekrar etti.
- Sınırlar: 18 pencere, hava 2 olay (kesin hüküm yok). Kontrol günü etiketleri dış kaynakla doğrulanmadı. V4-07, V4-12 ve V4-13'te kaynaklar olayı doğrular, trafikte sapma yarattığını doğrulamaz; sistemin sapma görmemesi tutarlı bir bulgudur.
- Karar kuralı değiştirilmedi. v4'ten doğan adaylar (ölçülmemiş, yeni etiketli pencerelerle değerlendirilir): (1) saatlik yerel düşüşün kararda kullanımı; (2) ETL yoğunluk işaretli saatlerin hava günlerinde kapıyı kapatmaması; (3) kontrol seçiminde baseline tatil ve hava temizliği.

## Kamu idari izni (20 Kasım 2026, ölçülmemiş karar kuralı değişikliği)

Dal: idari-izin (1d44d8c). Test: tests/idari_izin_test.py (9 kapı), run_all ve e2e_final 26/26 yeşil.

Değişiklik: calendar_ctx.ADMIN_LEAVE'e 8-9 Nisan 2024 (Ramazan Bayramı öncesi, kaynak: capital.com.tr haberi) eklendi. Karar kuralı: pencerede TAM GÜN kamu idari izni varsa ve resmî tatil yoksa, tatil hipotezi "desteklemiyor" yerine "belirsiz" olur. Böylece güven "düşük" olur ve insana sorulur; "açıklanamayan" yolu kapanır. Yarım günler (9 Nisan 2024, 27 Haziran 2023) yalnız bağlam notu olarak kalır, karar değişmez.

Neden "belirsiz", "destekliyor" değil: izin yalnızca devlet memurlarını kapsar, özel sektör ve toplu taşıma kullanımı için etkisi kısmi olabilir. Kanıt "olabilir" düzeyinde, "açıklar" düzeyinde değil.

ÖLÇÜLMEDİ: Bu kural v3 ve v4 setlerinde yeniden ölçülmedi. v4'te V4-05 (9 Nisan 2024) yarım gün olduğu için sonucu değişmez; tam gün idari izne denk gelen etiketli bir pencere sette yok. Tek kanıt demo penceresi 8 Nisan 2024 ve birim testleridir. Bu pencere kurala göre ayarlanmış değildir, kural önce yazılıp pencere sonra kontrol edilmiştir; ancak tek pencereyle doğrulanmış bir kuralı genel doğru saymıyoruz.

## 20 Kasım ek ölçümleri: kapı ve ETL adayları

Hepsi v3 ve v4 etiketli pencerelerde ve 523 günlük tüm veride, önceden yazılmış eşikle ölçüldü. Eşik hiçbir olaya göre ayarlanmadı. Her aday ayrı dalda denendi, sonuçlar `eval/` altında.

- **A, yerel düşüş kuralı (reddedildi):** 1 doğru yakalama, 2 yanlış alarm. Kazanç yok.
- **B, tüm-saat medyanı kapısı (kabul edildi, `saatlik-yerel` dalı):** Temiz saatlerde sapma yokken ETL işaretli saatler dahil medyan eşiğin dışındaysa kapı açılır. ETL payı 0.25'in altındaysa uygulanır (üstü ETL-payı kuralına bırakılır), `veri_hatası` bu durumda `belirsiz` olur. Etiketli sonuç v4 16/18, değişen tek pencere V4-10. Dikkat: B bu pencereden esinlenerek yazıldı, bağımsız doğrulama yok. 523 günde yalnız 3 günü etkiliyor (2023-07-31, 2023-11-29, 2024-01-01). Demo pencereleri etkilenmiyor.
- **C, baseline'da tatil ve idari izin haftalarını çıkarma (alınmadı):** 523 günde 7 gün değişti, etiketli pencerede değişim yok, VC08 düzelmedi, veri kapsamı azalıyor.
- **D, çok noktalı hava (7 nokta, maksimum yağış, p90 yeniden) (alınmadı):** 54 pencerede 2 bayrak değişti, ikisi de yanlış yönde (W10, V4-12). Hava etiketli pencerelerde kazanç yok, E01 yine eşik altı (maksimum 10,8 mm, yeni p90 11,3 mm). Not: ölçüm betiğinin tek nokta p90'ı 6,9, `tools.get_weather` 7,5; sonucu değiştirmiyor.
- **E, ETL yoğunluk kuralında `mild` saatleri temiz sayma (alınmadı):** Kapı yalnız 1 günde değişti (2023-06-24, oran 1.16 -> 1.15, sınırda), ETL-payı kuralı hiç değişmedi, etiketli pencerelerde değişim yok. Kapsam: yalnız kapı ve pay kuralı ölçüldü, `veri_hatası` hipotez etiketi ölçülmedi.

## 20 Kasım: B için bağımsız bakış (B master'a ALINMADI)

B (tüm-saat medyanı kapısı) 523 günde yalnız üç günü değiştiriyor. Bu günler master (B yok) ve `saatlik-yerel` (B var) ile yan yana çalıştırıldı:

- **2023-07-31:** master oran 0.88, sapma yok. B oran 0.84, sapma var, güven düşük, insan gerekli (`veri_hatası` belirsiz, diğer hipotezler desteklemiyor). Bağımsız kaynakta o güne ait bir olay bulunamadı; **doğrulanmadı**.
- **2023-11-29:** master oran 0.89, sapma yok. B oran 0.83, hava destekliyor (yağış 30.6 mm, rüzgâr 52.9 km/sa). Bu gün V4-10, yani B'yi yazdıran pencere: bağımsız değil.
- **2024-01-01:** master oran 0.85, sapma yok (tatil desteklemiyor). B oran 0.84, sapma var, tatil destekliyor (Yılbaşı). Bağımsız kaynak: DHA ve AA haberleri, saat 09.15'te İBB trafik yoğunluğu yüzde 1 (https://www.posta.com.tr/gundem/istanbulda-yilin-ilk-gunu-otoyollar-sokaklar-ve-caddeler-bos-2686723 , https://www.gzt.com/gundem/istanbulda-yilin-ilk-gunu-yollar-bos-kaldi-2039026).

Yorum: üç günde de fark eşik bandının kenarında (master 0.85-0.89, B 0.83-0.84; alt eşik 0.85). B, eşiğin hemen altına düşen tüm-saat medyanını yakalıyor. 2024-01-01'de yön doğru (gerçek tatil düşüşü), ama eşik kenarında olduğu için sağlam kanıt sayılmaz; 2023-07-31 için kanıt yok. Bağımsız doğrulama yalnız bir günde (1/3).

Karar: B master'a alınmadı, `saatlik-yerel` dalında duruyor (denendi, ölçüldü, kısmen teyit edildi). Gerekçe: kanıt ince, karar kuralı değişikliği az sayıda günü etkiliyor ve B tek pencereden esinlenerek yazıldı ("tek olaya göre ayar yok" ilkesi).

## 20 Kasım: veri_sorunu kesinliği 0/7 nasıl okunmalı (ölçüm, post-hoc)
- v4'te 18 pencerenin hiçbirinde gerçek veri sorunu yok. 0/7 = 7 "bildirildi", 0 doğru; geri çağırma v4'te tanımsız (0/0).
- eval_v4.py'deki "veri_bildirildi" üç ayrı şeyi tek sayıda topluyor: iddia (veri_hatası destekliyor), belirsiz ve yalnız veri_kalitesi_uyarısı notu.
- Kademeler (snapshot'lardan, scripts/olcum/veri_kademe_olc.py): iddia v3'te 2/2 doğru (geri çağırma 2/3), v4'te iddia yok (yanlış iddia 0); belirsiz C01-C04 1/4 gerçek; yalnız uyarı notu v3'te 0/3, v4'te 0/7.
- Kod ve eşik DEĞİŞMEDİ. Kademe ayrımı sonuçlar görüldükten sonra yapıldı (post-hoc): açıklama, kanıt değil.
- Kaçan tek gerçek pozitif (C03) yoğunluk kuralından değil, yetersiz geçmiş veriden (belirsiz) geliyor; eşik kuralı bunu düzeltmez.
- Sınırlar: gerçek pozitif yalnız 3 (v3), v4'te sıfır; uyarı notunun içeriği (işaretli ve eksik saat) snapshot'ta yok, yoğunluk kuralı ile ilişkisi bu ölçümden doğrudan gösterilmedi.
- Sonuç: gate'te veri hatası iddiası için kanıtlanmış bir hata yok; "precision 0/7" ifadesi iddia kesinliği olarak okunmamalı.

## 20 Kasım: hava penceresi ve idari izin kurallarının etkisi (ölçüm, doğrulama değil)
- Yöntem: eval/kural_etki_onkayit.txt (ölçümden önce yazıldı), scripts/olcum/kural_etki_olc.py, eval/kural_etki_olcum.txt. İlk çalıştırmada yamalar tools ve calendar_ctx üzerine yapıldı, ama evidence.py "tools_gw" kullandığı için etkisizdi; "ölçülemedi" diye eval/kural_etki_olcum_1_yama_etkisiz.txt olarak saklandı. Düzeltilmiş ölçümde yama sayaçları var.
- İdari izin (4 gün): kural yalnız 2024-04-08'de etkili. Kapalıyken tatil "desteklemiyor", açıklanamayan "destekliyor"; açıkken tatil "belirsiz", açıklanamayan "desteklemiyor". Güven (düşük) ve insan onayı ikisinde de aynı. 2023-06-26 (sapma yok), 2023-06-27 ve 2024-04-09 (yarım gün; kural yalnız tam gün) değişmedi. 2024-04-08 etiketli pencerelerde yok: kuralın doğruluğu ölçülemez, etkisi 1 gün.
- Hava penceresi, etiketli 57 pencere: karar değişen 0; yalnız 1'i çok günlü, üç hava etiketli pencere tek gün (toplam = gün_max: 4.6, 13.8, 30.6 mm; p90 7.5). Etiketler bu kuralın doğruluğu hakkında bilgi vermez.
- Yalnız yağış, kayan pencere 2021-12-01..2024-04-30 (üst üste binen, birbirine bağımlı): 3 gün 555 pencere: eski kural (toplam > p90) 164, yeni (en yağışlı gün > p90) 134, bastırılan 30. 7 gün 567 pencere: eski 315, yeni 251, bastırılan 64.
- Yapısal bulgu: yeni kural da çok günlü pencerede "aşırı hava" oranını şişiriyor: tek günlük p90 (7.5 mm) ile pencere içindeki en yağışlı gün karşılaştırıldığı için 7 günlük pencerelerin %44'ü, 3 günlüklerin %24'ü aşırı sayılıyor (tek günde beklenen yaklaşık %10). Gün sayısına göre eşik düzeltmesi YAPILMADI; çok günlü pencerelerde "hava destekliyor" tek başına nedensellik kanıtı sayılmamalı. Hava, sapma varken ek kanıt olarak okunmalı.
- Sınırlar: yalnız-yağış sayımı judge'dan geçmedi (sapma şartı ve rüzgâr dışarıda); kayan pencereler bağımlı; hava etiketli yalnız 3 pencere.
