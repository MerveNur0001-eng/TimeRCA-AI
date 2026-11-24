# 09 - Final Rapor: TimeRCA-AI

## 1. Problem ve amaç
Zaman serilerinde ani düşüş veya beklenmeyen artış olduğunda, değişimin gerçek bir olaydan mı yoksa veri toplama, işleme veya aktarım hatasından mı kaynaklandığını bulmak çoğu zaman farklı kaynakların elle taranmasını gerektirir ve müdahale süresini uzatır. TimeRCA-AI, olası nedenleri araçlarla araştıran, bulgularını kaynaklarıyla raporlayan, kanıt yetersizse insana soran ve kesin neden bulamazsa "açıklanamayan" diyen yerel (Ollama) bir ajandır.

## 2. Hedef - kanıt eşlemesi
| Hedef | Durum | Kanıt |
|---|---|---|
| Ani düşüş/sıçrama tespiti | Tamam | Pencere medyanı, önceki 4 haftanın aynı gün-saati medyanıyla karşılaştırılır (eşik 0.85/1.15); src/evidence.py |
| Farklı veri kaynakları ve araçlar | Tamam | 5 araç: ETL logu, geçmiş karşılaştırma, hava, resmî takvim, deprem; src/tools.py, MCP sunucusu, HTTP API |
| Veri hatası ile gerçek olayı ayırma | Kısmen | Veri hatası ve tatil ayrımı ölçüldü (bölüm 5). Hava ve deprem nedenleri kanıtlanmadı: hava 0/1, deprem 0/1 |
| Bulguları kaynaklarıyla raporlama | Tamam | Pydantic JSON rapor: hipotez başına kaynak araç, bilgi tabanından kaynaklı notlar, ham araç çıktıları; docs/demo/ |
| Kanıt yetersizse insana başvurma | Tamam | E05 demosu: insan_onayi_bekleniyor, ardından onaylandi (docs/demo/E05_*.json) |
| Kesin neden yoksa "açıklanamayan" | Tamam | W04 ve E05; özet cümlesi "Kesin neden belirlenemedi (açıklanamayan)" |
| Yerel çalışma | Tamam | Ollama: soru kutusunda soru anlama gemma3:4b (yalnız kural çözemezse), kaynak arama embeddinggemma, komut satırında açıklama gemma3:4b; karar kuralda, LLM karar vermez |
| Otomatik anomali listesi ve grafik | Tamam | src/scan.py, src/series.py, arayüz (GET /); series_real_test 9/9 (gerçek veri tutarlılığı) |
| Farklı zaman serilerine genelleme | Kanıtlanmadı | Yalnızca İstanbul trafiği; araç katmanı seriden bağımsız tasarlandı, başka seride denenmedi |

## 3. Mimari
ETL (scripts/veri/ingest.py, logs/etl_log.jsonl) -> saatlik seri -> LangGraph akışı: araçları topla, hipotezleri kuralla puanla, RAG notlarını getir, güven düşükse insana sor (HITL), rapor üret. Hipotezler: veri hatası, hava, tatil, deprem, açıklanamayan. Deprem hipotezi en fazla "belirsiz" olur; ajan nedensellik iddia etmez. Kanıt yoksa neden uydurulmaz.

## 4. Veri
İBB Açık Veri saatlik trafik yoğunluğu (gerçek veri). 18 ay yüklendi, hiçbirinde boşluksuz veri yok. Hava: Open-Meteo reanalysis. Deprem: USGS yerel katalog (AFAD API geçmiş sorgulara boş döndü). Takvim: holidays paketi; okul tatili, arife yarım günü ve kamu idari izni bağlam olarak eklendi (docs/12).

## 5. Değerlendirme
| Set | Sonuç | Not |
|---|---|---|
| v0 (16 pencere) | 14/16 | Eşikler bu veriye ayarlı, iyimser |
| v1 (12 pencere) | 10/12 | İlk koşu 8/12; düzeltme bu vakalardan türedi |
| v2 (14 pencere) | 12/14 | İlk koşu 11/14; düzeltme v1'den türedi, küçük doğrulama; veri sorunu recall 4/5, precision 4/5 |
| v3 (13 pencere, dış etiket) | 11/13 | İlk koşu, düzeltme yok; yanlış alarm 0/7; veri sorunu recall 3/3, precision 3/9 (kısıtlı tanımda 2/2) |

Dürüst okuma: yalnızca v3 gerçekten bağımsızdır ve 13 pencere, 20-30 hedefinin altındadır. Sonuçlar eğilim gösterir, kesin değildir. v3'te 4/7 kontrol günü baseline yetersizliği nedeniyle "değerlendirilemedi" çıktı ve insana yönlendirildi.

### 5.1 RAG değerlendirmesi

- Bilgi tabanı: kb/*.md, 59 parça. Parçalayıcı `line-v1` (satır bazlı), gömme modeli `embeddinggemma`. İndeks parmak izi KB, model veya parçalayıcı değişince indeksi bayat sayar; değerlendirme bayat indekste çalışmayı reddeder.
- Rol: karar kuralda verilir. RAG kararı etkilemez; rapora araç başına kaynaklı not ekler ve soru-cevap yolunu besler.
- Soru seti: eval/rag_final.jsonl, 24 soru (14 cevaplı, 4 kapsam dışı, 3 KB'de cevabı olmayan, 3 konu dışı). Etiketleri sistemi yazan kişi koydu, bağımsız bir set değildir; küçük örneklem nedeniyle sonuçlar yön göstericidir.
- Cevaplı sorular: yanlış ret 0/14; ilgili parça ilk sırada 11/14, ilk 3'te 14/14, ilk 5'te 14/14; MRR 0,893.
- Kapsam dışı sorular: 4/4 doğru reddedildi (kural tabanlı scope.py).
- Konu dışı sorular: 3/3 reddedildi (gömme uzaklığı eşiği 0,70, yaklaşık bir karar).
- KB'de cevabı olmayan ama konu içi sorular (3): otomatik metrik yok. Sistem bunları reddetmiyor, "ilgili not (doğrudan cevap olmayabilir)" etiketiyle en yakın notları döndürüyor. Bilinen zayıflık budur.
- Yeniden sıralama (rerank) denemesi: kural tabanlı rerank (cosine + kelime örtüşmesi, deterministik, LLM yok) yazıldı ve 17 kapılı birim testi var (src/rag.py, tests/rag_rerank_test.py). Ölçüm (tests/rag_rerank_olc.py, 23 Kasım): dev2 cevaplı 20 soruda ilk sonuç 14→16, MRR 0,804→0,850; final cevaplı 14 soruda ilk sonuç 11→11, MRR 0,893→0,881 (2 sorunun sırası değişti); kapsam, konu dışı ve zor soru durumları değişmedi. Kabul ölçütü ölçümden önce yazıldı: açık hal hiçbir ölçütte kapalıdan kötü olmayacak. Final MRR'ında gerileme olduğu için ölçüt sağlanmadı ve rerank varsayılan olarak KAPALI bırakıldı (TIMERCA_RERANK=1 ile açılır). Örneklem küçüktür (20 ve 14 soru); fark kesin sayılmaz. Bu yüzden bu belgedeki RAG sayıları rerank'siz haldir.
- Etiket düzeltmesi: kapsam genişleyince (Haziran 2023 ve sonrası yüklendi) iki "kapsam dışı" soru (F15 Eylül 2023, F17 Kurban Bayramı 2023) kapsam içi kaldı ve gerçekten kapsam dışı olan iki soruyla değiştirildi. Bu, sonuca göre ayar değil, veri kapsamı değiştiği için etiket güncellemesidir.

## 6. Bilinen sınırlar
- Karar kapısı gün düzeyi medyana bakar; yerel/saatlik etkiler (E01 kar fırtınası) kaçar.
- Deprem hipotezi hiçbir koşulda "destekliyor" olmaz; en fazla belirsiz + insana sor (E05).
- Takvim aracı okul tatilini yalnız bağlam notu olarak verir, karar kuralında kullanılmaz (E01 yarıyıl tatili karışıklığı; docs/12).
- ETL logu boşluğun nedenini söylemez.
- Hava ve deprem nedenlerini ayırma becerisi ölçülmedi.
- Genelleme denenmedi.
- Baseline (önceki 4 hafta medyanı) boşluklara ve düzey kaymasına kırılgandır (Ocak 2024: 15-23 Ocak eksik, sonrasında düzey yaklaşık 2 kat; 25 ve 31 Ocak 'artış' oranı 2,1, açıklanamayan).
- ETL işaretli saat oranı yüksekken (28-30 Nisan 2024: 43 saatin 39'u) karışık durum kuralı yalnızca eksik saati sayar; ajan 'veri hatası: desteklemiyor', 'açıklanamayan', insan gerekli der. Sonuç güvenlidir ama etiket yanıltıcı olabilir (v4 adayı).
- RAG gömme uzaklığı eşiği 'bilgi tabanında cevap var mı' sorusunu ayırt edemez (AUC 0,80); kapsam kararı bu yüzden kodda (scope.py). Rerank adımı uygulanmadı.
- Hava p90 yağış eşiği: bugünkü araç çıktısı 7,5 mm, docs/07 E01 notunda 7,2 mm; fark açıklanmadı (karar etkilenmedi).
- Okul tatili ve arife yarım günü bağlam notu olarak eklendi, karar kuralını değiştirmez (docs/12). Yol çalışması ve etkinlik verisi yok.
- Pencere dışı eksik saatler karışık durum kuralını tetiklemez (25 Nisan 2023 14:00-18:00: günde 14/24 eksik, pencerede 0). Ret formundaki iddia pencereye göre sınanır; gün düzeyinde doğru bir iddia bu pencerede 'kanıt yok' çıkabilir (v4 adayı).

- Giriş katmanı anahtar kelimeyle yönlendirir: listede olmayan bir kalıp ("trafikte düşüş görüldü mü" gibi) analiz sayılmaz ve bilgi yoluna gider. Aynı soru her zaman aynı yola gider, ama kapsamı sınırlıdır. Saat belirtilemez, tek tarih tam gün analiz edilir.
- İnsan onayı durumsuzdur: karar gelince ajan baştan çalışır (karar ve karar2 ile). Basit ve n8n için ek durum gerektirmez, ama her kararda ajan yeniden koşar. Kalıcı durum (checkpoint) kullanılmadı.
- Hipotez tablosunda deprem "belirsiz" iken "açıklanamayan" işaretlenmez, oysa rapor özeti "açıklanamayan" der (E05). Kural, belirsiz hipotezi açıklama sayar.

- MCP geçişi ölçümü: agent_test (37 kapı) direct modda 5 sn, MCP modunda önbellekli 70 sn, önbelleksiz 673 sn sürdü. Fark, her MCP oturumunda yeni bir Python süreci açılmasından gelir. MCP mod yaklaşık 14 kat yavaştır, ama çağrılar pencere başına bir süreçte toplandığı için tek analiz için kabul edilebilir. Dağıtıkta kalıcı bir MCP sunucusu bağlantısı bu maliyeti ortadan kaldırır.
- Hata enjeksiyonu testleri (final_check hava hatası kapısı, agent_robust_test) süreç içi fonksiyon değiştirdiği için direct modda koşar. MCP modu ayrıca mcp_test ve mcp_stdio_test eşdeğerlik testleriyle doğrulanır. Kapı gevşetilmemiştir, yalnızca doğru modda çalıştırılır.

## 7. Demo senaryoları
- E02 Ramazan Bayramı: tatil destekleniyor, insan gerekmiyor.
- E05 Düzce depremi: deprem belirsiz, insan onayı bekleniyor, onay sonrası tamamlanıyor.
- E07 veri boşluğu: veri hatası destekleniyor.
- E01 kar fırtınası (24-26 Ocak 2022): gün düzeyinde 24 Ocak günü (0,91) ajan sapma görmüyor (kaçırılan vaka); 25 Ocak günü (0,56) sapma var, açıklanamayan ve insan onayı; 3 günlük 24-26 Ocak penceresinde (0,82) hava destekliyor (pencere toplam yağışı günlük p90 ile karşılaştırıldığı için, bkz. docs/13).

## 8. Çalıştırma ve tekrar üretilebilirlik
README.md. Teslim sürümü git etiketi teslim-20261123c (v3-degerlendirme v3 ölçüm noktasıdır); yedek: yerel git bundle. Tüm kapılar: python tests\run_all.py (17 Kasım 2026 çıktısı, TÜMÜ TEMİZ): final_check 31/31, agent_test 37/37 (MCP ve direct), agent_robust_test 6/6, router_test 9/9, evidence_gate_test 9/9, feedback_test 27/27, rag_rerank_test 17/17, bayram_hafta_test 37/37 (24 Kasım), yeni_sorular_test 52/52 (24 Kasım), reliability_test 27/27, selection_test 18/18, scan_test 19/19, series_real_test 9/9 (gerçek veri). Son çalıştırma 23 Kasım 2026: python tests\e2e_final.py --hepsi 26/26 PASS (içinde run_all TÜMÜ TEMİZ). run_all dışında ayrıca çalıştırılan: report_test 7/7, api_test 12/12, agent_hitl_test 10/10.

## 9. n8n tetikleyici
Akış docs/n8n-akisi.json (12 düğüm). n8n, API'nin /ask ucunu çağırır; kanıt yetersizse akış formda durur ve insan Onayla / Ek inceleme / Reddet seçer. Ret kolu: RET MI -> RET FORMU (iddia, açıklama, kaynak) -> GERI BILDIRIM (POST /feedback). DURUM: ret kolu 23 Kasım 2026'da n8n içinde denendi (08.04.2024 penceresi, Reddet, ret formu, GERİ BİLDİRİM adımı /feedback'ten kayıt döndürdü); test kaydı sonra silindi. API anahtarı kullanılacaksa Header Auth credential'ı elle atanmalıdır. Tetikleyici manueldir, canlı veri akışı yok.

## 10. v3 sonrası eklenenler ve ölçülmemiş kısımlar
Eklenenler (ayrıntı docs/02): anomali taraması (src/scan.py), trafik yoğunluğu grafiği (src/series.py, /series), tek sayfa arayüz, iki aşamalı araç seçimi, olası nedenler + kanıt türü + nedensellik notu, genel değerlendirme (çoklu neden), kaynak bilgisi, saatlik bilgi, geri bildirim kaydı (src/feedback.py).

Karar kuralı durumu (dürüst ayrım):
- v3 sayıları (bölüm 5) v3 etiketinden önceki kuralla elde edilen ilk koşudur ve değişmemiştir.
- v3 etiketinden sonra karar kuralını değiştiren TEK ekleme: karışık durum kuralı (pencerenin en az %25'i eksik ve sapma temiz saatlerde sürüyorsa güven düşük, insan gerekli). Etiketli pencerelerle ölçülmemiştir; ölçülene kadar "ölçülmemiş" sayılır (v4).
- Diğer eklemeler gösterim veya kayıt katmanıdır ve karar çıktısını değiştirmez: tarama ve grafik yalnızca aday gösterir, genel değerlendirme karar vermez, geri bildirim kaydı ajanı değiştirmez (öğrenme yok, otomatik kabul yok).

## 11. Keşif bulguları (17 Kasım 2026, etiketsiz)
Gerçek veride grafikten ajan incelemesine kadar uçtan uca denendi. 22 Nisan 2023: oran 0,74, tatil/bayram destekleniyor, güven orta. 19 ve 25 Nisan 2023 (eksik veri + sapma): veri hatası destekleniyor, güven düşük, insan gerekli. 10 şiddetli pencerede ajan 4'ünde nedeni kanıtla destekledi (tatil 3, hava 1), 6'sında "açıklanamayan, insan gerekli" dedi ve neden uydurmadı. Veri bulguları (28-30 Nisan 2024 kapsam çöküşü, Ocak 2024 düzey kayması, baseline kırılganlığı) docs/03 ve docs/07 sonunda. Bu koşular doğruluk ölçüsü değildir ve kural ayarı için kullanılmamıştır.

## 12. Sürdürülebilirlik katkısı (23 Kasım)
Trafik ve hava kalitesi birbirine bağlı şehir göstergeleridir. İBB'nin saatlik NO2 (büyük ölçüde araç egzozundan gelir), PM10 ve O3 ölçümleri trafik verisiyle aynı kuralla (önceki 4 haftanın aynı gün ve saati, 0,85-1,15 eşikleri) karşılaştırılır. Amaç şehir yönetimine şu soruların kanıtlı cevabını vermektir: trafikteki bir azalma gerçek mi, ve havaya yansıdı mı? Bu, Sürdürülebilir Kalkınma Hedefi 11 (sürdürülebilir şehirler ve topluluklar) ile uyumludur.
- **Gösterim özellikleri:** tek günde saatlik trafik ve NO2 eğrileri üst üste; ayda trafiği düşen günlerin kaçında NO2 ve PM10 de düştü; tüm resmî tatil günlerinde trafik ve NO2; trafik ile NO2'nin gün gün ilişkisi (dağılım grafiği, bağıntı ve eğim); iki ay karşılaştırılırken NO2 oranı.
- **Ölçülen örnek:** Nisan 2024'te trafiğin düştüğü 7 günün 7'sinde NO2 de düştü.
- **Sınır:** NO2'nin trafik dışında da kaynakları vardır (ısınma, sanayi), rüzgâr ve yağış da değerini değiştirir. Bu özellikler yalnızca gösterimdir: hipotez puanlamasını, kararı ve özeti değiştirmez (testle sabit). Birlikte hareket nedeni kanıtlamaz.
