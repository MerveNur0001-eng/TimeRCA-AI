# 05 - Doğrulama Durumu (5 Kasım 2026)

| Konu | Durum | Kaynak / not |
|---|---|---|
| NUMBER_OF_VEHICLES = saatte hücredeki farklı araç sayısı | Doğrulandı | İBB veri sözlüğü (data.ibb.gov.tr, saatlik trafik yoğunluğu veri seti) |
| Geohash uzunluğu 6 | Doğrulandı | İBB veri sözlüğü |
| Hücre toplamı aynı aracı birden fazla kez sayabilir | Çıkarım | Sözlükte açıkça yazmıyor |
| DATE_TIME saat dilimi | Resmî kaynakta yok. Varsayım: yerel saat. Veriyle tutarlı, UTC dışlandı | Sözlük yalnızca formatı veriyor. scripts/kesif/tz_check.py (Ocak-Mayıs 2023, medyan profil): gece dibi hem hafta içi hem hafta sonu 03:00; en yüksek 3 saat hafta içi 06, 07, 19, hafta sonu 15, 16, 17. Damgalar UTC olsaydı dip yerel 06:00'ya denk gelirdi. Hafta içi sabah tepesi beklenenden biraz erken, dolaylı kanıt olduğu için varsayım olarak kalıyor |
| Boşlukların nedeni | Bilinmiyor | Veri seti sayfasında açıklama bulunamadı |
| USGS tamlığı | Düzeltildi: M4,5 | USGS atölye materyali: ComCat dünya genelinde M4,5'e kadar tam. M4-4,5 eksik olabilir |
| Marmara M>=2,5 için 0 kayıt | Beklenen | Küçük depremler USGS'de eksik |
| AFAD API | Kısmen doğrulandı | Topluluk dokümanı eski tarih sorgularını gösteriyor, bizim denememizde geçmiş boş döndü (1 Ekim 2026 ve öncesi 0, 29 Ekim sonrası var). Resmî doküman bulunamadı. Kullanılmıyor |
| Eşikler (0,9 kapsam, 0,5 yoğunluk, 3,5 z, %15 günlük) | Tasarım seçimi | Nisan 2023 üzerinde ayarlandı. Ocak-Şubat 2023 ve Ocak 2024 ayarda kullanılmadı |
| Open-Meteo | Yeniden doğrulanmadı | Reanalysis, tek nokta, istasyon ölçümü değil (kodda belirtilmiş) |
| Seçim tarihleri (14 ve 28 Mayıs 2023) | Önceki oturumda aramayla doğrulandı | Bu oturumda tekrar kontrol edilmedi |
| Kurban Bayramı | Kapsam dışı | Pilot dönem dışında |

## Düzeltilen eski ifadeler
- "Hiçbir ayda boşluksuz veri yok": yanlış, Şubat 2023 boşluksuz.
- "21 eksik blok": 24 olmalı.
- "USGS M4 üstü tam": M4,5.
- "Pilotta deprem vakası yok, 6 Şubat verisi indirilmedi": 6 Şubat verisi indirildi, trafikte belirgin iz yok.

## Tool calling testleri (yerel modeller)
| Test | Sonuç |
|---|---|
| qwen3:4b, 3 vaka, 3 prompt sürümü | V0 (genel prompt) 1/3, V1 (kısa ve katı prompt) 3/3. Düşünme bastırılamadı: 475-1088 token, 59-210 sn/çağrı. V0'daki bir başarısızlık kontrolün fazla katı olmasındandı (ertesi gün 00:00) |
| qwen2.5:3b, 3 vaka, V1 ve V2 | İkisi de 3/3, 7-10 sn (ilk çağrı 32 sn, model yükleme). Örnek konuşma (V2) fark yaratmadı, V1 kullanılıyor |
| qwen2.5:3b, 10 vaka (7 İngilizce, 3 Türkçe) | 9/10. Başarısız: "kanıt topla" sorusunda tek araç çağırdı ve başlangıç tarihini bir gün kaydırdı. Takvimde saatsiz tarih, hava ve depremde 23:59 yazdı (araçlar kabul ediyor) |
| qwen2.5:3b, araç sonucu yorumu | Tek örnek (ETL), doğru okudu. Genelleme yapılamaz |
| qwen2.5:3b, 4 vakalık araç planlama döngüsü | 2-4 araç çağırdı, sıra her vakada farklı. A (bayram) vakasında takvimi, D (6 Şubat) vakasında ETL, hava ve depremi atladı. B'de pencereyi iki kez yanlış yazdı. Karar: araç seçimi ve pencere kodda |
| gemma3:4b, qwen3:1.7b | Bu testte denenmedi |

Sınırlar: örneklem küçük, beklentileri biz yazdık, sorular çoğunlukla kolay ve İngilizce, tek prompt ailesi denendi.

## RAG testleri (5-11 Kasım)
| Test | Sonuç |
|---|---|
| Embedding modeli, 10 soru, 30 parça | embeddinggemma ilk sonuç 9/10, ilk 3'te 10/10; nomic-embed-text 8/10 ve 8/10. Beklentileri biz yazdık, örneklem küçük |
| Chroma mesafesi | numpy ile doğrulandı, uyumsuz 0 |
| Cevabı olmayan sorular | Mesafe tek başına ayırmıyor: konuya yakın ama cevabı olmayan sorular 0,47-0,64, cevabı olanlar 0,31-0,64. Yalnızca konu dışı sorular 0,75 üstü |
| Kapsam notu (kb/kapsam_ve_sinirlar.md) indekse eklenince | İlk sonuç doğruluğu 9/10'dan 7/10'a düştü (not iki sorunun ilk sırasını aldı). Çözüm: not aramadan hariç, her zaman bağlamda |
| qwen2.5:3b ile serbest RAG cevabı, 7 soru | Kapsam içi 2/3, cevabı olmayan 3/4, konu dışı 2/2 (eşikle). İki yanlış: Ramazan Bayramı için "veri yok" dedi (not tersini söylüyor); Kurban Bayramı'nı 22 Nisan 2023'te sandı |
| Karar | RAG kaynaklı notu olduğu gibi getirir, LLM serbest cevap üretmez |
Sınırlar: örneklem çok küçük, beklentileri biz yazdık, prompt ve bağlam düzeni ayrıca denenmedi, kapsam notu hariç tutulduktan sonra ilk sonuç doğruluğu yeniden ölçülmedi.

## RAG ölçümleri (geliştirme seti)
| Ölçüm | Sonuç |
|---|---|
| KB doğrulaması (kb_check.py) | 57/57. İlk KB'de 4 hata bulunup düzeltildi: kapsam notu çelişkisi, Kurban Bayramı tarihi (Temmuz'a taşıyor), Bolu depremi tarihi (yalnızca 16 Mart), hız yüzdesinin yalnızca Nisan 2023'e ait olması |
| Geliştirme seti, v1 (34 soru, 52 parça) | Cevaplı 20 soruda ilk sonuç 16/20, ilk 3 19/20, MRR 0,867. Kapsam soruları 3/6. AUC 0,988 (cevapsızlar kolaydı) |
| Zor cevapsız sınıf eklenince (40 soru) | AUC 0,800: konuya yakın cevapsız soruların mesafesi (0,38-0,56) cevaplı soruların aralığında. N10 ve N11 kısmen cevaplanabilir, etiketleri tartışmalı |
| v2 (Türkçe araç başlıkları) | İlk sonuç 17/20, ilk 3 19/20, MRR 0,900. Fark tek soru (A08), gürültüden ayırt edilemez. A09 başlıkla düzelmedi, nedeni bilinmiyor |
| Kapsam kararı | Getirme ile 3/6, kodda (scope.py) 27/27 birim test (testleri biz yazdık) |
Sınırlar: soruları ve etiketleri aynı kişi yazdı, ayarlar sonuçları gördükten sonra yapıldı, bağımsız test seti (12 soru) henüz çalıştırılmadı. pip check: holidays python-dateutil<3 ister, chromadb (kubernetes) >=3 ister; testler geçiyor ama kırılgan.

## RAG dondurulmuş test seti (11 Kasım, tek seferlik)
| Ölçüm | Sonuç |
|---|---|
| Cevaplı 14 soru (tam hat, k=5) | Yanlış ret 0/14. İlk sonuç 11/14, ilk 3'te 14/14, MRR 0,893. Üç soruda doğru not ikinci sıradaydı (F07, F09, F14) |
| Kapsam dışı 4 soru | 4/4 out_of_scope. F16 (İzmir) ve F18 (konser) scope.py listelerinde zaten bulunan sözcüklerle yazılmıştı, bu ikisi bağımsız kanıt değil. F15 ve F17 genel mantığı sınıyor |
| Konu dışı 3 soru | 3/3 off_topic (mesafe 0,774-0,846, eşik 0,70) |
| KB'de olmayan 3 soru (F19-F21) | Üçü de status=ok döndü, getirilen notların hiçbiri soruyu cevaplamıyor. Mesafeleri 0,46, 0,54 ve 0,69, cevaplı soruların aralığında (0,34-0,64). Bilinen sınır: ok yalnızca ilgili not demektir, cevap var demek değildir. Cevabı araçlar üretir |
Sınırlar: soruları KB'yi ve geliştirme sonuçlarını bilen biri yazdı, set bağımsız değil. Sonuç görüldükten sonra ne soru ne kod değiştirildi. Örneklem küçük: 11/14 için yaklaşık %95 aralık %52-92. Kapsam kuralları liste tabanlı, listede olmayan olay veya şehir geçer. A09 türü ifadelerde ("beklenen düzey") getirme hâlâ riskli.

## RAG zincir doğrulaması (11 Kasım, geliştirme seti)
| Ölçüm | Sonuç |
|---|---|
| KB, parça, embedding, Chroma (rag_pipeline_check.py, LLM yok) | 10/10. 52 benzersiz parça, saklanan metin KB ile birebir, vektörler 768 boyutlu, saklanan vektör yeniden üretilenle aynı (cos 1,0), her parça kendi vektörüyle sorgulanınca kendini buluyor (52/52) |
| LLM, yalnızca getirilen 3 notla JSON cevap (20 cevaplı soru) | Otomatik: JSON 20/20, kaynak geçerli 20/20, sayılar notta 18/20. Elle okuma (yazarın değerlendirmesi): iyi veya kabul edilebilir 7, gereksiz ret 4 (A01, A11, A17, A20), doğru ret 1 (A09), zayıf veya yanlış 8 |
| Cevapsız sorular (5, kodun reddetmediği) | 4 doğru ret, 1 uydurma (N08: "8 Şubat 2023" hiçbir notta yok) |
| Otomatik kontrolün açığı | A06: "Hangi ayda eksik yok?" sorusuna "Kasım 2023" dedi, doğrusu Şubat 2023. Kontrol yalnızca rakamlara baktığı için geçti. Ay adları ve tarihler denetlenmiyor |
| Karar | LLM serbest cevap üretmez. Yalnızca kodun hesapladığı bulguları açıklar, sayı, tarih ve ay adı kanıtta yoksa şablona düşülür |
Sınırlar: soruları ve değerlendirmeyi aynı kişi yaptı, set bağımsız değil, elle sınıflandırmada A04, A15 ve A16 tartışmalı.

## Cevap katmanı v1 (11 Kasım, geliştirme seti)
| Ölçüm | Sonuç |
|---|---|
| answer.py, 20 cevaplı soru | 9 llm_validated, 11 extractive (7'sinde model "cevap yok" dedi, cevap notlardaydı) |
| Cevapsız sorular (9) | Yanlışlıkla llm_validated 0. 4 kodda reddedildi, 5 not listesine düştü |
| Doğrulayıcı | A06 "Kasım 2023" uydurmasını yakaladı. A05'te doğru "88 saat" cevabı yanlış notu kaynak gösterdiği için atıldı |
| llm_validated 9 cevabın elle okunması (yazarın değerlendirmesi) | İyi veya kabul edilebilir 4 (A02, A07, A13, A14), tartışmalı 2 (A03, A15), yanlış veya yanıltıcı 3 (A04, A08, A10). A04: deprem notundaki UTC+3 bilgisi trafik damgalarına uygulandı, sayı kontrolü geçti |
| Karar | Varsayılan cevap extractive (birebir not + kaynak). llm_validated varsayılan değil. Doğrulayıcı sayı ve ay adını denetler, not karışıklığını ve mantık hatasını denetlemez |
Sınırlar: geliştirme seti, soruları ve değerlendirmeyi aynı kişi yaptı, örneklem küçük, A03 ve A15 sınıflandırması tartışmalı.

## RAG durumu (11 Kasım)
| Ölçüm | Sonuç |
|---|---|
| Hava-yağış korelasyonu | Pearson r = -0,418, n = 12 hafta, permütasyon p = 0,183: anlamlı bulunmadı, keşifsel. KB notu buna göre güncellendi |
| Uçtan uca testler (rag_e2e_strict.py) | 24/24 kapı: indeks ve metin bütünlüğü, kb_check 57/57, getirme gerilemesi, atıf bütünlüğü, determinizm, Ollama kapalı hatası, bayat indeks, CRLF/BOM |
| Dondurulmuş test seti, ilk çalıştırma (12 soru, soruları KB'yi bilen biri yazdı) | Cevaplı 8: ilk 3'te 7/8, ilk sonuç 6/8, MRR 0,792. Başarısız: H07 ("doğrulanmış kök neden var mı?", doğru not ilk 3 dışında). Kapsam dışı 1/1, konu dışı 1/1. H11 (rüzgâr sorusu) status=ok döndü, getirilen notlar cevap vermiyor |
| KB yeniden yazımı (başlıklı uzun sürüm) | Denendi, geri alındı: satır bazlı parçalayıcı başlıkları ayrı parça yapar, etiketler kayar |
| LLM cevap yolu (answer.py --llm) | Ürün iddiası değil. Teste özel kurallar eklenmişti, geri alındı. Varsayılan: kaynaklı not getirme (extractive) |
Sınırlar: soruları KB'yi bilen biri yazdı, küçük örneklem, dondurulmuş set bir kez çalıştı ve ayar için kullanılmadı. status=ok ilgili not demektir, cevap garantisi değil: ölçüm gerektiren sorular araçlarla cevaplanır. pip check: holidays ve chromadb/kubernetes python-dateutil sürümü konusunda çelişiyor, testler geçiyor ama kırılgan.

## RAG araç notları (11 Kasım)
| Ölçüm | Sonuç |
|---|---|
| rag_tool_notes_test.py | 25/25: 5 aracın tüm KB notları eksiksiz ve sıralı geliyor, metin KB ile aynı, kapsam notu karışmıyor, bilinmeyen araç hata veriyor, determinizm, Ollama kapalıyken çalışıyor, bayat indekste hata veriyor |
| rag_e2e_strict.py (v3 sonrası) | 24/24 |
| scope.py | 33/33 birim test (seçim günü kalıbı eklendi, "deprem seçim kuralı" gibi ifadeler engellenmiyor) |
Sınırlar: testleri biz yazdık. Araç notlarının KB'deki doğruluğu kb_check ile veriden doğrulanıyor, notların rapor için yeterli olup olmadığı ajan aşamasında ölçülecek.
