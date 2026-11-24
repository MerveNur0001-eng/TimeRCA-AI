# 02 - Mimari

## Akış ve durum
1. ETL (ingest.py): İBB CSV -> kontroller -> saatlik seri (parquet) + logs/etl_log.jsonl. [tamam]
2. Tespit: baseline = önceki 4 haftanın aynı gün-saati medyanı (en az 3 geçerli hafta) + log-oran üzerinde MAD z-skoru (detect.py, saat bazlı) ve günlük düzey kontrolü (daily_level.py). [tamam; aday listesi: src/scan.py (gün düzeyi), saatlik bölgeler: src/series.py (yalnız gösterim, karar kuralı değil)]
3. Araçlar (src/tools.py): deterministik Python fonksiyonları. [tamam; MCP sunucusu üzerinden de sunulur, bkz. Araç katmanı]
4. LangGraph: toplama -> hipotez değerlendirme -> kaynaklı not -> insana sor -> ek inceleme -> rapor (src/agent.py). [tamam]
5. Güven düşükse insana soru (HITL, interrupt). [tamam]
6. Çıktı: Pydantic ile doğrulanan JSON rapor, kaynak referanslarıyla. [tamam]

## Araçlar
Her araç sade giriş (start, end), JSON'a çevrilebilir çıktı ve kendi sınırını söyleyen bir "limits" alanı döndürür.
- check_etl_log: ETL logunu okur (eksik saat blokları, hücre kapsamı, yoğunluk şüphesi). Pencere ay sınırını aşarsa ilgili tüm ayların logunu okur; logu olmayan aylar months_without_log alanında bildirilir.
- compare_same_weekday_history: benzer gün/saatlerde geçmiş değerler. ETL'de işaretli saatleri ayırır, baseline günlerini döndürür.
- get_weather: Open-Meteo saatlik yağış, rüzgâr, sıcaklık (tek nokta, reanalysis).
- get_calendar: holidays paketi ile resmî tatil/bayram.
- get_earthquakes: USGS FDSN, önceden indirilmiş yerel katalog (AFAD canlı API'si geçmiş sorgulara boş döndü). İlgili deprem kuralı: M>=4,5 ve İstanbul'a <=500 km, veya M>=6,5 her mesafe. Eşikler seçimdir, trafik etkisi için bilinen bir eşik değildir. Zaman sırasına bakılır, büyüklük ve mesafe tek başına nedensellik göstermez.
- Kapsam: MONTHS = 18 yüklü ay (bkz. 03-veri.md); deprem kataloğu QUAKE_COVER aralıkları (Kas 2021-Oca 2022, Eyl-Kas 2022, Şub 2023-Oca 2024, Mar-Nis 2024). Listede olmayan aylar (ör. Ekim 2023, Şubat 2024) için baseline eksik kalabilir.

## Model ve altyapı
- LLM (Ollama, yerel, CPU, 15,8 GB RAM, aynı anda tek model): ajan akışında LLM karar vermez, araç seçmez, hipotez puanlamaz. Kullanıldığı yerler: (1) soru kutusunda, yalnız kural tarihi bulamazsa, gemma3:4b ile soru anlama (src/soru_llm.py; tarih sorunun metnine bağlanarak doğrulanır); (2) komut satırında `agent.py --llm` ile gemma3:4b Türkçe açıklama (src/llm_explain.py; sayı ve tarih doğrulaması tutmazsa kural metni gösterilir), panelde yoktur. Eski denemeler ürün yolunda DEĞİLDİR, toolcall_*.py ve agent_loop_test.py betiklerinde kalmıştır: qwen2.5:3b tool calling testinde 10 vakanın 9'u doğru; qwen3:4b elendi (think=false ve /no_think ile bile 475-1088 token, 59-210 sn/çağrı); 4 vakalık araç planlama döngüsünde LLM araçların 2-4'ünü çağırdı ve iki vakada kritik aracı atladı. Bu yüzden araç seçimi ve zaman penceresi kodda sabittir.
- RAG: Chroma (yerel dosya modu) + embeddinggemma (Ollama). kb/ altında 9 kısa Türkçe not, satır bazlı 52 parça, her not kb_check.py ile veriden doğrulanıyor (57 kontrol). Karar: RAG ilgili notu olduğu gibi ve kaynak dosyasıyla getirir; LLM serbest cevap üretmez (qwen2.5:3b testinde 7 sorunun 2'sinde bilgi tabanıyla çelişen cevap verdi). Mesafe yalnızca belirgin konu dışı soruları ayırır (eşik 0,70, yaklaşık). 'Bilgi tabanında cevap var mı' ve kapsam kararı mesafeyle verilemiyor: kapsam kararı kodda (src/scope.py: tarih, bayram, il, olay türü).
- MCP: tamam, bkz. aşağıda 'Araç katmanı (MCP)'.
- Güvenlik: araç çıktıları veri olarak ele alınır, talimat olarak değil. Araç çıktılarındaki dış metin alanları (ör. USGS place) bu yüzden önemli.

## Kural
Kanıt yoksa kök neden uydurulmaz. Sonuç "açıklanamayan" olabilir.

## Ajan akışı (uygulandı)
1. Anomali penceresi dedektör veya kullanıcı tarafından belirlenir.
2. Kod ETL logu ve geçmiş karşılaştırma araçlarını her pencerede çalıştırır; belirgin sapma varsa hava, takvim ve deprem araçlarını da çalıştırır (evidence.context_plan).
3. Kod hipotezleri puanlar ve güven düzeyini hesaplar.
4. Belirsiz veya çelişkili bulguda LangGraph interrupt ile insana soru sorulur.
5. İnsana sorulacak soru alanları (pencere, güven, destekleyen ve belirsiz nedenler) koddan gelir; LLM yazmaz.
6. Rapor Türkçe şablonla üretilir, Pydantic ile doğrulanır.
7. Serbest soru modu: kural soruyu bir pencereye çevirir; kural çözemezse doğrulamalı LLM soru anlama denenir. Pencereyi kod doğrular, analiz mevcut ajanı çağırır.

## RAG v3: araç notları
- Rapora giren yorumlama ve sınır notları anlamsal arama ile değil, metadata ile seçilir: `tool_notes(arac)` aracın KB'deki tüm notlarını sırasıyla getirir, `notes_for_tools([...])` çalışan araçlar için tekrarsız birleştirir. Embedding kullanmaz, Ollama kapalıyken de çalışır.
- `HYP_TOOLS`: hipotez -> kanıt araçları eşlemesi (veri_hatasi: check_etl_log, compare_same_weekday_history; hava: get_weather; tatil: get_calendar; deprem: get_earthquakes; aciklanamayan: compare_same_weekday_history).
- Serbest soru yolu (`answer_context`) yardımcı olarak kalır: kapsam kontrolü (scope.py) ve kaynaklı ilgili not getirme. `status=ok` ilgili not demektir, cevap garantisi değildir. Ölçüm isteyen sorular araçla cevaplanır.
- RAG bu noktada dondurulmuştur: yalnızca test bozukluğu bulunursa değişir.

## Giriş katmanı (src/router_graph.py, src/ask.py, api.py /ask)
Kullanıcı yalnızca soru yazar. Yönlendirme önce sabit kuraldır. Kural tarihi bulamazsa (analiz kalıbı var, tarih yok) ya da tarihli bir bilgi sorusu gelirse LLM (gemma3:4b, src/soru_llm.py) yalnız soruyu {niyet, başlangıç, bitiş} yapısına çevirmeyi dener; tarihin yılı, günü ve ayı sorunun metninde yazılı olmak zorundadır, doğrulama geçmezse ya da Ollama yoksa kural cevabı kullanılır. Kural zaten analiz diyorsa LLM çağrılmaz; TIMERCA_SORU_LLM=0 ile kapatılır. Kural: soruda analiz kalıbı (ör. "neden düş", "niçin düş", "anomali", "incele", "ne oldu") ve bir tarih varsa pencere analizi; analiz kalıbı var ama tarih yoksa tarih istenir; diğer her soru bilgi yoludur (RAG, kapsam ve konu dışı reddi dahil). Türkçe karakterler katlanır, "dustu" ve "düştü" aynı yola gider. Analiz yolu mevcut ajanı api.analyze üzerinden çağırır (/analyze ile aynı kod yolu ve HITL). İnsan onayı gerekirse soru gösterilir, karar (onayla, ek_inceleme, reddet) alınıp devam edilir.
- Tarih biçimleri: YYYY-MM-DD, GG.AA.YYYY, "10 Nisan 2024". Tek tarih tam gün sayılır, saat verilemez. En fazla 7 gün. Ayın N. haftası (kural, LLM değil) = ayın (N-1)×7+1 ile N×7. günleri, ay sonuna kırpılır; takvim haftası değildir. Gün aralığı "8-14 Ocak 2024" desteklenir. "Anomali var mıydı" gibi var mı soruları çok günlü pencerede gün gün tarama (scan.py) ile cevaplanır, neden aranmaz. Tarih yüklü trafik verisinin dışındaysa ajan çağrılmaz.
- HTTP: POST /ask {"soru": ..., "karar": ..., "karar2": ...}. TIMERCA_API_KEY tanımlıysa X-API-Key zorunludur.
- MCP: araç çağrıları logs/mcp_calls.jsonl dosyasına (araç, argüman, süre, hata) yazılır; stdout'a yazılmaz çünkü stdio protokol kanalıdır.
- Testler: tests/router_test.py, tests/router_plan_test.py.

## Araç katmanı (MCP)
Beş araç (check_etl_log, compare_same_weekday_history, get_weather, get_calendar, get_earthquakes) src/mcp_server.py içinde MCP sunucusu olarak yayınlanır (stdio). Ajanın toplama adımı (agent.collect, extra_review) ve karar veren kod (evidence.py, report.py) araçları src/tools_gw.py geçidi üzerinden çağırır. Geçit, src/mcp_client.py ile MCP sunucusuna bağlanır.
- Mod: TIMERCA_TOOLS=mcp (varsayılan) veya direct (doğrudan tools.py). MCP hata verirse logs/agent_log.jsonl'a mcp_fallback yazılır ve doğrudan çağrıya düşülür.
- Önbellek: geçit, bir pencere için ilk çağrıda 5 aracı tek MCP oturumunda getirir ve bellekte tutar. Hatalı sonuçlar önbelleğe alınmaz.
- İz: her MCP araç çağrısı logs/mcp_calls.jsonl dosyasına yazılır (araç, argüman, süre, hata).
- Doğrulama: mcp_test.py ve mcp_stdio_test.py MCP çıktısının doğrudan çıktıyla eşdeğerliğini sınar. agent_test 37/37 her iki modda geçer.

## Tetikleyici (n8n)
Akış docs/n8n-akisi.json dosyasıdır (n8n'de Import from File). Docker'daki n8n, host üzerindeki API'yi http://host.docker.internal:8000/ask adresinden çağırır. API `python src\api.py --host 0.0.0.0` ile başlatılır.
- Düğümler: Manuel tetikleyici, SORU, ILK ISTEK (POST /ask), BEKLIYOR MU (sonuc.tip == bekliyor). false kolu: rapor otomatik tamamlanmıştır. true kolu: ONAY FORMU (Wait düğümü, On Form Submitted; onayla / ek_inceleme / reddet; soru, pencere, güven, belirsiz hipotezler ve notlar formda gösterilir), KARAR (aynı soru ve karar), EK INCELEME MI, EK ONAY FORMU (onayla / reddet), KARAR 2 (karar ve karar2).
- İnsan onayı gerçektir: akış formda durur, karar gelmeden devam etmez. API durumsuzdur, her çağrıda ajan yeniden koşar ve kararlar sırayla (karar, karar2) gönderilir.
- API anahtarı JSON'da yoktur. n8n Credentials içinde Header Auth (X-API-Key) olarak tutulur.
- Bilinen sınırlar: tetikleyici manueldir (canlı veri akışı yok). API ThreadingHTTPServer kullanır; analiz (POST) istekleri tek kilitle sıralanır, aynı anda tek analiz çalışır (docs/14). Demo anahtarı basittir, dağıtıkta değiştirilmelidir.

## Anomali taraması ve grafik (src/scan.py, src/series.py)
- scan.py: tarih aralığını (en fazla 62 gün) gün gün önceki 4 haftanın aynı günü ile karşılaştırır. Eşikler evidence.py ile aynıdır (oran < 0.85 veya > 1.15; eksik saat oranı >= 0.25). Durumlar: normal, düşüş, artış, eksik veri, eksik veri + sapma, veri yok, değerlendirilemedi. Tarama yalnızca aday listesi üretir, nedeni ajan araştırır. HTTP: POST /scan.
- series.py: grafik verisi. Saatlik görünüm en fazla 14 gün, günlük görünüm en fazla 62 gün. Baseline tools.py ile aynıdır (önceki 4 haftanın aynı gün-saati medyanı, en az 3 geçerli hafta). ETL'nin işaretlediği saatler (düşük hücre kapsamı, yoğunluk şüpheli) bölge ve gün oranı hesabına girmez, grafikte gri şeritle gösterilir; böylece veri kapsamı çöküşü gerçek trafik düşüşü gibi çizilmez. En az 3 ardışık saat bant dışındaysa bir bölge işaretlenir. Bu işaretleme YALNIZCA GÖSTERİMDİR, karar kuralı değildir. Bölgeler saat sayısı x sapma büyüklüğüne göre sıralanır, ilk 5 gösterilir. Kısa bölgelerin sıradan olduğu, yüklü veriden hesaplanan taban oranıyla (394 gün: günlerin %60'ında en az bir bölge başlar, 12 saati aşan bölge yaklaşık 23 günde bir) arayüzde yazılıdır. HTTP: POST /series.
- Tutarlılık testi: tests/series_real_test.py gerçek veride grafik sayılarının tools.py çıktısıyla aynı olduğunu sınar (sentetik veri yok).

## Arayüz (src/ui/index.html, GET /)
Tek sayfa: trafik yoğunluğu grafiği, anomali taraması, pencere incelemesi, insan onayı (Onayla / Ek inceleme / Reddet), ret nedeni formu, soru kutusu. Grafikte bir güne veya bölgeye tıklamak pencereyi doldurur ve ajan incelemesini başlatır. Dış metinler DOM metin düğümü olarak yazılır (innerHTML kullanılmaz): araç çıktısı ve kullanıcı metni talimat veya kod olarak yorumlanmaz. API anahtarı alanı vardır (TIMERCA_API_KEY tanımlıysa X-API-Key zorunlu). Geçersiz veya boş zaman 400 döner.

## İki aşamalı araç seçimi
ETL logu ve geçmiş karşılaştırma araçları her pencerede çağrılır. Sonra evidence.context_plan(cmp) karşılaştırma çıktısına bakar: belirgin sapma yoksa hava, takvim ve deprem araçları çağrılmaz; çağrılmayan araç ve nedeni rapordaki arac_plani alanına ve "Araç çağrılmadı: ..." satırına yazılır. Çağrı seçimi kodla yapılır, LLM planlamaz. Karar çıktısını değiştirmez (sapma yoksa nedenler zaten değerlendirilmiyordu). Test: selection_test.py (18 kapı). MCP geçidi (tools_gw.py) aşamalı oturum açar.

## Rapor katmanı eklemeleri
- olasi_nedenler: sabit öncelik sırasıdır, OLASILIK DEĞİLDİR. Her satırda kanıt türü (kanit_turu) ve nedensellik notu bulunur (hava, tatil, deprem bulguları zamansal çakışmadır).
- kaynak_bilgisi: çağrılan her aracın kaynağı, kapsamı ve sınırı.
- saatlik_bilgi: bilgi amaçlı; karar kuralını değiştirmez.
- genel_degerlendirme: birden fazla etken destekleniyorsa bunu açıkça söyler (coklu_neden), payları ayrıştırılamayacağını belirtir, olasılık vermez; kapsam_siniri (etkinlik, yol çalışması, okul tatili dışlanmış sayılmaz). Karar çıktısını değiştirmez. Test: reliability_test.py (27 kapı).
- karisik_durum (karar kuralı): pencerenin en az %25'i kaynak dosyada eksikse ve sapma kalan temiz saatlerde sürüyorsa güven düşük, insan gerekli. Bu kural v3 etiketinden SONRA eklendi, bkz. docs/09 bölüm 10.

## Geri bildirim kaydı (src/feedback.py)
İnsan bir raporu reddedince ret nedenini bir iddia olarak girer (iddia, açıklama, kaynak). İddia araç kanıtıyla sınanır ve sonuç kayda yazılır. Kayıtlar SQLite'tadır (logs/feedback.sqlite). Ajan bundan ÖĞRENMEZ, kullanıcı düzeltmesini otomatik kabul etmez ve sistemin kararını değiştirmez. HTTP: POST /feedback. Test: feedback_test.py (27 kapı).

- Ret kolu: EK INCELEME MI false kolu ve KARAR 2 çıktısı RET MI düğümüne gider (sonuc.nihai_durum == reddedildi). RET FORMU (iddia seçimi, açıklama, kaynak) doldurulunca GERI BILDIRIM düğümü /feedback ucuna POST eder (pencere, ILK ISTEK düğümünden alınır). Akış 12 düğümdür. DURUM: ret kolu 23 Kasım 2026'da n8n içinde denendi (Reddet, ret formu, /feedback kaydı döndü; test kaydı silindi). API anahtarı kullanılacaksa Header Auth (X-API-Key) credential'ı elle atanmalıdır.
